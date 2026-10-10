---
name: clean-code-ch12-emergence
description: "Code quality checker based on Clean Code Ch12: Emergence (by Jeff Langr) — checks Kent Beck's 4 rules of Simple Design: all tests pass, no duplication, expressiveness, minimal classes/methods. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 12: Emergence (by Jeff Langr) — Code Quality Checker

## When to Use

Apply this skill whenever you are:
- Reviewing or writing code and need a high-level design quality framework
- Refactoring existing code and need to prioritize what to fix first
- Evaluating whether a system's design is "simple" by Kent Beck's definition
- Deciding between competing design approaches
- Checking if code follows emergent design principles that facilitate SRP, DIP, and other SOLID principles

The core premise: following four simple rules in priority order causes good designs to **emerge** naturally. You do not need to master every design principle upfront — adherence to these rules guides you toward SRP, DIP, low coupling, and high cohesion organically.

## Kent Beck's Four Rules of Simple Design (In Priority Order)

A design is "simple" if it:

1. **Runs all the tests** (HIGHEST PRIORITY)
2. **Contains no duplication**
3. **Expresses the intent of the programmer**
4. **Minimizes the number of classes and methods** (LOWEST PRIORITY)

The rules are listed in order of importance. Never sacrifice a higher-priority rule to satisfy a lower-priority one.

## Checklist

### Rule 1: Runs All the Tests
- [ ] The system is comprehensively tested and passes ALL tests ALL of the time
- [ ] The system is verifiable — a system that cannot be verified should never be deployed
- [ ] Classes are small and single-purpose (testability pushes toward SRP compliance)
- [ ] Coupling is loose — tight coupling makes testing difficult, so testable code naturally uses DIP, dependency injection, interfaces, and abstractions
- [ ] Following this simple rule continuously impacts adherence to the primary OO goals of low coupling and high cohesion
- [ ] Tests exist and are run continuously — "Writing tests leads to better designs."

### Rule 2: No Duplication (applied during refactoring)
> "Duplication is the primary enemy of a well-designed system. It represents additional work, additional risk, and additional unnecessary complexity."

- [ ] No lines of code that look exactly alike
- [ ] No lines of code that are similar but could be massaged to look alike and then refactored
- [ ] No duplication of implementation (e.g., two methods in a collection class that could share logic — `isEmpty()` should delegate to `size()` rather than tracking a separate boolean)
- [ ] Common code sequences are extracted into shared helper methods
- [ ] Higher-level structural duplication is eliminated via patterns like TEMPLATE METHOD
- [ ] "Reuse in the small" is practiced — extracting tiny commonalities into methods that may then be moved to other classes, elevating their visibility and reuse potential. "This 'reuse in the small' can cause system complexity to shrink dramatically. Understanding how to achieve reuse in the small is essential to achieving reuse in the large."

### Rule 3: Expressive
> "It's easy to write code that *we* understand, because at the time we write it we're deep in an understanding of the problem we're trying to solve. Other maintainers of the code aren't going to have so deep an understanding."

- [ ] Good names are chosen for classes and functions — you should not be surprised by a class's responsibilities when you hear its name
- [ ] Functions and classes are kept small — small things are easy to name, easy to write, and easy to understand
- [ ] Standard nomenclature is used — design pattern names (COMMAND, VISITOR, etc.) appear in class names that implement those patterns so other developers immediately understand the design
- [ ] Well-written unit tests serve as documentation by example — a primary goal of tests is to act as documentation by example; someone reading the tests should quickly understand what a class is all about
- [ ] **The most important way to be expressive is to *try*** — all too often we get code working and move on without giving sufficient thought to making it easy for the next person to read. Remember, the most likely next person to read the code will be you.
- [ ] The author took pride in their workmanship — spend a little time with each function and class, choose better names, split large functions into smaller functions, and generally take care of what you've created. "Care is a precious resource."

### Rule 4: Minimal Classes and Methods
- [ ] The overall system is kept small — not too many tiny classes and methods
- [ ] No pointless dogmatism: not every class needs an interface, not every system must separate fields from behavior into data classes and behavior classes
- [ ] Function and class counts are kept low as a pragmatic goal
- [ ] This rule is never used to justify violating rules 1-3 — it is the lowest priority

### Refactoring Safety Net
> *"The fact that we have these tests eliminates the fear that cleaning up the code will break it!"*

- [ ] Tests exist BEFORE refactoring begins — having tests eliminates the fear that cleaning up the code will break it
- [ ] After each few lines of code added, pause and reflect: did we just degrade the design?
- [ ] If yes, clean it up and run tests to demonstrate nothing is broken
- [ ] During refactoring, apply anything from the entire body of knowledge about good software design: increase cohesion, decrease coupling, separate concerns, modularize system concerns, shrink functions and classes, choose better names
- [ ] This is also where we apply the final three rules of simple design: eliminate duplication, ensure expressiveness, and minimize the number of classes and methods

