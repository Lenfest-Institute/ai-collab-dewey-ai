from openai import AzureOpenAI
from typing import List, Any
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import (
    VectorizedQuery,
    VectorQuery,
    QueryType,
)
from datetime import datetime
from dateutil.parser import parse
from models import DateRange, AzureSearchConfig, AzureOpenAIConfig
from tools import load_search_tool, load_search_prompt, load_answer_prompt
import json
import re
from tips import TipFormatter
from contextlib import contextmanager

class Dewey:
    def __init__(self, openai_config: AzureOpenAIConfig, search_config: AzureSearchConfig):
        # Initialize client connections
        self.oai_client = AzureOpenAI(
            api_key=openai_config.api_key,
            azure_endpoint=openai_config.endpoint,
            api_version="2025-03-01-preview"
        )
        self.search_client = SearchClient(
            search_config.service_endpoint,
            search_config.index_name,
            AzureKeyCredential(search_config.key)
        )

        # Store config for deployment names
        self.openai_config = openai_config
        self.sessions = {}
        self.tip_formatter = TipFormatter

    @contextmanager
    def step(self, title, show_steps=True):
        if not show_steps:
            yield lambda: None
            return
            
        step = {"title": title, "status": "pending"}
        if not hasattr(self, '_current_steps'):
            self._current_steps = []
        
        self._current_steps.append(step)
        
        class StepYielder:
            def __init__(self, step, steps_list):
                self.step = step
                self.steps_list = steps_list
                self.has_started = False
            
            def start(self, content=""):
                if not self.has_started:
                    if content:
                        self.step["content"] = content
                    self.has_started = True
                    return "", self.steps_list.copy()
                return None
            
            def complete(self, content=""):
                self.step["status"] = "done"
                if content:
                    self.step["content"] = content
                return "", self.steps_list.copy()
        
        yielder = StepYielder(step, self._current_steps)
        try:
            yield yielder
        finally:
            step["status"] = "done"

    def generate_metadata(self, messages, current_date: str):
        response = self.oai_client.responses.create(
            model=self.openai_config.chat_deployment,
            input=messages,
            instructions=load_search_prompt(current_date),
            tools=[load_search_tool()],
            tool_choice={"type": "function", "name": "search_archive"},
        )

        return json.loads(response.output[-1].arguments)
    
    def retrieve_articles(self, metadata):
        # Prepare vector query
        vectors: List[VectorQuery] = []

        embedding = self.oai_client.embeddings.create(
            model=self.openai_config.embedding_deployment,
            input=metadata["question"],
        )

        query_vector = VectorizedQuery(vector=embedding.data[0].embedding, k_nearest_neighbors=50, fields="content_vector")

        vectors.append(query_vector)

        # Build filter
        
        # Perform search
        results = self.search_client.search(
            search_text=metadata["question"],
            top=10,
            vector_queries=vectors,
            query_type=QueryType.SEMANTIC,
            semantic_configuration_name="default",
            semantic_query=metadata["question"],
            select=["url", "headline", "publish_date", "content", "authors"]
        )

        sources = []

        for page in results:
            sources.append(json.dumps({
                "url": page["url"],
                "publish_date": f"{parse(page['publish_date']).date().isoformat()}",
                "authors": json.loads(page["authors"]),
                "headline": page["headline"],
                "content":  page["content"].replace("\n", " ").replace("\r", " ")
            }))

        return sources

    def process(self, message: str, history: List, show_steps: bool=True):
        # Reset steps
        self._current_steps = []

        # Grab the current day
        date_today = datetime.now()
        formatted_date_today = date_today.strftime("%A, %B %d, %Y")
        
        # Build messages
        messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Step 1: Generate metadata
        with self.step("Generating metadata", show_steps) as step:
            if result := step.start("🔍 I'm planning my approach."):
                yield result
            metadata = self.generate_metadata(messages, formatted_date_today)
            metadata_tip = self.tip_formatter.tip_metadata(metadata)
            if result := step.complete(metadata_tip):
                yield result
        
        # Step 2: Search articles  
        with self.step("Searching articles", show_steps) as step:
            if result := step.start("🔍 Digging through the archives"):
                yield result
            sources = self.retrieve_articles(metadata)
            sources_tip = self.tip_formatter.tip_search(sources)
            if result := step.complete(sources_tip):
                yield result

        # Step 3: Generate final response with sources
        stacked_sources = '\n\n'.join(sources)
        messages.append({"role": "user", "content": f"{message}\n\n## Sources\n{stacked_sources}"})

        # Create source URL lookup from sources list
        source_urls = {}
        for i, source_json in enumerate(sources, 1):
            source_data = json.loads(source_json)
            source_urls[i] = source_data["url"]
        
        response = self.oai_client.responses.create(
            model=self.openai_config.chat_deployment,
            instructions=load_answer_prompt(formatted_date_today),
            input=messages,
            stream=True
        )

        partial = ""
        for chunk in response:
            if chunk.type == "response.output_text.delta":
                if delta := chunk.delta:
                    partial += delta
                    # Replace citation patterns with hyperlinks
                    processed_partial = re.sub(
                        r'\[SRC(\d+)\]',
                        lambda m: f"[[{m.group(1)}]]({source_urls.get(int(m.group(1)), '#')})",
                        partial
                    )
                    yield processed_partial, self._current_steps.copy()
