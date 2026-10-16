"""
Shared LLM configuration.

Chat providers, all spoken to through the `openai` SDK:
- Azure OpenAI (AZURE_OPENAI_* vars): chat, vision and embeddings.
- OpenAI-compatible APIs for chat only (embeddings fall back to local MiniLM, see rag_pipeline):
  - openrouter  (OPENROUTER_API_KEY): free ':free' models, no card needed.
  - custom      (LLM_BASE_URL + LLM_API_KEY + LLM_MODEL): any OpenAI-compatible API,
                e.g. Groq, Gemini's OpenAI endpoint, or a local Ollama server.
  - huggingface (HF_TOKEN): Inference Providers router; needs paid credits on free accounts.

LLM_PROVIDER=auto|azure|openrouter|custom|huggingface. auto picks the first configured in
AUTO_ORDER; with none configured -> offline rules / extractive answers.

Env vars are read at call time (not import time) so load_dotenv() ordering
in the entry points does not matter.
"""
import os
from dataclasses import dataclass, field
from openai import AzureOpenAI, OpenAI

DEFAULT_API_VERSION = "2024-02-15-preview"
PLACEHOLDER_MARKERS = ("your-key", "your_key", "hf_your", "sk-or-your")

HF_BASE_URL = "https://router.huggingface.co/v1"
HF_DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# $0 models with JSON output support, tried in order via OpenRouter fallback routing: free models are
# often rate-limited upstream (429), so a busy one is skipped. OPENROUTER_MODEL accepts a comma-separated list.
OPENROUTER_DEFAULT_MODEL = ("nvidia/nemotron-3-super-120b-a12b:free,"
                            "google/gemma-4-31b-it:free,"
                            "dots-studio/dots-3-note-preview:free")

# name -> (api key env, base url env or fixed url, model env, default model)
OPENAI_COMPATIBLE = {
    'openrouter': ('OPENROUTER_API_KEY', OPENROUTER_BASE_URL, 'OPENROUTER_MODEL', OPENROUTER_DEFAULT_MODEL),
    'custom': ('LLM_API_KEY', None, 'LLM_MODEL', None),
    'huggingface': ('HF_TOKEN', HF_BASE_URL, 'HF_MODEL', HF_DEFAULT_MODEL),
}
# Free providers first; Hugging Face last because free accounts get 402 (no credits)
AUTO_ORDER = ('azure', 'openrouter', 'custom', 'huggingface')
PROVIDER_ALIASES = {'hf': 'huggingface'}

@dataclass
class ChatBackend:
    client: object
    model: str
    provider: str  # 'azure' | 'openrouter' | 'custom' | 'huggingface'
    # Extra arguments for chat.completions.create (e.g. OpenRouter fallback model list)
    request_kwargs: dict = field(default_factory=dict)

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

def _openai_compatible(name):
    """ChatBackend for an OpenAI-compatible provider, or None if it is not fully configured."""
    key_env, base_url, model_env, default_model = OPENAI_COMPATIBLE[name]
    api_key = os.getenv(key_env)
    base_url = base_url or os.getenv('LLM_BASE_URL')
    models = [m.strip() for m in (os.getenv(model_env) or default_model or '').split(',') if m.strip()]
    if not (_real(api_key) and base_url and models):
        return None
    request_kwargs = {}
    if name == 'openrouter' and len(models) > 1:
        # https://openrouter.ai/docs: 'models' = ordered fallbacks when the first is unavailable/rate-limited
        request_kwargs = {'extra_body': {'models': models}}
    return ChatBackend(OpenAI(base_url=base_url, api_key=api_key), models[0], name, request_kwargs)

def get_chat_backend():
    """
    Chat-completion backend for extraction and RAG answers, or None.
    All providers expose client.chat.completions.create(model=..., messages=...).
    """
    provider = (os.getenv("LLM_PROVIDER") or "auto").lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    for name in (AUTO_ORDER if provider == 'auto' else (provider,)):
        if name == 'azure':
            if is_configured():
                return ChatBackend(get_client(), chat_deployment(), 'azure')
        elif name in OPENAI_COMPATIBLE:
            backend = _openai_compatible(name)
            if backend:
                return backend
    return None

def chat_deployment():
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

def embedding_deployment():
    return os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
