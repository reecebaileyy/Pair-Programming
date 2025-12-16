# Solution: Payment Transaction Processor

## Bug Analysis

### Bug 1: Race Condition in Balance Updates

**Location**: `process_payment()` method, lines with balance check and deduction

**The Problem**:
```python
# BUG: Not atomic!
current_balance = self.balances[user_id]
if current_balance < amount:
    # ...
self.balances[user_id] = current_balance - amount
```

**Why It Fails**:
This is a classic "check-then-act" race condition. Between reading the balance and updating it, another thread can interleave:

```
Thread A: reads balance = 100
Thread B: reads balance = 100
Thread A: deducts 50, writes 50
Thread B: deducts 50, writes 50
Final: 50 (should be 0!)
```

**The Fix**:
Wrap the entire balance check and update in a lock:
```python
with self.lock:
    current_balance = self.balances[user_id]
    if current_balance < amount:
        # return insufficient funds
    self.balances[user_id] = current_balance - amount
```

### Bug 2: Idempotency Check Timing

**Location**: `process_payment()` method, idempotency key check

**The Problem**:
```python
# BUG: Check happens BEFORE the lock!
if idempotency_key in self.processed_payments:
    return self.processed_payments[idempotency_key]

# ... later, balance is deducted without lock ...

# BUG: Recording happens AFTER processing!
self.processed_payments[idempotency_key] = result
```

**Why It Fails**:
Two threads with the same idempotency key can both pass the initial check before either records the result:

```
Thread A: checks key "abc", not found
Thread B: checks key "abc", not found
Thread A: processes payment, deducts balance
Thread B: processes payment, deducts balance (DUPLICATE!)
Thread A: records key "abc"
Thread B: records key "abc"
```

**The Fix**:
The idempotency check and balance operation must be atomic:
```python
with self.lock:
    # Check idempotency INSIDE the lock
    if idempotency_key in self.processed_payments:
        return self.processed_payments[idempotency_key]
    
    # Process payment
    # ...
    
    # Record BEFORE releasing the lock
    self.processed_payments[idempotency_key] = result
```

### Bug 3: Missing Refund Implementation

**Location**: `refund_payment()` method

**The Problem**:
The entire method is a TODO/NotImplementedError.

**The Fix**:
Implement with the same concurrency and idempotency patterns as `process_payment()`.

## Complete Fixed Implementation

```python
"""
Payment Transaction Processor for Circle Payment APIs - FIXED VERSION
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
    FIXED: All concurrency and idempotency bugs resolved.
    """
    
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.processed_payments: Dict[str, PaymentResult] = {}
        self.transaction_counter = 0
        
        # Single lock protects all shared state
        self.lock = threading.Lock()
    
    def create_account(self, user_id: str, initial_balance: float = 0.0) -> None:
        """Create a new user account with initial balance"""
        with self.lock:
            if user_id in self.balances:
                raise ValueError(f"Account {user_id} already exists")
            self.balances[user_id] = initial_balance
    
    def get_balance(self, user_id: str) -> float:
        """Get current balance for a user - now thread-safe"""
        with self.lock:
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
        
        FIXED: Idempotency check and balance update are now atomic.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        
        # CRITICAL: Everything happens inside the lock for atomicity
        with self.lock:
            # FIX 1: Check idempotency INSIDE the lock
            if idempotency_key in self.processed_payments:
                return self.processed_payments[idempotency_key]
            
            # Check if user exists
            if user_id not in self.balances:
                raise ValueError(f"Account {user_id} does not exist")
            
            # FIX 2: Balance check and deduction are atomic
            current_balance = self.balances[user_id]
            if current_balance < amount:
                result = PaymentResult(
                    success=False,
                    transaction_id="",
                    amount=amount,
                    message=f"Insufficient funds. Balance: {current_balance}, Required: {amount}",
                    timestamp=datetime.now()
                )
                # Don't cache failed payments
                return result
            
            # Deduct the amount
            self.balances[user_id] = current_balance - amount
            
            # Generate transaction ID
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
            
            # FIX 3: Record idempotency BEFORE releasing the lock
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
        
        FIXED: Complete implementation with same guarantees as payment processing.
        """
        if amount <= 0:
            raise ValueError("Refund amount must be positive")
        
        # Everything inside lock for atomicity
        with self.lock:
            # Check idempotency for refunds
            if idempotency_key in self.processed_payments:
                return self.processed_payments[idempotency_key]
            
            # Verify user exists
            if user_id not in self.balances:
                raise ValueError(f"Account {user_id} does not exist")
            
            # Add the amount back (refund)
            self.balances[user_id] += amount
            
            # Generate transaction ID for the refund
            self.transaction_counter += 1
            transaction_id = f"refund_{self.transaction_counter:06d}"
            
            # Create result
            result = PaymentResult(
                success=True,
                transaction_id=transaction_id,
                amount=amount,
                message=f"Refund processed for {original_transaction_id}",
                timestamp=datetime.now()
            )
            
            # Record the idempotency key
            self.processed_payments[idempotency_key] = result
            
            return result
    
    def get_transaction_count(self) -> int:
        """Get total number of transactions processed"""
        with self.lock:
            return self.transaction_counter
```

