---
name: clean-code-ch04-comments
description: "Code quality checker based on Clean Code Ch4: Comments — detects redundant, misleading, mandated, journal, noise, and commented-out code; validates good comment patterns. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 4: Comments -- Code Quality Checker

> "Don't comment bad code -- rewrite it." -- Brian W. Kernighan and P. J. Plaugher

## Core Philosophy

Comments are, at best, a necessary evil. They compensate for our failure to express ourselves in code. The proper use of comments is to compensate for our failure to express intent in code. Every comment represents a failure to make the code self-explanatory. Truth can only be found in one place: the code. Inaccurate comments are far worse than no comments at all.

**The Golden Rule:** Before writing any comment, ask: "Can I express this in code instead?" If yes, do that. The only truly good comment is the comment you found a way not to write.

### Comments Do Not Make Up for Bad Code

One of the more common motivations for writing comments is bad code. We write a module and we know it is confusing and disorganized. We know it's a mess. So we say to ourselves, "Ooh, I'd better comment that!" No! You'd better clean it! Clear and expressive code with few comments is far superior to cluttered and complex code with lots of comments. Rather than spend your time writing the comments that explain the mess you've made, spend it cleaning that mess.

### Explain Yourself in Code

There are certainly times when code makes a poor vehicle for explanation. Unfortunately, many programmers have taken this to mean that code is seldom, if ever, a good means for explanation. This is patently false. Which would you rather see? This:

```java
// Check to see if the employee is eligible for full benefits
if ((employee.flags & HOURLY_FLAG) && (employee.age > 65))
```

Or this?

```java
if (employee.isEligibleForFullBenefits())
```

It takes only a few seconds of thought to explain most of your intent in code. In many cases it's simply a matter of creating a function that says the same thing as the comment you want to write.

## When to Use

Invoke this skill when:
- Reviewing code for comment quality (PR reviews, audits, refactoring)
- Writing new code and deciding whether a comment is warranted
- Refactoring existing code to remove or improve comments
- Evaluating whether commented-out code should be deleted
- Checking if mandated/boilerplate comments are adding clutter
- Assessing whether a function or variable name could replace a comment

## Checklist

Run through this checklist for every comment encountered:

### Quick Accept (Good Comment Patterns)
- [ ] Is it a **legal/copyright** comment required by corporate standards?
- [ ] Does it provide genuinely **informative** context that the code cannot express (e.g., regex format explanation)?
- [ ] Does it explain **intent** -- the WHY behind a decision, not the WHAT?
- [ ] Does it **clarify** an obscure argument or return value from code you cannot alter (e.g., standard library)?
- [ ] Does it **warn of consequences** (e.g., thread safety, long-running tests, side effects)?
- [ ] Is it a **TODO** that marks a legitimate deferred task with context?
- [ ] Does it **amplify** the importance of something that seems inconsequential?
- [ ] Is it a **Javadoc/docstring on a public API** that helps external consumers?

### Quick Reject (Bad Comment Patterns)
- [ ] Is it **mumbling** -- vague, incomplete, written hastily without thought?
- [ ] Is it **redundant** -- restating what the code already says, taking longer to read than the code?
- [ ] Is it **misleading** -- subtly inaccurate about what the code actually does?
- [ ] Is it **mandated** -- forced by a rule requiring every function/variable to have a comment?
- [ ] Is it a **journal comment** -- a changelog at the top of the file?
- [ ] Is it **noise** -- restating the obvious (e.g., `/** Default constructor. */`)?
- [ ] Is it **scary noise** -- noisy Javadocs with copy-paste errors?
- [ ] Could a **function or variable name** replace this comment?
- [ ] Is it a **position marker/banner** (e.g., `// Actions //////////`)?
- [ ] Is it a **closing brace comment** (e.g., `} //while`, `} //try`)?
- [ ] Is it an **attribution/byline** (e.g., `/* Added by Rick */`)?
- [ ] Is it **commented-out code**?
- [ ] Does it contain **HTML markup** in source code?
- [ ] Does it describe **nonlocal information** -- something far away in the system?
- [ ] Does it contain **too much information** -- historical discussions, irrelevant detail?
- [ ] Is the **connection between comment and code inobvious** -- does the comment itself need explanation?
- [ ] Is it a **function header** on a small, well-named function that needs no description?
- [ ] Is it a **Javadoc/docstring on nonpublic code** -- internal classes/methods that do not need formal docs?

---

## Violations to Detect

### BAD-01: Mumbling

**What it is:** A comment dropped in because the programmer felt obligated or the process required it, but without spending the time to make it clear. The comment forces the reader to look at other modules to understand its meaning.

**Detection pattern:** Comments in catch blocks, error handlers, or edge cases that are vague, incomplete, or cryptic. Comments that raise more questions than they answer.

