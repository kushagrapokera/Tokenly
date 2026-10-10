---
name: clean-code-ch10-classes
description: "Code quality checker based on Clean Code Ch10: Classes -- checks class size, Single Responsibility Principle, cohesion, organization, encapsulation, Open/Closed Principle, and Dependency Inversion. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 10: Classes -- Code Quality Checker

> Chapter written with Jeff Langr. References: [RDD] *Object Design*, Wirfs-Brock et al.; [PPP] *Agile Software Development*, Robert C. Martin; [Knuth92] *Literate Programming*, Donald Knuth.

## When to Use

Apply this skill when:
- Reviewing or writing any class, struct, module, or type definition
- A class feels "too big" or hard to name concisely
- You see a class with many instance variables used by only some methods
- Adding new functionality requires modifying existing classes
- Tests are hard to write because of concrete dependencies
- A class name contains weasel words: Processor, Manager, Super
- Refactoring for maintainability, testability, or extensibility

## Checklist

### 1. Class Organization (Internal Ordering)

Follow the standard convention for internal ordering of class members:

1. **Public static constants** come first
2. **Private static variables** come next
3. **Private instance variables** follow
4. **Public functions** come after variables
5. **Private utilities** called by a public function appear immediately after that public function (stepdown rule)

There is seldom a good reason to have a public variable. The class should read like a newspaper article -- top-level public API first, then supporting private details descending in abstraction.

### 2. Encapsulation

- Keep variables and utility functions **private** by default
- Loosen to **protected** or package scope only when a test in the same package genuinely needs access
- Always look for a way to maintain privacy first; loosening encapsulation is a **last resort**
- Never make something public just for convenience -- ask whether the design can be improved instead

### 3. Classes Should Be Small

**The first rule of classes is that they should be small. The second rule is that they should be smaller than that.**

- With functions, size is measured by counting **physical lines**
- With classes, size is measured by counting **responsibilities** (not lines or method count)
- A class with only 5 public methods can still be too large if it has too many responsibilities (see SuperDashboard example below)

**The SuperDashboard Anti-Pattern (Listing 10-1, "Too Many Responsibilities"):**
A class with ~70 public methods is a "God class." The full Listing 10-1 spans multiple pages with methods like `getCustomizerLanguagePath()`, `getSystemConfigDocument()`, `getGuruState()`, `isMetadataDirty()`, `getLastFocusedComponent()`, `getMajorVersionNumber()`, `getFileManager()`, `getConfigManager()`, `runProject()`, etc. Some developers might refer to `SuperDashboard` as a "God class."

**But what if it only had the 5 methods shown in Listing 10-2 ("Small Enough?")?**

```java
// Listing 10-2: Small Enough?
public class SuperDashboard extends JFrame implements MetaDataUser
    public Component getLastFocusedComponent()
    public void setLastFocused(Component lastFocused)
    public int getMajorVersionNumber()
    public int getMinorVersionNumber()
    public int getBuildNumber()
}
```

Five methods isn't too much, is it? In this case it is because despite its small number of methods, `SuperDashboard` has too many *responsibilities*.

This class has TWO reasons to change: (1) It tracks version information that would seemingly need to be updated every time the software gets shipped. (2) It manages Java Swing components (it is a derivative of `JFrame`, the Swing representation of a top-level GUI window). No doubt we'll want to update the version number if we change any of the Swing code, but the converse isn't necessarily true: We might change the version information based on changes to other code in the system.

### 4. The Single Responsibility Principle (SRP)

**A class or module should have one, and only one, reason to change.**

SRP is both a definition of responsibility and a guideline for class size. It is one of the most important concepts in OO design, yet the most frequently abused.

#### The 25-Word Description Test

You should be able to write a brief description of the class in about **25 words, without using the words "if," "and," "or," or "but."**

- If the description requires "and," the class likely has too many responsibilities
- If you cannot derive a concise name, the class is likely too large
- The more ambiguous the name, the more likely it has too many responsibilities

