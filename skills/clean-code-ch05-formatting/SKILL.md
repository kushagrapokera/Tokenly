---
name: clean-code-ch05-formatting
description: "Code quality checker based on Clean Code Ch5: Formatting -- checks vertical formatting (file size, openness, density, distance, ordering), horizontal formatting (line length, spacing, alignment, indentation), and team rules. Scope: shared - applies to backend and frontend code."
---

# Clean Code Chapter 5: Formatting -- Code Quality Checker

## Core Principle

Code formatting is *important*. It is too important to ignore and it is too important to treat religiously. Code formatting is about **communication**, and communication is the professional developer's first order of business.

Perhaps you thought that "getting it working" was the first order of business for a professional developer. The functionality you create today has a good chance of changing in the next release, but the readability of your code will have a profound effect on all the changes that will ever be made. The coding style and readability set precedents that continue to affect maintainability and extensibility long after the original code has been changed beyond recognition. Your style and discipline survive, even though your code does not.

When people look under the hood, we want them to be impressed with the neatness, consistency, and attention to detail that they perceive. We want them to be struck by the orderliness. If instead they see a scrambled mass of code that looks like it was written by a bevy of drunken sailors, they are likely to conclude that the same inattention to detail pervades every other aspect of the project.

Choose a set of simple formatting rules, apply them consistently, and if on a team, agree to a single set of rules that all members follow. Encode those rules into an automated tool that can apply those formatting rules for you.

---

## When to Use

Invoke this skill when:
- Reviewing any code (pull requests, self-review, refactoring)
- Writing new files or functions
- Reorganizing or restructuring existing code
- Establishing or auditing team coding standards
- Evaluating whether a file has grown too large or too wide
- Checking that related concepts are grouped properly
- Assessing readability of variable placement, function ordering, or whitespace usage

---

## Checklist

### A. Vertical Formatting

- [ ] **File Size**: File is ideally ~200 lines, with a soft upper limit of ~500 lines. Although this should not be a hard and fast rule, it should be considered very desirable. Small files are usually easier to understand than large files. (FitNesse: ~50,000 lines of code, average file ~65 lines, one-third of files between 40-100+ lines, largest ~400 lines, smallest 6 lines. JUnit, FitNesse, Time and Money: none over 500 lines, most <200 lines. Tomcat and Ant: files reaching several thousand lines, close to half over 200 lines.)
- [ ] **Newspaper Metaphor**: File reads top-to-bottom like a newspaper article. Name is simple but explanatory. Top of file has high-level concepts/abstractions. Detail increases as you move downward. Lowest-level functions and details are at the bottom. A newspaper is composed of many articles; most are very small. If the newspaper were just one long story containing a disorganized agglomeration of facts, dates, and names, we simply would not read it.
- [ ] **Vertical Openness Between Concepts**: Blank lines separate distinct thoughts -- between package declaration, imports, and each function. Each blank line is a visual cue identifying a new and separate concept.
- [ ] **Vertical Density**: Lines that are tightly related appear vertically dense (no unnecessary blank lines or comments between them). Useless comments between closely related declarations break the visual association.
- [ ] **Vertical Distance -- General Principle**: Concepts that are closely related should be kept vertically close to each other [G10]. Closely related concepts should not be separated into different files unless you have a very good reason. Indeed, this is one of the reasons that protected variables should be avoided. For concepts that belong in the same source file, their vertical separation should be a measure of how important each is to the understandability of the other.
- [ ] **Vertical Distance -- Variable Declarations**: Local variables declared as close to their usage as possible. In short functions, variables appear at the top. Control variables for loops declared within the loop statement. In rare cases, a variable may be declared at the top of a block or just before a loop in a longer function.
- [ ] **Vertical Distance -- Instance Variables**: Declared at the top of the class (Java convention) or in one well-known, consistent place. Everyone should know where to find them. Never hide them in the middle of the class.
- [ ] **Vertical Distance -- Dependent Functions**: Caller is above the callee. This gives the program a natural downward flow. Readers can trust that function definitions will follow shortly after their use.
- [ ] **Vertical Distance -- Conceptual Affinity**: Functions/code that share a common naming scheme, perform variations of the same task, or have direct dependence (one calls another, one uses a variable) are kept vertically close. The stronger the affinity, the less vertical distance between them.
- [ ] **Vertical Ordering**: Function call dependencies point downward. The called function is below the calling function. High-level concepts come first; low-level details come last. This allows skimming source files to get the gist from the first few functions, without having to immerse ourselves in the details. (Note: this is the exact opposite of languages like Pascal, C, and C++ that enforce functions to be defined, or at least declared, before they are used.)