**Example (VIOLATION):**
```java
public void loadProperties() {
    try {
        String propertiesPath = propertiesLocation + "/" + PROPERTIES_FILE;
        FileInputStream propertiesStream = new FileInputStream(propertiesPath);
        loadedProperties.load(propertiesStream);
    }
    catch(IOException e) {
        // No properties files means all defaults are loaded
    }
}
```
*Problem:* Who loads the defaults? Were they loaded before the call? Did loadProperties.load catch the exception, load the defaults, and re-throw? The comment is an enigma that forces exploration of other code.

**Fix:** Either make the comment precise and complete, or refactor the code so the behavior is obvious:
```java
public void loadProperties() {
    try {
        loadPropertiesFrom(propertiesLocation + "/" + PROPERTIES_FILE);
    }
    catch(IOException e) {
        loadDefaultProperties();  // Code is self-documenting now
    }
}
```

---

### BAD-02: Redundant Comments

**What it is:** A comment that is no more informative than the code itself. It takes longer to read than the code. It does not justify the code, provide intent, or offer rationale. It is less precise than the code and entices the reader to accept imprecision.

**Detection pattern:** Comments on simple methods/fields that merely restate the signature or declaration in English prose. Javadocs on every field that just echo the field name.

**Example (VIOLATION):**
```java
// Utility method that returns when this.closed is true. Throws an exception
// if the timeout is reached.
public synchronized void waitForClose(final long timeoutMillis)
    throws Exception
{
    if(!closed) {
        wait(timeoutMillis);
        if(!closed)
            throw new Exception("MockResponseSender could not be closed");
    }
}
```
*Problem:* The comment is not easier to read than the code. It adds no information beyond what the method signature and body already communicate.

**Example (VIOLATION) -- Redundant Javadocs on fields:**
```java
/** The processor delay for this component. */
protected int backgroundProcessorDelay = -1;

/** The lifecycle event support for this component. */
protected LifecycleSupport lifecycle = new LifecycleSupport(this);

/** The container event listeners for this Container. */
protected ArrayList listeners = new ArrayList();
```
*Problem:* Each comment just restates the variable name and type in English. They serve no documentary purpose and clutter the code.

**Fix:** Remove the comments entirely. If the name is not descriptive enough, rename the variable:
```java
protected int backgroundProcessorDelay = -1;
protected LifecycleSupport lifecycle = new LifecycleSupport(this);
protected ArrayList listeners = new ArrayList();
```

---

### BAD-03: Misleading Comments

**What it is:** A comment that is not precise enough to be accurate. It states something subtly different from what the code does, creating false expectations that lead to debugging sessions.

**Detection pattern:** Comments that describe behavior using words like "when" (implying event-driven) when the code actually polls or checks conditionally. Comments that omit important conditions or exception paths.

**Example (VIOLATION):**
```java
// Utility method that returns when this.closed is true. Throws an exception
// if the timeout is reached.
public synchronized void waitForClose(final long timeoutMillis)
    throws Exception
{
    if(!closed) {
        wait(timeoutMillis);
        if(!closed)
            throw new Exception("MockResponseSender could not be closed");
    }
}
```
*Problem:* The comment says the method returns "when this.closed becomes true." In fact, it returns IF this.closed is already true; otherwise, it waits for a blind timeout and then throws if this.closed is still not true. A programmer reading only the comment could expect immediate return upon state change.

**Fix:** Either fix the comment to be precisely accurate, or better, let the code speak:
```java
public synchronized void waitForClose(final long timeoutMillis)
    throws Exception
{
    if(!closed) {
        wait(timeoutMillis);
        if(!closed)
            throw new TimeoutException("waitForClose timed out after " + timeoutMillis + "ms");
    }
}
```

---

### BAD-04: Mandated Comments

**What it is:** Comments required by a rule that says every function must have a Javadoc, or every variable must have a comment. These clutter the code, propagate lies, and lend to general confusion.

**Detection pattern:** Javadocs where every `@param` simply restates the parameter name. Boilerplate doc comments on trivial methods like getters/setters. Comments that exist only to satisfy a linter rule.

**Example (VIOLATION):**
```java
/**
 *
 * @param title The title of the CD
 * @param author The author of the CD
 * @param tracks The number of tracks on the CD
 * @param durationInMinutes The duration of the CD in minutes
 */
public void addCD(String title, String author,
                   int tracks, int durationInMinutes) {
    CD cd = new CD();
    cd.title = title;
    cd.author = author;
    cd.tracks = tracks;
    cd.duration = duration;
    cdlist.add(cd);
}
```
*Problem:* Every @param just repeats the parameter name. The comment adds nothing, clutters the code, and creates the potential for lies when parameters change but the comment does not.

**Fix:** Remove the comment. The method signature is self-documenting:
```java
public void addCD(String title, String author, int tracks, int durationInMinutes) {
    CD cd = new CD();
    cd.title = title;
    cd.author = author;
    cd.tracks = tracks;
    cd.duration = durationInMinutes;
    cdlist.add(cd);
}
```

---

### BAD-05: Journal Comments

**What it is:** A log of changes accumulated at the top of a module -- a changelog maintained by hand inside the source file.

**Detection pattern:** Block comments at the top of files with dated entries listing changes, authors, and descriptions. Comments that look like version control logs.

