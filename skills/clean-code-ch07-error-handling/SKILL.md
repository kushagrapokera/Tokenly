---
name: clean-code-ch07-error-handling
description: "Code quality checker based on Clean Code Ch7: Error Handling — checks exception vs error codes, try-catch structure, exception context, caller-oriented exceptions, Special Case pattern, null return/pass prevention. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 7: Error Handling -- Code Quality Checker

*Chapter authored by Michael Feathers*

> "Error handling is important, *but if it obscures logic, it's wrong.*" -- Robert C. Martin

> "Clean code is readable, but it must also be robust. These are not conflicting goals. We can write robust clean code if we see error handling as a separate concern, something that is viewable independently of our main logic." -- Chapter 7 Conclusion

## When to Use

Activate this skill when reviewing or writing code that:
- Handles errors, failures, or exceptional conditions
- Returns status codes, error flags, or sentinel values (like null, -1, false) to indicate failure
- Contains try-catch-finally blocks (or language equivalents: defer/recover in Go, try/except in Python, rescue in Ruby)
- Calls third-party APIs or libraries that can throw exceptions
- Returns null/nil/None from methods or accepts null/nil/None as parameters
- Contains deeply nested null checks or defensive programming patterns
- Uses exceptions for flow control in non-exceptional situations
- Defines custom exception classes
- Wraps external libraries or APIs

## Core Principle

Error handling is a **separate concern** from the main logic. When error handling dominates or is tangled with business logic, the code becomes nearly impossible to understand. The goal is to write code that is both clean AND robust -- these are not conflicting goals. Separate what you do when things go right from what you do when things go wrong.

## Checklist

### 1. Use Exceptions Rather Than Return Codes
- [ ] Functions signal errors by throwing exceptions, NOT by returning error codes, flags, or sentinel values
- [ ] The calling code is NOT cluttered with immediate error-checking after every call
- [ ] The happy path (device algorithm, business logic) is clearly separated from the error-handling path
- [ ] Error handling does not obscure the main logic of the code

**Why:** With return codes, the caller must check for errors immediately after the call. It is easy to forget. With exceptions, the calling code is cleaner -- its logic is not obscured by error handling. Two concerns that were tangled (business logic and error handling) become separated.

**BAD -- Return codes tangle logic and error handling (Listing 7-1):**
```java
public class DeviceController {
  public void sendShutDown() {
    DeviceHandle handle = getHandle(DEV1);
    // Check the state of the device
    if (handle != DeviceHandle.INVALID) {
      // Save the device status to the record field
      retrieveDeviceRecord(handle);
      // If not suspended, shut down
      if (record.getStatus() != DEVICE_SUSPENDED) {
        pauseDevice(handle);
        clearDeviceWorkQueue(handle);
        closeDevice(handle);
      } else {
        logger.log("Device suspended. Unable to shut down");
      }
    } else {
      logger.log("Invalid handle for: " + DEV1.toString());
    }
  }
}
```

**GOOD -- Exceptions separate concerns (Listing 7-2):**
```java
public class DeviceController {
  public void sendShutDown() {
    try {
      tryToShutDown();
    } catch (DeviceShutDownError e) {
      logger.log(e);
    }
  }

  private void tryToShutDown() throws DeviceShutDownError {
    DeviceHandle handle = getHandle(DEV1);
    DeviceRecord record = retrieveDeviceRecord(handle);

    pauseDevice(handle);
    clearDeviceWorkQueue(handle);
    closeDevice(handle);
  }

  private DeviceHandle getHandle(DeviceID id) {
    ...
    throw new DeviceShutDownError("Invalid handle for: " + id.toString());
    ...
  }
}
```

**Language-specific equivalents:**
- **Go:** Return `error` as second value and wrap with `fmt.Errorf` -- but keep the happy path unindented and guard clauses early
- **Python:** Raise exceptions rather than returning error tuples or status dicts
- **Rust:** Use `Result<T, E>` with the `?` operator to propagate errors cleanly
- **TypeScript/JavaScript:** Throw errors or return `Result` types; avoid `{ success: false, error: "..." }` patterns when exceptions are cleaner

