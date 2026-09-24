"""
LLM Client Subsystem for PRISM Tier 2.

Provides a unified interface for querying language models for strategic subgoal
generation, supporting OpenRouter (including free tier models), local backends,
and deterministic mock clients for offline testing.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from prism.core.config import Tier2Config

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for Tier 2 LLM inference backends."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Submit a prompt and return the model's text generation.

        Args:
            prompt: Formatted strategic prompt text.

        Returns:
            str: Raw generated response text.

        Raises:
            RuntimeError: If request fails and cannot be recovered.
        """
        pass


class MockLLMClient(LLMClient):
    """
    Deterministic offline mock client for testing and CI.

    Supports pre-set canned responses, dynamic bridging synthesis from prompt,
    and simulated error modes for testing exception containment.
    """

    def __init__(
        self,
        canned_responses: Optional[List[str]] = None,
        error_mode: bool = False,
    ):
        self.canned_responses: List[str] = list(canned_responses or [])
        self.error_mode: bool = error_mode
        self.call_history: List[str] = []

    def generate(self, prompt: str) -> str:
        self.call_history.append(prompt)

        if self.error_mode:
            raise RuntimeError("Simulated network or service failure in MockLLMClient.")

        if self.canned_responses:
            return self.canned_responses.pop(0)

        # Dynamic bridging synthesis from prompt text
        goal_match = re.search(r"CURRENT GOAL:\s*\((?:Inheritance|Evaluation|Implication)\s+(\w+)\s+(\w+)\)", prompt)
        facts_match = re.findall(r"\((?:Inheritance|Evaluation|Implication)\s+(\w+)\s+(\w+)\)", prompt)

        if goal_match:
            sub, obj = goal_match.group(1), goal_match.group(2)
            # Find an intermediate concept from known facts
            intermediate = "M"
            for f_sub, f_obj in facts_match:
                if f_sub != sub and f_sub != obj:
                    intermediate = f_sub
                    break
                elif f_obj != sub and f_obj != obj:
                    intermediate = f_obj
                    break

            payload = {
                "subgoal": f"(Inheritance {sub} {intermediate})",
                "suggested_premise": f"(Inheritance {sub} {intermediate})",
                "reasoning": f"Synthesizing intermediate bridge between {sub} and {obj} via {intermediate}.",
            }
            return json.dumps(payload)

        # Fallback default JSON
        return json.dumps({
            "subgoal": "(Inheritance A M)",
            "suggested_premise": "(Inheritance A B)",
            "reasoning": "Default heuristic bridging subgoal.",
        })


class OpenRouterClient(LLMClient):
    """
    OpenRouter API client supporting free and commercial model endpoints.
    Uses standard library urllib for zero external dependencies.
    """

    def __init__(self, config: Optional[Tier2Config] = None):
        cfg = config or Tier2Config()
        key = cfg.api_key or os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            key_file = os.path.expanduser("~/.openrouter_key")
            if os.path.exists(key_file):
                try:
                    with open(key_file) as f:
                        key = f.read().strip()
                except Exception:
                    pass
        self.api_key: str = key
        self.model_name: str = cfg.model_name
        self.base_url: str = cfg.base_url.rstrip("/")
        self.timeout_seconds: float = cfg.timeout_seconds
        self.max_tokens: int = cfg.max_tokens
        self.temperature: float = cfg.temperature

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key in Tier2Config."
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/trueagi-io/pln",
            "X-Title": "PRISM PLN Inference Control",
            "User-Agent": "PRISM/0.1.0",
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert automated reasoning assistant for Probabilistic Logic Networks. "
                        "Respond strictly in the requested JSON schema without prose outside the JSON block."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                status = response.getcode()
                raw_body = response.read().decode("utf-8")
                if status != 200:
                    raise RuntimeError(f"OpenRouter API HTTP {status}: {raw_body}")
                resp_json = json.loads(raw_body)
                choices = resp_json.get("choices", [])
                if not choices:
                    raise RuntimeError(f"Empty choices in OpenRouter response: {raw_body}")
                msg = choices[0].get("message", {})
                content = msg.get("content")
                if not content:
                    content = msg.get("reasoning", "")
                return str(content or "")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter HTTPError {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter URLError: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"OpenRouter unexpected failure: {e}") from e


def create_llm_client(config: Optional[Tier2Config] = None) -> LLMClient:
    """
    Factory function to instantiate the appropriate LLM client backend.
    """
    cfg = config or Tier2Config()
    backend = cfg.backend.lower()

    if backend == "openrouter":
        api_key = cfg.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            key_file = os.path.expanduser("~/.openrouter_key")
            if os.path.exists(key_file):
                try:
                    with open(key_file) as f:
                        api_key = f.read().strip()
                except Exception:
                    pass
        if api_key:
            return OpenRouterClient(cfg)
        logger.warning(
            "[PRISM Tier 2] 'openrouter' backend requested but no API key found in env or ~/.openrouter_key. "
            "Falling back to MockLLMClient."
        )
        return MockLLMClient()

    return MockLLMClient()
