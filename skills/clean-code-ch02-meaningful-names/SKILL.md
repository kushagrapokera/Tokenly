---
name: clean-code-ch02-meaningful-names
description: "Code quality checker based on Clean Code Ch2: Meaningful Names -- checks naming conventions, intention-revealing names, disinformation avoidance, searchability, encoding avoidance, and context. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 2: Meaningful Names -- Code Quality Checker

*By Tim Ottinger*

> Names are everywhere in software. We name our variables, our functions, our arguments, classes, and packages. We name our source files and the directories that contain them. We name our jar files and war files and ear files. We name and name and name. Because we do so much of it, we'd better do it well.

## When to Use

Invoke this skill when:
- Reviewing any code (PR reviews, refactoring, new feature development)
- Naming new variables, functions, classes, methods, arguments, packages, or files
- Encountering code that is hard to understand and naming may be the root cause
- Running a naming audit on an existing codebase
- A developer asks "what should I name this?"
- Before committing code -- as a final naming quality gate

## Checklist

Run through EVERY rule below when reviewing names. A name is clean only when it passes ALL checks.

### 1. Intention-Revealing Names
- [ ] Does the name tell WHY it exists, WHAT it does, and HOW it is used?
- [ ] Can you understand the code without a comment explaining the name?
- [ ] If a name requires a comment, the name does not reveal its intent -- rename it.

Key insight: Choosing good names takes time but saves more than it takes. Take care with your names and change them when you find better ones. Everyone who reads your code (including you) will be happier if you do.

The problem is not the *simplicity* of code but the **implicity** of the code (to coin a phrase): the degree to which the context is not explicit in the code itself.

**BAD:**
```java
int d; // elapsed time in days
```
**GOOD:**
```java
int elapsedTimeInDays;
int daysSinceCreation;
int daysSinceModification;
int fileAgeInDays;
```

**BAD -- implicit context, unreadable:**
```java
public List<int[]> getThem() {
    List<int[]> list1 = new ArrayList<int[]>();
    for (int[] x : theList)
        if (x[0] == 4)
            list1.add(x);
    return list1;
}
```
Questions you cannot answer from this code: What is `theList`? What does index `0` mean? What does `4` mean? What is `list1` used for?

**BETTER -- named constants and meaningful variable names:**
```java
public List<int[]> getFlaggedCells() {
    List<int[]> flaggedCells = new ArrayList<int[]>();
    for (int[] cell : gameBoard)
        if (cell[STATUS_VALUE] == FLAGGED)
            flaggedCells.add(cell);
    return flaggedCells;
}
```

**BEST -- domain object with intention-revealing method:**
```java
public List<Cell> getFlaggedCells() {
    List<Cell> flaggedCells = new ArrayList<Cell>();
    for (Cell cell : gameBoard)
        if (cell.isFlagged())
            flaggedCells.add(cell);
    return flaggedCells;
}
```

### 2. Avoid Disinformation
- [ ] Does the name avoid words with entrenched meanings that differ from intended meaning?
- [ ] Does the name avoid platform-specific terms used as variable names (e.g., `hp`, `aix`, `sco`)? Even if you are coding a hypotenuse and `hp` looks like a good abbreviation, it could be disinformative.
- [ ] If it is NOT a `List`, does the name avoid the word "List"? (e.g., `accountList` when it is really a `Set` or `Map`)
- [ ] Do similar names have obviously visible differences? (Not `XYZControllerForEfficientHandlingOfStrings` vs `XYZControllerForEfficientStorageOfStrings`)
- [ ] Are spellings consistent? (Inconsistent spelling is DISinformation.) With modern IDEs we enjoy automatic code completion. It is very helpful if names for very similar things sort together alphabetically and if the differences are very obvious, because the developer is likely to pick an object by name without seeing your copious comments or even the list of methods supplied by that class.
- [ ] Does the name avoid using lowercase-L (`l`) or uppercase-O (`O`) as variable names (look like `1` and `0`)?

**BAD -- "List" when not a List:**
```java
Account[] accountList; // It's an array, not a List!
```
**GOOD:**
```java
Account[] accountGroup;
// or
Account[] bunchOfAccounts;
// or
Account[] accounts;
```
Note: Even if the container *is* a `List`, it is probably better not to encode the container type into the name.

