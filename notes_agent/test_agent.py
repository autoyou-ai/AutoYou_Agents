#!/usr/bin/env python3
# Copyright (c) 2025 AutoYou
#
# Licensed under the MIT License
#
# This software is released under the MIT License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/MIT

"""
Simplified test script for basic agent functionality.
"""

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_functionality():
    """Test basic agent functionality."""
    print("\n=== Testing Basic Functionality ===")
    try:
        # Import agent functions
        from .agent import create_note, search_notes, list_notes
        
        # Test creating a note
        result = create_note(title="Test Note", content="This is a test note", tags=["test"])
        print(f"Create Note Result: {result}")
        
        # Test listing notes
        result = list_notes(limit=5)
        print(f"List Notes Result: {result}")
        
        # Test searching notes
        result = search_notes(query="test", limit=5)
        print(f"Search Notes Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("AutoYou Notes Agent Test")
    print("========================")
    
    test_basic_functionality()
    
    print("\nTest completed!")