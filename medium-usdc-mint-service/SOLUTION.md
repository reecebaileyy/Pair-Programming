# Solution: USDC Mint Service

## Bug Analysis and Fixes

### Bug 1: Deadlock in `_transfer_between_accounts()`

**Location**: `mint_service.py`, `_transfer_between_accounts()` method

**The Problem**:
```python
# BUG: Lock order depends on parameter order!
from_lock = self.storage.get_account_lock(from_account)
to_lock = self.storage.get_account_lock(to_account)

with from_lock:
    with to_lock:
        # transfer logic
```

**Why It Deadlocks**:
Classic circular wait condition:

```
Thread A: transfer("account1", "account2", 100)
  - Acquires lock for "account1"
  - Tries to acquire lock for "account2"

Thread B: transfer("account2", "account1", 50)
  - Acquires lock for "account2"  
  - Tries to acquire lock for "account1"

Result: Both threads wait forever (deadlock)
```

**The Fix - Lock Ordering**:

Always acquire locks in a consistent order, regardless of parameter order:

```python
def _transfer_between_accounts(
    self,
    from_account: str,
    to_account: str,
    amount: float
) -> bool:
    """Transfer with deadlock prevention via lock ordering"""
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")
    
    # FIX: Always lock in alphabetical order
    # This ensures consistent lock acquisition order
    accounts = sorted([from_account, to_account])
    lock1 = self.storage.get_account_lock(accounts[0])
    lock2 = self.storage.get_account_lock(accounts[1])
    
    with lock1:
        with lock2:
            # Check sufficient balance
            from_balance = self.storage.get_balance(from_account)
            if from_balance < amount:
                return False
            
            # Perform transfer
            self.storage.add_to_balance(from_account, -amount)
            self.storage.add_to_balance(to_account, amount)
            return True
```

**Key Insight**: Deadlock prevention via **consistent lock ordering**. No matter what order the parameters are passed, we always acquire locks in alphabetical order.

### Bug 2: Idempotency Token Expiry Not Handled

**Location**: `storage.py`, `get_idempotency_token()` method

**The Problem**:
```python
def get_idempotency_token(self, token: str) -> Optional[IdempotencyToken]:
    with self.counter_lock:
        if token not in self.idempotency_tokens:
            return None
        
        token_obj = self.idempotency_tokens[token]
        
        # BUG: Detects expiry but doesn't remove the token!
        if time.time() > token_obj.expires_at:
            return None  # Says "not found" but token still in dict!
        
        return token_obj
```

