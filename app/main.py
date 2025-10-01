import gradio as gr
from dotenv import load_dotenv
from dewey import Dewey
from models import AzureSearchConfig, AzureOpenAIConfig
import os
import uuid
import json

load_dotenv()


oai_config = AzureOpenAIConfig(
    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    embedding_deployment=os.environ["EMBEDDING_DEPLOYMENT_NAME"],
    embedding_model=os.environ["EMBEDDING_MODEL_NAME"],
    chat_deployment=os.environ["CHATGPT_DEPLOYMENT_NAME"],
    chat_model=os.environ["CHATGPT_MODEL_NAME"]
)

search_config = AzureSearchConfig(
    service_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
    key=os.environ["AZURE_SEARCH_API_KEY"]
)

dewey = Dewey(oai_config, search_config)


def chat_with_dewey(message, history, session_state):
    # Initialize session if needed
    if session_state["session_id"] is None:
        session_state["session_id"] = str(uuid.uuid4())
        session_state["user_data"]["message_count"] = 0
    
    # Track message count
    session_state["user_data"]["message_count"] += 1
    
    # Add user message to history and show it immediately
    history.append({"role": "user", "content": message})
    yield history, session_state

    
    # Stream the response from Dewey
    history_length = len(history)
    for response, steps in dewey.process(message, history[:-1]):
        history = history[:history_length]
        for step in steps:
            history.append({
                "role": "assistant",
                "content": f"{step.get('content', '')}",
                "metadata": {
                    "title": step["title"],
                    "status": step["status"]
                }
            })
        history.append({
            "role": "assistant",
            "content": response
        })
        
        yield history, session_state

with gr.Blocks(title="Dewey") as demo:
    gr.Markdown("# Dewey")
    gr.Markdown("A newsroom archive assistant.")
    
    # Session state
    session_state = gr.State({"session_id": None, "user_data": {}})
    
    chatbot = gr.Chatbot(type="messages", label="Dewey")
    msg = gr.Textbox(label="Message", placeholder="Ask your question here...")
    clear = gr.Button("Clear")
    
    msg.submit(chat_with_dewey, [msg, chatbot, session_state], [chatbot, session_state])
    msg.submit(lambda: "", None, [msg])
    clear.click(lambda: [], None, [chatbot])

demo.launch()