### B. Horizontal Formatting

- [ ] **Line Width**: Lines are ideally ~45 characters (regularity peak from data). The old Hollerith limit of 80 is a bit arbitrary. Lines up to 100 or even 120 are acceptable. Beyond 120 is probably just careless. Uncle Bob's personal limit: 120 characters. Do not shrink the font so small that you can fit 200 characters across the screen. (Data from 7 projects: every size from 20 to 60 represents about 1 percent of the total number of lines -- that's 40 percent. Another 30% are <10 chars. The linear appearance of the drop-off above 80 characters on a log scale represents a very significant absolute decrease. Programmers clearly prefer short lines.)
- [ ] **Horizontal Openness and Density -- Assignment Operators**: Surround assignment operators with spaces to accentuate the two distinct sides (left and right). Example: `int lineSize = line.length();`
- [ ] **Horizontal Openness and Density -- Function Calls**: No space between function name and opening parenthesis (they are closely related). Separate arguments with a space after the comma. Example: `measureLine(line)` and `addLine(lineSize, lineCount)`
- [ ] **Horizontal Openness and Density -- Operator Precedence**: Use spacing to accentuate operator precedence. No space around high-precedence factors (multiplication), spaces around lower-precedence terms (addition/subtraction). Example: `return b*b - 4*a*c;` and `return (-b + Math.sqrt(determinant)) / (2*a);` (Note: most auto-formatters destroy this subtlety.)
- [ ] **Horizontal Alignment**: Do NOT use horizontal alignment of variable names, types, or rvalues in declarations/assignments. Aligned columns draw the eye to the wrong things (variable names without types, or rvalues without operators). If a list of declarations is long enough to warrant alignment, the problem is the length of the list, not the lack of alignment -- the class should be split.
- [ ] **Indentation**: A source file is a hierarchy rather like an outline. Indent source code in proportion to its position in the scope hierarchy. File-level statements (class declarations) not indented. Methods indented one level inside the class. Method implementations indented one level inside the method. Block implementations indented one level inside their containing block. And so on. Programmers rely heavily on this indentation scheme -- they visually line up lines on the left to see what scope they appear in, scan the left for new method declarations, new variables, and even new classes. Without indentation, programs would be virtually unreadable by humans.
- [ ] **Breaking Indentation**: Never collapse scopes onto one line for short `if` statements, short `while` loops, or short functions. Always expand and indent the scopes, even for single-line bodies.
- [ ] **Dummy Scopes**: Avoid empty bodies for `while` or `for` loops. If unavoidable, make the semicolon visible by placing it indented on its own line, surrounded by braces. Never let a semicolon sit silently at the end of a `while` on the same line.

### C. Team Rules

- [ ] The **team** agrees on a single formatting style (brace placement, indent size, naming conventions for classes/variables/methods, etc.). Every programmer has his own favorite formatting rules, but if he works in a team, then the team rules.
- [ ] Every member uses that style consistently -- the software should not look like it was written by a bunch of disagreeing individuals.
- [ ] Rules are encoded into the IDE/code formatter and used by all team members. When Uncle Bob started the FitNesse project back in 2002, he sat down with the team and this took about 10 minutes. They decided where to put braces, what indent size would be, how to name classes, variables, and methods, and so forth. These were not his preferred rules; they were rules decided by the team.
- [ ] A good software system is composed of a set of documents that read nicely. They need to have a consistent and smooth style. The reader needs to be able to trust that formatting gestures seen in one source file will mean the same thing in others. The last thing we want to do is add more complexity to the source code by writing it in a jumble of different individual styles.

### D. Uncle Bob's Formatting Rules

