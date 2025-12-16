"""
Storage layer for USDC Mint Service

Simulates a database with thread-safe operations.
"""

import threading
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MintRecord:
    """Record of a USDC mint operation"""
    mint_id: str
    account_id: str
    amount: float
    blockchain: str
    timestamp: datetime
    idempotency_token: str


@dataclass
class IdempotencyToken:
    """Idempotency token with expiration"""
    token: str
    mint_id: str
    created_at: float  # timestamp
    expires_at: float  # timestamp


class Storage:
    """
    Thread-safe storage for mint service.
    
    Provides:
    - Account balance tracking
    - Mint ledger
    - Idempotency token management with TTL
    - Per-account locking
    """
    
    def __init__(self):
        # Account balances: account_id -> balance
        self.balances: Dict[str, float] = {}
        
        # Mint ledger: mint_id -> MintRecord
        self.mint_ledger: Dict[str, MintRecord] = {}
        
        # Idempotency tokens: token -> IdempotencyToken
        self.idempotency_tokens: Dict[str, IdempotencyToken] = {}
        
        # Per-account locks for fine-grained concurrency
        self.account_locks: Dict[str, threading.Lock] = {}
        
        # Global lock for managing account_locks dict itself
        self.locks_lock = threading.Lock()
        
        # Counter for generating mint IDs
        self.mint_counter = 0
        self.counter_lock = threading.Lock()
    
    def create_account(self, account_id: str, initial_balance: float = 0.0) -> None:
        """Create a new account"""
        with self.locks_lock:
            if account_id in self.balances:
                raise ValueError(f"Account {account_id} already exists")
            self.balances[account_id] = initial_balance
            self.account_locks[account_id] = threading.Lock()
    
    def get_account_lock(self, account_id: str) -> threading.Lock:
        """Get the lock for a specific account"""
        with self.locks_lock:
            if account_id not in self.account_locks:
                raise ValueError(f"Account {account_id} does not exist")
            return self.account_locks[account_id]
    
    def get_balance(self, account_id: str) -> float:
        """Get account balance (caller should hold account lock)"""
        if account_id not in self.balances:
            raise ValueError(f"Account {account_id} does not exist")
        return self.balances[account_id]
    
    def set_balance(self, account_id: str, balance: float) -> None:
        """Set account balance (caller should hold account lock)"""
        if account_id not in self.balances:
            raise ValueError(f"Account {account_id} does not exist")
        self.balances[account_id] = balance
    
    def add_to_balance(self, account_id: str, amount: float) -> None:
        """Add to account balance (caller should hold account lock)"""
        if account_id not in self.balances:
            raise ValueError(f"Account {account_id} does not exist")
        self.balances[account_id] += amount
    
    def generate_mint_id(self) -> str:
        """Generate a unique mint ID"""
        with self.counter_lock:
            self.mint_counter += 1
            return f"mint_{self.mint_counter:08d}"
    
    def record_mint(self, record: MintRecord) -> None:
        """Record a mint in the ledger"""
        with self.counter_lock:  # Reusing for simplicity
            if record.mint_id in self.mint_ledger:
                raise ValueError(f"Mint {record.mint_id} already recorded")
            self.mint_ledger[record.mint_id] = record
    
    def get_mint(self, mint_id: str) -> Optional[MintRecord]:
        """Get a mint record"""
        with self.counter_lock:
            return self.mint_ledger.get(mint_id)
    
    def get_account_mints(self, account_id: str) -> List[MintRecord]:
        """Get all mints for an account"""
        with self.counter_lock:
            return [m for m in self.mint_ledger.values() if m.account_id == account_id]
    
    def store_idempotency_token(
        self, 
        token: str, 
        mint_id: str, 
        ttl_seconds: float
    ) -> None:
        """Store an idempotency token with TTL"""
        with self.counter_lock:
            now = time.time()
            self.idempotency_tokens[token] = IdempotencyToken(
                token=token,
                mint_id=mint_id,
                created_at=now,
                expires_at=now + ttl_seconds
            )
    
    def get_idempotency_token(self, token: str) -> Optional[IdempotencyToken]:
        """
        Get an idempotency token if it exists and hasn't expired.
        
        BUG: This doesn't handle expiry correctly!
        """
        with self.counter_lock:
            if token not in self.idempotency_tokens:
                return None
            
            token_obj = self.idempotency_tokens[token]
            
            # Check if expired
            if time.time() > token_obj.expires_at:
                # BUG: We detect it's expired but don't remove it!
                # This causes issues on retry
                return None
            
            return token_obj
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired idempotency tokens. Returns count removed."""
        with self.counter_lock:
            now = time.time()
            expired = [
                token for token, obj in self.idempotency_tokens.items()
                if now > obj.expires_at
            ]
            for token in expired:
                del self.idempotency_tokens[token]
            return len(expired)

