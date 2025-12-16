"""
Test suite for PaymentProcessor

Run with: pytest test_payment_service.py -v
"""

import pytest
import threading
import time
from payment_service import PaymentProcessor, PaymentResult


class TestBasicFunctionality:
    """Tests for basic payment processing (these should mostly pass)"""
    
    def test_create_account(self):
        """Test account creation"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        assert processor.get_balance("user1") == 100.0
    
    def test_create_duplicate_account_fails(self):
        """Test that duplicate account creation fails"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        with pytest.raises(ValueError, match="already exists"):
            processor.create_account("user1", 50.0)
    
    def test_get_balance_nonexistent_user(self):
        """Test getting balance for non-existent user"""
        processor = PaymentProcessor()
        with pytest.raises(ValueError, match="does not exist"):
            processor.get_balance("nobody")
    
    def test_simple_payment(self):
        """Test a single payment"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        result = processor.process_payment("user1", 30.0, "key1")
        
        assert result.success is True
        assert result.amount == 30.0
        assert processor.get_balance("user1") == 70.0
    
    def test_insufficient_funds(self):
        """Test payment with insufficient funds"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        result = processor.process_payment("user1", 150.0, "key1")
        
        assert result.success is False
        assert processor.get_balance("user1") == 100.0  # Balance unchanged


class TestIdempotency:
    """Tests for idempotency guarantees (some will fail due to bugs)"""
    
    def test_duplicate_idempotency_key_returns_same_result(self):
        """Test that using the same idempotency key returns the cached result"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        result1 = processor.process_payment("user1", 30.0, "key1")
        result2 = processor.process_payment("user1", 30.0, "key1")
        
        assert result1.transaction_id == result2.transaction_id
        assert processor.get_balance("user1") == 70.0  # Should only deduct once
    
    def test_idempotency_prevents_double_charge(self):
        """Test that idempotency prevents double charging"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        # Process same payment twice with same key
        processor.process_payment("user1", 50.0, "key1")
        processor.process_payment("user1", 50.0, "key1")
        
        # Should only charge once
        assert processor.get_balance("user1") == 50.0
    
    def test_different_keys_process_separately(self):
        """Test that different idempotency keys process separately"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        result1 = processor.process_payment("user1", 30.0, "key1")
        result2 = processor.process_payment("user1", 30.0, "key2")
        
        assert result1.transaction_id != result2.transaction_id
        assert processor.get_balance("user1") == 40.0  # Both should process


class TestConcurrency:
    """Tests for concurrent payment processing (these will fail due to race conditions)"""
    
    def test_concurrent_payments_same_user(self):
        """Test multiple concurrent payments from the same user"""
        processor = PaymentProcessor()
        processor.create_account("user1", 1000.0)
        
        results = []
        
        def make_payment(amount, key):
            result = processor.process_payment("user1", amount, key)
            results.append(result)
        
        # Launch 10 concurrent payments of 50 each
        threads = []
        for i in range(10):
            t = threading.Thread(target=make_payment, args=(50.0, f"key{i}"))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should succeed
        assert all(r.success for r in results)
        
        # Balance should be 1000 - (10 * 50) = 500
        final_balance = processor.get_balance("user1")
        assert final_balance == 500.0, f"Expected 500.0, got {final_balance}"
    
    def test_concurrent_payments_different_users(self):
        """Test concurrent payments from different users"""
        processor = PaymentProcessor()
        processor.create_account("user1", 500.0)
        processor.create_account("user2", 500.0)
        
        def make_payments(user_id, num_payments):
            for i in range(num_payments):
                processor.process_payment(user_id, 10.0, f"{user_id}_key{i}")
        
        thread1 = threading.Thread(target=make_payments, args=("user1", 20))
        thread2 = threading.Thread(target=make_payments, args=("user2", 20))
        
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
        
        # Each user should have spent 200 (20 * 10)
        assert processor.get_balance("user1") == 300.0
        assert processor.get_balance("user2") == 300.0
    
    def test_concurrent_duplicate_idempotency_keys(self):
        """Test that concurrent requests with same idempotency key only process once"""
        processor = PaymentProcessor()
        processor.create_account("user1", 1000.0)
        
        results = []
        
        def make_payment():
            # All threads use the SAME idempotency key
            result = processor.process_payment("user1", 100.0, "duplicate_key")
            results.append(result)
        
        # Launch 5 concurrent requests with same idempotency key
        threads = []
        for i in range(5):
            t = threading.Thread(target=make_payment)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should only charge once
        final_balance = processor.get_balance("user1")
        assert final_balance == 900.0, f"Expected 900.0, got {final_balance} (charged multiple times!)"
        
        # All results should have the same transaction ID
        transaction_ids = [r.transaction_id for r in results]
        assert len(set(transaction_ids)) == 1, "Should have only one unique transaction ID"


class TestRefunds:
    """Tests for refund functionality (will fail - not implemented)"""
    
    def test_simple_refund(self):
        """Test a basic refund"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        # Make a payment
        payment_result = processor.process_payment("user1", 30.0, "payment_key")
        assert processor.get_balance("user1") == 70.0
        
        # Refund it
        refund_result = processor.refund_payment(
            "user1", 30.0, "refund_key", payment_result.transaction_id
        )
        
        assert refund_result.success is True
        assert processor.get_balance("user1") == 100.0  # Back to original
    
    def test_refund_idempotency(self):
        """Test that refunds respect idempotency"""
        processor = PaymentProcessor()
        processor.create_account("user1", 100.0)
        
        payment_result = processor.process_payment("user1", 30.0, "payment_key")
        
        # Process same refund twice with same key
        refund1 = processor.refund_payment(
            "user1", 30.0, "refund_key", payment_result.transaction_id
        )
        refund2 = processor.refund_payment(
            "user1", 30.0, "refund_key", payment_result.transaction_id
        )
        
        assert refund1.transaction_id == refund2.transaction_id
        assert processor.get_balance("user1") == 100.0  # Should only refund once
    
    def test_concurrent_refunds(self):
        """Test concurrent refunds don't cause race conditions"""
        processor = PaymentProcessor()
        processor.create_account("user1", 1000.0)
        
        # Make 10 payments
        payment_ids = []
        for i in range(10):
            result = processor.process_payment("user1", 50.0, f"pay_key{i}")
            payment_ids.append(result.transaction_id)
        
        assert processor.get_balance("user1") == 500.0
        
        # Refund all concurrently
        def refund(idx):
            processor.refund_payment("user1", 50.0, f"refund_key{idx}", payment_ids[idx])
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=refund, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should be back to 1000
        assert processor.get_balance("user1") == 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


