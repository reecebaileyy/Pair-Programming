# Hard: Cross-Chain Settlement System

## Circle Engineering Challenge - Entry Level

Welcome to the most challenging workspace! You'll be working on a cross-chain USDC settlement system that orchestrates transfers across multiple blockchains - a core capability for Circle's CCTP (Cross-Chain Transfer Protocol) and Arc blockchain integration.

## Business Context

Circle operates USDC across 15+ blockchains (Ethereum, Solana, Polygon, Arbitrum, Base, etc.). Moving USDC between chains requires sophisticated settlement:

**The Challenge**:
- Users initiate cross-chain transfers (e.g., 1000 USDC from Ethereum → Solana)
- Must burn USDC on source chain
- Must mint USDC on destination chain
- Guarantee **exactly-once** execution (never double-process, never lose funds)
- Handle retries, failures, network issues
- Support concurrent settlements across chains

**Real-World Impact**:
- **Volume**: Billions in cross-chain USDC transfers monthly
- **Speed**: Users expect completion in minutes
- **Reliability**: 99.99% uptime requirement
- **Correctness**: Any bug = lost funds or regulatory violation
- **Scale**: 10,000+ settlements per hour during peak

**What Can Go Wrong**:
- 🔥 Double-processing: Burn once, mint twice → inflates supply
- 🔥 Lost funds: Burn but never mint → user loses money
- 🔥 Partial failures: Source succeeds, destination fails
- 🔥 Race conditions: Concurrent workers process same settlement
- 🔥 Restart failures: Service crashes, loses in-memory state

## The Situation

The settlement engine is partially built but has critical issues:

### 🚨 Critical Bug #1: Race Condition in Status Updates
**Symptom**: Same settlement processed twice by different workers
**Cause**: Check-then-act pattern in status updates (not atomic)
**Impact**: Could mint USDC twice = reserve backing violation
**Test**: `test_concurrent_worker_processing` fails

### 🚨 Critical Bug #2: Idempotency State Lost on Restart
**Symptom**: After service restart, idempotency guarantees lost
**Cause**: Using in-memory dict for idempotency tracking
**Impact**: Retries after restart could duplicate settlements
**Test**: `test_idempotency_survives_restart` fails

### 📝 TODO #1: Distributed Lock Implementation
**Status**: Skeleton only, not implemented
**Requirement**: Prevent multiple workers from processing same settlement
**Must have**: Timeouts (TTL) to handle crashes
**Test**: `test_distributed_lock_prevents_double_processing` fails

### 📝 TODO #2: Exactly-Once Retry Semantics
**Status**: Retry logic incomplete
**Requirement**: Safe retries even after partial completion
**Must handle**: Crashes at any point in the flow
**Test**: `test_retry_after_partial_completion` fails

### 📝 TODO #3: Saga Pattern for Partial Failures
**Status**: Compensation logic not implemented
**Requirement**: Roll back source chain if destination fails
**Must handle**: All failure scenarios gracefully
**Test**: `test_compensation_on_destination_failure` fails

## Technical Requirements

The `SettlementEngine` must:

1. **Atomic Status Transitions**: Status changes must be thread-safe
2. **Persistent Idempotency**: Survives service restarts
3. **Distributed Locking**: Prevent worker conflicts with TTL
4. **Exactly-Once Guarantees**: Even with retries and failures
5. **Saga Compensation**: Roll back on partial failures
6. **Worker Pool Management**: Multiple concurrent workers
7. **Failure Detection**: Detect and recover from crashes

## System Architecture

```
                    ┌─────────────────────────────┐
                    │   Settlement Request        │
                    │  (Source Chain → Dest)      │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   SettlementEngine          │
                    │  - initiate_settlement()    │
                    │  - Acquire distributed lock │
                    │  - Check idempotency        │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐   ┌─────────▼──────────┐   ┌───────▼────────┐
│ Source Chain      │   │ IdempotencyStore   │   │ Distributed    │
│ - burn_tokens()   │   │ (Persistent!)      │   │ Lock Service   │
│ ⚠️ May fail        │   │ ⚠️ In-memory BUG   │   │ ⚠️ TODO         │
└─────────┬─────────┘   └────────────────────┘   └────────────────┘
          │
          │ Success
          │
┌─────────▼──────────┐
│ Destination Chain  │
│ - mint_tokens()    │
│ ⚠️ May fail         │
└─────────┬──────────┘
          │
          │ Success or Failure
          │
┌─────────▼──────────┐
│ Update Status      │
│ - COMPLETED or     │
│   FAILED           │
│ ⚠️ Race condition   │
└────────────────────┘
```

## Known Issues Details

### Bug #1: Race Condition in Status Update

**Location**: `settlement_engine.py`, `_update_settlement_status()`

```python
# BUG: Check-then-act without lock!
if settlement.status == "PENDING":
    settlement.status = "PROCESSING"
    # Race! Another thread can interleave here
```