**Why It Fails**:
When a token expires, we return `None` (indicating it's not found), but we don't actually remove it from the dictionary. On the second attempt:
1. Token is still in the dict
2. Still expired
3. Returns `None` again
4. Mint service thinks it's expired and tries to create new mint
5. But the storage of the new token might conflict with the old one

The second mint might fail or cause inconsistency.

**The Fix**:
```python
def get_idempotency_token(self, token: str) -> Optional[IdempotencyToken]:
    """Get idempotency token if valid, remove if expired"""
    with self.counter_lock:
        if token not in self.idempotency_tokens:
            return None
        
        token_obj = self.idempotency_tokens[token]
        
        # FIX: Remove expired token from dictionary
        if time.time() > token_obj.expires_at:
            del self.idempotency_tokens[token]
            return None
        
        return token_obj
```

**Key Insight**: When detecting expired state, clean it up immediately to prevent stale data issues.

### Feature 1: Rate Limiter Implementation

**Location**: `mint_service.py`, `_check_rate_limit()` method

**Requirements**:
- Max 10 mints per account per second
- Sliding window approach
- Thread-safe

**Implementation**:

```python
def __init__(self, storage: Storage):
    self.storage = storage
    
    # Rate limiting: account_id -> list of mint timestamps
    self.mint_timestamps: Dict[str, List[float]] = {}
    self.rate_limit_lock = threading.Lock()

def _check_rate_limit(self, account_id: str) -> bool:
    """
    Check if account has exceeded rate limit.
    Returns True if rate limit exceeded, False otherwise.
    """
    with self.rate_limit_lock:
        now = time.time()
        
        # Initialize if first mint for this account
        if account_id not in self.mint_timestamps:
            self.mint_timestamps[account_id] = []
        
        # Clean up timestamps older than 1 second (sliding window)
        self.mint_timestamps[account_id] = [
            ts for ts in self.mint_timestamps[account_id]
            if now - ts < 1.0
        ]
        
        # Check if at limit
        if len(self.mint_timestamps[account_id]) >= self.MAX_MINTS_PER_SECOND:
            return True  # Rate limit exceeded
        
        # Record this mint attempt
        self.mint_timestamps[account_id].append(now)
        return False
```

**Then update `mint_usdc()` to use it**:

```python
def mint_usdc(self, account_id: str, amount: float, blockchain: str, idempotency_token: str) -> MintResult:
    # ... existing idempotency check ...
    
    # Check rate limit
    if self._check_rate_limit(account_id):
        return MintResult(
            success=False,
            mint_id="",
            amount=amount,
            message="Rate limit exceeded. Max 10 mints per second.",
            timestamp=datetime.now()
        )
    
    # ... rest of minting logic ...
```

**Key Insight**: Sliding window rate limiting tracks timestamps of recent operations, not just counts.

### Feature 2: Failed Mint Reconciliation

**Location**: `mint_service.py`, `reconcile_failed_mint()` method

**Implementation**:

```python
def reconcile_failed_mint(self, mint_id: str) -> bool:
    """
    Reconcile a failed mint operation by rolling back changes.
    
    Returns True if reconciliation successful, False otherwise.
    """
    # Look up the mint record
    mint_record = self.storage.get_mint(mint_id)
    if not mint_record:
        return False  # Mint doesn't exist
    
    account_id = mint_record.account_id
    amount = mint_record.amount
    
    # Acquire account lock
    account_lock = self.storage.get_account_lock(account_id)
    
    with account_lock:
        # Reverse the mint (subtract the amount back)
        current_balance = self.storage.get_balance(account_id)
        
        # Ensure balance is sufficient to reverse
        if current_balance < amount:
            return False  # Can't reconcile, insufficient balance
        
        # Roll back the mint
        self.storage.add_to_balance(account_id, -amount)
        
        # Clean up idempotency token if it exists
        # (This allows the mint to be retried with same token)
        with self.rate_limit_lock:  # Reusing lock for simplicity
            token = mint_record.idempotency_token
            if token in self.storage.idempotency_tokens:
                del self.storage.idempotency_tokens[token]
        
        return True
```

**Key Insight**: Reconciliation = rollback. Undo state changes and clean up tracking data.

## Complete Fixed Code

### Fixed `storage.py`

```python
def get_idempotency_token(self, token: str) -> Optional[IdempotencyToken]:
    """Get idempotency token if valid, remove if expired"""
    with self.counter_lock:
        if token not in self.idempotency_tokens:
            return None
        
        token_obj = self.idempotency_tokens[token]
        
        # FIX: Remove expired tokens
        if time.time() > token_obj.expires_at:
            del self.idempotency_tokens[token]
            return None
        
        return token_obj
```

### Fixed `mint_service.py`

```python
import time
import threading
from typing import Optional, Dict, List
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
    """Service for minting USDC tokens - FIXED VERSION"""
    
    IDEMPOTENCY_TOKEN_TTL = 5.0
    MAX_MINTS_PER_SECOND = 10
    
    def __init__(self, storage: Storage):
        self.storage = storage
        
        # Rate limiting structures
        self.mint_timestamps: Dict[str, List[float]] = {}
        self.rate_limit_lock = threading.Lock()
    
    def mint_usdc(
        self,
        account_id: str,
        amount: float,
        blockchain: str,
        idempotency_token: str
    ) -> MintResult:
        """Mint USDC tokens with all safeguards"""
        if amount <= 0:
            raise ValueError("Mint amount must be positive")
        
        # Check idempotency
        existing_token = self.storage.get_idempotency_token(idempotency_token)
        if existing_token:
            existing_mint = self.storage.get_mint(existing_token.mint_id)
            if existing_mint:
                return MintResult(
                    success=True,
                    mint_id=existing_mint.mint_id,
                    amount=existing_mint.amount,
                    message="Mint already processed (idempotent)",
                    timestamp=existing_mint.timestamp
                )
        
        # Check rate limit
        if self._check_rate_limit(account_id):
            return MintResult(
                success=False,
                mint_id="",
                amount=amount,
                message="Rate limit exceeded. Max 10 mints per second.",
                timestamp=datetime.now()
            )
        
        # Acquire account lock
        account_lock = self.storage.get_account_lock(account_id)
        
        with account_lock:
            mint_id = self.storage.generate_mint_id()
            
            record = MintRecord(
                mint_id=mint_id,
                account_id=account_id,
                amount=amount,
                blockchain=blockchain,
                timestamp=datetime.now(),
                idempotency_token=idempotency_token
            )
            
            self.storage.record_mint(record)
            self.storage.add_to_balance(account_id, amount)
            self.storage.store_idempotency_token(
                idempotency_token,
                mint_id,
                self.IDEMPOTENCY_TOKEN_TTL
            )
            
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
        """Transfer with deadlock prevention"""
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        # FIX: Always lock in sorted order
        accounts = sorted([from_account, to_account])
        lock1 = self.storage.get_account_lock(accounts[0])
        lock2 = self.storage.get_account_lock(accounts[1])
        
        with lock1:
            with lock2:
                from_balance = self.storage.get_balance(from_account)
                if from_balance < amount:
                    return False
                
                self.storage.add_to_balance(from_account, -amount)
                self.storage.add_to_balance(to_account, amount)
                return True
    
    def _check_rate_limit(self, account_id: str) -> bool:
        """Check rate limit with sliding window"""
        with self.rate_limit_lock:
            now = time.time()
            
            if account_id not in self.mint_timestamps:
                self.mint_timestamps[account_id] = []
            
            # Sliding window: keep only last 1 second
            self.mint_timestamps[account_id] = [
                ts for ts in self.mint_timestamps[account_id]
                if now - ts < 1.0
            ]
            
            if len(self.mint_timestamps[account_id]) >= self.MAX_MINTS_PER_SECOND:
                return True
            
            self.mint_timestamps[account_id].append(now)
            return False
    
    def reconcile_failed_mint(self, mint_id: str) -> bool:
        """Reconcile a failed mint by rolling back"""
        mint_record = self.storage.get_mint(mint_id)
        if not mint_record:
            return False
        
        account_id = mint_record.account_id
        amount = mint_record.amount
        
        account_lock = self.storage.get_account_lock(account_id)
        
        with account_lock:
            current_balance = self.storage.get_balance(account_id)
            
            if current_balance < amount:
                return False
            
            # Roll back
            self.storage.add_to_balance(account_id, -amount)
            
            # Clean up idempotency token
            token = mint_record.idempotency_token
            self.storage.cleanup_expired_tokens()
            
            return True
    
    def get_account_balance(self, account_id: str) -> float:
        """Get current balance"""
        account_lock = self.storage.get_account_lock(account_id)
        with account_lock:
            return self.storage.get_balance(account_id)
    
    def get_mint_details(self, mint_id: str) -> Optional[MintRecord]:
        """Get mint details"""
        return self.storage.get_mint(mint_id)
```

## Key Concepts

### 1. Deadlock Prevention

**Four conditions for deadlock** (Coffman conditions):
1. Mutual exclusion (locks)
2. Hold and wait (holding lock while requesting another)
3. No preemption (can't force unlock)
4. Circular wait (cycle in resource graph)

**Solution**: Break circular wait with **lock ordering**.

**Lock Ordering Strategy**:
- Define a total order on locks (e.g., alphabetical by account ID)
- Always acquire locks in that order
- No cycle possible → no deadlock

### 2. Time-Based Idempotency

Idempotency tokens need expiration because:
- **Memory**: Can't store tokens forever
- **Flexibility**: Allow retry after timeout
- **Correctness**: Old operations shouldn't block new ones

**Pattern**:
```
Check token:
  - Not found → Process
  - Found and valid → Return cached result
  - Found but expired → Delete and process
```

### 3. Rate Limiting Strategies

**Fixed Window**:
- Count operations per fixed time bucket (00:00-00:01, 00:01-00:02, etc.)
- Simple but has burst problem at boundaries

**Sliding Window** (our solution):
- Track timestamps of recent operations
- Count operations in last N seconds from current time
- More accurate, prevents boundary bursts

**Token Bucket** (industry standard):
- Bucket refills at rate R
- Each operation consumes token
- Most sophisticated, smooth traffic shaping

### 4. Reconciliation Pattern

In distributed systems, partial failures happen:
1. Database write succeeds
2. Network fails
3. Response lost
4. Client retries
5. → Duplicate operation risk

**Reconciliation** cleans up:
- Identify partially completed operations
- Roll back changes
- Allow safe retry

## Production Considerations

### At Circle Scale

1. **Distributed Locks**: Use Redis or etcd, not in-memory locks
2. **Database Transactions**: PostgreSQL with SERIALIZABLE isolation
3. **Blockchain Integration**: Actual on-chain minting with gas management
4. **HSM Signing**: Hardware security modules for transaction signing
5. **Audit Trail**: Immutable log of all operations for compliance
6. **Multi-signature**: Multiple approvers for large mints
7. **Reserve Management**: Real-time reserve balance verification
8. **Monitoring**: Latency, throughput, error rates, deadlock detection

### Testing Strategy

```bash
# Run tests repeatedly to catch race conditions
for i in {1..100}; do 
    pytest test_mint_service.py::test_concurrent_mints_no_deadlock -v
done

# Use deadlock detection
pytest test_mint_service.py -v --timeout=5

# Run with thread sanitizer (C/C++ equivalent)
# Python: use -W to detect threading issues
python -W all -m pytest test_mint_service.py
```

### Monitoring

Key metrics for mint service:
- **Mint latency**: p50, p95, p99
- **Mint throughput**: mints/second
- **Error rate**: failed mints %
- **Idempotency hit rate**: cached responses %
- **Rate limit hits**: blocked requests %
- **Lock contention**: time waiting for locks
- **Deadlock incidents**: count (should be 0!)

## Alternative Approaches

### 1. Single-Threaded Event Loop
```python
async def mint_usdc(...):
    # No locks needed, single thread
```
**Pros**: No race conditions, no deadlocks
**Cons**: Doesn't use multiple cores

### 2. Actor Model (Akka-style)
```python
class MintActor:
    # Each account has dedicated actor
    # All operations serialized per actor
```
**Pros**: Natural isolation, scales horizontally
**Cons**: More complex architecture

### 3. Optimistic Concurrency
```python
def mint_usdc(...):
    while True:
        version = read_version()
        # do work
        if compare_and_swap(version):
            break
        # retry
```
**Pros**: No locks, high throughput
**Cons**: Retry overhead under contention

## Common Pitfalls

1. ❌ **Inconsistent lock ordering**: One path locks A→B, another B→A
2. ❌ **Forgetting to clean up expired state**: Memory leaks
3. ❌ **Rate limiting on wrong granularity**: Per-service vs per-account
4. ❌ **Not handling lock acquisition timeouts**: Can still hang
5. ❌ **Ignoring atomicity in reconciliation**: Partial rollback is bad

## Discussion Topics

1. **Lock-free programming**: Can we avoid locks entirely?
2. **Distributed consensus**: How does this work across datacenters?
3. **Byzantine fault tolerance**: What if a node is malicious?
4. **Blockchain finality**: When is a mint really final?
5. **Regulatory compliance**: How to prove correct operation?
6. **Disaster recovery**: What if database corrupted?

## Further Reading

- **Database Internals** by Alex Petrov
- **Designing Data-Intensive Applications** by Martin Kleppmann  
- **The Art of Multiprocessor Programming** by Herlihy & Shavit
- Circle's Engineering Blog: https://www.circle.com/blog/engineering

Great work completing this challenge! You've tackled real-world distributed systems problems that Circle engineers face daily.

