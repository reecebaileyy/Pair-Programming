"""
Payment Transaction Processor for Circle Payment APIs

This module handles payment processing with idempotency guarantees.
NOTE: This code has bugs! It's part of a debugging exercise.
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import threading


@dataclass
class PaymentResult:
    """Result of a payment operation"""
    success: bool
    transaction_id: str
    amount: float
    message: str
    timestamp: datetime


class PaymentProcessor:
    """
    Processes payments with idempotency guarantees.
    
    WARNING: This implementation has concurrency and idempotency bugs!
    """
    
    def __init__(self):
        # User balances: user_id -> balance
        self.balances: Dict[str, float] = {}
        
        # Idempotency tracking: idempotency_key -> PaymentResult
        self.processed_payments: Dict[str, PaymentResult] = {}
        
        # Transaction counter for generating unique transaction IDs
        self.transaction_counter = 0
        
        # TODO: Is this lock sufficient? What does it protect?
        self.lock = threading.Lock()
    
    def create_account(self, user_id: str, initial_balance: float = 0.0) -> None:
        """Create a new user account with initial balance"""
        with self.lock:
            if user_id in self.balances:
                raise ValueError(f"Account {user_id} already exists")
            self.balances[user_id] = initial_balance
    
    def get_balance(self, user_id: str) -> float:
        """Get current balance for a user"""
        # BUG? Should this be thread-safe?
        if user_id not in self.balances:
            raise ValueError(f"Account {user_id} does not exist")
        return self.balances[user_id]
    
    def process_payment(
        self, 
        user_id: str, 
        amount: float, 
        idempotency_key: str
    ) -> PaymentResult:
        """
        Process a payment with idempotency guarantee.
        
        Args:
            user_id: The user making the payment
            amount: Payment amount (must be positive)
            idempotency_key: Unique key to prevent duplicate processing
            
        Returns:
            PaymentResult with transaction details
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        
        # BUG ALERT: Check if this payment was already processed
        # Is this check happening at the right time?
        if idempotency_key in self.processed_payments:
            return self.processed_payments[idempotency_key]
        
        # Check if user exists and has sufficient balance
        if user_id not in self.balances:
            raise ValueError(f"Account {user_id} does not exist")
        
        # BUG ALERT: This balance check and deduction is not atomic!
        # What happens if multiple threads execute this simultaneously?
        current_balance = self.balances[user_id]
        if current_balance < amount:
            result = PaymentResult(
                success=False,
                transaction_id="",
                amount=amount,
                message=f"Insufficient funds. Balance: {current_balance}, Required: {amount}",
                timestamp=datetime.now()
            )
            return result
        
        # Deduct the amount
        self.balances[user_id] = current_balance - amount
        
        # Generate transaction ID
        with self.lock:
            self.transaction_counter += 1
            transaction_id = f"txn_{self.transaction_counter:06d}"
        
        # Create successful result
        result = PaymentResult(
            success=True,
            transaction_id=transaction_id,
            amount=amount,
            message="Payment processed successfully",
            timestamp=datetime.now()
        )
        
        # BUG ALERT: Recording the idempotency key after processing
        # Is the timing of this correct?
        self.processed_payments[idempotency_key] = result
        
        return result
    
    def refund_payment(
        self, 
        user_id: str, 
        amount: float, 
        idempotency_key: str,
        original_transaction_id: str
    ) -> PaymentResult:
        """
        Process a refund (add money back to account).
        
        Args:
            user_id: The user receiving the refund
            amount: Refund amount (must be positive)
            idempotency_key: Unique key to prevent duplicate refunds
            original_transaction_id: The transaction being refunded
            
        Returns:
            PaymentResult with refund details
        """
        if amount <= 0:
            raise ValueError("Refund amount must be positive")
        
        # TODO: Check if this refund was already processed (idempotency)
        # HINT: Similar to process_payment, but for refunds
        
        # TODO: Verify user exists
        
        # TODO: Add the amount back to the user's balance
        # HINT: Think about thread safety!
        
        # TODO: Generate a transaction ID for the refund
        
        # TODO: Create and store the result
        
        # TODO: Return the result
        
        raise NotImplementedError("Refund functionality not yet implemented")
    
    def get_transaction_count(self) -> int:
        """Get total number of transactions processed"""
        with self.lock:
            return self.transaction_counter

