"""
LLM Adapter - Switches between local GGUF model and free cloud APIs
Enables free tier deployment by using Groq/OpenAI/Hugging Face APIs
"""

import os
from typing import Dict, Union

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from config import config


def generate_with_groq(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> str:
    """Generate response using Groq API (FREE tier: 30 req/min)."""
    try:
        from groq import Groq
        
        if not config.LLM_API_KEY:
            return "I'm Dax, your F1 mechanic. Get a free Groq API key at console.groq.com"
        
        client = Groq(api_key=config.LLM_API_KEY)
        
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        return response.choices[0].message.content.strip()
    
    except ImportError:
        raise ImportError("groq not installed. Run: pip install groq")
    except Exception as e:
        print(f"❌ Groq API error: {e}")
        return "I'm having trouble connecting to my systems right now. Please try again."


def generate_with_openai(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> str:
    """Generate response using OpenAI API ($5 free credits for new users)."""
    try:
        from openai import OpenAI
        
        if not config.LLM_API_KEY:
            return "I'm Dax, your F1 mechanic. Get OpenAI API key at platform.openai.com"
        
        client = OpenAI(api_key=config.LLM_API_KEY)
        
        response = client.chat.completions.create(
            model=config.LLM_MODEL or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        return response.choices[0].message.content.strip()
    
    except ImportError:
        raise ImportError("openai not installed. Run: pip install openai")
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        return "I'm having trouble connecting to my systems right now. Please try again."


def generate_with_huggingface(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> str:
    """Generate response using Hugging Face Inference API (free tier available)."""
    try:
        import requests
        
        if not config.LLM_API_KEY:
            return "I'm Dax, your F1 mechanic. Get HF token at huggingface.co/settings/tokens"
        
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
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "").strip()
        
        return "I'm having trouble generating a response right now."
    
    except Exception as e:
        print(f"❌ Hugging Face API error: {e}")
        return "I'm having trouble connecting to my systems right now. Please try again."


def generate_llm_response(prompt: str, max_tokens: int = 150, temperature: float = 0.4) -> Dict:
    """
    Universal LLM response generator.
    Switches between local GGUF and cloud APIs based on USE_EXTERNAL_LLM env var.
    
    Returns:
        Dict with 'response' key containing generated text
    """
    if config.USE_EXTERNAL_LLM:
        print(f"🌐 Using {config.LLM_PROVIDER.upper()} API")
        
        # Route to provider
        provider = config.LLM_PROVIDER.lower()
        if provider == "groq":
            text = generate_with_groq(prompt, max_tokens, temperature)
        elif provider == "openai":
            text = generate_with_openai(prompt, max_tokens, temperature)
        elif provider in ["huggingface", "hf"]:
            text = generate_with_huggingface(prompt, max_tokens, temperature)
        else:
            print(f"⚠️ Unknown provider: {config.LLM_PROVIDER}, using Groq")
            text = generate_with_groq(prompt, max_tokens, temperature)
        
        return {"response": text}
    
    else:
        # Use local GGUF model
        print("🖥️ Using local GGUF model")
        # To avoid circular import, we should ideally NOT import from llamacpp here
        # or llamacpp should provide a low-level generate function
        from llamacpp import generate_npc_response
        return generate_npc_response(prompt, "neutral", 0, [], "Player")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM ADAPTER CONFIGURATION")
    print("=" * 60)
    print(f"Mode: {'EXTERNAL API' if USE_EXTERNAL_LLM else 'LOCAL MODEL'}")
    if USE_EXTERNAL_LLM:
        print(f"Provider: {LLM_PROVIDER}")
        print(f"Model: {LLM_MODEL}")
        print(f"API Key Set: {'✅ Yes' if LLM_API_KEY else '❌ No'}")
    print("=" * 60)
