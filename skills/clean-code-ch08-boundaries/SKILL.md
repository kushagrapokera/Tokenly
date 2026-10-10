---
name: clean-code-ch08-boundaries
description: "Code quality checker based on Clean Code Ch8: Boundaries — checks third-party wrapping, learning tests, boundary interfaces, adapter patterns, external dependency isolation. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 8: Boundaries -- Code Quality Checker

*Chapter by James Grenning*

## Core Principle

We seldom control all the software in our systems. Whether third-party packages, open source libraries, or subsystems built by other teams, we must cleanly integrate foreign code with our own. Code at the boundaries needs clear separation and tests that define expectations. It is better to depend on something *you* control than on something you don't control, lest it end up controlling you.

Good software designs accommodate change without huge investments and rework. When we use code that is out of our control, special care must be taken to protect our investment and make sure future change is not too costly. We manage third-party boundaries by having very few places in the code that refer to them -- we wrap them or use an ADAPTER to convert from our perfect interface to the provided interface. Either way our code speaks to us better, promotes internally consistent usage across the boundary, and has fewer maintenance points when the third-party code changes.

Learning the third-party code is hard. Integrating the third-party code is hard too. Doing both at the same time is doubly hard. Instead of experimenting in production code, we write learning tests (a term coined by Jim Newkirk) to explore our understanding of the third-party code in isolation.

## When to Use

Apply this checker whenever code:
- Imports, wraps, or calls any third-party library, framework, or external SDK
- Depends on an API provided by another team or subsystem (internal or external)
- Uses broad/powerful interfaces (maps, collections, generic containers) that are passed across module boundaries
- Integrates with a dependency whose API may change across versions
- Interfaces with code that does not yet exist (another team has not finished defining their API)
- Introduces a new third-party dependency for the first time
- Upgrades a third-party dependency to a new major version
- Passes framework-specific types (ORM entities, HTTP request objects, SDK response types) through multiple layers of the application

## Checklist

### 1. Third-Party Interface Wrapping
- [ ] Broad third-party interfaces (e.g., `Map`, `List`, generic collections, ORM session objects) are NOT passed around freely through the system
- [ ] If a boundary interface like `Map` is used, it is kept inside a single class or a close family of classes -- never returned from or accepted as an argument to public APIs
- [ ] Wrapper classes expose only the methods the application actually needs (tailored, constrained interface)
- [ ] Wrapper classes hide implementation details such as generics, casting, and type management from the rest of the application
- [ ] Wrapper classes can enforce design and business rules that the raw third-party interface cannot
- [ ] Changes to the third-party interface (e.g., generics added to `Map` in Java 5) affect only the wrapper, not the entire codebase

### 2. Learning Tests (Exploring and Learning Boundaries)
- [ ] It is recognized that while it's not our job to test the third-party code, it may be in our best interest to write tests for the third-party code we use
- [ ] When a new third-party library is introduced, learning tests exist that exercise the API as the application intends to use it
- [ ] Learning tests are controlled experiments that verify our understanding of the third-party API -- they focus on what we want out of the API
- [ ] Learning tests are run against new releases of third-party packages to detect behavioral differences early
- [ ] Learning tests serve as living documentation of how the third-party API actually works, including its quirks and inconsistencies
- [ ] Once the third-party API is understood through learning tests, that knowledge is encapsulated into our own boundary class so the rest of the application is isolated from the third-party boundary interface
- [ ] Even if learning tests are not written, boundary tests exist that exercise the third-party interface the same way the production code does

### 3. Adapter Pattern for Undefined/Evolving APIs
- [ ] When the API on the other side of a boundary is unknown or not yet defined, an interface is defined that represents what we *wish* the API looked like
- [ ] The wished-for interface is under our control, keeping client code readable and focused on intent
- [ ] An ADAPTER is written to bridge the gap once the actual API is defined, encapsulating interaction with the real API in a single place
- [ ] A Fake implementation of the wished-for interface exists for testing, providing a convenient seam
- [ ] The Adapter is the single place to change when the external API evolves