**BAD -- nearly identical names:**
```java
XYZControllerForEfficientHandlingOfStrings
XYZControllerForEfficientStorageOfStrings
```

**BAD -- l and O as names (look like 1 and 0):**
```java
int a = l;
if ( O == l )
    a = O1;
else
    l = 01;
```

### 3. Make Meaningful Distinctions
- [ ] Are names distinguished in a way that the reader can tell what the differences mean?
- [ ] Does the name avoid number-series naming (a1, a2, ... aN)? Number-series naming is the opposite of intentional naming.
- [ ] Does the name avoid noise words: `Info`, `Data`, `a`, `an`, `the` (when not meaningful), `variable`, `table`, `String`, `Object`?
- [ ] Can the reader tell the difference between similarly named items? (`getActiveAccount()` vs `getActiveAccounts()` vs `getActiveAccountInfo()` -- which to call?)
- [ ] If code is written solely to satisfy a compiler/interpreter, the naming is wrong. Consider the truly hideous practice of naming a variable `klass` just because `class` is already used for something else.

Note: There is nothing wrong with using prefix conventions like `a` and `the` so long as they make a meaningful distinction. For example you might use `a` for all local variables and `the` for all function arguments. The problem comes in when you decide to call a variable `theZork` because you already have another variable named `zork`.

**BAD -- number-series naming (noninformative):**
```java
public static void copyChars(char a1[], char a2[]) {
    for (int i = 0; i < a1.length; i++) {
        a2[i] = a1[i];
    }
}
```
**GOOD:**
```java
public static void copyChars(char source[], char destination[]) {
    for (int i = 0; i < source.length; i++) {
        destination[i] = source[i];
    }
}
```

**BAD -- noise words creating indistinguishable names:**
```
Product  vs  ProductInfo  vs  ProductData    // What's the difference?
Customer vs  CustomerObject                  // Which has payment history?
NameString                                    // Would a Name ever be a float?
moneyAmount vs money                         // Indistinguishable
customerInfo vs customer                     // Indistinguishable
accountData vs account                       // Indistinguishable
theMessage vs message                        // Indistinguishable
```

**BAD -- confusing triplet of functions:**
```java
getActiveAccount();
getActiveAccounts();
getActiveAccountInfo();
// Which one should I call?
```

### 4. Use Pronounceable Names
- [ ] Can you say the name out loud in conversation without sounding ridiculous?
- [ ] Does the name use real English words, not abbreviation soup?

This matters because **programming is a social activity**. If you cannot pronounce it, you cannot discuss it without sounding like an idiot: "Well, over here on the bee cee arr three cee enn tee we have a pee ess zee kyew int, see?"

**BAD -- unpronounceable:**
```java
class DtaRcrd102 {
    private Date genymdhms;      // generation date, year, month, day, hour, minute, second
    private Date modymdhms;      // modification date...
    private final String pszqint = "102";
};
```
**GOOD -- pronounceable:**
```java
class Customer {
    private Date generationTimestamp;
    private Date modificationTimestamp;
    private final String recordId = "102";
};
```
Now you can have an intelligent conversation: "Hey, Mikey, take a look at this record! The generation timestamp is set to tomorrow's date! How can that be?"

### 5. Use Searchable Names
- [ ] Can the name be found with a text search (grep/find)?
- [ ] Are single-letter names used ONLY as local variables in short methods?
- [ ] Are numeric constants replaced with named constants?
- [ ] Does the name length correspond to the size of its scope? (Longer scope = longer name)

**BAD -- unsearchable:**
```java
for (int j=0; j<34; j++) {
    s += (t[j]*4)/5;
}
```
**GOOD -- searchable:**
```java
int realDaysPerIdealDay = 4;
const int WORK_DAYS_PER_WEEK = 5;
int sum = 0;
for (int j=0; j < NUMBER_OF_TASKS; j++) {
    int realTaskDays = taskEstimate[j] * realDaysPerIdealDay;
    int realTaskWeeks = (realDays / WORK_DAYS_PER_WEEK);
    sum += realTaskWeeks;
}
```
Note that `sum`, above, is not a particularly useful name but at least it is searchable. The intentionally named code makes for a longer function, but consider how much easier it will be to find `WORK_DAYS_PER_WEEK` than to find all the places where `5` was used and filter the list down to just the instances with the intended meaning.