**Example (VIOLATION):**
```java
* Changes (from 11-Oct-2001)
* --------------------------
* 11-Oct-2001 : Re-organised the class and moved it to new package
*               com.jrefinery.date (DG);
* 05-Nov-2001 : Added a getDescription() method, and eliminated NotableDate
*               class (DG);
* 12-Nov-2001 : IBD requires setDescription() method, now that NotableDate
*               class is gone (DG);
* 05-Dec-2001 : Fixed bug in SpreadsheetDate class (DG);
* 29-May-2002 : Moved the month constants into a separate interface
*               (MonthConstants) (DG);
```
*Problem:* Source code control systems (git, svn, etc.) do this job. These entries are just clutter that obfuscate the module. They should be completely removed.

**Fix:** Delete the entire journal block. Use `git log` for change history:
```java
// (file starts with imports or package declaration -- no journal)
```

---

### BAD-06: Noise Comments

**What it is:** Comments that restate the obvious and provide no new information. They are so noisy we learn to ignore them, and then they begin to lie as the code around them changes.

**Detection pattern:** `/** Default constructor. */` on a default constructor. `/** The day of the month. */` on a field named `dayOfMonth`. `/** Returns the day of the month. @return the day of the month. */` on `getDayOfMonth()`.

**Example (VIOLATION):**
```java
/** Default constructor. */
protected AnnualDateRule() {
}

/** The day of the month. */
private int dayOfMonth;

/**
 * Returns the day of the month.
 *
 * @return the day of the month.
 */
public int getDayOfMonth() {
    return dayOfMonth;
}
```
*Problem:* Every comment restates exactly what the code already says. They add visual noise and train the reader to skip all comments -- including the rare important ones.

**Fix:** Remove all three comments. The code is self-documenting:
```java
protected AnnualDateRule() {
}

private int dayOfMonth;

public int getDayOfMonth() {
    return dayOfMonth;
}
```

**Extended Example (Listing 4-4 -- startSending):** The first comment below (`// normal. someone stopped the request.`) is acceptable because it explains why the catch block is being ignored. The second comment (`//Give me a break!`) is pure noise -- the programmer was venting frustration rather than improving the code:

```java
private void startSending()
{
    try
    {
        doSending();
    }
    catch(SocketException e)
    {
        // normal. someone stopped the request.
    }
    catch(Exception e)
    {
        try
        {
            response.add(ErrorResponder.makeExceptionString(e));
            response.closeAll();
        }
        catch(Exception e1)
        {
            //Give me a break!
        }
    }
}
```

**Fix (Listing 4-5 -- refactored):** Rather than venting in a noisy comment, the programmer should have redirected energy to extracting the last try/catch block into a separate function:

```java
private void startSending()
{
    try
    {
        doSending();
    }
    catch(SocketException e)
    {
        // normal. someone stopped the request.
    }
    catch(Exception e)
    {
        addExceptionAndCloseResponse(e);
    }
}

private void addExceptionAndCloseResponse(Exception e)
{
    try
    {
        response.add(ErrorResponder.makeExceptionString(e));
        response.closeAll();
    }
    catch(Exception e1)
    {
    }
}
```

---

### BAD-07: Scary Noise

**What it is:** Javadocs that are noisy AND contain copy-paste errors, proving the author was not paying attention. If authors are not careful when writing comments, why should readers trust them?

**Detection pattern:** Doc comments on fields where the text does not match the field name (copy-paste artifacts). Comments where the description clearly belongs to a different field.

**Example (VIOLATION):**
```java
/** The name. */
private String name;

/** The version. */
private String version;

/** The licenceName. */
private String licenceName;

/** The version. */
private String info;
```
*Problem:* The last comment says "The version" but the field is `info`. This is a copy-paste error that proves carelessness and undermines trust in all comments in the file.

**Fix:** Delete all four comments. The field names are self-documenting. If `info` is too vague, rename it:
```java
private String name;
private String version;
private String licenceName;
private String releaseInfo;
```

---

### BAD-08: Comment Instead of Function or Variable

**What it is:** A comment that explains what a complex expression does, when the expression could be extracted into a well-named function or variable that makes the comment unnecessary.

**Detection pattern:** Comments above `if` statements or complex expressions that describe the logic. Comments that could become function names or variable names.

**Example (VIOLATION):**
```java
// Check to see if the employee is eligible for full benefits
if ((employee.flags & HOURLY_FLAG) && (employee.age > 65))
```

**Fix:** Extract the condition into a method:
```java
if (employee.isEligibleForFullBenefits())
```

**Example (VIOLATION):**
```java
// does the module from the global list <mod> depend on the
// subsystem we are part of?
if (smodule.getDependSubsystems().contains(subSysMod.getSubSystem()))
```

**Fix:** Use explanatory variables:
```java
ArrayList moduleDependees = smodule.getDependSubsystems();
String ourSubSystem = subSysMod.getSubSystem();
if (moduleDependees.contains(ourSubSystem))
```

---

