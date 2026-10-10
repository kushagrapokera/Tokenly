---
name: clean-code-ch06-objects-and-data-structures
description: "Code quality checker based on Clean Code Ch6: Objects and Data Structures -- checks data abstraction, object/data anti-symmetry, Law of Demeter (train wrecks), hybrid avoidance, DTO/Active Record usage. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 6: Objects and Data Structures -- Code Quality Checker

## Core Thesis

There is a reason we keep variables private: we do not want anyone else to depend on them. We want the freedom to change their type or implementation on a whim. Yet programmers routinely add getters and setters, exposing private variables as if they were public. This chapter establishes the fundamental dichotomy between objects and data structures and the rules that govern clean usage of each.

---

## When to Use

Invoke this skill when reviewing or writing code that involves ANY of the following:

- Classes, structs, interfaces, or types that hold data
- Getter/setter methods or property accessors
- Method chains (e.g., `a.getB().getC().doSomething()`)
- Data transfer objects, DTOs, records, or bean-style classes
- Active Record patterns (ORM models with `save()`, `find()`, etc.)
- Decisions about whether to use procedural vs. object-oriented design
- Interface design for modules or libraries
- Refactoring classes that mix behavior and exposed data
- Any code where internal structure of one object is accessed through another object's return values

---

## Checklist

Run through EVERY item when reviewing code. A single "no" is a potential violation.

### 1. Data Abstraction
- [ ] Do interfaces/classes express data in **abstract terms** rather than concrete implementation details?
- [ ] Is the abstraction hiding *how* data is stored while exposing *what* operations are meaningful?
- [ ] Are getters/setters actually providing abstraction, or are they just mechanically exposing private variables?
- [ ] Do coordinate-setting methods enforce access policy (e.g., requiring both values be set atomically) rather than allowing independent manipulation of implementation details?
- [ ] Could a reader determine the internal representation from the interface? (If yes: violation.)
- [ ] Does the interface use abstract concepts (e.g., "percent fuel remaining") rather than concrete ones (e.g., "gallons of gasoline", "tank capacity in gallons")?

### 2. Data/Object Anti-Symmetry
- [ ] Is each type clearly EITHER an object (hides data, exposes behavior) OR a data structure (exposes data, has no meaningful behavior)?
- [ ] For **procedural code**: Are data structures simple (public fields, no behavior) with separate functions that operate on them?
- [ ] For **OO code**: Do objects hide their data behind abstractions and expose functions that operate on that data?
- [ ] Has the correct paradigm been chosen based on likely future changes?
  - Need to add new data types frequently? --> Use objects/polymorphism.
  - Need to add new functions frequently? --> Use data structures/procedural code.
- [ ] Is the code free from `instanceof`/type-checking chains that should be polymorphism?

### 3. Law of Demeter
- [ ] Does each method ONLY call methods on:
  - (a) Its own class (`this` / `self`)
  - (b) Objects it created within the method body
  - (c) Objects passed as arguments to the method
  - (d) Objects held in instance variables of its class
- [ ] Is the code free of **train wrecks** (chained method calls like `a.getB().getC().getD()`)?
- [ ] Are objects being *told* to do things rather than being *asked* for their internals?
- [ ] When navigating is truly needed, is the object being asked to perform the ultimate action itself (e.g., `ctxt.createScratchFileStream(classFileName)`) rather than exposing its guts?

### 4. No Hybrids
- [ ] Is the class free from being half-object/half-data-structure?
- [ ] Does the class avoid having BOTH significant behavior methods AND public variables or bean-style accessors that expose internals?
- [ ] If the class has public accessors, does it also avoid having functions that operate on business logic?

### 5. DTOs and Active Records
- [ ] Are DTOs kept pure: public variables (or bean accessors), NO business logic methods?
- [ ] Are Active Records treated as data structures, with business rules in SEPARATE objects?
- [ ] Is business logic kept out of Active Record classes (no business rule methods alongside `save()`/`find()`)?

