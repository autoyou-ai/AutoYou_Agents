# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT
"""
AutoYou Notes Agent.

This module implements the AutoYou Notes Agent, which uses a combination of
Ollama for local language processing and Google's Gemini API for advanced
natural language understanding. The agent is designed to handle note-taking,
organization, and retrieval tasks.
"""
# Standard library imports
import logging
import litellm
import asyncio

# Monkey-patch litellm to handle Ollama's message format
_original_acompletion = litellm.acompletion

def _flatten_message_content(messages):
    """
    Flattens the 'content' of messages if it is a list of parts,
    which is how ADK represents complex content, into a single string
    that Ollama expects.
    """
    for message in messages:
        if isinstance(message.get("content"), list):
            new_content = " ".join(
                part["text"]
                for part in message["content"]
                if isinstance(part, dict) and "text" in part
            )
            message["content"] = new_content
    return messages

async def _patched_acompletion(*args, **kwargs):
    """
    Patched version of litellm.acompletion that flattens message content
    before passing it to the original function.
    """
    if "messages" in kwargs:
        kwargs["messages"] = _flatten_message_content(kwargs["messages"])
    return await _original_acompletion(*args, **kwargs)

litellm.acompletion = _patched_acompletion


# Third-party imports
from google.adk.agents import Agent

# Local imports
from ollama_service import OllamaService
from notes_agent.agent import create_notes_agent
from model_config import get_model_config
from prompt import AGENT_NAME, AGENT_DESCRIPTION, AGENT_INSTRUCTION

# Enable LiteLLM debugging if needed
# litellm._turn_on_debug()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
ollama_service = OllamaService()

# Create the root agent with routing capabilities
try:
    model_config = get_model_config(ollama_service)
    logger.info("Successfully configured model: %s", model_config)
    
    # Create notes agent with the same model config
    notes_agent = create_notes_agent(model_config)

    root_agent = Agent(
        name=AGENT_NAME,
        model=model_config,  # Dynamic model selection: Ollama with fallback to Gemini
        description=AGENT_DESCRIPTION,
        instruction=AGENT_INSTRUCTION,
        sub_agents=[notes_agent]
    )

except Exception as e:
    logger.error("Failed to initialize agent: %s", str(e))
    logger.error("Please check your model configuration, availability of OLLAMA if locally running, or check GOOGLE API keys.")