### 4. Dependency Isolation and Minimizing Boundary Contact Points
- [ ] Third-party code is referenced in as few places as possible throughout the codebase
- [ ] Boundary code is clearly separated from the rest of the application logic
- [ ] The application does not let too much of its code know about third-party particulars
- [ ] Either wrapping or the ADAPTER pattern is used so that our code speaks to us better, promotes internally consistent usage, and has fewer maintenance points when the third-party code changes

### 5. Boundary Test Coverage
- [ ] Outbound boundary tests exist that exercise the interface the same way production code does
- [ ] Tests verify expected behavior survives third-party upgrades
- [ ] Without these boundary tests, the team might be tempted to stay with the old version longer than they should

## Violations to Detect

### V1: Raw Third-Party Type Leakage (from "Using Third-Party Code")
**Pattern:** A broad third-party interface (Map, List, Set, DataFrame, ORM Session, HTTP Client, SDK response object) is passed as a parameter, returned from a method, or stored in a public field across module boundaries.
**Why it is harmful:** Every consumer gains full power of the interface (e.g., `clear()`, `remove()`, unrestricted `put()`). The provider's intent (e.g., "read-only access" or "only Sensor objects allowed") cannot be enforced. If the third-party interface changes (like Java adding generics to Map), every usage site must be updated.
**Book example:** `Map sensors` passed around freely -- any user could call `sensors.clear()` or insert wrong types. Fix: `Sensors` wrapper class with `getById(String id)` returning only `Sensor` objects.
**Detection:**
- Public methods accepting or returning raw third-party collection/container types
- Third-party SDK types appearing in method signatures across package boundaries
- The same cast (e.g., `(Sensor) sensors.get(id)`) repeated throughout the codebase

### V2: No Wrapper Around Broad Interface (from "Using Third-Party Code")
**Pattern:** A powerful, general-purpose interface is used directly everywhere instead of being encapsulated in a domain-specific class.
**Why it is harmful:** The interface provides more capability than needed. Type safety and business rules cannot be enforced. Coupling to the third-party interface spreads across the entire codebase.
**Book example:** `Map<Sensor> sensors` used directly -- still exposes `clear()`, `putAll()`, etc. Better: `Sensors` class with `private Map sensors = new HashMap()` and only `getById(String id)` exposed.
**Detection:**
- Generic collections used directly in business logic without a domain wrapper
- Multiple modules importing and using the same third-party type directly
- Business rules about the collection (what can be added, who can delete) enforced by convention rather than by the type system

### V3: Missing Learning Tests (from "Exploring and Learning Boundaries" and "Learning log4j")
**Pattern:** A third-party library is integrated into production code without any tests that verify our understanding of how it behaves.
**Why it is harmful:** Learning the third-party code is hard. Integrating the third-party code is hard too. Doing both at the same time is doubly hard. Without learning tests, we might spend a day or two (or more) reading documentation and deciding how to use it, then write our code to use the third-party code and see whether it does what we think. We would not be surprised to find ourselves bogged down in long debugging sessions trying to figure out whether the bugs we are experiencing are in our code or theirs. When the third-party package releases a new version, we have no automated way to detect behavioral changes that break our usage.
**Book example:** The log4j learning journey -- instead of experimenting in production code, the team wrote incremental test cases (`testLogCreate`, `testLogAddAppender`, etc.) that explored the API step by step, discovering quirks like the "unconfigured" default `ConsoleAppender` constructor that feels like a bug or inconsistency. This culminated in `LogTest.java` (Listing 8-1) which encoded all their knowledge as a simple test suite. They then encapsulated that knowledge into their own logger class so the rest of the application was isolated from the log4j boundary interface.
**Detection:**
- Third-party library used in production with no corresponding test that exercises the library's API directly
- Integration bugs that required debugging sessions to determine if the issue was in our code or the library
- No tests that run against upgraded versions of dependencies to verify compatibility