---

## Violations to Detect

### VIOLATION 1: Concrete Exposure (Data Abstraction Failure)

**What it is:** An interface or class that reveals its implementation through its method signatures, making the internal representation obvious.

**Bad -- Concrete Point (exposes rectangular coordinate implementation):**
```java
public class Point {
  public double x;
  public double y;
}
```
This is unmistakably rectangular coordinates. The user is forced to manipulate coordinates independently. Even if `x` and `y` were private with getters/setters, the implementation would still be exposed.

**Good -- Abstract Point (hides implementation entirely):**
```java
public interface Point {
  double getX();
  double getY();
  void setCartesian(double x, double y);
  double getR();
  double getTheta();
  void setPolar(double r, double theta);
}
```
You cannot tell whether this is implemented in rectangular or polar coordinates. It might be neither. The interface enforces an access policy: you read coordinates individually but set them atomically as a complete pair.

**Bad -- Concrete Vehicle (reveals internal data format):**
```java
public interface Vehicle {
  double getFuelTankCapacityInGallons();
  double getGallonsOfGasoline();
}
```
These are clearly just accessors of variables. The concrete units ("gallons") and concepts ("tank capacity") expose how data is stored.

**Good -- Abstract Vehicle (expresses data abstractly):**
```java
public interface Vehicle {
  double getPercentFuelRemaining();
}
```
You have no idea about the form of the data. It could be calculated from gallons, liters, battery charge, or anything else. This is genuine abstraction.

**Key principle:** Hiding implementation is NOT just putting a layer of functions between variables. It is about exposing abstract interfaces that let users manipulate the *essence* of the data without knowing its implementation. Serious thought must be put into the best way to represent data. The worst option is to blithely add getters and setters.

**Detection patterns:**
- Getter/setter pairs that mirror private field names exactly
- Method names containing concrete units or implementation terms
- Interfaces where you can trivially reconstruct the backing field list
- Set methods that allow independent manipulation of coupled values

---

### VIOLATION 2: Wrong Paradigm Choice (Data/Object Anti-Symmetry Failure)

**What it is:** Using OO when procedural would be better (or vice versa), leading to code that is hard to extend in the direction it actually needs to grow.

**The fundamental dichotomy:**

- **Procedural code** (data structures + external functions): Easy to add new functions without changing existing data structures. Hard to add new data types because all functions must change.
- **OO code** (objects with polymorphism): Easy to add new data types without changing existing functions. Hard to add new functions because all classes must change.

These are diametrically opposed. What is easy for OO is hard for procedural, and vice versa.

**Procedural example (Listing 6-5) -- data structures with external functions:**
```java
public class Square {
  public Point topLeft;
  public double side;
}
public class Rectangle {
  public Point topLeft;
  public double height;
  public double width;
}
public class Circle {
  public Point center;
  public double radius;
}

public class Geometry {
  public final double PI = 3.14159265358979;

  public double area(Object shape) throws NoSuchShapeException {
    if (shape instanceof Square) {
      Square s = (Square)shape;
      return s.side * s.side;
    } else if (shape instanceof Rectangle) {
      Rectangle r = (Rectangle)shape;
      return r.height * r.width;
    } else if (shape instanceof Circle) {
      Circle c = (Circle)shape;
      return PI * c.radius * c.radius;
    }
    throw new NoSuchShapeException();
  }
}
```
Adding `perimeter()` is easy -- no shape classes change. Adding a new shape (e.g., `Triangle`) requires modifying every function in `Geometry`.

**OO example (Listing 6-6) -- polymorphic objects:**
```java
public class Square implements Shape {
  private Point topLeft;
  private double side;
  public double area() { return side * side; }
}
public class Rectangle implements Shape {
  private Point topLeft;
  private double height;
  private double width;
  public double area() { return height * width; }
}
public class Circle implements Shape {
  private Point center;
  private double radius;
  public final double PI = 3.14159265358979;
  public double area() { return PI * radius * radius; }
}
```
Adding a new shape (e.g., `Triangle`) is easy -- no existing classes change. Adding a new function (e.g., `perimeter()`) requires changing every shape class.

