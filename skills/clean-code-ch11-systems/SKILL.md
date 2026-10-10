---
name: clean-code-ch11-systems
description: "Code quality checker based on Clean Code Ch11: Systems -- checks construction/use separation, dependency injection, cross-cutting concerns, AOP patterns, architecture testability, decision timing, and DSL usage. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 11: Systems -- Code Quality Checker

## Core Principle

"Complexity kills. It sucks the life out of developers, it makes products difficult to plan, build, and test." -- Ray Ozzie, CTO, Microsoft Corporation. Clean systems separate concerns at every level of abstraction. At the system level, this means separating construction from use, modularizing cross-cutting concerns, keeping domain logic in plain objects (POJOs), deferring architectural decisions as long as responsibly possible, and using the simplest thing that can possibly work. Software systems are unique compared to physical systems: their architectures can grow incrementally, *if* we maintain the proper separation of concerns. An optimal system architecture consists of modularized domains of concern, each implemented with Plain Old Java (or other) Objects, integrated together with minimally invasive Aspects or Aspect-like tools, and can be test-driven, just like the code.

### The City Metaphor (Chapter Opening)
Could you manage all the details of a city yourself? Probably not. Even managing an existing city is too much for one person. Yet cities work because they have teams of people who manage particular parts -- water systems, power systems, traffic, law enforcement, building codes, and so forth. Some are responsible for the *big picture*, while others focus on the details. Cities also work because they have evolved appropriate levels of abstraction and modularity that make it possible for individuals and "components" to work effectively, even without understanding the big picture. Software teams are often organized like that too, but the systems they work on often don't have the same separation of concerns and levels of abstraction.

### The Hotel Construction Analogy
Construction is a very different process from use. As a building is being constructed, there are cranes, hard hats, work clothes, bare concrete. When finished, the building is clean, encased in glass and attractive paint, and the people working and staying there look very different. *Software systems should separate the startup process, when the application objects are constructed and the dependencies are "wired" together, from the runtime logic that takes over after startup.*

### The City Growth Analogy (Scaling Up)
Cities grow from towns, which grow from settlements. At first the roads are narrow and practically nonexistent, then they are paved, then widened over time. Small buildings and empty plots are filled with larger buildings, some of which will eventually be replaced with skyscrapers. At first there are no services like power, water, sewage, and the Internet -- these are added as population and building densities increase. This growth is not without pain ("Why didn't they build it wide enough the first time!?") but it couldn't have happened any other way. Who can justify the expense of a six-lane highway through a small town that anticipates growth?

## When to Use

Apply this checker whenever code:
- Contains application startup, initialization, or bootstrapping logic
- Uses lazy initialization/evaluation idioms (null-check-then-create patterns)
- Constructs objects that are used in the same module that creates them
- Has cross-cutting concerns like persistence, transactions, security, caching, or logging woven into business logic
- Uses or should use dependency injection (DI) containers or Inversion of Control (IoC)
- Relies on factory patterns for object creation
- Contains proxy-based or decorator-based infrastructure code
- Introduces a new framework, standard, or architectural pattern
- Makes irreversible architectural decisions early in the project lifecycle
- Implements domain logic that could benefit from a domain-specific language (DSL)
- Couples business logic tightly to a container, framework, or platform (e.g., EJB, Spring internals, ORM framework)
- Mixes configuration/wiring with runtime logic
- Is being designed at the system or module level (not just individual classes/functions)

## Checklist

### 1. Separation of Construction from Use
- [ ] The startup process (object construction, dependency wiring) is separated from runtime logic
- [ ] Application code does not know how objects are constructed -- it simply expects that everything has been built properly
- [ ] The `main` module (or startup modules) handles construction and passes fully-built objects to the application
- [ ] Dependency arrows from `main` point toward the application, never the reverse -- the application has no knowledge of `main` or the construction process
- [ ] Lazy initialization (null-check-then-create) is NOT scattered throughout the codebase as ad hoc construction logic mixed with runtime behavior
- [ ] If lazy initialization is used, it is isolated in a single place or handled by the DI container, not duplicated across the application
- [ ] There is a global, consistent strategy for resolving major dependencies (not ad hoc and scattered)

### 2. Factory Pattern Usage
- [ ] When the application must control *when* an object is created (not just *how*), the ABSTRACT FACTORY pattern is used
- [ ] The factory interface is defined on the application side of the boundary; the factory implementation lives on the `main`/construction side
- [ ] The application controls the timing of object creation but is decoupled from the details of *how* that creation happens
- [ ] Dependencies from factory implementations point toward the application, not away from it
- [ ] Application-specific constructor arguments can be passed through the factory without the application knowing the concrete type being created