## Violations to Detect

### Rule 1 Violations: Missing or Failing Tests
- **No tests exist** — the system cannot be verified
- **Tests do not pass** — broken tests are never acceptable
- **Partial test coverage** — untested code paths are unverifiable code paths
- **Untestable design** — classes are too large, too coupled, or have too many responsibilities to test easily
- **Tight coupling prevents testing** — no interfaces, no dependency injection, concrete dependencies everywhere

### Rule 2 Violations: Duplication
- **Exact duplicate code blocks** — identical lines of code in multiple locations
- **Similar code that could be unified** — sequences that differ only slightly and could be refactored to share a common implementation
- **Duplication of implementation** — two methods that independently implement the same concept when one could delegate to the other

  Bad — separate implementations:
  ```
  int size() {}
  boolean isEmpty() {}  // tracks its own boolean independently
  ```

  Good — isEmpty delegates to size:
  ```java
  boolean isEmpty() {
    return 0 == size();
  }
  ```

- **Duplicated disposal/cleanup sequences** — repeated multi-line patterns like dispose/gc/reassign that should be extracted

  Bad — duplicated cleanup in scaleToOneDimension and rotate:
  ```java
  public void scaleToOneDimension(float desiredDimension, float imageDimension) {
    if (Math.abs(desiredDimension - imageDimension) < errorThreshold)
      return;
    float scalingFactor = desiredDimension / imageDimension;
    scalingFactor = (float)(Math.floor(scalingFactor * 100) * 0.01f);

    RenderedOp newImage = ImageUtilities.getScaledImage(image, scalingFactor, scalingFactor);
    image.dispose();
    System.gc();
    image = newImage;
  }

  public synchronized void rotate(int degrees) {
    RenderedOp newImage = ImageUtilities.getRotatedImage(image, degrees);
    image.dispose();
    System.gc();
    image = newImage;
  }
  ```

  Good — extracted common replaceImage method:
  ```java
  public void scaleToOneDimension(float desiredDimension, float imageDimension) {
    if (Math.abs(desiredDimension - imageDimension) < errorThreshold)
      return;
    float scalingFactor = desiredDimension / imageDimension;
    scalingFactor = (float)(Math.floor(scalingFactor * 100) * 0.01f);

    replaceImage(ImageUtilities.getScaledImage(image, scalingFactor, scalingFactor));
  }

  public synchronized void rotate(int degrees) {
    replaceImage(ImageUtilities.getRotatedImage(image, degrees));
  }

  private void replaceImage(RenderedOp newImage) {
    image.dispose();
    System.gc();
    image = newImage;
  }
  ```

- **Higher-level structural duplication** — methods that follow the same algorithm with only small variations

  Bad — accrueUSDivisionVacation and accrueEUDivisionVacation have the same structure with only the "legal minimums" step differing:
  ```java
  public class VacationPolicy {
    public void accrueUSDivisionVacation() {
      // code to calculate vacation based on hours worked to date
      // code to ensure vacation meets US minimums
      // code to apply vacation to payroll record
    }
    public void accrueEUDivisionVacation() {
      // code to calculate vacation based on hours worked to date
      // code to ensure vacation meets EU minimums
      // code to apply vacation to payroll record
    }
  }
  ```

  Good — TEMPLATE METHOD pattern extracts the common algorithm, subclasses supply only the varying part:
  ```java
  abstract public class VacationPolicy {
    public void accrueVacation() {
      calculateBaseVacationHours();
      alterForLegalMinimums();
      applyToPayroll();
    }
    private void calculateBaseVacationHours() { /* ... */ };
    abstract protected void alterForLegalMinimums();
    private void applyToPayroll() { /* ... */ };
  }

  public class USVacationPolicy extends VacationPolicy {
    @Override protected void alterForLegalMinimums() {
      // US specific logic
    }
  }

  public class EUVacationPolicy extends VacationPolicy {
    @Override protected void alterForLegalMinimums() {
      // EU specific logic
    }
  }
  ```

  The subclasses fill in the "hole" in the `accrueVacation` algorithm, supplying the only bits of information that are not duplicated.

### Rule 3 Violations: Poor Expressiveness
- **Cryptic or misleading names** — names that do not reveal intent or that surprise the reader
- **Large functions or classes** — big things are hard to name, hard to understand, and hard to maintain
- **Missing pattern nomenclature** — a class implements the Command pattern but is not named `FooCommand`; a class implements Visitor but is not named `BarVisitor`
- **Tests that do not document behavior** — tests that are hard to read, poorly named, or do not demonstrate what the class is about
- **No effort spent on readability** — code works but the author moved on without making it clear for the next reader. As systems become more complex, they take more and more time for a developer to understand, and there is an ever greater opportunity for a misunderstanding.
- **The majority of the cost of a software project is in long-term maintenance** — in order to minimize the potential for defects as we introduce change, it's critical for us to be able to understand what a system does. Unclear code increases defect potential and maintenance cost.

