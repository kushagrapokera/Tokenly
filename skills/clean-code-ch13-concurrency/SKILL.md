---
name: clean-code-ch13-concurrency
description: "Code quality checker based on Clean Code Ch13: Concurrency — checks SRP for threading, data scope limiting, execution models, synchronized section size, shut-down correctness, and threaded code testing. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 13: Concurrency -- Code Quality Checker

## When to Use

Apply this skill whenever reviewing or writing code that involves:
- Multiple threads, goroutines, coroutines, or async tasks
- Shared mutable state accessed by more than one execution context
- Locks, mutexes, semaphores, synchronized blocks, or any synchronization primitive
- Producer-consumer queues, worker pools, or parallel pipelines
- Graceful shutdown logic for long-running or daemon-like systems
- Thread-safe collections or concurrent data structures
- Any code where timing, ordering, or scheduling of execution matters

## Core Concepts

### Chapter Attribution
- Written by **Brett L. Schuchert**
- Epigraph: *"Objects are abstractions of processing. Threads are abstractions of schedule."* -- James O. Coplien

### Why Concurrency?
- Concurrency is a **decoupling strategy**: it separates *what* gets done from *when* it gets done
- In single-threaded code, *what* and *when* are tightly coupled (visible in stack traces); concurrency breaks this coupling
- Structural benefit: the application looks like many small collaborating components rather than one big main loop
- Performance benefit: systems with heavy I/O wait time or many users can see dramatic throughput improvements
- Concurrency is NOT always the answer -- it adds complexity and must be justified by structural or performance needs

#### Motivating Examples from the Chapter
- **Servlet model**: Web/EJB containers *partially* manage concurrency -- servlets execute asynchronously, each in its own world, decoupled from others. *In principle* the programmer doesn't manage incoming requests. But the decoupling is far less than perfect; programmers must still guard against concurrent update and deadlock.
- **Information aggregator**: A single-threaded system hitting many web sites sequentially, always finishing one before starting the next. As sites are added, the daily run exceeds 24 hours. A multithreaded version hits more than one site at a time, dramatically reducing wall-clock time by sharing I/O wait time across threads.
- **Multi-user response time**: A system handling one user per second is responsive for a few users, but with many users, response times grow (no one wants to wait behind 150 others). Handling users concurrently improves response time.
- **Large data set processing**: A system interpreting large data sets where each data set can be processed on a different computer in parallel.

### Myths and Misconceptions (MUST understand these)
1. **MYTH: Concurrency always improves performance** -- TRUTH: Only sometimes, when there is wait time shareable across threads/processors. Neither situation is trivial.
2. **MYTH: Design does not change when writing concurrent programs** -- TRUTH: Concurrent design is remarkably different from single-threaded design. The decoupling of *what* from *when* has a huge structural effect.
3. **MYTH: Understanding concurrency issues is not important when using a container (e.g., web server, EJB container)** -- TRUTH: You must know what your container does and guard against concurrent update and deadlock issues yourself.

### Balanced Truths
- Concurrency incurs overhead, both in performance and in additional code
- Correct concurrency is complex, even for simple problems
- Concurrency bugs are not usually repeatable, so they are often dismissed as one-offs instead of treated as true defects
- Concurrency often requires a fundamental change in design strategy

### Challenges
- Simple operations (like `++lastIdUsed`) can produce surprising wrong results when two threads execute them simultaneously
- Example: two threads share an instance of class X with `lastIdUsed` set to 42, both call `getNextId()`. Three possible outcomes:
  - Thread one gets 43, thread two gets 44, `lastIdUsed` is 44 (correct)
  - Thread one gets 44, thread two gets 43, `lastIdUsed` is 44 (correct)
  - Thread one gets 43, thread two gets 43, `lastIdUsed` is 43 (**surprising wrong result** -- the two threads stepped on each other)
- A single line of Java code can generate thousands of possible byte-code execution paths when two threads run it (e.g., 12,870 paths for `int`, 2,704,156 for `long`)
- Most paths produce correct results, but *some do not* -- and those are the bugs

## Checklist

### Concurrency Defense Principles

- [ ] **D1: Single Responsibility Principle (SRP) for Concurrency** -- Concurrency-related code is separated from non-concurrency code
  - Concurrency code has its own life cycle of development, change, and tuning
  - Concurrency code has its own challenges, different from and harder than non-concurrent code
  - Miswritten concurrency code can fail in enough ways without the added burden of application logic
  - **Action**: Keep concurrency-related code in its own classes/modules, separate from business logic

