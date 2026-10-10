---
name: clean-code-appa-concurrency-ii
description: "Code quality checker based on Clean Code Appendix A: Concurrency II -- checks server threading patterns, execution path analysis, library thread-safety, method dependency in concurrent code, deadlock prevention (4 conditions), and multithreaded testing strategies. Scope: shared - applies to backend and frontend code."
---

# Clean Code Appendix A: Concurrency II -- Code Quality Checker

## When to Use

Apply this skill whenever reviewing or writing code that involves:
- Server/client architectures handling multiple simultaneous connections
- Any use of threads, thread pools, executors, or concurrent task scheduling
- Shared mutable state accessed by more than one thread
- Synchronized methods or blocks, locks, mutexes, semaphores
- Non-atomic operations on shared variables (increment, check-then-act, read-modify-write)
- Resource pools (database connections, MQ connections, file handles)
- Iterator or collection usage across multiple threads
- Performance optimization via concurrency for I/O-bound operations
- Any code where deadlock, livelock, or starvation could occur

## Checklist

### 1. Server Threading Architecture (SRP for Concurrency)

- [ ] **Thread management is isolated into its own class/module** -- not mixed with socket connection management, client processing, or server shutdown logic
- [ ] **Server code separates these responsibilities into distinct classes:**
  - Socket connection management
  - Client processing / business logic
  - Threading policy (how many threads, pool vs. per-request)
  - Server shutdown policy
- [ ] **Threading policy is behind an abstraction** (e.g., a `ClientScheduler` interface) so the strategy can be changed without modifying other code
- [ ] **Thread pool / Executor framework is used** instead of manually creating `new Thread()` for each request
- [ ] **Thread count is bounded** -- the server cannot create unlimited threads that exhaust JVM/OS resources under load
- [ ] **I/O-bound vs. CPU-bound work is identified** -- threading only improves throughput for I/O-bound work; adding threads to CPU-bound work does not help

### 2. Possible Paths of Execution

- [ ] **Developers understand the combinatorial explosion** -- for N bytecode instructions across T threads, the number of possible execution paths is (N*T)! / N!^T
- [ ] **Even a single line of source code compiles to multiple bytecode instructions** -- e.g., `return ++lastIdUsed;` becomes 8 bytecode instructions, yielding 12,870 possible paths for just 2 threads
- [ ] **The three possible outcomes are understood** -- when two threads both call `incrementValue()` on a shared `IdGenerator` (starting at 93): (a) Thread 1 gets 94, Thread 2 gets 95, lastIdUsed is 95; (b) Thread 1 gets 95, Thread 2 gets 94, lastIdUsed is 95; (c) Thread 1 gets 94, Thread 2 gets 94, lastIdUsed is **94** (lost update -- one increment is lost)
- [ ] **The `++` operator (pre-increment and post-increment) is NOT atomic** -- it involves GETFIELD, IADD, and PUTFIELD as separate interruptible steps
- [ ] **The full bytecode for `++lastIdUsed` is understood** -- the 8 instructions are: ALOAD 0, DUP, GETFIELD lastId, ICONST_1, IADD, DUP_X1, PUTFIELD value, IRETURN -- a context switch can occur between ANY of these instructions
- [ ] **The lost-update interleaving is understood** -- Thread 1 executes through GETFIELD (reads 42 onto its operand stack), gets interrupted; Thread 2 runs the entire method (reads 42, increments to 43, stores 43, returns 43); Thread 1 resumes with stale value 42 still on its operand stack, adds 1 to get 43, stores 43, returns 43 -- one increment is lost
- [ ] **Contrast: `resetId()` (assigning a constant) IS atomic** -- its bytecode is only ALOAD 0, ICONST_0, PUTFIELD lastId; although the thread can be interrupted between these instructions, the operands (constant 0 and `this` reference) are local to the frame and cannot be affected by another thread, so the outcome is always the same
- [ ] **Assignment to 32-bit values (int) is atomic per JVM spec**, but assignment to 64-bit values (long, double) is NOT guaranteed atomic -- it may require two 32-bit operations; if `lastIdUsed` were `long`, every read/write becomes two 32-bit operations, increasing possible paths from 12,870 to **2,704,156**
- [ ] **JVM bytecode concepts are understood**: Frame (return address + parameters + local variables for each method invocation, enabling the call stack), Local variable (variables in method scope, including `this` as the 0th variable in instance methods), Operand stack (LIFO stack where JVM instructions place their parameters -- each thread has its own, so values on the operand stack cannot be touched by other threads)
- [ ] **Shared mutable fields are identified** and developers know:
  - Where shared objects/values exist
  - Which code paths can cause concurrent read/update issues
  - How to guard against those issues (synchronized, atomic classes, immutability)
