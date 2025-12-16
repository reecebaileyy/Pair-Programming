# Circle Backend Engineering - Pair Programming Interview Workspaces

Professional pair programming interview challenges for **Backend New Grad Engineers** at Circle, the financial technology company behind USDC and global blockchain infrastructure.

## 🎯 Overview

This repository contains **three progressive difficulty workspaces** designed for 90-minute pair programming interviews. Each workspace features **pre-existing buggy code** that candidates must debug, fix, and complete - simulating real-world engineering scenarios at Circle.

**Core Focus Areas**:
- ⚡ **Concurrency**: Thread safety, race conditions, deadlocks
- 🔄 **Idempotency**: Preventing duplicate operations in financial systems
- 🏗️ **Distributed Systems**: Locks, persistence, exactly-once semantics
- 💰 **Financial Infrastructure**: Payment processing, token minting, cross-chain settlements

## 📁 Workspaces

### 1️⃣ Easy: Payment Transaction Processor
**Difficulty**: Entry Level  
**Time**: 90 minutes  
**Domain**: Payment processing with idempotency (Circle Payment APIs)

**What You'll Debug**:
- ❌ Race condition in balance updates (missing lock)
- ❌ Idempotency key timing bug (allows duplicates)
- 📝 Incomplete refund implementation (TODO)

**Skills Tested**:
- Basic threading and locks
- Idempotency patterns
- Balance consistency

**Initial Test Results**: 8/15 tests passing

```bash
cd easy-payment-processor
pytest test_payment_service.py -v
```

---

### 2️⃣ Medium: USDC Mint Service
**Difficulty**: Intermediate  
**Time**: 90 minutes  
**Domain**: USDC token minting with high concurrency (Core Circle operation)

**What You'll Debug**:
- 🚨 Deadlock bug in transfer operations (lock ordering)
- ❌ Idempotency token expiry not handled
- 📝 Rate limiter missing (TODO)
- 📝 Failed mint reconciliation logic (TODO)

**Skills Tested**:
- Deadlock prevention
- Time-based idempotency
- Rate limiting algorithms
- Atomic operations with rollback

**Initial Test Results**: 10/20 tests passing (some hang due to deadlock)

```bash
cd medium-usdc-mint-service
pytest test_mint_service.py -v --timeout=10
```

---

