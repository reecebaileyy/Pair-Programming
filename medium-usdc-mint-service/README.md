# Medium: USDC Mint Service

## Circle Engineering Challenge - Entry Level

Welcome to the USDC Mint Service challenge! You'll be debugging and completing a service that mints USDC tokens - one of Circle's core operations. This service handles high-volume concurrent requests and must guarantee exactly-once minting semantics.

## Business Context

Circle's USDC stablecoin is backed 1:1 by US dollars. When institutions deposit dollars, Circle mints equivalent USDC tokens on-chain. This is a critical operation:

- **Volume**: Billions of dollars in USDC minted daily
- **Correctness**: Must never mint without deposit, or double-mint
- **Performance**: Handle concurrent mint requests from multiple institutions
- **Compliance**: Every mint is audited and must match reserve deposits
- **Availability**: 24/7 operation across multiple blockchains

A minting error could:
- Break the 1:1 reserve backing (regulatory violation)
- Cost Circle millions in losses
- Damage trust in USDC

## The Situation

The mint service has been deployed but is experiencing critical issues:

1. **Deadlock Incidents**: The service occasionally freezes completely - multiple threads waiting forever
2. **Stale Token Issues**: Expired idempotency tokens are being reused, causing incorrect behavior
3. **Missing Features**: Rate limiting was never implemented (security risk)
4. **Failed Mint Reconciliation**: When mints fail, there's no cleanup logic

Your mission: Debug the deadlock, fix the expiry bug, and implement the missing features.

## Technical Requirements

The `MintService` must:

1. **Mint USDC tokens** - Record mints in the ledger with full traceability
2. **Enforce idempotency** - Use time-limited tokens to prevent duplicate mints
3. **Handle token expiry** - Expired idempotency tokens should allow reminting
4. **Prevent deadlocks** - Support concurrent mints across accounts
5. **Rate limiting** - Prevent abuse (implement the TODO)
6. **Reconciliation** - Handle failed mints properly (implement the TODO)

## Known Issues

Production monitoring has revealed:

### 🚨 Critical: Deadlock Bug
**Symptom**: Service occasionally hangs completely with all threads blocked
**Reproduction**: Concurrent mints to accounts with circular dependencies
**Test**: `test_concurrent_mints_no_deadlock` - currently hangs forever

### 🐛 Bug: Idempotency Token Expiry
**Symptom**: After a token expires (5 seconds), the second mint attempt fails incorrectly
**Reproduction**: Make mint, wait >5s, retry with same token - should succeed but doesn't
**Test**: `test_idempotency_token_expiry` - fails

### 📝 TODO: Rate Limiter
**Status**: Not implemented
**Requirement**: Max 10 mints per account per second
**Test**: `test_rate_limiter` - fails due to NotImplementedError

### 📝 TODO: Failed Mint Reconciliation
**Status**: Not implemented
**Requirement**: When a mint fails mid-process, clean up partial state
**Test**: `test_reconcile_failed_mint` - fails due to NotImplementedError

## Interview Rules

**Time Limit**: 90 minutes

**Priority Order**:
1. **First**: Fix the deadlock (critical production issue)
2. **Second**: Fix the token expiry bug (correctness issue)
3. **Third**: Implement rate limiter (security requirement)
4. **Fourth**: Implement reconciliation (if time permits)

**Collaboration**: 
- Think out loud - explain your debugging process
- Ask about real-world Circle operations
- Discuss tradeoffs in your solutions

**Testing**: 
```bash
pytest test_mint_service.py -v

# Test specific issue
pytest test_mint_service.py::test_concurrent_mints_no_deadlock -v -s

# Note: Deadlock test will timeout - this proves the bug exists
pytest test_mint_service.py::test_concurrent_mints_no_deadlock -v --timeout=10
```

**What You Can Do**:
- Modify `mint_service.py` and `storage.py`
- Restructure the locking strategy
- Add new data structures
- Import from Python standard library only

**What You Cannot Do**:
- Modify test files
- Use external libraries (except pytest)
- Change the public API signatures

## Evaluation Criteria

### Problem Analysis (30%)
- Can you identify the deadlock cause? (lock ordering)
- Do you understand why token expiry fails?
- Can you explain your debugging approach?

### Critical Fixes (40%)
- Deadlock completely resolved (no hangs)
- Token expiry working correctly
- Thread-safe implementation maintained

