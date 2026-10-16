"""
Shared LLM configuration.

Two chat providers, both spoken to through the `openai` SDK:
- Azure OpenAI (AZURE_OPENAI_* vars): chat, vision and embeddings.
- Hugging Face Inference Providers (HF_TOKEN): free-tier chat via the
  OpenAI-compatible router at https://router.huggingface.co/v1. Text only;
  embeddings fall back to local MiniLM (see rag_pipeline).

LLM_PROVIDER=auto|azure|huggingface (default auto: Azure if configured, else
Hugging Face if HF_TOKEN is set, else none -> offline rules/extractive answers).

Env vars are read at call time (not import time) so load_dotenv() ordering
in the entry points does not matter.
"""
import os
from dataclasses import dataclass
from openai import AzureOpenAI, OpenAI

DEFAULT_API_VERSION = "2024-02-15-preview"
PLACEHOLDER_MARKERS = ("your-key", "your_key", "hf_your")

HF_BASE_URL = "https://router.huggingface.co/v1"
# Not gated, supports JSON output; ~$0.001 of free monthly credit per extraction (3 runs)
HF_DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"

@dataclass
class ChatBackend:
    client: object
    model: str
    provider: str  # 'azure' | 'huggingface'

def _clean_endpoint(endpoint):
    """Accept either the resource URL or a full deployment URL copied from the portal."""
    if not endpoint:
        return None
    endpoint = endpoint.split("/openai/deployments")[0]
    return endpoint.split("?")[0]

def _real(value):
    return bool(value) and not any(marker in value for marker in PLACEHOLDER_MARKERS)

def is_configured():
    """True when Azure OpenAI credentials are present (Azure-only features: vision OCR, embeddings)."""
    return _real(os.getenv("AZURE_OPENAI_API_KEY")) and bool(_clean_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT")))

def hf_configured():
    return _real(os.getenv("HF_TOKEN"))

def get_client():
    """Return an AzureOpenAI client, or None when credentials are missing/placeholders."""
    if not is_configured():
        return None
    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
        azure_endpoint=_clean_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT")),
    )

def get_chat_backend():
    """
    Chat-completion backend for extraction and RAG answers, or None.
    Both providers expose client.chat.completions.create(model=..., messages=...).
    """
    provider = (os.getenv("LLM_PROVIDER") or "auto").lower()
    if provider in ("auto", "azure") and is_configured():
        return ChatBackend(get_client(), chat_deployment(), "azure")
    if provider in ("auto", "huggingface", "hf") and hf_configured():
        client = OpenAI(base_url=os.getenv("HF_BASE_URL") or HF_BASE_URL, api_key=os.getenv("HF_TOKEN"))
        return ChatBackend(client, os.getenv("HF_MODEL") or HF_DEFAULT_MODEL, "huggingface")
    return None

def chat_deployment():
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

def embedding_deployment():
    return os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
