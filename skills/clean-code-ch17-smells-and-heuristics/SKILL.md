---
name: clean-code-ch17-smells-and-heuristics
description: "Code quality checker based on Clean Code Ch17: Smells and Heuristics — comprehensive reference of ALL 66 code smells organized as C1-C5, E1-E2, F1-F4, G1-G36, J1-J3, N1-N7, T1-T9. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 17: Smells and Heuristics -- Code Quality Checker

Robert C. Martin's comprehensive catalog of code smells and heuristics compiled from walking through several different programs and refactoring them. For every change, he asked himself *why* he made that change and wrote down the reason. The result is a rather long list of things that smell bad when reading code. This list is meant to be read from top to bottom and also used as a reference. There is a cross-reference for each heuristic in "Appendix C" (p. 409) showing where it is referenced in the rest of the text. This is the master reference -- 66 items across 7 categories.

**Key references cited**: Martin Fowler's *Refactoring* (code smells origin), Dave Thomas & Andy Hunt's *The Pragmatic Programmer* (DRY principle, "Writing Shy Code"), *Design Patterns* by GoF (TEMPLATE METHOD, STRATEGY), Kent Beck's *Smalltalk Best Practice Patterns* and *Implementation Patterns* (explanatory variables), Robert C. Martin's *Agile Software Development: Principles, Patterns, and Practices* (PPP), Eric Evans' *Domain Driven Design* (ubiquitous language).

## When to Use

- **Code review**: Systematically scan code for all 66 smells before approving
- **Refactoring**: Identify which smells exist and prioritize fixes
- **New code**: Validate that freshly written code does not introduce any smells
- **Technical debt audit**: Catalog all smells in a module to estimate cleanup effort
- **Teaching**: Reference specific smell IDs (e.g., G5, N1) in review comments
- **Pre-commit check**: Run the checklist mentally before every commit
- **Architecture review**: Evaluate structural smells (G6, G7, G8, G13, G22, G36)

## Master Checklist (All 66 Smells)

### Comments (C1-C5)

#### C1: Inappropriate Information
- **Smell**: Comments holding information better kept in a different system (source control, issue tracker, record-keeping system)
- **Examples**: Change histories, author names, last-modified dates, SPR numbers in comments
- **Detection**: Look for dates, author names, change logs, ticket numbers in comment blocks
- **Fix**: Remove meta-data from comments; let source control track history. Comments should be reserved for technical notes about the code and design.
- **Code smell pattern**:
```
// Modified by John on 2024-01-15
// SPR #4532 - fixed null pointer
// Change History: v1.0 initial, v1.1 added logging...
```

#### C2: Obsolete Comment
- **Smell**: A comment that has gotten old, irrelevant, and incorrect
- **Examples**: Comments describing behavior the code no longer has; parameter descriptions that no longer match; TODO comments for long-completed work
- **Detection**: Compare every comment against the actual code it describes. Look for comments that have "migrated away" from the code they describe.
- **Fix**: Update it or delete it immediately. Obsolete comments become floating islands of irrelevance and misdirection. Best not to write comments that will become obsolete; if you find one, get rid of it as quickly as possible.
- **Code smell pattern**:
```
// Returns the count of active users  <-- but function now returns a map
func GetUsers() map[string]User {
```

#### C3: Redundant Comment
- **Smell**: A comment that describes something that adequately describes itself
- **Examples**: `i++; // increment i`, Javadocs that say nothing more than the function signature, comments restating the obvious
- **Detection**: Read the code without the comment. If meaning is identical, the comment is redundant. Comments should say things the code cannot say for itself.
- **Fix**: Delete the comment. The code is the authoritative source of truth.
- **Code smell pattern**:
```
i++; // increment i

// Sets the name
func SetName(name string) { ... }

/**
 * @param sellRequest
 * @return
 * @throws ManagedComponentException
 */
public SellResponse beginSellItem(SellRequest sellRequest)
```

#### C4: Poorly Written Comment
- **Smell**: A comment worth writing is worth writing well
- **Detection**: Look for rambling comments, bad grammar, comments that state the obvious, imprecise language
- **Fix**: Choose words carefully. Use correct grammar and punctuation. Don't ramble. Don't state the obvious. Be brief. If you are going to write a comment, take the time to make sure it is the best comment you can write.

#### C5: Commented-Out Code
- **Smell**: Stretches of code that are commented out
- **Detection**: Look for blocks of commented-out code (not explanatory comments, but actual code lines prefixed with comment markers)
- **Fix**: DELETE IT. Source code control remembers it. No one will delete it because everyone assumes someone else needs it or has plans for it. It rots, calling functions that no longer exist, using variables whose names have changed. It pollutes the modules that contain it and distracts people who try to read it. Commented-out code is an abomination.
- **Code smell pattern**:
```
// oldValue := computeOldWay(x)
// if oldValue > threshold {
//     return oldValue
// }
newValue := computeNewWay(x)
```

---

### Environment (E1-E2)

#### E1: Build Requires More Than One Step
- **Smell**: Building a project requires multiple arcane commands, hunting for JARs/dependencies, or context-dependent scripts
- **Detection**: Count the number of commands needed to go from clean checkout to built artifact. If more than one simple command after checkout, this smell is present.
- **Fix**: You should be able to check out the system with one simple command and then issue one other simple command to build it.
- **Good example**:
```
git clone <repo>
cd mySystem
make build   # or: go build ./...
```

#### E2: Tests Require More Than One Step
- **Smell**: Running all unit tests requires multiple commands, special setup, or manual steps
- **Detection**: Can you run ALL unit tests with just one command? Can you click one button in your IDE?
- **Fix**: You should be able to run all the unit tests with just one command. Being able to run all the tests is so fundamental and so important that it should be quick, easy, and obvious to do.
- **Good example**:
```
go test ./...        # one command runs everything
make test            # or a single make target
```

---

### Functions (F1-F4)

#### F1: Too Many Arguments
- **Smell**: Functions with more than three arguments
- **Detection**: Count function parameters. Zero is best, then one, then two, then three. More than three is very questionable and should be avoided with prejudice.
- **Fix**: Group related arguments into structs/objects; use builder pattern; split into multiple functions.
- **Code smell pattern**:
```
// BAD - too many arguments
func createUser(name, email, phone, address, city, state, zip string) {}

// GOOD - use a struct
type UserInfo struct { Name, Email, Phone, Address, City, State, Zip string }
func createUser(info UserInfo) {}
```