**Mature programmers know that the idea that everything is an object is a myth. Sometimes you really do want simple data structures with procedures operating on them.**

**Visitor pattern note:** There are ways around the OO limitation of adding new functions (e.g., VISITOR or dual-dispatch), but these techniques carry costs of their own and generally return the structure to that of a procedural program.

**Detection patterns:**
- `instanceof` / type-switch chains in OO code that should be polymorphism
- Polymorphic hierarchies where new functions are constantly being added (should be procedural)
- Data classes that never gain new subtypes but constantly gain new operations
- "Shape" hierarchies where both new types AND new operations are needed (consider Visitor pattern)

---

### VIOLATION 3: Train Wrecks (Law of Demeter -- Chained Calls)

**What it is:** Chains of method calls that navigate through multiple objects, looking like coupled train cars.

**Bad -- Train wreck:**
```java
final String outputDir = ctxt.getOptions().getScratchDir().getAbsolutePath();
```
This call chain means the calling function knows that `ctxt` has options, which contain a scratch directory, which has an absolute path. That is far too much knowledge for one function.

**Slightly better -- Split into intermediate variables:**
```java
Options opts = ctxt.getOptions();
File scratchDir = opts.getScratchDir();
final String outputDir = scratchDir.getAbsolutePath();
```
This is still potentially a Demeter violation despite being more readable. The calling module still knows that `ctxt` contains options, which contain a scratch directory, which has an absolute path.

**Critical distinction -- Is it objects or data structures?**

Whether this violates the Law of Demeter depends entirely on whether `ctxt`, `Options`, and `ScratchDir` are **objects** or **data structures**:

- **If they are objects:** Their internal structure should be hidden, and navigating through their innards IS a clear Demeter violation.
- **If they are data structures:** They naturally expose their internal structure, and Demeter does not apply. The following would be equivalent and nobody would question it:
  ```java
  final String outputDir = ctxt.options.scratchDir.absolutePath;
  ```

**The confusion arises from accessor functions.** If data structures had public variables and no functions, while objects had private variables and public functions, this issue would be far less confusing. But frameworks like JavaBeans demand that even simple data structures have accessors and mutators, blurring the line.

**The Law of Demeter formally states:** A method `f` of class `C` should only call methods of:
1. `C` itself
2. An object created by `f`
3. An object passed as an argument to `f`
4. An object held in an instance variable of `C`

The method should NOT invoke methods on objects returned by any of the allowed functions. Talk to friends, not to strangers.

**Detection patterns:**
- More than one dot in a statement (e.g., `a.b().c()`) where the intermediate values are objects, not data structures
- Methods that know the navigation path through multiple objects
- Functions that reach through several layers of abstraction to get data

---

### VIOLATION 4: Hybrids (Half-Object, Half-Data-Structure)

**What it is:** A class that has functions that do significant things AND public variables or accessors/mutators that expose internal data, making it neither a proper object nor a proper data structure.

**Why they are the worst of both worlds:**
- Hard to add new functions (like data structures in procedural code)
- Hard to add new data types (like objects in OO code)
- They tempt external functions to use the variables the way a procedural program would use a data structure (Feature Envy)

**Detection patterns:**
- Classes with business logic methods alongside getter/setter pairs for most fields
- Classes where some methods do real computation while other methods just shuttle data in and out
- Classes that you cannot cleanly categorize as "data holder" or "behavior provider"
- Authors who are unsure whether they need protection from functions or types

**How to fix:** Split the class. Extract the data into a pure data structure. Extract the behavior into a proper object that hides its internals.

---

### VIOLATION 5: Hiding Structure Failure (Asking Instead of Telling)

