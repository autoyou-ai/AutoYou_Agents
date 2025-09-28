# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
AutoYou Notes Agent FastAPI Server.

This module provides a FastAPI server for the AutoYou Notes Agent,
including health checks, agent information, and notes statistics endpoints.
"""

import argparse
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# Load environment variables
load_dotenv()

def setup_default_environment_variables():
    """Set up default environment variables for the AutoYou Notes Agent."""
    default_env_vars = {
        'OLLAMA_API_BASE': 'http://localhost:11434',
        'OLLAMA_MODEL': 'qwen3:4b',
        'USE_GOOGLE_API': '0',
        'GOOGLE_API_KEY': 'NULL',
        'GOOGLE_MODEL': 'gemini-2.5-flash'
    }

    for key, default_value in default_env_vars.items():
        if not os.getenv(key):
            os.environ[key] = default_value
            print(f"Set default environment variable: {key}={default_value}")
        else:
            print(f"Using existing environment variable: {key}={os.getenv(key)}")

# Initialize environment variables
setup_default_environment_variables()

# Set up paths
DIRNAME = os.path.dirname(__file__)
AGENT_NAME = os.path.basename(DIRNAME)  # Extract only "AutoYou_Agents"
AGENT_DIR = os.path.abspath(DIRNAME)
BASE_DIR = os.path.dirname(AGENT_DIR)  # Parent directory containing the agent

# Create session service configuration
session_db_kwargs = {
    "echo": False,
}

# Create the FastAPI app using ADK's helper
app: FastAPI = get_fast_api_app(
    agents_dir=BASE_DIR,
    allow_origins=["*"],  # In production, restrict this
    web=True,  # Enable the ADK Web UI
)

# Import REST API components
from rest_api import (
    ChatRequest, ChatResponse, SessionInfo, APIStatus,
    process_chat_message, get_session_info, get_api_status
)

# Add custom health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "AutoYou AI Agent"}

# REST API Endpoints for external chat applications

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest):
    """
    Main chat endpoint for external applications.
    
    Send a message to the AutoYou AI Agent and receive a response.
    Supports session management for conversation continuity.
    """
    return await process_chat_message(chat_request)

@app.get("/api/sessions/{user_id}/{session_id}", response_model=SessionInfo)
async def get_session_endpoint(user_id: str, session_id: str):
    """
    Get information about a specific session.
    """
    return await get_session_info(user_id, session_id)

@app.get("/api/status", response_model=APIStatus)
async def api_status_endpoint():
    """
    Get the current API status and agent information.
    """
    return await get_api_status()

@app.get("/api/docs")
async def api_documentation():
    """
    API documentation endpoint with usage examples.
    """
    return {
        "title": "AutoYou AI Agent REST API",
        "version": "1.0.0",
        "description": "REST API for interacting with AutoYou AI Agent",
        "endpoints": {
            "/api/chat": {
                "method": "POST",
                "description": "Send a message to the agent and receive a response",
                "example_request": {
                    "message": "Hello, how can you help me?",
                    "session_id": "optional-session-id",
                    "user_id": "user123",
                    "context": [],
                    "metadata": {}
                },
                "example_response": {
                    "response": "Hello! I'm AutoYou, your AI assistant...",
                    "session_id": "generated-or-provided-session-id",
                    "message_id": "unique-message-id",
                    "timestamp": "2025-01-27T10:30:00Z",
                    "agent_name": "AutoYou AI Agent",
                    "metadata": {}
                }
            },
            "/api/sessions/{user_id}/{session_id}": {
                "method": "GET",
                "description": "Get information about a specific session"
            },
            "/api/status": {
                "method": "GET", 
                "description": "Get API status and agent information"
            }
        },
        "usage_notes": [
            "All endpoints return JSON responses",
            "Session IDs are automatically generated if not provided",
            "Context is maintained automatically within sessions",
            "The agent supports multi-agent routing for specialized tasks"
        ]
    }

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AutoYou AI Agent Server")
    parser.add_argument("--port", type=int, default=8001,
                        help="Port to run the server on (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host to bind the server to (default: 0.0.0.0)")
    args = parser.parse_args()

    print("Starting AutoYou AI Agent FastAPI server...")
    print(f"Agent directory: {AGENT_DIR}")
    print(f"Access the web UI at: http://localhost:{args.port}/dev-ui/?app={AGENT_NAME}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=False
    )