### BAD-09: Position Markers (Banners)

**What it is:** Comments used to mark sections of a source file, often with long trains of slashes or other characters.

**Detection pattern:** Lines like `// Actions ///////////////////////////` or `// ============ Section ============`. Long runs of repeated characters used as visual separators.

**Example (VIOLATION):**
```java
// Actions //////////////////////////////////
```

*Problem:* If you overuse banners, they fall into background noise and are ignored. They are clutter, especially the noisy train of slashes at the end.

**Fix:** Remove the banner. If the file is so large it needs section markers, it probably needs to be split into separate classes/files. Use them only extremely sparingly where the benefit is significant.

---

### BAD-10: Closing Brace Comments

**What it is:** Comments placed on closing braces to indicate which block they close, such as `} //while` or `} //try`.

**Detection pattern:** Comments on lines that contain only a closing brace (`}`), annotating which construct (while, for, try, if, method) the brace closes.

**Example (VIOLATION):**
```java
while ((line = in.readLine()) != null) {
    lineCount++;
    charCount += line.length();
    String words[] = line.split("\\W");
    wordCount += words.length;
} //while
System.out.println("wordCount = " + wordCount);
System.out.println("lineCount = " + lineCount);
System.out.println("charCount = " + charCount);
} // try
catch (IOException e) {
    System.err.println("Error:" + e.getMessage());
} //catch
} //main
```
*Problem:* If a function is so long and deeply nested that you need closing brace comments to track where you are, the real problem is the function length. These comments are a symptom of excessive complexity.

**Fix:** Shorten the function. Extract nested blocks into well-named sub-functions. When functions are small, closing brace comments become unnecessary:
```java
while ((line = in.readLine()) != null) {
    processLine(line);
}
```

---

### BAD-11: Attributions and Bylines

**What it is:** Comments that record who wrote or modified a particular piece of code.

**Detection pattern:** Comments like `/* Added by Rick */`, `// Author: Jane`, or `/* Modified by Bob, 2003-10-14 */`.

**Example (VIOLATION):**
```java
/* Added by Rick */
```

*Problem:* Source control systems track authorship with perfect accuracy. These comments get stale, become inaccurate over years, and pollute the code.

**Fix:** Delete the comment. Use `git blame` to determine authorship:
```java
// (no comment needed -- git blame shows authorship)
```

---

### BAD-12: Commented-Out Code

**What it is:** Lines of code that have been commented out rather than deleted.

**Detection pattern:** Lines beginning with `//` or wrapped in `/* */` that contain syntactically valid code (variable declarations, method calls, assignments, control flow).

**Example (VIOLATION):**
```java
InputStreamResponse response = new InputStreamResponse();
response.setBody(formatter.getResultStream(), formatter.getByteCount());
// InputStream resultsStream = formatter.getResultStream();
// StreamReader reader = new StreamReader(resultsStream);
// response.setContent(reader.read(formatter.getByteCount()));
```

**Example (VIOLATION):**
```java
this.bytePos = writeBytes(pngIdBytes, 0);
//hdrPos = bytePos;
writeHeader();
writeResolution();
//dataPos = bytePos;
if (writeImageData()) {
    writeEnd();
    this.pngBytes = resizeByteArray(this.pngBytes, this.maxPos);
}
```

*Problem:* Other programmers will not have the courage to delete it. They will think it is there for a reason and is too important to remove. So commented-out code accumulates like dregs at the bottom of a bad bottle of wine.

**Fix:** Delete it. Source code control remembers everything. We will not lose it:
```java
InputStreamResponse response = new InputStreamResponse();
response.setBody(formatter.getResultStream(), formatter.getByteCount());
```

---

### BAD-13: HTML Comments

**What it is:** HTML tags embedded within source code comments, making them hard to read in the one place they should be easy to read -- the editor/IDE.

**Detection pattern:** Comments containing `<p>`, `<pre>`, `<b>`, `&lt;`, `&quot;`, `<br>`, or other HTML entities and tags.

**Example (VIOLATION):**
```java
/**
 * Task to run fit tests.
 * This task runs fitnesse tests and publishes the results.
 * <p/>
 * <pre>
 * Usage:
 * &lt;taskdef name=&quot;execute-fitnesse-tests&quot;
 *     classname=&quot;fitnesse.ant.ExecuteFitnesseTestsTask&quot;
 *     classpathref=&quot;classpath&quot; /&gt;
 * OR
 * &lt;taskdef classpathref=&quot;classpath&quot;
 *          resource=&quot;tasks.properties&quot; /&gt;
 * <p/>
 * &lt;execute-fitnesse-tests
 *     suitepage=&quot;FitNesse.SuiteAcceptanceTests&quot;
 *     fitnesseport=&quot;8082&quot;
 *     resultsdir=&quot;${results.dir}&quot;
 *     resultshtmlpage=&quot;fit-results.html&quot;
 *     classpathref=&quot;classpath&quot; /&gt;
 * </pre>
 */
```