- [ ] Uncle Bob's personal rules are illustrated by Listing 5-6 (CodeAnalyzer.java). Code itself makes the best coding standard document.
- [ ] The listing demonstrates: instance variables at top, constructor next, static public methods, public methods, then private methods. Caller above callee throughout. Blank lines between methods. Short methods. Consistent indentation. No horizontal alignment. 120-char line limit.

---

## Violations to Detect

### V1: File Too Long
- **Symptom**: Source file exceeds ~500 lines.
- **Severity**: Warning at >300 lines, strong warning at >500 lines.
- **Evidence from chapter**: Significant systems (FitNesse, ~50,000 lines) can be built with most files ~200 lines and none exceeding 500. Small files are usually easier to understand than large files.
- **Fix**: Extract classes, split responsibilities. Each file should represent a single concept.

### V2: Missing Vertical Openness (No Blank Lines Between Concepts)
- **Symptom**: Package declaration, imports, functions, or distinct thought groups are NOT separated by blank lines.
- **Evidence**: Listing 5-1 vs 5-2 -- removing blank lines makes code look like "a muddle" and is "remarkably obscuring."
- **Fix**: Add a single blank line between each distinct concept (package, imports, each function, logical groups within functions).

### V3: Broken Vertical Density (Unnecessary Gaps Between Related Lines)
- **Symptom**: Useless comments or blank lines wedged between closely related declarations or statements.
- **Evidence**: Listing 5-3 vs 5-4 -- comments between two instance variables break the "eye-full" association.
- **Fix**: Remove pointless intervening comments. Keep tightly related lines (e.g., instance variable declarations) immediately adjacent.

### V4: Variable Declared Far from Usage
- **Symptom**: A local variable is declared many lines before it is first used, or at a distance that requires scrolling.
- **Fix**: Move the declaration to the closest point before its first use. For short functions, declare at the top. For loop variables, declare within the loop statement itself.

### V5: Instance Variables Not at Top of Class
- **Symptom**: Instance variables declared in the middle or bottom of the class, or scattered throughout.
- **Evidence**: The TestSuite class in JUnit 4.3.1 hid instance variables (`fName`, `fTests`) halfway down the listing. "It would be hard to hide them in a better place."
- **Fix**: Move all instance variables to the top of the class (Java convention) or the bottom (C++ scissors rule) -- pick one well-known place and be consistent.

### V6: Caller Below Callee (Inverted Dependency Order)
- **Symptom**: A function that calls another function is defined BELOW the function it calls.
- **Evidence**: Listing 5-5 (WikiPageResponder.java) demonstrates the correct pattern -- `makeResponse` calls `getPageNameOrDefault`, `loadPage`, `notFoundResponse`, `makePageResponse`, and each callee appears below its caller.
- **Fix**: Reorder so the caller is always above the callee. High-level functions at top, low-level at bottom. This creates a natural top-down reading flow.

### V7: Conceptually Related Code Separated
- **Symptom**: Functions sharing a naming scheme (e.g., `assertTrue`, `assertFalse`) or performing variations of the same task are placed far apart in the file, possibly with unrelated functions between them.
- **Evidence**: The Assert class in JUnit 4.3.1 groups `assertTrue(message, condition)`, `assertTrue(condition)`, `assertFalse(message, condition)`, `assertFalse(condition)` together -- they have "strong conceptual affinity."
- **Fix**: Group conceptually related functions together regardless of whether they directly call each other.

### V8: Line Too Long
- **Symptom**: Lines exceeding 120 characters.
- **Severity**: Suggestion at >100 characters, warning at >120 characters.
- **Evidence**: Data from 7 projects shows regularity at ~45 chars with sharp drop-off above 80 on log scale. "Beyond [120] is probably just careless."
- **Fix**: Break the line at a logical point. If many lines are long, consider extracting variables or methods.

### V9: Incorrect Horizontal Spacing
- **Symptom**: Missing spaces around assignment operators, spaces between function names and parentheses, missing spaces after commas in argument lists, or uniform spacing that ignores operator precedence.
- **Evidence**: `int lineSize = line.length();` (space around `=`) but `measureLine(line)` (no space before `(`). `b*b - 4*a*c` uses no space around `*` but space around `-`.
- **Fix**: Apply spacing rules consistently: spaces around assignments, no space between function name and `(`, space after commas, and (where formatters allow) tighter spacing for higher-precedence operators.

