"""
Test suite for USDC Mint Service

Run with: pytest test_mint_service.py -v
For deadlock detection: pytest test_mint_service.py -v --timeout=10
"""

import pytest
import threading
import time
from mint_service import MintService
from storage import Storage


class TestBasicMinting:
    """Tests for basic mint functionality (most should pass)"""
    
    def test_create_account_and_mint(self):
        """Test basic account creation and minting"""
        storage = Storage()
        service = MintService(storage)
        
        storage.create_account("institution1", 0.0)
        
        result = service.mint_usdc(
            "institution1",
            1000.0,
            "ethereum",
            "token1"
        )
        
        assert result.success is True
        assert result.amount == 1000.0
        assert service.get_account_balance("institution1") == 1000.0
    
    def test_multiple_sequential_mints(self):
        """Test multiple mints to same account"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        service.mint_usdc("institution1", 500.0, "solana", "token2")
        service.mint_usdc("institution1", 250.0, "polygon", "token3")
        
        assert service.get_account_balance("institution1") == 1750.0
    
    def test_mint_details_retrieval(self):
        """Test retrieving mint details"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        result = service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        
        details = service.get_mint_details(result.mint_id)
        assert details is not None
        assert details.amount == 1000.0
        assert details.blockchain == "ethereum"
        assert details.account_id == "institution1"


class TestIdempotency:
    """Tests for idempotency behavior"""
    
    def test_duplicate_token_same_result(self):
        """Test that duplicate idempotency token returns same result"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        result1 = service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        result2 = service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        
        assert result1.mint_id == result2.mint_id
        assert service.get_account_balance("institution1") == 1000.0  # Only minted once
    
    def test_idempotency_prevents_double_mint(self):
        """Test idempotency prevents double minting"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        # Mint three times with same token
        service.mint_usdc("institution1", 500.0, "ethereum", "token1")
        service.mint_usdc("institution1", 500.0, "ethereum", "token1")
        service.mint_usdc("institution1", 500.0, "ethereum", "token1")
        
        assert service.get_account_balance("institution1") == 500.0
    
    def test_idempotency_token_expiry(self):
        """
        Test that expired idempotency tokens allow reminting.
        
        BUG: This test will FAIL due to the expiry bug in storage.py
        """
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        # First mint
        result1 = service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        assert service.get_account_balance("institution1") == 1000.0
        
        # Wait for token to expire (TTL is 5 seconds)
        time.sleep(6)
        
        # Second mint with same token should work (new mint)
        result2 = service.mint_usdc("institution1", 500.0, "ethereum", "token1")
        
        # Should be different mints
        assert result1.mint_id != result2.mint_id
        # Balance should include both
        assert service.get_account_balance("institution1") == 1500.0