*Problem:* This is an abomination in source code. It is unreadable in the editor. If HTML is needed for generated docs, the documentation tool should add it, not the programmer.

**Fix:** Write the comment in plain text. Let the doc generation tool handle formatting:
```java
/**
 * Runs FitNesse tests and publishes results.
 *
 * Usage: Configure via taskdef and invoke execute-fitnesse-tests
 * with suitepage, fitnesseport, resultsdir, and classpathref.
 */
```

---

### BAD-14: Nonlocal Information

**What it is:** A comment that describes information from somewhere else in the system -- not the code immediately adjacent. When the distant code changes, this comment will not be updated.

**Detection pattern:** Comments that mention default values, ports, configuration settings, or behaviors defined in other files or classes. Comments that reference system-wide state not controlled by the local function.

**Example (VIOLATION):**
```java
/**
 * Port on which fitnesse would run. Defaults to <b>8082</b>.
 *
 * @param fitnessePort
 */
public void setFitnessePort(int fitnessePort)
{
    this.fitnessePort = fitnessePort;
}
```
*Problem:* The comment mentions the default port 8082, but this function is a setter -- it has no control over the default. The default is defined elsewhere. When it changes, this comment will become a lie.

**Fix:** Remove the nonlocal information. Only describe what the function itself does:
```java
public void setFitnessePort(int fitnessePort) {
    this.fitnessePort = fitnessePort;
}
```

---

### BAD-15: Too Much Information

**What it is:** Comments containing interesting historical discussions, irrelevant descriptions of detail, or encyclopedic entries that no reader needs.

**Detection pattern:** Multi-paragraph comments explaining RFC specifications, algorithm history, mathematical proofs, or implementation details of external standards. Comments longer than the code they describe.

**Example (VIOLATION):**
```java
/*
 RFC 2045 - Multipurpose Internet Mail Extensions (MIME)
 Part One: Format of Internet Message Bodies
 section 6.8.  Base64 Content-Transfer-Encoding
 The encoding process represents 24-bit groups of input bits as output
 strings of 4 encoded characters. Proceeding from left to right, a
 24-bit input group is formed by concatenating 3 8-bit input groups.
 These 24 bits are then treated as 4 concatenated 6-bit groups, each
 of which is translated into a single digit in the base64 alphabet.
 When encoding a bit stream via the base64 encoding, the bit stream
 must be presumed to be ordered with the most-significant-bit first.
 ...
*/
```

*Problem:* Nobody reading the code needs the full RFC text. The RFC number alone is sufficient for anyone who needs the details.

**Fix:** Reference the standard without copying it:
```java
// Encodes/decodes base64 per RFC 2045 section 6.8.
```

---

### BAD-16: Inobvious Connection

**What it is:** A comment whose connection to the code it describes is not obvious. The comment itself needs an explanation.

**Detection pattern:** Comments that use terms not found in the adjacent code. Comments where the reader cannot understand the mapping between comment concepts and code variables/operations.

**Example (VIOLATION):**
```java
/*
 * start with an array that is big enough to hold all the pixels
 * (plus filter bytes), and an extra 200 bytes for header info
 */
this.pngBytes = new byte[((this.width + 1) * this.height * 3) + 200];
```

*Problem:* What is a "filter byte"? Does the +1 relate to it? Or to the *3? Is a pixel a byte? Why 200? The comment raises questions it does not answer. A comment that needs its own explanation has failed.

**Fix:** Make both the code and comment crystal clear:
```java
int pixelDataSize = this.width * this.height * BYTES_PER_PIXEL;
int filterBytesSize = this.height;  // one filter byte per scanline
int headerSize = 200;
this.pngBytes = new byte[pixelDataSize + filterBytesSize + headerSize];
```

---

### BAD-17: Function Headers

**What it is:** Comments placed above short, well-named functions that simply describe what the function does -- when the function name already communicates this.

**Detection pattern:** Block comments or Javadocs above small functions (fewer than ~10 lines) where the function name is descriptive and the body is straightforward.

**Example (VIOLATION):**
```java
/**
 * Crosses out all multiples of the given integer in the crossedOut array.
 */
private static void crossOutMultiplesOf(int i) {
    for (int multiple = 2*i;
         multiple < crossedOut.length;
         multiple += i)
        crossedOut[multiple] = true;
}
```

**Fix:** The function name `crossOutMultiplesOf` already says everything. Remove the comment:
```java
private static void crossOutMultiplesOf(int i) {
    for (int multiple = 2*i;
         multiple < crossedOut.length;
         multiple += i)
        crossedOut[multiple] = true;
}
```

---

### BAD-18: Javadocs in Nonpublic Code

**What it is:** Formal Javadoc comments on internal classes, private methods, and package-private code that is not part of a public API.

**Detection pattern:** `/** ... */` style comments on `private`, `protected`, or package-private methods and classes that are not part of an external API surface.

**Example (VIOLATION):**
```java
/**
 * @param maxValue is the generation limit.
 */
public static int[] generatePrimes(int maxValue) {
    // ... internal utility, not a public API
}
```

