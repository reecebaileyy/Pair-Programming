"""
USDC Mint Service

Handles minting of USDC tokens with idempotency and concurrency guarantees.

WARNING: This code has bugs! (Deadlock, expiry handling, incomplete features)
"""

import time
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from storage import Storage, MintRecord


@dataclass
class MintResult:
    """Result of a mint operation"""
    success: bool
    mint_id: str
    amount: float
    message: str
    timestamp: datetime


class MintService:
    """
    Service for minting USDC tokens.
    
    KNOWN ISSUES:
    - Deadlock bug in _transfer_between_accounts
    - Idempotency token expiry not handled properly
    - Rate limiter not implemented
    - Reconciliation logic missing
    """
    
    # Token expiry time in seconds
    IDEMPOTENCY_TOKEN_TTL = 5.0
    
    # Rate limit: max mints per account per second
    MAX_MINTS_PER_SECOND = 10
    
    def __init__(self, storage: Storage):
        self.storage = storage
        
        # TODO: Add rate limiting data structures
        # Hint: Track recent mint timestamps per account
    
    def mint_usdc(
        self,
        account_id: str,
        amount: float,
        blockchain: str,
        idempotency_token: str
    ) -> MintResult:
        """
        Mint USDC tokens for an account.
        
        Args:
            account_id: Account to mint tokens for
            amount: Amount of USDC to mint (must be positive)
            blockchain: Target blockchain (ethereum, solana, etc.)
            idempotency_token: Unique token to prevent duplicate mints
            
        Returns:
            MintResult with operation details
        """
        if amount <= 0:
            raise ValueError("Mint amount must be positive")
        
        # Check idempotency - has this mint already been processed?
        existing_token = self.storage.get_idempotency_token(idempotency_token)
        if existing_token:
            # Return the existing mint result
            existing_mint = self.storage.get_mint(existing_token.mint_id)
            if existing_mint:
                return MintResult(
                    success=True,
                    mint_id=existing_mint.mint_id,
                    amount=existing_mint.amount,
                    message="Mint already processed (idempotent)",
                    timestamp=existing_mint.timestamp
                )
        
        # TODO: Check rate limit before processing
        # if self._check_rate_limit(account_id):
        #     return MintResult(...)
        
        # Acquire account lock for thread safety
        account_lock = self.storage.get_account_lock(account_id)
        
        with account_lock:
            # Generate unique mint ID
            mint_id = self.storage.generate_mint_id()
            
            # Create mint record
            record = MintRecord(
                mint_id=mint_id,
                account_id=account_id,
                amount=amount,
                blockchain=blockchain,
                timestamp=datetime.now(),
                idempotency_token=idempotency_token
            )
            
            # Record in ledger
            self.storage.record_mint(record)
            
            # Update account balance
            self.storage.add_to_balance(account_id, amount)
            
            # Store idempotency token
            self.storage.store_idempotency_token(
                idempotency_token,
                mint_id,
                self.IDEMPOTENCY_TOKEN_TTL
            )
            
            # TODO: Record mint timestamp for rate limiting
            
            return MintResult(
                success=True,
                mint_id=mint_id,
                amount=amount,
                message=f"Minted {amount} USDC on {blockchain}",
                timestamp=record.timestamp
            )
    
    def _transfer_between_accounts(
        self,
        from_account: str,
        to_account: str,
        amount: float
    ) -> bool:
        """
        Transfer USDC between two accounts (internal operation).
        
        DEADLOCK BUG: This method can deadlock with concurrent calls!
        
        Scenario:
        - Thread A: transfer(account1, account2, 100)
        - Thread B: transfer(account2, account1, 50)
        
        Thread A locks account1, waits for account2
        Thread B locks account2, waits for account1
        = DEADLOCK!
        """
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        # BUG: Lock order depends on parameter order!
        # This can cause circular wait conditions
        from_lock = self.storage.get_account_lock(from_account)
        to_lock = self.storage.get_account_lock(to_account)
        
        with from_lock:
            # Check sufficient balance
            from_balance = self.storage.get_balance(from_account)
            if from_balance < amount:
                return False
            
            # BUG: Acquiring second lock while holding first lock
            # If another thread does opposite order = deadlock
            with to_lock:
                # Perform transfer
                self.storage.add_to_balance(from_account, -amount)
                self.storage.add_to_balance(to_account, amount)
                return True
    
    def _check_rate_limit(self, account_id: str) -> bool:
        """
        Check if account has exceeded rate limit.
        
        TODO: Implement rate limiting!
        
        Requirements:
        - Max MAX_MINTS_PER_SECOND mints per account per second
        - Use sliding window approach
        - Thread-safe implementation
        
        Returns:
            True if rate limit exceeded, False otherwise
        """
        # TODO: Implement this!
        # Hints:
        # 1. Track timestamps of recent mints per account
        # 2. Count how many mints in last 1 second
        # 3. If >= MAX_MINTS_PER_SECOND, reject
        # 4. Clean up old timestamps
        
        raise NotImplementedError("Rate limiting not implemented")
    
    def reconcile_failed_mint(self, mint_id: str) -> bool:
        """
        Reconcile a failed mint operation.
        
        TODO: Implement reconciliation logic!
        
        When a mint fails after partial completion:
        1. Check what state was modified
        2. Roll back the changes
        3. Mark the mint as failed
        
        Returns:
            True if reconciliation successful, False otherwise
        """
        # TODO: Implement this!
        # Hints:
        # 1. Look up the mint record
        # 2. Check current account balance
        # 3. Reverse the mint (subtract the amount)
        # 4. Update the mint status
        # 5. Clean up idempotency token
        
        raise NotImplementedError("Reconciliation not implemented")
    
    def get_account_balance(self, account_id: str) -> float:
        """Get current USDC balance for an account"""
        account_lock = self.storage.get_account_lock(account_id)
        with account_lock:
            return self.storage.get_balance(account_id)
    
    def get_mint_details(self, mint_id: str) -> Optional[MintRecord]:
        """Get details of a specific mint"""
        return self.storage.get_mint(mint_id)