**What it is:** When objects are queried for their internals so the caller can make a decision, instead of being told to perform the action themselves.

**Bad -- Asking objects for their guts, then acting on it:**
```java
// Caller navigates to get path, then uses it to create a file
String outFile = outputDir + "/" + className.replace('.', '/') + ".class";
FileOutputStream fout = new FileOutputStream(outFile);
BufferedOutputStream bos = new BufferedOutputStream(fout);
```
The caller discovered the scratch directory path only to create a file there. The mixing of different abstraction levels (dots, slashes, file extensions, File objects, strings) is troubling.

**Bad -- Delegating navigation but still asking:**
```java
ctxt.getAbsolutePathOfScratchDirectoryOption();  // Explosion of methods on ctxt
```
or:
```java
ctx.getScratchDirectoryOption().getAbsolutePath();  // Presumes data structure return
```
The first leads to method explosion. The second presumes `getScratchDirectoryOption()` returns a data structure, not an object. Neither option feels good.

**Good -- Telling the object to do what you actually need:**
```java
BufferedOutputStream bos = ctxt.createScratchFileStream(classFileName);
```
This is a reasonable thing to ask an object to do. It allows `ctxt` to hide its internals. The current function no longer needs to violate the Law of Demeter by navigating through objects it should not know about. The object is told to *do something*, not asked to *reveal something*.

**Key principle:** If an object is supposed to hide its internal structure, we should not be navigating through it. We should be telling it to do something. Ask yourself: "Why do I need this internal data?" Then tell the object to accomplish that ultimate goal instead.

**Detection patterns:**
- Getting internal data from an object, then using that data to perform an action the object could do itself
- Methods that extract paths, IDs, or references from objects only to pass them to constructors or other methods
- Code that mixes abstraction levels (string manipulation alongside object method calls)

---

### VIOLATION 6: Impure DTOs (Business Logic in Data Transfer Objects)

**What it is:** Adding business rule methods to classes whose purpose is to transfer data.

**DTOs (Data Transfer Objects)** are the quintessential data structure: a class with public variables and no functions. They are useful for communicating with databases, parsing messages from sockets, and as the first stage in translating raw data into application objects.

**Bean form** (common but provides no real benefit over public variables):
```java
public class Address {
  private String street;
  private String streetExtra;
  private String city;
  private String state;
  private String zip;

  public Address(String street, String streetExtra,
                 String city, String state, String zip) {
    this.street = street;
    this.streetExtra = streetExtra;
    this.city = city;
    this.state = state;
    this.zip = zip;
  }

  public String getStreet() { return street; }
  public String getStreetExtra() { return streetExtra; }
  public String getCity() { return city; }
  public String getState() { return state; }
  public String getZip() { return zip; }
}
```
The quasi-encapsulation of beans seems to make OO purists feel better but usually provides no other benefit. This is a DTO -- it should stay pure.

**Detection patterns:**
- DTO/record/struct classes that also contain validation logic, formatting, or calculation methods
- "Bean" classes with business methods mixed in alongside getters/setters

---

### VIOLATION 7: Active Record Misuse (Business Rules in Active Records)

**What it is:** Treating Active Records as objects by stuffing business rule methods into them.

**Active Records** are special DTOs. They are data structures with public (or bean-accessed) variables that also have navigational methods like `save()` and `find()`. They are typically direct translations from database tables.

**Bad -- Business rules crammed into Active Record:**
```java
public class Employee extends ActiveRecord {
  // data fields + save/find from ActiveRecord...

  public double calculatePay() { /* business logic */ }
  public void promote() { /* business logic */ }
  public boolean isEligibleForBonus() { /* business logic */ }
}
```
This creates an awkward hybrid between a data structure and an object.

