# Den — development rules

These rules apply to every prompt and every file in this project.

## Code organization
1. Create a separate file/module for each distinct concern — services,
   logging, config, routes, utilities, etc. Code must stay readable:
   never pile everything into one file.

## Reusability
2. Use and maintain reusable components whenever and wherever possible.
   If the same logic is needed twice, extract it once and reuse it.

## Error handling
3. Write proper error handling for each and every possible error —
   dedicated error definitions and clear messages. No silent failures.

## Logging
4. Perform logging whenever and wherever possible: every significant
   operation gets logged with an appropriate level.

## Testing
5. Perform unit, integration, and smoke testing after each and every
   phase before it is considered done.

## Naming
6. Follow proper variable and function naming conventions — names must
   be easy to read and understand.
7. Use a good, easy-to-understand file naming convention.

## Project structure
- One top-level folder per concern (Spring-style): config/, errors/,
  logging_setup/, routes/, services/, templates/, static/, tests/.
  Entry point is main.py at the project root.
- Every new concern gets its own folder (e.g. sandboxes/ ),
  never one growing dump file.
- Never name a folder after a Python stdlib module — hence
  logging_setup/, not logging

## Performance work
- Read [`LESSONS.md`](LESSONS.md) before optimizing anything. The short
  version: profile first, separate fixed per-run cost from variable cost, and
  confirm the change targets the largest number in the table. Parallelism is
  rarely the answer — on this project it was worth 43 ms, while deleting
  redundant work was worth 742 ms.
- Never quote a performance figure that was not measured. Numbers in
  `parallelism.md` are labelled measured or projected; keep it that way.

## Clean Code skills (installed for this project)
`.claude/skills/` holds 16 code-quality checkers derived from *Clean Code*
(Robert C. Martin), one per chapter, plus Appendix A. They are installed
project-only (no global installs) and shared with every tool we use:

| Tool | Reads skills from |
|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` (native) |
| opencode | `.claude/skills/<name>/SKILL.md` |
| Cline | `.cline/skills/<name>/SKILL.md` (symlink to `.claude/skills`) |
| Codex | `.agents/skills/<name>/SKILL.md` (symlink to `.claude/skills`) |

Cline reads `.claude/skills/` too, but `.cline/skills/` is its documented
recommended path, so the installer exposes that symlink as well.

Use them: before finishing a code change, load the skill matching the
area you touched (naming -> ch02, functions -> ch03, error handling ->
ch07, tests -> ch09, smells -> ch17) and fix what it reports.
`skills/README.md` is the index. Skills load on demand, so nothing is
paid for until invoked.

Maintain with `python scripts/install_clean_code_skills.py` (re-clone
upstream and refresh) or `--check` to verify the install.