### 2. Write Your Try-Catch-Finally Statement First
- [ ] When writing code that could throw exceptions, the try-catch-finally structure is written FIRST
- [ ] The try block is treated as a transaction -- the catch leaves the program in a consistent state
- [ ] Tests are written that force exceptions FIRST, then behavior is added to satisfy the tests (TDD approach)

**Why:** One of the most interesting things about exceptions is that they **define a scope** within your program. When you execute code in the try portion of a try-catch-finally statement, you are stating that execution can abort at any point and then resume at the catch. In a way, try blocks are like transactions -- your catch has to leave your program in a consistent state, no matter what happens in the try. Starting with try-catch-finally helps you define what the user of that code should expect, no matter what goes wrong with the code that is executed in the try.

**TDD approach -- start with a test that forces an exception:**
```java
@Test(expected = StorageException.class)
public void retrieveSectionShouldThrowOnInvalidFileName() {
  sectionStore.retrieveSection("invalid - file");
}
```

**Then create a stub that doesn't throw (it will fail the test):**
```java
public List<RecordedGrip> retrieveSection(String sectionName) {
  // dummy return until we have a real implementation
  return new ArrayList<RecordedGrip>();
}
```

**Then change the implementation so that it attempts to access an invalid file -- this throws an exception, and our test passes:**
```java
public List<RecordedGrip> retrieveSection(String sectionName) {
  try {
    FileInputStream stream = new FileInputStream(sectionName);
  } catch (Exception e) {
    throw new StorageException("retrieval error", e);
  }
  return new ArrayList<RecordedGrip>();
}
```

**Then refactor -- narrow the exception type to match what `FileInputStream` actually throws:**
```java
public List<RecordedGrip> retrieveSection(String sectionName) {
  try {
    FileInputStream stream = new FileInputStream(sectionName);
    stream.close();
  } catch (FileNotFoundException e) {
    throw new StorageException("retrieval error", e);
  }
  return new ArrayList<RecordedGrip>();
}
```

**Key insight:** Now that the scope is defined with a try-catch structure, you can use TDD to build up the rest of the logic. The logic will be added between the creation of the `FileInputStream` and the `close`, and can pretend that nothing goes wrong. Write tests that force exceptions, and then add behavior to your handler to satisfy your tests. This builds the transaction scope of the try block first and helps maintain the transaction nature of that scope.

### 3. Use Unchecked Exceptions
- [ ] Prefer unchecked (runtime) exceptions over checked exceptions
- [ ] Checked exceptions are NOT forcing signature changes through multiple layers of the call hierarchy
- [ ] Low-level implementation details are NOT leaking into high-level function signatures via throws clauses

**Why:** The debate is over. When checked exceptions were introduced in the first version of Java, they seemed like a great idea -- the signature of every method would list all of the exceptions it could pass to its caller, and your code literally wouldn't compile if the signature didn't match. Yes, they can yield *some* benefit, but it is clear now that they aren't necessary for the production of robust software.

The price of checked exceptions is an Open/Closed Principle violation. If you throw a checked exception from a method and the catch is three levels above, *you must declare that exception in the signature of each method between you and the catch*. This means that a change at a low level of the software can force signature changes on many higher levels. The changed modules must be rebuilt and redeployed even though nothing they care about changed.

Consider the calling hierarchy of a large system. Functions at the top call functions below them, which call more functions below them, ad infinitum. If one of the lowest level functions is modified to throw a checked exception, then the function signature must add a `throws` clause. But this means that every function that calls our modified function must also be modified either to catch the new exception or to append the appropriate `throws` clause to its signature. Ad infinitum. The net result is a cascade of changes from the lowest levels to the highest! Encapsulation is broken because all functions in the path of a throw must know about details of that low-level exception. Given that the purpose of exceptions is to allow you to handle errors at a distance, it is a shame that checked exceptions break encapsulation in this way.