- [ ] **D2: Limit the Scope of Shared Data** -- Minimize the number of places where shared data can be updated
  - Use `synchronized` / locks / mutexes to protect critical sections that access shared objects
  - The more places shared data can be updated, the more likely you will:
    - Forget to protect one or more of those places, breaking all code that modifies shared data
    - Duplicate effort to ensure everything is guarded (DRY violation)
    - Have difficulty finding the source of failures
  - **Action**: Take data encapsulation to heart; severely limit the access of any data that may be shared

- [ ] **D3: Use Copies of Data** -- Avoid sharing objects in the first place
  - Copy objects and treat them as read-only
  - Copy objects, collect results from multiple threads in separate copies, then merge in a single thread
  - The cost of extra object creation and garbage collection is often less than the cost of intrinsic locks and synchronization overhead
  - **Action**: Prefer immutable copies over shared mutable state wherever possible

- [ ] **D4: Threads Should Be as Independent as Possible** -- Each thread should exist in its own world
  - Each thread processes one request, with all required data coming from an unshared source and stored as local variables
  - Threads should behave as if they were the only thread in the world, with no synchronization requirements
  - **Action**: Partition data into independent subsets that can be operated on by independent threads, possibly in different processors

### Know Your Library

- [ ] **L1: Use thread-safe collections** -- Prefer `ConcurrentHashMap` over `HashMap`, or equivalent concurrent data structures in your language
- [ ] **L2: Use the executor framework** for executing unrelated tasks (thread pools, task scheduling)
- [ ] **L3: Use nonblocking solutions when possible** -- Lock-free algorithms, atomic operations
- [ ] **L4: Know which library classes are NOT thread safe** -- Do not assume thread safety without verification
- [ ] **L5: Know advanced concurrency classes** available in your language:
  - `ReentrantLock` -- a lock that can be acquired in one method and released in another
  - `Semaphore` -- classic semaphore, a lock with a count
  - `CountDownLatch` -- a lock that waits for N events before releasing all waiting threads
  - Language-specific equivalents (Go: `sync.Mutex`, `sync.WaitGroup`, channels; Python: `threading.Lock`, `queue.Queue`; etc.)
- [ ] **L6: Review the concurrent classes available in your language** -- In Java, become familiar with `java.util.concurrent`, `java.util.concurrent.atomic`, `java.util.concurrent.locks`; the `ConcurrentHashMap` performs better than `HashMap` in nearly all situations, allows simultaneous concurrent reads and writes, and has methods supporting common composite operations that are otherwise not thread safe

### Know Your Execution Models

Understand these fundamental concurrency definitions:

| Term | Definition |
|------|-----------|
| **Bound Resources** | Resources of fixed size or number (database connections, fixed-size read/write buffers) |
| **Mutual Exclusion** | Only one thread can access shared data or a shared resource at a time |
| **Starvation** | One thread or a group of threads is prohibited from proceeding for an excessively long time or forever. For example, always letting fast-running threads through first could starve out longer running threads if there is no end to the fast-running threads |
| **Deadlock** | Two or more threads waiting for each other to finish. Each thread has a resource that the other thread requires and neither can finish until it gets the other resource |
| **Livelock** | Threads in lockstep, each trying to do work but finding another "in the way." Due to resonance, threads continue trying to make progress but are unable to for an excessively long time -- or forever |

- [ ] **E1: Producer-Consumer** -- Producers create work and place it in a buffer/queue; consumers take work from the queue and complete it
  - The queue is a *bound resource*
  - Producers must wait for free space; consumers must wait for items
  - Coordination via signaling: producers signal "queue not empty"; consumers signal "queue not full"
  - Both may potentially wait to be notified when they can continue

- [ ] **E2: Readers-Writers** -- A shared resource that primarily serves as a source of information for readers, but is occasionally updated by writers
  - Emphasizing throughput for readers can cause starvation of writers and the accumulation of stale information
  - Allowing readers so they do not read something a writer is updating (and vice versa) is a tough balancing act; writers tend to block many readers for a long period of time, causing throughput issues
  - Giving writers priority can reduce throughput; if there are frequent writers and they are given priority, throughput will suffer
  - The challenge is to balance the needs of both readers and writers to satisfy correct operation, provide reasonable throughput, and avoid starvation
  - Simple strategy: writers wait until there are no readers before performing an update -- but continuous readers starve writers

