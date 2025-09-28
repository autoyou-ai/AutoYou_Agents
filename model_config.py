# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
Model configuration module for AutoYou Notes Agent.

This module provides dynamic model selection between Ollama (local) and Gemini (cloud) models
based on availability and environment configuration.
"""
import os
import logging
from google.adk.models.lite_llm import LiteLlm
from ollama_service import OllamaService

logger = logging.getLogger(__name__)
BASE_OLLAMA_PROVIDER = "ollama_chat/"

def get_model_config(ollama_service: OllamaService):
    """
    Determine the best available model configuration.

    Args:
        ollama_service: Instance of OllamaService for checking Ollama availability

    Returns:
        Model instance for ADK Agent - either LiteLlm with Ollama or fallback to Gemini

    Raises:
        ValueError: If no valid API key is found for Gemini model
    """
    # Check if we should use Google API based on environment variable
    use_google_api = os.getenv('USE_GOOGLE_API', '0').lower() in ('1', 'true', 'yes')

    if use_google_api:
        logger.info("USE_GOOGLE_API is enabled, using Gemini model directly")
        return _configure_gemini_model()

    # Try to configure Ollama first
    try:
        return _configure_ollama_model(ollama_service)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to configure Ollama model: %s", str(e))

    # Fallback to Gemini
    logger.info("Falling back to Gemini model")
    return _configure_gemini_model()


def _configure_gemini_model():
    """Configure and return Gemini model configuration."""
    # Check if Google API key is available
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'NULL':
        logger.error("No valid Google API key found. Cannot use Gemini model.")
        raise ValueError(
            "No valid Google API key found. Please set GOOGLE_API_KEY or "
            "GEMINI_API_KEY environment variable."
        )

    model_name = os.getenv('GOOGLE_MODEL', 'gemini-2.5-flash')
    logger.info("Using Gemini model: %s", model_name)

    return LiteLlm(model=model_name)


def _configure_ollama_model(ollama_service: OllamaService):
    """Configure and return Ollama model configuration."""
    # Check if Ollama is available
    if not ollama_service.is_available():
        raise ConnectionError("Ollama service is not available")

    # Get the configured model name
    model_name = os.getenv('OLLAMA_MODEL', 'qwen3:4b')
    logger.info("Attempting to use Ollama model: %s", model_name)

    # Get list of available models
    available_models = ollama_service.list_models()
    if not available_models:
        raise RuntimeError("No models available in Ollama")

    # Find the best matching model
    selected_model = _find_available_model(model_name, available_models)
    if not selected_model:
        # Try to find a fallback model
        selected_model = _select_fallback_model(available_models, ollama_service)

    if not selected_model:
        raise RuntimeError("No suitable Ollama model found")

    logger.info("Using Ollama model: %s", selected_model)

    # Configure LiteLlm with Ollama
    api_base = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    return LiteLlm(
        model=BASE_OLLAMA_PROVIDER + selected_model,
        api_base=api_base
    )


def _find_available_model(model_name: str, model_names: list) -> str:
    """Find the best matching model from available models."""
    # Direct match
    if model_name in model_names:
        return model_name

    # Try without the prefix
    if '/' in model_name:
        base_name = model_name.split('/', 1)[1]
        if base_name in model_names:
            return base_name

    return None


def _select_fallback_model(model_names: list, ollama_service: OllamaService) -> str:
    """Select a fallback model from available models."""
    # Use the latest model or default
    return ollama_service.get_latest_model() or ollama_service.get_default_model()