*Problem:* Generating Javadoc pages for internal code is not generally useful. The extra formality of Javadoc amounts to little more than cruft and distraction. Internal code needs readability, not formal documentation.

**Fix:** Use simple comments only where they add genuine value, or let the code speak for itself:
```java
public static int[] generatePrimes(int maxValue) {
    // ...
}
```

---

## GOOD Comment Patterns (Acceptable/Encouraged)

### GOOD-01: Legal Comments

**What it is:** Copyright and license statements required by corporate coding standards at the top of source files.

**When acceptable:** Always, when required. Refer to a standard license rather than embedding full terms.

**Example:**
```java
// Copyright (C) 2003,2004,2005 by Object Mentor, Inc. All rights reserved.
// Released under the terms of the GNU General Public License version 2 or later.
```

---

### GOOD-02: Informative Comments

**What it is:** Comments that provide basic information that is genuinely useful, especially when the code alone is insufficient (e.g., explaining regex patterns, abstract method return types).

**When acceptable:** When renaming or restructuring cannot convey the information. Still, prefer making the comment redundant by renaming.

**Example (abstract method return type):**
```java
// Returns an instance of the Responder being tested.
protected abstract Responder responderInstance();
```
*Note:* This comment can be made redundant by renaming the function to `responderBeingTested`.

**Example (regex format):**
```java
// format matched kk:mm:ss EEE, MMM dd, yyyy
Pattern timeMatcher = Pattern.compile(
    "\\d*:\\d*:\\d* \\w*, \\w* \\d*, \\d*");
```

**Better approach:** Move the regex to a class with a descriptive name that converts date/time formats, making the comment superfluous.

---

### GOOD-03: Explanation of Intent

**What it is:** Comments that go beyond information about implementation to reveal the intent behind a decision -- the WHY, not the WHAT.

**When acceptable:** When the code shows what was done but not why the programmer chose this approach over alternatives.

**Example:**
```java
public int compareTo(Object o) {
    if(o instanceof WikiPagePath) {
        WikiPagePath p = (WikiPagePath) o;
        String compressedName = StringUtil.join(names, "");
        String compressedArgumentName = StringUtil.join(p.names, "");
        return compressedName.compareTo(compressedArgumentName);
    }
    return 1; // we are greater because we are the right type.
}
```

**Example:**
```java
public void testConcurrentAddWidgets() throws Exception {
    // This is our best attempt to get a race condition
    // by creating large number of threads.
    for (int i = 0; i < 25000; i++) {
        WidgetBuilderThread widgetBuilderThread =
            new WidgetBuilderThread(widgetBuilder, text, parent, failFlag);
        Thread thread = new Thread(widgetBuilderThread);
        thread.start();
    }
    assertEquals(false, failFlag.get());
}
```

---

### GOOD-04: Clarification

**What it is:** Comments that translate the meaning of an obscure argument or return value into something readable, especially when using standard library code you cannot alter.

**When acceptable:** When the argument/return value is part of a library API and you cannot make it self-documenting. Take great care that the clarification is accurate -- there is substantial risk of being wrong.

**Example:**
```java
assertTrue(a.compareTo(a) == 0);    // a == a
assertTrue(a.compareTo(b) != 0);    // a != b
assertTrue(ab.compareTo(ab) == 0);  // ab == ab
assertTrue(a.compareTo(b) == -1);   // a < b
assertTrue(aa.compareTo(ab) == -1); // aa < ab
assertTrue(ba.compareTo(bb) == -1); // ba < bb
assertTrue(b.compareTo(a) == 1);    // b > a
assertTrue(ab.compareTo(aa) == 1);  // ab > aa
assertTrue(bb.compareTo(ba) == 1);  // bb > ba
```

---

### GOOD-05: Warning of Consequences

**What it is:** Comments that warn other programmers about consequences -- why a test is disabled, why something is not thread-safe, why a particular approach is dangerous.

**When acceptable:** Always, when the consequence is non-obvious and important.

**Example:**
```java
// Don't run unless you have some time to kill.
public void _testWithReallyBigFile() {
    writeLinesToFile(10000000);
    // ...
}
```

**Example:**
```java
public static SimpleDateFormat makeStandardHttpDateFormat() {
    // SimpleDateFormat is not thread safe,
    // so we need to create each instance independently.
    SimpleDateFormat df = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z");
    df.setTimeZone(TimeZone.getTimeZone("GMT"));
    return df;
}
```

---

### GOOD-06: TODO Comments

**What it is:** Notes in the form of `// TODO` that mark tasks the programmer believes should be done but cannot do right now.

**When acceptable:** When there is a legitimate reason the work cannot be done now. TODOs should explain why the function has a degenerate implementation, what its future should be, or what event it is waiting on. They are NOT an excuse to leave bad code in the system.

**Example:**
```java
// TODO-MdM these are not needed
// We expect this to go away when we do the checkout model
protected VersionInfo makeVersion() throws Exception {
    return null;
}
```

**Important:** Scan through TODOs regularly and eliminate the ones you can. Do not litter your code with TODOs.