### V4: Missing Boundary Tests for Third-Party Upgrades (from "Learning Tests Are Better Than Free")
**Pattern:** Third-party dependencies are upgraded without running tests that verify our specific usage patterns still work.
**Why it is harmful:** Learning tests verify that the third-party packages we are using work the way we expect them to. Once integrated, there are no guarantees that the third-party code will stay compatible with our needs. The original authors will have pressures to change their code to meet new needs of their own. They will fix bugs and add new capabilities. With each release comes new risk. If the third-party package changes in some way incompatible with our tests, we will find out right away -- but only if those tests exist.
**Book example:** "Whether you need the learning provided by the learning tests or not, a clean boundary should be supported by a set of outbound tests that exercise the interface the same way the production code does. Without these *boundary tests* to ease the migration, we might be tempted to stay with the old version longer than we should."
**Detection:**
- Dependency version pinned for a long time with no tests validating behavior
- Upgrade PRs that include no test changes or boundary test runs
- History of breakage after dependency upgrades

### V5: No Adapter for Undefined or Volatile APIs (from "Using Code That Does Not Yet Exist")
**Pattern:** Code directly depends on an external API that is not yet defined, is unstable, or is controlled by another team, without an insulating layer. This is another kind of boundary -- one that separates the known from the unknown. There are often places in the code where our knowledge seems to drop off the edge; sometimes what is on the other side of the boundary is unknowable (at least right now).
**Why it is harmful:** Development is blocked waiting for the other team. When the API is finally defined (or changes), modifications ripple through the entire codebase. Testing is difficult because there is no seam to inject fakes.
**Book example:** The "Transmitter" subsystem in a radio communications system. The team knew little about it, and the people responsible for the subsystem had not gotten to the point of defining their interface. The team did not want to be blocked, so they started their work far away from the unknown part of the code. They defined their own `Transmitter` interface with a `transmit(frequency, stream)` method -- the interface they *wished* they had. `CommunicationsController` depended on this interface. A `FakeTransmitter` was used for testing. When the real Transmitter API was finally defined, a `TransmitterAdapter` was written to bridge the gap in a single place. They could also create boundary tests once they had the `TransmitterAPI` to make sure they were using the API correctly.
**Detection:**
- Code that directly calls an API known to be in flux or not yet finalized
- TODO comments like "waiting for Team X to finalize API"
- No interface/adapter separating our code from the external dependency
- Inability to test a module because it depends directly on an unavailable external system
- Multiple modules importing an unstable API type directly

### V6: Tension Between Provider and User Not Managed (from "Using Third-Party Code")
**Pattern:** The natural tension between interface providers (who want broad applicability) and interface users (who want focused, specific interfaces) is not acknowledged or managed.
**Why it is harmful:** Providers strive for broad applicability to appeal to a wide audience. Users want an interface focused on their particular needs. This tension causes problems at the boundaries of our systems when the broad interface is used as-is.
**Detection:**
- Using a framework's generic base classes directly in domain code without narrowing the interface
- Exposing SDK-specific configuration objects throughout the application
- Domain logic that must understand framework-specific concepts

## How to Fix

### Fix 1: Wrap Third-Party Interfaces in Domain-Specific Classes
The book shows a three-stage progression from worst to best:

**Stage 1 -- Raw Map, no generics (worst):**
```java
Map sensors = new HashMap();
// Passed around freely. Cast required at every access point:
Sensor s = (Sensor) sensors.get(sensorId);
// This cast appears "over and over again throughout the code"
```

**Stage 2 -- Generics improve readability but do not solve the real problem:**
```java
Map<Sensor> sensors = new HashMap<Sensor>();
Sensor s = sensors.get(sensorId);
// Cleaner, but Map<Sensor> still provides more capability than we need or want.
// Passing Map<Sensor> liberally means many places to fix if Map interface changes.
// Systems were "inhibited from using generics because of the sheer magnitude of
// changes needed to make up for the liberal use of Maps."
```

