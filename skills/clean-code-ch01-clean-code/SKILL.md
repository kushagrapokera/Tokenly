---
name: clean-code-ch01-clean-code
description: "Code quality checker based on Clean Code Ch1: Clean Code -- checks overall code cleanliness philosophy, readability, minimal dependencies, expressiveness, and the Boy Scout Rule. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 1: Clean Code -- Code Quality Checker

## When to Use

- When reviewing any code for quality (pull requests, code reviews, refactoring sessions)
- When writing new code and wanting to verify it meets clean code standards
- When evaluating whether a codebase is accumulating technical debt
- When deciding whether to refactor vs. rewrite a module
- When assessing if code is "wading" territory (tangled, hard to navigate)
- When checking if a commit leaves the code cleaner than it was found (Boy Scout Rule)
- When onboarding to a new codebase and assessing its health
- Before any merge to main/master -- final cleanliness gate check

## Core Philosophy

### There Will Be Code

Code will always exist. It is the language in which we express requirements with the precision machines demand. Higher-level languages and DSLs will emerge, but they are still code. There is no future where code disappears. Therefore, code quality is a permanent professional concern.

Specifying requirements at the detail a machine can execute them *is* programming. A specification at that level of detail *is* code. We will never eliminate necessary precision -- so there will always be code. The notion that code will one day disappear is as misguided as mathematicians hoping for a mathematics that does not have to be formal.

### Bad Code

Kent Beck, in the preface to *Implementation Patterns*, calls the premise that good code matters "a rather fragile premise." Martin disagrees -- it is one of the most robust, supported, and overloaded of all the premises in our craft. We know good code matters because we have had to deal for so long with its lack.

**Wading**: When programmers encounter bad code, they *wade* through it -- slogging through a morass of tangled brambles and hidden pitfalls, struggling to find their way, hoping for some hint, some clue, while all they see is more and more senseless code.

Bad code can bring a company down. Martin recounts a company in the late 80s that wrote a *killer* app -- popular and widely used -- but bugs went unrepaired, load times grew, crashes increased. They had rushed to market, made a huge mess, and as they added features the code got worse until they could not manage it. *It was the bad code that brought the company down.*

### The Total Cost of Owning a Mess

As the mess builds, productivity of the team continues to decrease, asymptotically approaching zero. Management adds more staff, but the new staff do not understand the design of the system. They do not know the difference between a change that matches the design intent and one that thwarts it. Under pressure to increase productivity, they all make more messes, driving productivity ever further toward zero. (See Figure 1-1: Productivity vs. Time -- a steep decline curve.)

### The Grand Redesign in the Sky

Eventually the team rebels and demands a redesign. Management authorizes a **tiger team** to build a new system from scratch, while everyone else maintains the old one. The two teams race: the new system must do everything the old one does, plus keep up with ongoing changes. This race can go on for a **very long time** -- Martin has seen it take 10 years. By the time it is done, the original tiger team members are long gone, and the current members are demanding a redesign of the new system because it is now such a mess. Keeping code clean is not just cost effective; it is a matter of **professional survival**.

### Attitude

Why does good code rot so quickly into bad code? We blame requirements changes, tight schedules, stupid managers. But the fault is in ourselves -- we are unprofessional. Managers and marketers look to *us* for the information they need to make promises. We are deeply complicit in the planning and share responsibility for failures.

"Most managers want the truth, even when they don't act like it. Most managers want good code, even when they are obsessing about the schedule." It is *your* job to defend the code with equal passion.

The doctor/hand-washing analogy: A patient demands the doctor skip hand-washing because it takes too much time. The doctor should refuse -- the doctor knows the risks of disease and infection better than the patient. So too it is unprofessional for programmers to bend to the will of managers who don't understand the risks of making messes. (Historical note: hand-washing was first recommended to physicians by Ignaz Semmelweis in 1847 and was rejected because doctors were "too busy.")

### The Primal Conundrum

LeBlanc's Law: **Later equals never.** If you leave a mess intending to clean it up later, you never will.

Developers know messes slow them down, yet feel pressure to make messes to meet deadlines. The resolution: **the only way to go fast is to keep the code clean at all times.** You will *not* make the deadline by making the mess. The mess will slow you down instantly and will force you to miss the deadline. The *only* way to make the deadline is to keep the code as clean as possible at all times.

### The Art of Clean Code?