---

### GOOD-07: Amplification

**What it is:** A comment that amplifies the importance of something that may otherwise seem inconsequential, preventing a future programmer from "optimizing" it away.

**When acceptable:** When the significance of a line of code is non-obvious and removing or changing it would cause subtle bugs.

**Example:**
```java
String listItemContent = match.group(3).trim();
// the trim is real important. It removes the starting
// spaces that could cause the item to be recognized
// as another list.
new ListItemWidget(this, listItemContent, this.level + 1);
return buildList(text.substring(match.end()));
```

---

### GOOD-08: Javadocs in Public APIs

**What it is:** Well-written documentation comments on public API methods, classes, and interfaces that external consumers depend on.

**When acceptable:** Always, for public APIs. But keep in mind the rest of this chapter -- Javadocs can be just as misleading, nonlocal, and dishonest as any other kind of comment.

**Example:**
```java
/**
 * Generates prime numbers up to a user-specified maximum.
 * The algorithm used is the Sieve of Eratosthenes.
 * Given an array of integers starting at 2:
 * Find the first uncrossed integer, and cross out all its
 * multiples. Repeat until there are no more multiples
 * in the array.
 */
public class PrimeGenerator { ... }
```

---

## How to Fix

### Decision Tree: What to Do With a Comment

```
Found a comment
    |
    v
Is it a legal/copyright comment? --> YES --> Keep it (reference external license doc)
    |
    NO
    v
Is it commented-out code? --> YES --> DELETE IT (source control remembers)
    |
    NO
    v
Is it a journal/changelog? --> YES --> DELETE IT (use git log)
    |
    NO
    v
Is it an attribution/byline? --> YES --> DELETE IT (use git blame)
    |
    NO
    v
Can you express it as a function or variable name? --> YES --> REFACTOR
    |
    NO
    v
Does it explain INTENT (the WHY)? --> YES --> KEEP IT (ensure accuracy)
    |
    NO
    v
Does it WARN of consequences? --> YES --> KEEP IT
    |
    NO
    v
Is it a TODO with legitimate reason? --> YES --> KEEP IT (review periodically)
    |
    NO
    v
Does it AMPLIFY something non-obvious? --> YES --> KEEP IT
    |
    NO
    v
Does it CLARIFY library code you cannot change? --> YES --> KEEP IT (verify accuracy)
    |
    NO
    v
Is it on a PUBLIC API? --> YES --> KEEP JAVADOC (make it accurate and local)
    |
    NO
    v
Does it provide INFORMATIVE context code cannot? --> YES --> KEEP (try to make redundant first)
    |
    NO
    v
DELETE IT or REFACTOR the code to make it unnecessary
```

### Refactoring Strategies

1. **Extract Method:** Replace a comment explaining a code block with a well-named function.
2. **Extract Variable:** Replace a comment explaining an expression with a well-named variable.
3. **Rename:** If a comment explains what a function/variable is, rename the function/variable instead.
4. **Delete:** If a comment adds no value (noise, redundant, journal, byline, commented-out code), remove it.
5. **Rewrite:** If a comment is mumbling, misleading, or has an inobvious connection, either rewrite it to be precise and accurate, or refactor the code so it is unnecessary.

---

## Self-Improvement Protocol

After each code review using this skill:

1. **Tally violations** by category (BAD-01 through BAD-18) to identify the most common anti-patterns in the codebase.
2. **Track false positives** -- comments initially flagged as bad that turned out to be genuinely valuable. Refine detection heuristics.
3. **Measure comment density** -- a high ratio of comments to code often indicates the code is not expressive enough. The goal is fewer, better comments.
4. **Check for stale comments** -- comments that no longer match the code they describe are the most dangerous. Prioritize fixing or removing these.
5. **Verify good comments** -- for any comment you keep, confirm it is accurate, local, and has an obvious connection to the code.
6. **Apply the fundamental rule:** Every time you express yourself in code instead of a comment, pat yourself on the back. Every time you write a comment, grimace and feel the failure of your ability of expression.

---

## Full Chapter Example: Before and After

The chapter concludes with a complete before/after example showing how comment-heavy code (Listing 4-7, GeneratePrimes.java) can be refactored into clean code (Listing 4-8, PrimeGenerator.java) where the code itself communicates intent and only two explanatory comments survive.

### Before (Listing 4-7 -- GeneratePrimes.java)

This module was intended as an example of bad code and commenting style. Note the excessive comments: HTML in Javadoc, noise comments, redundant remarks, bylines, and unclear variable names that demand explanation.