**Example failure:** "The SuperDashboard provides access to the component that last held the focus, **and** it also allows us to track the version and build numbers." The word "and" reveals two responsibilities.

#### Weasel Word Names

Class names including **Processor**, **Manager**, or **Super** often hint at an unfortunate aggregation of responsibilities. These names are too vague and signal that the class is doing too much.

#### SRP Refactoring -- Extract Version (Listing 10-3):

```java
// GOOD -- single responsibility extracted
public class Version {
    public int getMajorVersionNumber()
    public int getMinorVersionNumber()
    public int getBuildNumber()
}
```

The Version class has high potential for reuse across other applications.

#### Why SRP Is Violated So Often

- Getting software to **work** and making it **clean** are two very different activities
- Most of us have limited room in our heads, so we focus on getting our code to work more than organization and cleanliness -- this is wholly appropriate
- **Maintaining a separation of concerns is just as important in our programming *activities* as it is in our programs** -- the problem is that too many of us think we are done once the program works
- We fail to switch to the *other* concern of organization and cleanliness. We move on to the next problem rather than going back and breaking the overstuffed classes into decoupled units with single responsibilities
- Many developers fear that a large number of small, single-purpose classes makes it more difficult to understand the bigger picture -- they are concerned they must navigate from class to class to figure out how a larger piece of work gets accomplished

#### Many Small Classes vs. Few Large Classes

A system with many small classes has **no more moving parts** than a system with a few large classes. There is just as much to learn in the system with a few large classes. The same amount of logic and complexity exists either way.

The question is: **Do you want your tools organized into toolboxes with many small drawers each containing well-defined and well-labeled components? Or do you want a few drawers that you just toss everything into?**

**Every sizable system will contain a large amount of logic and complexity.** The primary goal in managing such complexity is to **organize** it so that a developer knows where to look to find things and need only understand the directly affected complexity at any given time. In contrast, a system with larger, multipurpose classes always hampers us by insisting we wade through lots of things we don't need to know right now.

Each small class should:
- Encapsulate a single responsibility
- Have a single reason to change
- Collaborate with a few others to achieve desired system behaviors

### 5. Cohesion

**Classes should have a small number of instance variables. Each method should manipulate one or more of those variables.**

- The more variables a method manipulates, the more cohesive that method is to its class
- **Maximum cohesion:** every method uses every instance variable
- In practice, maximal cohesion is neither advisable nor possible, but aim for **high** cohesion
- High cohesion means the methods and variables of the class are co-dependent and hang together as a **logical whole**

**The Stack Example -- A Highly Cohesive Class (Listing 10-4):**

```java
public class Stack {
    private int topOfStack = 0;
    List<Integer> elements = new LinkedList<Integer>();

    public int size() {
        return topOfStack;
    }

    public void push(int element) {
        topOfStack++;
        elements.add(element);
    }

    public int pop() throws PoppedWhenEmpty {
        if (topOfStack == 0)
            throw new PoppedWhenEmpty();
        int element = elements.get(--topOfStack);
        elements.remove(topOfStack);
        return element;
    }
}
```

Only `size()` fails to use both variables. The class is very cohesive.

#### Cohesion Metric

For each class, evaluate: **What fraction of instance variables does each method use?**
- If many methods use only a subset of variables, the class is losing cohesion
- A proliferation of instance variables used by only a subset of methods signals that at least one other class is trying to get out of the larger class
- **When classes lose cohesion, split them!**

### 6. Maintaining Cohesion Results in Many Small Classes

Breaking large functions into smaller functions causes a proliferation of classes -- and this is a GOOD thing.

**The mechanism:**
1. You have a large function with many local variables
2. You want to extract a small part into a separate function
3. The extracted code uses 4 of the variables declared in the large function
4. Instead of passing all 4 as arguments, **promote them to instance variables**
5. Now you can extract the code without passing any arguments
6. BUT this means the class is losing cohesion (more instance variables used by only some methods)
7. When this happens, **split the class** so that the new classes are more cohesive

