"""
LLM Adapter - Switches between local GGUF model and free cloud APIs
Enables free tier deployment by using Groq/OpenAI/Hugging Face APIs

Every generator returns {"text": ..., "finish_reason": ...} and raises LLMError when
the provider fails or returns no text, so callers never mistake an error for a reply.
"""

from functools import lru_cache
from typing import Dict

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from config import config


class LLMError(Exception):
    """The LLM provider failed or returned no usable text."""


@lru_cache(maxsize=1)
def _groq_client():
    """One client per process; a short timeout keeps a stuck request from holding the chat open."""
    from groq import Groq
    return Groq(api_key=config.LLM_API_KEY, timeout=20.0, max_retries=1)


def generate_with_groq(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> Dict:
    """Generate response using Groq API."""
    if not config.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set")

    extra_body = {}
    if "qwen3" in config.LLM_MODEL.lower():
        # Qwen3 reasons by default and the reasoning counts against max_tokens,
        # which can leave nothing for the reply itself
        extra_body["reasoning_effort"] = "none"

    try:
        response = _groq_client().chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=extra_body or None,
        )
    except Exception as e:
        raise LLMError(f"Groq API error: {e}") from e

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        raise LLMError(f"Groq returned no text (finish_reason={choice.finish_reason})")
    return {"text": text, "finish_reason": choice.finish_reason}


def generate_with_openai(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> Dict:
    """Generate response using OpenAI API."""
    if not config.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.LLM_API_KEY, timeout=20.0, max_retries=1)
        response = client.chat.completions.create(
            model=config.LLM_MODEL or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as e:
        raise LLMError(f"OpenAI API error: {e}") from e

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        raise LLMError(f"OpenAI returned no text (finish_reason={choice.finish_reason})")
    return {"text": text, "finish_reason": choice.finish_reason}


def generate_with_huggingface(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> Dict:
    """Generate response using Hugging Face Inference API (free tier available)."""
    if not config.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set")

    try:
        import requests

        api_url = f"https://api-inference.huggingface.co/models/{config.LLM_MODEL or 'mistralai/Mistral-7B-Instruct-v0.1'}"
        headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False
            }
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
    except Exception as e:
        raise LLMError(f"Hugging Face API error: {e}") from e

    text = ""
    if isinstance(result, list) and len(result) > 0:
        text = (result[0].get("generated_text") or "").strip()
    if not text:
        raise LLMError("Hugging Face returned no text")
    # The Inference API doesn't say why generation stopped
    return {"text": text, "finish_reason": None}


def generate_llm_response(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> Dict:
    """
    Universal LLM response generator for cloud providers.

    Returns:
        Dict with 'response' (generated text) and 'finish_reason' ('length' when
        the reply was cut off by max_tokens). Raises LLMError on failure.
    """
    if not config.USE_EXTERNAL_LLM:
        raise LLMError("External LLM is disabled in config")

    print(f"🌐 Using {config.LLM_PROVIDER.upper()} API")

    # Route to provider
    provider = config.LLM_PROVIDER.lower()
    if provider == "groq":
        result = generate_with_groq(prompt, max_tokens, temperature)
    elif provider == "openai":
        result = generate_with_openai(prompt, max_tokens, temperature)
    elif provider in ["huggingface", "hf"]:
        result = generate_with_huggingface(prompt, max_tokens, temperature)
    else:
        print(f"⚠️ Unknown provider: {config.LLM_PROVIDER}, using Groq")
        result = generate_with_groq(prompt, max_tokens, temperature)

    return {"response": result["text"], "finish_reason": result.get("finish_reason")}


if __name__ == "__main__":
    print("=" * 60)
    print("LLM ADAPTER CONFIGURATION")
    print("=" * 60)
    print(f"Mode: {'EXTERNAL API' if config.USE_EXTERNAL_LLM else 'LOCAL MODEL'}")
    if config.USE_EXTERNAL_LLM:
        print(f"Provider: {config.LLM_PROVIDER}")
        print(f"Model: {config.LLM_MODEL}")
        print(f"API Key Set: {'✅ Yes' if config.LLM_API_KEY else '❌ No'}")
    print("=" * 60)