- [ ] **E3: Dining Philosophers** -- A number of philosophers sit around a circular table. A fork is placed to the left of each philosopher. There is a big bowl of spaghetti in the center. The philosophers spend their time thinking unless they get hungry. Once hungry, they pick up the forks on either side of them and eat. A philosopher cannot eat unless holding two forks. If the philosopher to his right or left is already using one of the forks he needs, he must wait until that philosopher finishes eating and puts the forks back down. Once a philosopher eats, he puts both forks back down and waits until he is hungry again.
  - Replace philosophers with threads and forks with resources: this maps to many enterprise applications in which processes compete for resources
  - Unless carefully designed, such systems can experience deadlock, livelock, throughput degradation, and efficiency degradation
  - A thread needs multiple resources simultaneously to proceed

- [ ] **E4: Study these algorithms** -- Most concurrent problems are variations of these three. Learn them and write solutions yourself.

### Synchronized Method Dependencies

- [ ] **S1: Avoid dependencies between synchronized methods on a shared object** -- If there is more than one synchronized method on the same shared class, the system may be written incorrectly
- [ ] **S2: When multiple methods on a shared object are necessary**, use one of three strategies:
  - **Client-Based Locking**: Client locks the server before calling the first method; lock extent includes all method calls
  - **Server-Based Locking**: Server creates a method that locks the server, calls all methods, then unlocks. Client calls the single combined method
  - **Adapted Server**: Create an intermediary that performs the locking (when the original server cannot be changed)

### Keep Synchronized Sections Small

- [ ] **K1: Synchronized/locked sections must be as small as possible**
  - The `synchronized` keyword introduces a lock; all sections of code guarded by the same lock are guaranteed to have only one thread executing through them at any given time
  - Locks are expensive: they create delays and add overhead
  - Do not litter code with `synchronized` statements
  - Critical sections must be guarded, but design code with **as few critical sections as possible**
  - A critical section is any section of code that must be protected from simultaneous use for the program to be correct
  - **Anti-pattern**: Some naive programmers try to achieve this by making their critical sections very large -- however, extending synchronization beyond the minimal critical section increases contention and degrades performance
  - **Action**: Keep your synchronized sections as small as possible

### Writing Correct Shut-Down Code

- [ ] **SD1: Think about shut-down early and get it working early** -- It will take longer than expected
- [ ] **SD2: Watch for deadlock in shutdown** -- Parent threads waiting for children that are deadlocked; consumers blocked expecting messages from already-shut-down producers
- [ ] **SD3: Review existing shutdown algorithms** -- This is probably harder than you think
- [ ] **SD4: Common shutdown problems**:
  - Parent spawns children, waits for all to finish, but one child is deadlocked -- parent waits forever
  - Producer shuts down, but consumer is blocked waiting for the next message and never receives the shutdown signal

### Testing Threaded Code

- [ ] **T1: Write tests that have the potential to expose problems** -- Run them frequently, with different programmatic configurations, system configurations, and load
- [ ] **T2: If tests ever fail, track down the failure** -- Do not ignore a failure just because the tests pass on a subsequent run
- [ ] **T3: Treat spurious failures as candidate threading issues** -- Do not assume one-offs are cosmic rays. Threaded code causes things to fail that "simply cannot fail." Bugs may appear once in a thousand or million executions. Assume one-offs do not exist.
- [ ] **T4: Get your nonthreaded code working first** -- Do not chase threading bugs and nonthreading bugs simultaneously. Create POJOs/plain objects called by threads; test them independently outside of the threaded environment.
- [ ] **T5: Make your threaded code pluggable** -- Write concurrency-supporting code to run in several configurations:
  - One thread, several threads, varied as it executes
  - Threaded code interacts with real components or test doubles
  - Execute with test doubles that run quickly, slowly, variably
  - Configure tests to run for a configurable number of iterations
- [ ] **T6: Make your threaded code tunable** -- Allow the number of threads to be easily tuned, even at runtime. Allow self-tuning based on throughput and system utilization.
- [ ] **T7: Run with more threads than processors** -- Encourage task swapping to surface missing critical sections and deadlock conditions
- [ ] **T8: Run on different platforms** -- Different operating systems have different threading policies that impact execution. Code that passes on one OS may fail on another. Run threaded code on all target platforms early and often.
- [ ] **T9: Instrument your code to try and force failures** -- Threading bugs hide because only a few of thousands of possible pathways through vulnerable sections actually fail. The probability of hitting a failing pathway is startlingly low.