**The PrintPrimes Refactoring (Listings 10-5 through 10-8):**

The example is a translation into Java of Knuth's `PrintPrimes` program from *Literate Programming* [Knuth92]. Listing 10-5 shows the original: a single monolithic class with one huge `main` method -- a deeply indented structure, a plethora of odd variables, and a tightly coupled structure. At the very least, the one big function should be split up into a few smaller functions.

Listings 10-6 through 10-8 show the refactored result -- three classes, each with a single responsibility:

| Class | Responsibility | Changes when... |
|---|---|---|
| `PrimePrinter` (Listing 10-6) | Handles the execution environment / main program | Method of invocation changes (e.g., converted to a SOAP service) |
| `RowColumnPagePrinter` (Listing 10-7) | Knows how to format a list of numbers into pages with a certain number of rows and columns | Output formatting requirements change |
| `PrimeGenerator` (Listing 10-8) | Knows how to generate a list of prime numbers. **Not meant to be instantiated as an object** -- the class is just a useful scope in which its variables can be declared and kept hidden | Algorithm for computing prime numbers changes |

Key observations about this refactoring:
- The program got **longer** (from a little over one page to nearly three pages) because of: (1) longer, more descriptive variable names, (2) function and class declarations used as a way to add commentary to the code, and (3) whitespace and formatting techniques to keep the program readable
- **It was not a rewrite!** We did not start over from scratch and write the program over again. If you look closely at the two different programs, you'll see that they use the same algorithm and mechanics to get their work done
- The change was made by writing a test suite that verified the **precise** behavior of the first program. Then a myriad of tiny little changes were made, one at a time. After each change the program was executed to ensure that the behavior had not changed. One tiny step after another, the first program was cleaned up and transformed into the second
- Each class is now small, cohesive, and has a single reason to change

### 7. Organizing for Change (Open/Closed Principle)

**For most systems, change is continual. Every change subjects us to the risk that the remainder of the system no longer works as intended. In a clean system we organize our classes so as to reduce the risk of change.**

**The Sql Anti-Pattern (Listing 10-9, "A class that must be opened for change"):**

The `Sql` class is used to generate properly formed SQL strings given appropriate metadata. It's a work in progress and, as such, doesn't yet support SQL functionality like `update` statements. When the time comes for the `Sql` class to support an `update` statement, we'll have to "open up" this class to make modifications. The problem with opening a class is that it introduces risk. Any modifications to the class have the potential of breaking other code in the class. It must be fully retested.

```java
// BAD -- must be opened for modification
public class Sql {
    public Sql(String table, Column[] columns)
    public String create()
    public String insert(Object[] fields)
    public String selectAll()
    public String findByKey(String keyColumn, String keyValue)
    public String select(Column column, String pattern)
    public String select(Criteria criteria)
    public String preparedInsert()
    private String columnList(Column[] columns)
    private String valuesList(Object[] fields, final Column[] columns)
    private String selectWithCriteria(String criteria)
    private String placeholderList(Column[] columns)
}
```

This class violates SRP with **two reasons to change:**
1. When we add a new type of statement (e.g., `update`)
2. When we alter the details of a single statement type (e.g., modifying `select` to support subselects)

**Organizational smell:** Private methods like `selectWithCriteria` that apply only to a subset of the public methods reveal that different responsibilities are tangled together. **Private method behavior that applies only to a small subset of a class can be a useful heuristic for spotting potential areas for improvement.**

**However:** The primary spur for taking action should be **system change itself**. If the `Sql` class is deemed logically complete, then we need not worry about separating the responsibilities. If we won't need `update` functionality for the foreseeable future, then we should leave `Sql` alone. But as soon as we find ourselves **opening up a class** to make changes, we should consider fixing our design.

