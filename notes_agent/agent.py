# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

from google.adk.agents import Agent

from .notes_tool import NotesTool
from .prompt import AGENT_NAME, AGENT_DESCRIPTION, AGENT_INSTRUCTION
from typing import Optional, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize notes tool with database in the current directory where source code is
notes_tool = NotesTool()

def create_note(title: str, content: str, tags: Optional[List[str]] = None, category: Optional[str] = None) -> dict:
    """Create a new note with the given title, content, tags, and category.
    
    Args:
        title: The title of the note
        content: The content/body of the note
        tags: Optional list of tags for the note
        category: Optional category for the note
        
    Returns:
        dict: Result with note_id if successful, or error message
    """
    try:
        result = notes_tool.create_note(
            title=title,
            content=content,
            tags=tags or [],
            category=category
        )
        if result.get('success'):
            return {
                "status": "success",
                "note_id": result['note_id'],
                "message": f"Note '{title}' created successfully with ID {result['note_id']}"
            }
        else:
            return {
                "status": "error",
                "message": result.get('error', 'Unknown error occurred')
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create note: {str(e)}"
        }

def search_notes(query: str, limit: Optional[int] = 10) -> dict:
    """Search for notes containing the given query.
    
    Args:
        query: The search query to find in notes
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        dict: Search results with matching notes
    """
    try:
        results = notes_tool.search_notes(query=query, limit=limit or 10)
        return {
            "status": "success",
            "results": results,
            "count": len(results),
            "message": f"Found {len(results)} notes matching '{query}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to search notes: {str(e)}"
        }

def list_notes(category: Optional[str] = None, limit: Optional[int] = 20) -> dict:
    """List all notes, optionally filtered by category.
    
    Args:
        category: Optional category to filter by
        limit: Maximum number of notes to return (default: 20)
        
    Returns:
        dict: List of notes
    """
    try:
        results = notes_tool.list_notes(category=category, limit=limit or 20)
        return {
            "status": "success",
            "notes": results,
            "count": len(results),
            "message": f"Retrieved {len(results)} notes" + (f" in category '{category}'" if category else "")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list notes: {str(e)}"
        }

def get_note(note_id: int) -> dict:
    """Retrieve a specific note by its ID.
    
    Args:
        note_id: The ID of the note to retrieve
        
    Returns:
        dict: The note data if found, or error message
    """
    try:
        note = notes_tool.get_note(note_id)
        if note:
            return {
                "status": "success",
                "note": note,
                "message": f"Retrieved note {note_id}"
            }
        else:
            return {
                "status": "error",
                "message": f"Note {note_id} not found"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get note: {str(e)}"
        }

def update_note(note_id: int, title: Optional[str] = None, content: Optional[str] = None, 
                tags: Optional[List[str]] = None, category: Optional[str] = None) -> dict:
    """Update an existing note.
    
    Args:
        note_id: The ID of the note to update
        title: New title for the note (optional)
        content: New content for the note (optional)
        tags: New tags for the note (optional)
        category: New category for the note (optional)
        
    Returns:
        dict: Success or error message
    """
    try:
        success = notes_tool.update_note(
            note_id=note_id,
            title=title,
            content=content,
            tags=tags,
            category=category
        )
        if success:
            return {
                "status": "success",
                "message": f"Note {note_id} updated successfully"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to update note {note_id} - note may not exist"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update note: {str(e)}"
        }

def delete_note(note_id: int) -> dict:
    """Delete a note by its ID.
    
    Args:
        note_id: The ID of the note to delete
        
    Returns:
        dict: Success or error message
    """
    try:
        success = notes_tool.delete_note(note_id)
        if success:
            return {
                "status": "success",
                "message": f"Note {note_id} deleted successfully"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to delete note {note_id} - note may not exist"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete note: {str(e)}"
        }

def create_notes_agent(model_config):
    """Create a notes agent with the provided model configuration.
    
    Args:
        model_config: The model configuration to use for the agent
        
    Returns:
        Agent: Configured notes agent
    """
    return Agent(
        name=AGENT_NAME,
        model=model_config,
        description=AGENT_DESCRIPTION,
        instruction=AGENT_INSTRUCTION,
        tools=[
            create_note,
            search_notes,
            list_notes,
            get_note,
            update_note,
            delete_note
        ]
    )
