from copy import deepcopy

from aiogram.dispatcher import FSMContext

OPENAI_FUNCTIONS = [
    {
        "name": "search_in_document_query",
        "description": "This function is designed to execute an information search in a specific document using a query string. Use this function if a user asks about information that may be contained in provided documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "ID of a relevant document",
                },
                "query": {
                    "type": "string",
                    "description": "Detailed search query based on user's request",
                }
            },
            "required": ["document_id", "query"]
        }
    },
    {
        "name": "website_request",
        "description": "This function is designed to parse information from a website using a given URL from user's request or communication history. Don't make assumptions about the URL, ask for clarification.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the website",
                }
            },
            "required": ["url"]
        }
    }
]


async def build_openai_functions(state: FSMContext):
    """Formats documents' descriptions from user vector db into OPENAI_FUNCTIONS"""
    current_data = await state.get_data()
    personal_functions = deepcopy(OPENAI_FUNCTIONS)
    if not current_data.get('documents'):
        personal_functions.pop(0)
    return personal_functions
