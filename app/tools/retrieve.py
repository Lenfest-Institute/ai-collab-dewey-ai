from typing import Dict, Any
from textwrap import dedent

def load_search_prompt(current_date: str) -> str:
    return dedent(f"""
        The assistant is Dewey, created by The Philadelphia Inquirer.

        The current date is {current_date}.

        Dewey is a librarian that assists users in finding news articles to answer their questions. Dewey has access to a corpus of news articles spanning from January 2, 1978 to today. This corpus only contains articles written by The Philadelphia Inquirer. This corpus is searchable via a question, and filterable by both dates and authors.

        When a user asks a question, Dewey is responsible for performing a search to this corpus. The search will include a always include a question based on the user's question and conversation history. The search question should always be a full sentence. It should not include information used as filter criteria. Assume any questions are about the Greater Philadelphia Region.

        If a user asks for articles from certain time periods, Dewey should include them as filters in the search criteia. Nevermind any vague time period referenced like "lately" or "recently". If the user asks for articles written by specified authors, Dewey should also use them as filters in the search criteia.
    """).strip()

def load_search_tool() -> Dict[str, Any]:
    """
    Provides the schema for the search function that retrieves news articles
    from The Philadelphia Inquirer's archives. The tool generates an optimized query,
    date range, and list of authors based on the user's input.
    """
    return {
            "type": "function",
            "name": "search_archive",
            "description": "Retrieves news articles from The Philadelphia Inquirer's archives using the user's query and metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string", 
                        "description": "The semantic search query text to find relevant articles."
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start_date": {
                                "type": ["string", "null"],
                                "description": "The start date of the user's query in ISO format (YYYY-MM-DD)",
                            },
                            "end_date": {
                                "type": ["string", "null"],
                                "description": "The end date of the user's query in ISO format (YYYY-MM-DD)",
                            }
                        },
                        "required": ["start_date", "end_date"],
                        "additionalProperties": False,
                    },
                    "authors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Full journalist name"}
                            },
                            "additionalProperties": False,
                            "required": ["name"]
                        },
                    },
                },
                "required": ["question", "date_range", "authors"],
                "additionalProperties": False,
            },
            "strict": True
        }