### 3. Dependency Injection (DI) and Inversion of Control (IoC)
- [ ] Objects do NOT take direct steps to resolve their own dependencies -- they are completely passive
- [ ] Dependencies are injected via constructor arguments, setter methods, or both
- [ ] A DI container (or the `main` routine) is responsible for instantiating objects and wiring dependencies together
- [ ] Which concrete objects are used is specified through configuration (file or programmatic), not hard-coded in business logic
- [ ] The application code is almost completely decoupled from the DI framework -- only a few lines of framework-specific code are needed (e.g., `XmlBeanFactory bf = new XmlBeanFactory(new ClassPathResource("app.xml", getClass())); Bank bank = (Bank) bf.getBean("bank");`)
- [ ] Setter methods or constructor arguments are provided for each dependency, enabling the DI container to inject them
- [ ] The class does not call `new` on its major collaborators inside business methods
- [ ] DI supports the *Single Responsibility Principle* -- in the context of dependency management, an object should not take responsibility for instantiating dependencies itself; it should pass this responsibility to another "authoritative" mechanism (the `main` routine or a special-purpose container), thereby inverting the control
- [ ] If lazy-initialization is desired, it is handled by the DI container (most won't construct objects until needed, and provide mechanisms for invoking factories or constructing proxies for lazy-evaluation) rather than scattered throughout business code. Remember: "Don't forget that lazy instantiation/evaluation is just an optimization and perhaps premature!"

### 4. POJO-Based Domain Logic
- [ ] Business logic is written in Plain Old Java Objects (or the language equivalent) with no dependencies on framework infrastructure
- [ ] POJOs are conceptually simpler and easier to test because they have no framework dependencies
- [ ] Domain objects do not extend framework base classes or implement framework lifecycle interfaces unless absolutely necessary
- [ ] POJOs do not contain persistence, transaction, security, or other infrastructure concerns directly in their code
- [ ] Domain logic can be unit tested without starting a container or framework

### 5. Cross-Cutting Concerns Separation
- [ ] Cross-cutting concerns (persistence, transactions, security, caching, logging, authorization) are NOT manually spread across many objects
- [ ] Cross-cutting concerns are handled declaratively (annotations, configuration files, aspect definitions) rather than imperatively woven into every business method
- [ ] The persistence strategy is consistent across the application, not re-implemented differently in each object
- [ ] Transaction boundaries are declared, not manually coded with begin/commit/rollback in every method
- [ ] Security checks are applied via aspects or declarative mechanisms, not duplicated in every entry point
- [ ] Changes to a cross-cutting concern (e.g., switching persistence strategy) affect configuration, not business logic
- [ ] Concerns like persistence tend to cut across the *natural object boundaries* of a domain -- you want to persist all objects using generally the same strategy (e.g., using a particular DBMS vs flat files, following certain naming conventions for tables and columns, using consistent transactional semantics). The persistence framework and domain logic, in isolation, might each be modular; the problem is the fine-grained *intersection* of these domains
- [ ] In AOP, modular constructs called *aspects* specify which points in the system should have their behavior modified in some consistent way to support a particular concern. This specification is done using a succinct declarative or programmatic mechanism. The behavior modifications are made *noninvasively* (meaning no manual editing of the target source code is required) to the target code by the AOP framework

### 6. Aspect-Oriented Programming (AOP) Patterns
- [ ] AOP or aspect-like mechanisms are used for cross-cutting concerns rather than manual code duplication. The chapter examines three aspects or aspect-like mechanisms in Java: (1) Java Proxies, (2) Pure Java AOP Frameworks (Spring AOP, JBoss AOP), and (3) AspectJ Aspects
- [ ] If Java proxies are used, they are limited to simple cases (wrapping individual method calls on interfaces); for complex cases, a framework is used instead
- [ ] AOP framework configuration (Spring AOP, annotations, etc.) is kept separate from business logic
- [ ] The "Russian doll" decorator pattern (nested proxies/wrappers) is used transparently -- clients are unaware of the wrapping layers
- [ ] Aspect behavior is specified declaratively and applied noninvasively to target code
- [ ] Although XML can be verbose and hard to read, the "policy" specified in configuration files is simpler than the complicated proxy and aspect logic that is hidden from view and created automatically. The architecture of frameworks like Spring (declarative cross-cutting via XML/annotations) was so compelling it led to a complete overhaul of the EJB standard for version 3
- [ ] If AspectJ or similar is used, it is justified by the need for full-featured aspect support beyond what pure-Java AOP can provide. AspectJ is "the most full-featured tool for separating concerns through aspects" -- an extension of Java that provides "first-class" support for aspects as modularity constructs
- [ ] Pure Java AOP approaches (Spring AOP, JBoss AOP) are sufficient for 80-90 percent of the cases where aspects are most useful; AspectJ is reserved for the remaining cases that need its richer and more powerful tool set
- [ ] If AspectJ is used, consider the "annotation form" where Java 5 annotations define aspects using pure Java code, mitigating the adoption cost of learning new language constructs and tools. The Spring Framework also makes incorporation of annotation-based aspects easier for teams with limited AspectJ experience

### 7. Architecture Testability (Test Drive the System Architecture)
- [ ] The system architecture can evolve from simple to sophisticated incrementally
- [ ] It is NOT necessary to do Big Design Up Front (BDUF) -- the architecture starts "naively simple" and grows. Important distinction: BDUF is not the same as the good practice of up-front design. BDUF specifically means designing *everything* up front before implementing anything at all. There is still a significant amount of iterative exploration and discussion of details, even after construction starts
- [ ] Domain logic can be tested independently of the infrastructure/architectural choices
- [ ] Architectural decisions are reversible -- switching frameworks or infrastructure does not require rewriting domain logic
- [ ] The architecture does not inhibit adapting to change
- [ ] A good API largely "disappears" from view, so the team spends most creative effort on user stories, not fighting the architecture. The early EJB architecture is but one of many well-known APIs that are over-engineered and that compromise separation of concerns. Even well-designed APIs can be overkill when they aren't really needed
- [ ] Building architects have to do BDUF because it is not feasible to make radical architectural changes to a large physical structure once construction is well underway. Although software has its own "physics" (term coined by [Kolence]), it is economically feasible to make radical change, *if* the structure of the software separates its concerns effectively
- [ ] This does not mean going into a project "rudderless" -- we have some expectations of the general scope, goals, and schedule, as well as the general structure of the resulting system. However, we must maintain the ability to change course in response to evolving circumstances

### 8. Optimize Decision Making
- [ ] Decisions are given to the most qualified persons (decentralized management)
- [ ] Decisions are postponed until the last responsible moment -- not out of laziness, but to make informed choices with the best possible information
- [ ] Premature decisions (made with suboptimal knowledge, less customer feedback, less experience) are avoided
- [ ] The modularity provided by a POJO system with modularized concerns enables just-in-time decision making
- [ ] The complexity of decisions is reduced by the system's modular structure

### 9. Use Standards Wisely
- [ ] Standards are adopted only when they add *demonstrable* value, not because they are hyped
- [ ] Lighter-weight, more straightforward designs are preferred when a standard is overkill
- [ ] The team's focus remains on implementing value for customers, not on implementing standards for their own sake
- [ ] Standards are valued for reuse of ideas, components, recruiting, and encapsulation of good ideas -- but weighed against the cost of adoption

### 10. Domain-Specific Languages (DSLs)
- [ ] Domain logic is expressed in a language or API that reads like structured prose a domain expert would write
- [ ] DSLs minimize the "communication gap" between domain concepts and the code that implements them, just as agile practices optimize the communications within a team and with the project's stakeholders
- [ ] DSLs raise the abstraction level above code idioms and design patterns. They allow the developer to reveal the intent of the code at the appropriate level of abstraction
- [ ] If domain logic is complex, consider whether a small scripting language or fluent API could express it more clearly. Building construction, like most domains, has developed a rich language with a vocabulary, idioms, and patterns that convey essential information clearly and concisely. Similarly, software should develop DSLs for its domains
- [ ] DSLs allow all levels of abstraction and all domains in the application to be expressed as POJOs, from high-level policy to low-level details
- [ ] If you are implementing domain logic in the same language that a domain expert uses, there is less risk that you will incorrectly translate the domain into the implementation

## Violations to Detect

### V1: Construction Logic Mixed with Runtime Logic (from "Separate Constructing a System from Using It")
**Pattern:** A method that provides a service also contains object construction logic, typically via the LAZY INITIALIZATION/EVALUATION idiom: `if (service == null) { service = new MyServiceImpl(...); } return service;`
**Acknowledged merits:** This idiom has several merits -- we don't incur the overhead of construction unless we actually use the object, and our startup times can be faster as a result. We also ensure that null is never returned. However, these benefits do not outweigh the harms when the pattern is scattered throughout the codebase.
**Why it is harmful:**
- Hard-coded dependency on `MyServiceImpl` and everything its constructor requires -- cannot compile without resolving these dependencies even if the object is never used at runtime
- Testing requires either using the real `MyServiceImpl` (heavyweight) or setting up a TEST DOUBLE before the method is called -- must test all execution paths including the null-check construction path
- The method is doing two things (construction + providing a service), violating the Single Responsibility Principle
- We do not know whether `MyServiceImpl` is the right object in all cases -- the comment "Good enough default for most cases?" reveals uncertainty
- When scattered across an application, these "little setup idioms" destroy modularity and cause significant duplication of the global setup strategy
**Detection:**
- Null-check-then-construct patterns inside service methods
- `new ConcreteClass(...)` calls inside methods that also contain business logic
- Methods that both create and return objects they also use
- Constructors of concrete implementations called outside of `main`, factories, or DI configuration

### V2: No Separation of Main (from "Separation of Main")
**Pattern:** Construction logic is interleaved with application logic throughout the codebase rather than being concentrated in `main` or dedicated startup modules.
**Why it is harmful:**
- The application has implicit knowledge of the construction process
- Dependency arrows are bidirectional (application knows about construction and vice versa) instead of unidirectional (main -> application)
- The flow of control during startup is hard to follow
- Cannot reason about what the application does without also understanding how it is built
**Detection:**
- Object construction spread across multiple modules with no central coordination
- Application modules importing builder/factory/configuration classes that should only live in startup code
- No clear `main`/startup module that builds and wires the system before handing off to the application

### V3: Abstract Factory Pattern Missing When Application Needs Creation Control (from "Factories")
**Pattern:** The application needs to control *when* objects are created but directly instantiates concrete classes instead of using a factory interface.
**Why it is harmful:**
- The application is coupled to the concrete type being created (e.g., `LineItemFactory Implementation`)
- Cannot change the construction details without modifying the application code
- The dependency arrows point both ways -- application knows about concrete construction
**Book example:** In an order processing system, the application must create `LineItem` instances to add to an `Order`. Using the ABSTRACT FACTORY pattern, `main` creates a `LineItemFactoryImplementation` and passes it as the `LineItemFactory` interface. The `OrderProcessing` application calls `makeLineItem()` on the interface, controlling when items are created but remaining decoupled from how they are built.
**Detection:**
- `new ConcreteClass(...)` in application code where the application clearly needs to control creation timing but should not know the concrete type
- Application modules importing concrete implementation classes that should be behind a factory interface
- Object creation logic in application code that changes when requirements change about *how* to construct objects

### V4: Active Dependency Resolution Instead of Injection (from "Dependency Injection")
**Pattern:** Objects actively resolve their own dependencies by calling lookup services (e.g., JNDI), service locators, or global registries, instead of being passively injected.
**Why it is harmful:**
- The object still actively participates in resolving the dependency, even if it doesn't know the concrete type
- Inversion of Control is incomplete -- the object should be completely passive, providing setters or constructor arguments for dependencies to be injected
- Harder to test because the object depends on the lookup infrastructure being available
**Book example:** JNDI lookups are a "partial" implementation of DI: `MyService myService = (MyService)(jndiContext.lookup("NameOfMyService"));` The object doesn't control what is returned but still actively resolves the dependency. True DI means the class provides setter methods or constructor arguments and the DI container injects the required objects.
**Detection:**
- Calls to `lookup()`, `getService()`, `ServiceLocator.get()`, or similar in business logic
- Constructor or method bodies that reach out to global registries or contexts to find dependencies
- Objects that cannot be instantiated without a running service locator or JNDI context

### V5: Business Logic Tightly Coupled to Container/Framework (from "Scaling Up" / EJB2 example)
**Pattern:** Domain objects must subclass framework base classes, implement framework lifecycle interfaces, or embed container-specific code.
**Why it is harmful:**
- Isolated unit testing is difficult because the heavyweight container must be mocked or started
- Reuse outside the framework architecture is effectively impossible due to tight coupling
- Object-oriented programming is undermined -- cannot inherit from other domain objects because the framework base class slot is consumed
- Forces use of "data transfer objects" (DTOs) that are essentially structs with no behavior, leading to redundant types and boilerplate copy code
- Business logic is hard to understand because it is mixed with lifecycle methods (`ejbActivate`, `ejbPassivate`, `ejbLoad`, `ejbStore`, etc.)
**Book example:** The EJB2 `Bank` entity bean (Listings 11-1 and 11-2) required: a local (in process) or remote (separate JVM) interface extending `EJBLocalObject`, a corresponding `LocalHome` interface (essentially a factory used to create objects and finder/query methods), an abstract implementation class extending `EntityBean`, many lifecycle methods (mostly empty), JNDI lookups embedded in business logic (`addAccount` method), and XML deployment descriptors that specify object-relational mapping, transactional behavior, and security constraints. Despite all this coupling, the EJB2 architecture came close to true separation of concerns in one area: the desired transactional, security, and some persistence behaviors were declared in the deployment descriptors *independently* of the source code -- this "anticipated" aspect-oriented programming. Contrast with the EJB3/JPA `Bank` entity (Listing 11-5): a clean POJO with annotations. Entity details are in the annotations, which can optionally be moved to XML deployment descriptors for a truly pure POJO. EJB3 largely follows the Spring model of declaratively supporting cross-cutting concerns using XML configuration files and/or Java 5 annotations.
**Detection:**
- Domain classes extending framework-specific base classes (e.g., `EntityBean`, `HttpServlet`, framework-specific `Controller`)
- Empty lifecycle methods required by the framework but never used by the domain
- JNDI lookups or container API calls inside domain methods
- Domain classes that cannot be instantiated without a container
- DTOs created solely to copy data between framework-coupled objects

### V6: Cross-Cutting Concerns Manually Scattered (from "Cross-Cutting Concerns")
**Pattern:** Infrastructure concerns like persistence, transactions, security, or caching are implemented by spreading the same code pattern across many objects rather than being modularized.
**Why it is harmful:**
- Concerns like persistence cut across natural object boundaries -- you want to persist all objects the same way, but the code for doing so must be duplicated in every object
- The persistence framework and the domain logic, in isolation, might each be modular, but the fine-grained *intersection* of these domains is the problem
- Changing the persistence strategy (e.g., switching from flat files to DBMS) requires touching every object
- The same boilerplate for transaction management or security checks is repeated in dozens of classes
**Detection:**
- Transaction begin/commit/rollback code duplicated across multiple service methods
- Security/authorization checks copy-pasted into every API endpoint
- Persistence/serialization code (save, load, query) mixed directly into domain objects in a non-declarative way
- Logging/audit code duplicated identically in every method of a service layer

### V7: Proxy Complexity Obscuring Clean Code (from "Java Proxies")
**Pattern:** JDK dynamic proxies or hand-written proxy/decorator code is used for cross-cutting concerns, resulting in a lot of complicated code even for simple cases.
**Why it is harmful:**
- JDK dynamic proxies only work with interfaces, not classes (byte-code manipulation libraries needed for classes)
- The `InvocationHandler` pattern requires reflection-based dispatch with string method name matching, which is error-prone and hard to read
- The volume and complexity of proxy code makes it hard to create clean code
- Proxies don't provide a mechanism for specifying system-wide execution "points" of interest -- needed for a true AOP solution
**Book example:** The `BankProxyHandler` (Listing 11-3) required an interface (`Bank`), a POJO implementation (`BankImpl`), an `InvocationHandler` implementation with reflection-based method dispatch, and explicit proxy creation via `Proxy.newProxyInstance(...)` -- all for just two methods (`getAccounts`/`setAccounts`).
**Detection:**
- Hand-written `InvocationHandler` implementations with string-based method name matching
- `Proxy.newProxyInstance(...)` calls scattered through the codebase
- Proxy code that is disproportionately complex relative to the concern it addresses
- Method interception logic using reflection where a declarative approach (annotations, AOP framework) would be simpler

### V8: Big Design Up Front (BDUF) (from "Test Drive the System Architecture")
**Pattern:** The entire system architecture is designed in detail before any implementation begins, with the assumption that it cannot change later.
**Why it is harmful:**
- BDUF inhibits adapting to change because of psychological resistance to discarding prior effort and because early architecture choices influence all subsequent thinking
- Software is not a physical system -- it *can* grow incrementally from simple to complex if concerns are properly separated
- Early architectural decisions are made with the least amount of knowledge (least customer feedback, least experience with implementation)
- The architecture becomes a constraint that inhibits the efficient delivery of value
**Book principle:** "It is a myth that we can get systems 'right the first time.' Instead, we should implement only today's *stories*, then refactor and expand the system to implement new stories tomorrow. This is the essence of iterative and incremental agility. Test-driven development, refactoring, and the clean code they produce make this work at the code level."
**Detection:**
- Massive architecture documents created before any code is written
- Framework or infrastructure choices that cannot be changed without rewriting domain logic
- Architectural decisions being made months before the relevant features are implemented
- Architecture that constrains the team more than it enables them

### V9: Premature or Unnecessary Standard Adoption (from "Use Standards Wisely")
**Pattern:** A complex standard or framework is adopted before there is demonstrable need, simply because it is popular or "the standard."
**Why it is harmful:**
- Teams lose focus on implementing value for customers and instead spend effort implementing the standard itself
- Standards can be overkill when lighter-weight designs would suffice
- The process of creating standards can take too long for industry to wait, and some standards lose touch with the real needs of adopters
- Over-engineered standards (like early EJB) compromise separation of concerns and impose unnecessary barriers to organic growth
**Book example:** "Many teams used the EJB2 architecture because it was a standard, even when lighter-weight and more straightforward designs would have been sufficient."
**Detection:**
- Heavyweight frameworks adopted for simple applications
- Standards or frameworks used that the team cannot articulate concrete value for
- Significant effort spent on framework compliance rather than feature delivery
- Architecture patterns adopted "because everyone uses it" rather than because the project needs it

### V10: Domain Logic Expressed at Wrong Abstraction Level (from "Systems Need Domain-Specific Languages")
**Pattern:** Domain logic is expressed in low-level code idioms and implementation details rather than in a language or API that a domain expert could read and verify.
**Why it is harmful:**
- A "communication gap" exists between the domain concept and the code, increasing the risk of incorrectly translating the domain into the implementation
- Code is harder for domain experts (and other developers) to review for correctness
- The abstraction level is too low -- implementation patterns and idioms obscure the domain intent
**Book principle:** "A good DSL minimizes the 'communication gap' between a domain concept and the code that implements it, just as agile practices optimize the communications within a team and with the project's stakeholders."
**Detection:**
- Business rules expressed as complex conditional chains rather than readable, declarative rules
- Domain experts unable to read or verify the code that implements their rules
- No fluent APIs, builder patterns, or DSL-like abstractions for complex domain logic
- The same domain concept expressed differently in different parts of the codebase

## How to Fix

### Fix 1: Separate Construction from Use via Main
**Before (violation):**
```java
public Service getService() {
    if (service == null)
        service = new MyServiceImpl(...); // Good enough default for most cases?
    return service;
}
```
**After (clean separation):**
```java
// In main (or startup module):
Service service = new MyServiceImpl(dep1, dep2);
Application app = new Application(service);
app.run();

// In application code:
public class Application {
    private final Service service;
    public Application(Service service) {
        this.service = service; // Just uses it, never constructs it
    }
}
```
**Principle:** "If we are *diligent* about building well-formed and robust systems, we should never let little, *convenient* idioms lead to modularity breakdown." Move ALL aspects of construction to `main` or modules called by `main`. Design the rest of the system assuming all objects have been constructed and wired. All dependency arrows point from `main` toward the application, never the reverse.

### Fix 2: Use Abstract Factory When Application Controls Creation Timing
**Before (violation):**
```java
// Application directly creates concrete objects
public void processOrder(Order order) {
    LineItem item = new LineItemImpl(order.getSpec()); // Coupled to concrete type
    order.addItem(item);
}
```
**After (factory pattern):**
```java
// Interface on application side:
public interface LineItemFactory {
    LineItem makeLineItem(ItemSpec spec);
}

// Implementation on main side:
public class LineItemFactoryImpl implements LineItemFactory {
    public LineItem makeLineItem(ItemSpec spec) {
        return new LineItemImpl(spec);
    }
}

// In main:
LineItemFactory factory = new LineItemFactoryImpl();
OrderProcessing app = new OrderProcessing(factory);

// Application code -- controls WHEN, decoupled from HOW:
public void processOrder(Order order) {
    LineItem item = factory.makeLineItem(order.getSpec());
    order.addItem(item);
}
```
**Principle:** The application controls when `LineItem` instances are created and can pass application-specific constructor arguments. But the details of construction are on the `main` side of the line. All dependencies point from `main` toward the `OrderProcessing` application.

### Fix 3: Use True Dependency Injection (Not Service Locators)
**Before (partial DI -- active resolution):**
```java
MyService myService = (MyService)(jndiContext.lookup("NameOfMyService"));
```
**After (true DI -- completely passive):**
```java
public class MyComponent {
    private final MyService myService;

    // DI container injects via constructor
    public MyComponent(MyService myService) {
        this.myService = myService;
    }

    // Or via setter:
    public void setMyService(MyService myService) {
        this.myService = myService;
    }
}

// Configuration (e.g., Spring XML or annotations) specifies which concrete object to inject
```
**Principle:** The class takes no direct steps to resolve its dependencies; it is completely passive. It provides setter methods or constructor arguments that are used to *inject* the dependencies. During construction, the DI container instantiates required objects (usually on demand) and uses the constructor arguments or setter methods to wire dependencies together. Which objects are actually used is specified through a configuration file or programmatically in a special-purpose construction module.

### Fix 4: Write POJOs, Separate Infrastructure with Aspects/Decorators
**Before (tightly coupled to container -- EJB2 style):**
```java
public abstract class Bank implements javax.ejb.EntityBean {
    // Business logic...
    public abstract String getStreetAddr1();
    public abstract void setStreetAddr1(String street1);
    // ... many abstract getters/setters ...

    public void addAccount(AccountDTO accountDTO) {
        InitialContext context = new InitialContext();  // JNDI lookup in business logic!
        AccountHomeLocal accountHome = context.lookup("AccountHomeLocal");
        AccountLocal account = accountHome.create(accountDTO);
        accounts.add(account);
    }

    // EJB container lifecycle methods:
    public void setEntityContext(EntityContext ctx) {}
    public void unsetEntityContext() {}
    public void ejbActivate() {}
    public void ejbPassivate() {}
    public void ejbLoad() {}
    public void ejbStore() {}
    public void ejbRemove() {}
}
```
**After (POJO with declarative concerns -- EJB3/JPA style):**
```java
@Entity
@Table(name = "BANKS")
public class Bank implements java.io.Serializable {
    @Id @GeneratedValue(strategy = GenerationType.AUTO)
    private int id;

    @Embedded
    private Address address; // Clean embedded value object

    @OneToMany(cascade = CascadeType.ALL, fetch = FetchType.EAGER, mappedBy = "bank")
    private Collection<Account> accounts = new ArrayList<>();

    public void addAccount(Account account) {
        account.setBank(this);
        accounts.add(account);  // Pure business logic, no JNDI, no container coupling
    }

    // Simple getters/setters, no framework lifecycle methods
}
```
**Principle:** The code is much cleaner. Entity details are in annotations, which can optionally be moved to XML descriptors for a truly pure POJO. The code is clean, clear, easy to test, maintain, and evolve. No framework base classes, no lifecycle methods, no JNDI lookups.

### Fix 5: Use AOP Frameworks Instead of Hand-Written Proxies
**Before (hand-written proxy with InvocationHandler):**
```java
public class BankProxyHandler implements InvocationHandler {
    private Bank bank;
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        String methodName = method.getName();
        if (methodName.equals("getAccounts")) {
            bank.setAccounts(getAccountsFromDatabase());
            return bank.getAccounts();
        } else if (methodName.equals("setAccounts")) {
            // ... more string-based dispatch
        }
    }
}
// Creation:
Bank bank = (Bank) Proxy.newProxyInstance(Bank.class.getClassLoader(),
    new Class[] { Bank.class }, new BankProxyHandler(new BankImpl()));
```
**After (declarative AOP via Spring/framework):**
```xml
<!-- Spring configuration: "Russian doll" of decorators -->
<bean id="appDataSource" class="org.apache.commons.dbcp.BasicDataSource"
    destroy-method="close"
    p:driverClassName="com.mysql.jdbc.Driver"
    p:url="jdbc:mysql://localhost:3306/mydb"
    p:username="me"/>

<bean id="bankDataAccessObject"
    class="com.example.banking.persistence.BankDataAccessObject"
    p:dataSource-ref="appDataSource"/>

<bean id="bank"
    class="com.example.banking.model.Bank"
    p:dataAccessObject-ref="bankDataAccessObject"/>
```
**Principle:** In Spring, you write your business logic as *Plain-Old Java Objects* (POJOs) that are purely focused on their domain, with no dependencies on enterprise frameworks (or any other domain). Hence, they are conceptually simpler and easier to test drive. You incorporate the required application infrastructure -- cross-cutting concerns like persistence, transactions, security, caching, failover -- using declarative configuration files or APIs, often specifying Spring or JBoss library aspects where the framework handles the mechanics of using Java proxies or byte-code libraries transparently to the user. These declarations drive the DI container, which instantiates the major objects and wires them together on demand.

Each "bean" is like one part of a nested "Russian doll" -- a domain object for `Bank` proxied (wrapped) by a data accessor object (DAO), which is itself proxied by a JDBC driver data source (see Figure 11-3 in the book). The client believes it is invoking `getAccounts()` on a `Bank` object, but it is actually talking to the outermost of a set of nested DECORATOR objects that extend the basic behavior for transactions, caching, and so forth. In the application, only a few lines are needed to ask the DI container for the top-level objects, as specified in the XML file. The application is almost *completely decoupled from Spring*, eliminating all the tight-coupling problems of systems like EJB2. The example can be further simplified using mechanisms that exploit *convention over configuration* and Java 5 annotations to reduce the amount of explicit "wiring" logic required.

### Fix 6: Test Drive the Architecture -- Start Simple, Evolve
**Approach:**
1. Start with a "naively simple" but nicely decoupled architecture
2. Deliver working user stories quickly
3. Add more infrastructure as you scale up (caching, security, virtualization, etc.)
4. Keep designs appropriately *simple* at each level of abstraction and scope
5. Maintain the ability to change course in response to evolving circumstances

**Principle:** It is not necessary to do Big Design Up Front (BDUF). In fact, BDUF is harmful because it inhibits adapting to change. If the structure of the software separates its concerns effectively, it is economically feasible to make radical change. You can start a software project with a "naively simple" but nicely decoupled architecture, delivering working user stories quickly, then adding more infrastructure as you scale up.

### Fix 7: Defer Decisions to the Last Responsible Moment
**Before (premature decision):**
- Choosing a database engine in month 1 of a project that won't need persistence until month 6
- Selecting a caching framework before understanding access patterns
- Picking a messaging system before message volume requirements are known

**After (deferred, informed decision):**
- Build domain logic as POJOs with repository interfaces
- Implement the simplest persistence that works (maybe in-memory) initially
- When the feature requiring real persistence arrives, choose the database with full knowledge of the data model, access patterns, and scale requirements
- The modular, POJO-based design makes the switch a localized change

**Principle:** "It is best to postpone decisions until the last possible moment. This isn't lazy or irresponsible; it lets us make informed choices with the best possible information. A premature decision is a decision made with suboptimal knowledge."

### Fix 8: Introduce Domain-Specific Languages for Complex Domain Logic
**Before (low-level implementation):**
```java
if (account.getBalance() > 0 && account.getType().equals("SAVINGS")
    && account.getAge() > 365 && !account.isFrozen()) {
    double interest = account.getBalance() * getRate(account.getTier());
    account.credit(interest);
}
```
**After (DSL-like fluent API):**
```java
accountPolicy
    .forSavingsAccounts()
    .olderThan(days(365))
    .withPositiveBalance()
    .notFrozen()
    .applyInterest(basedOnTier());
```
**Principle:** A good DSL minimizes the "communication gap" between a domain concept and the code that implements it. DSLs raise the abstraction level above code idioms and design patterns. They allow the developer to reveal the intent of the code at the appropriate level of abstraction. Domain-Specific Languages allow all levels of abstraction and all domains in the application to be expressed as POJOs, from high-level policy to low-level details.

## Self-Improvement Protocol

After each system-level review, update your knowledge:

1. **Map the construction/use boundary:**
   - Identify where objects are constructed in the system. Are construction sites concentrated in `main`/startup modules, or scattered throughout?
   - Count instances of `new ConcreteClass(...)` in application (non-startup) code. (Target: minimal -- only value objects and simple data structures)
   - Are there lazy initialization patterns scattered across the codebase? (Target: zero outside of DI container configuration)
   - Do all dependency arrows from construction modules point toward the application? (Target: strictly unidirectional)

2. **Assess dependency injection health:**
   - Is there a DI container or a clear `main`-based wiring strategy? (Target: yes, one consistent approach)
   - Are objects passively injected, or do they actively look up their dependencies? (Target: all passive injection)
   - Can every business-logic class be instantiated in a test without a running container? (Target: yes for all)
   - How many lines of framework-specific code exist in business-logic modules? (Target: near zero -- only annotations or minimal configuration)

3. **Evaluate cross-cutting concern modularity:**
   - Are persistence, transactions, security, and logging handled declaratively? (Target: all declarative)
   - How many files would need to change to switch the persistence strategy? (Target: configuration only, not business logic)
   - Is the same infrastructure boilerplate (transaction management, security checks, etc.) duplicated across multiple classes? (Target: zero duplication)
   - Are cross-cutting concerns modularized as aspects, decorators, or interceptors? (Target: yes)

4. **Measure architecture agility:**
   - Could you swap out the web framework without rewriting domain logic? (Target: yes)
   - Could you switch databases without modifying domain objects? (Target: yes)
   - Could you test the entire domain layer without starting any infrastructure? (Target: yes)
   - Is the architecture evolving incrementally with the project, or was it locked in up front? (Target: incremental evolution)
   - Are there decisions made prematurely that now constrain the team? (Target: none)

5. **Check standards and DSL usage:**
   - Are any frameworks or standards adopted without demonstrable value? (Target: every standard justified by concrete benefit)
   - Is domain logic expressed at the right abstraction level? (Target: readable by domain experts)
   - Are there domain areas where a DSL or fluent API would reduce the communication gap? (Target: identified and addressed for high-complexity domains)

6. **Apply the core heuristic from the chapter (Conclusion):**
   - "Whether you are designing systems or individual modules, never forget to *use the simplest thing that can possibly work.*"
   - At all levels of abstraction, write POJOs and use aspect-like mechanisms to incorporate cross-cutting concerns noninvasively.
   - "Systems must be clean too. An invasive architecture overwhelms the domain logic and impacts agility. When the domain logic is obscured, quality suffers because bugs find it easier to hide and stories become harder to implement. If agility is compromised, productivity suffers and the benefits of TDD are lost."
   - "At all levels of abstraction, the intent should be clear. This will only happen if you write POJOs and you use aspect-like mechanisms to incorporate other implementation concerns noninvasively."
