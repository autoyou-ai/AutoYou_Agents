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
from datetime import datetime, timedelta
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
    
    def _validate_date_input(self, date_filter: Optional[str] = None) -> Optional[str]:
        """Validate and normalize date input for filtering."""
        if date_filter is None:
            return None
            
        if not isinstance(date_filter, str):
            raise ValueError("Date filter must be a string")
            
        # Handle common date formats and keywords
        date_filter = date_filter.lower().strip()
        
        if date_filter in ['today', 'now']:
            return datetime.now().date().isoformat()
        elif date_filter == 'yesterday':
            yesterday = datetime.now().date() - timedelta(days=1)
            return yesterday.isoformat()
        elif date_filter in ['this week', 'week']:
            # Return start of current week (Monday)
            today = datetime.now().date()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
            return week_start.isoformat()
        elif date_filter in ['this month', 'month']:
            # Return start of current month
            today = datetime.now().date()
            month_start = today.replace(day=1)
            return month_start.isoformat()
        else:
            # Try to parse as ISO date (YYYY-MM-DD)
            try:
                parsed_date = datetime.fromisoformat(date_filter).date()
                return parsed_date.isoformat()
            except ValueError:
                # Try other common formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        parsed_date = datetime.strptime(date_filter, fmt).date()
                        return parsed_date.isoformat()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid date format: {date_filter}. Use YYYY-MM-DD, 'today', 'yesterday', 'this week', or 'this month'")

    def list_notes(self, category: Optional[str] = None, limit: int = None, 
                   created_after: Optional[str] = None, created_before: Optional[str] = None,
                   created_on: Optional[str] = None) -> List[Dict[str, Any]]:
        """List notes, optionally filtered by category and/or date.
        
        Args:
            category: Filter by category (optional)
            limit: Maximum number of results (optional)
            created_after: Show notes created after this date (YYYY-MM-DD or keywords like 'today')
            created_before: Show notes created before this date (YYYY-MM-DD or keywords like 'today')
            created_on: Show notes created on this specific date (YYYY-MM-DD or keywords like 'today')
        """
        try:
            # Validate inputs
            if category is not None:
                self._validate_input(category=category)
            
            if limit is None:
                limit = self.DEFAULT_LIST_LIMIT
            elif not isinstance(limit, int) or limit <= 0 or limit > self.SEARCH_LIMIT_MAX:
                limit = self.DEFAULT_LIST_LIMIT  # Default safe limit
            
            # Validate and normalize date inputs
            created_after_date = self._validate_date_input(created_after)
            created_before_date = self._validate_date_input(created_before)
            created_on_date = self._validate_date_input(created_on)
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Build dynamic query
            where_conditions = ["archived = FALSE"]
            params = []
            
            if category:
                where_conditions.append("category = ?")
                params.append(category)
            
            if created_on_date:
                # For "created on" we want the entire day
                where_conditions.append("DATE(created_at) = ?")
                params.append(created_on_date)
            else:
                if created_after_date:
                    where_conditions.append("DATE(created_at) >= ?")
                    params.append(created_after_date)
                
                if created_before_date:
                    where_conditions.append("DATE(created_at) <= ?")
                    params.append(created_before_date)
            
            where_clause = " AND ".join(where_conditions)
            params.append(limit)
            
            query = f"""
                SELECT id, title, content, tags, category, created_at, updated_at
                FROM notes WHERE {where_clause}
                ORDER BY updated_at DESC LIMIT ?
            """
            
            cursor.execute(query, params)
            
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
                          limit: Optional[int] = None, created_after: Optional[str] = None,
                          created_before: Optional[str] = None, created_on: Optional[str] = None) -> str:
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
                created_after: Filter notes created after this date (YYYY-MM-DD or 'today', 'yesterday', etc.)
                created_before: Filter notes created before this date (YYYY-MM-DD or 'today', 'yesterday', etc.)
                created_on: Filter notes created on this specific date (YYYY-MM-DD or 'today', 'yesterday', etc.)
            
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
                    
                    result = self.create_note(title, content, tags, category)
                    if result['success']:
                        return f"✅ Note created successfully!\n📝 Title: {result['title']}\n🏷️ Category: {result['category']}\n🆔 ID: {result['note_id']}"
                    else:
                        return f"❌ Failed to create note: {result['error']}"
                
                elif action == "search":
                    if not query or not query.strip():
                        return "Error: Search query is required."
                    
                    results = self.search_notes(query, limit)
                    if not results:
                        return f"🔍 No notes found matching '{query}'"
                    
                    response = f"🔍 Found {len(results)} note(s) matching '{query}':\n\n"
                    for note in results:
                        tags_str = f" 🏷️ {', '.join(note['tags'])}" if note['tags'] else ""
                        response += f"📝 **{note['title']}** (ID: {note['id']})\n"
                        response += f"   📂 Category: {note['category']}{tags_str}\n"
                        response += f"   📄 Content: {note['content'][:100]}{'...' if len(note['content']) > 100 else ''}\n"
                        response += f"   📅 Created: {note['created_at']}\n\n"
                    
                    return response.strip()
                
                elif action == "get":
                    if note_id is None:
                        return "Error: Note ID is required to get a note."
                    
                    note = self.get_note(note_id)
                    if not note:
                        return f"❌ Note with ID {note_id} not found."
                    
                    tags_str = f"\n🏷️ Tags: {', '.join(note['tags'])}" if note['tags'] else ""
                    archived_str = " (ARCHIVED)" if note.get('archived') else ""
                    
                    return f"📝 **{note['title']}**{archived_str}\n" \
                           f"🆔 ID: {note['id']}\n" \
                           f"📂 Category: {note['category']}{tags_str}\n" \
                           f"📄 Content:\n{note['content']}\n" \
                           f"📅 Created: {note['created_at']}\n" \
                           f"🔄 Updated: {note['updated_at']}"
                
                elif action == "list":
                    results = self.list_notes(category, limit, created_after, created_before, created_on)
                    if not results:
                        filter_desc = []
                        if category:
                            filter_desc.append(f"category '{category}'")
                        if created_on:
                            filter_desc.append(f"created on {created_on}")
                        elif created_after or created_before:
                            if created_after and created_before:
                                filter_desc.append(f"created between {created_after} and {created_before}")
                            elif created_after:
                                filter_desc.append(f"created after {created_after}")
                            elif created_before:
                                filter_desc.append(f"created before {created_before}")
                        
                        filter_text = " with " + " and ".join(filter_desc) if filter_desc else ""
                        return f"📋 No notes found{filter_text}."
                    
                    # Build filter description for response
                    filter_desc = []
                    if category:
                        filter_desc.append(f"category '{category}'")
                    if created_on:
                        filter_desc.append(f"created on {created_on}")
                    elif created_after or created_before:
                        if created_after and created_before:
                            filter_desc.append(f"created between {created_after} and {created_before}")
                        elif created_after:
                            filter_desc.append(f"created after {created_after}")
                        elif created_before:
                            filter_desc.append(f"created before {created_before}")
                    
                    filter_text = " (" + ", ".join(filter_desc) + ")" if filter_desc else ""
                    
                    response = f"📋 Your notes{filter_text}:\n\n"
                    for i, note in enumerate(results, 1):
                        tags_str = f" 🏷️ {', '.join(note['tags'])}" if note['tags'] else ""
                        response += f"{i}. **{note['title']}** ({note['category']}){tags_str}\n"
                        response += f"   📄 Content: {note['content']}\n"
                        response += f"   📅 Created: {note['created_at']}\n\n"
                    
                    return response.strip()

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