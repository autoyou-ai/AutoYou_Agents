# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
Session management utilities for AutoYou AI Agent.

This module provides session management functionality including
session creation, retrieval, and metrics tracking.
"""
import os
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions with SQLite storage.
    """
    
    def __init__(self, db_path: str = os.path.join(os.path.dirname(__file__), "sessions.db")):
        """
        Initialize the session manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, session_id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_session 
                    ON sessions(user_id, session_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_updated_at 
                    ON sessions(updated_at)
                """)
                
                conn.commit()
                logger.info(f"Session database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize session database: {e}")
            raise
    
    def create_user_session(self, user_id: str, session_id: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user session.
        
        Args:
            user_id: The user identifier
            session_id: The session identifier
            initial_state: Initial session state data
            
        Returns:
            The created session data
        """
        try:
            with self._lock:
                session_data = {
                    **initial_state,
                    "user_id": user_id,
                    "session_id": session_id,
                    "created_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat()
                }
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO sessions 
                        (id, user_id, session_id, data, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        f"{user_id}:{session_id}",
                        user_id,
                        session_id,
                        json.dumps(session_data)
                    ))
                    conn.commit()
                
                logger.info(f"Created session {session_id} for user {user_id}")
                return session_data
                
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def get_user_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user session by ID.
        
        Args:
            user_id: The user identifier
            session_id: The session identifier
            
        Returns:
            Session data if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT data FROM sessions 
                    WHERE user_id = ? AND session_id = ?
                """, (user_id, session_id))
                
                row = cursor.fetchone()
                if row:
                    session_data = json.loads(row[0])
                    # Update last activity
                    session_data["last_activity"] = datetime.now().isoformat()
                    
                    # Update in database
                    conn.execute("""
                        UPDATE sessions 
                        SET data = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND session_id = ?
                    """, (json.dumps(session_data), user_id, session_id))
                    conn.commit()
                    
                    return session_data
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    def update_user_session(self, user_id: str, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing user session with provided fields and persist to DB.
        
        Args:
            user_id: The user identifier
            session_id: The session identifier
            updates: A dictionary of fields to update in the session data
        
        Returns:
            The updated session data if successful, None otherwise
        """
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT data FROM sessions WHERE user_id = ? AND session_id = ?",
                        (user_id, session_id)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    session_data = json.loads(row[0])
                    # Merge updates
                    if updates:
                        session_data.update(updates)
                    # Always refresh last activity
                    session_data["last_activity"] = datetime.now().isoformat()
                    
                    conn.execute(
                        "UPDATE sessions SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND session_id = ?",
                        (json.dumps(session_data), user_id, session_id)
                    )
                    conn.commit()
                    return session_data
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return None


class SessionMetrics:
    """
    Tracks session metrics and statistics.
    """
    
    def __init__(self, db_path: str = os.path.join(os.path.dirname(__file__), "sessions.db")):
        """
        Initialize the session metrics tracker.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._message_counts = {}
        self._lock = threading.Lock()
    
    def record_message(self, user_id: str, session_id: str):
        """
        Record a message for metrics tracking.
        
        Args:
            user_id: The user identifier
            session_id: The session identifier
        """
        try:
            with self._lock:
                key = f"{user_id}:{session_id}"
                self._message_counts[key] = self._message_counts.get(key, 0) + 1
                
        except Exception as e:
            logger.error(f"Failed to record message metric: {e}")
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """
        Get basic session statistics.
        
        Returns:
            Dictionary containing basic statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get total sessions
                cursor = conn.execute("SELECT COUNT(*) FROM sessions")
                total_sessions = cursor.fetchone()[0]
                
                # Get total messages from in-memory counter
                total_messages = sum(self._message_counts.values())
                
                # Get active sessions (updated in last hour)
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM sessions 
                    WHERE updated_at > ?
                """, (one_hour_ago,))
                active_sessions = cursor.fetchone()[0]
                
                return {
                    "total_sessions": total_sessions,
                    "active_sessions": active_sessions,
                    "total_messages": total_messages,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "total_messages": 0,
                "timestamp": datetime.now().isoformat()
            }


def format_session_info(session_data: Dict[str, Any]) -> str:
    """
    Format session information for display.
    
    Args:
        session_data: Session data dictionary
        
    Returns:
        Formatted session information string
    """
    try:
        user_id = session_data.get("user_id", "unknown")
        session_id = session_data.get("session_id", "unknown")
        created_at = session_data.get("created_at", "unknown")
        message_count = session_data.get("message_count", 0)
        
        return f"Session {session_id} for user {user_id} (created: {created_at}, messages: {message_count})"
        
    except Exception as e:
        logger.error(f"Failed to format session info: {e}")
        return "Session information unavailable"