#### F2: Output Arguments
- **Smell**: Arguments used as outputs rather than inputs
- **Detection**: Look for function arguments that are modified by the function to return data (rather than using return values). Readers expect arguments to be inputs, not outputs.
- **Fix**: If your function must change the state of something, have it change the state of the object it is called on (the receiver/this). Use return values instead of output parameters.
- **Code smell pattern**:
```
// BAD - output argument
appendFooter(report)   // Is report being appended TO, or appended?

// GOOD - method on object
report.appendFooter()
```

#### F3: Flag Arguments
- **Smell**: Boolean arguments that select between behaviors
- **Detection**: Look for boolean parameters, especially those named like `flag`, `isX`, `shouldX` that cause if/else branching inside the function. They loudly declare that the function does more than one thing.
- **Fix**: Split into two separate functions, one for each behavior.
- **Code smell pattern**:
```
// BAD - flag argument
render(true)
calculatePay(employee, true)  // true = overtime as time-and-a-half

// GOOD - separate functions
renderForSuite()
renderForSingleTest()
calculateOvertimePayAtTimeAndAHalf(employee)
calculateStraightTimePay(employee)
```

#### F4: Dead Function
- **Smell**: Methods that are never called
- **Detection**: Use IDE/tooling to find functions with zero callers. Look for functions only referenced in comments or old tests.
- **Fix**: Delete it. Don't be afraid to delete the function. Your source code control system still remembers it. Keeping dead code around is wasteful.

---

### General (G1-G36)

#### G1: Multiple Languages in One Source File
- **Smell**: A single source file containing multiple programming languages
- **Examples**: Java file with embedded XML, HTML, YAML, JavaScript; Go file with embedded SQL strings spanning dozens of lines; JSP with Java + HTML + JavaScript + tag libraries
- **Detection**: Count the distinct languages in each source file. The ideal is one, and only one, language per file.
- **Fix**: Minimize the number and extent of extra languages. Use separate template files, configuration files, or generated code to isolate languages.

#### G2: Obvious Behavior Is Unimplemented
- **Smell**: A function or class does not implement the behaviors another programmer could reasonably expect (Principle of Least Surprise / Principle of Least Astonishment)
- **Example**: A `DayDate.StringToDay("Monday")` that doesn't handle "Monday" or common abbreviations like "Mon", doesn't ignore case, or fails to translate common variations that a reasonable caller would expect
- **Detection**: For every function, ask: "What would a reasonable caller expect this to do?" If the implementation fails to meet those expectations, this smell is present.
- **Fix**: Implement all obvious behaviors. When obvious behavior is not implemented, readers lose their trust in the original author and must fall back on reading the details of the code.

#### G3: Incorrect Behavior at the Boundaries
- **Smell**: Code that does not behave correctly at boundary conditions, corner cases, and edge cases
- **Detection**: Look for every boundary condition, every corner case, every quirk and exception. Don't rely on your intuition.
- **Fix**: Write a test for every boundary condition. There is no replacement for due diligence. Every boundary condition, every corner case, every quirk and exception represents something that can confound an elegant and intuitive algorithm.

#### G4: Overridden Safeties
- **Smell**: Disabling compiler warnings, turning off failing tests, suppressing safety checks
- **Examples**: `@SuppressWarnings`, `//nolint`, `t.Skip()` on failing tests, disabling all compiler warnings, ignoring `serialVersionUID`
- **Detection**: Search for suppression annotations, disabled tests, ignored warnings. Turning off failing tests and telling yourself you'll get them to pass later is as bad as pretending your credit cards are free money.
- **Fix**: Don't override safeties. Fix the underlying problem. It is risky to override safeties -- it may help you get the build to succeed, but at the risk of endless debugging sessions.

