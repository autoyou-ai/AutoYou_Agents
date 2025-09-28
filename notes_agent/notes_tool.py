# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

import sqlite3
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

class NotesTool:
    """Native note-taking tool for AutoYou agent with SQLite storage."""
    
    # Security constants
    MAX_TITLE_LENGTH = 1000
    MAX_CONTENT_LENGTH = 100000000
    MAX_CATEGORY_LENGTH = 1000
    MAX_TAG_LENGTH = 1000
    MAX_TAGS_COUNT = 1000
    SEARCH_LIMIT_MAX = 1000
    DB_TIMEOUT = 30.0
    
    # Query and display limits
    MAX_QUERY_LENGTH = 1000
    DEFAULT_SEARCH_LIMIT = 100
    DEFAULT_LIST_LIMIT = 200
    CONTENT_TRUNCATE_LENGTH = 200
    
    ALLOWED_COLUMNS = {'title', 'content', 'tags', 'category'}  # Whitelist for dynamic queries
    
    def __init__(self, db_path: str = os.path.join(os.path.dirname(__file__), "autoyou_notes.db")):
        self.db_path = self._validate_db_path(db_path)
        self._init_notes_database()
    
    def _validate_db_path(self, db_path: str) -> str:
        """Validate and sanitize database path to prevent path traversal attacks."""
        if not db_path or not isinstance(db_path, str):
            raise ValueError("Database path must be a non-empty string")
        
        # Remove any path traversal attempts
        db_path = db_path.replace('..', '').replace('//', '/').replace('\\\\', '\\')
        
        # Ensure it ends with .db extension
        if not db_path.endswith('.db'):
            db_path += '.db'
        
        return db_path
    
    def _validate_input(self, title: Optional[str] = None, content: Optional[str] = None, 
                       tags: Optional[List[str]] = None, category: Optional[str] = None,
                       note_id: Optional[int] = None, query: Optional[str] = None) -> None:
        """Validate all input parameters to prevent injection and ensure data integrity."""
        
        if title is not None:
            if not isinstance(title, str):
                raise ValueError("Title must be a string")
            if len(title) > self.MAX_TITLE_LENGTH:
                raise ValueError(f"Title too long (max {self.MAX_TITLE_LENGTH} characters)")
            if not title.strip():
                raise ValueError("Title cannot be empty")
        
        if content is not None:
            if not isinstance(content, str):
                raise ValueError("Content must be a string")
            if len(content) > self.MAX_CONTENT_LENGTH:
                raise ValueError(f"Content too long (max {self.MAX_CONTENT_LENGTH} characters)")
        
        if category is not None:
            if not isinstance(category, str):
                raise ValueError("Category must be a string")
            if len(category) > self.MAX_CATEGORY_LENGTH:
                raise ValueError(f"Category too long (max {self.MAX_CATEGORY_LENGTH} characters)")
            # Category can contain any Unicode characters (global languages and emojis)
            # No character restrictions for category
        
        if tags is not None:
            if not isinstance(tags, list):
                raise ValueError("Tags must be a list")
            if len(tags) > self.MAX_TAGS_COUNT:
                raise ValueError(f"Too many tags (max {self.MAX_TAGS_COUNT})")
            for tag in tags:
                if not isinstance(tag, str):
                    raise ValueError("All tags must be strings")
                if len(tag) > self.MAX_TAG_LENGTH:
                    raise ValueError(f"Tag too long (max {self.MAX_TAG_LENGTH} characters)")
                # Tags can contain any Unicode characters (global languages and emojis)
                # No character restrictions for tags
        
        if note_id is not None:
            if not isinstance(note_id, int) or note_id <= 0:
                raise ValueError("Note ID must be a positive integer")
        
        if query is not None:
            if not isinstance(query, str):
                raise ValueError("Query must be a string")
            if len(query) > self.MAX_QUERY_LENGTH:  # Reasonable limit for search queries
                raise ValueError(f"Search query too long (max {self.MAX_QUERY_LENGTH} characters)")
            # Basic FTS injection prevention - remove potentially dangerous characters
            if any(char in query for char in ['"', "'", ';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE', 'INSERT']):
                # Instead of raising error, sanitize the query
                query = re.sub(r'["\';\-\*/]', ' ', query)
                query = re.sub(r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)\b', '', query, flags=re.IGNORECASE)
                query = ' '.join(query.split())  # Normalize whitespace
    
    def _get_db_connection(self):
        """Get a secure database connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.DB_TIMEOUT,  # 30 second timeout
            check_same_thread=False
        )
        # Enable foreign key constraints and other security settings
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous = NORMAL")  # Balance between safety and performance
        return conn
    
    def _init_notes_database(self):
        """Initialize the SQLite database for notes storage."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Create notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    archived BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create full-text search for notes
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_search USING fts5(
                    title, content, tags, category, content='notes', content_rowid='id'
                )
            """)
            
            # Create triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                    INSERT INTO notes_search(rowid, title, content, tags, category) 
                    VALUES (new.id, new.title, new.content, new.tags, new.category);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                    INSERT INTO notes_search(notes_search, rowid, title, content, tags, category) 
                    VALUES('delete', old.id, old.title, old.content, old.tags, old.category);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                    INSERT INTO notes_search(notes_search, rowid, title, content, tags, category) 
                    VALUES('delete', old.id, old.title, old.content, old.tags, old.category);
                    INSERT INTO notes_search(rowid, title, content, tags, category) 
                    VALUES (new.id, new.title, new.content, new.tags, new.category);
                END
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Notes database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize notes database: {e}")
            raise
    
    def create_note(self, title: str, content: str, tags: Optional[List[str]] = None, category: str = "general") -> Dict[str, Any]:
        """Create a new note.
        
        Args:
            title: Note title
            content: Note content
            tags: List of tags (optional)
            category: Note category (default: general)
            
        Returns:
            Dictionary with note details or error message
        """
        try:
            # Validate all inputs
            self._validate_input(title=title, content=content, tags=tags, category=category)
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            tags_json = json.dumps(tags) if tags else None
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO notes (title, content, tags, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, content, tags_json, category, now, now))
            
            note_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Created note with ID: {note_id}")
            return {
                'success': True,
                'note_id': note_id,
                'title': title,
                'category': category,
                'tags': tags or [],
                'created_at': now
            }
            
        except ValueError as e:
            logger.warning(f"Invalid input for create_note: {e}")
            return {'success': False, 'error': f"Invalid input: {str(e)}"}
        except Exception as e:
            logger.error(f"Failed to create note: {e}")
            return {'success': False, 'error': str(e)}
    
    def search_notes(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """Search notes using full-text search."""
        try:
            # Validate inputs
            self._validate_input(query=query)
            
            if limit is None:
                limit = self.DEFAULT_SEARCH_LIMIT
            elif not isinstance(limit, int) or limit <= 0 or limit > self.SEARCH_LIMIT_MAX:
                limit = self.DEFAULT_SEARCH_LIMIT  # Default safe limit
            
            # Sanitize query for FTS
            sanitized_query = self._sanitize_fts_query(query)
            if not sanitized_query.strip():
                return []  # Empty query after sanitization
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Use FTS for search
            cursor.execute("""
                SELECT n.id, n.title, n.content, n.tags, n.category, n.created_at, n.updated_at
                FROM notes n
                JOIN notes_search ns ON n.id = ns.rowid
                WHERE notes_search MATCH ? AND n.archived = FALSE
                ORDER BY rank
                LIMIT ?
            """, (sanitized_query, limit))
            
            results = []
            for row in cursor.fetchall():
                tags = json.loads(row[3]) if row[3] else []
                results.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'tags': tags,
                    'category': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to search notes: {e}")
            return []
    
    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize FTS query to prevent injection attacks."""
        # Remove potentially dangerous FTS operators and SQL keywords
        query = re.sub(r'["\';\-\*/]', ' ', query)
        query = re.sub(r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|MATCH)\b', '', query, flags=re.IGNORECASE)
        
        # Remove FTS-specific operators that could be misused
        query = re.sub(r'[\^\$\*\+\?\{\}\[\]\(\)\|\\]', ' ', query)
        
        # Normalize whitespace and return
        return ' '.join(query.split())
    
    def get_note(self, note_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific note by ID."""
        try:
            # Validate input
            self._validate_input(note_id=note_id)
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, tags, category, created_at, updated_at, archived
                FROM notes WHERE id = ?
            """, (note_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                tags = json.loads(row[3]) if row[3] else []
                return {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'tags': tags,
                    'category': row[4],
                    'created_at': row[5],
                    'updated_at': row[6],
                    'archived': bool(row[7])
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get note {note_id}: {e}")
            return None
    
    def update_note(self, note_id: int, title: Optional[str] = None, 
                   content: Optional[str] = None, tags: Optional[List[str]] = None, 
                   category: Optional[str] = None) -> bool:
        """Update an existing note."""
        try:
            # Validate all inputs
            self._validate_input(note_id=note_id, title=title, content=content, tags=tags, category=category)
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Build dynamic update query using whitelisted columns only
            updates = []
            params = []
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            
            if content is not None:
                updates.append("content = ?")
                params.append(content)
            
            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags))
            
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            
            if not updates:
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(note_id)
            
            # Use parameterized query - safe because we control the column names
            query = f"UPDATE notes SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if success:
                logger.info(f"Updated note {note_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update note {note_id}: {e}")
            return False
    
    def delete_note(self, note_id: int) -> bool:
        """Delete a note (archive it)."""
        try:
            # Validate input
            self._validate_input(note_id=note_id)
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE notes SET archived = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (note_id,))
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if success:
                logger.info(f"Archived note {note_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete note {note_id}: {e}")
            return False
    
    def list_notes(self, category: Optional[str] = None, limit: int = None) -> List[Dict[str, Any]]:
        """List notes, optionally filtered by category."""
        try:
            # Validate inputs
            if category is not None:
                self._validate_input(category=category)
            
            if limit is None:
                limit = self.DEFAULT_LIST_LIMIT
            elif not isinstance(limit, int) or limit <= 0 or limit > self.SEARCH_LIMIT_MAX:
                limit = self.DEFAULT_LIST_LIMIT  # Default safe limit
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            if category:
                cursor.execute("""
                    SELECT id, title, content, tags, category, created_at, updated_at
                    FROM notes WHERE category = ? AND archived = FALSE
                    ORDER BY updated_at DESC LIMIT ?
                """, (category, limit))
            else:
                cursor.execute("""
                    SELECT id, title, content, tags, category, created_at, updated_at
                    FROM notes WHERE archived = FALSE
                    ORDER BY updated_at DESC LIMIT ?
                """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                tags = json.loads(row[3]) if row[3] else []
                results.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2][:self.CONTENT_TRUNCATE_LENGTH] + '...' if len(row[2]) > self.CONTENT_TRUNCATE_LENGTH else row[2],  # Truncate for listing
                    'tags': tags,
                    'category': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to list notes: {e}")
            return []
    
    def get_tool(self) -> FunctionTool:
        """Get the Google ADK FunctionTool for notes functionality."""
        
        def notes_function(action: str, title: Optional[str] = None, content: Optional[str] = None, 
                          tags: Optional[List[str]] = None, category: Optional[str] = None,
                          query: Optional[str] = None, note_id: Optional[int] = None, 
                          limit: Optional[int] = None) -> str:
            """Handle notes operations with comprehensive input validation.
            
            Args:
                action: The action to perform (create, search, get, list, update, delete)
                title: Note title (required for create, optional for update)
                content: Note content (required for create, optional for update)
                tags: List of tags for the note
                category: Note category (default: general)
                query: Search query for finding notes
                note_id: Note ID for get, update, or delete operations
                limit: Maximum number of results to return
            
            Returns:
                String result of the operation
            """
            try:
                # Validate action parameter
                valid_actions = {"create", "search", "get", "list", "update", "delete"}
                if not action or action not in valid_actions:
                    return f"Error: Invalid action '{action}'. Available actions: {', '.join(valid_actions)}"
                
                # Set defaults
                if tags is None:
                    tags = []
                if category is None:
                    category = "general"
                if limit is None:
                    limit = self.DEFAULT_SEARCH_LIMIT
                    
                if action == "create":
                    if not title or not title.strip():
                        return "Error: Title is required to create a note."
                    if not content or not content.strip():
                        return "Error: Content is required to create a note."
                    
                    result = self.create_note(title.strip(), content.strip(), tags, category)
                    if result.get('success'):
                        return f"Note created successfully with ID: {result['note_id']}"
                    else:
                        return f"Error creating note: {result.get('error', 'Unknown error')}"
                
                elif action == "search":
                    if not query or not query.strip():
                        return "Error: Search query is required."
                    
                    results = self.search_notes(query.strip(), limit)
                    if results:
                        return f"Found {len(results)} notes:\n" + "\n".join([
                            f"ID: {note['id']}, Title: {note['title']}, Category: {note['category']}"
                            for note in results
                        ])
                    else:
                        return "No notes found matching your search."
                
                elif action == "get":
                    if note_id is None:
                        return "Error: Note ID is required."
                    
                    note = self.get_note(note_id)
                    if note:
                        return f"Title: {note['title']}\nContent: {note['content']}\nTags: {', '.join(note['tags'])}\nCategory: {note['category']}"
                    else:
                        return "Note not found."
                
                elif action == "list":
                    list_category = None if category == "general" else category
                    notes = self.list_notes(list_category, limit)
                    if notes:
                        return f"Found {len(notes)} notes:\n" + "\n".join([
                            f"ID: {note['id']}, Title: {note['title']}, Category: {note['category']}"
                            for note in notes
                        ])
                    else:
                        return "No notes found."
                
                elif action == "update":
                    if note_id is None:
                        return "Error: Note ID is required."
                    
                    # Prepare update parameters
                    update_title = title.strip() if title and title.strip() else None
                    update_content = content.strip() if content and content.strip() else None
                    update_category = None if category == "general" else category
                    
                    result = self.update_note(note_id, update_title, update_content, tags, update_category)
                    if result.get('success'):
                        return f"Note updated successfully. Updated {result.get('updated_fields', 0)} fields."
                    else:
                        return f"Error updating note: {result.get('error', 'Unknown error')}"
                
                elif action == "delete":
                    if note_id is None:
                        return "Error: Note ID is required."
                    
                    result = self.delete_note(note_id)
                    if result.get('success'):
                        return "Note deleted successfully."
                    else:
                        return f"Error deleting note: {result.get('error', 'Unknown error')}"
                    
            except ValueError as e:
                logger.warning(f"Invalid input in notes function: {e}")
                return f"Error: {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error in notes function: {e}")
                return f"Error: An unexpected error occurred. Please try again."
        
        return FunctionTool(notes_function)