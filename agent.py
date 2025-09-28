# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

# Standard library imports
import logging

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