### V10: Horizontal Alignment of Declarations/Assignments
- **Symptom**: Columns of variable names or rvalues are aligned using extra whitespace.
- **Evidence**: The FitNesseExpediter example shows how alignment draws the eye to the wrong things -- reading down variable names without seeing types, or reading rvalues without seeing operators. Auto-formatters usually eliminate this alignment anyway.
- **Fix**: Remove horizontal alignment. Use unaligned declarations. If the list is long enough to "need" alignment, the class has too many fields and should be split.

### V11: Collapsed/Missing Indentation
- **Symptom**: Short `if` bodies, `while` bodies, or short functions written on a single line. Or code that collapses scopes to reduce vertical space.
- **Evidence**: `public String render() throws Exception {return "";}` collapsed onto one line vs. the properly expanded and indented version.
- **Fix**: Always expand the scope onto its own indented line(s), even for single-statement bodies.

### V12: Invisible Dummy Scope
- **Symptom**: A `while` or `for` loop with an empty body where the semicolon sits at the end of the same line as the loop statement, making it nearly invisible.
- **Evidence**: `while (dis.read(buf, 0, readBufferSize) != -1)` with the semicolon hidden at end of line.
- **Fix**: Place the semicolon on its own indented line, preferably within braces:
  ```
  while (dis.read(buf, 0, readBufferSize) != -1)
    ;
  ```

### V13: Inconsistent Team Style
- **Symptom**: Different files in the same project use different brace placement, indent sizes, naming conventions, or spacing rules. The codebase looks like it was "written by a bunch of disagreeing individuals."
- **Fix**: Agree on team rules. Encode them in the formatter/linter. All members comply. Individual preferences yield to team consistency.

### V14: Constants Buried in Low-Level Functions
- **Symptom**: Well-known and expected constants are defined deep inside low-level functions rather than being passed down from the higher-level caller.
- **Evidence**: The `"FrontPage"` constant in Listing 5-5 is passed as a parameter from `makeResponse` to `getPageNameOrDefault` rather than being buried in the low-level function. This is a nice example of keeping constants at the appropriate level [G35]. The constant could have been buried in `getPageNameOrDefault`, but that would have hidden a well-known and expected constant in an inappropriately low-level function. It was better to pass that constant down from the place where it makes sense to know it to the place that actually uses it.
- **Fix**: Keep constants at the appropriate level of abstraction. Pass them from high-level to low-level, not the reverse.

### V15: File Name Not Explanatory
- **Symptom**: The source file name does not clearly communicate what the file contains, or you cannot tell if you are in the right module from the name alone.
- **Evidence**: The Newspaper Metaphor requires "the name should be simple but explanatory. The name, by itself, should be sufficient to tell us whether we are in the right module or not."
- **Fix**: Rename the file/class so its name communicates its purpose at a glance.

---

## How to Fix

### Vertical Formatting Fixes

1. **Shrink large files**: Extract classes using Single Responsibility Principle. Each file should represent one concept. Target ~200 lines; hard-question anything over 500.

2. **Apply the Newspaper Metaphor**:
   - File name = headline (descriptive)
   - Top of file = synopsis (public API, high-level functions)
   - Middle = increasing detail
   - Bottom = lowest-level details and helpers

3. **Add blank lines between concepts**: One blank line between package, imports, each method, and each logical group of statements within a method.

4. **Remove unnecessary gaps**: Delete useless Javadoc-style comments on obvious fields. Keep tightly related declarations adjacent with no intervening blank lines or comments.

5. **Move variables close to usage**: Local vars at function top (for short functions), loop vars in the loop statement, block vars at block top. Instance vars at class top.

6. **Reorder functions top-down**: Caller above callee. Group conceptually related functions together. Public API methods near top, private helpers below.

### Horizontal Formatting Fixes

7. **Enforce line length**: Set IDE/linter max at 120 characters. Break long lines at logical points (after commas, before operators).

8. **Apply spacing rules**:
   - Spaces around `=`, `+=`, `-=`, etc.
   - No space between function name and `(`
   - Space after commas in argument lists
   - Consider operator precedence in spacing (tight for `*`, loose for `+`)

9. **Remove horizontal alignment**: Delete extra whitespace used to align columns. If the field list is too long, split the class.