One might easily grep for `MAX_CLASSES_PER_STUDENT`, but the number `7` could be more troublesome. Searches may turn up the digit as part of file names, other constant definitions, and in various expressions where the value is used with different intent. It is even worse when a constant is a long number and someone might have transposed digits, thereby creating a bug while simultaneously evading the programmer's search.

The name `e` is a particularly poor choice for any variable a programmer might need to search for -- it is the most common letter in the English language and likely to show up in every passage of text in every program. In this regard, longer names trump shorter names, and any searchable name trumps a constant in code.

Cross-reference: See also smell **[N5]** in Chapter 17 -- "If a variable or constant might be seen or used in multiple places in a body of code, it is imperative to give it a search-friendly name."

### 6. Avoid Encodings

Encoding type or scope information into names adds an extra burden of deciphering. It hardly seems reasonable to require each new employee to learn yet another encoding "language" in addition to learning the (usually considerable) body of code. Encoded names are seldom pronounceable and are easy to mis-type.

#### 6a. Hungarian Notation
- [ ] Does the name avoid type-encoding prefixes (e.g., `strName`, `iCount`, `bFlag`, `szBuffer`)?
- [ ] Modern languages have rich type systems and IDEs that make Hungarian Notation an impediment, not a help.
- [ ] Type encodings make names harder to read, harder to change type, and can become lies when the type changes but the name does not.

Historical context: In days of old, when we worked in name-length-challenged languages, we violated this rule out of necessity. Fortran forced encodings by making the first letter a code for the type. Early versions of BASIC allowed only a letter plus one digit. Hungarian Notation (HN) took this to a whole new level. HN was considered important back in the Windows C API, when everything was an integer handle or a long pointer or a `void` pointer, or one of several implementations of "string" (with different uses and attributes). The compiler did not check types in those days, so the programmers needed a crutch to help them remember the types. In modern languages we have much richer type systems, and the compilers remember and enforce the types. There is a trend toward smaller classes and shorter functions so that people can usually see the point of declaration of each variable they are using.

**BAD:**
```java
PhoneNumber phoneString;  // name not changed when type changed!
```

#### 6b. Member Prefixes
- [ ] Does the name avoid `m_` or similar member-variable prefixes?
- [ ] Classes and functions should be small enough that you do not need them.
- [ ] Modern IDEs highlight/colorize members to make them distinct.

**BAD:**
```java
public class Part {
    private String m_dsc; // The textual description
    void setName(String name) {
        m_dsc = name;
    }
}
```
**GOOD:**
```java
public class Part {
    String description;
    void setDescription(String description) {
        this.description = description;
    }
}
```

Besides, people quickly learn to ignore the prefix (or suffix) to see the meaningful part of the name. The more we read the code, the less we see the prefixes. Eventually the prefixes become unseen clutter and a marker of older code.

#### 6c. Interfaces and Implementations
- [ ] If you must encode, encode the IMPLEMENTATION, not the INTERFACE.
- [ ] Prefer `ShapeFactory` (interface) with `ShapeFactoryImp` or `CShapeFactory` (implementation) over `IShapeFactory` (interface) with `ShapeFactory` (implementation).
- [ ] Users should not know they are being handed an interface. The `I` prefix is a distraction at best and too much information at worst.

**BAD:**
```java
IShapeFactory  // I prefix on interface
```
**GOOD:**
```java
ShapeFactory          // clean interface name
ShapeFactoryImp       // encoded implementation
CShapeFactory         // alternative encoded implementation
```

### 7. Avoid Mental Mapping
- [ ] Does the reader NOT have to mentally translate the name to a concept they already know?
- [ ] Are single-letter variable names limited to loop counters (`i`, `j`, `k`) in small scopes?
- [ ] Never use `l` (lowercase L) as a loop counter -- always use `i`, `j`, or `k`.
- [ ] Does the name use domain terms or solution terms rather than private abbreviations the reader must decode?

Key principle: **Clarity is king.** The professional understands that their job is to write code that others can understand. A smart programmer shows off by writing clear code, not by demonstrating mental juggling abilities.

