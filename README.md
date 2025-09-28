# AutoYou AI Agent

**AutoYou AI Agent** is an intelligent, multi-agent AI assistant built on Google's AI Development Kit (ADK). It serves as a personal AI assistant with specialized capabilities, featuring a modular architecture that combines general conversation abilities with specialized sub-agents for specific tasks. The primary implementation showcases a sophisticated notes management system powered by local Ollama models with cloud-based Gemini fallback.

## Core Agent System

The **AutoYou AI Agent** is designed as a conversational AI assistant that can:
- Handle general conversations and provide assistance on various topics
- Intelligently route specialized requests to appropriate sub-agents
- Maintain context across conversations and agent interactions
- Operate with both local (Ollama) and cloud-based (Google Gemini) language models

## Notes Agent Implementation

The **Notes Agent** is a specialized sub-agent that provides comprehensive note-taking and management capabilities:
- Natural language-based note creation, search, and organization
- Full-text search with SQLite FTS5 for fast content retrieval
- Persistent storage with comprehensive data validation and security
- Category-based organization and tagging system

## Key Features

### Core AI Agent
*   **Multi-Agent Architecture**: Intelligent routing between general conversation and specialized sub-agents
*   **Context Preservation**: Maintains conversation context across agent interactions
*   **Dual Model Support**: Seamless integration with local Ollama models and cloud-based Google Gemini
*   **Dynamic Model Selection**: Automatically detects and selects the best available language model
*   **ADK Integration**: Built on Google's AI Development Kit for robust agent capabilities

### Notes Agent Capabilities
*   **Comprehensive Note Management**: Create, search, update, delete, and list notes using natural language
*   **Advanced Search**: Full-text search with SQLite FTS5 for fast and accurate content retrieval
*   **Persistent Storage**: Secure SQLite database with comprehensive input validation
*   **Flexible Organization**: Category-based organization with multi-tag support
*   **RESTful API**: Clean web interface for programmatic access

## Project Structure

```
/
├── .gitignore
├── LICENSE
├── README.md
├── __init__.py           # Package initialization with root_agent export
├── agent.py             # Root agent orchestrator with multi-agent routing
├── model_config.py      # Dynamic LLM configuration and selection logic
├── ollama_service.py    # Service for Ollama model discovery and management
├── prompt.py            # Root agent prompt configuration (name, description, instructions)
├── requirements.txt     # Production dependencies
├── server.py            # FastAPI server with ADK integration
└── notes_agent/
    ├── agent.py         # Notes agent implementation with CRUD operations
    ├── notes_tool.py    # Comprehensive notes tool with SQLite FTS5
    ├── prompt.py        # Notes agent prompt configuration (name, description, instructions)
    └── test_agent.py    # Test script for notes agent functionality
```

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd AutoYou_Agents
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Ollama (Recommended)**:
    *   Download and install from [ollama.ai](https://ollama.ai).
    *   Pull a model to be used by the agent (e.g., `qwen3:4b`):
        ```bash
        ollama pull qwen3:4b
        ```

## Usage

You can run the AutoYou AI Agent as a web service with full ADK integration.

### Run OLLAMA

Run OLLAMA. The Google ADK might get stuck or fallback to GEMINI model (GOOGLE_API) if not.

### Start the Server

Execute the following command from the project root:

```bash
python server.py
```

To specify a different host or port:

```bash
python server.py --host 0.0.0.0 --port 8000
```

The server will automatically:
- Set up default environment variables if not configured
- Initialize the session database for conversation persistence
- Enable the ADK Web UI for interactive agent communication
- Start the FastAPI server with CORS support

## Open WebUI in Browser

Once the server is running, open your web browser and navigate to:

```
http://localhost:8000/dev-ui/app=AutoYou_Agents
```

Replace `localhost` and `8000` with your specified host and port if different.


### API Endpoints

The server provides the following endpoints:

*   `GET /health`: Health check endpoint returning service status
*   **ADK Web UI**: Interactive web interface for conversing with the agent (enabled by default)

## Configuration

### Environment Variables

The agent can be configured using a `.env` file in the project root.

```
# Ollama Configuration
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=qwen3:4b

# Google Gemini Configuration (Fallback)
USE_GOOGLE_API=0
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.5-flash
```

### LLM Selection Logic

The agent uses intelligent model selection with the following priority:
1.  **Environment Override**: If `USE_GOOGLE_API=1`, directly use Google Gemini
2.  **Ollama Primary**: The model specified in `OLLAMA_MODEL` if available via Ollama
3.  **Ollama Fallback**: The latest available model from Ollama if the specified model isn't found
4.  **Cloud Fallback**: Google Gemini model specified in `GOOGLE_MODEL` if Ollama is unavailable

## Development

### Extending the Agent

The framework is designed for extensibility. To add new specialized capabilities:
1.  **Create a new tool**: Develop a Python file similar to <mcfile name="agent.py" path="notes_agent\agent.py"></mcfile> with your desired functionality
2.  **Create prompt configuration**: Create a <mcfile name="prompt.py" path="notes_agent\prompt.py"></mcfile> file with agent name, description, and instructions
3.  **Create a specialized agent**: Build an agent implementation that utilizes your new tool and imports from your prompt configuration
4.  **Integrate with root agent**: Add your new agent as a sub-agent in <mcfile name="agent.py" path="agent.py"></mcfile>
5.  **Update routing logic**: Modify the root agent's instruction in <mcfile name="prompt.py" path="prompt.py"></mcfile> to handle routing to your new sub-agent

### Testing

A test script for the notes agent is provided:

```bash
python notes_agent/test_agent.py
```

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new feature branch.
3.  Commit your changes.
4.  Submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

*   Google AI Development Kit (ADK)
*   Ollama for local LLM support
*   The open-source community