### Feature Completion (20%)
- Rate limiter implemented correctly
- Reconciliation logic working
- Edge cases handled

### Code Quality (10%)
- Clean, maintainable code
- Good variable names and comments
- Efficient algorithms

## Debugging Hints

<details>
<summary>Hint 1: Finding the Deadlock</summary>

A deadlock occurs when threads circularly wait for locks:
- Thread A holds Lock 1, waits for Lock 2
- Thread B holds Lock 2, waits for Lock 1
- Both wait forever

Look at `_transfer_between_accounts()`. What locks does it acquire? In what order?

What happens if two threads call it with opposite account pairs?
</details>

<details>
<summary>Hint 2: Understanding Lock Ordering</summary>

**Deadlock prevention rule**: Always acquire locks in a consistent order.

If you need locks for accounts A and B, which should you lock first?
Hint: Make the order deterministic (e.g., alphabetical)
</details>

<details>
<summary>Hint 3: Token Expiry Issue</summary>

Look at where token expiry is checked. Is the expired token being removed?
What happens when you try to use an expired token the second time?
</details>

<details>
<summary>Hint 4: Rate Limiter Design</summary>

Need to track: "How many mints has this account done in the last second?"

Consider:
- Sliding window vs. fixed window
- Where to store the counts?
- Thread safety?

Simple approach: Store timestamps of recent mints per account.
</details>

<details>
<summary>Hint 5: Reconciliation Pattern</summary>

When a mint fails after partial completion:
1. Identify what state was changed
2. Roll back those changes
3. Mark the attempt as failed

Think about: What state changes happen during a mint?
</details>

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (many will fail)
pytest test_mint_service.py -v

# Run with timeout to catch deadlocks
pytest test_mint_service.py -v --timeout=5

# Read the code
cat mint_service.py
cat storage.py
```

## System Architecture

```
┌─────────────────────────────────────────┐
│         MintService                     │
│  ┌────────────────────────────────┐    │
│  │  mint_usdc()                    │    │
│  │  - Check idempotency token      │    │
│  │  - Validate account              │    │
│  │  - Rate limit check (TODO)      │    │
│  │  - Record mint in ledger         │    │
│  │  - Update balances               │    │
│  └────────────────────────────────┘    │
│                                         │
│  ┌────────────────────────────────┐    │
│  │  _transfer_between_accounts()   │    │
│  │  ⚠️  DEADLOCK BUG HERE          │    │
│  │  - Acquires multiple locks       │    │
│  │  - Order depends on parameters   │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│           Storage Layer                 │
│  ┌────────────────────────────────┐    │
│  │  Account balances               │    │
│  │  Mint ledger                     │    │
│  │  Idempotency tokens (with TTL)   │    │
│  │  Per-account locks               │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Success Criteria

You're successful when:
- ✅ All tests pass (or all except reconciliation if short on time)
- ✅ No deadlocks (tests complete without hanging)
- ✅ Token expiry works correctly
- ✅ Rate limiter prevents abuse
- ✅ You can explain your fixes clearly

## Real-World Circle Context

This challenge mirrors actual Circle engineering:

- **USDC Minting**: Real Circle operation for all USDC issuance
- **Multi-chain**: Circle mints USDC on 15+ blockchains simultaneously
- **Compliance**: Every mint is audited and must be traceable
- **Reserve Proof**: Circle publishes monthly attestations of reserves
- **Scale**: $50+ billion USDC in circulation

Circle's actual mint service uses:
- Distributed databases (PostgreSQL with replication)
- Message queues (Kafka) for async processing
- Blockchain integration (Ethereum, Solana, etc.)
- Hardware security modules (HSMs) for signing
- Multi-signature approval workflows

But the core concurrency and idempotency challenges are exactly what you're solving here!

## Interview Discussion Topics

Great questions to explore:

1. **Deadlock prevention**: What strategies exist beyond lock ordering?
2. **Idempotency at scale**: How long should tokens live in production?
3. **Rate limiting**: Fixed window vs. sliding window tradeoffs?
4. **Failure scenarios**: What if the database crashes mid-mint?
5. **Testing**: How do you reliably test race conditions?
6. **Monitoring**: What alerts would you set up?

Remember: In financial systems, **correctness is non-negotiable**. Take time to reason about edge cases!

---

**Note**: Check `SOLUTION.md` after completing the challenge for the reference implementation and detailed explanations.