**Key facts:**
- When checked exceptions were introduced in the first version of Java, they seemed like a great idea
- C# does not have checked exceptions, and despite valiant attempts, C++ doesn't either. Neither do Python or Ruby. Yet it is possible to write robust software in all of these languages
- Checked exceptions can sometimes be useful if you are writing a critical library: You must catch them
- But in general application development the dependency costs outweigh the benefits

**BAD -- checked exceptions cascading through layers:**
```java
// Low level
public void readFile() throws FileNotFoundException { ... }

// Mid level -- forced to declare exception it doesn't care about
public void processData() throws FileNotFoundException {
  readFile();
}

// High level -- forced to declare exception it doesn't care about
public void handleRequest() throws FileNotFoundException {
  processData();
}
```

**GOOD -- unchecked exceptions don't cascade:**
```java
// Low level -- wraps in unchecked exception
public void readFile() {
  try { ... }
  catch (FileNotFoundException e) {
    throw new StorageException("retrieval error", e);
  }
}

// Mid level -- clean signature, no forced dependency
public void processData() {
  readFile();
}

// High level -- catches where appropriate
public void handleRequest() {
  try {
    processData();
  } catch (StorageException e) {
    logger.log(e);
  }
}
```

### 4. Provide Context with Exceptions
- [ ] Each exception provides enough context to determine the **source** and **location** of the error
- [ ] Exception messages mention the **operation that failed** and the **type of failure**
- [ ] If logging, enough information is passed to log the error in the catch block
- [ ] Stack traces alone are NOT considered sufficient context (a stack trace cannot tell you the intent of the operation that failed)

**Why:** A stack trace tells you where an exception was thrown, but it cannot tell you the intent of the operation that failed. You need informative error messages that mention the operation that failed and the type of failure.

**BAD:**
```java
throw new Exception("error");
throw new StorageException(e);  // just wrapping, no context
```

**GOOD:**
```java
throw new StorageException("retrieval error", e);
throw new DeviceShutDownError("Invalid handle for: " + id.toString());
// Includes: what operation failed + what went wrong + original cause
```

### 5. Define Exception Classes in Terms of a Caller's Needs
- [ ] Exception classes are defined based on **how they are caught**, NOT by source or type of error
- [ ] Third-party APIs are wrapped so that their many exception types are translated into a single, caller-meaningful exception type
- [ ] Duplicate catch blocks doing the same thing are consolidated by wrapping
- [ ] Only use different exception classes when you want to catch one exception and allow the other to pass through

**Why:** When we define exception classes, our most important concern should be *how they are caught*. Wrapping third-party APIs is a best practice -- the benefits are:
1. You minimize your dependencies upon the third-party vendor
2. You can choose to move to a different library in the future without much penalty
3. Wrapping makes it easier to mock out third-party calls when you are testing your own code
4. You aren't tied to a particular vendor's API design choices -- you can define an API that you feel comfortable with

**BAD -- poor exception classification with duplicated handling:**
```java
ACMEPort port = new ACMEPort(12);

try {
  port.open();
} catch (DeviceResponseException e) {
  reportPortError(e);
  logger.log("Device response exception", e);
} catch (ATM1212UnlockedException e) {
  reportPortError(e);
  logger.log("Unlock exception", e);
} catch (GMXError e) {
  reportPortError(e);
  logger.log("Device response exception");
} finally {
  ...
}
```

**GOOD -- wrapper translates to a single exception type:**
```java
LocalPort port = new LocalPort(12);
try {
  port.open();
} catch (PortDeviceFailure e) {
  reportError(e);
  logger.log(e.getMessage(), e);
} finally {
  ...
}
```

