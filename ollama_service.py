# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
Ollama service module for AutoYou Notes Agent.

This module provides a simplified service for interacting with Ollama models,
including model discovery, availability checking, and on-demand client initialization.
"""
import logging
import os
from typing import Optional, List, Dict, Any

import ollama

logger = logging.getLogger(__name__)


class OllamaService:
    """Simplified service for getting available OLLAMA models."""

    def __init__(self):
        self.client = None
        self.ollama_available = False
        # Get default model from environment variable or use fallback
        default_model_env = os.getenv('OLLAMA_MODEL', 'qwen3:4b')
        # Remove ollama_chat/ or ollama/ or openapi/ prefix if present
        if '/' in default_model_env:
            self.default_model = default_model_env.split('/', 1)[1]
        else:
            self.default_model = default_model_env

    def _get_client(self):
        """Get or create OLLAMA client on demand."""
        if self.client is None:
            try:
                # Use OLLAMA_API_BASE environment variable if set
                api_base = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
                self.client = ollama.Client(host=api_base)
                # Test the connection
                self.client.list()
                self.ollama_available = True
                logger.info("OLLAMA is available at %s", api_base)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("OLLAMA not available: %s", str(e))
                self.ollama_available = False
                self.client = None
        return self.client

    def _check_ollama_availability(self) -> bool:
        """Check if OLLAMA is installed and available."""
        client = self._get_client()
        return client is not None and self.ollama_available

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OLLAMA."""
        if not self._check_ollama_availability():
            logger.warning("OLLAMA is not available")
            return []

        try:
            models = self.client.list()
            return models.get('models', [])
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error getting available models: %s", str(e))
            return []

    def list_models(self) -> List[str]:
        """Get list of available model names."""
        models = self.get_available_models()
        return [model['model'] for model in models]

    def get_first_available_model(self) -> Optional[str]:
        """Get the first available model name."""
        models = self.list_models()
        return models[0] if models else None

    def get_latest_model(self) -> Optional[str]:
        """Get the latest model (first in the list)."""
        models = self.get_available_models()
        if not models:
            return None

        # Sort by modified time if available, otherwise return first
        try:
            sorted_models = sorted(
                models,
                key=lambda x: x.get('modified_at', ''),
                reverse=True
            )
            return sorted_models[0]['model']
        except (KeyError, TypeError):
            return models[0]['model'] if models else None

    def get_model_by_name(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get model information by name."""
        models = self.get_available_models()
        for model in models:
            if model['model'] == model_name:
                return model
        return None

    def get_default_model(self) -> Optional[str]:
        """Get the default model name."""
        # First try to get the configured default model if it exists
        if self.get_model_by_name(self.default_model):
            return self.default_model
        # Otherwise return the first available model
        return self.get_first_available_model()

    def is_available(self) -> bool:
        """Check if Ollama service is available."""
        return self._check_ollama_availability()
