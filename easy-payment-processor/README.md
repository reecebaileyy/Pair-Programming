# Easy: Payment Transaction Processor

## Circle Engineering Challenge - Entry Level

Welcome to your Circle pair programming interview! You'll be working on a payment transaction processor that handles concurrent payment requests with idempotency guarantees - a critical component of Circle's payment infrastructure.

## Business Context

At Circle, we process millions of payment transactions daily through our USDC stablecoin and payment APIs. Our systems must:
- Handle concurrent requests from multiple users simultaneously
- Ensure no duplicate charges occur (idempotency)
- Maintain accurate account balances under high load
- Operate 24/7 with zero tolerance for financial inconsistencies

## The Situation

A previous engineer started building a `PaymentProcessor` service but left several bugs in the code before moving to another project. The QA team has reported:
- Occasional duplicate charges when the same payment is submitted multiple times
- Race conditions causing incorrect balance calculations under concurrent load
- The refund functionality was never completed

Your task is to debug the existing code and complete the missing functionality.

## Technical Requirements

The `PaymentProcessor` class must:

1. **Process payments safely** - Deduct amounts from user balances correctly
2. **Enforce idempotency** - Using idempotency keys to prevent duplicate charges
3. **Handle concurrency** - Multiple threads processing payments simultaneously must not corrupt balances
4. **Support refunds** - Complete the refund logic (currently has TODOs)
5. **Provide balance queries** - Thread-safe balance lookups

## Known Issues

The QA team identified these failing test scenarios:
- ❌ Concurrent payments to the same account cause incorrect final balance
- ❌ Duplicate idempotency keys sometimes result in double charges
- ❌ Refund functionality is incomplete
- ❌ Race conditions in balance updates

## Interview Rules

**Time Limit**: 90 minutes

**Collaboration**: This is pair programming - discuss your approach, ask questions, and think out loud!

**Testing**: Run `pytest test_payment_service.py -v` to see which tests pass/fail

**What You Can Do**:
- Modify `payment_service.py` to fix bugs and complete TODOs
- Add new methods or data structures if needed
- Ask clarifying questions about requirements
- Use debugging tools (print statements, debugger, etc.)

**What You Cannot Do**:
- Change the test file (tests represent real requirements)
- Import external libraries (use only Python standard library)
- Change method signatures that tests depend on

## Evaluation Criteria

We're assessing:

1. **Problem Identification** (30%)
   - Can you identify the concurrency bugs?
   - Do you understand the idempotency issue?
   - Can you articulate why the bugs occur?

2. **Solution Quality** (40%)
   - Do your fixes actually solve the race conditions?
   - Is the idempotency implementation correct?
   - Is the refund logic complete and correct?

3. **Code Quality** (20%)
   - Clean, readable code
   - Proper use of threading primitives
   - Good error handling

4. **Communication** (10%)
   - Clear explanation of your approach
   - Good questions about edge cases
   - Discussion of tradeoffs

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the tests (many will fail initially)
pytest test_payment_service.py -v

# Run a specific test
pytest test_payment_service.py::test_concurrent_payments -v
```

## Hints

<details>
<summary>Click for hints (try solving first!)</summary>

**Hint 1 - Concurrency**: When multiple threads access shared data (like balances), what Python primitive prevents race conditions?

**Hint 2 - Idempotency**: Think about the order of operations. When should you check the idempotency key vs. when should you record it?

**Hint 3 - Refunds**: A refund is like a payment in reverse. What should happen to the balance? What about idempotency tracking?

**Hint 4 - Testing**: The test file shows exactly what behavior is expected. Read the failing tests carefully!

</details>

## Success Metrics

You're successful when:
- ✅ All 15 tests pass
- ✅ You can explain why your fixes work
- ✅ The code handles edge cases correctly
- ✅ You've demonstrated understanding of concurrency and idempotency concepts

## Real-World Context

At Circle, this pattern applies to:
- **Payment APIs**: All Circle payment endpoints require idempotency keys
- **USDC transfers**: Ensuring transfers happen exactly once, even with retries
- **High-frequency trading**: Processing thousands of concurrent requests
- **Financial compliance**: Zero tolerance for duplicate charges or lost funds

Good luck! Remember, this is pair programming - we want to see how you think and collaborate, not just the final solution.

---

**Note**: After completing this challenge, check `SOLUTION.md` for the reference implementation and explanations.