**Stage 3 -- Domain wrapper class (clean boundary):**
```java
public class Sensors {
    private Map sensors = new HashMap();

    public Sensor getById(String id) {
        return (Sensor) sensors.get(id);
    }
    // Only expose what the application needs
    // Generics, casting, type management hidden inside
    // Can enforce business rules
}
```
**Principle:** The interface at the boundary (Map) is hidden. It can evolve with very little impact on the rest of the application. The use of generics is no longer a big issue because the casting and type management is handled inside the Sensors class. No user of Sensors would care one bit if generics were used or not -- that choice has become (and always should be) an implementation detail. The interface is tailored and constrained to meet the needs of the application -- easier to understand, harder to misuse. The Sensors class can enforce design and business rules.

**Important caveat from the book:** "We are not suggesting that every use of Map be encapsulated in this form. Rather, we are advising you not to pass Maps (or any other interface at a boundary) around your system. If you use a boundary interface like Map, keep it inside the class, or close family of classes, where it is used. Avoid returning it from, or accepting it as an argument to, public APIs."

### Fix 2: Write Learning Tests When Adopting Third-Party Code
**Approach:**
1. Write a simple test calling the API as you expect to use it
2. When it fails, learn why (missing configuration, unexpected behavior)
3. Refine with more tests, each testing a specific aspect
4. End result: a test suite that encodes your understanding

**Full example from the book (log4j learning test journey):**

Step 1 -- Naive first attempt, expecting "hello" on the console. Fails with error telling us we need an `Appender`:
```java
@Test
public void testLogCreate() {
    Logger logger = Logger.getLogger("MyLogger");
    logger.info("hello");
}
```

Step 2 -- Add a `ConsoleAppender`. Discover the Appender has no output stream:
```java
@Test
public void testLogAddAppender() {
    Logger logger = Logger.getLogger("MyLogger");
    ConsoleAppender appender = new ConsoleAppender();
    logger.addAppender(appender);
    logger.info("hello");
}
```

Step 3 -- After Googling, try with `PatternLayout` and `SYSTEM_OUT`. This works, but it seems odd that we have to tell the `ConsoleAppender` that it writes to the console:
```java
@Test
public void testLogAddAppender() {
    Logger logger = Logger.getLogger("MyLogger");
    logger.removeAllAppenders();
    logger.addAppender(new ConsoleAppender(
            new PatternLayout("%p %t %m%n"),
            ConsoleAppender.SYSTEM_OUT));
    logger.info("hello");
}
```

Key discoveries during exploration:
- Removing the `ConsoleAppender.SystemOut` argument: "hello" is still printed
- Removing the `PatternLayout`: the logger complains about the lack of an output stream -- "very strange behavior"
- The default `ConsoleAppender` constructor is "unconfigured," which does not seem too obvious or useful -- "This feels like a bug, or at least an inconsistency, in log4j"

Step 4 -- Final encoded knowledge (Listing 8-1, LogTest.java). After more googling, reading, and testing, all knowledge is captured as simple unit tests:
```java
public class LogTest {
    private Logger logger;

    @Before
    public void initialize() {
        logger = Logger.getLogger("logger");
        logger.removeAllAppenders();
        Logger.getRootLogger().removeAllAppenders();
    }

    @Test
    public void basicLogger() {
        BasicConfigurator.configure();
        logger.info("basicLogger");
    }

    @Test
    public void addAppenderWithStream() {
        logger.addAppender(new ConsoleAppender(
            new PatternLayout("%p %t %m%n"),
            ConsoleAppender.SYSTEM_OUT));
        logger.info("addAppenderWithStream");
    }

    @Test
    public void addAppenderWithoutStream() {
        logger.addAppender(new ConsoleAppender(
            new PatternLayout("%p %t %m%n")));
        logger.info("addAppenderWithoutStream");
    }
}
```
**Result:** "Now we know how to get a simple console logger initialized, and we can encapsulate that knowledge into our own logger class so that the rest of our application is isolated from the log4j boundary interface."

**Principle:** The learning tests end up costing nothing -- we had to learn the API anyway, and writing those tests was an easy and isolated way to get that knowledge. They are precise experiments that helped increase our understanding. Not only are learning tests free, they have a positive return on investment: when there are new releases of the third-party package, we run the learning tests to see whether there are behavioral differences. They serve as living documentation of how the API actually works, including its quirks.