- [ ] **The `synchronized` keyword is used on methods/blocks that access shared mutable state** -- reducing possible execution paths from thousands to N! (for 2 threads) or just 2

### 3. Know Your Library -- Thread-Safe Constructs

- [ ] **Use the Executor framework** (`java.util.concurrent.Executor`, `Executors.newFixedThreadPool()`) instead of hand-rolling thread management -- it pools threads, resizes automatically, and recreates threads if necessary
- [ ] **Use `Callable<T>` instead of `Runnable`** when threads need to return a value
- [ ] **Use `Future<T>`** for executing multiple independent operations concurrently and waiting for results -- submit a Callable to an ExecutorService, continue local processing, then call `result.get()` to block until the future completes
- [ ] **Use nonblocking atomic classes** (`AtomicBoolean`, `AtomicInteger`, `AtomicReference`, etc.) instead of `synchronized` for simple value updates -- they use Compare and Swap (CAS) which is analogous to optimistic locking and nearly always faster than synchronized (pessimistic locking)
- [ ] **CAS operation pattern**: read current value, attempt swap only if value hasn't changed since read; if another thread changed it, retry -- this avoids locking entirely; the CAS operation itself is atomic at the processor level
- [ ] **CAS pseudocode is understood**: `do { currentValue = variableBeingSet } while(currentValue != compareAndSwap(currentValue, newValue))` -- the `compareAndSwap` method checks if the variable still holds `currentValue`; if yes, sets to `newValue` and returns `currentValue` (loop ends); if no, returns the changed value (loop retries)
- [ ] **Recognize inherently non-thread-safe classes** and guard them:
  - `SimpleDateFormat`
  - Database connections
  - Containers in `java.util` (HashMap, ArrayList, etc.)
  - Servlets
- [ ] **Individual methods being thread-safe does NOT mean multi-method sequences are safe** -- e.g., `containsKey()` + `put()` on a HashTable is NOT atomic even though each method is synchronized individually
- [ ] **Use `java.util.concurrent` collections** (`ConcurrentHashMap`, etc.) which provide compound atomic operations like `putIfAbsent()`

### 4. Dependencies Between Methods Can Break Concurrent Code

- [ ] **Check for check-then-act patterns across synchronized methods** -- when a client calls `hasNext()` then `next()` on a shared iterator, another thread can interleave between those calls
- [ ] **Three resolution strategies are evaluated:**

  **a. Tolerate the Failure:**
  - Catch the exception and handle it gracefully
  - Acceptable only when the failure causes no real harm
  - Considered sloppy -- like "cleaning up memory leaks by rebooting at midnight"

  **b. Client-Based Locking:**
  - Each client wraps the multi-method call sequence in a `synchronized` block on the shared object
  - Example: `synchronized(iterator) { if(!iterator.hasNext()) break; nextValue = iterator.next(); }`
  - Downside: violates DRY (every client must duplicate the locking code)
  - Risky: all programmers must remember to lock, and a single missed lock in hundreds of places causes intermittent failures
  - Client-based locking is fragile and error-prone at scale

  **c. Server-Based Locking (PREFERRED):**
  - Change the server/class to provide a single atomic method that combines the check-and-act: e.g., `getNextOrNull()` that is `synchronized` and returns `null` when exhausted
  - Client code becomes simpler: `while((value = iterator.getNextOrNull()) != null) { ... }`
  - Advantages over client-based locking:
    - Reduces repeated code -- clients do not write locking logic
    - Allows better performance -- can swap thread-safe server for non-thread-safe in single-threaded deployment
    - Reduces possibility of error -- only one place to get locking right
    - Enforces a single policy -- in the server, not scattered across clients
    - Reduces scope of shared variables -- clients unaware of locking internals
  - If you do not own the server code, use an ADAPTER to wrap it with a thread-safe API (e.g., `ThreadSafeIntegerIterator` wrapping `IntegerIterator` with a `synchronized getNextOrNull()` that internally calls `hasNext()` + `next()`)
  - Note: the `Iterator` interface is inherently not thread-safe -- it was never designed to be used by multiple threads

