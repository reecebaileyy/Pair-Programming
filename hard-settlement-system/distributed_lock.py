"""
Distributed Lock Manager

Provides distributed locking with TTL for preventing concurrent processing.

WARNING: This is a skeleton implementation with TODOs!
"""

import threading
import time
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class LockInfo:
    """Information about a held lock"""
    lock_key: str
    holder_id: str
    acquired_at: float  # timestamp
    ttl_seconds: float
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        return time.time() > (self.acquired_at + self.ttl_seconds)


class DistributedLockManager:
    """
    Manages distributed locks with TTL.
    
    In production, this would use Redis (Redlock algorithm) or etcd.
    For this exercise, simulating with in-memory dict + locks.
    
    TODO: Complete the implementation!
    
    Requirements:
    - Only one holder can acquire a lock at a time
    - Locks automatically expire after TTL (handle crashed holders)
    - Thread-safe
    - Deadlock-free
    """
    
    def __init__(self):
        # Stores active locks: lock_key -> LockInfo
        self.locks: Dict[str, LockInfo] = {}
        
        # Lock for protecting the locks dict itself
        self.manager_lock = threading.Lock()
    
    def acquire(
        self,
        lock_key: str,
        holder_id: str,
        ttl_seconds: float = 30.0
    ) -> bool:
        """
        Try to acquire a lock.
        
        TODO: Implement this properly!
        
        Logic:
        1. Check if lock exists
        2. If exists and not expired, return False (someone else holds it)
        3. If exists but expired, clean it up and acquire
        4. If doesn't exist, acquire
        
        Args:
            lock_key: Unique identifier for the lock
            holder_id: ID of the holder (e.g., worker name)
            ttl_seconds: Time-to-live for the lock
            
        Returns:
            True if acquired, False if already held by another
        """
        with self.manager_lock:
            # TODO: Implement lock acquisition logic
            
            # Check if lock exists
            if lock_key in self.locks:
                existing_lock = self.locks[lock_key]

                if existing_lock.is_expired():
                    del self.locks[lock_key]
                elif existing_lock.holder_id == holder_id:
                    existing_lock.acquired_at = time.time()
                    return True  # Reentrant acquisition by same holder
                else:
                    return False
                
                # TODO: Check if expired
                # If expired, clean up and allow acquisition
                # If not expired and held by someone else, return False
                # If held by same holder, allow (reentrant)
            
            # TODO: Acquire the lock
            self.locks[lock_key] = LockInfo(lock_key, holder_id, time.time(), ttl_seconds)
            
            return True

        
        
        # TEMPORARY: Return True to allow tests to run
        # You should replace this with proper logic!
        return True
    
    def release(
        self,
        lock_key: str,
        holder_id: str
    ) -> bool:
        """
        Release a lock.
        
        TODO: Implement this!
        
        Logic:
        1. Check if lock exists
        2. Check if held by this holder
        3. If yes, remove from dict
        4. If no, return False
        
        Args:
            lock_key: Lock identifier
            holder_id: ID of the holder releasing
            
        Returns:
            True if released, False if not held by this holder
        """
        with self.manager_lock:
            # TODO: Implement lock release
            
            # Check if lock exists and is held by this holder
            # If yes, remove it
            # If no, return False
            
            pass  # Remove this and implement!
        
        # TEMPORARY
        return True
    
    def extend(
        self,
        lock_key: str,
        holder_id: str,
        additional_ttl: float
    ) -> bool:
        """
        Extend the TTL of a held lock.
        
        TODO: Implement this! (Optional, but useful)
        
        Useful for long-running operations that need to keep the lock.
        
        Args:
            lock_key: Lock identifier
            holder_id: ID of the holder
            additional_ttl: Additional seconds to add to TTL
            
        Returns:
            True if extended, False if not held by this holder
        """
        with self.manager_lock:
            # TODO: Implement lock extension
            
            pass
        
        return False
    
    def is_locked(self, lock_key: str) -> bool:
        """
        Check if a lock is currently held.
        
        Accounts for TTL expiry.
        """
        with self.manager_lock:
            if lock_key not in self.locks:
                return False
            
            lock_info = self.locks[lock_key]
            
            # If expired, clean up and return False
            if lock_info.is_expired():
                del self.locks[lock_key]
                return False
            
            return True
    
    def cleanup_expired_locks(self) -> int:
        """
        Clean up expired locks.
        
        This would run periodically in production.
        
        Returns:
            Number of locks cleaned up
        """
        with self.manager_lock:
            expired_keys = [
                key for key, lock_info in self.locks.items()
                if lock_info.is_expired()
            ]
            
            for key in expired_keys:
                del self.locks[key]
            
            return len(expired_keys)
    
    def get_lock_info(self, lock_key: str) -> Optional[LockInfo]:
        """Get information about a lock (for debugging/testing)"""
        with self.manager_lock:
            return self.locks.get(lock_key)


# Hint for implementation:
# 
# def acquire(self, lock_key, holder_id, ttl_seconds):
#     with self.manager_lock:
#         if lock_key in self.locks:
#             existing = self.locks[lock_key]
#             if existing.is_expired():
#                 del self.locks[lock_key]
#             elif existing.holder_id == holder_id:
#                 return True  # Reentrant
#             else:
#                 return False  # Held by someone else
#         
#         self.locks[lock_key] = LockInfo(
#             lock_key=lock_key,
#             holder_id=holder_id,
#             acquired_at=time.time(),
#             ttl_seconds=ttl_seconds
#         )
#         return True