**The Refactored Sql -- A Set of Closed Classes (Listing 10-10):**

```java
// GOOD -- closed for modification, open for extension
abstract public class Sql {
    public Sql(String table, Column[] columns)
    abstract public String generate();
}

public class CreateSql extends Sql {
    public CreateSql(String table, Column[] columns)
    @Override public String generate()
}

public class SelectSql extends Sql {
    public SelectSql(String table, Column[] columns)
    @Override public String generate()
}

public class InsertSql extends Sql {
    public InsertSql(String table, Column[] columns, Object[] fields)
    @Override public String generate()
    private String valuesList(Object[] fields, final Column[] columns)
}

public class SelectWithCriteriaSql extends Sql {
    public SelectWithCriteriaSql(
        String table, Column[] columns, Criteria criteria)
    @Override public String generate()
}

public class SelectWithMatchSql extends Sql {
    public SelectWithMatchSql(
        String table, Column[] columns, Column column, String pattern)
    @Override public String generate()
}

public class FindByKeySql extends Sql {
    public FindByKeySql(
        String table, Column[] columns, String keyColumn, String keyValue)
    @Override public String generate()
}

public class PreparedInsertSql extends Sql {
    public PreparedInsertSql(String table, Column[] columns)
    @Override public String generate()
    private String placeholderList(Column[] columns)
}

public class Where {
    public Where(String criteria)
    public String generate()
}

public class ColumnList {
    public ColumnList(Column[] columns)
    public String generate()
}
```

**Benefits of this restructuring:**
- Code in each class is **excruciatingly simple**
- Comprehension time drops to **almost nothing**
- Risk that one function breaks another becomes **vanishingly small**
- Testing is easier because all bits of logic are **isolated from one another**
- Private methods (e.g., `valuesList`) move directly to the subclass where they are needed
- Common private behavior is isolated to utility classes (`Where`, `ColumnList`)

**To add `update` functionality:** Create a new `UpdateSql extends Sql` subclass. **None of the existing classes need to change.** No other code in the system will break.

This supports the **Open-Closed Principle (OCP):** Classes should be **open for extension but closed for modification.** Our restructured `Sql` class is open to allow new functionality via subclassing, but we can make this change while keeping every other class closed. We simply drop our `UpdateSql` class in place.

**We want to structure our systems so that we muck with as little as possible when we update them with new or changed features. In an ideal system, we incorporate new features by extending the system, not by making modifications to existing code.**

### 8. Isolating from Change (Dependency Inversion Principle)

**Needs will change, therefore code will change.** We learned in OO 101 that there are:
- **Concrete classes** -- contain implementation details (code)
- **Abstract classes / Interfaces** -- represent concepts only

A client class depending upon concrete details is at risk when those details change. We can introduce interfaces and abstract classes to help **isolate the impact of those details.**

Dependencies upon concrete details create challenges for testing our system.

**The Portfolio / StockExchange Example:**

Problem: We're building a `Portfolio` class and it depends upon an external `TokyoStockExchange` API to derive the portfolio's value. Our test cases are impacted by the volatility of such a lookup. It's hard to write a test when we get a different answer every five minutes!

```java
// GOOD -- depend on abstraction, not concrete detail
public interface StockExchange {
    Money currentPrice(String symbol);
}

public class Portfolio {
    private StockExchange exchange;
    public Portfolio(StockExchange exchange) {
        this.exchange = exchange;
    }
    // ...
}
```

Now tests can use a stub:

```java
public class PortfolioTest {
    private FixedStockExchangeStub exchange;
    private Portfolio portfolio;

    @Before
    protected void setUp() throws Exception {
        exchange = new FixedStockExchangeStub();
        exchange.fix("MSFT", 100);
        portfolio = new Portfolio(exchange);
    }

    @Test
    public void GivenFiveMSFTTotalShouldBe500() throws Exception {
        portfolio.add(5, "MSFT");
        Assert.assertEquals(500, portfolio.value());
    }
}
```