### 5. Increasing Throughput -- Correct Concurrent Design

- [ ] **Synchronized sections are as small as possible** -- keep the critical section to the minimum necessary code, synchronize as little as possible
- [ ] **I/O-bound work benefits from threading** -- while one thread waits on I/O (network, disk), other threads can use the CPU
- [ ] **CPU-bound work does NOT benefit from adding threads beyond available cores** -- adding threads to a processor-bound problem will not make it go faster
- [ ] **Throughput calculation is understood:**
  - Single-thread for N pages: `(I/O_time + processing_time) * N` (e.g., 1.5s * N)
  - Multi-thread with 3 threads: can overlap I/O wait with processing, achieving up to 3x throughput for I/O-bound work (e.g., 2 pages/second instead of 0.67)
- [ ] **Shared iterators/generators used by multiple threads have their `synchronized` block kept minimal** -- only the next-item retrieval is synchronized, not the processing of that item
- [ ] **The PageReader/PageIterator pattern is understood** -- `PageReader` retrieves a page's contents given a URL (I/O-bound); `PageIterator` wraps the URL iterator with a `synchronized getNextPageOrNull()` method that only synchronizes the iterator access (hasNext + next), NOT the page retrieval itself; each thread gets its own `PageReader` instance while sharing the `PageIterator`
- [ ] **Single-thread vs. multi-thread throughput math**: with 1s I/O + 0.5s processing per page, single-thread processes N pages in 1.5s * N; with 3 threads the processor-bound parsing overlaps with I/O-bound page retrieval, achieving ~2 pages/second (3x improvement) because each 1-second I/O wait is overlapped with two 0.5-second parses

### 6. Deadlock -- Four Required Conditions

All four of these conditions must hold simultaneously for deadlock to occur. Breaking ANY ONE prevents deadlock.

- [ ] **Condition 1: Mutual Exclusion** -- resources cannot be used by multiple threads simultaneously and are limited in number (e.g., database connections, file locks, semaphores)
- [ ] **Condition 2: Lock & Wait** -- once a thread acquires a resource, it holds it while waiting to acquire additional resources, never releasing what it has
- [ ] **Condition 3: No Preemption** -- one thread cannot forcibly take resources from another thread; the holder must voluntarily release
- [ ] **Condition 4: Circular Wait (Deadly Embrace)** -- Thread T1 holds Resource R1 and needs R2; Thread T2 holds R2 and needs R1, forming a cycle
- [ ] **The concrete deadlock scenario is understood** -- a web app with a pool of 10 DB connections and a pool of 10 MQ connections; "create" acquires MQ then DB, "update" acquires DB then MQ; if 10 users hit "create" (all 10 MQ connections acquired, waiting for DB) and 10 users hit "update" (all 10 DB connections acquired, waiting for MQ) simultaneously, the system deadlocks and never recovers
- [ ] **The debugging paradox is recognized** -- adding debug/logging statements to diagnose a deadlock changes the timing enough to make the deadlock "disappear," only for it to reappear months later in a different situation; this makes deadlocks extremely hard to reproduce and fix

### 7. Deadlock Prevention -- Breaking Each Condition

- [ ] **Breaking Mutual Exclusion:**
  - Use resources that allow simultaneous access (e.g., `AtomicInteger` instead of synchronized int)
  - Increase resource pool sizes to equal or exceed the number of competing threads
  - Check that all needed resources are free before seizing any
  - Limitation: most resources are inherently limited and do not allow simultaneous use

- [ ] **Breaking Lock & Wait:**
  - Refuse to wait: check each resource before seizing; if any resource is busy, release ALL held resources and start over
  - Potential problems:
    - **Starvation**: a thread with a rare combination of resources may never acquire them all
    - **Livelock**: threads repeatedly acquire one resource, find the next busy, release, and retry in lockstep -- causes high but useless CPU utilization
  - This is a last-resort strategy: inefficient but can always be implemented

