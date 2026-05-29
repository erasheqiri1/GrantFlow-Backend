from openai import OpenAI
from app.core.config import settings


def get_ai_client():
    """Kthen OpenAI client dhe emrin e modelit bazuar në API keys të konfiguruara."""
    if settings.OPENAI_API_KEY:
        return OpenAI(api_key=settings.OPENAI_API_KEY), "gpt-4o-mini"
    if settings.GROQ_API_KEY:
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama-3.1-8b-instant"
    return None, None