#### Instrumentation: Hand-Coded
  - Insert calls to `wait()`, `sleep()`, `yield()`, `priority()` (or language equivalents) to change execution pathways
  - Useful for testing particularly thorny pieces of code
  - **Drawbacks**: Must manually find appropriate places; unclear which call to use; slows production code; shotgun approach that may not find flaws
  - **Better approach**: Divide system into POJOs (thread-ignorant) and threading classes, then create test jigs that invoke POJOs under different regimes of sleep, yield, etc.

#### Instrumentation: Automated
  - Use tools (Aspect-Oriented Frameworks, CGLIB, ASM, or language-specific equivalents) to programmatically instrument code
  - Create a "jiggle point" class (e.g., `ThreadJigglePoint.jiggle()`) and insert calls at critical points
  - In production: `jiggle()` does nothing
  - In testing: `jiggle()` randomly selects among sleeping, yielding, or falling through
  - Running tests a thousand times with random jiggling roots out flaws
  - Tools like IBM's ConTest provide sophisticated automated jiggling
  - **Action**: Use jiggling strategies to ferret out errors

## Violations to Detect

### Critical Violations (High Severity)

| ID | Violation | What to Look For |
|----|-----------|-----------------|
| V1 | **Shared mutable state without synchronization** | Fields/variables accessed by multiple threads with no lock, mutex, synchronized block, or atomic operation protecting them |
| V2 | **Concurrency logic mixed with business logic** | Threading code (locks, thread spawning, synchronization) interleaved directly with domain/business logic instead of being separated (SRP violation) |
| V3 | **Overly broad synchronized sections** | Lock/synchronized blocks that encompass far more code than the actual critical section; entire methods locked when only a few lines need protection |
| V4 | **Dependencies between synchronized methods** | Multiple synchronized methods on the same object that must be called in sequence, creating subtle ordering bugs |
| V5 | **No shutdown strategy** | Long-running/daemon code with no graceful shutdown mechanism; threads that cannot be signaled to stop; missing deadlock considerations in shutdown paths |
| V6 | **Ignoring spurious test failures** | Threading test failures dismissed as "one-offs" or "cosmic rays" instead of investigated as genuine concurrency bugs |
| V7 | **Using non-thread-safe collections in concurrent contexts** | Standard HashMap, ArrayList, etc. shared between threads without external synchronization when thread-safe alternatives exist |

### Moderate Violations (Medium Severity)

| ID | Violation | What to Look For |
|----|-----------|-----------------|
| V8 | **Shared mutable data with too many access points** | Shared data modified in many different places rather than encapsulated with minimal access points |
| V9 | **No use of copies/immutability** | Sharing mutable objects between threads when copying or treating as read-only would eliminate the need for synchronization |
| V10 | **Threads not independent** | Threads sharing data unnecessarily when they could each work on independent subsets of data with no synchronization |
| V11 | **Nonthreaded code not tested independently** | Business logic only tested within its threaded context, making it impossible to distinguish threading bugs from logic bugs |
| V12 | **Non-pluggable threading configuration** | Thread counts, pool sizes, and configurations hard-coded rather than tunable/configurable |
| V13 | **Unrecognized execution model** | Code implementing Producer-Consumer, Readers-Writers, or Dining Philosophers patterns without recognizing them, leading to missed edge cases (starvation, deadlock, livelock) |

### Minor Violations (Low Severity)

| ID | Violation | What to Look For |
|----|-----------|-----------------|
| V14 | **Tests only run on one platform** | Threaded tests never executed on different OSes with different threading policies |
| V15 | **No forced-failure instrumentation** | No jiggle points, no randomized delays, no mechanism to force different execution orderings during testing |
| V16 | **Tests run with fewer threads than processors** | Not running with enough threads to encourage task swapping and expose race conditions |
| V17 | **Missing concurrency library knowledge** | Hand-rolling synchronization when the language standard library provides better, tested concurrent data structures and utilities |

## How to Fix

### Fix for V1 (Shared mutable state without synchronization)
**Before (WRONG):**
```java
public class IdGenerator {
    private int lastIdUsed;
    public int getNextId() {
        return ++lastIdUsed; // 12,870 possible paths for two threads!
    }
}
```
**After (CORRECT):**
```java
public class IdGenerator {
    private final AtomicInteger lastIdUsed = new AtomicInteger(0);
    public int getNextId() {
        return lastIdUsed.incrementAndGet();
    }
}
```