**Dependency Inversion Principle (DIP):** Classes should depend upon **abstractions**, not on **concrete details.** Instead of being dependent upon the implementation details of the `TokyoStockExchange` class, our `Portfolio` class is now dependent upon the `StockExchange` interface. The `StockExchange` interface represents the abstract concept of asking for the current price of a symbol. This abstraction isolates all of the specific details of obtaining such a price, including from where that price is obtained.

Benefits of DIP:
- **If a system is decoupled enough to be tested this way, it will also be more flexible and promote more reuse** -- the lack of coupling means elements are better isolated from each other and from change
- Isolation makes each element of the system **easier to understand**
- Enables testability through test doubles (stubs, mocks, fakes)
- Dependencies upon concrete details create challenges for testing (e.g., stock prices that change every five minutes make tests unreliable)

## Violations to Detect

### Critical Violations

| ID | Violation | Detection Heuristic |
|---|---|---|
| C1 | **God Class** | Class with 70+ public methods, or implements multiple unrelated interfaces |
| C2 | **Multiple Reasons to Change** | Class description requires "and" / "or" / "but" to explain what it does |
| C3 | **Failed 25-Word Test** | Cannot describe the class in ~25 words without conjunctions ("if", "and", "or", "but") |
| C4 | **Weasel Word Names** | Class named with Processor, Manager, Super, Handler, Data, Info (vague aggregation names) |
| C5 | **Concrete Dependency on Volatile Details** | Constructor or field directly instantiates a concrete service class (e.g., `new TokyoStockExchange()`) instead of accepting an interface |
| C6 | **Forced Modification for Extension** | Adding new functionality requires modifying existing class body rather than creating a new subclass or implementation |

### Structural Violations

| ID | Violation | Detection Heuristic |
|---|---|---|
| S1 | **Low Cohesion** | Instance variables are used by only a small subset of methods; clusters of methods each use different subsets of fields |
| S2 | **Private Methods Serving Only One Public Method** | Private helper that is only relevant to one area of the class (signals a hidden class wanting to get out) |
| S3 | **Wrong Member Ordering** | Public variables declared after private ones; private utilities placed far from the public function that calls them; constants not at top |
| S4 | **Gratuitous Public Exposure** | Variables or utility functions made public/protected without justification; encapsulation loosened without first seeking a design improvement |
| S5 | **Monolithic Function Promoting Variables** | Large function broken into smaller ones by promoting locals to instance variables, but the class was never subsequently split -- resulting in low cohesion |
| S6 | **Mixed Abstraction Levels in One Class** | Class contains both high-level orchestration logic and low-level implementation details that should be in separate classes |

## How to Fix

### Fix 1: Extract Class by Responsibility (SRP)

When a class has multiple reasons to change, extract each responsibility into its own class.

**Before:**
```java
public class SuperDashboard extends JFrame implements MetaDataUser {
    public Component getLastFocusedComponent()
    public void setLastFocused(Component lastFocused)
    public int getMajorVersionNumber()
    public int getMinorVersionNumber()
    public int getBuildNumber()
}
```

**After:**
```java
public class SuperDashboard extends JFrame implements MetaDataUser {
    public Component getLastFocusedComponent()
    public void setLastFocused(Component lastFocused)
}

public class Version {
    public int getMajorVersionNumber()
    public int getMinorVersionNumber()
    public int getBuildNumber()
}
```

**Steps:**
1. Identify the distinct reasons to change (group related methods)
2. Create a new class for each distinct responsibility
3. Move the relevant methods and the instance variables they use
4. Update callers to use the new class

### Fix 2: Replace Conditional/Branching Class with Polymorphism (OCP)

When a class uses conditionals or switch statements to handle different types of behavior, refactor to an abstract base class with concrete subclasses.

**Before:**
```java
public class Sql {
    public String create() { ... }
    public String insert(Object[] fields) { ... }
    public String selectAll() { ... }
    // Must modify this class to add update()
}
```

