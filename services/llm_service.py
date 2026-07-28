"""
Supply Chain Orchestrator — Unified LLM Service

Provides an async LLM client with:
  • Primary:  Google Gemini (gemini-2.5-flash) via google-genai SDK
  • Fallback: GPT-4o-mini via GitHub Models (Azure-compatible OpenAI endpoint)

All agent code calls `llm_service.generate(...)` — provider selection and
fallback logic are encapsulated here.
"""

import json
import logging
import time
from typing import Any, Optional

from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Async LLM gateway with automatic fallback.

    Usage:
        service = LLMService()
        result = await service.generate("Summarise this inventory data…")
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── Primary: Google Gemini ───────────────────────────
        self._gemini_client = genai.Client(api_key=settings.google_api_key)
        self._gemini_model = settings.gemini_model

        # ── Fallback: GitHub Models (OpenAI-compatible) ──────
        self._github_client = AsyncOpenAI(
            api_key=settings.github_token,
            base_url=settings.github_models_endpoint,
        )
        self._github_model = settings.github_model

    # ── Public API ───────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        response_mime_type: str = "application/json",
        temperature: float = 0.3,
        max_output_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Generate a structured JSON response from the LLM.

        Tries Gemini first; falls back to GitHub Models on failure.
        Returns the parsed JSON dict.
        """
        # Attempt 1 — Gemini
        try:
            return await self._call_gemini(
                prompt,
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("Gemini call failed (%s), falling back to GitHub Models", exc)

        # Attempt 2 — GitHub Models (fallback)
        return await self._call_github(
            prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        temperature: float = 0.5,
        max_output_tokens: int = 4096,
    ) -> str:
        """
        Generate a plain-text response (no JSON parsing).
        Tries Gemini first; falls back to GitHub Models.
        """
        try:
            return await self._call_gemini_text(
                prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("Gemini text call failed (%s), falling back to GitHub Models", exc)

        return await self._call_github_text(
            prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    # ── Gemini Internals ─────────────────────────────────────

    async def _call_gemini(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        response_mime_type: str,
        temperature: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        """Call Gemini and return parsed JSON."""
        t0 = time.perf_counter()
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            system_instruction=system_instruction,
        )
        response = await self._gemini_client.aio.models.generate_content(
            model=self._gemini_model,
            contents=prompt,
            config=config,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Gemini responded in %.0f ms", elapsed)

        raw = response.text
        return json.loads(raw)

    async def _call_gemini_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Call Gemini and return raw text."""
        t0 = time.perf_counter()
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
        )
        response = await self._gemini_client.aio.models.generate_content(
            model=self._gemini_model,
            contents=prompt,
            config=config,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Gemini text responded in %.0f ms", elapsed)
        return response.text

    # ── GitHub Models Internals ──────────────────────────────

    async def _call_github(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        """Call GitHub Models (OpenAI-compatible) and return parsed JSON."""
        t0 = time.perf_counter()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._github_client.chat.completions.create(
            model=self._github_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("GitHub Models responded in %.0f ms", elapsed)

        raw = response.choices[0].message.content
        return json.loads(raw)

    async def _call_github_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Call GitHub Models and return raw text."""
        t0 = time.perf_counter()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._github_client.chat.completions.create(
            model=self._github_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("GitHub Models text responded in %.0f ms", elapsed)
        return response.choices[0].message.content
