"""
Tests for LLMService 3-Tier Fallback Architecture (Groq -> GitHub -> Gemini)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.llm_service import LLMService, _clean_json_string


def test_clean_json_string():
    """Verify markdown code fences stripping."""
    assert _clean_json_string('```json\n{"status": "ok"}\n```') == '{"status": "ok"}'
    assert _clean_json_string('{"status": "ok"}') == '{"status": "ok"}'
    assert _clean_json_string(None) == ""


@pytest.mark.asyncio
async def test_llm_service_groq_success(capsys):
    """Verify primary call succeeds using Groq and prints debug message."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"result": "groq_output"})))
    ]

    with patch("services.llm_service.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.groq_api_key = "gsk_test_key"
        mock_settings.groq_models_endpoint = "https://api.groq.com/openai/v1"
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.github_token = "gh_test_token"
        mock_settings.github_models_endpoint = "https://models.inference.ai.azure.com"
        mock_settings.github_model = "gpt-4o-mini"
        mock_settings.google_api_key = ""
        mock_get_settings.return_value = mock_settings

        with patch("services.llm_service.AsyncOpenAI") as mock_openai_cls:
            mock_groq_client = AsyncMock()
            mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_groq_client

            service = LLMService()
            res = await service.generate("Test prompt")

            assert res == {"result": "groq_output"}
            captured = capsys.readouterr()
            assert "DEBUG: Successfully generated response using Groq" in captured.out


@pytest.mark.asyncio
async def test_llm_service_groq_failure_fallback_to_github():
    """Verify fallback to GitHub Models when Groq fails."""
    mock_github_response = MagicMock()
    mock_github_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"result": "github_output"})))
    ]

    with patch("services.llm_service.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.groq_api_key = "gsk_test_key"
        mock_settings.groq_models_endpoint = "https://api.groq.com/openai/v1"
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.github_token = "gh_test_token"
        mock_settings.github_models_endpoint = "https://models.inference.ai.azure.com"
        mock_settings.github_model = "gpt-4o-mini"
        mock_settings.google_api_key = ""
        mock_get_settings.return_value = mock_settings

        with patch("services.llm_service.AsyncOpenAI") as mock_openai_cls:
            mock_groq_client = AsyncMock()
            mock_groq_client.chat.completions.create = AsyncMock(side_effect=Exception("Groq rate limit"))
            
            mock_github_client = AsyncMock()
            mock_github_client.chat.completions.create = AsyncMock(return_value=mock_github_response)
            
            mock_openai_cls.side_effect = [mock_groq_client, mock_github_client]

            service = LLMService()
            res = await service.generate("Test prompt")

            assert res == {"result": "github_output"}


@pytest.mark.asyncio
async def test_llm_service_groq_and_github_failure_fallback_to_gemini():
    """Verify fallback to Gemini when both Groq and GitHub fail."""
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = json.dumps({"result": "gemini_output"})

    with patch("services.llm_service.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.groq_api_key = "gsk_test_key"
        mock_settings.groq_models_endpoint = "https://api.groq.com/openai/v1"
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.github_token = "gh_test_token"
        mock_settings.github_models_endpoint = "https://models.inference.ai.azure.com"
        mock_settings.github_model = "gpt-4o-mini"
        mock_settings.google_api_key = "gemini_test_key"
        mock_settings.gemini_model = "gemini-2.0-flash"
        mock_get_settings.return_value = mock_settings

        with patch("services.llm_service.AsyncOpenAI") as mock_openai_cls, \
             patch("services.llm_service.genai.Client") as mock_genai_cls:
            
            mock_groq_client = AsyncMock()
            mock_groq_client.chat.completions.create = AsyncMock(side_effect=Exception("Groq rate limit"))
            
            mock_github_client = AsyncMock()
            mock_github_client.chat.completions.create = AsyncMock(side_effect=Exception("GitHub rate limit"))
            
            mock_openai_cls.side_effect = [mock_groq_client, mock_github_client]

            mock_gemini_client = MagicMock()
            mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_gemini_response)
            mock_genai_cls.return_value = mock_gemini_client

            service = LLMService()
            res = await service.generate("Test prompt")

            assert res == {"result": "gemini_output"}
