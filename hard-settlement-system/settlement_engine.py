"""
Cross-Chain Settlement Engine for USDC transfers

Orchestrates settlements across multiple blockchains with exactly-once guarantees.

WARNING: This code has critical bugs and incomplete implementations!
- Race condition in status updates
- Uses incomplete distributed lock
- Incomplete retry logic
- No compensation logic
"""

import threading
import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from distributed_lock import DistributedLockManager
from idempotency_store import IdempotencyStore


class SettlementStatus(Enum):
    """Status of a settlement operation"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    BURNING = "BURNING"
    BURNED = "BURNED"
    MINTING = "MINTING"
    MINTED = "MINTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"


@dataclass
class Settlement:
    """Represents a cross-chain settlement"""
    settlement_id: str
    source_chain: str
    dest_chain: str
    amount: float
    user_id: str
    status: SettlementStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    burn_tx_hash: Optional[str] = None
    mint_tx_hash: Optional[str] = None
    
    # TODO: Add lock for thread-safe status updates?
    # Hint: Each settlement needs its own lock


class BlockchainSimulator:
    """
    Simulates blockchain operations (burn/mint).
    
    In production, this would interact with actual blockchains.
    Simulates failures for testing.
    """
    
    def __init__(self):
        self.balances: Dict[str, Dict[str, float]] = {}  # chain -> user -> balance
        self.lock = threading.Lock()
        self.tx_counter = 0
        
        # Failure simulation
        self.should_fail_burn = False
        self.should_fail_mint = False
    
    def set_balance(self, chain: str, user_id: str, amount: float):
        """Set user balance on a chain"""
        with self.lock:
            if chain not in self.balances:
                self.balances[chain] = {}
            self.balances[chain][user_id] = amount
    
    def get_balance(self, chain: str, user_id: str) -> float:
        """Get user balance on a chain"""
        with self.lock:
            return self.balances.get(chain, {}).get(user_id, 0.0)
    
    def burn_tokens(self, chain: str, user_id: str, amount: float) -> str:
        """
        Burn tokens on source chain.
        Returns transaction hash.
        """
        # Simulate network delay
        time.sleep(0.01)
        
        if self.should_fail_burn:
            raise Exception(f"Burn failed on {chain}")
        
        with self.lock:
            current = self.balances.get(chain, {}).get(user_id, 0.0)
            if current < amount:
                raise ValueError(f"Insufficient balance on {chain}")
            
            self.balances[chain][user_id] = current - amount
            self.tx_counter += 1
            return f"burn_tx_{self.tx_counter:06d}"
    
    def mint_tokens(self, chain: str, user_id: str, amount: float) -> str:
        """
        Mint tokens on destination chain.
        Returns transaction hash.
        """
        # Simulate network delay
        time.sleep(0.01)
        
        if self.should_fail_mint:
            raise Exception(f"Mint failed on {chain}")
        
        with self.lock:
            if chain not in self.balances:
                self.balances[chain] = {}
            current = self.balances[chain].get(user_id, 0.0)
            self.balances[chain][user_id] = current + amount
            self.tx_counter += 1
            return f"mint_tx_{self.tx_counter:06d}"


class SettlementEngine:
    """
    Engine for processing cross-chain settlements.
    
    KNOWN BUGS:
    1. Race condition in _update_settlement_status()
    2. Distributed lock not fully implemented
    3. Retry logic incomplete
    4. Compensation logic missing
    """
    
    def __init__(
        self,
        blockchain: BlockchainSimulator,
        lock_manager: DistributedLockManager,
        idempotency_store: IdempotencyStore
    ):
        self.blockchain = blockchain
        self.lock_manager = lock_manager
        self.idempotency_store = idempotency_store
        
        # Store settlements: settlement_id -> Settlement
        self.settlements: Dict[str, Settlement] = {}
        self.settlements_lock = threading.Lock()
        
        # Counter for generating settlement IDs
        self.settlement_counter = 0
        self.counter_lock = threading.Lock()
    
    def initiate_settlement(
        self,
        source_chain: str,
        dest_chain: str,
        amount: float,
        user_id: str,
        idempotency_key: str
    ) -> Settlement:
        """
        Initiate a cross-chain settlement.
        
        Args:
            source_chain: Source blockchain
            dest_chain: Destination blockchain
            amount: Amount of USDC to transfer
            user_id: User initiating transfer
            idempotency_key: Unique key for idempotency
            
        Returns:
            Settlement object
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Check idempotency - has this been processed?
        existing_settlement_id = self.idempotency_store.get(idempotency_key)
        if existing_settlement_id:
            return self.settlements[existing_settlement_id]
        
        # Generate settlement ID
        with self.counter_lock:
            self.settlement_counter += 1
            settlement_id = f"settlement_{self.settlement_counter:08d}"
        
        # Create settlement
        settlement = Settlement(
            settlement_id=settlement_id,
            source_chain=source_chain,
            dest_chain=dest_chain,
            amount=amount,
            user_id=user_id,
            status=SettlementStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Store settlement
        with self.settlements_lock:
            self.settlements[settlement_id] = settlement
        
        # Record idempotency
        self.idempotency_store.put(idempotency_key, settlement_id)
        
        return settlement
    
    def process_settlement(self, settlement_id: str) -> bool:
        """
        Process a settlement (to be called by worker).
        
        BUG: Race condition in status updates allows double processing!
        
        Returns:
            True if processing started, False if already being processed
        """
        settlement = self.settlements.get(settlement_id)
        if not settlement:
            raise ValueError(f"Settlement {settlement_id} not found")
        
        # Try to acquire distributed lock
        lock_acquired = self.lock_manager.acquire(
            lock_key=f"settlement_{settlement_id}",
            holder_id=threading.current_thread().name,
            ttl_seconds=30
        )
        
        if not lock_acquired:
            return False  # Another worker is processing
        
        try:
            # BUG ALERT: This check is not atomic!
            # Race condition: Multiple threads can pass this check
            if settlement.status != SettlementStatus.PENDING:
                return False
            
            # Update to PROCESSING
            # BUG: Another thread can have passed the check above!
            self._update_settlement_status(settlement_id, SettlementStatus.PROCESSING)
            
            # Execute the settlement
            self._execute_settlement(settlement_id)
            
            return True
            
        finally:
            # Release lock
            self.lock_manager.release(
                lock_key=f"settlement_{settlement_id}",
                holder_id=threading.current_thread().name
            )
    
    def _execute_settlement(self, settlement_id: str):
        """
        Execute the settlement stages: burn then mint.
        
        TODO: Add exactly-once retry logic!
        TODO: Add saga compensation on failure!
        """
        settlement = self.settlements[settlement_id]
        
        try:
            # Stage 1: Burn tokens on source chain
            self._update_settlement_status(settlement_id, SettlementStatus.BURNING)
            
            burn_tx = self.blockchain.burn_tokens(
                settlement.source_chain,
                settlement.user_id,
                settlement.amount
            )
            settlement.burn_tx_hash = burn_tx
            
            self._update_settlement_status(settlement_id, SettlementStatus.BURNED)
            
            # Stage 2: Mint tokens on destination chain
            self._update_settlement_status(settlement_id, SettlementStatus.MINTING)
            
            mint_tx = self.blockchain.mint_tokens(
                settlement.dest_chain,
                settlement.user_id,
                settlement.amount
            )
            settlement.mint_tx_hash = mint_tx
            
            self._update_settlement_status(settlement_id, SettlementStatus.MINTED)
            
            # Complete
            self._update_settlement_status(settlement_id, SettlementStatus.COMPLETED)
            
        except Exception as e:
            # TODO: Implement saga compensation!
            # If burn succeeded but mint failed, need to mint back on source
            settlement.error_message = str(e)
            self._update_settlement_status(settlement_id, SettlementStatus.FAILED)
            raise
    
    def retry_settlement(self, settlement_id: str) -> bool:
        """
        Retry a failed settlement.
        
        TODO: Implement exactly-once retry semantics!
        
        Challenge: Settlement may have partially completed.
        - If burn succeeded, don't burn again
        - Resume from the failed stage
        
        Requirements:
        - Idempotent: Safe to call multiple times
        - Resumable: Continue from where it failed
        - Thread-safe: Multiple retries don't conflict
        
        Returns:
            True if retry started, False otherwise
        """
        settlement = self.settlements.get(settlement_id)
        if not settlement:
            return False
        
        # TODO: Check current status and resume from appropriate stage
        # Hint: Use the status to determine what's already done
        
        # TODO: Acquire lock to prevent concurrent retries
        
        # TODO: Implement resumable execution
        
        raise NotImplementedError("Retry logic not implemented")
    
    def _compensate_settlement(self, settlement_id: str):
        """
        Compensate a failed settlement (saga pattern).
        
        TODO: Implement compensation logic!
        
        If burn succeeded but mint failed:
        1. Mint the tokens back on the source chain (undo burn)
        2. Mark settlement as COMPENSATED or FAILED
        
        This ensures user doesn't lose funds.
        """
        settlement = self.settlements[settlement_id]
        
        # TODO: Check if burn succeeded
        # TODO: If yes, mint back on source chain
        # TODO: Update status appropriately
        
        raise NotImplementedError("Compensation not implemented")
    
    def _update_settlement_status(
        self,
        settlement_id: str,
        new_status: SettlementStatus
    ):
        """
        Update settlement status.
        
        BUG ALERT: This is not thread-safe!
        Multiple threads can call this simultaneously, causing race conditions.
        """
        settlement = self.settlements.get(settlement_id)
        if not settlement:
            return
        
        # BUG: No lock protecting this update!
        # Multiple threads can execute this simultaneously
        settlement.status = new_status
        settlement.updated_at = datetime.now()
    
    def get_settlement(self, settlement_id: str) -> Optional[Settlement]:
        """Get settlement by ID"""
        return self.settlements.get(settlement_id)
    
    def get_all_settlements(self) -> List[Settlement]:
        """Get all settlements"""
        with self.settlements_lock:
            return list(self.settlements.values())


class WorkerPool:
    """
    Pool of workers processing settlements concurrently.
    
    In production, this would be multiple service instances.
    """
    
    def __init__(self, engine: SettlementEngine, num_workers: int = 5):
        self.engine = engine
        self.num_workers = num_workers
        self.workers: List[threading.Thread] = []
        self.running = False
    
    def start(self):
        """Start worker threads"""
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{i}",
                daemon=True
            )
            self.workers.append(worker)
            worker.start()
    
    def stop(self):
        """Stop worker threads"""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=1)
    
    def _worker_loop(self):
        """Worker loop - continuously process pending settlements"""
        while self.running:
            # Find pending settlements
            pending = [
                s for s in self.engine.get_all_settlements()
                if s.status == SettlementStatus.PENDING
            ]
            
            for settlement in pending:
                try:
                    self.engine.process_settlement(settlement.settlement_id)
                except Exception as e:
                    print(f"Worker {threading.current_thread().name} error: {e}")
            
            time.sleep(0.01)  # Small delay

