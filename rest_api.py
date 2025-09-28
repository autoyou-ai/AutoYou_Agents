# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
REST API module for AutoYou AI Agent.

This module provides REST API endpoints that allow external chat applications
to interact with the ADK agent by sending full request messages and receiving
full response messages.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from agent import root_agent
from session_utils import SessionManager, SessionMetrics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session manager and metrics
session_manager = SessionManager()
session_metrics = SessionMetrics()

# Global ADK instances (shared across requests)
adk_runner = None
adk_session_service = None

def initialize_adk():
    """Initialize ADK components once at startup."""
    global adk_runner, adk_session_service
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from agent import root_agent
        
        # Shared session service and runner wired to it
        adk_session_service = InMemorySessionService()
        adk_runner = Runner(agent=root_agent, app_name="AutoYou_Agents", session_service=adk_session_service)
        logger.info("ADK components initialized successfully")
    except ImportError as e:
        logger.warning(f"ADK not available: {e}")
        adk_runner = None
        adk_session_service = None

# Initialize ADK at startup
initialize_adk()

class ChatRequest(BaseModel):
    """Request model for chat API."""
    message: str = Field(..., description="The user's message to send to the agent")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field("AutoYou-client", description="User ID for session management")
    context: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Previous conversation context")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the request")

class ChatResponse(BaseModel):
    """Response model for chat API."""
    response: str = Field(..., description="The agent's response message")
    session_id: str = Field(..., description="Session ID for this conversation")
    message_id: str = Field(..., description="Unique ID for this message exchange")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the response")
    agent_name: str = Field(..., description="Name of the agent that responded")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional response metadata")

class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    message_count: int = Field(..., description="Number of messages in this session")

class APIStatus(BaseModel):
    """API status model."""
    status: str = Field(..., description="API status")
    version: str = Field("1.0.0", description="API version")
    agent_name: str = Field(..., description="Agent name")
    timestamp: datetime = Field(default_factory=datetime.now, description="Status timestamp")

