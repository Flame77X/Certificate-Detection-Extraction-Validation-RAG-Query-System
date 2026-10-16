"""
Shared Azure OpenAI configuration.

Env vars are read at call time (not import time) so load_dotenv() ordering
in the entry points does not matter.
"""
import os
from openai import AzureOpenAI

DEFAULT_API_VERSION = "2024-02-15-preview"
PLACEHOLDER_MARKERS = ("your-key", "your_key")

def _clean_endpoint(endpoint):
    """Accept either the resource URL or a full deployment URL copied from the portal."""
    if not endpoint:
        return None
    endpoint = endpoint.split("/openai/deployments")[0]
    return endpoint.split("?")[0]

def is_configured():
    key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = _clean_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT"))
    if not key or not endpoint:
        return False
    return not any(marker in key for marker in PLACEHOLDER_MARKERS)

def get_client():
    """Return an AzureOpenAI client, or None when credentials are missing/placeholders."""
    if not is_configured():
        return None
    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
        azure_endpoint=_clean_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT")),
    )

def chat_deployment():
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

def embedding_deployment():
    return os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