```java
/**
 * This class Generates prime numbers up to a user specified
 * maximum.  The algorithm used is the Sieve of Eratosthenes.
 * <p>
 * Eratosthenes of Cyrene, b. c. 276 BC, Cyrene, Libya --
 * d. c. 194, Alexandria.  The first man to calculate the
 * circumference of the Earth.  Also known for working on
 * calendars with leap years and ran the library at Alexandria.
 * <p>
 * The algorithm is quite simple.  Given an array of integers
 * starting at 2.  Cross out all multiples of 2.  Find the next
 * uncrossed integer, and cross out all of its multiples.
 * Repeat until you have passed the square root of the maximum
 * value.
 *
 * @author Alphonse
 * @version 13 Feb 2002 atp
 */
import java.util.*;

public class GeneratePrimes
{
    /**
     * @param maxValue is the generation limit.
     */
    public static int[] generatePrimes(int maxValue)
    {
        if (maxValue >= 2) // the only valid case
        {
            // declarations
            int s = maxValue + 1; // size of array
            boolean[] f = new boolean[s];
            int i;

            // initialize array to true.
            for (i = 0; i < s; i++)
                f[i] = true;

            // get rid of known non-primes
            f[0] = f[1] = false;

            // sieve
            int j;
            for (i = 2; i < Math.sqrt(s) + 1; i++)
            {
                if (f[i]) // if i is uncrossed, cross its multiples.
                {
                    for (j = 2 * i; j < s; j += i)
                        f[j] = false; // multiple is not prime
                }
            }

            // how many primes are there?
            int count = 0;
            for (i = 0; i < s; i++)
            {
                if (f[i])
                    count++; // bump count.
            }

            int[] primes = new int[count];

            // move the primes into the result
            for (i = 0, j = 0; i < s; i++)
            {
                if (f[i])             // if prime
                    primes[j++] = i;
            }

            return primes;  // return the primes
        }
        else // maxValue < 2
            return new int[0]; // return null array if bad input.
    }
}
```

**Comment problems identified:** HTML in Javadoc (`<p>`), too much information (Eratosthenes biography), `@author` byline, `@version` tag (journal-like), mandated `@param` Javadoc on nonpublic code, noise comments (`// declarations`, `// size of array`, `// bump count.`, `// return the primes`, `// return null array if bad input.`), redundant comments (`// the only valid case`, `// if prime`, `// multiple is not prime`, `// initialize array to true.`, `// get rid of known non-primes`), unclear variable names (`s`, `f`, `i`, `j`) that force comment explanations.

### After (Listing 4-8 -- PrimeGenerator.java, refactored)

The refactored version has just two comments in the whole module. Both are explanatory in nature. The code itself reads clearly through well-named methods and variables.

```java
/**
 * This class Generates prime numbers up to a user specified
 * maximum.  The algorithm used is the Sieve of Eratosthenes.
 * Given an array of integers starting at 2:
 * Find the first uncrossed integer, and cross out all its
 * multiples.  Repeat until there are no more multiples
 * in the array.
 */
public class PrimeGenerator
{
    private static boolean[] crossedOut;
    private static int[] result;

    public static int[] generatePrimes(int maxValue)
    {
        if (maxValue < 2)
            return new int[0];
        else
        {
            uncrossIntegersUpTo(maxValue);
            crossOutMultiples();
            putUncrossedIntegersIntoResult();
            return result;
        }
    }

    private static void uncrossIntegersUpTo(int maxValue)
    {
        crossedOut = new boolean[maxValue + 1];
        for (int i = 2; i < crossedOut.length; i++)
            crossedOut[i] = false;
    }

    private static void crossOutMultiples()
    {
        int limit = determineIterationLimit();
        for (int i = 2; i <= limit; i++)
            if (notCrossed(i))
                crossOutMultiplesOf(i);
    }

    private static int determineIterationLimit()
    {
        // Every multiple in the array has a prime factor that
        // is less than or equal to the root of the array size,
        // so we don't have to cross out multiples of numbers
        // larger than that root.
        double iterationLimit = Math.sqrt(crossedOut.length);
        return (int) iterationLimit;
    }

    private static void crossOutMultiplesOf(int i)
    {
        for (int multiple = 2*i;
             multiple < crossedOut.length;
             multiple += i)
            crossedOut[multiple] = true;
    }

    private static boolean notCrossed(int i)
    {
        return crossedOut[i] == false;
    }

    private static void putUncrossedIntegersIntoResult()
    {
        result = new int[numberOfUncrossedIntegers()];
        for (int j = 0, i = 2; i < crossedOut.length; i++)
            if (notCrossed(i))
                result[j++] = i;
    }

    private static int numberOfUncrossedIntegers()
    {
        int count = 0;
        for (int i = 2; i < crossedOut.length; i++)
            if (notCrossed(i))
                count++;

        return count;
    }
}
```

**Key observations:**
- The first comment (class Javadoc) is arguably redundant since `generatePrimes` reads very much like the function itself. Still, it serves to ease the reader into the algorithm.
- The second comment (in `determineIterationLimit`) is almost certainly necessary. It explains the *rationale* behind using the square root as the loop limit -- the WHY behind a mathematical optimization. No simple variable name nor different coding structure could make this point clear without the comment.
- All noise, redundant, and byline comments are gone. Variable names (`crossedOut`, `result`, `notCrossed`, `crossOutMultiplesOf`) eliminate the need for comments. Short, well-named functions replace commented code blocks.