### Rule 4 Violations: Excessive Classes and Methods
- **Too many tiny classes** — over-application of SRP creating an explosion of classes with no real benefit
- **Mandatory interfaces for every class** — dogmatic coding standards requiring interfaces even when there is only one implementation and no testing need
- **Forced separation of fields and behavior** — insisting on data classes + behavior classes when a unified class is simpler
- **Pointless dogmatism** — any rule applied so rigidly that it creates unnecessary complexity

## How to Fix

### Step 1: Establish the Test Safety Net (Rule 1)
1. Write comprehensive tests for all existing behavior
2. Ensure ALL tests pass — fix any failures before proceeding
3. If code is untestable, refactor for testability first: extract interfaces, inject dependencies, break up large classes
4. Set up continuous test execution — run tests after every change

### Step 2: Eliminate Duplication (Rule 2)
1. Search for exact duplicate code blocks and extract them into shared methods
2. Look for near-duplicate code — massage similar sequences to be identical, then extract
3. Check for implementation duplication — can one method delegate to another instead of reimplementing the same concept?
4. Extract common multi-line patterns (like dispose/gc/reassign) into named helper methods
5. Look for higher-level structural duplication — methods that follow the same algorithm with small variations
6. Apply the TEMPLATE METHOD pattern when multiple methods share an algorithm but differ in specific steps: create an abstract base class with the common algorithm, make the varying steps abstract, implement variations in subclasses
7. After each extraction, check if the new method belongs in a different class (extracting commonality reveals SRP violations and increases reuse)

### Step 3: Improve Expressiveness (Rule 3)
1. Choose better names — class and function names should clearly reveal intent and responsibility
2. Keep functions and classes small — small things are inherently easier to understand
3. Use standard nomenclature — name classes after the design patterns they implement (Command, Visitor, Factory, etc.)
4. Write expressive unit tests — tests are documentation by example; they should make a class's purpose immediately clear
5. Take pride in your workmanship — spend time with each function and class, split large functions into smaller ones, and make code easy for the next reader
6. Remember: the next person to read the code will most likely be you

### Step 4: Minimize Classes and Methods (Rule 4)
1. Resist dogmatic rules that inflate class/method counts without real benefit
2. Do not create an interface for every class unless there is a genuine need
3. Do not force separation of data and behavior if a unified class is simpler
4. Keep the overall system small — but NEVER at the expense of rules 1-3
5. This is the lowest priority rule — it is more important to have tests, eliminate duplication, and express yourself clearly

### The Refactoring Loop
After every few lines of code:
1. Pause and reflect — did we just degrade the design?
2. If yes, clean it up immediately
3. Run all tests to prove nothing is broken
4. The tests eliminate the fear that cleaning up will break things
5. Repeat — incremental refactoring keeps the codebase clean continuously

## Key Insight: Emergent Design

The central insight of this chapter is that **good design emerges from following simple rules**. You do not need to create a perfect big-picture design upfront. By:
- Writing tests (which pushes you toward SRP, DIP, low coupling, high cohesion)
- Eliminating duplication (which reveals hidden abstractions and SRP violations)
- Making code expressive (which reduces long-term maintenance cost)
- Keeping things minimal (which prevents over-engineering)

...you naturally arrive at designs that embody principles and patterns that would otherwise take years to learn.

> "Is there a set of simple practices that can replace experience? Clearly not. On the other hand, the practices described in this chapter and in this book are a crystallized form of the many decades of experience enjoyed by the authors. Following the practice of simple design can and does encourage and enable developers to adhere to good principles and patterns that otherwise take years to learn."

## Self-Improvement Protocol

After applying this checklist to any code review or refactoring session:

1. **Verify Rule 1 first** — Are all tests passing? If not, stop everything and fix tests. If there are no tests, write them before doing anything else.
2. **Hunt for duplication (Rule 2)** — Look at every level: exact duplicates, near-duplicates, implementation duplication, structural/algorithmic duplication. Apply extraction and TEMPLATE METHOD as needed.
3. **Read the code as a stranger (Rule 3)** — Can you understand the intent of every class and method from its name alone? Are functions small enough to be self-evident? Would design pattern names help communicate the design?
4. **Count the cost (Rule 4)** — Are there unnecessary classes, interfaces, or methods created from dogma rather than need? Remove them, but only if doing so does not violate rules 1-3.
5. **Log recurring patterns** — If you keep finding the same type of violation, add it to your project's coding guidelines or linting rules.
6. **Remember the priority order** — When two rules conflict, the higher-priority rule always wins. Tests trump everything. Minimal classes/methods is the least important and must never be used to justify duplication or poor expressiveness.