**The wrapper class that enables this:**
```java
public class LocalPort {
  private ACMEPort innerPort;

  public LocalPort(int portNumber) {
    innerPort = new ACMEPort(portNumber);
  }

  public void open() {
    try {
      innerPort.open();
    } catch (DeviceResponseException e) {
      throw new PortDeviceFailure(e);
    } catch (ATM1212UnlockedException e) {
      throw new PortDeviceFailure(e);
    } catch (GMXError e) {
      throw new PortDeviceFailure(e);
    }
  }
}
```

**Key rules:**
- Often a single exception class is fine for a particular area of code
- The information sent with the exception can distinguish the errors
- Use different exception classes ONLY when you want to catch one and let the other pass through

### 6. Define the Normal Flow (SPECIAL CASE PATTERN)
- [ ] Exceptions are NOT used for business logic flow control
- [ ] Where an "exceptional" case is actually a known, normal business scenario, the SPECIAL CASE PATTERN is used instead
- [ ] Special case objects encapsulate the exceptional behavior so the client code does not have to deal with it
- [ ] The catch block is NOT being used to define normal business behavior

**Why:** If you follow the advice in the preceding sections, you'll end up with a good amount of separation between your business logic and your error handling. The bulk of your code will start to look like a clean unadorned algorithm. However, the process of doing this pushes error detection to the edges of your program. You wrap external APIs so that you can throw your own exceptions, and you define a handler above your code so that you can deal with any aborted computation. Most of the time this is a great approach, but there are some times when you may not want to abort.