### Fix 3: Define the Interface You Wish You Had (Adapter Pattern)
**When the API does not yet exist or is volatile:**
1. Define an interface that represents what you *want* from the other side of the boundary
2. Write your application code against that wished-for interface
3. Create a Fake implementation for testing
4. When the real API is defined, write an Adapter that implements your interface and delegates to the real API

**Example from the book (Transmitter in a radio communications system):**

Context: The team was developing software for a radio communications system. There was a subsystem, the "Transmitter," that they knew little about, and the people responsible for the subsystem had not gotten to the point of defining their interface. The team did not want to be blocked, so they started their work far away from the unknown part of the code. They wanted to tell the transmitter something like: *"Key the transmitter on the provided frequency and emit an analog representation of the data coming from this stream."*

They defined their own interface -- called it `Transmitter`, gave it a method called `transmit` that took a frequency and a data stream. This was the interface they *wished* they had.

```
CommunicationsController --> <<interface>> Transmitter
                                  + transmit(frequency, stream)
                                    ^                ^
                                    |                |
                            FakeTransmitter    TransmitterAdapter --> <<future>> Transmitter API
```
(Figure 8-2: "Predicting the transmitter")

**Principle:** By using our own application-specific interface, we kept our `CommunicationsController` code clean and expressive. The interface is under our control, which helps keep client code more readable and focused on what it is trying to accomplish. Once the transmitter API was defined, the `TransmitterAdapter` was written to bridge the gap -- the ADAPTER encapsulated the interaction with the API and provides a single place to change when the API evolves. This design also gives us a very convenient seam in the code for testing: using a suitable `FakeTransmitter`, we can test the `CommunicationsController` classes. We can also create boundary tests once we have the `TransmitterAPI` that make sure we are using the API correctly.

### Fix 4: Write Boundary Tests That Mirror Production Usage
**Approach:**
- For every third-party integration, write tests that exercise the interface the same way production code does
- Run these tests as part of the CI pipeline, especially after dependency upgrades
- These tests ease migration to new versions and detect incompatibilities immediately

**Principle:** Without boundary tests, teams are tempted to stay with old versions longer than they should. The tests protect your investment and make sure future change is not too costly.

### Fix 5: Minimize Boundary Contact Points
**Approach:**
- Reference third-party code in as few places as possible
- Either wrap them (as with the Sensors/Map example) or use an Adapter (as with the Transmitter example)
- Either way, the code speaks to us better, promotes internally consistent usage across the boundary, and has fewer maintenance points when the third-party code changes

## Self-Improvement Protocol

After each boundary review, update your knowledge:

1. **Catalog boundary points:** For every third-party dependency in the project, note where it crosses the boundary into your code. Count the number of files that directly import/reference each third-party package.

2. **Measure boundary hygiene:**
   - How many public methods accept or return raw third-party types? (Target: zero outside wrapper/adapter classes)
   - How many files directly import each third-party package? (Target: minimize -- ideally 1-2 wrapper/adapter files per dependency)
   - Do learning tests or boundary tests exist for each third-party dependency? (Target: at least boundary tests for every dependency)
   - Are there interfaces/adapters for volatile or external-team APIs? (Target: yes for every cross-team or unstable dependency)

3. **Track upgrade safety:**
   - When was each dependency last upgraded?
   - Did boundary tests catch any incompatibilities during the last upgrade?
   - Are there dependencies pinned to old versions with no boundary tests? (These are migration risks)

4. **Detect new violations after code changes:**
   - Did a new import of a third-party package appear in a file that is not a wrapper or adapter?
   - Did a public method signature change to include a third-party type?
   - Was a new third-party dependency added without corresponding learning/boundary tests?
   - Is there a new cross-team API integration without an adapter layer?

5. **Apply the core heuristic from the chapter:**
   - "It's better to depend on something *you* control than on something you don't control, lest it end up controlling you."
   - For every boundary, ask: if the other side changes tomorrow, how many files in our codebase must change? If the answer is more than one or two, the boundary is not clean.