**BAD:** Using `r` to mean "the lower-cased version of the url with the host and scheme removed." The reader must mentally map `r` every time they encounter it.

**BAD:** There can be no worse reason for using the name `c` than because `a` and `b` were already taken.

### 8. Class Names
- [ ] Is the class name a noun or noun phrase? (e.g., `Customer`, `WikiPage`, `Account`, `AddressParser`)
- [ ] Does the class name AVOID verbs?
- [ ] Does the class name AVOID vague words like `Manager`, `Processor`, `Data`, `Info`?

**GOOD class names:** `Customer`, `WikiPage`, `Account`, `AddressParser`
**BAD class names:** `Manager`, `Processor`, `Data`, `Info` (as standalone names -- too vague)

### 9. Method Names
- [ ] Is the method name a verb or verb phrase? (e.g., `postPayment`, `deletePage`, `save`)
- [ ] Do accessors start with `get`? (e.g., `getName()`)
- [ ] Do mutators start with `set`? (e.g., `setName("mike")`)
- [ ] Do predicates start with `is`? (e.g., `isPosted()`)

Accessors, mutators, and predicates should be named for their value and prefixed with `get`, `set`, and `is` according to the javabean standard.
- [ ] When constructors are overloaded, are static factory methods with descriptive names used instead?

**GOOD -- method naming conventions:**
```java
string name = employee.getName();
customer.setName("mike");
if (paycheck.isPosted())...
```

**GOOD -- static factory method over overloaded constructor:**
```java
Complex fulcrumPoint = Complex.FromRealNumber(23.0);
```
**BAD -- overloaded constructor (less descriptive):**
```java
Complex fulcrumPoint = new Complex(23.0);
```
Consider enforcing use of static factory methods by making corresponding constructors private.

### 10. Don't Be Cute
- [ ] Does the name avoid jokes, slang, colloquialisms, or culture-dependent references?
- [ ] Does the name say what it means, clearly and directly?

**BAD:**
```
HolyHandGrenade   ->  GOOD: DeleteItems
whack()            ->  GOOD: kill()
eatMyShorts()      ->  GOOD: abort()
```
Rule: **Say what you mean. Mean what you say.** Choose clarity over entertainment value.

### 11. Pick One Word per Concept
- [ ] Is one consistent word used for each abstract concept throughout the codebase?
- [ ] Are `fetch`, `retrieve`, and `get` NOT used interchangeably across classes for the same concept?
- [ ] Are `controller`, `manager`, and `driver` NOT used interchangeably for the same concept?

**BAD -- inconsistent lexicon:**
```
DeviceManager     vs  ProtocolController   // Why not both "controllers" or both "managers"?
fetch()  /  retrieve()  /  get()           // Pick ONE for the same concept
```

Modern editing environments like Eclipse and IntelliJ provide context-sensitive clues, such as the list of methods you can call on a given object. But note that the list does not usually give you the comments you wrote around your function names and parameter lists. You are lucky if it gives the parameter *names* from function declarations. The function names have to stand alone, and they have to be consistent in order for you to pick the correct method without any additional exploration.

A consistent lexicon is a great boon to the programmers who must use your code.

### 12. Don't Pun
- [ ] Is the SAME word NOT used for two DIFFERENT purposes?
- [ ] If many classes have an `add` method that creates a new value by adding/concatenating two values, does a class that puts a single parameter into a collection use `insert` or `append` instead of `add`?

**BAD -- punning on "add":**
```java
// Existing classes: add() means concatenate/combine two values
// New class: add() means put a single item into a collection
list.add(element);  // This is a PUN -- different semantics, same word
```
**GOOD:**
```java
list.insert(element);  // or
list.append(element);  // clearly different from the "add = combine" convention
```

Principle: Our goal, as authors, is to make our code as easy as possible to understand. We want our code to be a quick skim, not an intense study. We want to use the popular paperback model whereby the author is responsible for making himself clear and not the academic model where it is the scholar's job to dig the meaning out of the paper.

### 13. Use Solution Domain Names
- [ ] For technical concepts, does the name use CS terms, algorithm names, pattern names, or math terms?
- [ ] Programmers will read your code -- use the vocabulary they already know.