- [ ] **Breaking Preemption:**
  - Allow threads to request resources from other threads; if the owner is also waiting, it releases all its resources and starts over
  - Similar to breaking Lock & Wait but with the benefit that a thread CAN wait for a resource (reducing restarts)
  - Tricky to manage all the request/release negotiations

- [ ] **Breaking Circular Wait (MOST COMMON APPROACH):**
  - Establish a global ordering of all resources; all threads must acquire resources in that same order
  - Example: if Thread 1 wants R1 and R2, and Thread 2 wants R2 and R1, force BOTH to acquire R1 first, then R2 -- circular wait becomes impossible
  - Trade-offs:
    - Acquisition order may not match usage order, so a resource acquired first might be locked longer than necessary
    - Sometimes ordering is not possible if the identity of the second resource depends on operations performed on the first

- [ ] **General deadlock prevention principle**: Isolate the thread-related part of your solution to allow for tuning and experimentation -- TANSTAAFL (There Ain't No Such Thing As A Free Lunch)

### 8. Testing Multithreaded Code

- [ ] **Concurrency bugs are extremely hard to reproduce** -- they may have a cross-section so small they occur once in a billion opportunities
- [ ] **A test that runs N iterations may need millions or hundreds of millions of iterations to expose a threading bug** -- even with loop count of 1,000,000, a bug may appear only once in 10 executions
- [ ] **The test pattern for proving threading bugs:**
  1. Record the current value of the shared state
  2. Create two (or more) threads that both invoke the concurrent operation
  3. Start all threads, then join (wait for all to complete)
  4. Verify the final state matches the expected result
  5. Loop this many times -- if the result EVER differs from expected, threading is broken
  6. If the loop completes without finding a discrepancy, the test has FAILED to prove the bug (not that the bug doesn't exist)

- [ ] **Monte Carlo Testing:**
  - Make tests flexible/tunable (parameterize iteration counts, thread counts, etc.)
  - Run the test repeatedly on a continuous integration server, randomly varying tuning values
  - If the test EVER fails, the code is broken
  - Log the exact conditions under which failure occurred for reproduction
  - Start writing and running these tests early

- [ ] **Run on every target deployment platform** -- a test tuned to fail on one machine/OS/JVM may need different values on another

- [ ] **Run under varying loads** -- simulate production-like loads if possible; concurrency bugs often appear only under stress

- [ ] **Accept the hard truth** -- even with all of the above, you still have a low chance of finding all threading problems; the most insidious bugs have occurrence rates of one-in-a-billion

### 9. Tool Support for Testing Thread-Based Code

- [ ] **Use instrumentation tools** (e.g., IBM ConTest or equivalent for your platform) that make non-thread-safe code fail faster by inserting context-switch points
- [ ] **Instrumented code dramatically increases failure detection** -- from one failure in 10 million iterations to one failure in ~30 iterations in the ConTest example; specific loop values after instrumentation: 13, 23, 0, 54, 16, 14, 6, 69, 107, 49, 2 (i.e., the bug was found within the first few dozen iterations every time)
- [ ] **Process for tool-assisted testing:**
  1. Write tests specifically designed to simulate multiple users under varying loads
  2. Instrument both test and production code with the threading tool
  3. Run the tests
- [ ] **Even without specialized tools, consider adding `Thread.yield()` or `Thread.sleep(0)` calls in development builds** at strategic points to increase the chance of exposing interleavings

## Violations to Detect

### Critical Violations

| ID | Violation | What to Look For |
|----|-----------|------------------|
| CA-01 | **Unbounded thread creation** | Server creates `new Thread()` for every request without any pool or limit; can exhaust JVM/OS under load |
| CA-02 | **Mixed threading responsibilities** | A single class/method handles socket management AND client processing AND threading policy AND shutdown -- violates SRP |
| CA-03 | **Non-atomic operations on shared mutable state** | `++`, `--`, `+=`, check-then-act (`if(x) then modify(x)`) on fields accessed by multiple threads without synchronization |
| CA-04 | **Assuming `++` is atomic** | Pre/post-increment compiles to multiple bytecode instructions (GETFIELD, IADD, PUTFIELD) that can be interleaved |
| CA-05 | **64-bit assignment assumed atomic** | Assignment to `long` or `double` fields shared between threads without synchronization; JVM spec does not guarantee atomicity |
| CA-06 | **Multi-method sequences on shared objects without external synchronization** | Calling `hasNext()` then `next()`, or `containsKey()` then `put()` on a shared object -- each call is atomic but the pair is not |
| CA-07 | **Deadlock-prone resource acquisition** | Two or more threads acquiring multiple shared resources in different orders (circular wait) |
| CA-08 | **All four deadlock conditions present** | Code has mutual exclusion + lock & wait + no preemption + potential circular wait with no mitigation strategy |
| CA-09 | **Using non-thread-safe classes in concurrent context** | `SimpleDateFormat`, `java.util.HashMap/ArrayList`, database connections, servlets used across threads without protection |
| CA-10 | **Client-based locking relied upon at scale** | Dozens or hundreds of call sites must all remember to lock the same shared resource -- a single missed lock causes intermittent failures |

### Moderate Violations

| ID | Violation | What to Look For |
|----|-----------|------------------|
| CA-11 | **Hand-rolled thread management instead of Executor framework** | Creating and managing threads manually when `ExecutorService` / `Executors.newFixedThreadPool()` would be cleaner |
| CA-12 | **Synchronized where AtomicInteger/AtomicBoolean would suffice** | Using `synchronized` blocks for simple counter increments or boolean flags when lock-free atomic classes perform better via CAS |
| CA-13 | **Over-broad synchronized blocks** | Synchronizing an entire method or large block when only a small critical section needs protection -- reduces throughput unnecessarily |
| CA-14 | **Threading added to CPU-bound work expecting speedup** | Adding threads will not speed up processor-bound operations; it only helps I/O-bound work where threads can overlap I/O waits |
| CA-15 | **No concurrency tests exist** | Concurrent code with zero tests specifically designed to expose threading bugs through repeated execution with multiple threads |
| CA-16 | **Concurrency tests with insufficient iterations** | Tests that run only a few hundred iterations will almost never catch threading bugs that manifest once in millions of executions |
| CA-17 | **Missing `volatile` on shutdown flags** | Boolean fields like `keepProcessing` used to signal thread shutdown must be `volatile` to ensure visibility across threads |
| CA-18 | **Server-based locking not considered first** | Defaulting to client-based locking or tolerating failures instead of providing atomic compound operations in the server/class itself |

### Design Smells

| ID | Violation | What to Look For |
|----|-----------|------------------|
| CA-19 | **No threading abstraction / interface** | Threading strategy is hardcoded rather than behind an interface that can be swapped (e.g., `ClientScheduler` pattern) |
| CA-20 | **Concurrency not isolated for testing** | Threading code is entangled with business logic, making it impossible to test threading behavior independently or swap strategies |
| CA-21 | **No throughput validation test** | No performance/throughput test that asserts the system completes work within an acceptable time bound (e.g., `@Test(timeout=10000)`) |
| CA-22 | **No instrumentation for concurrency testing** | Not using tools like ConTest (or equivalent) to instrument code and increase the probability of detecting thread interleavings |
| CA-23 | **Debugging concurrency with log/print statements** | Adding debug output to diagnose threading issues changes timing enough to make the bug disappear (the debugging paradox); use instrumentation tools like ConTest instead |

## How to Fix

### Fix: Unbounded Thread Creation (CA-01)
```
// BEFORE: unbounded
void process(final Socket socket) {
    new Thread(() -> handleClient(socket)).start();
}

// AFTER: bounded thread pool via Executor
ExecutorService executor = Executors.newFixedThreadPool(MAX_THREADS);
void process(final Socket socket) {
    executor.execute(() -> handleClient(socket));
}
```

### Fix: Mixed Threading Responsibilities (CA-02)
```
// BEFORE: everything in one class
public void run() {
    while (keepProcessing) {
        Socket socket = serverSocket.accept();
        new Thread(() -> {
            String msg = MessageUtils.getMessage(socket);
            MessageUtils.sendMessage(socket, "Processed: " + msg);
        }).start();
    }
}

// AFTER: separated responsibilities
public void run() {
    while (keepProcessing) {
        ClientConnection conn = connectionManager.awaitClient();
        ClientRequestProcessor processor = new ClientRequestProcessor(conn);
        clientScheduler.schedule(processor);  // threading policy isolated
    }
    connectionManager.shutdown();
}

// Threading policy is swappable via interface
public interface ClientScheduler {
    void schedule(ClientRequestProcessor requestProcessor);
}

// Thread-per-request implementation
public class ThreadPerRequestScheduler implements ClientScheduler {
    public void schedule(final ClientRequestProcessor requestProcessor) {
        Runnable runnable = new Runnable() {
            public void run() { requestProcessor.process(); }
        };
        Thread thread = new Thread(runnable);
        thread.start();
    }
}
```

Note: The book's full server listing uses `volatile boolean keepProcessing = true;` -- the `volatile` keyword ensures the shutdown flag is visible across threads.

### Fix: Non-Atomic Increment (CA-03, CA-04)
```
// BEFORE: not thread-safe
public class IdGenerator {
    int lastIdUsed;
    public int incrementValue() {
        return ++lastIdUsed;  // 8 bytecode instructions, NOT atomic
    }
}

// AFTER option 1: synchronized
public class IdGenerator {
    int lastIdUsed;
    public synchronized int incrementValue() {
        return ++lastIdUsed;
    }
}

// AFTER option 2: AtomicInteger (preferred -- nonblocking, faster)
public class IdGenerator {
    private AtomicInteger lastIdUsed = new AtomicInteger(0);
    public int incrementValue() {
        return lastIdUsed.incrementAndGet();
    }
}
```

### Fix: Multi-Method Sequence on Shared Object (CA-06)
```
// BEFORE: check-then-act is NOT atomic
if (!hashTable.containsKey(someKey)) {
    hashTable.put(someKey, new SomeValue());
}

// AFTER option 1: client-based locking (acceptable but fragile)
synchronized (map) {
    if (!map.containsKey(key))
        map.put(key, value);
}

// AFTER option 2: server-based locking via ADAPTER (better)
public class WrappedHashtable<K, V> {
    private Map<K, V> map = new Hashtable<>();
    public synchronized void putIfAbsent(K key, V value) {
        if (!map.containsKey(key))
            map.put(key, value);
    }
}

// AFTER option 3: use concurrent collections (best)
ConcurrentHashMap<Integer, String> map = new ConcurrentHashMap<>();
map.putIfAbsent(key, value);
```

### Fix: Iterator Shared Between Threads (CA-06, CA-18)
```
// BEFORE: two synchronized methods, but client uses both -- not safe
public class IntegerIterator implements Iterator<Integer> {
    private Integer nextValue = 0;
    public synchronized boolean hasNext() { return nextValue < 100000; }
    public synchronized Integer next() {
        if (nextValue == 100000) throw new IteratorPastEndException();
        return nextValue++;
    }
}
// Client (BROKEN under concurrency):
while (iterator.hasNext()) {
    int val = iterator.next();  // Thread can interleave between hasNext and next
}

// AFTER: server-based locking with atomic compound method
public class IntegerIteratorServerLocked {
    private Integer nextValue = 0;
    public synchronized Integer getNextOrNull() {
        if (nextValue < 100000)
            return nextValue++;
        else
            return null;
    }
}
// Client (safe):
Integer val;
while ((val = iterator.getNextOrNull()) != null) {
    doSomethingWith(val);
}
```

### Fix: Adapter for Thread-Safe Wrapper When You Don't Own the Server (CA-06, CA-18)
```
// When you cannot modify IntegerIterator, wrap it with an ADAPTER
public class ThreadSafeIntegerIterator {
    private IntegerIterator iterator = new IntegerIterator();

    public synchronized Integer getNextOrNull() {
        if (iterator.hasNext())
            return iterator.next();
        return null;
    }
}
```

### Fix: Minimal Synchronized Block in Shared Iterator (CA-13)
```
// PageIterator: synchronized block covers ONLY the iterator access, not the I/O
public class PageIterator {
    private PageReader reader;
    private URLIterator urls;

    public synchronized String getNextPageOrNull() {
        if (urls.hasNext())
            return getPageFor(urls.next());  // I/O happens inside sync -- see note
        else
            return null;
    }

    public String getPageFor(String url) {
        return reader.getPageFor(url);  // Each thread has its own PageReader
    }
}
// Note: In the book's example, getPageFor is called inside the synchronized
// method for simplicity. In production, you'd want to extract the URL inside
// the sync block and do the I/O outside it for maximum concurrency.
```

### Fix: Deadlock via Circular Wait (CA-07, CA-08)
```
// BEFORE: deadlock-prone -- different acquisition orders
// Thread 1 (create): acquires DB connection, then MQ connection
// Thread 2 (update): acquires MQ connection, then DB connection

// AFTER: enforce global resource ordering
// ALL threads acquire DB connection first, then MQ connection
// This breaks circular wait and makes deadlock impossible
```

### Fix: Concurrency Testing (CA-15, CA-16)
```
// The class under test (from the book):
public class ClassWithThreadingProblem {
    int nextId;
    public int takeNextId() {
        return nextId++;  // Post-increment is NOT atomic
    }
}

// Pattern for testing threading bugs:
@Test
public void twoThreadsShouldFailEventually() throws Exception {
    final ClassWithThreadingProblem instance = new ClassWithThreadingProblem();
    Runnable runnable = () -> { instance.takeNextId(); };

    for (int i = 0; i < 50000; ++i) {
        int startingId = instance.lastId;
        int expectedResult = 2 + startingId;

        Thread t1 = new Thread(runnable);
        Thread t2 = new Thread(runnable);
        t1.start(); t2.start();
        t1.join();  t2.join();

        int endingId = instance.lastId;
        if (endingId != expectedResult)
            return;  // Proved the code is broken
    }
    fail("Should have exposed a threading issue but it did not.");
}
```

### Fix: CAS Pseudocode -- How Nonblocking Works (CA-12)
```
// Logical equivalent of what the VM does atomically at the processor level
int variableBeingSet;

void simulateNonBlockingSet(int newValue) {
    int currentValue;
    do {
        currentValue = variableBeingSet;
    } while (currentValue != compareAndSwap(currentValue, newValue));
}

int synchronized compareAndSwap(int currentValue, int newValue) {
    if (variableBeingSet == currentValue) {
        variableBeingSet = newValue;
        return currentValue;  // Success: loop ends
    }
    return variableBeingSet;  // Fail: another thread changed it, retry
}
```

### Fix: Using Futures for Concurrent Independent Work (CA-11)
```
// Execute two independent operations concurrently
public String processRequest(String message) throws Exception {
    Callable<String> makeExternalCall = () -> {
        // make external request
        return result;
    };

    Future<String> result = executorService.submit(makeExternalCall);
    String partialResult = doSomeLocalProcessing();  // runs in parallel
    return result.get() + partialResult;  // blocks until future completes
}
```

## Self-Improvement Protocol

After each review, update your mental model with answers to these questions:

1. **Shared State Audit**: Have I identified every shared mutable variable? Do I know every thread that can access each one? What bytecode operations does each access compile to?

2. **Execution Path Awareness**: For N bytecode instructions and T threads, have I considered that there are (N*T)! / N!^T possible interleavings? Even a single `++` on a shared int has 12,870 paths for 2 threads.

3. **Library Fitness**: Am I using the strongest available concurrency primitive? Prefer `ConcurrentHashMap.putIfAbsent()` over synchronized wrapper over client-based locking over tolerating failure.

4. **Deadlock Analysis**: For every pair of resources acquired by different threads, trace the acquisition order. Can a cycle form? Which of the four conditions can be broken most cheaply?

5. **Locking Strategy**: Am I defaulting to server-based locking? If client-based locking exists, count how many call sites must get it right. One missed lock means intermittent production failures.

6. **Test Sufficiency**: Are concurrency tests running millions of iterations? Are they running on all target platforms? Under varying loads? Are they instrumented with tools that increase interleaving probability? A test that passes does not mean the code is correct -- it may mean the test is inadequate.

7. **Responsibility Separation**: Is ALL threading code in exactly one place? Can I change from thread-per-request to a thread pool to an Executor framework by modifying one class? If not, threading concerns are leaking into business logic.

8. **Performance Model**: Is the bottleneck I/O or CPU? If I/O-bound, concurrency helps. If CPU-bound, adding threads beyond core count hurts. Have I measured which one it is?