**Good -- Active Record as pure data structure, business rules in separate object:**
```java
// Active Record: pure data structure
public class EmployeeRecord extends ActiveRecord {
  public String name;
  public double salary;
  public String department;
  // save(), find() inherited -- these are navigational, not business logic
}

// Business object: hides internal data, exposes behavior
public class Employee {
  private EmployeeRecord record;

  public double calculatePay() { /* uses record internally */ }
  public void promote() { /* uses record internally */ }
  public boolean isEligibleForBonus() { /* uses record internally */ }
}
```

The solution is to treat the Active Record as a data structure and create separate objects that contain the business rules and hide their internal data (which are probably just instances of the Active Record).

**Detection patterns:**
- ORM model classes with methods beyond persistence (`save`, `find`, `delete`)
- Database-mapped classes containing calculation, validation, or workflow logic
- Classes that inherit from an ORM base AND contain domain-specific business methods

---

## How to Fix

### Fix 1: Replace Concrete Interfaces with Abstract Ones
1. Identify getter/setter pairs that mirror internal fields.
2. Ask: "What is the *essence* of this data to the consumer?"
3. Redesign the interface around abstract concepts (percentages, behaviors, capabilities) rather than concrete storage details.
4. Enforce access policies through the interface (e.g., atomic setters for coupled values).
5. Ensure a reader cannot determine the internal representation from the interface alone.

### Fix 2: Choose the Right Paradigm
1. Ask: "Will this code more likely gain new data types or new functions?"
2. If **new data types** are more likely: use objects with polymorphism (OO).
3. If **new functions** are more likely: use data structures with procedures (procedural).
4. Do not assume OO is always correct. Mature programmers pick the approach best for the job.
5. Convert `instanceof` chains to polymorphism when new types are expected.
6. Convert polymorphic hierarchies to procedural code when new operations are expected.

### Fix 3: Break Train Wrecks by Telling, Not Asking
1. Identify the chain: `a.getB().getC().doSomething()`.
2. Determine if the intermediates are objects or data structures.
3. **If data structures:** Convert to field access (`a.b.c.something`) and accept the chain -- Demeter does not apply to data structures.
4. **If objects:** Ask "Why do I need to navigate this deep?" Identify the *ultimate goal* of the navigation.
5. Add a method to the nearest object that accomplishes the ultimate goal directly.
   - Before: `ctxt.getOptions().getScratchDir().getAbsolutePath()` + file creation code
   - After: `ctxt.createScratchFileStream(classFileName)`
6. The object hides its structure and does the work internally.

### Fix 4: Split Hybrids
1. Identify the dual nature: which methods are "behavior" and which are "data access"?
2. Extract a pure data structure (public fields or bean accessors, no logic).
3. Extract a proper object (private data, public behavior methods) that wraps the data structure.
4. External code uses the object for behavior, the data structure for data transfer.

### Fix 5: Purify DTOs
1. Remove all business logic methods from DTOs.
2. Move business logic into dedicated service or domain objects.
3. Keep DTOs as pure data carriers: constructors, fields (or bean accessors), and nothing else.

### Fix 6: Separate Active Records from Business Objects
1. Keep the Active Record as a pure data structure with only persistence methods (`save`, `find`, `delete`).
2. Create a separate business object class.
3. The business object wraps the Active Record internally and exposes domain behavior.
4. External code interacts with the business object, never directly adding business rules to the Active Record.

---

## Decision Framework: Object vs. Data Structure

```
Is this type primarily about BEHAVIOR or DATA?
|
|-- BEHAVIOR (hide data, expose operations)
|   --> Use an OBJECT
|   --> Private fields, no getters/setters
|   --> Public methods that DO things
|   --> Good for: polymorphism, adding new types
|   --> Law of Demeter APPLIES
|
|-- DATA (expose data, no meaningful behavior)
|   --> Use a DATA STRUCTURE
|   --> Public fields (or bean accessors if framework requires)
|   --> No business logic methods
|   --> Good for: procedural code, adding new functions
|   --> Law of Demeter DOES NOT APPLY
|
|-- BOTH?
    --> You have a HYBRID -- split it into two classes
```