**GOOD solution domain names:**
```
AccountVisitor     // VISITOR pattern -- any programmer recognizes this
JobQueue           // Queue data structure -- universally understood
```

Do NOT force readers to run to the domain expert for every name when a well-known CS term exists.

### 14. Use Problem Domain Names
- [ ] When there is no "programmer-eese" for a concept, does the name come from the problem domain?
- [ ] Can a domain expert help clarify the meaning if needed?

Separating solution and problem domain concepts is part of the job of a good programmer and designer. The code that has more to do with problem domain concepts should have names drawn from the problem domain.

### 15. Add Meaningful Context
- [ ] Are variables placed in context via well-named classes, functions, or namespaces?
- [ ] If a variable cannot be placed in a class/function for context, is a prefix used as a last resort?
- [ ] Can the reader understand what a variable represents without reading the entire function?

**Full Address example progression:** Imagine you have variables named `firstName`, `lastName`, `street`, `houseNumber`, `city`, `state`, and `zipcode`. Taken together it is pretty clear that they form an address. But what if you just saw the `state` variable being used alone in a method? Would you automatically infer that it was part of an address?

**BAD -- variables with unclear context used alone:**
```
state    // State of what? An address? A process? A UI element?
```
**BETTER -- prefix for context:**
```
addrFirstName, addrLastName, addrState
```
At least readers will understand that these variables are part of a larger structure.

**BEST -- enclosing class provides context:**
```java
class Address {
    String firstName;
    String lastName;
    String street;
    String houseNumber;
    String city;
    String state;   // Now clearly an address state
    String zipcode;
}
```
Then, even the compiler knows that the variables belong to a bigger concept.

**BAD -- long function with context only from algorithm (Listing 2-1):**
```java
private void printGuessStatistics(char candidate, int count) {
    String number;
    String verb;
    String pluralModifier;
    if (count == 0) {
        number = "no";
        verb = "are";
        pluralModifier = "s";
    } else if (count == 1) {
        number = "1";
        verb = "is";
        pluralModifier = "";
    } else {
        number = Integer.toString(count);
        verb = "are";
        pluralModifier = "s";
    }
    String guessMessage = String.format(
        "There %s %s %s%s", verb, number, candidate, pluralModifier
    );
    print(guessMessage);
}
```

**GOOD -- class provides context, function is decomposed (Listing 2-2):**
```java
public class GuessStatisticsMessage {
    private String number;
    private String verb;
    private String pluralModifier;

    public String make(char candidate, int count) {
        createPluralDependentMessageParts(count);
        return String.format(
            "There %s %s %s%s",
            verb, number, candidate, pluralModifier);
    }

    private void createPluralDependentMessageParts(int count) {
        if (count == 0) {
            thereAreNoLetters();
        } else if (count == 1) {
            thereIsOneLetter();
        } else {
            thereAreManyLetters(count);
        }
    }

    private void thereAreManyLetters(int count) {
        number = Integer.toString(count);
        verb = "are";
        pluralModifier = "s";
    }

    private void thereIsOneLetter() {
        number = "1";
        verb = "is";
        pluralModifier = "";
    }

    private void thereAreNoLetters() {
        number = "no";
        verb = "are";
        pluralModifier = "s";
    }
}
```

### 16. Don't Add Gratuitous Context
- [ ] Does the name avoid unnecessary prefixes from the application or module name?
- [ ] Are shorter names preferred when they are clear? (Add no more context than is necessary)
- [ ] For class names: are short, precise names used rather than long prefixed ones?

In an imaginary application called "Gas Station Deluxe," it is a bad idea to prefix every class with `GSD`. Frankly, you are working against your tools. You type `G` and press the completion key and are rewarded with a mile-long list of every class in the system. Is that wise? Why make it hard for the IDE to help you?

Likewise, say you invented a `MailingAddress` class in GSD's accounting module, and you named it `GSDAccountAddress`. Later, you need a mailing address for your customer contact application. Do you use `GSDAccountAddress`? Does it sound like the right name? Ten of 17 characters are redundant or irrelevant.

