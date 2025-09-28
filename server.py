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

# Create session service configuration
session_db_kwargs = {
    "echo": False,
}

# Create the FastAPI app using ADK's helper
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_db_kwargs=session_db_kwargs,
    allow_origins=["*"],
    web=True,  # Enable the ADK Web UI
)

# Add custom health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "AutoYou AI Agent"}

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AutoYou Notes Agent Server")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to run the server on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host to bind the server to (default: 0.0.0.0)")
    args = parser.parse_args()

    print("Starting AutoYou Notes Agent FastAPI server...")
    print(f"Agent directory: {AGENT_DIR}")
    print(f"Session database: {SESSION_DB_URL}")
    print(f"Access the web UI at: http://localhost:{args.port}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=False
    )