---

## Law of Demeter -- Complete Reference

### Formal Rule
A method `f` of class `C` may only call methods on:
1. **C** itself (`this.method()`)
2. An object **created by f** (`new Thing().method()`)
3. An object **passed as a parameter** to f (`param.method()`)
4. An object **held in an instance variable** of C (`this.field.method()`)

It must NOT call methods on objects **returned by** any of the above. "Talk to friends, not to strangers."

### Edge Cases and Clarifications

| Scenario | Violation? | Reason |
|----------|-----------|--------|
| `this.field.method()` | No | Instance variable is a "friend" |
| `param.method()` | No | Parameter is a "friend" |
| `new Foo().method()` | No | Locally created object is a "friend" |
| `this.getField().method()` | Yes (if object) | Return value is a "stranger" |
| `param.getX().doY()` | Yes (if object) | Navigating through a stranger |
| `a.b.c` (data structure fields) | No | Demeter applies to objects, not data structures |
| `list.stream().filter().map()` | No | Fluent APIs on same logical object / builder pattern |
| `builder.setA().setB().build()` | No | Builder returns itself, not a stranger |
| `dto.name` (public field) | No | Data structure, not an object |
| `dto.getName()` | No* | Data structure with accessors -- Demeter does not apply to data structures |

*The confusion arises because accessor functions make data structures look like objects. If you are unsure whether something is an object or data structure, that itself is a design smell (likely a hybrid).

### The "Tell, Don't Ask" Corollary
When you find yourself reaching into an object's structure, stop and ask: "What am I trying to accomplish?" Then tell the object to accomplish that goal itself.

- **Ask (bad):** "Give me your scratch directory path so I can create a file there."
- **Tell (good):** "Create a scratch file stream for this class name."

---

## Chapter Conclusion (Verbatim Essence)

Objects expose behavior and hide data. This makes it easy to add new kinds of objects without changing existing behaviors. It also makes it hard to add new behaviors to existing objects. Data structures expose data and have no significant behavior. This makes it easy to add new behaviors to existing data structures but makes it hard to add new data structures to existing functions.

In any given system we will sometimes want the flexibility to add new data types, and so we prefer objects for that part of the system. Other times we will want the flexibility to add new behaviors, and so in that part of the system we prefer data types and procedures. **Good software developers understand these issues without prejudice and choose the approach that is best for the job at hand.**

### Bibliography

- **[Refactoring]:** *Refactoring: Improving the Design of Existing Code*, Martin Fowler et al., Addison-Wesley, 1999. (Referenced in context of Feature Envy -- when external functions use another object's variables as a procedural program would use a data structure.)

---

## Self-Improvement Protocol

After each review, update your understanding:

1. **Track recurring patterns:** If a codebase frequently mixes objects and data structures, note the architectural root cause (e.g., ORM framework encouraging hybrids).
2. **Calibrate severity:**
   - Train wrecks on confirmed data structures: low severity (cosmetic).
   - Train wrecks on objects: high severity (coupling, fragility).
   - Hybrids: high severity (worst of both worlds).
   - Concrete interfaces where abstract would work: medium severity (lost flexibility).
   - Business logic in Active Records: high severity (architectural debt).
3. **Context-sensitive judgment:** The "right" answer depends on whether the system needs new types or new functions. Do not dogmatically apply OO when procedural is more appropriate, and vice versa.
4. **Framework awareness:** Some frameworks (JavaBeans, ORMs, serialization libraries) force accessor patterns on data structures. Distinguish framework-mandated accessors from genuine abstraction failures.
5. **Language idioms:** In languages with properties (C#, Python, Kotlin), property syntax may blur the line between field access and method calls. Apply the principle (abstract vs. concrete) rather than the syntax.
6. **Accumulate per-project norms:** If a project consistently uses DTOs one way, flag deviations. If a project has a clear object/data-structure boundary, enforce it consistently.