#### G5: Duplication
- **Smell**: Duplicated code in any form -- one of the most important rules in the book (DRY principle: Don't Repeat Yourself)
- **Forms of duplication**:
  1. **Identical code clumps**: Same code copy-pasted in multiple places. Replace with simple methods.
  2. **Repeated switch/case or if/else chains**: Same set of conditions tested in various modules. Replace with polymorphism.
  3. **Modules with similar algorithms**: Algorithms that look similar but don't share identical lines. Apply TEMPLATE METHOD or STRATEGY pattern.
- **Detection**: Look for any repeated patterns, logic, or structure. Every duplication represents a missed opportunity for abstraction.
- **Fix**: Find and eliminate duplication wherever you can. By folding duplication into an abstraction, you increase the vocabulary of your design. Most design patterns are simply well-known ways to eliminate duplication.

#### G6: Code at Wrong Level of Abstraction
- **Smell**: Mixing higher-level general concepts with lower-level detailed concepts in the same class/module
- **Detection**: Examine abstract classes/interfaces. Are there constants, variables, or utility functions pertaining to detailed implementation in the base class? The base class should know nothing about them.
- **Fix**: Ensure ALL lower-level concepts are in derivatives and ALL higher-level concepts are in the base class. The separation needs to be complete. You cannot lie or fake your way out of a misplaced abstraction.
- **Code smell pattern**:
```
// BAD - percentFull is wrong abstraction level for Stack interface
type Stack interface {
    Pop() (any, error)
    Push(o any) error
    PercentFull() float64  // not all stacks can know this!
}

// GOOD - move to derivative
type BoundedStack interface {
    Stack
    PercentFull() float64
}
```

#### G7: Base Classes Depending on Their Derivatives
- **Smell**: Base classes that mention or know about their derived classes
- **Detection**: Look for imports, type references, or conditional logic in base classes that references specific derived class names. In general, base classes should know nothing about their derivatives.
- **Fix**: Deploy derivatives and bases in different packages/modules. Make sure the base packages know nothing about the contents of the derivative packages. This allows independent deployment and reduces the impact of changes.
- **Exception**: When the number of derivatives is strictly fixed and the base selects between them (e.g., finite state machines), the coupling may be acceptable.

#### G8: Too Much Information
- **Smell**: Wide, deep interfaces that expose too much; classes with too many methods, variables, or instance variables
- **Detection**: Count exposed methods, public variables, interface functions. Well-defined modules have very small interfaces that allow you to do a lot with a little. Poorly defined modules have wide and deep interfaces that force many different gestures.
- **Fix**: Hide your data. Hide your utility functions. Hide your constants and temporaries. Don't create classes with lots of methods or lots of instance variables. Don't create lots of protected variables and functions for subclasses. Concentrate on keeping interfaces very tight and very small. Help keep coupling low by limiting information.

#### G9: Dead Code
- **Smell**: Code that isn't executed -- unreachable conditions, unused catch blocks, unused utility methods, switch/case conditions that never occur
- **Detection**: Look for: `if` statements checking conditions that can't happen, `catch` blocks for exceptions that are never thrown, unused utility methods, impossible `switch/case` conditions. Dead code does not follow newer conventions or rules -- it was written at a time when the system was different.
- **Fix**: Give it a decent burial. Delete it from the system. The older dead code is, the stronger and sourer the odor becomes.

#### G10: Vertical Separation
- **Smell**: Variables and functions defined far from where they are used
- **Detection**: Look for local variables declared hundreds of lines from their first usage. Look for private functions defined far below their first invocation.
- **Fix**: Local variables should be declared just above their first usage and should have a small vertical scope. Private functions should be defined just below their first usage. Finding a private function should just be a matter of scanning downward from the first usage.

#### G11: Inconsistency
- **Smell**: Similar things done in dissimilar ways throughout the codebase
- **Detection**: If a variable holds an `HttpServletResponse` and is named `response` in one function, is the same name used in other functions that use `HttpServletResponse`? If a method is named `processVerificationRequest`, is a similar name like `processDeletionRequest` used for similar methods?
- **Fix**: If you do something a certain way, do all similar things in the same way. Be careful with the conventions you choose, and once chosen, be careful to continue to follow them. Simple consistency, when reliably applied, can make code much easier to read and modify. (Principle of Least Surprise.)

#### G12: Clutter
- **Smell**: Default constructors with no implementation, variables that aren't used, functions that are never called, comments that add no information
- **Detection**: Look for empty constructors, unused variables, uncalled functions, information-free comments. All they serve to do is clutter up the code with meaningless artifacts.
- **Fix**: Keep your source files clean, well organized, and free of clutter. Remove all of it.

#### G13: Artificial Coupling
- **Smell**: Coupling between two modules that serves no direct purpose -- putting a variable, constant, or function in a temporarily convenient but inappropriate location
- **Examples**: General `enums` placed inside specific classes (forcing the whole application to know about those classes); general-purpose `static` functions declared in specific classes
- **Detection**: Ask: "Does this thing NEED to be here, or was it just convenient?" Take the time to figure out where functions, constants, and variables ought to be declared.
- **Fix**: Don't just toss them in the most convenient place at hand and leave them there. Move them to where they logically belong. This is lazy and careless.

#### G14: Feature Envy
- **Smell**: A method that uses accessors and mutators of some other object to manipulate data within that object -- it "envies" the scope of the other class
- **Detection**: Look for methods that call many getters/setters on another object. The method wishes it were inside that other class so it could have direct access to the variables.
- **Fix**: Move the method to the class whose data it manipulates, or redesign so the data owner performs the operation. Eliminate Feature Envy because it exposes the internals of one class to another.
- **Exception**: Sometimes Feature Envy is a necessary evil. For example, `HourlyEmployeeReport.reportHours()` envies `HourlyEmployee`, but moving the report format string into `HourlyEmployee` would violate SRP, the Open Closed Principle, and the Common Closure Principle -- it would couple `HourlyEmployee` to the format of the report.
- **Code smell pattern**:
```
// BAD - calculateWeeklyPay envies HourlyEmployee
func (c *PayCalculator) CalculateWeeklyPay(e *HourlyEmployee) Money {
    tenthRate := e.GetTenthRate().GetPennies()
    tenthsWorked := e.GetTenthsWorked()
    straightTime := min(400, tenthsWorked)
    // ... all data comes from e
}

// GOOD - move to HourlyEmployee
func (e *HourlyEmployee) CalculateWeeklyPay() Money { ... }
```

#### G15: Selector Arguments
- **Smell**: Arguments (boolean, enum, integer) used to select behavior inside a function -- a lazy way to avoid splitting a large function
- **Detection**: Look for boolean parameters, enum arguments, or integer codes that control which path the function takes. What does `calculateWeeklyPay(false)` mean? Not only is the purpose difficult to remember, each selector argument combines many functions into one.
- **Fix**: Split into multiple functions. It is better to have many functions than to pass some code into a function to select the behavior.
- **Code smell pattern**:
```
// BAD
calculateWeeklyPay(false)  // false = what?

// GOOD
calculateStraightTimePay()
calculateOvertimePayAtTimeAndAHalf()
```

#### G16: Obscured Intent
- **Smell**: Code that is not as expressive as possible -- run-on expressions, Hungarian notation, magic numbers all obscure the author's intent
- **Detection**: Look for cryptic variable names, dense expressions, unexplained numbers, Hungarian prefixes. Can you understand the intent at a glance?
- **Fix**: It is worth taking the time to make the intent of our code visible to our readers. Use explanatory names, break up complex expressions, name constants.
- **Code smell pattern**:
```
// BAD - obscured intent
public int m_otCalc() {
    return iThsWkd * iThsRte +
        (int) Math.round(0.5 * iThsRte *
            Math.max(0, iThsWkd - 400));
}

// GOOD - clear intent
public int overtimePay() {
    int overtimeTenths = Math.max(0, tenthsWorked - 400);
    int overtimeBonus = overTimeBonus(overtimeTenths);
    return straightPay() + overtimeBonus;
}
```

#### G17: Misplaced Responsibility
- **Smell**: Code placed where it is convenient for the developer rather than where a reader would naturally expect it
- **Detection**: Apply the Principle of Least Surprise. Where would a reader naturally expect to find this function/constant? The `PI` constant should go where the trig functions are declared. The `OVERTIME_RATE` should be in the `HourlyPayCalculator` class. Look at function names to decide -- if the report module has `getTotalHours` and the timecard module has `saveTimeCard`, the total calculation belongs in the report module.
- **Fix**: Place code where a reader would naturally expect it. Use function names as a guide to placement.

#### G18: Inappropriate Static
- **Smell**: Making a function static when it should be a nonstatic member function
- **Detection**: Ask: "Is there a reasonable chance we'll want this function to behave polymorphically?" If yes, it should not be static. If the function operates on data from its arguments only and there is no chance you'll ever want it polymorphic, static may be appropriate (e.g., `Math.max`).
- **Fix**: In general, prefer nonstatic methods to static methods. When in doubt, make the function nonstatic. If you really want a function to be static, make sure there is no chance that you'll want it to behave polymorphically.
- **Code smell pattern**:
```
// Questionable static - may need polymorphism later
HourlyPayCalculator.calculatePay(employee, overtimeRate)

// Better as instance method on Employee (enables polymorphic dispatch)
employee.CalculatePay()
```

#### G19: Use Explanatory Variables
- **Smell**: Complex calculations without intermediate variables to explain the steps
- **Detection**: Look for long expressions, nested function calls, or complex arithmetic without any intermediate variables breaking them apart.
- **Fix**: Break calculations up into intermediate values held in variables with meaningful names. More explanatory variables are generally better than fewer. It is remarkable how an opaque module can suddenly become transparent simply by breaking the calculations up into well-named intermediate values.
- **Code smell pattern**:
```
// BAD
headers.put(line.split(":")[0].trim().toLowerCase(), line.split(":")[1].trim())

// GOOD
match := headerPattern.FindStringSubmatch(line)
if match != nil {
    key := match[1]
    value := match[2]
    headers[strings.ToLower(key)] = value
}
```

#### G20: Function Names Should Say What They Do
- **Smell**: Function names that don't clearly describe the function's behavior
- **Detection**: If you have to look at the implementation (or documentation) of the function to know what it does, you should work to find a better name or rearrange the functionality so it can be placed in functions with better names.
- **Fix**: Choose names that make the behavior unambiguous from the call site.
- **Code smell pattern**:
```
// BAD - what does add(5) do? Days? Hours? Weeks? Does it mutate or return new?
date.add(5)

// GOOD
date.addDaysTo(5)      // mutates, adds days
date.daysLater(5)      // returns new Date, 5 days later
date.increaseByDays(5) // mutates, adds days
```

#### G21: Understand the Algorithm
- **Smell**: Code that "works" by plugging in enough `if` statements and flags without the programmer truly understanding the algorithm
- **Detection**: Look for functions that feel like they were "fiddled" into working -- lots of special cases, flags, and workarounds. Ask: "Does the programmer truly understand how it works, or just that it passes the tests they thought of?"
- **Fix**: Before you consider yourself done with a function, make sure you understand how it works. It is not good enough that it passes all the tests. You must *know* the solution is correct. Often the best way is to refactor the function into something so clean and expressive that it is *obvious* how it works.
- **Key distinction**: There is a difference between knowing how the code works and knowing whether the algorithm will do the job required of it. Being unsure that an algorithm is appropriate is often a fact of life. Being unsure what your code does is just laziness.

#### G22: Make Logical Dependencies Physical
- **Smell**: A module makes assumptions about the module it depends upon instead of explicitly asking for the information
- **Example**: `HourlyReporter` declares `PAGE_SIZE = 55` but page size should be the responsibility of `HourlyReportFormatter`. This is an assumption (logical dependency) that `HourlyReportFormatter` can deal with page sizes of 55. This also represents a misplaced responsibility [G17].
- **Detection**: Look for constants or values in one module that really belong to another module. If Module A depends on Module B, does A explicitly ask B for all the information it depends upon?
- **Fix**: Physicalize the dependency by creating a method in the depended-upon module. E.g., create `getMaxPageSize()` in `HourlyReportFormatter` instead of hardcoding `PAGE_SIZE` in `HourlyReporter`.

#### G23: Prefer Polymorphism to If/Else or Switch/Case
- **Smell**: Using switch statements or if/else chains where polymorphism would be more appropriate
- **Detection**: Treat every switch statement as suspect. Apply the "ONE SWITCH" rule: there may be no more than one switch statement for a given type of selection. The cases in that switch must create polymorphic objects that take the place of other such switch statements in the rest of the system.
- **Fix**: Replace switch/case with polymorphic dispatch. Most people use switch because it's the obvious brute force solution -- consider polymorphism before using a switch. The cases where functions are more volatile than types are relatively rare.

#### G24: Follow Standard Conventions
- **Smell**: Not following the team's coding standard
- **Detection**: Look for inconsistencies in: where instance variables are declared, how classes/methods/variables are named, where braces are placed, naming patterns, spacing conventions.
- **Fix**: Every team should follow a coding standard based on common industry norms. The team should not need a document to describe conventions because their code provides the examples. Everyone on the team should follow these conventions. It doesn't matter a whit where you put your braces so long as you all agree on where to put them.

#### G25: Replace Magic Numbers with Named Constants
- **Smell**: Raw numbers in code that have no obvious meaning
- **Detection**: Look for any numeric literal that is not self-describing. The term "Magic Number" applies to any token that has a value that is not self-describing -- not just numbers. `"John Doe"` can be a magic number too.
- **Fix**: Hide raw numbers behind well-named constants. E.g., `86400` becomes `SECONDS_PER_DAY`, `55` becomes `LINES_PER_PAGE`.
- **Exceptions**: Some formulae are simply better written as raw numbers in self-explanatory context: `int dailyPay = hourlyRate * 8` (8 hours is obvious), `double circumference = radius * Math.PI * 2` (the formula is well-known). But `3.141592653589793` should always be `Math.PI`.
- **Code smell pattern**:
```
// BAD
if timeout > 86400 { ... }
assertEquals(7777, Employee.find("John Doe").employeeNumber())

// GOOD
if timeout > SECONDS_PER_DAY { ... }
assertEquals(HOURLY_EMPLOYEE_ID, Employee.find(HOURLY_EMPLOYEE_NAME).employeeNumber())
```

#### G26: Be Precise
- **Smell**: Imprecision and laziness in code decisions
- **Examples**: Expecting the first match to a query to be the only match; using floating point for currency; avoiding locks because concurrent update "probably won't happen"; declaring `ArrayList` when `List` will do; making all variables `protected`
- **Detection**: Look for: missing null checks on functions that might return null, missing uniqueness checks on queries, floating point for currency, absent locking mechanisms, overly specific or overly general type declarations.
- **Fix**: When you make a decision in your code, make sure you make it precisely. Know why you have made it and how you will deal with any exceptions. Don't be lazy about the precision of your decisions. Ambiguities and imprecision are either a result of disagreements or laziness -- in either case they should be eliminated.

#### G27: Structure over Convention
- **Smell**: Relying on naming conventions rather than structural enforcement
- **Detection**: Look for places where compliance depends on developers remembering to follow a convention vs. being forced by the compiler/type system.
- **Fix**: Enforce design decisions with structure over convention. For example, switch/case with nicely named enumerations are inferior to base classes with abstract methods. No one is forced to implement the switch the same way each time; but the base classes do enforce that concrete classes have all abstract methods implemented.

#### G28: Encapsulate Conditionals
- **Smell**: Boolean logic exposed directly in `if` or `while` statements rather than wrapped in a descriptive function
- **Detection**: Look for complex boolean expressions directly in control flow statements.
- **Fix**: Extract functions that explain the intent of the conditional.
- **Code smell pattern**:
```
// BAD
if timer.HasExpired() && !timer.IsRecurrent() { ... }

// GOOD
if shouldBeDeleted(timer) { ... }

func shouldBeDeleted(timer Timer) bool {
    return timer.HasExpired() && !timer.IsRecurrent()
}
```

#### G29: Avoid Negative Conditionals
- **Smell**: Conditionals expressed as negatives, which are harder to understand than positives
- **Detection**: Look for `!`, `not`, negated method names in conditionals.
- **Fix**: Express conditionals as positives when possible.
- **Code smell pattern**:
```
// BAD
if !buffer.ShouldNotCompact() { ... }

// GOOD
if buffer.ShouldCompact() { ... }
```

#### G30: Functions Should Do One Thing
- **Smell**: Functions with multiple sections that each perform a distinct operation
- **Detection**: Look for functions that can be divided into sections -- looping, checking a condition, and performing an action are three things.
- **Fix**: Convert into many smaller functions, each of which does one thing.
- **Code smell pattern**:
```
// BAD - does three things: loops, checks payday, calculates+delivers
func pay() {
    for _, e := range employees {
        if e.IsPayday() {
            pay := e.CalculatePay()
            e.DeliverPay(pay)
        }
    }
}

// GOOD - each function does one thing
func pay() {
    for _, e := range employees {
        payIfNecessary(e)
    }
}
func payIfNecessary(e Employee) {
    if e.IsPayday() { calculateAndDeliverPay(e) }
}
func calculateAndDeliverPay(e Employee) {
    pay := e.CalculatePay()
    e.DeliverPay(pay)
}
```

#### G31: Hidden Temporal Couplings
- **Smell**: Function calls that must be executed in a specific order, but the code does not enforce the ordering
- **Detection**: Look for sequences of function calls where reordering them would cause bugs but nothing in the code prevents reordering.
- **Fix**: Structure the arguments of your functions so that the order in which they should be called is obvious. Create a "bucket brigade" where each function produces a result that the next function needs.
- **Code smell pattern**:
```
// BAD - nothing prevents calling these out of order
saturateGradient()
reticulateSplines()
diveForMoog(reason)

// GOOD - bucket brigade enforces ordering
gradient := saturateGradient()
splines := reticulateSplines(gradient)
diveForMoog(splines, reason)
```

#### G32: Don't Be Arbitrary
- **Smell**: Code structure that appears arbitrary rather than intentional
- **Detection**: Look for classes nested inside other classes for no clear reason, inconsistent structural choices, things placed in locations without clear rationale. If a structure appears arbitrary, others will feel empowered to change it.
- **Fix**: Have a reason for the way you structure your code, and make sure that reason is communicated by the structure. If a structure appears consistently throughout the system, others will use it and preserve the convention. Public classes that are not utilities of some other class should not be scoped inside another class. The convention is to make them public at the top level of their package.

#### G33: Encapsulate Boundary Conditions
- **Smell**: Boundary condition expressions (like `level + 1`) scattered throughout code rather than encapsulated in a single place
- **Detection**: Look for `+1`, `-1` expressions repeated in code. Boundary conditions are hard to keep track of. Don't let them leak all over the code.
- **Fix**: Put the processing for boundary conditions in one place. Encapsulate the boundary expression in a well-named variable.
- **Code smell pattern**:
```
// BAD - level+1 scattered in multiple places
if level+1 < len(tags) {
    parts = Parse(body, tags, level+1, offset+endTag)
    body = ""
}

// GOOD - encapsulated
nextLevel := level + 1
if nextLevel < len(tags) {
    parts = Parse(body, tags, nextLevel, offset+endTag)
    body = ""
}
```

#### G34: Functions Should Descend Only One Level of Abstraction
- **Smell**: Statements within a function that are at mixed levels of abstraction
- **Detection**: Look at each statement in a function. Is it at the same level of abstraction as the function name suggests, or does it descend more than one level? Humans are just too good at seamlessly mixing levels of abstraction, making this may be the hardest of these heuristics to interpret and follow.
- **Fix**: Separate levels of abstraction into different functions. Separating levels of abstraction is one of the most important functions of refactoring, and it's one of the hardest to do well. When you break a function along lines of abstraction, you often uncover new lines of abstraction that were obscured by the previous structure.
- **Code smell pattern**:
```
// BAD - mixes HR tag concept with HTML syntax details
func render() string {
    html := "<hr"
    if size > 0 {
        html += fmt.Sprintf(` size="%d"`, size+1)
    }
    html += ">"
    return html
}

// GOOD - one level of abstraction each
func render() string {
    hr := NewHtmlTag("hr")
    if extraDashes > 0 {
        hr.AddAttribute("size", hrSize(extraDashes))
    }
    return hr.Html()
}
func hrSize(height int) string {
    return fmt.Sprintf("%d", height+1)
}
```

#### G35: Keep Configurable Data at High Levels
- **Smell**: Configuration constants/defaults buried in low-level functions
- **Detection**: Look for default values, configuration constants, or magic numbers buried deep in the code that should be visible at the top level.
- **Fix**: Expose configurable data as constants or arguments at a high level of abstraction. Configuration constants should reside at a very high level and be easy to change. The lower levels of the application do not own the values of these constants.
- **Code smell pattern**:
```
// BAD - default port buried deep in code
func startServer() {
    if arguments.Port == 0 { // use 80 by default
        listen(80)
    }
}

// GOOD - configuration at high level
type Arguments struct {
    DefaultPath string = "."
    DefaultRoot string = "FitNesseRoot"
    DefaultPort int    = 80
    DefaultVersionDays int = 14
}
```

#### G36: Avoid Transitive Navigation
- **Smell**: Modules navigating through collaborators' collaborators (violating Law of Demeter / "Writing Shy Code")
- **Detection**: Look for chained method calls like `a.getB().getC().doSomething()`. We don't want a single module to know much about its collaborators. If A collaborates with B, and B collaborates with C, we don't want modules that use A to know about C.
- **Fix**: Make sure modules know only about their immediate collaborators and do not know the navigation map of the whole system. If many modules use `a.getB().getC()`, it would be hard to interpose a Q between B and C -- you'd have to find every instance and change it.
- **Code smell pattern**:
```
// BAD - transitive navigation
a.GetB().GetC().DoSomething()

// GOOD - ask immediate collaborator directly
myCollaborator.DoSomething()
```

---

### Java (J1-J3)

#### J1: Avoid Long Import Lists by Using Wildcards
- **Smell**: Long lists of specific imports (80+ lines) cluttering the tops of modules
- **Detection**: Count import lines. If using two or more classes from a package, import the whole package with wildcards. Long lists of imports are daunting to the reader.
- **Fix**: Use wildcard imports (`import package.*`). Specific imports are hard dependencies; wildcard imports are not. Wildcard imports simply add the package to the search path -- no true dependency is created, keeping modules less coupled.
- **Exception**: Wildcard imports can sometimes cause name conflicts and ambiguities. Two classes with the same name in different packages must be specifically imported. This is a rare nuisance.
- **Go equivalent**: Go enforces minimal imports by default (unused imports are compilation errors), but avoid unnecessary aliasing.

#### J2: Don't Inherit Constants
- **Smell**: Using inheritance to gain access to constants from an interface (abusing inheritance as a scoping mechanism)
- **Detection**: Look for classes implementing interfaces solely to access constants. The constants are hidden at the top of the inheritance hierarchy -- a hideous practice.
- **Fix**: Use static imports instead (`import static PayrollConstants.*`). Don't use inheritance as a way to cheat the scoping rules of the language.
- **Go equivalent**: In Go, this manifests as importing a package solely for its constants when they should be defined locally or accessed through a proper dependency.

#### J3: Constants versus Enums
- **Smell**: Using `public static final int` constants instead of enums (Java 5+)
- **Detection**: Look for groups of related integer constants. The meaning of `int`s can get lost; the meaning of `enum`s cannot, because they belong to a named enumeration.
- **Fix**: Use enums. Study the syntax carefully -- enums can have methods and fields, making them very powerful tools that allow much more expression and flexibility than integer constants.
- **Go equivalent**: Use typed constants with `iota` or dedicated types instead of raw untyped integer constants.
- **Code smell pattern**:
```
// BAD - raw constants
const (
    StatusActive  = 0
    StatusPending = 1
    StatusClosed  = 2
)

// GOOD - typed constants
type Status int
const (
    StatusActive Status = iota
    StatusPending
    StatusClosed
)
func (s Status) String() string { ... }
```

---

### Names (N1-N7)

#### N1: Choose Descriptive Names
- **Smell**: Names that don't clearly describe what a variable, function, or class does
- **Detection**: Consider what a name tells you. Can you infer what the code does from names alone? Names in software are 90 percent of what make software readable.
- **Fix**: Don't be too quick to choose a name. Make sure it is descriptive. Remember that meanings tend to drift as software evolves, so frequently reevaluate the appropriateness of names. Names are too important to treat carelessly. The power of carefully chosen names is that they overload the structure of the code with description.
- **Code smell pattern**:
```
// BAD - meaningless names
func x() int {
    q := 0; z := 0
    for kk := 0; kk < 10; kk++ { ... }
}

// GOOD - descriptive names
func score() int {
    score := 0; frame := 0
    for frameNumber := 0; frameNumber < 10; frameNumber++ { ... }
}
```

#### N2: Choose Names at the Appropriate Level of Abstraction
- **Smell**: Names that communicate implementation details rather than the abstraction level of the class or function
- **Detection**: Look for names that are too specific for their context. Each time you make a pass over your code, you will likely find some variable that is named at too low a level.
- **Fix**: Choose names that reflect the level of abstraction. Making code readable requires a dedication to continuous improvement.
- **Code smell pattern**:
```
// BAD - "phoneNumber" is too implementation-specific for a generic Modem
type Modem interface {
    Dial(phoneNumber string) bool  // what about cable modems, USB modems?
    GetConnectedPhoneNumber() string
}

// GOOD - abstracted names
type Modem interface {
    Connect(connectionLocator string) bool
    GetConnectedLocator() string
}
```

#### N3: Use Standard Nomenclature Where Possible
- **Smell**: Inventing novel names when standard terminology exists
- **Detection**: Look for functions or classes that implement well-known patterns but don't use the standard name. Are DECORATOR classes named with "Decorator"? Are `toString`-equivalent functions following the language's convention?
- **Fix**: Use pattern names (Decorator, Factory, Visitor, etc.) in class names. Follow language conventions (e.g., `toString`, `String()`, `MarshalJSON()`). Use the project's ubiquitous language (per Domain-Driven Design). The more you can use names that are overloaded with special meanings relevant to your project, the easier it will be for readers to know what your code is talking about.

#### N4: Unambiguous Names
- **Smell**: Names that are vague or could refer to multiple possible behaviors
- **Detection**: Look for functions whose names don't clearly distinguish what they do. If there is a function named `doRename` inside a function named `renamePage`, what do the names tell you about the difference? Nothing.
- **Fix**: Choose names that make the workings of a function or variable unambiguous. The name should tell you exactly what it does, even if it makes the name long. `renamePageAndOptionallyAllReferences` is better than `doRename` if that's what it actually does.

#### N5: Use Long Names for Long Scopes
- **Smell**: Short names for variables/functions with long scopes; long names for tiny scopes
- **Detection**: Look at scope length. Variable names like `i` and `j` are fine for a 5-line loop. But variables and functions with short names lose their meaning over long distances.
- **Fix**: The length of a name should be related to the length of the scope. Short variable names for tiny scopes, longer and more precise names for larger scopes.
- **Code smell pattern**:
```
// GOOD - short name for tiny scope
for i := 0; i < n; i++ {
    g.Roll(pins)
}

// BAD - short name for long scope (50+ lines)
var r = getReport()
// ... 50 lines later ...
r.Print()  // what is r again?
```

#### N6: Avoid Encodings
- **Smell**: Names encoded with type or scope information (Hungarian notation, prefixes like `m_`, `f_`, `vis_`)
- **Detection**: Look for prefixes like `m_`, `f`, `I` (for interface), `vis_`, type suffixes like `strName`, `iCount`. Today's environments provide all that information without having to mangle the names.
- **Fix**: Remove encoding prefixes/suffixes. Keep your names free of Hungarian pollution. Project and/or subsystem encodings such as `vis_` (for visual imaging system) are distracting and redundant.

#### N7: Names Should Describe Side-Effects
- **Smell**: Names that describe only a simple action when the function actually does more
- **Detection**: Look for getter-style names on functions that create, initialize, or modify state as a side effect.
- **Fix**: Names should describe everything that a function, variable, or class is or does. Don't hide side effects with a simple verb.
- **Code smell pattern**:
```
// BAD - "get" hides the creation side effect
func GetOos() ObjectOutputStream {
    if oos == nil {
        oos = NewObjectOutputStream(socket.GetOutputStream())
    }
    return oos
}

// GOOD - name describes the side effect
func CreateOrReturnOos() ObjectOutputStream { ... }
```

---

### Tests (T1-T9)

#### T1: Insufficient Tests
- **Smell**: A test suite that doesn't test everything that could possibly break
- **Detection**: Are there conditions that have not been explored by the tests? Are there calculations that have not been validated? The metric many programmers use -- "That seems like enough" -- is wrong.
- **Fix**: A test suite should test everything that could possibly break. The tests are insufficient so long as there are conditions that have not been explored or calculations that have not been validated.

#### T2: Use a Coverage Tool!
- **Smell**: Not using code coverage tools to find gaps in testing strategy
- **Detection**: Are you relying on guesswork to determine which code is tested? Coverage tools report gaps, making it easy to find modules, classes, and functions that are insufficiently tested.
- **Fix**: Use coverage tools. Most IDEs give you a visual indication, marking lines that are covered in green and those that are uncovered in red. This makes it quick and easy to find `if` or `catch` statements whose bodies haven't been checked.

#### T3: Don't Skip Trivial Tests
- **Smell**: Not writing tests because they seem "too trivial"
- **Detection**: Are there simple behaviors that are untested because they were deemed too easy to break?
- **Fix**: Write them anyway. They are easy to write and their documentary value is higher than the cost to produce them.

#### T4: An Ignored Test Is a Question about an Ambiguity
- **Smell**: Tests that are commented out or annotated with `@Ignore` / `t.Skip()`
- **Detection**: Look for commented-out tests or skipped test annotations. Sometimes we are uncertain about a behavioral detail because the requirements are unclear.
- **Fix**: Express ambiguity about requirements as a test that is commented out or annotated with `@Ignore`. Which you choose depends on whether the ambiguity is about something that would compile or not. The test records the question for future resolution.

#### T5: Test Boundary Conditions
- **Smell**: Not testing edge cases and boundary conditions
- **Detection**: Are zero, empty, nil, max, min, off-by-one, and overflow conditions tested? We often get the middle of an algorithm right but misjudge the boundaries.
- **Fix**: Take special care to test boundary conditions. We often get the middle right but misjudge the boundaries.

#### T6: Exhaustively Test Near Bugs
- **Smell**: Not writing additional tests around code where bugs were found
- **Detection**: When a bug is found in a function, does the test suite expand to exhaustively test that function?
- **Fix**: Bugs tend to congregate. When you find a bug in a function, do an exhaustive test of that function. You'll probably find that the bug was not alone.

#### T7: Patterns of Failure Are Revealing
- **Smell**: Not analyzing failure patterns in test results to diagnose problems
- **Detection**: Look at which tests fail and see if there's a pattern. Do all tests with inputs larger than 5 characters fail? Do all tests that pass a negative number as the second argument fail?
- **Fix**: Make the test cases as complete as possible. Complete test cases, ordered in a reasonable way, expose patterns. Sometimes just seeing the pattern of red and green in the test report is enough to spark the "Aha!" that leads to the solution.

#### T8: Test Coverage Patterns Can Be Revealing
- **Smell**: Not examining which lines are executed by passing tests to understand why other tests fail
- **Detection**: Look at the code that IS or IS NOT executed by the passing tests for clues about why the failing tests fail.
- **Fix**: Use coverage information to understand failures. Looking at the code that is or is not executed by passing tests gives clues to why failing tests fail.

#### T9: Tests Should Be Fast
- **Smell**: Slow tests
- **Detection**: Measure test execution time. A slow test is a test that won't get run.
- **Fix**: Do what you must to keep your tests fast. When things get tight, it's the slow tests that will be dropped from the suite. A slow test is a test that won't get run.

---

## Violations to Detect -- Quick-Scan Patterns

When reviewing code, scan for these high-signal patterns in this priority order:

### Critical (fix immediately)
| ID | Pattern | What to look for |
|----|---------|-----------------|
| G5 | Duplication | Copy-pasted blocks, repeated switch/case chains, similar algorithms |
| G9 | Dead Code | Unreachable branches, uncalled functions, impossible conditions |
| C5 | Commented-Out Code | Code lines commented out (not explanatory comments) |
| G4 | Overridden Safeties | `//nolint`, `@SuppressWarnings`, `t.Skip()` on failing tests |
| E1 | Build Requires More Than One Step | Multi-step build instructions |
| E2 | Tests Require More Than One Step | Can't run all tests with one command |

### High Priority (fix in current sprint)
| ID | Pattern | What to look for |
|----|---------|-----------------|
| F1 | Too Many Arguments | Functions with 4+ parameters |
| G6 | Code at Wrong Level of Abstraction | Implementation details in base classes/interfaces |
| G14 | Feature Envy | Methods accessing many getters of another class |
| G30 | Functions Should Do One Thing | Functions with multiple distinct sections |
| G34 | Mixed Abstraction Levels | Statements at different abstraction levels in one function |
| G36 | Transitive Navigation | Chained calls: `a.GetB().GetC().Do()` |
| N1 | Poor Names | Single-letter names in large scopes, meaningless names |
| T1 | Insufficient Tests | Missing boundary tests, untested error paths |

### Medium Priority (fix proactively)
| ID | Pattern | What to look for |
|----|---------|-----------------|
| G1 | Multiple Languages | Mixed languages in one file |
| G8 | Too Much Information | Wide public interfaces, many public methods |
| G10 | Vertical Separation | Variables declared far from usage |
| G11 | Inconsistency | Same thing done different ways |
| G13 | Artificial Coupling | Things placed where convenient, not where they belong |
| G16 | Obscured Intent | Cryptic variable names, dense expressions |
| G22 | Logical Dependencies | Assumptions instead of explicit queries |
| G25 | Magic Numbers | Raw numeric/string literals with non-obvious meaning |
| G28 | Exposed Conditionals | Complex booleans directly in if/while |
| G29 | Negative Conditionals | `!shouldNot...`, double negatives |
| G31 | Hidden Temporal Couplings | Order-dependent calls with no enforcement |
| N7 | Hidden Side-Effects in Names | `GetX()` that also creates X |
| T9 | Slow Tests | Tests taking more than a few seconds |

### Low Priority (fix when touching the code)
| ID | Pattern | What to look for |
|----|---------|-----------------|
| C1 | Inappropriate Information | Dates, authors, change logs in comments |
| C2 | Obsolete Comment | Comments that no longer match code |
| C3 | Redundant Comment | Comments restating what code says |
| C4 | Poorly Written Comment | Rambling, grammatically incorrect comments |
| G12 | Clutter | Unused variables, empty constructors, information-free comments |
| G15 | Selector Arguments | Booleans/enums selecting function behavior |
| G17 | Misplaced Responsibility | Code not where reader expects it |
| G19 | Missing Explanatory Variables | Complex expressions without intermediates |
| G32 | Arbitrary Structure | Nested classes without clear reason |
| G33 | Unencapsulated Boundary Conditions | `level+1` repeated in multiple places |
| N2 | Names at Wrong Abstraction Level | `phoneNumber` on generic `Modem` |
| N5 | Name Length vs Scope Mismatch | Short names for long scopes |
| N6 | Encoded Names | Hungarian notation, `m_` prefixes |

---

## How to Fix -- Refactoring Strategies by Smell Category

### Comments (C1-C5)
1. Delete all commented-out code (C5) -- source control remembers it
2. Delete all redundant comments (C3) -- code should be self-documenting
3. Move meta-data to tracking systems (C1) -- dates, authors, SPR numbers
4. Update or delete obsolete comments (C2) -- do not leave them to rot
5. Rewrite poorly written comments to be brief and precise (C4)

### Environment (E1-E2)
1. Create a single build command (Makefile, script, or CI config)
2. Create a single test command that runs the entire suite
3. Document both in the project README

### Functions (F1-F4)
1. Group arguments into parameter objects/structs (F1)
2. Replace output arguments with return values or method calls on receivers (F2)
3. Split functions with flag arguments into separate named functions (F3)
4. Delete dead functions (F4) -- source control remembers them

### General -- Structural
1. **Duplication (G5)**: Extract shared code into functions, use polymorphism for repeated conditionals, apply TEMPLATE METHOD for similar algorithms
2. **Abstraction (G6, G34)**: Move implementation details to derivatives; ensure each function stays at one level of abstraction
3. **Dependencies (G7, G22, G36)**: Base classes must not know about derivatives; make logical dependencies physical; avoid transitive navigation (Law of Demeter)
4. **Coupling (G8, G13)**: Minimize public interface surface area; place things where they logically belong, not where convenient
5. **Precision (G3, G26, G33)**: Test all boundary conditions; be precise in decisions; encapsulate boundary expressions

### General -- Clarity
1. **Naming (G16, G20)**: Make intent visible through clear names; function names must describe behavior
2. **Structure (G10, G31, G32)**: Keep variables near usage; expose temporal couplings through function arguments; have a reason for every structural decision
3. **Simplification (G11, G12, G24, G28, G29, G30)**: Be consistent; remove clutter; follow team conventions; encapsulate conditionals; prefer positive expressions; make each function do one thing
4. **Design (G18, G23, G25, G27, G35)**: Prefer nonstatic methods; prefer polymorphism over switch; name all magic numbers; enforce with structure not convention; keep config at high levels

### Names (N1-N7)
1. Choose descriptive names that overload the code with meaning (N1)
2. Match name abstraction to the level of the code (N2)
3. Use established pattern names and language conventions (N3)
4. Make names unambiguous -- prefer long clarity over short confusion (N4)
5. Scale name length to scope size (N5)
6. Remove all Hungarian notation and type/scope encodings (N6)
7. Name functions to reveal all their effects (N7)

### Tests (T1-T9)
1. Test everything that could possibly break (T1)
2. Use coverage tools to find gaps (T2)
3. Write even trivial tests -- documentary value exceeds cost (T3)
4. Use ignored/skipped tests to document requirement ambiguities (T4)
5. Focus on boundary conditions (T5)
6. When you find a bug, exhaustively test the surrounding code (T6)
7. Analyze failure patterns for diagnostic clues (T7)
8. Use coverage patterns to understand failures (T8)
9. Keep tests fast -- slow tests don't get run (T9)

---

## Self-Improvement Protocol

After every code review using this skill:

1. **Tally**: Count how many of each smell ID you found (e.g., "3x G5, 2x N1, 1x C5")
2. **Prioritize**: Fix Critical smells immediately, High Priority in current sprint
3. **Track patterns**: Note which smell categories appear most often in the codebase -- this reveals systematic issues
4. **Root cause**: If G5 (Duplication) keeps appearing, the team may need better abstraction patterns. If N1 (Poor Names) is frequent, a naming convention discussion is needed. If T1 (Insufficient Tests) dominates, invest in test infrastructure.
5. **Measure progress**: Re-scan the same module after fixes. The smell count should decrease monotonically.
6. **Internalize**: The goal is not to follow a list of rules mechanically. Clean code is not written by following a set of rules. You don't become a software craftsman by learning a list of heuristics. Professionalism and craftsmanship come from values that drive disciplines. This list is a value system -- internalize it until detecting smells becomes automatic.