Writing clean code is like painting a picture. Most of us can recognize good art, but that does not mean we know how to paint. Recognizing clean code does not mean you know how to write it.

Writing clean code requires the disciplined use of a myriad of little techniques applied through a painstakingly acquired sense of "cleanliness." This **"code-sense"** is the key. Some are born with it; some must fight to acquire it. It not only lets us see whether code is good or bad, but also shows us the strategy for transforming bad code into clean code.

- A programmer **without** "code-sense" can look at a messy module and recognize the mess but will have no idea what to do about it.
- A programmer **with** "code-sense" will look at a messy module and see options and variations. The "code-sense" will help that programmer choose the best variation and guide a sequence of **behavior-preserving transformations** to get from here to there.

In short, a programmer who writes clean code is an **artist** who can take a blank screen through a series of transformations until it is an elegantly coded system.

## Definitions of Clean Code -- Master Checklist

### 1. Bjarne Stroustrup (inventor of C++): Elegant and Efficient

> "I like my code to be elegant and efficient. The logic should be straightforward to make it hard for bugs to hide, the dependencies minimal to ease maintenance, error handling complete according to an articulated strategy, and performance close to optimal so as not to tempt people to make the code messy with unprincipled optimizations. Clean code does one thing well."

**Checklist items derived:**
- 1.1. **Elegance**: Code should be *pleasing* to read -- graceful, stylish, ingenious yet simple
- 1.2. **Efficiency**: Performance should be close to optimal (not necessarily micro-optimized, but not wasteful)
- 1.3. **Straightforward logic**: Control flow and logic should be obvious; no hidden paths where bugs can lurk
- 1.4. **Minimal dependencies**: Modules/classes/functions should have the fewest possible external dependencies
- 1.5. **Complete error handling**: Every error case is handled according to a deliberate, articulated strategy -- not glossed over or abbreviated
- 1.6. **Does one thing well**: Each function, class, and module is *focused* -- single-minded in purpose, undistracted by surrounding concerns
- 1.7. **No temptation to make it worse**: Code should not invite "broken windows" -- bad code *tempts* the mess to grow; when others change bad code, they tend to make it worse. (The "broken windows" metaphor comes from Pragmatic Dave Thomas and Andy Hunt: a building with broken windows looks like nobody cares, so others stop caring, more windows break, graffiti appears, garbage collects. One broken window starts the process toward decay.)

### 2. Grady Booch (author of Object Oriented Analysis and Design with Applications): Reads Like Prose

> "Clean code is simple and direct. Clean code reads like well-written prose. Clean code never obscures the designer's intent but rather is full of crisp abstractions and straightforward lines of control."

**Checklist items derived:**
- 2.1. **Simple and direct**: No unnecessary complexity or indirection
- 2.2. **Reads like well-written prose**: Code should be narrative -- you read it and understand the story being told, like reading a good book
- 2.3. **Designer's intent is clear**: The *why* behind the code is never obscured; purpose is obvious
- 2.4. **Crisp abstractions**: "Crisp" is a fascinating oxymoron paired with "abstraction" -- the dictionary defines "crisp" as *briskly decisive and matter-of-fact, without hesitation or unnecessary detail*. Code should contain only what is necessary, be matter-of-fact as opposed to speculative, and our readers should perceive us to have been decisive.
- 2.5. **Straightforward lines of control**: Control flow is linear and predictable; no tangled paths
- 2.6. **Reads like a good novel**: Like a good novel, clean code should clearly expose the tensions in the problem to be solved, build those tensions to a climax, and then give the reader that "Aha! Of course!" as the issues are resolved in the revelation of an obvious solution.

### 3. "Big" Dave Thomas (founder of OTI, godfather of Eclipse): Readable, Tested, Minimal

> "Clean code can be read, and enhanced by a developer other than its original author. It has unit and acceptance tests. It has meaningful names. It provides one way rather than many ways for doing one thing. It has minimal dependencies, which are explicitly defined, and provides a clear and minimal API. Code should be literate since depending on the language, not all necessary information can be expressed clearly in code alone."