class TestConcurrency:
    """Tests for concurrent minting (deadlock test will hang)"""
    
    def test_concurrent_mints_same_account(self):
        """Test multiple threads minting to same account"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        def mint_worker(amount, token):
            service.mint_usdc("institution1", amount, "ethereum", token)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=mint_worker, args=(100.0, f"token{i}"))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have minted 10 * 100 = 1000
        assert service.get_account_balance("institution1") == 1000.0
    
    def test_concurrent_mints_different_accounts(self):
        """Test concurrent mints to different accounts"""
        storage = Storage()
        service = MintService(storage)
        
        for i in range(5):
            storage.create_account(f"institution{i}", 0.0)
        
        def mint_worker(account, amount, token):
            service.mint_usdc(account, amount, "ethereum", token)
        
        threads = []
        for i in range(5):
            for j in range(10):
                t = threading.Thread(
                    target=mint_worker,
                    args=(f"institution{i}", 100.0, f"inst{i}_token{j}")
                )
                threads.append(t)
                t.start()
        
        for t in threads:
            t.join()
        
        # Each account should have 1000
        for i in range(5):
            assert service.get_account_balance(f"institution{i}") == 1000.0
    
    def test_concurrent_mints_no_deadlock(self):
        """
        Test that concurrent transfers don't deadlock.
        
        DEADLOCK BUG: This test will HANG due to circular lock dependency!
        
        Run with timeout: pytest test_mint_service.py::test_concurrent_mints_no_deadlock -v --timeout=10
        """
        storage = Storage()
        service = MintService(storage)
        
        storage.create_account("account1", 1000.0)
        storage.create_account("account2", 1000.0)
        
        results = {"success": 0, "failed": 0}
        results_lock = threading.Lock()
        
        def transfer_worker(from_acc, to_acc):
            try:
                success = service._transfer_between_accounts(from_acc, to_acc, 50.0)
                with results_lock:
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
            except Exception as e:
                print(f"Error in transfer: {e}")
        
        # Launch opposite transfers simultaneously
        # This will deadlock!
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=transfer_worker, args=("account1", "account2"))
            t2 = threading.Thread(target=transfer_worker, args=("account2", "account1"))
            threads.extend([t1, t2])
        
        for t in threads:
            t.start()
        
        # If deadlock, this will hang forever
        for t in threads:
            t.join(timeout=5)
        
        # Should complete without hanging
        assert results["success"] + results["failed"] > 0


class TestRateLimiting:
    """Tests for rate limiting (will fail - not implemented)"""
    
    def test_rate_limiter(self):
        """
        Test that rate limiter prevents excessive mints.
        
        TODO: This will fail until rate limiting is implemented
        """
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        # Try to mint more than MAX_MINTS_PER_SECOND
        successful = 0
        rate_limited = 0
        
        for i in range(20):
            try:
                result = service.mint_usdc(
                    "institution1",
                    100.0,
                    "ethereum",
                    f"token{i}"
                )
                if result.success:
                    successful += 1
                else:
                    rate_limited += 1
            except NotImplementedError:
                pytest.skip("Rate limiting not implemented yet")
        
        # Should have hit rate limit
        assert successful == service.MAX_MINTS_PER_SECOND
        assert rate_limited == 10
    
    def test_rate_limiter_resets(self):
        """Test that rate limiter resets after time window"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        try:
            # Mint up to limit
            for i in range(service.MAX_MINTS_PER_SECOND):
                service.mint_usdc("institution1", 100.0, "ethereum", f"token{i}")
            
            # Should be rate limited now
            result = service.mint_usdc("institution1", 100.0, "ethereum", "token_extra")
            assert result.success is False
            
            # Wait for window to pass
            time.sleep(1.1)
            
            # Should work again
            result = service.mint_usdc("institution1", 100.0, "ethereum", "token_after_wait")
            assert result.success is True
            
        except NotImplementedError:
            pytest.skip("Rate limiting not implemented yet")


class TestReconciliation:
    """Tests for failed mint reconciliation (will fail - not implemented)"""
    
    def test_reconcile_failed_mint(self):
        """
        Test reconciliation of a failed mint.
        
        TODO: This will fail until reconciliation is implemented
        """
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        # Mint some USDC
        result = service.mint_usdc("institution1", 1000.0, "ethereum", "token1")
        mint_id = result.mint_id
        
        assert service.get_account_balance("institution1") == 1000.0
        
        try:
            # Reconcile (roll back) the mint
            success = service.reconcile_failed_mint(mint_id)
            assert success is True
            
            # Balance should be back to 0
            assert service.get_account_balance("institution1") == 0.0
            
        except NotImplementedError:
            pytest.skip("Reconciliation not implemented yet")
    
    def test_reconcile_nonexistent_mint(self):
        """Test reconciliation of non-existent mint"""
        storage = Storage()
        service = MintService(storage)
        
        try:
            success = service.reconcile_failed_mint("fake_mint_id")
            assert success is False
        except NotImplementedError:
            pytest.skip("Reconciliation not implemented yet")


class TestEdgeCases:
    """Edge case tests"""
    
    def test_zero_amount_mint_fails(self):
        """Test that zero amount mint is rejected"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        with pytest.raises(ValueError, match="must be positive"):
            service.mint_usdc("institution1", 0.0, "ethereum", "token1")
    
    def test_negative_amount_mint_fails(self):
        """Test that negative amount mint is rejected"""
        storage = Storage()
        service = MintService(storage)
        storage.create_account("institution1", 0.0)
        
        with pytest.raises(ValueError, match="must be positive"):
            service.mint_usdc("institution1", -100.0, "ethereum", "token1")
    
    def test_mint_to_nonexistent_account_fails(self):
        """Test minting to non-existent account"""
        storage = Storage()
        service = MintService(storage)
        
        with pytest.raises(ValueError, match="does not exist"):
            service.mint_usdc("fake_account", 100.0, "ethereum", "token1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