**BAD -- application prefix on every class ("Gas Station Deluxe" = GSD):**
```
GSDAccountAddress   // 10 of 17 characters are redundant
GSDCustomerAddress
GSDMailingAddress
```
**GOOD:**
```
AccountAddress      // or just Address if unambiguous in context
CustomerAddress
MailingAddress
```

For instance names, `accountAddress` and `customerAddress` are fine. But for class names, `Address` is sufficient. If you need to differentiate, use `PostalAddress`, `MAC`, `URI` -- more precise names, not longer prefixed ones.

Shorter names are generally better than longer ones, so long as they are clear.

### Final Words

The hardest thing about choosing good names is that it requires good descriptive skills and a shared cultural background. This is a teaching issue rather than a technical, business, or management issue. As a result many people in this field do not learn to do it very well.

People are also afraid of renaming things for fear that some other developers will object. We do not share that fear and find that we are actually grateful when names change (for the better). Most of the time we do not really memorize the names of classes and methods. We use the modern tools to deal with details like that so we can focus on whether the code reads like paragraphs and sentences, or at least like tables and data structure (a sentence is not always the best way to display data). You will probably end up surprising someone when you rename, just like you might with any other code improvement. Do not let it stop you in your tracks.

Follow some of these rules and see whether you do not improve the readability of your code. If you are maintaining someone else's code, use refactoring tools to help resolve these problems. It will pay off in the short term and continue to pay in the long run.

---

## Violations to Detect

Use these patterns to scan code for naming violations. Each pattern includes a detection strategy and severity.

### CRITICAL Violations (Fix immediately)

| ID | Rule | Detection Pattern | Example |
|----|------|-------------------|---------|
| N-01 | Single-letter names in non-loop scope | Grep for variable declarations matching `(int\|string\|var\|let\|const\|auto)\s+[a-z]\s*[=;,)]` outside of `for(` statements. Flag any single-letter name (`d`, `e`, `s`, `n`, `x`, etc.) that is not `i`, `j`, `k` inside a short for-loop. | `int d;` `String s;` `var x = getValue();` |
| N-02 | Magic numbers / unsearchable constants | Grep for raw numeric literals in logic: `[^0-9][0-9]{1,}[^0-9.]` in conditionals, calculations, loop bounds. Look for `== \d+`, `< \d+`, `\* \d+`, `/ \d+` where the number is not 0 or 1. | `if (x[0] == 4)`, `j < 34`, `(t[j]*4)/5` |
| N-03 | Intention not revealed (comment required) | Grep for variable declarations followed by `//` comment explaining what it is. Pattern: `(int\|String\|var\|let\|const)\s+\w+\s*;?\s*//` where the comment describes purpose. | `int d; // elapsed time in days` |
| N-04 | Names with `l`/`O` as identifiers | Grep for declarations or assignments where the variable name is exactly `l` or `O`. Pattern: `\b[lO]\s*[=;]` | `int a = l; if (O == l)` |

### HIGH Violations (Fix before merge)

| ID | Rule | Detection Pattern | Example |
|----|------|-------------------|---------|
| N-05 | Number-series naming | Grep for `\b[a-zA-Z][0-9]+\b` used as parameter or variable names, especially `a1`, `a2`, `list1`, `list2`, etc. | `copyChars(char a1[], char a2[])` |
| N-06 | Hungarian Notation | Grep for variable names starting with type prefixes: `\b(str|int|bool|btn|lbl|txt|dbl|flt|arr|lst|obj|sz|psz|b|n|i|f|d|ch|p|lp)\[A-Z\]`. | `strName`, `iCount`, `bIsValid`, `szBuffer` |
| N-07 | Member prefix `m_` | Grep for `\bm_\w+` in field/member declarations. | `private String m_dsc;` |
| N-08 | Interface `I` prefix | Grep for interface declarations with `I` prefix: `interface I[A-Z]\w+`. | `interface IShapeFactory` |
| N-09 | Noise words in names | Grep for names containing: `Info$`, `Data$`, `Object$`, `String$` (in non-type position), `Variable`, `Table` (in variable name). | `ProductInfo`, `CustomerObject`, `NameString`, `accountData` |
| N-10 | Unpronounceable names | Grep for identifiers with no vowels or heavy abbreviation: 3+ consecutive consonants, all-caps abbreviations embedded in camelCase without vowels. | `genymdhms`, `modymdhms`, `pszqint`, `DtaRcrd102` |
| N-11 | Cute/joke names | Grep for names containing slang, jokes, or pop-culture references: `whack`, `nuke`, `kill` (when not OS-signal), `eatMyShorts`, `holyHandGrenade`, `smack`. | `HolyHandGrenade`, `whack()`, `eatMyShorts()` |
| N-12 | Disinformative container suffix | Grep for variables with `List` in the name whose type is NOT a List: `\w+List\b` then cross-reference with actual type declaration. | `Account[] accountList;` `Set<User> userList;` |