**Checklist items derived:**
- 3.1. **Readable and enhanceable by others**: Not just easy to read -- easy for someone *else* to modify and improve. There is a crucial difference between code that is easy to read and code that is easy to change; Dave emphasizes both.
- 3.2. **Has unit and acceptance tests**: Code without tests is not clean, period. No matter how elegant or readable.
- 3.3. **Meaningful names**: Variables, functions, classes, modules all have names that communicate intent
- 3.4. **One way to do each thing**: Does not offer multiple paths for the same operation -- provides a single, clear approach
- 3.5. **Minimal, explicitly defined dependencies**: Dependencies are few, and each is clearly declared
- 3.6. **Clear and minimal API**: The public interface is small and obvious
- 3.7. **Literate**: Code should be composed in a form readable by humans; supplemented by comments/docs where the language cannot express everything. This is a soft reference to Knuth's *literate programming* [Knuth92].
- 3.8. **Smaller is better**: Dave uses the word *minimal* twice. Code that is small is valued over code that is large. This has been a common refrain throughout software literature since its inception.

### 4. Michael Feathers (author of Working Effectively with Legacy Code): Written by Someone Who Cares

> "I could list all of the qualities that I notice in clean code, but there is one overarching quality that leads to all of them. Clean code always looks like it was written by someone who cares. There is nothing obvious that you can do to make it better. All of those things were thought about by the code's author, and if you try to imagine improvements, you're led back to where you are, sitting in appreciation of the code someone left for you -- code left by someone who cares deeply about the craft."

**Checklist items derived:**
- 4.1. **Looks like someone cared**: The code has clearly had thought and attention invested in it
- 4.2. **Nothing obvious to improve**: When you look at the code, you cannot see an easy way to make it better
- 4.3. **Simple and orderly**: Someone took the time to keep it that way
- 4.4. **Appropriate attention to details**: Every aspect has been considered

### 5. Ron Jeffries (author of Extreme Programming Installed): Simple Code Rules

> "In recent years I begin, and nearly end, with Beck's rules of simple code. In priority order, simple code: Runs all the tests; Contains no duplication; Expresses all the design ideas that are in the system; Minimizes the number of entities such as classes, methods, functions, and the like."

**Checklist items derived:**
- 5.1. **Runs all the tests**: The code passes its complete test suite -- correctness is non-negotiable
- 5.2. **Contains no duplication**: Duplication is the primary enemy. When the same thing is done repeatedly, it signals an idea not well represented in code. Extract and name it.
- 5.3. **Expresses all design ideas**: Meaningful names, small focused classes/methods. Expressiveness includes names, method extraction, and using standard pattern names (e.g., COMMAND, VISITOR) when applicable.
- 5.4. **Minimizes entities**: After eliminating duplication and maximizing expressiveness, reduce the number of classes, methods, and functions. Smaller is better.
- 5.5. **Early building of simple abstractions**: When patterns like "find things in a collection" recur, wrap them in an abstract method or class to clarify intent and reduce implementation noise.

**Ron Jeffries' extended commentary on expressiveness**: Expressiveness goes beyond names. He also looks at whether an object or method is doing more than one thing. If it is an object, it probably needs to be broken into two or more objects. If it is a method, he will always use the **Extract Method** refactoring, resulting in one method that says more clearly what it does, and some submethods saying how it is done. He changes the names of things several times before settling in -- with modern IDE tools, renaming is inexpensive.

**Ron Jeffries' summary of clean code: No duplication, one thing, expressiveness, tiny abstractions.**

### 6. Ward Cunningham (inventor of Wiki, Fit, coinventor of eXtreme Programming): No Surprises

> "You know you are working on clean code when each routine you read turns out to be pretty much what you expected. You can call it beautiful code when the code also makes it look like the language was made for the problem."

**Checklist items derived:**
- 6.1. **No surprises**: Each routine does pretty much what you expected when you read its name/signature
- 6.2. **Obvious and simple**: You read it, nod, and move on -- it does not puzzle, complicate, or misdirect
- 6.3. **Each module sets the stage for the next**: Reading one module tells you how the next will be written
- 6.4. **Makes the language look like it was made for the problem**: Beautiful code doesn't fight the language; it uses the language so naturally that the solution appears inevitable
- 6.5. **Ridiculously simple**: Programs that are *that* clean look simple like all exceptional designs -- the designer made it look easy
- 6.6. **It is the programmer's responsibility, not the language's**: Beautiful code *makes the language look like it was made for the problem*. It is not the language that makes programs appear simple -- it is the programmer who makes the language appear simple. Language bigots everywhere, beware!

## Full Checklist -- All Principles

### A. Foundational Principles

