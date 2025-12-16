"""
Test suite for Cross-Chain Settlement Engine

Run with: pytest test_settlement_engine.py -v
"""

import pytest
import threading
import time
import tempfile
import os
from settlement_engine import (
    SettlementEngine,
    BlockchainSimulator,
    SettlementStatus,
    WorkerPool
)
from distributed_lock import DistributedLockManager
from idempotency_store import IdempotencyStore


class TestBasicSettlement:
    """Tests for basic settlement functionality"""
    
    def test_initiate_settlement(self):
        """Test creating a settlement"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        assert settlement.amount == 100.0
        assert settlement.status == SettlementStatus.PENDING
        assert settlement.source_chain == "ethereum"
        assert settlement.dest_chain == "solana"
    
    def test_simple_settlement_processing(self):
        """Test processing a simple settlement"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        engine.process_settlement(settlement.settlement_id)
        
        # Check final status
        updated = engine.get_settlement(settlement.settlement_id)
        assert updated.status == SettlementStatus.COMPLETED
        
        # Check balances
        assert blockchain.get_balance("ethereum", "user1") == 900.0
        assert blockchain.get_balance("solana", "user1") == 100.0
    
    def test_idempotency_prevents_duplicate(self):
        """Test that same idempotency key returns same settlement"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        
        settlement1 = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        settlement2 = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"  # Same key
        )
        
        assert settlement1.settlement_id == settlement2.settlement_id


class TestConcurrency:
    """Tests for concurrent processing"""
    
    def test_concurrent_worker_processing(self):
        """
        Test that concurrent workers don't double-process.
        
        BUG: This test will FAIL due to race condition in status update!
        """
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 10000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        # Create 10 settlements
        settlements = []
        for i in range(10):
            s = engine.initiate_settlement(
                "ethereum",
                "solana",
                100.0,
                "user1",
                f"key{i}"
            )
            settlements.append(s)
        
        # Process concurrently with multiple workers
        results = []
        
        def worker():
            for settlement in settlements:
                try:
                    success = engine.process_settlement(settlement.settlement_id)
                    if success:
                        results.append(settlement.settlement_id)
                except Exception as e:
                    print(f"Worker error: {e}")
        
        threads = []
        for i in range(5):  # 5 concurrent workers
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Each settlement should be processed exactly once
        # Check balances
        eth_balance = blockchain.get_balance("ethereum", "user1")
        sol_balance = blockchain.get_balance("solana", "user1")
        
        assert eth_balance == 9000.0, f"Expected 9000, got {eth_balance} (double burn?)"
        assert sol_balance == 1000.0, f"Expected 1000, got {sol_balance} (double mint?)"
    
    def test_concurrent_different_settlements(self):
        """Test that different settlements can process concurrently"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        # Set up multiple users
        for i in range(5):
            blockchain.set_balance("ethereum", f"user{i}", 1000.0)
            blockchain.set_balance("solana", f"user{i}", 0.0)
        
        # Create settlements for each user
        settlements = []
        for i in range(5):
            s = engine.initiate_settlement(
                "ethereum",
                "solana",
                100.0,
                f"user{i}",
                f"key{i}"
            )
            settlements.append(s)
        
        # Process all concurrently
        def worker(settlement):
            engine.process_settlement(settlement.settlement_id)
        
        threads = []
        for s in settlements:
            t = threading.Thread(target=worker, args=(s,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should complete
        for i in range(5):
            assert blockchain.get_balance("ethereum", f"user{i}") == 900.0
            assert blockchain.get_balance("solana", f"user{i}") == 100.0


class TestIdempotencyPersistence:
    """Tests for idempotency persistence across restarts"""
    
    def test_idempotency_survives_restart(self):
        """
        Test that idempotency survives service restart.
        
        BUG: This test will FAIL because idempotency is in-memory only!
        """
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        
        # Use temp file for persistence
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            persistence_file = f.name
        
        try:
            # First instance
            idempotency_store1 = IdempotencyStore(persistence_file)
            engine1 = SettlementEngine(blockchain, lock_manager, idempotency_store1)
            
            blockchain.set_balance("ethereum", "user1", 1000.0)
            blockchain.set_balance("solana", "user1", 0.0)
            
            settlement1 = engine1.initiate_settlement(
                "ethereum",
                "solana",
                100.0,
                "user1",
                "persistent_key"
            )
            
            engine1.process_settlement(settlement1.settlement_id)
            
            # Simulate restart: create new engine instance
            idempotency_store2 = IdempotencyStore(persistence_file)
            engine2 = SettlementEngine(blockchain, lock_manager, idempotency_store2)
            
            # Copy settlements (in production, these would be in DB)
            engine2.settlements = engine1.settlements
            
            # Try to initiate with same key
            settlement2 = engine2.initiate_settlement(
                "ethereum",
                "solana",
                100.0,
                "user1",
                "persistent_key"  # Same key
            )
            
            # Should return the original settlement
            assert settlement2.settlement_id == settlement1.settlement_id
            
            # Balance should only reflect one settlement
            assert blockchain.get_balance("ethereum", "user1") == 900.0
            assert blockchain.get_balance("solana", "user1") == 100.0
            
        finally:
            if os.path.exists(persistence_file):
                os.remove(persistence_file)


class TestDistributedLock:
    """Tests for distributed locking"""
    
    def test_distributed_lock_basic(self):
        """Test basic lock acquire and release"""
        lock_manager = DistributedLockManager()
        
        # Acquire lock
        acquired1 = lock_manager.acquire("lock1", "worker1", 5.0)
        assert acquired1 is True
        
        # Try to acquire same lock with different holder
        acquired2 = lock_manager.acquire("lock1", "worker2", 5.0)
        assert acquired2 is False  # Should fail
        
        # Release lock
        released = lock_manager.release("lock1", "worker1")
        assert released is True
        
        # Now worker2 can acquire
        acquired3 = lock_manager.acquire("lock1", "worker2", 5.0)
        assert acquired3 is True
    
    def test_distributed_lock_ttl_expiry(self):
        """Test that locks expire after TTL"""
        lock_manager = DistributedLockManager()
        
        # Acquire with short TTL
        lock_manager.acquire("lock1", "worker1", 0.1)
        
        # Immediately can't acquire
        assert lock_manager.acquire("lock1", "worker2", 5.0) is False
        
        # Wait for expiry
        time.sleep(0.2)
        
        # Now can acquire (lock expired)
        assert lock_manager.acquire("lock1", "worker2", 5.0) is True
    
    def test_distributed_lock_prevents_double_processing(self):
        """
        Test that distributed lock prevents double processing.
        
        TODO: Will fail until distributed lock is properly implemented!
        """
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        # Try to process with multiple workers simultaneously
        process_count = [0]
        lock = threading.Lock()
        
        def worker():
            if engine.process_settlement(settlement.settlement_id):
                with lock:
                    process_count[0] += 1
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Only one worker should have actually processed it
        assert process_count[0] == 1, f"Expected 1 processing, got {process_count[0]}"
        
        # Check balances (should only happen once)
        assert blockchain.get_balance("ethereum", "user1") == 900.0
        assert blockchain.get_balance("solana", "user1") == 100.0


class TestRetryLogic:
    """Tests for retry and failure handling"""
    
    def test_retry_after_partial_completion(self):
        """
        Test retry after partial completion.
        
        TODO: Will fail until retry logic is implemented!
        """
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        # Make mint fail
        blockchain.should_fail_mint = True
        
        try:
            engine.process_settlement(settlement.settlement_id)
        except Exception:
            pass  # Expected to fail
        
        # Should have burned but not minted
        assert blockchain.get_balance("ethereum", "user1") == 900.0
        assert blockchain.get_balance("solana", "user1") == 0.0
        
        # Settlement should be in FAILED state
        updated = engine.get_settlement(settlement.settlement_id)
        assert updated.status == SettlementStatus.FAILED
        
        # Fix the blockchain
        blockchain.should_fail_mint = False
        
        # Retry should complete (not burn again!)
        success = engine.retry_settlement(settlement.settlement_id)
        assert success is True
        
        # Should now be completed
        updated = engine.get_settlement(settlement.settlement_id)
        assert updated.status == SettlementStatus.COMPLETED
        
        # Balances should be correct (burn happened once, mint completes)
        assert blockchain.get_balance("ethereum", "user1") == 900.0
        assert blockchain.get_balance("solana", "user1") == 100.0


class TestCompensation:
    """Tests for saga compensation on failures"""
    
    def test_compensation_on_destination_failure(self):
        """
        Test compensation when destination fails.
        
        TODO: Will fail until compensation is implemented!
        """
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 1000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        # Make mint fail
        blockchain.should_fail_mint = True
        
        try:
            engine.process_settlement(settlement.settlement_id)
        except Exception:
            pass
        
        # Burn happened
        assert blockchain.get_balance("ethereum", "user1") == 900.0
        
        # Trigger compensation
        engine._compensate_settlement(settlement.settlement_id)
        
        # Should have minted back on source (compensation)
        assert blockchain.get_balance("ethereum", "user1") == 1000.0
        assert blockchain.get_balance("solana", "user1") == 0.0


class TestWorkerPool:
    """Tests for worker pool"""
    
    def test_worker_pool_processes_settlements(self):
        """Test that worker pool processes pending settlements"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 10000.0)
        blockchain.set_balance("solana", "user1", 0.0)
        
        # Create multiple settlements
        for i in range(5):
            engine.initiate_settlement(
                "ethereum",
                "solana",
                100.0,
                "user1",
                f"key{i}"
            )
        
        # Start worker pool
        pool = WorkerPool(engine, num_workers=3)
        pool.start()
        
        # Wait for processing
        time.sleep(0.5)
        
        pool.stop()
        
        # All should be completed
        settlements = engine.get_all_settlements()
        completed = [s for s in settlements if s.status == SettlementStatus.COMPLETED]
        
        assert len(completed) == 5
        assert blockchain.get_balance("ethereum", "user1") == 9500.0
        assert blockchain.get_balance("solana", "user1") == 500.0


class TestEdgeCases:
    """Edge case tests"""
    
    def test_zero_amount_rejected(self):
        """Test that zero amount is rejected"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        with pytest.raises(ValueError, match="must be positive"):
            engine.initiate_settlement(
                "ethereum",
                "solana",
                0.0,
                "user1",
                "key1"
            )
    
    def test_insufficient_balance_fails(self):
        """Test that insufficient balance fails gracefully"""
        blockchain = BlockchainSimulator()
        lock_manager = DistributedLockManager()
        idempotency_store = IdempotencyStore()
        engine = SettlementEngine(blockchain, lock_manager, idempotency_store)
        
        blockchain.set_balance("ethereum", "user1", 50.0)
        
        settlement = engine.initiate_settlement(
            "ethereum",
            "solana",
            100.0,
            "user1",
            "key1"
        )
        
        with pytest.raises(ValueError, match="Insufficient balance"):
            engine.process_settlement(settlement.settlement_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