### Fix for V2 (Concurrency mixed with business logic)
**Before (WRONG):**
```java
public class OrderProcessor {
    public void processOrders(List<Order> orders) {
        ExecutorService pool = Executors.newFixedThreadPool(4);
        for (Order order : orders) {
            pool.submit(() -> {
                synchronized(this) {
                    // 50 lines of business logic interleaved with threading
                    validateOrder(order);
                    calculateTax(order);
                    chargePayment(order);
                }
            });
        }
        pool.shutdown();
    }
}
```
**After (CORRECT):**
```java
// POJO: Pure business logic, no threading awareness
public class OrderProcessor {
    public OrderResult process(Order order) {
        validateOrder(order);
        calculateTax(order);
        return chargePayment(order);
    }
}

// Separate class: Concurrency concerns only
public class ConcurrentOrderDispatcher {
    private final ExecutorService pool;
    private final OrderProcessor processor;

    public ConcurrentOrderDispatcher(int threadCount) {
        this.pool = Executors.newFixedThreadPool(threadCount);
        this.processor = new OrderProcessor();
    }

    public List<Future<OrderResult>> dispatch(List<Order> orders) {
        return orders.stream()
            .map(order -> pool.submit(() -> processor.process(order)))
            .collect(Collectors.toList());
    }
}
```

### Fix for V3 (Overly broad synchronized sections)
**Before (WRONG):**
```java
public synchronized void updateAccount(Account acct) {
    // Logging -- does not need lock
    logger.info("Updating account " + acct.getId());
    // Validation -- does not need lock
    validateAccount(acct);
    // ONLY this needs synchronization
    accounts.put(acct.getId(), acct);
    // Notification -- does not need lock
    notifyListeners(acct);
}
```
**After (CORRECT):**
```java
public void updateAccount(Account acct) {
    logger.info("Updating account " + acct.getId());
    validateAccount(acct);
    synchronized(accounts) {
        accounts.put(acct.getId(), acct); // Only the critical section is locked
    }
    notifyListeners(acct);
}
```

### Fix for V4 (Dependencies between synchronized methods)
**Before (WRONG):**
```java
// Client calls both methods -- gap between calls is unprotected
synchronized int getCount() { return count; }
synchronized void setCount(int c) { count = c; }
// Client: obj.setCount(obj.getCount() + 1); // RACE CONDITION between get and set
```
**After (CORRECT -- Server-Based Locking):**
```java
public synchronized void incrementCount() {
    count++; // Single atomic operation on the server
}
```

### Fix for V5 (No shutdown strategy)
**Before (WRONG):**
```java
public void start() {
    while (true) { // No way to stop
        process(queue.take());
    }
}
```
**After (CORRECT):**
```java
private volatile boolean running = true;

public void start() {
    while (running) {
        try {
            Item item = queue.poll(1, TimeUnit.SECONDS);
            if (item != null) process(item);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            running = false;
        }
    }
    cleanup();
}

public void shutdown() {
    running = false;
}
```

### Fix for V9 (No use of copies/immutability)
**Before (WRONG):**
```java
// Shared mutable config accessed by all threads
public class Config {
    private Map<String, String> settings; // Mutable, shared
    public synchronized String get(String key) { return settings.get(key); }
    public synchronized void set(String key, String val) { settings.put(key, val); }
}
```
**After (CORRECT):**
```java
// Immutable copy -- no synchronization needed for reads
public class Config {
    private volatile Map<String, String> settings; // Replace entire map atomically
    public String get(String key) {
        return settings.get(key); // No lock needed -- reading immutable snapshot
    }
    public void update(String key, String val) {
        Map<String, String> copy = new HashMap<>(settings);
        copy.put(key, val);
        settings = Collections.unmodifiableMap(copy); // Atomic reference swap
    }
}
```

### Fix for V15 (No forced-failure instrumentation)
**Before:** No jiggle points, relying on luck to find race conditions.

**After (Automated jiggling):**
```java
public class ThreadJigglePoint {
    private static boolean testing = false;
    private static final Random random = new Random();

    public static void enable() { testing = true; }
    public static void disable() { testing = false; }

    public static void jiggle() {
        if (!testing) return;
        int action = random.nextInt(3);
        if (action == 0) return; // Do nothing
        if (action == 1) Thread.yield();
        if (action == 2) {
            try { Thread.sleep(random.nextInt(5)); }
            catch (InterruptedException e) { /* ignore */ }
        }
    }
}

// Usage in concurrent code:
public synchronized String nextUrlOrNull() {
    if (hasNext()) {
        ThreadJigglePoint.jiggle();
        String url = urlGenerator.next();
        ThreadJigglePoint.jiggle();
        updateHasNext();
        ThreadJigglePoint.jiggle();
        return url;
    }
    return null;
}
```