### 3️⃣ Hard: Cross-Chain Settlement System
**Difficulty**: Advanced  
**Time**: 90 minutes  
**Domain**: Multi-chain USDC settlements (Circle's CCTP & Arc blockchain)

**What You'll Debug**:
- 🚨 Subtle race condition in status updates (check-then-act)
- 🚨 In-memory idempotency store (lost on restart)
- 📝 Distributed lock skeleton (TODO - must implement with TTL)
- 📝 Exactly-once retry logic (TODO)
- 📝 Saga compensation for partial failures (TODO)

**Skills Tested**:
- Distributed systems patterns
- Persistent idempotency guarantees
- Distributed locking with timeouts
- Exactly-once semantics
- Saga pattern for compensation

**Initial Test Results**: 12/25 tests passing

```bash
cd hard-settlement-system
pytest test_settlement_engine.py -v
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd Pair-Programming

# Choose a workspace
cd easy-payment-processor  # or medium-usdc-mint-service or hard-settlement-system

# Install dependencies
pip install -r requirements.txt

# Run tests to see initial state
pytest -v

# Read the README for detailed instructions
cat README.md
```

### Workflow for Each Workspace

1. **Read README.md** (5-10 min)
   - Understand the business context
   - Review known issues
   - Check evaluation criteria

2. **Run Tests** (5 min)
   - See which tests fail
   - Understand expected behavior

3. **Debug & Fix** (60-70 min)
   - Identify bugs through code analysis
   - Fix race conditions and concurrency issues
   - Implement TODOs

4. **Verify & Discuss** (10-15 min)
   - Ensure tests pass
   - Discuss tradeoffs and production considerations

## 📊 Difficulty Comparison

| Aspect | Easy | Medium | Hard |
|--------|------|--------|------|
| **Bug Complexity** | Obvious race conditions | Deadlock + expiry | Subtle race + persistence |
| **Concepts** | Locks, idempotency | Lock ordering, TTL | Distributed systems, sagas |
| **LOC to Fix** | ~30 lines | ~50 lines | ~100+ lines |
| **Tests Passing Initially** | 8/15 (53%) | 10/20 (50%) | 12/25 (48%) |
| **Expected Completion** | Fix all bugs + TODO | Fix bugs + 2 TODOs | Fix bugs + 1-2 TODOs |
| **Time Pressure** | Moderate | High | Very High |

## 🎓 Learning Objectives

### Entry-Level Engineers Should Demonstrate

**Technical Skills**:
- ✅ Identify and fix race conditions
- ✅ Implement proper locking strategies
- ✅ Understand idempotency requirements
- ✅ Debug multi-threaded code
- ✅ Write clean, maintainable solutions

**Soft Skills**:
- ✅ Think out loud during debugging
- ✅ Ask clarifying questions
- ✅ Discuss tradeoffs
- ✅ Collaborate effectively
- ✅ Manage time under pressure

### What Success Looks Like

**Minimum (Entry Level)**:
- Fixed critical bugs (race conditions)
- Tests passing
- Can explain the issues
- Clean code

**Target (Strong Entry Level)**:
- All bugs fixed
- 1-2 TODOs implemented
- Discussed production considerations
- Handled edge cases

**Exceptional**:
- All tests passing
- All TODOs complete
- Multiple solution approaches discussed
- Performance optimizations considered

## 🏢 About Circle

Circle is a financial technology company at the epicenter of the emerging internet of money. We build infrastructure that enables businesses, institutions, and developers to harness blockchain technology for global payments and commerce.

**Key Products**:
- **USDC**: World's largest regulated stablecoin ($50+ billion in circulation)
- **EURC**: Digital euro stablecoin
- **Circle Payments Network**: Real-time global settlement network
- **CCTP**: Cross-Chain Transfer Protocol for USDC
- **Arc**: Layer-1 blockchain for programmable money

**Engineering at Circle**:
- Building financial infrastructure used globally
- Handling billions of dollars in transactions
- 24/7 availability requirements
- Zero tolerance for financial bugs
- Regulatory compliance (MiCA, BitLicense, FCA, MAS, etc.)

Learn more: [https://www.circle.com](https://www.circle.com)

## 📝 Interview Format

### Structure (90 minutes)

**10 min**: Introduction & Setup
- Meet your pair programming partner
- Choose workspace based on experience
- Read the README
- Run initial tests

**60 min**: Collaborative Debugging & Implementation
- Identify bugs together
- Discuss approaches
- Write code
- Run tests iteratively

**20 min**: Wrap-up & Discussion
- Review solution
- Discuss production considerations
- Q&A about Circle engineering
- Feedback

### Evaluation Criteria

**Problem Analysis (30%)**:
- Identifies bugs correctly
- Understands root causes
- Asks good questions

**Solution Quality (40%)**:
- Bugs actually fixed
- Code is correct and thread-safe
- Tests pass

**Code Quality (20%)**:
- Clean, readable code
- Proper error handling
- Good naming and comments

**Communication (10%)**:
- Clear explanations
- Collaborative approach
- Discusses tradeoffs

## 🔧 Technology Stack

**Language**: Python 3.11+

**Core Libraries**:
- `threading` - Concurrency primitives
- `dataclasses` - Clean data structures
- `typing` - Type hints for clarity

**Testing**:
- `pytest` - Test framework
- `pytest-timeout` - Deadlock detection

**Why Python?**:
- Clear syntax for interviews
- Excellent for demonstrating concepts
- Circle uses Python alongside Go and Java

## 💡 Tips for Candidates

### Before the Interview

1. **Review concurrency basics**:
   - Locks, mutexes, semaphores
   - Race conditions and deadlocks
   - Thread-safe patterns

2. **Understand idempotency**:
   - Why it matters in financial systems
   - Common implementation patterns
   - Edge cases

3. **Practice debugging**:
   - Reading stack traces
   - Using print statements effectively
   - Reasoning about concurrent execution

### During the Interview

1. **Communicate constantly**:
   - Think out loud
   - Explain your reasoning
   - Ask questions

2. **Start with tests**:
   - Understand what's expected
   - Use failing tests to guide debugging
   - Run tests frequently

3. **Prioritize critical bugs**:
   - Fix race conditions first
   - Then handle TODOs
   - Edge cases last if time permits

4. **Don't get stuck**:
   - Ask for hints
   - Discuss your approach
   - Move on if necessary

## 📚 Additional Resources

### Documentation

Each workspace includes:
- **README.md**: Problem description and requirements
- **SOLUTION.md**: Reference implementation and explanations
- **Test files**: Comprehensive test suites with clear expectations
- **Code comments**: Hints and pointers to bugs

### Reference Materials

**Concurrency**:
- Python threading documentation
- "The Art of Multiprocessor Programming" (Herlihy & Shavit)

**Distributed Systems**:
- "Designing Data-Intensive Applications" (Kleppmann)
- "Database Internals" (Petrov)

**Financial Systems**:
- Circle Engineering Blog
- Payment API design patterns

## 🤝 Contributing

This repository is maintained by Circle's Engineering team for interview purposes.

For questions or issues:
- Contact: recruiting@circle.com
- Circle Careers: https://www.circle.com/en/careers

## 📄 License

© 2025 Circle Internet Group, Inc. All rights reserved.

This repository is for interview and educational purposes.

---

## 🎯 Workspace Selection Guide

**Choose Easy if you**:
- Have limited concurrent programming experience
- Want to focus on fundamentals
- Prefer clear, straightforward bugs
- Are early in your career

**Choose Medium if you**:
- Have worked with threads before
- Want moderate challenge
- Like deadlock and timing puzzles
- Have 1+ year experience

**Choose Hard if you**:
- Have distributed systems experience
- Want maximum challenge
- Enjoy complex architectural problems
- Have 2+ years or strong internship experience

**Not sure?** Start with Easy! You can always move up if you finish early.

---

## 📞 Support During Interview

Your interviewer will:
- Answer questions about requirements
- Provide hints if stuck
- Discuss Circle's actual implementation
- Give feedback in real-time

Remember: **This is pair programming, not a solo test!** Collaboration is encouraged and expected.

---

## 🌟 Why These Challenges?

These workspaces reflect **real Circle engineering problems**:

1. **Payment Processor** → Circle's payment APIs require idempotency
2. **USDC Mint Service** → Actual USDC issuance operations
3. **Settlement System** → Circle's CCTP cross-chain protocol

The bugs are inspired by **actual production issues** that financial systems face. By solving these challenges, you're demonstrating skills Circle engineers use daily.

---

**Good luck! We're excited to see how you approach these challenges. 🚀**

_"At Circle, we're building a new internet financial system where value can travel like other digital data — globally, nearly instantly, and less expensively than legacy settlement systems."_

---

## Quick Links

- 🏠 [Circle Homepage](https://www.circle.com)
- 💼 [Circle Careers](https://www.circle.com/en/careers)
- 📖 [Circle Developer Docs](https://developers.circle.com)
- 🪙 [USDC](https://www.circle.com/en/usdc)
- 🔗 [CCTP](https://www.circle.com/en/cross-chain-transfer-protocol)
- ⚡ [Arc Blockchain](https://www.circle.com/en/arc)