1. **Code represents requirements at the level of precision machines demand** -- never treat code as a second-class artifact
2. **Later equals never** -- never leave a mess intending to clean it up "later"
3. **The only way to go fast is to keep the code clean** -- messes slow you down immediately, not just eventually
4. **Productivity decreases asymptotically toward zero as mess builds** -- every change breaks two or three other things; every modification requires understanding tangles of knots
5. **Bad code can bring a company down** -- this is not hypothetical; companies have gone out of business because of unmanageable codebases
6. **It is unprofessional to make messes under pressure** -- defend code quality the way a doctor defends hygiene
7. **"Code-sense" is key** -- the ability to look at messy code, see options and variations, and plot behavior-preserving transformations to clean it

### B. Structural Cleanliness

8. **Each function does one thing** (Stroustrup, Jeffries)
9. **Each class has a single responsibility** (Stroustrup -- "focused", Jeffries -- minimize entities)
10. **Each module exposes a single-minded attitude** -- undistracted and unpolluted by surrounding details (Stroustrup)
11. **Dependencies are minimal** (Stroustrup, Dave Thomas)
12. **Dependencies are explicitly defined** (Dave Thomas)
13. **APIs are clear and minimal** (Dave Thomas)
14. **One way to do each thing** -- do not provide multiple paths for the same operation (Dave Thomas)
15. **Minimize the number of entities** -- classes, methods, functions (Jeffries)

### C. Readability and Expressiveness

16. **Code reads like well-written prose** (Booch)
17. **Meaningful names that communicate intent** (Dave Thomas, Jeffries)
18. **Designer's intent is never obscured** (Booch)
19. **Crisp abstractions** -- matter-of-fact, decisive, only what is necessary (Booch)
20. **Straightforward lines of control** (Booch, Stroustrup)
21. **Code is literate** -- readable by humans, supplemented where language falls short (Dave Thomas)
22. **Expresses all design ideas in the system** (Jeffries)
23. **No surprises -- each routine does what you'd expect from its name** (Ward Cunningham)
24. **Makes the language look like it was made for the problem** (Ward Cunningham)

### D. Error Handling and Robustness

25. **Error handling is complete** -- not abbreviated, not glossed over (Stroustrup)
26. **Error handling follows an articulated strategy** -- consistent approach, not ad-hoc (Stroustrup)
27. **No memory leaks, race conditions, or inconsistent naming** -- attention to details matters (Stroustrup commentary)

### E. Testing

