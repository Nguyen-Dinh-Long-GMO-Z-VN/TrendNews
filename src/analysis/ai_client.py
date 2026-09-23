"""
AI client for analysis/translation/filtering.
Supports multiple providers via environment variables.
Uses requests for OpenAI-compatible providers; anthropic SDK for Claude;
native generateContent endpoint for Gemini.

Environment variables (prefix mặc định "AI"):
  AI_PROVIDER   = claude | deepseek | openai | gemini | ollama  (default: claude)
  AI_API_KEY    = your api key (fallback: ANTHROPIC_API_KEY cho claude,
                  GOOGLE_API_KEY cho gemini)
  AI_BASE_URL   = optional override
  AI_MODEL      = optional override

Per-feature prefixes: AIClient("TRANSLATE") đọc TRANSLATE_PROVIDER,
TRANSLATE_API_KEY, TRANSLATE_BASE_URL, TRANSLATE_MODEL.
Provider/model/base_url KHÔNG kế thừa AI_* (feature độc lập);
chỉ API key fallback: <PREFIX>_API_KEY → provider env → AI_API_KEY.
"""

import os
import json
import requests
from typing import Optional

PROVIDER_DEFAULTS = {
    "claude": {
        "model": "claude-sonnet-4-6",  # balanced quality/speed for analysis
    },
    "openai": {
        "base_url": "https://api.openai.com",
        "model": "gpt-4o-mini",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-3.5-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
    },
}

# API key env fallback theo provider
_KEY_FALLBACKS = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


class AIClient:
    """
    Multi-provider AI client.

    Args:
        env_prefix: prefix env vars ("AI" mặc định → AI_PROVIDER/AI_API_KEY/...).
                    Prefix khác (vd "TRANSLATE") đọc TRANSLATE_* rồi fallback AI_*.
        default_provider: provider mặc định nếu env không set
                          ("claude" cho AI, "gemini" cho prefix khác).

    Ví dụ dùng Gemini trực tiếp (free key từ AI Studio):
      TRANSLATE_PROVIDER=gemini
      GOOGLE_API_KEY=AIza...
      TRANSLATE_MODEL=gemini-3.5-flash   # optional, đây là default
    """

    def __init__(self, env_prefix: str = "AI", default_provider: str = None):
        self.env_prefix = env_prefix
        if default_provider is None:
            default_provider = "claude" if env_prefix == "AI" else "gemini"

        # PROVIDER/BASE_URL/MODEL chỉ đọc theo prefix riêng — KHÔNG kế thừa
        # AI_* (tránh feature Gemini trực tiếp bị rơi về proxy AI_PROVIDER)
        self.provider = (
            os.environ.get(f"{env_prefix}_PROVIDER", "").strip() or default_provider
        ).lower()

        # API key: <PREFIX>_API_KEY → provider-specific env → AI_API_KEY
        self.api_key = os.environ.get(f"{env_prefix}_API_KEY", "").strip()
        if not self.api_key:
            self.api_key = os.environ.get(
                _KEY_FALLBACKS.get(self.provider, ""), ""
            ).strip()
        if not self.api_key and env_prefix != "AI":
            self.api_key = os.environ.get("AI_API_KEY", "").strip()

        defaults = PROVIDER_DEFAULTS.get(self.provider, PROVIDER_DEFAULTS["deepseek"])
        self.base_url = (
            os.environ.get(f"{env_prefix}_BASE_URL", "").strip()
            or defaults.get("base_url", "")
        ).rstrip("/")
        self.model = (
            os.environ.get(f"{env_prefix}_MODEL", "").strip() or defaults["model"]
        )
        self.timeout = 120

    def is_configured(self) -> bool:
        """Check if API key is available (Ollama doesn't need one)."""
        if self.provider == "ollama":
            return True
        return bool(self.api_key)

    def complete(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        """
        Send a prompt and return the completion text.
        Raises on network/API errors.
        """
        if self.provider == "claude":
            return self._complete_claude(prompt, system, max_tokens)
        elif self.provider == "gemini":
            return self._complete_gemini(prompt, system, max_tokens)
        elif self.provider == "ollama":
            return self._complete_ollama(prompt, system, max_tokens)
        else:
            # OpenAI-compatible (openai, deepseek, and most others)
            return self._complete_openai_compat(prompt, system, max_tokens)

    def _complete_claude(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens or 8192,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        return message.content[0].text

    def _complete_openai_compat(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens or 4096,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _complete_gemini(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        url = (
            f"{self.base_url}/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens or 8192,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _complete_ollama(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        if not system:
            payload.pop("system")
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["response"]