**Failure Scenario**:
```
Worker A: Check status = PENDING
Worker B: Check status = PENDING (still!)
Worker A: Set status = PROCESSING, start burn
Worker B: Set status = PROCESSING, start burn
Result: Double burn + double mint!
```

### Bug #2: In-Memory Idempotency Store

**Location**: `idempotency_store.py`

```python
class IdempotencyStore:
    def __init__(self):
        self.store = {}  # BUG: In memory, lost on restart!
```

**Failure Scenario**:
```
1. Settlement starts, recorded in memory
2. Service crashes
3. Service restarts, memory cleared
4. Retry arrives, no record of previous attempt
5. Double processing!
```

### TODO #1: Distributed Lock

**Location**: `distributed_lock.py`

Must implement:
- `acquire()`: Get lock with timeout (TTL)
- `release()`: Release lock
- `extend()`: Extend lock if still processing
- **Critical**: Handle case where holder crashes

**Requirements**:
- Only one worker can hold lock at a time
- Lock automatically releases after TTL
- Thread-safe

### TODO #2: Exactly-Once Retry

**Challenge**: Settlement can fail at any step:

```
Step 1: Burn on source ✓
Step 2: Crash! ✗
Step 3: Mint on dest (never happened)

On retry:
- Can't burn again (already burned)
- Must continue from mint step
- How to track progress?
```

**Must implement**: Idempotent retry logic that safely resumes.

### TODO #3: Saga Compensation

**Challenge**: What if destination fails after source succeeded?

```
Step 1: Burn on source ✓
Step 2: Mint on dest ✗ (chain down)

Can't leave funds burned!
Must: Mint back on source (compensation)
```

**Must implement**: Compensation transactions for rollback.

## Interview Rules

**Time Limit**: 90 minutes

**Priority Order**:
1. **First** (Critical): Fix race condition in status update
2. **Second** (Critical): Fix idempotency persistence bug
3. **Third** (Important): Implement distributed lock
4. **Fourth** (Important): Implement exactly-once retries
5. **Fifth** (Stretch): Implement saga compensation

**Realistic Expectation**: 
- Entry-level candidates: Fix bugs + start on distributed lock
- Strong candidates: Fix bugs + complete distributed lock + start retries
- Exceptional candidates: Everything working

**Collaboration**:
- Discuss system design tradeoffs
- Explain distributed systems concepts
- Ask about Circle's actual implementation

**Testing**:
```bash
# Run all tests
pytest test_settlement_engine.py -v

# Focus on specific issue
pytest test_settlement_engine.py::test_concurrent_worker_processing -v

# Run with coverage
pytest test_settlement_engine.py --cov=. --cov-report=term-missing
```

**What You Can Do**:
- Modify all .py files in this workspace
- Add new files if needed
- Use Python standard library
- Simulate persistence (e.g., JSON files for idempotency store)

**What You Cannot Do**:
- Modify test files
- Use external dependencies (except pytest)
- Assume single-threaded execution

## Evaluation Criteria

### Problem Analysis (25%)
- Identify the race condition cause
- Understand the persistence requirement
- Explain distributed locking challenges
- Discuss exactly-once semantics

### Critical Fixes (30%)
- Status update race fixed (atomic operations)
- Idempotency persisted correctly
- No data loss on restart

### Feature Implementation (30%)
- Distributed lock working with TTL
- Retry logic handles partial completion
- Compensation logic for failures

### Code Quality (15%)
- Clean, maintainable code
- Good error handling
- Comprehensive comments
- Efficient algorithms

## Hints

<details>
<summary>Hint 1: Fixing the Race Condition</summary>

The problem is **atomicity**. The check and update must happen together.

Options:
1. Lock the entire settlement object during status update
2. Use atomic compare-and-swap operation
3. Use database transaction (if we had a DB)

For this exercise: Add a lock to each Settlement object.
</details>

<details>
<summary>Hint 2: Persistent Idempotency</summary>

In-memory dict won't survive restarts. Need persistence.

Options:
1. **SQLite database**: Simple, persistent, single file
2. **JSON file**: Very simple, works for exercise
3. **Redis**: Production choice

For this exercise: JSON file is fine!

Pattern:
```python
def record_operation(self, key, value):
    self.store[key] = value
    self._save_to_disk()  # Persist immediately
```
</details>

<details>
<summary>Hint 3: Distributed Lock Design</summary>

Key requirements:
- **Mutual exclusion**: Only one holder
- **Deadlock-free**: TTL auto-releases
- **Fault tolerance**: Works if holder crashes

Simple implementation:
```python
lock_table = {
    "settlement_123": {
        "holder": "worker-A",
        "acquired_at": 1234567890,
        "ttl": 30
    }
}
```

Check TTL on acquire attempt.
</details>

<details>
<summary>Hint 4: Exactly-Once Retry</summary>

Track progress through stages:

```python
PENDING → BURNING → BURNED → MINTING → MINTED → COMPLETED
```

On retry:
1. Check current stage
2. Skip already-completed stages
3. Continue from where it failed

Idempotency: Each stage is idempotent (safe to repeat).
</details>

