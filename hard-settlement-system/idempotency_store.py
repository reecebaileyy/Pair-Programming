"""
Idempotency Store for Settlement Engine

Tracks processed operations to prevent duplicates.

BUG: Currently uses in-memory dict, doesn't survive restarts!
"""

import threading
import json
import os
from typing import Optional, Dict


class IdempotencyStore:
    """
    Store for tracking idempotency keys.
    
    BUG: Using in-memory dict means state is lost on restart!
    
    In production, this would be:
    - Database (PostgreSQL with unique constraint)
    - Redis (persistent mode)
    - Distributed cache
    
    For this exercise, needs to survive "restarts".
    Hint: Use a JSON file for persistence.
    """
    
    def __init__(self, persistence_file: Optional[str] = None):
        """
        Initialize idempotency store.
        
        Args:
            persistence_file: Path to file for persistence (if None, in-memory only)
        """
        # BUG: In-memory dict - lost on restart!
        self.store: Dict[str, str] = {}  # idempotency_key -> settlement_id
        
        self.lock = threading.Lock()
        
        # TODO: Implement persistence!
        # If persistence_file provided, load from disk
        self.persistence_file = persistence_file
        
        if self.persistence_file:
            self._load_from_disk()
    
    def put(self, idempotency_key: str, settlement_id: str):
        """
        Record an idempotency key.
        
        BUG: Only stores in memory!
        TODO: Persist to disk immediately after storing
        """
        with self.lock:
            self.store[idempotency_key] = settlement_id
            
            # TODO: Persist to disk!
            # if self.persistence_file:
            #     self._save_to_disk()
    
    def get(self, idempotency_key: str) -> Optional[str]:
        """
        Get settlement ID for an idempotency key.
        
        Returns:
            Settlement ID if key exists, None otherwise
        """
        with self.lock:
            return self.store.get(idempotency_key)
    
    def delete(self, idempotency_key: str):
        """Delete an idempotency key"""
        with self.lock:
            if idempotency_key in self.store:
                del self.store[idempotency_key]
                
                # TODO: Persist to disk!
                # if self.persistence_file:
                #     self._save_to_disk()
    
    def _load_from_disk(self):
        """
        Load idempotency store from disk.
        
        TODO: Implement this!
        """
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return
        
        try:
            # TODO: Load from JSON file
            # with open(self.persistence_file, 'r') as f:
            #     self.store = json.load(f)
            pass
        except Exception as e:
            print(f"Error loading idempotency store: {e}")
    
    def _save_to_disk(self):
        """
        Save idempotency store to disk.
        
        TODO: Implement this!
        """
        if not self.persistence_file:
            return
        
        try:
            # TODO: Save to JSON file
            # with open(self.persistence_file, 'w') as f:
            #     json.dump(self.store, f)
            pass
        except Exception as e:
            print(f"Error saving idempotency store: {e}")
    
    def clear(self):
        """Clear all idempotency keys (for testing)"""
        with self.lock:
            self.store.clear()
            if self.persistence_file and os.path.exists(self.persistence_file):
                os.remove(self.persistence_file)


# Hint for implementation:
#
# def _load_from_disk(self):
#     if not self.persistence_file or not os.path.exists(self.persistence_file):
#         return
#     try:
#         with open(self.persistence_file, 'r') as f:
#             self.store = json.load(f)
#     except Exception as e:
#         print(f"Error loading: {e}")
#
# def _save_to_disk(self):
#     if not self.persistence_file:
#         return
#     try:
#         # Create directory if needed
#         os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
#         with open(self.persistence_file, 'w') as f:
#             json.dump(self.store, f)
#     except Exception as e:
#         print(f"Error saving: {e}")