## Chapter Conclusion -- Key Synthesis Points

These points from the chapter's conclusion synthesize the above into actionable wisdom and include unique insights not stated elsewhere:

- Concurrent code is difficult to get right. Code that is simple to follow can become nightmarish when multiple threads and shared data get into the mix.
- **First and foremost**, follow SRP: break your system into POJOs that separate thread-aware code from thread-ignorant code. When testing thread-aware code, you are only testing it and nothing else -- this suggests that **your thread-aware code should be small and focused**.
- Know the possible sources of concurrency issues: multiple threads operating on shared data, or using a common resource pool. **Boundary cases, such as shutting down cleanly or finishing the iteration of a loop, can be especially thorny.**
- Learn your library and know the fundamental algorithms. Understand how some of the features offered by the library support solving problems similar to the fundamental algorithms.
- **Learn how to find regions of code that must be locked and lock them. Do not lock regions of code that do not need to be locked. Avoid calling one locked section from another.** This requires a deep understanding of whether something is or is not shared.
- Keep the amount of shared objects and the scope of the sharing as narrow as possible. **Change designs of the objects with shared data to accommodate clients rather than forcing clients to manage shared state.**
- Issues will crop up. The ones that do not crop up early are often written off as a one-time occurrence. These so-called one-offs typically only happen under load or at seemingly random times. Therefore, you need to be able to **run your thread-related code in many configurations on many platforms repeatedly and continuously**.
- **Testability, which comes naturally from following the Three Laws of TDD**, implies some level of plug-ability, which offers the support necessary to run in a wider range of configurations.
- Invest in instrumentation early. You want to be running your thread-based code as long as possible before you put it into production.
- **If you take a clean approach, your chances of getting it right increase drastically.**

## Self-Improvement Protocol

After every concurrency code review, answer these questions:

1. **SRP Separation**: Is ALL concurrency code (thread management, synchronization, locking) in dedicated classes, separate from business logic POJOs?
2. **Shared Data Audit**: Can I list every piece of shared mutable data? Is each one protected? Can any be eliminated by using copies or partitioning?
3. **Scope Minimization**: For each synchronized/locked section, is it the absolute minimum code necessary? Could I narrow the scope further?
4. **Execution Model Recognition**: Does this code match a known pattern (Producer-Consumer, Readers-Writers, Dining Philosophers)? Am I handling that pattern's specific risks (starvation, deadlock, livelock)?
5. **Library Usage**: Am I using the best concurrent data structures and utilities available in my language, or am I hand-rolling what the standard library already provides?
6. **Shutdown Path**: If this code runs long-term, is there a graceful shutdown path? Have I considered deadlock scenarios during shutdown?
7. **Testing Rigor**:
   - Are spurious failures treated as real bugs?
   - Is nonthreaded logic tested independently?
   - Is threading configuration pluggable and tunable?
   - Are tests run with more threads than processors?
   - Are tests run on multiple platforms?
   - Is there any instrumentation (jiggle points) to force different execution orderings?
8. **Myth Check**: Am I assuming concurrency will "just work" or "always be faster"? Am I respecting that correct concurrency is fundamentally hard?

### Key Recommendations Summary (from the chapter)
- Keep your concurrency-related code separate from other code (SRP)
- Severely limit the access of any data that may be shared
- Use copies of data rather than sharing mutable objects
- Partition data into independent subsets for independent threads
- Review the concurrent data structures and utilities in your language
- Learn Producer-Consumer, Readers-Writers, and Dining Philosophers and recognize them in your code
- Avoid using more than one synchronized method on a shared object
- Keep synchronized sections as small as possible
- Think about shut-down early -- it is harder than you expect
- Do not ignore system failures as one-offs
- Get nonthreaded code working first, independently; make sure your code works outside of threads
- Make threaded code pluggable and tunable
- Run with more threads than processors
- Run on different platforms
- Use jiggling strategies (hand-coded or automated) to ferret out errors
- Do not lock regions of code that do not need to be locked; avoid calling one locked section from another
- Change designs of objects with shared data to accommodate clients rather than forcing clients to manage shared state
- Invest in instrumentation early; run your thread-based code as long as possible before putting it into production