<details>
<summary>Hint 5: Saga Compensation</summary>

Saga pattern: For each action, define compensation:

```
Action: burn(source) → Compensation: mint(source)
Action: mint(dest) → Compensation: burn(dest)
```

On failure, execute compensations in reverse order.
</details>

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (many will fail)
pytest test_settlement_engine.py -v

# Check what's implemented
cat settlement_engine.py
cat distributed_lock.py
cat idempotency_store.py

# Start with the race condition
pytest test_settlement_engine.py::test_concurrent_worker_processing -v -s
```

## Success Criteria

You're successful when:

**Minimum (Entry Level)**:
- ✅ Race condition fixed (atomic status updates)
- ✅ Idempotency persisted to disk
- ✅ Can explain distributed systems concepts
- ✅ Tests: `test_concurrent_worker_processing`, `test_idempotency_survives_restart` pass

**Target (Strong Entry Level)**:
- ✅ Above, plus distributed lock implemented
- ✅ Lock prevents double processing
- ✅ Tests: Above + `test_distributed_lock_prevents_double_processing` pass

**Stretch (Exceptional)**:
- ✅ All of the above
- ✅ Exactly-once retries working
- ✅ Saga compensation implemented
- ✅ All tests passing

## Real-World Circle Context

This challenge models:

**Circle's CCTP (Cross-Chain Transfer Protocol)**:
- Actual product moving USDC between chains
- Handles billions in transfers
- Must be exactly-once (financial correctness)
- Multiple validators reach consensus

**Circle's Arc Blockchain**:
- Purpose-built for programmable money
- Integrates with traditional finance
- High transaction throughput
- Deterministic finality

**Production Differences**:
- **Consensus**: Byzantine fault-tolerant consensus (not single service)
- **Blockchain Integration**: Real smart contracts and transaction signing
- **Monitoring**: Extensive observability, alerting, tracing
- **Testing**: Chaos engineering, fault injection
- **Scale**: Thousands of workers across multiple datacenters
- **Security**: HSMs, multi-sig, formal verification

## Discussion Topics

Excellent topics to explore with interviewer:

1. **CAP Theorem**: Which do we choose: consistency or availability?
2. **Two-Phase Commit**: Could we use 2PC? Why or why not?
3. **Byzantine Failures**: What if a blockchain lies about state?
4. **Observability**: How would you debug issues in production?
5. **Testing**: How do you test exactly-once guarantees?
6. **Performance**: How to optimize for throughput vs. latency?
7. **State Management**: Alternative approaches to idempotency?

## Common Pitfalls

1. ❌ **Forgetting TTL**: Lock held forever if holder crashes
2. ❌ **Not persisting idempotency**: Restarts = lost guarantees
3. ❌ **Non-atomic status updates**: Race conditions
4. ❌ **Not handling partial completion**: Retries duplicate work
5. ❌ **No compensation logic**: Failed settlements leave inconsistent state
6. ❌ **Assuming single-threaded**: Tests use concurrent workers!
7. ❌ **Not testing crash scenarios**: Real world has crashes

## Advanced Concepts

### Exactly-Once Semantics

In distributed systems, "exactly-once" is hard. What we really mean:

- **At-most-once**: Might lose, never duplicate (unacceptable for money)
- **At-least-once**: Might duplicate, never lose (need idempotency)
- **Exactly-once**: Appears to happen once (achieved via idempotency + retries)

**Key Insight**: Exactly-once = at-least-once delivery + idempotent processing

### Saga Pattern

For long-running distributed transactions:

1. Break into steps (burn, mint)
2. Each step is a local transaction
3. If step fails, run compensating transactions
4. No distributed locks held across steps

**vs. Two-Phase Commit**: Saga more scalable, handles failures better.

### Distributed Lock Properties

- **Safety**: At most one holder at a time
- **Liveness**: Eventually someone can acquire (no deadlock)
- **Fault Tolerance**: Works even if holder crashes

**Redlock Algorithm**: Production distributed locks (Redis-based).

## Time Management Strategy

**0-15 minutes**: Understand the system
- Read all files
- Run tests, understand failures
- Identify the bugs

**15-35 minutes**: Fix critical bugs
- Race condition in status update
- Idempotency persistence
- Verify tests pass

**35-60 minutes**: Implement distributed lock
- Design the lock structure
- Implement acquire/release with TTL
- Test with concurrent workers

**60-80 minutes**: Implement retries (if time)
- Track settlement stages
- Skip completed stages on retry
- Test partial completion scenarios

**80-90 minutes**: Wrap up & discuss
- Code cleanup
- Discuss tradeoffs
- Production considerations

## Resources

After completing, review:
- `SOLUTION.md`: Complete reference implementation
- System design: How Circle actually does this
- Further reading: Distributed systems papers

---

**Note**: This is a **hard** challenge. Don't expect to finish everything. We're evaluating:
- How you approach complex problems
- Your understanding of distributed systems
- Code quality and thought process
- Communication and collaboration

Good luck! Remember: In distributed systems, **assume everything fails**. Design for it.