10. **Always indent scope bodies**: Expand every `if`, `while`, `for`, and function body onto indented lines. Never collapse to single line.

11. **Make dummy scopes visible**: Put the semicolon on its own indented line if an empty loop body is unavoidable.

### Team Formatting Fixes

12. **Establish team rules**: Sit down as a team and agree on: brace placement, indent size, class/variable/method naming, spacing conventions. This should take ~10 minutes.

13. **Encode in tooling**: Configure the IDE formatter, linter, or CI checks to enforce the agreed rules automatically.

14. **Prioritize consistency over preference**: Individual style yields to team consistency. The code should read as though written by one author.

---

## Specific Metrics Reference (from Chapter 5 data)

### File Length Data (Figure 5-1, 7 Java projects, log scale, box height = sigma)

Note: The lines through the boxes show the minimum and maximum file lengths in each project. The box shows sigma/2 above and below the mean (approximately one standard deviation total). The middle of the box is the mean. This is a log scale, so a small difference in vertical position implies a very large difference in absolute size.

| Project       | Average File Size | Typical Range     | Max File Size        |
|---------------|-------------------|-------------------|----------------------|
| JUnit         | ~50 lines         | Most <200         | <500 lines           |
| FitNesse      | ~65 lines         | 40-100+ lines     | ~400 lines           |
| testNG        | ~100 lines        | Wider spread      | ~1000+ lines         |
| Time and Money| ~50 lines         | Most <200         | <500 lines           |
| JDepend       | ~100 lines        | 50-300            | ~500 lines           |
| Ant           | ~200 lines        | Close to half >200| Several thousand     |
| Tomcat        | ~200 lines        | Close to half >200| Several thousand     |

- **Key insight**: FitNesse is close to 50,000 lines of code total, proving it appears to be possible to build significant systems out of files that are typically 200 lines long, with an upper limit of 500.
- **Recommendation**: Although this should not be a hard and fast rule, it should be considered very desirable. Small files are usually easier to understand than large files.

### Line Width Data (Figure 5-2, Java line width distribution, 7 projects)

Y-axis: Number of Lines (percentage, log scale from 0.0000% to 100.0000%). X-axis: Line Width (0 to 150).

- Regularity is impressive, especially right around 45 characters
- Every size from 20 to 60 represents about 1 percent of the total number of lines -- that's 40 percent
- Another 30 percent of lines are less than 10 characters wide
- Significant drop-off above 80 characters (remember this is a log scale, so the linear appearance of the drop-off above 80 characters is really very significant -- programmers clearly prefer short lines)
- **Recommendation**: Strive to keep lines short. The old Hollerith limit of 80 is a bit arbitrary. Lines edging out to 100 or even 120 are acceptable. Beyond that is probably just careless. Uncle Bob personally sets his limit at 120. Do not shrink font to fit 200 characters across the screen.

---

## Self-Improvement Protocol

After each code review using this skill:

1. **Tally violations found** by category (V1-V15). Track which violations recur most frequently in your codebase.

2. **Prioritize by impact**: Vertical distance violations (V4-V7) and file size (V1) tend to have the largest impact on readability. Horizontal issues (V8-V12) are easier to fix with tooling.

3. **Automate what you can**: Encode V2 (blank lines), V8 (line length), V9 (spacing), V10 (alignment), V11 (indentation), V12 (dummy scopes) into your formatter/linter configuration. These should never require manual review.

4. **Focus manual review on**: V1 (file size / SRP), V5 (instance variable placement), V6 (caller-callee ordering), V7 (conceptual affinity grouping), V13 (team consistency), V14 (constant placement), V15 (file naming). These require human judgment about code organization.

5. **Measure over time**: Track average file size and max file size in your project. If files are growing past 200-300 lines regularly, revisit extraction discipline. Track max line widths to ensure the 120-char limit holds.

6. **Revisit team rules periodically**: As the team grows or technology changes, the agreed-upon formatting rules may need updating. But changes should be team decisions, not individual drift.

7. **Remember the fundamental rule**: Code formatting is about communication. Every formatting choice should make the code easier to read, understand, and maintain. When in doubt, ask: "Does this formatting help or hinder the next person who reads this code?"