If the catch block is defining default/alternative business behavior, the exception is cluttering the logic. The SPECIAL CASE PATTERN (from Martin Fowler's *Refactoring*) creates a class or configures an object so that it handles the special case for you -- the client code does not have to deal with exceptional behavior because that behavior is encapsulated in the special case object.

**BAD -- exception used for normal business flow:**
```java
try {
  MealExpenses expenses = expenseReportDAO.getMeals(employee.getID());
  m_total += expenses.getTotal();
} catch (MealExpensesNotFound e) {
  m_total += getMealPerDiem();
}
```
Here, if meals are expensed they become part of the total; if not, the employee gets a per diem amount. The exception clutters the logic.

**GOOD -- Special Case Pattern eliminates the exception:**
```java
MealExpenses expenses = expenseReportDAO.getMeals(employee.getID());
m_total += expenses.getTotal();
```

This works because `ExpenseReportDAO` is changed so that it always returns a `MealExpense` object. If there are no meal expenses, it returns a Special Case object that returns the per diem as its total:

```java
public class PerDiemMealExpenses implements MealExpenses {
  public int getTotal() {
    // return the per diem default
  }
}
```

**When to apply:**
- A method returns different types depending on success/failure, and the "failure" case has a valid default behavior
- You find yourself catching exceptions just to provide a default value
- The "exceptional" case is actually a normal, expected business scenario
- Null would otherwise be returned (return a Special Case object instead)

### 7. Don't Return Null
- [ ] Methods do NOT return null/nil/None to indicate absence or failure
- [ ] Instead of returning null, methods throw an exception OR return a SPECIAL CASE object
- [ ] If calling a third-party API that returns null, wrap that method so it throws an exception or returns a special case object
- [ ] For collections/lists, return an empty collection instead of null
- [ ] Code is NOT littered with `if (x != null)` checks

**Why:** Any discussion about error handling should include mention of the things we do that invite errors. The first on the list is returning null. When we return null, we are essentially creating work for ourselves and foisting problems upon our callers. All it takes is one missing null check to send an application spinning out of control. It's easy to say that the problem with the code is that it is missing a null check, but in actuality, the problem is that it has *too many*. If you are tempted to return null from a method, consider throwing an exception or returning a SPECIAL CASE object instead. If you are calling a null-returning method from a third-party API, consider wrapping that method with a method that either throws an exception or returns a special case object.

**BAD -- returning null forces defensive null checks everywhere:**
```java
public void registerItem(Item item) {
  if (item != null) {
    ItemRegistry registry = peristentStore.getItemRegistry();
    if (registry != null) {
      Item existing = registry.getItem(item.getID());
      if (existing.getBillingPeriod().hasRetailOwner()) {
        existing.register(item);
      }
    }
  }
}
```
Note: what happens if `persistentStore` is null? There is no null check for it. We would get a NullPointerException at runtime.

**BAD -- returning null for a list:**
```java
List<Employee> employees = getEmployees();
if (employees != null) {
  for (Employee e : employees) {
    totalPay += e.getPay();
  }
}
```

**GOOD -- return empty list instead of null:**
```java
List<Employee> employees = getEmployees();
for (Employee e : employees) {
  totalPay += e.getPay();
}
```

Where `getEmployees()` is:
```java
public List<Employee> getEmployees() {
  if ( .. there are no employees .. )
    return Collections.emptyList();
}
```

**Language-specific equivalents for avoiding null returns:**
- **Java:** `Collections.emptyList()`, `Collections.emptyMap()`, `Optional<T>`
- **Go:** Return zero-value structs, empty slices (`[]Type{}`), or use the comma-ok idiom
- **Python:** Return empty lists `[]`, empty dicts `{}`, or use `Optional` type hints with explicit handling
- **Rust:** Use `Option<T>` -- null does not exist
- **TypeScript:** Return empty arrays `[]`, use `undefined` with strict null checks, or use discriminated unions
- **C#:** Return `Enumerable.Empty<T>()`, `Array.Empty<T>()`, or use nullable reference types

### 8. Don't Pass Null
- [ ] Null/nil/None is NOT passed as a function argument (unless an external API explicitly expects it)
- [ ] Functions do NOT need defensive null-parameter checks for internally-called code
- [ ] The codebase has a policy/convention that forbids passing null by default

**Why:** Returning null from methods is bad, but passing null *into* methods is worse. Unless you are working with an API which expects you to pass null, you should avoid passing null in your code whenever possible.

When someone passes null, you get a NullPointerException. You can add a check and throw `InvalidArgumentException`, but then you need a handler for that -- is it any better than a NullPointerException? You can use assertions (`assert p1 != null : "p1 should not be null"`), but that is good documentation that still results in a runtime error if someone passes null.

In most programming languages there is no good way to deal with a null that is passed by a caller accidentally. Because this is the case, the rational approach is to forbid passing null by default. When you do, you can code with the knowledge that a null in an argument list is an indication of a problem, and end up with far fewer careless mistakes.

**Original method:**
```java
public class MetricsCalculator {
  public double xProjection(Point p1, Point p2) {
    return (p2.x - p1.x) * 1.5;
  }
}
```

**BAD -- passing null causes NullPointerException:**
```java
calculator.xProjection(null, new Point(12, 13));
// Results in NullPointerException
```

**INADEQUATE FIX 1 -- throw on null (still need a handler):**
```java
public class MetricsCalculator {
  public double xProjection(Point p1, Point p2) {
    if (p1 == null || p2 == null) {
      throw InvalidArgumentException(
        "Invalid argument for MetricsCalculator.xProjection");
    }
    return (p2.x - p1.x) * 1.5;
  }
}
```

**INADEQUATE FIX 2 -- assertions (good docs, still runtime error):**
```java
public class MetricsCalculator {
  public double xProjection(Point p1, Point p2) {
    assert p1 != null : "p1 should not be null";
    assert p2 != null : "p2 should not be null";
    return (p2.x - p1.x) * 1.5;
  }
}
```

**BEST APPROACH:** Forbid passing null by convention/policy. Neither of the above fixes is truly good. The rational approach is to prevent the problem at its source by making null-passing a coding standard violation.

## Violations to Detect

### CRITICAL Violations
| ID | Violation | What to Look For |
|----|-----------|-----------------|
| CH7-V1 | **Error codes instead of exceptions** | Functions returning -1, 0/1, false, error codes, status enums to signal failure; callers checking return values with if/else chains immediately after calls |
| CH7-V2 | **Returning null** | Any `return null`, `return nil`, `return None` from a method; methods that can return null forcing callers to null-check |
| CH7-V3 | **Passing null as argument** | Null literals passed as function arguments; method signatures that routinely accept nullable parameters for internal code |
| CH7-V4 | **Null-check cascades** | Deeply nested `if (x != null)` chains; more than one level of null checking in a single method |
| CH7-V5 | **Exceptions for normal flow control** | Catch blocks that implement business logic defaults; catching exceptions where a Special Case Pattern should be used instead |

### MAJOR Violations
| ID | Violation | What to Look For |
|----|-----------|-----------------|
| CH7-V6 | **Missing exception context** | Exceptions thrown with empty messages, generic messages ("error"), or without the operation name and failure type |
| CH7-V7 | **Checked exception cascade** | (Java) Checked exceptions forcing throws declarations through multiple layers of the call hierarchy; low-level exception types appearing in high-level method signatures |
| CH7-V8 | **Duplicate catch blocks** | Multiple catch blocks performing essentially the same action (log + report); third-party API exceptions not wrapped into a single caller-meaningful type |
| CH7-V9 | **Try-catch not written first** | Complex try blocks where the error handling was clearly an afterthought; inconsistent exception handling within a try block; catch blocks that leave the program in an inconsistent state |
| CH7-V10 | **Returning null for collections** | Methods returning null instead of empty collections/lists/arrays |

### MINOR Violations
| ID | Violation | What to Look For |
|----|-----------|-----------------|
| CH7-V11 | **Unwrapped third-party APIs** | Direct use of third-party library exceptions in application code; no wrapper/adapter layer around external libraries |
| CH7-V12 | **Overly broad exception types** | Catching `Exception` or `Throwable` (Java), `except Exception` (Python), `rescue => e` (Ruby) when a more specific type is appropriate |
| CH7-V13 | **Error handling obscures logic** | Business logic methods where error handling code is more prominent than the actual algorithm; tangled concerns |

## How to Fix

### Fix CH7-V1: Replace Error Codes with Exceptions
1. Identify the error condition currently signaled by a return code
2. Create a descriptive exception class (or use an existing one) named after the failure
3. Throw the exception at the point of failure with context message
4. Move the happy-path logic into a clean method free of error checks
5. Add a try-catch at the appropriate level to handle the error

### Fix CH7-V2 & CH7-V10: Eliminate Null Returns
1. **For collections:** Replace `return null` with `return Collections.emptyList()` (Java), `return []` (Python/JS/Go), etc.
2. **For objects with default behavior:** Apply the Special Case Pattern -- create a class implementing the same interface that provides default behavior
3. **For objects without default behavior:** Throw a descriptive exception instead of returning null
4. **For third-party APIs that return null:** Wrap the call in a method that throws an exception or returns a special case object
5. Remove all downstream null checks that are now unnecessary

### Fix CH7-V3 & CH7-V4: Eliminate Null Passing
1. Establish a codebase convention: null is not a valid argument for internal methods
2. Remove null arguments from call sites by providing proper objects or using overloaded methods
3. If an API truly requires a nullable parameter, document it explicitly and isolate it behind a wrapper
4. Remove defensive null-parameter checks from internal methods (they become unnecessary when null-passing is forbidden)

### Fix CH7-V5: Apply the Special Case Pattern
1. Identify the catch block that implements default/alternative business logic
2. Create a Special Case class that implements the same interface as the normal-case object
3. Have the Special Case class return the default values that were previously in the catch block
4. Modify the data source (DAO, repository, factory) to return the Special Case object instead of throwing
5. Remove the try-catch -- the client code now works uniformly without knowing about the special case

**Template:**
```java
// 1. Interface (existing)
public interface MealExpenses {
  int getTotal();
}

// 2. Normal case (existing)
public class ActualMealExpenses implements MealExpenses {
  public int getTotal() { return actualTotal; }
}

// 3. Special Case (new)
public class PerDiemMealExpenses implements MealExpenses {
  public int getTotal() { return PER_DIEM_DEFAULT; }
}

// 4. Factory/DAO returns Special Case instead of throwing
public MealExpenses getMeals(int employeeId) {
  // If no meals found, return PerDiemMealExpenses instead of throwing
}

// 5. Client code is clean -- no try-catch needed
MealExpenses expenses = dao.getMeals(employee.getID());
m_total += expenses.getTotal();
```

### Fix CH7-V6: Add Exception Context
1. Include the **operation that failed** (e.g., "retrieval error", "device shutdown")
2. Include the **type of failure** or relevant data (e.g., "Invalid handle for: DEV1")
3. Include the **original cause** as a chained exception (e.g., `new StorageException("retrieval error", e)`)
4. Ensure enough information is present to log the error meaningfully in the catch block

### Fix CH7-V7: Convert to Unchecked Exceptions
1. Change checked exceptions to extend `RuntimeException` (Java) instead of `Exception`
2. Remove `throws` declarations from intermediate method signatures
3. Catch the exception at the appropriate high level where it can be meaningfully handled
4. Exception: Keep checked exceptions in critical library code where callers MUST handle them

### Fix CH7-V8: Wrap Third-Party APIs
1. Create a wrapper class for the third-party API (e.g., `LocalPort` wrapping `ACMEPort`)
2. In the wrapper, catch all vendor-specific exceptions and translate them to a single application-specific exception
3. Replace all direct API usage with the wrapper
4. Benefits: minimized vendor dependency, easier to switch libraries, easier to mock for testing, cleaner calling code

### Fix CH7-V9: Restructure Try-Catch-Finally
1. Write the try-catch-finally structure FIRST, before the business logic
2. Write a test that forces an exception to define the scope
3. Treat the try block as a transaction -- ensure the catch block leaves the program in a consistent state
4. Add business logic inside the try block incrementally, using TDD

### Fix CH7-V13: Separate Error Handling from Logic
1. Extract the happy-path logic into a separate method (like `tryToShutDown()`)
2. Keep the try-catch in the calling method
3. The extracted method should read like a clean, unadorned algorithm
4. Error handling methods should only handle errors -- not contain business logic

## Self-Improvement Protocol

After applying this checklist, verify:

1. **Separation test:** Can you read the business logic without being distracted by error handling? Can you read the error handling independently of the business logic? If both: pass.
2. **Null audit:** Search the codebase for `return null`, `return nil`, `return None`. Each instance is a potential violation. Search for `!= null`, `!= nil`, `is not None` -- excessive checks indicate null-returning methods upstream.
3. **Exception context audit:** For every `throw new` / `raise` / `panic`, verify the message includes the operation name and failure details. A stack trace alone is insufficient.
4. **Special Case scan:** For every catch block, ask: "Is this catch implementing default business behavior?" If yes, apply the Special Case Pattern.
5. **Wrapper audit:** For every third-party API used directly, ask: "Are we catching multiple vendor exceptions in the same way?" If yes, wrap the API.
6. **Collection return audit:** For every method returning a list/array/map, verify it never returns null. It should return an empty collection.
7. **Null parameter audit:** Search for calls passing null literals as arguments. Each is a violation unless the API explicitly requires it.
8. **Transaction consistency check:** For every try-catch-finally, verify: does the catch leave the program in a consistent state? Is the try block written as a transaction?

## Bibliography

- **[Martin]:** *Agile Software Development: Principles, Patterns, and Practices*, Robert C. Martin, Prentice Hall, 2002.
- **[Fowler]:** *Refactoring: Improving the Design of Existing Code*, Martin Fowler et al., Addison-Wesley, 1999. (Referenced for the SPECIAL CASE PATTERN)