## Key Insights

### 1. Atomicity is Critical

The fundamental issue was **atomicity**. Operations that must happen together (check + act) were separated, allowing race conditions.

**Rule**: If multiple threads access shared mutable state, protect ALL access with synchronization.

### 2. Idempotency Requires Atomicity Too

Idempotency isn't just about checking a cache - the check and record must be atomic with the operation itself.

**Pattern**:
```python
with lock:
    if already_done:
        return cached_result
    do_work()
    cache_result()
```

### 3. Lock Granularity

We used a single coarse-grained lock. This is simple and correct, though it limits concurrency.

**Alternatives**:
- **Fine-grained locking**: Separate locks per user account (more complex, higher throughput)
- **Lock-free structures**: Using atomic operations (most complex, highest performance)

For an entry-level interview, the single lock is the right choice - it's correct and understandable.

### 4. Read Operations Need Locks Too

Even `get_balance()` needs protection - reading a `float` might not be atomic on all platforms, and consistency matters.

## Alternative Approaches

### Approach 1: Per-User Locks
```python
def __init__(self):
    self.user_locks: Dict[str, threading.Lock] = {}
    # Lock for user_locks dict itself
    self.user_locks_lock = threading.Lock()
```

**Pros**: Higher concurrency (different users don't block each other)
**Cons**: More complex, need to ensure lock ordering to avoid deadlocks

### Approach 2: Thread-Safe Queue
```python
def __init__(self):
    self.command_queue = queue.Queue()
    self.worker_thread = threading.Thread(target=self._process_commands)
```

**Pros**: Single-threaded processing eliminates race conditions
**Cons**: Serializes all operations, lower throughput

### Approach 3: Database-Backed
```python
def process_payment(self, ...):
    with transaction():
        # Use database transactions for atomicity
        db.execute("UPDATE balances SET amount = amount - ? WHERE user_id = ?")
```

**Pros**: Industry-standard approach, handles crashes/restarts
**Cons**: Requires external database (not in scope for this exercise)

## Production Considerations

In a real Circle system, you would need:

1. **Persistent Storage**: Database with ACID transactions
2. **Distributed Systems**: Multiple servers need distributed locks (Redis, etcd)
3. **Idempotency Expiration**: Old keys should expire to prevent unbounded memory growth
4. **Audit Logging**: Every transaction logged for compliance
5. **Metrics**: Latency, throughput, error rates
6. **Rate Limiting**: Prevent abuse
7. **Retries**: Handle transient failures with exponential backoff
8. **Dead Letter Queue**: Handle permanently failed transactions

## Common Mistakes to Avoid

1. ❌ **Checking outside the lock**: Classic TOCTOU (time-of-check-time-of-use) bug
2. ❌ **Inconsistent lock usage**: Some methods use lock, others don't
3. ❌ **Lock ordering issues**: Can cause deadlocks with multiple locks
4. ❌ **Holding locks too long**: Doing I/O or expensive computation while holding lock
5. ❌ **Not handling exceptions**: Locks can be left held if exception occurs

## Testing Strategy

The tests are designed to catch specific issues:

- **Basic tests**: Verify happy path works
- **Idempotency tests**: Verify duplicate keys are handled
- **Concurrency tests**: Use threads to trigger race conditions
- **Combined tests**: Concurrent + idempotent = hardest case

**Pro tip**: Run tests multiple times - race conditions can be non-deterministic!

```bash
# Run 100 times to catch flaky tests
for i in {1..100}; do pytest test_payment_service.py::test_concurrent_duplicate_idempotency_keys; done
```

## Interview Discussion Points

Great topics to discuss with your interviewer:

1. **Tradeoffs**: Single lock vs. fine-grained locking
2. **Scalability**: How would this work with 1M users?
3. **Failure modes**: What if the server crashes mid-transaction?
4. **Testing**: How do you test race conditions reliably?
5. **Monitoring**: What metrics would you track in production?
6. **Edge cases**: What about negative refunds? Partial refunds?

Remember: At Circle, **correctness > performance**. Better to be slow and correct than fast and wrong with people's money!

