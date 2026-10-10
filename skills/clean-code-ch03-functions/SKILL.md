---
name: clean-code-ch03-functions
description: "Code quality checker based on Clean Code Ch3: Functions — checks function size, single responsibility, abstraction levels, argument counts, side effects, command-query separation, error handling, and DRY. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 3: Functions -- Code Quality Checker

## When to Use

Invoke this skill when:
- Reviewing any function/method in a pull request or code review
- Writing new functions or refactoring existing ones
- Encountering functions that feel hard to read, test, or understand
- Performing code quality audits on a module or file
- A function exceeds 20 lines, has more than 2 arguments, or mixes abstraction levels
- Before committing code that adds or modifies functions

## Checklist

Run through EVERY item below for each function under review. A function must pass ALL checks to be considered clean.

### 1. SIZE: Is the function small enough?

- [ ] Function is **20 lines or fewer** (ideal: 2-5 lines, as in Kent Beck's Sparkle program)
- [ ] Lines are **no longer than 150 characters** (prefer shorter)
- [ ] Function fits on a single screen without scrolling
- [ ] Blocks inside `if`, `else`, `while`, `for`, `switch`, and `try/catch` are **one line long** -- typically a function call with a descriptive name
- [ ] Indentation level is **no greater than one or two** (no deeply nested structures)
- [ ] The function cannot be meaningfully shortened further without mere restatement

**Book reference:** "The first rule of functions is that they should be small. The second rule of functions is that they should be smaller than that." In the eighties, the rule was that a function should be no bigger than a screen-full (VT100 screens: 24 lines by 80 columns, with 4 lines for admin). Today with 150 characters per line and 100+ lines on screen, functions should still be very small. "Lines should not be 150 characters long. Functions should not be 100 lines long. Functions should hardly ever be 20 lines long." Martin visited Kent Beck in 1999 and saw a Java/Swing program (Sparkle) where every function was just two, three, or four lines long. Each was transparently obvious, told a story, and led to the next in a compelling order.

### 2. DO ONE THING: Does the function do exactly one thing?

- [ ] The function can be described as a brief TO paragraph: "TO [FunctionName], we [single coherent action]."
- [ ] All statements in the function are **one level of abstraction below** the stated name of the function
- [ ] You **cannot extract** another function from it with a name that is NOT merely a restatement of its implementation
- [ ] The function cannot be reasonably divided into **sections** (e.g., "declarations," "initializations," "sieve" as in the `generatePrimes` function in Listing 4-7) -- if it can be divided into sections, it does more than one thing

**The "three things" test (Listing 3-3):** Does this re-refactored function do one thing or three?
```java
public static String renderPageWithSetupsAndTeardowns(
    PageData pageData, boolean isSuite) throws Exception {
    if (isTestPage(pageData))
        includeSetupAndTeardownPages(pageData, isSuite);
    return pageData.getHtml();
}
```
It arguably does three things: (1) determining whether the page is a test page, (2) if so including setups and teardowns, (3) rendering the page in HTML. But notice that all three steps are one level of abstraction below the function name. The function is doing one thing: *including setups and teardowns into a test page*. A function named `includeSetupsAndTeardownsIfTestPage` would merely be a restatement of the code, not a meaningful extraction -- confirming it does one thing.

**Book reference -- the TO paragraph test:**
> TO RenderPageWithSetupsAndTeardowns, we check to see whether the page is a test page and if so, we include the setups and teardowns. In either case we render the page in HTML.

If the steps described are one level below the function name, the function is doing one thing. If they jump across multiple abstraction levels, it is doing too much.

### 3. ONE LEVEL OF ABSTRACTION: Are all statements at the same abstraction level?

- [ ] No mixing of high-level concepts (e.g., `getHtml()`) with intermediate details (e.g., `String pagePathName = PathParser.render(pagePath)`) and low-level operations (e.g., `.append("\n")`) in the same function
- [ ] Each function introduces the next, reading like a top-down narrative
- [ ] Once details are mixed with essential concepts, more and more details tend to accrete within the function (the "broken windows" effect)

**The Stepdown Rule:** Code should read like a top-down set of TO paragraphs, each describing the current level and referencing the next level down:
> To include the setups and teardowns, we include setups, then we include the test page content, and then we include the teardowns.
>   To include the setups, we include the suite setup if this is a suite, then we include the regular setup.
>     To include the suite setup, we search the parent hierarchy for the "SuiteSetUp" page and add an include statement with the path of that page.
>       To search the parent...

### 4. SWITCH STATEMENTS: Are switch/if-else chains handled properly?

- [ ] Switch statements (and equivalent if/else chains) appear **at most once** for a given type discrimination
- [ ] They are **buried in a low-level class** (typically an Abstract Factory) and never seen by the rest of the system
- [ ] They are used **only to create polymorphic objects** -- all subsequent behavior is dispatched polymorphically through an interface/abstract class
- [ ] They do NOT violate the **Single Responsibility Principle** (more than one reason to change)
- [ ] They do NOT violate the **Open/Closed Principle** (must be modified when new types are added)

**Bad -- switch in business logic (Listing 3-4):**
```java
public Money calculatePay(Employee e) throws InvalidEmployeeType {
    switch (e.type) {
        case COMMISSIONED: return calculateCommissionedPay(e);
        case HOURLY:       return calculateHourlyPay(e);
        case SALARIED:     return calculateSalariedPay(e);
        default: throw new InvalidEmployeeType(e.type);
    }
}
```
Problem: `isPayday(Employee e, Date date)` and `deliverPay(Employee e, Money pay)` and unlimited other functions would need the same switch structure.

**Good -- switch buried in factory (Listing 3-5):**
```java
public abstract class Employee {
    public abstract boolean isPayday();
    public abstract Money calculatePay();
    public abstract void deliverPay(Money pay);
}

public interface EmployeeFactory {
    public Employee makeEmployee(EmployeeRecord r) throws InvalidEmployeeType;
}

public class EmployeeFactoryImpl implements EmployeeFactory {
    public Employee makeEmployee(EmployeeRecord r) throws InvalidEmployeeType {
        switch (r.type) {
            case COMMISSIONED: return new CommissionedEmployee(r);
            case HOURLY:       return new HourlyEmployee(r);
            case SALARIED:     return new SalariedEmployee(r);
            default: throw new InvalidEmployeeType(r.type);
        }
    }
}
```

### 5. DESCRIPTIVE NAMES: Is the name clear and complete?

- [ ] The function name **says what it does** -- a reader should get "pretty much what you expected" (Ward's principle)
- [ ] Long descriptive names are preferred over short enigmatic ones
- [ ] Long descriptive names are preferred over long descriptive comments
- [ ] Naming convention supports **multiple words** that are easy to read (camelCase, snake_case, etc.)
- [ ] Names are **consistent** across the module -- same phrases, nouns, and verbs throughout (e.g., `includeSetupAndTeardownPages`, `includeSetupPages`, `includeSuiteSetupPage`, `includeSetupPage` -- consistent verb/noun phrasing)
- [ ] Spend time choosing the name; try several; read the code with each in place before committing
- [ ] Choosing descriptive names will **clarify the design of the module** in your mind and help you improve it -- hunting for a good name often results in a favorable restructuring of the code
- [ ] Changing a name to improve clarity is always worth the effort -- modern IDEs (Eclipse, IntelliJ) make this trivial
- [ ] Consistency test: if you have `includeTeardownPages`, `includeSuiteTeardownPage`, and `includeTeardownPage`, readers see the pattern and ask "What happened to `includeSetupPages`, `includeSuiteSetupPage`, and `includeSetupPage`?" -- that's "pretty much what you expected"

### 6. FUNCTION ARGUMENTS: Are there as few arguments as possible?

**Argument count rules (strict):**
- [ ] **Niladic (0 args):** Ideal. Prefer this form.
- [ ] **Monadic (1 arg):** Good. Acceptable and common.
- [ ] **Dyadic (2 args):** Acceptable with caution. Harder to understand than monadic.
- [ ] **Triadic (3 args):** Avoid. Requires very special justification.
- [ ] **Polyadic (4+ args):** Never. Refactor immediately.

**Why arguments are costly:** Arguments take conceptual power. They force readers to interpret details at a different level of abstraction than the function name. `includeSetupPage()` is easier to understand than `includeSetupPageInto(newPageContent)` -- the `StringBuffer` argument forces you to know a detail that isn't important at that point. Arguments are also harder from a **testing** perspective: with zero arguments, testing is trivial; with one, it's manageable; with two or more, testing every combination of appropriate values can be daunting.

#### 6a. Common Monadic Forms (1 argument)

Three legitimate patterns for single-argument functions:
1. **Asking a question:** `boolean fileExists("MyFile")` -- input arg, boolean return
2. **Transforming:** `InputStream fileOpen("MyFile")` -- input arg, transformed return value. The transformation should appear as the return value, NOT as an output argument. `StringBuffer transform(StringBuffer in)` is better than `void transform(StringBuffer out)` even if the implementation simply returns the input.
3. **Event:** `void passwordAttemptFailedNtimes(int attempts)` -- input arg, no return, alters system state. Use carefully; make it clear from name/context that it is an event.

Avoid monadic functions that do not follow these forms, e.g., `void includeSetupPageInto(StringBuffer pageText)` -- using an output argument for a transformation is confusing.

#### 6b. Flag Arguments

- [ ] **No boolean arguments** -- flag args loudly proclaim the function does more than one thing (one thing when true, another when false)
- [ ] Split into two functions instead: `renderForSuite()` and `renderForSingleTest()` rather than `render(boolean isSuite)`
- [ ] `render(true)` is confusing to any reader -- `render(boolean isSuite)` is only marginally better
- [ ] Note: Even in Listing 3-7 Martin admits the flag argument was a compromise because callers were already passing the boolean and he wanted to limit the scope of refactoring. The ideal would have been `renderForSuite()` and `renderForSingleTest()`

#### 6c. Dyadic Functions (2 arguments)

- [ ] Dyads are acceptable when arguments have **natural ordering or cohesion**: `Point(0, 0)`, `assertEquals(expected, actual)`
- [ ] Even natural dyads like `assertEquals(expected, actual)` are problematic -- readers frequently swap the order
- [ ] Convert to monads when possible: make one arg a member variable, make the function a method on one arg's class, or extract a new class (e.g., `FieldWriter` taking `outputStream` in constructor, then calling `write(name)`)
- [ ] `writeField(outputStream, name)` is harder to understand than `outputStream.writeField(name)`

#### 6d. Triads (3 arguments)

- [ ] Think very carefully before creating a triad
- [ ] `assertEquals(message, expected, actual)` -- readers consistently pause, read `message` as `expected`, and must learn to ignore the first argument
- [ ] `assertEquals(1.0, amount, .001)` is more tolerable because the floating-point comparison delta is a well-known convention

#### 6e. Argument Objects

- [ ] When a function needs 2-3 arguments, **wrap related args into a class/struct**
- [ ] `makeCircle(double x, double y, double radius)` becomes `makeCircle(Point center, double radius)`
- [ ] This is NOT cheating -- when variables are passed together, they likely represent a concept (like "point") that deserves its own name

#### 6f. Argument Lists (Varargs)

- [ ] Variable argument lists that are all treated identically count as a **single argument of type List**
- [ ] `String.format("%s worked %.2f hours.", name, hours)` is effectively dyadic: `format(String, Object...)`
- [ ] Same niladic/monadic/dyadic/triadic rules apply after collapsing the varargs:
  - `void monad(Integer... args);`
  - `void dyad(String name, Integer... args);`
  - `void triad(String name, int count, Integer... args);`

#### 6g. Verbs and Keywords

- [ ] Monad: function and argument form a **verb/noun pair** -- `write(name)`, `writeField(name)`
- [ ] Use the **keyword form** to encode argument names in the function name: `assertExpectedEqualsActual(expected, actual)` instead of `assertEquals(expected, actual)` -- eliminates ordering confusion

### 7. SIDE EFFECTS: Does the function do only what its name promises?

**"Side effects are lies."** Your function promises to do one thing, but it also does other *hidden* things.

- [ ] No hidden changes to class member variables beyond what the name implies
- [ ] No hidden changes to function parameters
- [ ] No hidden changes to system globals
- [ ] No **temporal couplings** hidden inside the function

**Bad -- hidden side effect (Listing 3-6, `UserValidator.java`):**
```java
public class UserValidator {
    private Cryptographer cryptographer;

    public boolean checkPassword(String userName, String password) {
        User user = UserGateway.findByName(userName);
        if (user != User.NULL) {
            String codedPhrase = user.getPhraseEncodedByPassword();
            String phrase = cryptographer.decrypt(codedPhrase, password);
            if ("Valid Password".equals(phrase)) {
                Session.initialize();  // SIDE EFFECT! Name says "check" not "initialize"
                return true;
            }
        }
        return false;
    }
}
```
The call to `Session.initialize()` is a side effect. The name `checkPassword` does not imply session initialization. A caller who believes what the name of the function says runs the risk of **erasing the existing session data** when he or she decides to check the validity of the user. This side effect creates a **temporal coupling**: `checkPassword` can only be called at certain times (when it is safe to initialize the session). If called out of order, session data may be inadvertently lost. If the temporal coupling is truly needed, rename to `checkPasswordAndInitializeSession` (though this violates "do one thing").

#### 7a. Output Arguments

- [ ] **Avoid output arguments entirely** -- arguments are naturally interpreted as inputs
- [ ] `appendFooter(s)` is confusing -- does it append `s` as the footer, or append a footer to `s`? Having to look at the signature (`void appendFooter(StringBuffer report)`) to understand is a cognitive break
- [ ] In OO languages, use `this`/`self` instead: `report.appendFooter()` rather than `appendFooter(report)`
- [ ] If a function must change state, have it change the state of **its owning object**

### 8. COMMAND QUERY SEPARATION: Does the function either do something OR answer something, never both?

- [ ] Functions that **change state** (commands) should return `void`
- [ ] Functions that **return information** (queries) should not change state
- [ ] Never combine both -- it creates ambiguity

**Bad:**
```java
public boolean set(String attribute, String value);
// Usage becomes ambiguous:
if (set("username", "unclebob"))...
// Is this asking "was username previously set to unclebob"?
// Or "did setting username to unclebob succeed"?
```

The author intended `set` to be a verb, but in the `if` statement context it *feels* like an adjective -- "If the username attribute was previously set to unclebob." One could try renaming to `setAndCheckIfExists`, but that doesn't much help readability. The real solution is to separate command from query so ambiguity cannot occur.

**Good -- separate command and query:**
```java
if (attributeExists("username")) {
    setAttribute("username", "unclebob");
    ...
}
```

### 9. ERROR HANDLING: Exceptions over error codes, properly separated?

#### 9a. Prefer Exceptions to Returning Error Codes

- [ ] Do NOT return error codes -- they force callers into deeply nested `if` structures and violate command-query separation
- [ ] Error codes promote commands being used as expressions in `if` predicates: `if (deletePage(page) == E_OK)` -- this is a subtle CQS violation

**Bad -- error codes produce nesting:**
```java
if (deletePage(page) == E_OK) {
    if (registry.deleteReference(page.name) == E_OK) {
        if (configKeys.deleteKey(page.name.makeKey()) == E_OK) {
            logger.log("page deleted");
        } else {
            logger.log("configKey not deleted");
        }
    } else {
        logger.log("deleteReference from registry failed");
    }
} else {
    logger.log("delete failed");
    return E_ERROR;
}
```

**Good -- exceptions separate happy path from error handling:**
```java
try {
    deletePage(page);
    registry.deleteReference(page.name);
    configKeys.deleteKey(page.name.makeKey());
} catch (Exception e) {
    logger.log(e.getMessage());
}
```

#### 9b. Extract Try/Catch Blocks

- [ ] `try/catch` blocks are extracted into their own functions -- they are ugly and confuse the structure by mixing error processing with normal processing
- [ ] The function containing `try/catch` should do **nothing else** -- it begins with `try` and ends after `catch`/`finally`

**Good -- extracted error handling (three separate functions):**
```java
public void delete(Page page) {
    try {
        deletePageAndAllReferences(page);
    } catch (Exception e) {
        logError(e);
    }
}

private void deletePageAndAllReferences(Page page) throws Exception {
    deletePage(page);
    registry.deleteReference(page.name);
    configKeys.deleteKey(page.name.makeKey());
}

private void logError(Exception e) {
    logger.log(e.getMessage());
}
```

The `delete` function is all about error processing. `deletePageAndAllReferences` is all about the processes of fully deleting a page. Error handling can be ignored. Clean separation.

#### 9c. Error Handling Is One Thing

- [ ] A function that handles errors should do **nothing else**
- [ ] If `try` exists in a function, it should be the **first word** in the function
- [ ] There should be **nothing after** the `catch`/`finally` blocks

#### 9d. Error Enum / Dependency Magnet

- [ ] Do NOT use error code enums/classes -- they are **dependency magnets**
- [ ] Error code classes force recompilation and redeployment of all importing classes when they change, creating pressure to reuse old codes rather than add new ones

**Bad -- the `Error.java` dependency magnet:**
```java
public enum Error {
    OK,
    INVALID,
    NO_SUCH,
    LOCKED,
    OUT_OF_RESOURCES,
    WAITING_FOR_EVENT;
}
```
Many other classes must import and use this enum. When it changes, all those classes must be recompiled and redeployed. Programmers resist adding new error codes because of the rebuild/redeploy cost, so they reuse old ones instead.

- [ ] Use **exceptions** (which are derivatives of the exception class) instead -- new exceptions can be added without forcing recompilation of existing code (Open/Closed Principle)

### 10. DON'T REPEAT YOURSELF (DRY)

- [ ] No duplicated algorithm appearing in multiple places (even if not uniformly duplicated or intermixed with other code)
- [ ] Duplication is identified and extracted into a single function
- [ ] Four-fold duplication means four places to maintain and four opportunities for errors of omission

**Book reference:** In Listing 3-1, the same algorithm for finding and including pages was repeated four times for SetUp, SuiteSetUp, TearDown, and SuiteTearDown. In the refactored Listing 3-7, this was remedied by the single `include` method, dramatically improving readability.

Duplication may be the root of all evil in software. Structured programming, Aspect Oriented Programming, Component Oriented Programming, Codd's database normal forms, and OOP itself are all, in part, strategies for eliminating duplication.

### 11. STRUCTURED PROGRAMMING (Dijkstra's Rules)

- [ ] In **small functions**: multiple `return`, `break`, and `continue` statements are acceptable and can be more expressive than the single-entry, single-exit rule
- [ ] In **large functions** (which should not exist): one entry, one exit -- single `return`, no `break`/`continue` in loops, never `goto`
- [ ] `goto` should **never** be used (only makes sense in large functions, which should not exist)

## Violations to Detect

When reviewing code, scan for these specific anti-patterns. Each is keyed to a checklist section above.

| # | Violation | Detection Signal | Severity |
|---|-----------|-----------------|----------|
| V1 | **Long function** | >20 lines of code | HIGH |
| V2 | **Deep nesting** | Indent level >2 | HIGH |
| V3 | **Multiple responsibilities** | Function can be described with "and" or divided into sections | HIGH |
| V4 | **Mixed abstraction levels** | High-level calls next to low-level string/byte manipulation in same function | HIGH |
| V5 | **Exposed switch/if-else chain** | Switch on type not in a factory, or repeated in multiple functions | HIGH |
| V6 | **Vague or misleading name** | Name does not describe what function actually does; requires reading body to understand | MEDIUM |
| V7 | **Inconsistent naming** | Related functions use different verb/noun conventions (e.g., `fetch` in one, `get` in another, `retrieve` in a third for the same concept) | MEDIUM |
| V8 | **Too many arguments** | 3+ args (triadic or worse) | HIGH |
| V9 | **Flag argument** | Boolean parameter that controls branching behavior | HIGH |
| V10 | **Output argument** | Argument used to return/modify data instead of using return value or owning object | MEDIUM |
| V11 | **Hidden side effect** | Function does something not described by its name (e.g., `checkPassword` initializes session) | CRITICAL |
| V12 | **Temporal coupling** | Function can only be called at certain times due to hidden side effects, but this is not reflected in the name | HIGH |
| V13 | **Command-query mix** | Function both changes state AND returns a value describing state | HIGH |
| V14 | **Error code return** | Returning error enum/int instead of throwing exception | MEDIUM |
| V15 | **Unextracted try/catch** | `try/catch` mixed with business logic in the same function; code after catch block | MEDIUM |
| V16 | **Error code enum** | Centralized error code class/enum acting as dependency magnet | MEDIUM |
| V17 | **Duplicated logic** | Same algorithm/structure appears in 2+ places (even non-uniformly intermixed) | HIGH |
| V18 | **Long blocks in control structures** | Body of `if`/`else`/`while`/`for` is more than one line (should be a function call) | MEDIUM |
| V19 | **Sections within function** | Function body can be divided into labeled sections (declarations, init, work, cleanup) | MEDIUM |
| V20 | **Non-stepdown reading order** | Called functions defined before calling functions; reader cannot read top-down | LOW |

## How to Fix

### Fix for V1 (Long Function)
Extract smaller functions. Each extracted function should do one thing and have a descriptive name. The refactoring of `testableHtml` (Listing 3-1, ~70 lines) into `renderPageWithSetupsAndTeardowns` (Listing 3-2, ~12 lines) and finally (Listing 3-3, ~5 lines) demonstrates the progression.

### Fix for V2 (Deep Nesting)
Extract the nested block into a named function. Blocks within `if`/`else`/`while` should be one line long -- a function call. This simultaneously reduces nesting and documents intent through the function name.

### Fix for V3 (Multiple Responsibilities)
Apply the TO paragraph test. Write: "TO [functionName], we [description]." If the description contains "and" or multiple steps at different abstraction levels, split into multiple functions. Each extracted function should pass the TO test independently.

### Fix for V4 (Mixed Abstraction Levels)
Group statements by abstraction level. Extract low-level details into helper functions with descriptive names. The result should read like a top-down narrative where each function introduces the next (The Stepdown Rule).

Before:
```java
// Mixed: high-level getHtml() with low-level .append("\n")
WikiPage wikiPage = pageData.getWikiPage();
String pagePathName = PathParser.render(pagePath);
buffer.append("!include -setup .")
    .append(pagePathName)
    .append("\n");
```

After (as in Listing 3-7 SetupTeardownIncluder):
```java
// Each function at one consistent abstraction level
private void includeSetupPages() throws Exception {
    if (isSuite)
        includeSuiteSetupPage();
    includeSetupPage();
}

private void includeSuiteSetupPage() throws Exception {
    include(SuiteResponder.SUITE_SETUP_NAME, "-setup");
}

private void include(String pageName, String arg) throws Exception {
    WikiPage inheritedPage = findInheritedPage(pageName);
    if (inheritedPage != null) {
        String pagePathName = getPathNameForPage(inheritedPage);
        buildIncludeDirective(pagePathName, arg);
    }
}
```

### Fix for V5 (Exposed Switch Statement)
1. Create an abstract class or interface defining the polymorphic methods
2. Create an Abstract Factory with the switch statement buried inside
3. The factory returns concrete subclass instances
4. All client code calls methods on the abstract type -- the switch is never seen again
5. Tolerate switch only when: it appears once, creates polymorphic objects, and is hidden behind an inheritance relationship

### Fix for V6-V7 (Bad/Inconsistent Names)
- Replace vague names with descriptive ones: `testableHtml` becomes `SetupTeardownIncluder.render`
- Use consistent verb/noun families: if you have `includeSetupAndTeardownPages`, name siblings `includeSetupPages`, `includeSuiteSetupPage`, `includeSetupPage` (all use "include" + descriptive noun)
- Try several names; read the code with each; pick the one where every routine is "pretty much what you expected"
- A long descriptive name is BETTER than a short enigmatic name
- A long descriptive name is BETTER than a long descriptive comment

### Fix for V8 (Too Many Arguments)
1. **Wrap related args into an object:** `makeCircle(double x, double y, double radius)` becomes `makeCircle(Point center, double radius)`
2. **Make args instance variables:** If an arg is passed to every function in a class, make it a field (as in `SetupTeardownIncluder` where `pageData`, `isSuite`, `testPage`, `newPageContent`, `pageCrawler` are all fields)
3. **Extract a class:** Create a new class that takes some args in its constructor and provides a method for the operation
4. **Use the keyword form** for unavoidable multi-arg functions: `assertExpectedEqualsActual(expected, actual)`

### Fix for V9 (Flag Argument)
Split the function into two with descriptive names:
- `render(boolean isSuite)` becomes `renderForSuite()` and `renderForSingleTest()`
- Each function does exactly one thing without branching on a flag

### Fix for V10 (Output Argument)
- Use `return` for transformations: `StringBuffer transform(StringBuffer in)` not `void transform(StringBuffer out)`
- In OO languages, call the method on the owning object: `report.appendFooter()` not `appendFooter(report)`
- If a function must change state, change the state of **its owning object**

### Fix for V11-V12 (Hidden Side Effects / Temporal Coupling)
1. **Best:** Remove the side effect entirely -- extract it into its own function
2. **If coupling is necessary:** Rename the function to include both responsibilities: `checkPasswordAndInitializeSession` -- at least the caller knows what will happen (though this violates "do one thing")
3. **Never hide** state changes behind a name that does not describe them

### Fix for V13 (Command-Query Mix)
Separate into two functions:
```java
// BAD: command + query combined
if (set("username", "unclebob"))...

// GOOD: query then command, separate
if (attributeExists("username")) {
    setAttribute("username", "unclebob");
}
```

### Fix for V14-V16 (Error Code Returns / Unextracted Try-Catch / Error Enum)
1. Replace error codes with exceptions
2. Extract `try/catch` into its own function where `try` is the first word and nothing follows `catch`/`finally`
3. Create the happy-path logic in a separate function called from within `try`
4. Replace error code enums with exception class hierarchies -- new exceptions can be added without recompilation of dependents (Open/Closed Principle)

### Fix for V17 (Duplicated Logic)
Extract the duplicated algorithm into a single function parameterized for the variations. In Listing 3-7, the four instances of the include-page algorithm (SetUp, SuiteSetUp, TearDown, SuiteTearDown) were collapsed into a single `include(String pageName, String arg)` method.

### Fix for V18-V19 (Long Blocks / Sections in Functions)
Extract blocks into named functions. If a function has identifiable sections (declarations, initializations, sieve), it is doing more than one thing. Each section should become its own function.

### Fix for V20 (Non-Stepdown Order)
Reorder functions so that callers appear above callees. The reader should be able to read the file top-to-bottom, encountering each function just after the function that calls it, descending one abstraction level at a time.

## The Writing Process

Functions do NOT emerge perfectly on the first draft. Martin's own process:

1. **First draft:** Long functions with lots of indenting and nested loops, long argument lists, arbitrary names, duplicated code
2. **Unit tests:** A suite of tests covering every line of the clumsy first draft
3. **Refine:** Massage and refine the code -- split functions, change names, eliminate duplication, shrink methods, reorder. Sometimes break out whole classes.
4. **Keep tests passing** throughout the entire process
5. **End result:** Functions that follow all the rules in this chapter

"I don't write them that way to start. I don't think anyone could."

## Conclusion: Functions as Language Design

Every system is built from a domain-specific language designed by its programmers. **Functions are the verbs** of that language; **classes are the nouns**. Master programmers think of systems as *stories to be told* rather than programs to be written. They use their programming language to construct a richer, more expressive domain-specific language that tells that story. The hierarchy of functions describes all the actions that take place within the system -- and in an artful act of recursion, those actions are written to use the very domain-specific language they define to tell their own small part of the story.

Your real goal is never just to make functions follow rules. It is to make functions **tell the story of the system** -- to fit cleanly together into a clear and precise language.

## The Gold Standard: SetupTeardownIncluder (Listing 3-7)

The complete refactored class (Listing 3-7) demonstrates every principle simultaneously:

```java
package fitnesse.html;

import fitnesse.responders.run.SuiteResponder;
import fitnesse.wiki.*;

public class SetupTeardownIncluder {
    private PageData pageData;
    private boolean isSuite;
    private WikiPage testPage;
    private StringBuffer newPageContent;
    private PageCrawler pageCrawler;

    public static String render(PageData pageData) throws Exception {
        return render(pageData, false);
    }

    public static String render(PageData pageData, boolean isSuite)
        throws Exception {
        return new SetupTeardownIncluder(pageData).render(isSuite);
    }

    private SetupTeardownIncluder(PageData pageData) {
        this.pageData = pageData;
        testPage = pageData.getWikiPage();
        pageCrawler = testPage.getPageCrawler();
        newPageContent = new StringBuffer();
    }

    private String render(boolean isSuite) throws Exception {
        this.isSuite = isSuite;
        if (isTestPage())
            includeSetupAndTeardownPages();
        return pageData.getHtml();
    }

    private boolean isTestPage() throws Exception {
        return pageData.hasAttribute("Test");
    }

    private void includeSetupAndTeardownPages() throws Exception {
        includeSetupPages();
        includePageContent();
        includeTeardownPages();
        updatePageContent();
    }

    private void includeSetupPages() throws Exception {
        if (isSuite)
            includeSuiteSetupPage();
        includeSetupPage();
    }

    private void includeSuiteSetupPage() throws Exception {
        include(SuiteResponder.SUITE_SETUP_NAME, "-setup");
    }

    private void includeSetupPage() throws Exception {
        include("SetUp", "-setup");
    }

    private void includePageContent() throws Exception {
        newPageContent.append(pageData.getContent());
    }

    private void includeTeardownPages() throws Exception {
        includeTeardownPage();
        if (isSuite)
            includeSuiteTeardownPage();
    }

    private void includeTeardownPage() throws Exception {
        include("TearDown", "-teardown");
    }

    private void includeSuiteTeardownPage() throws Exception {
        include(SuiteResponder.SUITE_TEARDOWN_NAME, "-teardown");
    }

    private void updatePageContent() throws Exception {
        pageData.setContent(newPageContent.toString());
    }

    private void include(String pageName, String arg) throws Exception {
        WikiPage inheritedPage = findInheritedPage(pageName);
        if (inheritedPage != null) {
            String pagePathName = getPathNameForPage(inheritedPage);
            buildIncludeDirective(pagePathName, arg);
        }
    }

    private WikiPage findInheritedPage(String pageName) throws Exception {
        return PageCrawlerImpl.getInheritedPage(pageName, testPage);
    }

    private String getPathNameForPage(WikiPage page) throws Exception {
        WikiPagePath pagePath = pageCrawler.getFullPath(page);
        return PathParser.render(pagePath);
    }

    private void buildIncludeDirective(String pagePathName, String arg) {
        newPageContent
            .append("\n!include ")
            .append(arg)
            .append(" .")
            .append(pagePathName)
            .append("\n");
    }
}
```

This class demonstrates every principle simultaneously:

- **Small functions:** Every method is 1-4 lines (longest is `include` at 5 lines of logic)
- **One thing each:** `render()` renders, `isTestPage()` checks test status, `includeSetupAndTeardownPages()` orchestrates includes, `include()` does a single include
- **One abstraction level:** `includeSetupAndTeardownPages` calls `includeSetupPages`, `includePageContent`, `includeTeardownPages`, `updatePageContent` -- all at the same level
- **Stepdown rule:** Reader descends from `render` -> `includeSetupAndTeardownPages` -> `includeSetupPages` -> `includeSuiteSetupPage` / `includeSetupPage` -> `include` -> `findInheritedPage` / `getPathNameForPage` / `buildIncludeDirective`
- **Descriptive names:** Every function name says exactly what it does
- **Few arguments:** Most are niladic (zero args); `include` takes 2 (pageName, arg); the private helper `buildIncludeDirective` takes 2
- **No side effects:** Each function does only what its name says
- **DRY:** The single `include` method replaces the four-fold duplication in the original
- **Instance variables over arguments:** `pageData`, `isSuite`, `testPage`, `newPageContent`, `pageCrawler` are fields, not passed as arguments everywhere

## Self-Improvement Protocol

After each review using this skill:

1. **Track violation frequency:** Note which violations appear most often in the codebase. Prioritize fixing the most common ones.
2. **Before/after comparison:** For each refactored function, verify the refactored version passes every checklist item that the original failed.
3. **Test coverage gate:** Never refactor without a passing test suite. Run tests after every change.
4. **Name quality audit:** After refactoring, re-read function names top-to-bottom. Does the code read like a top-down narrative? Can you understand the module without reading function bodies?
5. **Argument count trend:** Track the distribution of niladic/monadic/dyadic/triadic functions across the codebase over time. The ratio should shift toward fewer arguments.
6. **Duplication scan:** After fixing one instance of duplication, search the entire codebase for the same pattern. Duplication often appears in multiple files.
7. **Incremental application:** When encountering a massive legacy function, do not attempt a full rewrite. Apply one rule at a time (extract one sub-function, rename one thing, remove one flag argument) and verify tests pass after each step.
8. **Review feedback loop:** When a reviewer flags a function issue, map it to a specific violation number (V1-V20) and the corresponding fix. This builds a shared vocabulary for the team.