### MEDIUM Violations (Fix when touching this code)

| ID | Rule | Detection Pattern | Example |
|----|------|-------------------|---------|
| N-13 | Inconsistent concept words | Grep across codebase for mixed usage of synonyms: `fetch\w*\(` and `retrieve\w*\(` and `get\w*\(` for the same concept. Similarly: `controller` vs `manager` vs `driver` for equivalent roles. | `fetchUser()` in one class, `retrieveUser()` in another |
| N-14 | Punning (same word, different semantics) | Find all methods named `add` (or other common verb) and verify they all do the same kind of operation. If some `add` methods combine values and others insert into collections, flag the insertions. | `add()` meaning both "concatenate" and "insert" |
| N-15 | Gratuitous context / app prefix | Grep for class/variable names that start with a project-specific prefix: `\b(GSD\|APP\|SYS)\w+`. Also flag names where removing the prefix leaves a perfectly clear name. | `GSDAccountAddress` instead of `AccountAddress` |
| N-16 | Class name is verb | Grep for class declarations where name contains a verb stem: `class (Process\|Handle\|Manage\|Execute\|Run\|Do\|Make\|Perform)`. Classes should be nouns. | `class ProcessPayment`, `class HandleRequest` |
| N-17 | Method name is not verb | Grep for public method declarations that are noun-only: no verb prefix like `get`, `set`, `is`, `has`, `create`, `delete`, `update`, `find`, `build`, `make`, `compute`, `check`, `validate`, `convert`, `parse`, `format`, `to`, `from`. | `public String name()` when it should be `getName()` |
| N-18 | Missing context / naked variables | Look for standalone variables like `state`, `number`, `verb`, `name`, `status`, `value` used in methods longer than ~10 lines without a clear enclosing class/namespace providing context. | `String state;` in a 50-line function |
| N-19 | Accessor/mutator/predicate naming | Grep for getter methods not prefixed with `get`, setters not prefixed with `set`, boolean-returning methods not prefixed with `is`/`has`/`can`/`should`. | `boolean posted()` should be `isPosted()` |
| N-20 | Overloaded constructor instead of factory method | Grep for classes with multiple constructors that take different types. Suggest static factory methods with descriptive names. | `new Complex(23.0)` vs `Complex.FromRealNumber(23.0)` |

---

## How to Fix

### General Renaming Strategy
1. **Identify the intent**: Ask "WHY does this exist? WHAT does it represent? HOW is it used?"
2. **Choose domain-appropriate words**: Use solution domain (CS) terms for technical concepts, problem domain terms for business concepts.
3. **Verify pronounceability**: Say it out loud. If you cannot discuss it in a sentence, rename it.
4. **Verify searchability**: Can you grep for it? Is it unique enough to find? Name length should match scope size.
5. **Verify distinctiveness**: Is it clearly different from all other names in scope? Could someone confuse it with a similar name?
6. **Remove encodings**: Strip type prefixes, member prefixes, interface prefixes.
7. **Remove noise**: Strip words like `Info`, `Data`, `Object`, `String`, `Variable`, `the`, `a` when they add no meaning.
8. **Add context through structure**: Prefer enclosing classes/namespaces over prefixes. Use prefixes only as a last resort.

### Fix by Violation Type