**After:**
```java
abstract public class Sql {
    abstract public String generate();
}
public class CreateSql extends Sql { @Override public String generate() { ... } }
public class InsertSql extends Sql { @Override public String generate() { ... } }
public class SelectSql extends Sql { @Override public String generate() { ... } }
// To add update: just create UpdateSql extends Sql -- no existing code changes
```

**Steps:**
1. Identify the abstract concept (e.g., "SQL statement generation")
2. Create an abstract base class or interface with the common contract
3. Create one concrete subclass per variant
4. Move private helpers into the subclass where they are used
5. Extract shared private behavior into utility classes (e.g., `Where`, `ColumnList`)

### Fix 3: Restore Cohesion by Splitting

When promoting variables from function locals to instance scope causes cohesion loss, split the class.

**Steps:**
1. Identify clusters of methods that share the same subset of instance variables
2. Extract each cluster (methods + their variables) into a new class
3. The resulting classes will each be more cohesive

**Signal:** After breaking a large function into smaller functions by promoting locals to instance variables, check whether all methods use all instance variables. If not, split.

### Fix 4: Introduce Interface for Dependency Inversion (DIP)

When a class directly depends on a volatile concrete implementation, introduce an interface.

**Before:**
```java
public class Portfolio {
    private TokyoStockExchange exchange = new TokyoStockExchange();
}
```

**After:**
```java
public interface StockExchange {
    Money currentPrice(String symbol);
}

public class Portfolio {
    private StockExchange exchange;
    public Portfolio(StockExchange exchange) {
        this.exchange = exchange;
    }
}
```

**Steps:**
1. Identify the concrete dependency that is volatile or hard to test
2. Define an interface representing the abstract concept
3. Have the concrete class implement the interface
4. Change the client to accept the interface via constructor injection
5. In tests, provide a stub/mock implementation

### Fix 5: Reorder Class Members

When members are in the wrong order, reorganize following the newspaper metaphor.

**Correct order:**
1. Public static constants
2. Private static variables
3. Private instance variables
4. Public functions
5. Private utilities (each placed immediately after the public function that calls it)

### Fix 6: Incremental Refactoring (Not Rewriting)

When restructuring a large class or module:
1. **Write a test suite** that verifies the precise behavior of the existing code
2. Make a **myriad of tiny changes**, one at a time
3. After each change, **run the test suite** to ensure behavior has not changed
4. Step by step, transform the old structure into the new one
5. This is NOT a rewrite -- the same algorithms and mechanics are preserved

## Self-Improvement Protocol

When reviewing code against these rules, follow this sequence:

1. **Name Test:** Can you describe the class in ~25 words without "if", "and", "or", "but"? If not, it has too many responsibilities.

2. **Reason-to-Change Test:** List every distinct reason this class might need to change. If more than one, it violates SRP.

3. **Cohesion Audit:** For each method, list which instance variables it uses. Look for clusters that share variables -- each cluster may be a separate class.

4. **Encapsulation Check:** Are any variables or helper functions more visible than necessary? Could protected/public members be made private?

5. **Organization Check:** Are members ordered correctly (constants, static vars, instance vars, public methods, private methods in stepdown order)?

6. **OCP Test:** If you needed to add a new variant of behavior, would you have to modify this class? If yes, consider an abstract base + subclasses pattern.

7. **DIP Test:** Does this class directly instantiate or depend on concrete implementations of volatile services? If yes, introduce an interface and inject the dependency.

8. **Private Method Smell:** Do any private methods serve only one area of the class? If so, they may belong in a separate class alongside the methods they support.

9. **Toolbox Analogy:** Is this class a well-labeled small drawer with a clear purpose, or a big drawer everything gets tossed into?

10. **Refactoring Safety:** Any restructuring must be done incrementally with tests verifying behavior at each step -- never as a big-bang rewrite.