28. **Code has unit tests** (Dave Thomas)
29. **Code has acceptance tests** (Dave Thomas)
30. **Code without tests is not clean** -- "No matter how elegant it is, no matter how readable and accessible, if it hath not tests, it be unclean" (Dave Thomas commentary by Martin)
31. **All tests run and pass** (Jeffries -- rule #1 of simple code)

### F. Duplication

32. **Contains no duplication** (Jeffries -- rule #2 of simple code)
33. **When the same thing is done repeatedly, extract and name the concept** (Jeffries)
34. **Build simple abstractions early** to eliminate repetitive patterns (Jeffries)

### G. Care and Craftsmanship

35. **Code looks like it was written by someone who cares** (Feathers)
36. **Nothing obvious you can do to improve it** (Feathers)
37. **Someone took the time to keep it simple and orderly** (Feathers)
38. **Appropriate attention paid to every detail** (Feathers)

### H. The Boy Scout Rule

39. **Leave the code cleaner than you found it** -- every commit, every touch. Adapted from the Boy Scouts of America rule: *"Leave the campground cleaner than you found it."* (Originally from Robert Stephenson Smyth Baden-Powell's farewell message: "Try and leave this world a little better than you found it...")
40. **Continuous improvement**: rename one variable for clarity, break up one too-large function, eliminate one small duplication, simplify one composite `if` statement
41. **Code should get better over time**, not worse -- active prevention of code rot

### I. We Are Authors

42. **We are authors** -- the `@author` field of a Javadoc tells us who we are. Authors are *responsible* for communicating well with their readers. Every line of code you write is communication to the next developer.
43. **Code is read far more than it is written** -- the read-to-write ratio exceeds 10:1. Martin demonstrated this by playing back edit sessions in 80s/90s editors like Emacs: the vast majority of the playback was scrolling and navigating to other modules, not typing. You cannot write code if you cannot read the surrounding code.
44. **Making code easy to read makes it easier to write** -- readability is not a luxury, it is a prerequisite for velocity. There is no escape from this logic: if you want to go fast, if you want your code to be easy to write, make it easy to read.

### J. Schools of Thought

45. **This book represents one school of thought** -- the Object Mentor School of Clean Code -- not absolute truth. Like martial arts schools (Gracie Jiu Jitsu, Hakkoryu Jiu Jitsu, Jeet Kune Do), there are other schools with equally valid perspectives.
46. **Act within the school**: Within a particular school, we *act* as though the teachings *are* right. There is a right way to practice within a school, and this rightness does not invalidate other schools.
47. **Recommendations are born of decades of experience** -- learned through trial and error. They are controversial; you may disagree. But it would be a shame not to see and respect the point of view.

### K. Prequel and Principles

48. **This book references key design principles**: Single Responsibility Principle (SRP), Open Closed Principle (OCP), Dependency Inversion Principle (DIP) among others, described in depth in *Agile Software Development: Principles, Patterns, and Practices* (PPP).
49. **Clean Code is the code-level sequel to PPP**: PPP concerns object-oriented design principles and professional practices; Clean Code continues that story at the level of code itself.

### L. Conclusion -- Practice

50. **A book about code cannot promise to make you a good programmer** -- just as a book on art cannot promise to make you an artist. It can only show you the thought processes, tricks, techniques, and tools of good programmers.
51. **Practice, Practice, Practice**: The final message of the chapter is the old joke about the concert violinist asking how to get to Carnegie Hall -- "Practice, son. Practice!" Reading is not enough; you must practice writing clean code.

## Violations to Detect

### V1. Broken Windows -- Code That Invites Decay

**Bad:**
```python
# TODO: fix this later
def calc(x, y, z, flag, mode, extra=None):
    if flag:
        # don't know why this works
        result = x * y + z
    else:
        result = x * y + z  # same thing??
    if mode == 1:
        pass  # not implemented
    elif mode == 2:
        pass  # also not implemented
    return result
```

**Good:**
```python
def calculate_area(width: float, height: float) -> float:
    """Calculate the rectangular area from width and height."""
    return width * height
```

**Detection patterns:**
- TODO/FIXME/HACK/XXX comments that have been present for more than one sprint
- Commented-out code blocks
- Functions with `pass` or `NotImplementedError` in production code
- Comments like "don't know why", "this works somehow", "fix later"

### V2. Functions That Do More Than One Thing

**Bad:**
```java
public void processOrder(Order order) {
    // validate
    if (order.getItems().isEmpty()) throw new RuntimeException("empty");
    // calculate totals
    double total = 0;
    for (Item item : order.getItems()) {
        total += item.getPrice() * item.getQuantity();
    }
    // apply discount
    if (total > 100) total *= 0.9;
    // save to database
    db.save(order);
    // send email
    emailService.sendConfirmation(order);
    // update inventory
    for (Item item : order.getItems()) {
        inventory.decrease(item.getId(), item.getQuantity());
    }
}
```

**Good:**
```java
public void processOrder(Order order) {
    validateOrder(order);
    double total = calculateTotal(order);
    total = applyDiscounts(total);
    persistOrder(order, total);
    notifyCustomer(order);
    updateInventory(order);
}
```

**Detection patterns:**
- Functions longer than ~20 lines (heuristic)
- Functions with multiple comment blocks describing "sections"
- Functions with the word "and" in their name (e.g., `validateAndSave`)
- Multiple levels of abstraction within one function

### V3. Missing or Incomplete Error Handling

**Bad:**
```python
def read_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        pass  # swallowed exception
```

**Good:**
```python
def read_config(path: str) -> dict:
    """Read and parse JSON configuration file.

    Raises:
        FileNotFoundError: If config file does not exist.
        json.JSONDecodeError: If config file contains invalid JSON.
    """
    with open(path) as f:
        return json.load(f)
```

**Detection patterns:**
- Bare `except:` or `except Exception:` with `pass`
- Empty catch blocks in Java/C#/Go
- Functions that return `None`/`null`/`nil` on error without explanation
- Error codes returned but never checked by callers
- `// TODO: handle error` comments

### V4. Duplication

**Bad:**
```javascript
function getAdminUsers(users) {
    const result = [];
    for (const user of users) {
        if (user.role === 'admin' && user.active) {
            result.push({ name: user.name, email: user.email });
        }
    }
    return result;
}

function getEditorUsers(users) {
    const result = [];
    for (const user of users) {
        if (user.role === 'editor' && user.active) {
            result.push({ name: user.name, email: user.email });
        }
    }
    return result;
}
```

**Good:**
```javascript
function getActiveUsersByRole(users, role) {
    return users
        .filter(user => user.role === role && user.active)
        .map(({ name, email }) => ({ name, email }));
}
```

**Detection patterns:**
- Functions with identical structure differing only in one or two values
- Copy-pasted blocks with minor variations
- Repeated conditional patterns (same `if` structure in multiple places)
- Identical loops over the same data structure in different functions

### V5. Obscured Intent / Poor Naming

**Bad:**
```go
func proc(d []int, f int) int {
    r := 0
    for _, v := range d {
        if v > f {
            r += v
        }
    }
    return r
}
```

**Good:**
```go
func sumValuesAboveThreshold(values []int, threshold int) int {
    total := 0
    for _, value := range values {
        if value > threshold {
            total += value
        }
    }
    return total
}
```

**Detection patterns:**
- Single-letter variable names outside of trivial loop counters (`i`, `j`, `k`)
- Function names that are abbreviations or acronyms (`proc`, `calc`, `mgr`, `svc`)
- Variable names that are types rather than purposes (`string1`, `list2`, `data`, `info`, `temp`)
- Names that require a comment to explain what they mean

### V6. No Tests

**Bad:** Any production code module without a corresponding test file.

**Good:** Every module has tests that verify its behavior.

**Detection patterns:**
- Source files with no corresponding `*_test.*`, `*.test.*`, `*.spec.*`, or `test_*.*` file
- Test files that exist but contain no assertions
- Test files that are all commented out or skipped (`@Ignore`, `skip`, `xit`, `xdescribe`)
- Test coverage below meaningful thresholds

### V7. Excessive Dependencies

**Bad:**
```python
# A single module importing half the system
from auth import authenticate, authorize, get_user, get_permissions
from database import connect, query, insert, update, delete, transaction
from cache import get_cache, set_cache, invalidate
from email import send_email, send_sms, send_push
from logging import log_info, log_error, log_debug, log_warning
from validation import validate_email, validate_phone, validate_address
from formatting import format_date, format_currency, format_name
```

**Good:** Module depends only on what it directly needs; functionality is delegated to focused collaborators.

**Detection patterns:**
- Files with more than ~10 import statements
- Modules that import from 5+ different packages/modules
- Circular dependencies
- God objects or utility classes that everything depends on

### V8. Code That Surprises -- Violating the Principle of Least Astonishment

**Bad:**
```java
// Method named "getUser" but also modifies state
public User getUser(int id) {
    User user = db.find(id);
    user.setLastAccessed(new Date());  // surprise side effect!
    db.save(user);                      // surprise persistence!
    auditLog.record("accessed", id);    // surprise logging!
    return user;
}
```

**Good:**
```java
public User getUser(int id) {
    return db.find(id);
}

public void recordUserAccess(int userId) {
    User user = db.find(userId);
    user.setLastAccessed(new Date());
    db.save(user);
    auditLog.record("accessed", userId);
}
```

**Detection patterns:**
- `get*` methods that modify state
- Functions whose names suggest queries but perform mutations
- Methods with non-obvious side effects (sending emails, writing files, modifying globals)
- Boolean parameters that fundamentally change behavior (`process(data, true)`)

### V9. Complexity That Invites Unprincipled Optimization

**Bad:**
```python
# Prematurely optimized, unreadable
def f(n):
    return n & (n - 1) == 0 and n != 0  # is power of 2?
```

**Good:**
```python
import math

def is_power_of_two(number: int) -> bool:
    """Check if a positive integer is a power of two."""
    if number <= 0:
        return False
    return math.log2(number).is_integer()
```

**Detection patterns:**
- Bitwise operations without clear documentation of purpose
- "Clever" one-liners that require mental compilation to understand
- Performance optimizations without benchmarks or comments explaining necessity
- Code where someone has sacrificed readability for speed without measurement

### V10. The Grand Redesign Smell -- Signs of Terminal Mess

**Detection patterns (project-level):**
- Productivity on the project has dramatically decreased over time
- New features that used to take days now take weeks
- Every change introduces unexpected regressions
- Team is discussing a "rewrite from scratch"
- New team members take months to become productive
- Fear of modifying existing code is pervasive

## How to Fix

### Remediation Pattern 1: Apply the Boy Scout Rule Incrementally
Do not attempt big-bang refactors. Each time you touch a file:
- Rename one unclear variable
- Extract one well-named method from a long function
- Remove one instance of duplication
- Add one missing test
- Simplify one complex conditional

### Remediation Pattern 2: Add Tests Before Refactoring
Before changing any code, ensure tests exist that characterize its current behavior. This provides a safety net for transformation.

### Remediation Pattern 3: Extract Until You Drop
When a function does multiple things:
1. Identify each "thing" (often marked by comment blocks or blank lines separating sections)
2. Extract each section into a well-named private method
3. The original function becomes a readable outline of steps

### Remediation Pattern 4: Eliminate Duplication Through Abstraction
1. Identify two or more similar code blocks
2. Determine what varies between them
3. Extract the common pattern into a function/method, parameterizing the varying parts
4. Replace all instances with calls to the new abstraction

### Remediation Pattern 5: Complete the Error Handling
1. Identify every point of failure (I/O, parsing, network, allocation)
2. Decide on a strategy: exceptions, error returns, Result types
3. Apply the strategy consistently across the module
4. Ensure no errors are silently swallowed

### Remediation Pattern 6: Improve Names Until Intent Is Obvious
1. Read a function/variable name and ask: "Would a new team member understand this?"
2. If no, rename it to communicate purpose, not implementation
3. Use domain language, not technical jargon
4. Longer descriptive names are better than short cryptic ones

### Remediation Pattern 7: Reduce Dependencies
1. Apply the Dependency Inversion Principle -- depend on abstractions, not concretions
2. Use dependency injection to make dependencies explicit
3. Split god-classes into focused collaborators
4. Question each import: "Does this module truly need this dependency?"

### Remediation Pattern 8: Make Code Unsurprising
1. Ensure every function does what its name says and nothing more
2. Separate queries (return data, no side effects) from commands (perform actions)
3. Remove hidden side effects
4. If a function must do something unexpected, rename it to include that behavior

## Self-Improvement Protocol

When reviewing code against this skill:

1. **Systematic scan**: For each checklist item (1-51), search for violations using Grep/Glob across the target codebase
   - Search for TODO/FIXME/HACK comments: `Grep pattern="(TODO|FIXME|HACK|XXX)" type="<language>"`
   - Search for empty catch/except blocks: `Grep pattern="(except.*pass|catch.*\{\s*\})" type="<language>"`
   - Search for overly long functions: use language-appropriate tools to measure function length
   - Search for duplication: look for functions with similar names or identical structure
   - Search for poor names: `Grep pattern="(data|info|temp|tmp|foo|bar|baz|x|y|z)\b" type="<language>"` in variable declarations
   - Search for missing tests: `Glob pattern="src/**/*.<ext>"` then verify corresponding test files exist
   - Search for excessive imports: check files with many import/require/include statements

2. **Log new patterns**: If violations are discovered that don't match existing patterns in this skill, document the new pattern with:
   - What the violation looks like (code example)
   - Which principle(s) it violates (reference checklist numbers)
   - How to fix it

3. **Append discoveries**: If new violation patterns are found, append them to the "Violations to Detect" section above with the next sequential number (V11, V12, etc.)

4. **Cross-reference**: Check findings against other Clean Code chapter skills:
   - Chapter 2 (Meaningful Names) for naming violations
   - Chapter 3 (Functions) for function-level violations
   - Chapter 4 (Comments) for comment-related issues
   - Chapter 5 (Formatting) for structural formatting
   - Chapter 6 (Objects and Data Structures) for abstraction issues
   - Chapter 7 (Error Handling) for error handling completeness
   - Chapter 9 (Unit Tests) for testing concerns
   - Chapter 10 (Classes) for class-level organization
   - Chapter 17 (Smells and Heuristics) for the comprehensive smell catalog

5. **Severity scoring**: Rate each finding:
   - **Critical**: Violates principles 2, 3, 5, 25-27, 28-31 (missing tests, swallowed errors, code that can bring systems down)
   - **High**: Violates principles 6, 8-10, 32-34 (multi-responsibility, duplication)
   - **Medium**: Violates principles 16-24, 35-38 (readability, expressiveness, care)
   - **Low**: Violates principles 39-44 (Boy Scout Rule, incremental improvement opportunities)