| Violation | Fix |
|-----------|-----|
| Single-letter name | Replace with intention-revealing name: `d` -> `elapsedTimeInDays` |
| Magic number | Extract to named constant: `4` -> `FLAGGED`, `5` -> `WORK_DAYS_PER_WEEK` |
| Comment-required name | Fold the comment into the name: `int d; // days` -> `int days;` |
| Number-series args | Use role names: `a1, a2` -> `source, destination` |
| Hungarian prefix | Remove prefix, use plain name: `strName` -> `name`, `iCount` -> `count` |
| `m_` prefix | Remove prefix, use `this.` if needed: `m_dsc` -> `description` |
| `I` prefix on interface | Remove prefix, encode implementation instead: `IShapeFactory` -> `ShapeFactory` (interface) + `ShapeFactoryImp` (implementation) |
| Noise words | Remove noise: `ProductInfo` -> `Product`, `NameString` -> `Name`, `accountData` -> `account` |
| Unpronounceable | Use full English words: `genymdhms` -> `generationTimestamp`, `DtaRcrd102` -> `Customer` |
| Unsearchable | Lengthen to be unique and greppable: `e` -> `event`, `s` -> `sum` |
| Cute/joke name | Replace with clear name: `HolyHandGrenade` -> `DeleteItems`, `whack()` -> `kill()` |
| Inconsistent concept words | Standardize across codebase: pick `get` or `fetch` or `retrieve` -- use one everywhere for the same concept |
| Punning | Use a different word for different semantics: `add` (combine) vs `insert` or `append` (put into collection) |
| Gratuitous context | Remove application/module prefix: `GSDAccountAddress` -> `AccountAddress` or just `Address` |
| Class name is verb | Refactor to noun: `ProcessPayment` -> `PaymentProcessor` or extract to method on a noun class |
| Method name not verb | Add verb prefix: `name()` -> `getName()`, `total()` -> `calculateTotal()` |
| Missing context | Enclose in a class: standalone `state`, `number`, `verb` -> fields of `GuessStatisticsMessage` class |
| Bad predicate name | Add `is`/`has` prefix: `posted()` -> `isPosted()`, `valid()` -> `isValid()` |
| Overloaded constructor | Create static factory method: `new Complex(23.0)` -> `Complex.FromRealNumber(23.0)` |

### Language-Specific Adaptations

**Go:** Methods often omit `Get` prefix by convention (`Name()` not `GetName()`). This is idiomatic Go and NOT a violation. Check for exported vs unexported (capitalization). Go interfaces are often named with `-er` suffix (`Reader`, `Writer`) -- this is GOOD.

**Python:** Uses `snake_case` for variables/functions, `PascalCase` for classes. `_prefix` for private members is idiomatic (NOT a Hungarian Notation violation). `is_`, `has_` for boolean functions is good.

**JavaScript/TypeScript:** `camelCase` for variables/functions, `PascalCase` for classes/components. `I` prefix on interfaces in TypeScript is debatable but increasingly discouraged -- prefer no prefix.

**Rust:** `snake_case` for variables/functions, `PascalCase` for types/traits, `SCREAMING_SNAKE` for constants. Abbreviated names are especially discouraged in Rust culture.

---

## Self-Improvement Protocol

After each review, track:

1. **Pattern frequency**: Which violations appear most? Focus team education on those.
2. **False positives**: Names flagged that are actually fine (e.g., `i` in a for-loop is acceptable). Tune detection thresholds.
3. **Domain vocabulary**: Build a project-specific dictionary of approved problem-domain and solution-domain terms to validate names against.
4. **Consistency map**: Maintain a concept-to-word mapping for the codebase (e.g., "retrieving a record" always uses `fetch`, never `get` or `retrieve`).
5. **Rename impact**: Track whether renaming improved code comprehension in subsequent reviews. Did the same code section generate fewer questions?

### Review Prompt Template

When reviewing code for naming, ask these questions for EVERY identifier:

```
For each name, verify:
1. Can I understand this name WITHOUT reading surrounding code or comments?
2. Can I pronounce it in a sentence to a colleague?
3. Can I grep for it and find only relevant results?
4. Does it use the right domain vocabulary (solution domain for tech, problem domain for business)?
5. Is it consistent with how the same concept is named elsewhere in the codebase?
6. Does it have the right length for its scope? (wider scope = longer, more descriptive name)
7. Is it free of encodings, noise words, and gratuitous context?
8. If it's a class -- is it a noun? If a method -- is it a verb? If a boolean -- does it read as a predicate?
```