async def process_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message using the ADK agent and return the response.
    
    Args:
        request: The chat request containing message and metadata
        
    Returns:
        ChatResponse with the agent's reply and session information
    """
    try:
        # Debug: Log the request context type and content
        logger.info(f"Request context type: {type(request.context)}")
        if request.context:
            logger.info(f"First context item type: {type(request.context[0])}")
            logger.info(f"Context content: {request.context}")
        # Start processing timer
        start_time = datetime.now()
        
        # Generate session ID if not provided
        if not request.session_id:
            request.session_id = str(uuid.uuid4())
        
        # Create or get existing session
        session_data = session_manager.get_user_session(request.user_id, request.session_id)
        if not session_data:
            # Create new session with initial context (ensure it's serializable)
            context_data = []
            if request.context:
                for item in request.context:
                    if isinstance(item, dict):
                        context_data.append(item)
                    elif hasattr(item, 'dict'):
                        # Convert Pydantic model to dict
                        context_data.append(item.dict())
                    else:
                        # Convert any other object to dict
                        context_data.append({
                            "role": getattr(item, 'role', 'user'),
                            "content": getattr(item, 'content', str(item)),
                            "timestamp": getattr(item, 'timestamp', datetime.now()).isoformat() if hasattr(getattr(item, 'timestamp', None), 'isoformat') else str(getattr(item, 'timestamp', datetime.now()))
                        })
            
            initial_state = {
                "user_id": request.user_id,
                "created_at": datetime.now().isoformat(),
                "context": context_data,
                "message_count": 0
            }
            session_data = session_manager.create_user_session(
                request.user_id, 
                request.session_id, 
                initial_state
            )
        
        # Update message count
        current_count = session_data.get("message_count", 0)
        session_data["message_count"] = current_count + 1
        # Persist updated message_count
        session_manager.update_user_session(request.user_id, request.session_id, {"message_count": session_data["message_count"]})
        
        # Try to use ADK agent for processing
        try:
            from google.genai import types
            
            # Use global ADK instances
            if adk_runner is None or adk_session_service is None:
                raise ImportError("ADK components not initialized")
            
            # Use the provided session_id or create a new one
            adk_session_id = request.session_id or f"session_{request.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Ensure the session exists in the shared ADK session service
            await adk_session_service.create_session(
                app_name="AutoYou_Agents",
                user_id=request.user_id,
                session_id=adk_session_id
            )
            logger.info(f"Ensured ADK session exists: {adk_session_id}")
            
            # Build message content with context
            message_content = request.message
            if request.context:
                context_text = "Previous conversation:\n"
                for msg in request.context[-5:]:  # Last 5 messages for context
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_text += f"{role}: {content}\n"
                context_text += f"\nCurrent message: {request.message}"
                message_content = context_text
            
            # Create proper Content object with role and parts
            new_message = types.Content(
                role="user",
                parts=[types.Part(text=message_content)]
            )
            
            # Run the agent and collect response
            response_parts = []
            async for chunk in adk_runner.run_async(
                user_id=request.user_id,
                session_id=adk_session_id,
                new_message=new_message
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    if hasattr(chunk.content, 'parts') and chunk.content.parts:
                        for part in chunk.content.parts:
                            if hasattr(part, 'text') and part.text:
                                response_parts.append(part.text)
                    else:
                        response_parts.append(str(chunk.content))
                elif hasattr(chunk, 'text'):
                    response_parts.append(chunk.text)
                else:
                    response_parts.append(str(chunk))
            
            agent_response = "".join(response_parts) if response_parts else "I'm here to help! How can I assist you today?"
            
        except ImportError as e:
            logger.warning(f"ADK import failed, using fallback: {e}")
            # Fallback response when ADK is not available
            agent_response = f"Hello! I received your message: '{request.message}'. I'm currently running in fallback mode. How can I help you today?"
            
        except Exception as e:
            logger.error(f"Error running ADK agent: {e}")
            # Fallback response for any other errors
            agent_response = f"I apologize, but I encountered an issue processing your request. However, I received your message: '{request.message}'. Please try again or rephrase your question."
        
        # Generate response
        message_id = str(uuid.uuid4())
        
        # Update session metrics
        session_metrics.record_message(request.user_id, request.session_id)
        
        # Prepare response metadata
        end_time = datetime.now()
        processing_time_ms = max(0, int((end_time - start_time).total_seconds() * 1000))
        response_metadata = {
            "session_message_count": session_data.get("message_count", 1),
            "processing_time_ms": processing_time_ms,
            "agent_version": "1.0.0",
            **(request.metadata or {})
        }
        
        return ChatResponse(
            response=agent_response,
            message_id=message_id,
            session_id=request.session_id,
            agent_name="AutoYou AI Agent",
            timestamp=datetime.now(),
            metadata=response_metadata
        )
        
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")

async def get_session_info(user_id: str, session_id: str) -> SessionInfo:
    """
    Get information about a specific session.
    
    Args:
        user_id: The user identifier
        session_id: The session identifier
        
    Returns:
        SessionInfo with session details
    """
    try:
        session_data = session_manager.get_user_session(user_id, session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionInfo(
            session_id=session_id,
            user_id=user_id,
            created_at=session_data.get("created_at", datetime.now().isoformat()),
            last_activity=session_data.get("last_activity", datetime.now().isoformat()),
            message_count=session_data.get("message_count", 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")

async def get_api_status() -> APIStatus:
    """
    Get the current API status and information.
    
    Returns:
        APIStatus with current system information
    """
    try:
        # Get basic session statistics
        stats = session_metrics.get_basic_stats()
        
        return APIStatus(
            status="healthy",
            agent_name="AutoYou AI Agent",
            version="1.0.0",
            active_sessions=stats.get("total_sessions", 0),
            total_messages=stats.get("total_messages", 0),
            uptime_seconds=0,  # Could be calculated if needed
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error getting API status: {e}")
        return APIStatus(
            status="error",
            agent_name="AutoYou AI Agent", 
            version="1.0.0",
            active_sessions=0,
            total_messages=0,
            uptime_seconds=0,
            timestamp=datetime.now()
        )