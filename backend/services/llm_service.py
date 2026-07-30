"""
Supply Chain Orchestrator — Unified LLM Service

Provides an async LLM client with a 3-tier fallback architecture:
  • Priority 1 (Primary): Groq API (llama-3.3-70b-versatile via AsyncOpenAI)
  • Priority 2 (Secondary): GitHub Models (gpt-4o-mini via Azure-compatible OpenAI endpoint)
  • Priority 3 (Tertiary): Google Gemini (gemini-2.0-flash via google-genai SDK)

All agent code calls `llm_service.generate(...)` — provider selection and
fallback logic are encapsulated here.
"""

import json
import logging
import os
import time
from typing import Any, Optional

from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _clean_json_string(text: str) -> str:
    """Strip markdown code fence wrappers from raw JSON strings."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


class LLMService:
    """
    Async LLM gateway with automatic 3-tier fallback (Groq -> GitHub -> Gemini).

    Usage:
        service = LLMService()
        result = await service.generate("Summarise this inventory data…")
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── Priority 1: Groq API (Primary OpenAI-compatible) ──
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY") or ""
        self._groq_client = None
        if groq_key:
            try:
                self._groq_client = AsyncOpenAI(
                    api_key=groq_key,
                    base_url=settings.groq_models_endpoint,
                )
            except Exception as exc:
                logger.warning("Could not initialize Groq client: %s", exc)
        self._groq_model = settings.groq_model

        # ── Priority 2: GitHub Models (Secondary Fallback) ──
        github_token = settings.github_token or "placeholder_token"
        self._github_client = AsyncOpenAI(
            api_key=github_token,
            base_url=settings.github_models_endpoint,
        )
        self._github_model = settings.github_model

        # ── Priority 3: Google Gemini (Tertiary Fallback) ──
        self._gemini_client = None
        if settings.google_api_key:
            try:
                self._gemini_client = genai.Client(api_key=settings.google_api_key)
            except Exception as exc:
                logger.warning("Could not initialize Gemini client: %s", exc)
        self._gemini_model = settings.gemini_model

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

        Tries Groq first; falls back to GitHub Models, then Gemini on failure.
        Returns the parsed JSON dict.
        """
        # Attempt 1 — Groq (Primary)
        if self._groq_client:
            try:
                return await self._call_groq(
                    prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                logger.warning("Groq primary call failed (%s), falling back to GitHub Models", exc)

        # Attempt 2 — GitHub Models (Secondary Fallback)
        try:
            return await self._call_github(
                prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("GitHub Models secondary call failed (%s), falling back to Gemini", exc)

        # Attempt 3 — Gemini (Tertiary Fallback)
        try:
            if not self._gemini_client:
                raise ValueError("Gemini client is not initialized or API key is missing.")
            return await self._call_gemini(
                prompt,
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("Gemini tertiary fallback failed cleanly: %s", exc)
            raise

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
        Tries Groq first; falls back to GitHub Models, then Gemini.
        """
        # Attempt 1 — Groq (Primary)
        if self._groq_client:
            try:
                return await self._call_groq_text(
                    prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                logger.warning("Groq text call failed (%s), falling back to GitHub Models", exc)

        # Attempt 2 — GitHub Models (Secondary Fallback)
        try:
            return await self._call_github_text(
                prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("GitHub Models text call failed (%s), falling back to Gemini", exc)

        # Attempt 3 — Gemini (Tertiary Fallback)
        try:
            if not self._gemini_client:
                raise ValueError("Gemini client is not initialized or API key is missing.")
            return await self._call_gemini_text(
                prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.warning("Gemini text fallback failed cleanly: %s", exc)
            raise

    # ── Groq Internals ────────────────────────────────────────

    async def _call_groq(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        """Call Groq API (OpenAI-compatible) and return parsed JSON."""
        if not self._groq_client:
            raise ValueError("Groq client is not initialized.")
        t0 = time.perf_counter()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._groq_client.chat.completions.create(
            model=self._groq_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Groq responded in %.0f ms", elapsed)
        print("DEBUG: Successfully generated response using Groq")

        raw = response.choices[0].message.content or ""
        cleaned = _clean_json_string(raw)
        return json.loads(cleaned)

    async def _call_groq_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Call Groq API and return raw text."""
        if not self._groq_client:
            raise ValueError("Groq client is not initialized.")
        t0 = time.perf_counter()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._groq_client.chat.completions.create(
            model=self._groq_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Groq text responded in %.0f ms", elapsed)
        print("DEBUG: Successfully generated response using Groq")
        return response.choices[0].message.content or ""

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

        raw = response.choices[0].message.content or ""
        cleaned = _clean_json_string(raw)
        return json.loads(cleaned)

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
        return response.choices[0].message.content or ""

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
        if not self._gemini_client:
            raise ValueError("Gemini client is not initialized.")
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

        raw = response.text or ""
        cleaned = _clean_json_string(raw)
        return json.loads(cleaned)

    async def _call_gemini_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Call Gemini and return raw text."""
        if not self._gemini_client:
            raise ValueError("Gemini client is not initialized.")
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
        return response.text or ""


