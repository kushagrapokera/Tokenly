# Den project skills

Two skill families, installed project-only, sharing one source of truth:

| Family | What | Installer |
|---|---|---|
| Clean Code | 16 code-quality checkers from *Clean Code* (Robert C. Martin) | `scripts/install_clean_code_skills.py` |
| UI/UX design | 15 design/frontend skills for the React + Tailwind UI base (`frontend/`) | `scripts/install_ui_skills.py` |

Installed from
[hatlesswizard/clean-code-skills](https://github.com/hatlesswizard/clean-code-skills),
[nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) (MIT),
[pbakaus/impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0), and
[emilkowalski/skills](https://github.com/emilkowalski/skills) (MIT).

## Where they live

The single source of truth is `skills/<name>/SKILL.md`. Every tool
we use finds them there through a symlink:

| Tool | Path it reads |
|---|---|
| Claude Code | `.claude/skills/` (symlink to `../skills`) |
| opencode | `.claude/skills/` (Claude-compatible path) |
| Cline | `.cline/skills/` (relative symlink to `../skills`) |
| Codex | `.agents/skills/` (relative symlink to `../skills`) |

The three symlinks are machine-local and are not tracked, so a fresh
checkout needs them recreated before the tools find anything:

```bash
mkdir -p .claude .cline .agents
ln -s ../skills .claude/skills
ln -s ../skills .cline/skills
ln -s ../skills .agents/skills
```

Cline also reads `.claude/skills/` directly, but `.cline/skills/` is its
documented *recommended* path, so both are exposed and Cline finds
the skills whichever path its build scans.

## The Clean Code skills

| Skill | Chapter | Covers |
|---|---|---|
| `clean-code-ch01-clean-code` | 1: Clean Code | readability, minimal dependencies, Boy Scout Rule |
| `clean-code-ch02-meaningful-names` | 2: Meaningful Names | intention-revealing, searchable, no disinformation |
| `clean-code-ch03-functions` | 3: Functions | size, single responsibility, argument count, side effects |
| `clean-code-ch04-comments` | 4: Comments | redundant, misleading, commented-out code |
| `clean-code-ch05-formatting` | 5: Formatting | vertical and horizontal structure |
| `clean-code-ch06-objects-and-data-structures` | 6: Objects and Data Structures | data abstraction, Law of Demeter |
| `clean-code-ch07-error-handling` | 7: Error Handling | try/catch, exception context, no silent failures |
| `clean-code-ch08-boundaries` | 8: Boundaries | wrapping third-party code, boundary interfaces |
| `clean-code-ch09-unit-tests` | 9: Unit Tests | TDD laws, FIRST principles, one concept per test |
| `clean-code-ch10-classes` | 10: Classes | SRP, cohesion, encapsulation, Open/Closed |
| `clean-code-ch11-systems` | 11: Systems | construction/use separation, dependency injection |
| `clean-code-ch12-emergence` | 12: Emergence | the 4 rules of Simple Design |
| `clean-code-ch13-concurrency` | 13: Concurrency | SRP for threading, data scope, shut-down correctness |
| `clean-code-ch14-successive-refinement` | 14: Successive Refinement | incremental refactoring discipline |
| `clean-code-ch17-smells-and-heuristics` | 17: Smells and Heuristics | the full catalog of 66 code smells |
| `clean-code-appa-concurrency-ii` | Appendix A | deadlock conditions, thread-safety of libraries |

## Deliberately excluded

Two upstream skills are language-bound rather than about code quality, so
they are dropped for this Python/FastAPI project. The installer enforces
this via `EXCLUDED_SKILL_NAMES`, so they cannot come back on a refresh:

| Not installed | Why |
|---|---|
| `clean-code-ch15-junit-internals` | the chapter *is* the JUnit test class |
| `clean-code-ch16-refactoring-serialdate` | a walkthrough refactoring a Java class |

The concurrency skills (`ch13`, `appA`) are **kept on purpose** — their
rules are language-agnostic, `appA` even covers the GIL, and Den runs an
async web server plus queued test runs.

## UI/UX design skills

Selected for Den's frontend base (React 18 + Vite + Tailwind +
material-tailwind, see `frontend/` and `ui.md`). 15 of the 22 skills the
three upstreams offer:

| Skill | Upstream | Covers |
|---|---|---|
| `ui-ux-pro-max` | ui-ux-pro-max-skill | searchable design intelligence: styles, palettes, font pairings, UX guidelines, icon/chart/stack data |
| `ui-styling` | ui-ux-pro-max-skill | Tailwind utility styling, accessible components, responsive layouts, themes, dark mode |
| `design-system` | ui-ux-pro-max-skill | design tokens (primitive→semantic→component), CSS variables, spacing/typography scales |
| `impeccable` | impeccable | design critique/audit/polish for dashboards, app shells, components; accessibility, motion, theming; includes the detector CLI |
| `emil-design-eng` | emilkowalski/skills | Emil Kowalski's UI polish and component-design philosophy |
| `animate` | emilkowalski/skills | building a web animation from scratch with the right curve/duration/properties |
| `review-animations` | emilkowalski/skills | strict review of animation code against a high craft bar |
| `improve-animations` | emilkowalski/skills | whole-codebase motion audit → prioritized implementation plans (read-only) |
| `find-animation-opportunities` | emilkowalski/skills | where motion would genuinely help, and what not to animate (read-only) |
| `animation-vocabulary` | emilkowalski/skills | reverse-lookup glossary of motion effect names |
| `break-ui` | emilkowalski/skills | stress-test UI with worst-case data (long names, huge counts, empty lists) |
| `pick-ui-library` | emilkowalski/skills | curated library picks for a task (manual invocation) |
| `prototype` | emilkowalski/skills | build multiple UI variants behind a live picker (manual invocation) |
| `mobile-native` | emilkowalski/skills | make the web app feel native on phones (tap states, 100vh, safe areas) |
| `apple-design` | emilkowalski/skills | Apple's interface and fluid-motion principles translated for the web |

### Deliberately not selected

| Not installed | Why |
|---|---|
| `banner-design`, `brand`, `design`, `slides` (ui-ux-pro-max-skill) | marketing/asset generation (logos, ads, social, presentations), not product UI |
| `write-swift` (emilkowalski) | Swift language skill — Den is Python + React |
| `animate-expo` (emilkowalski) | React Native/Expo — Den's UI is web |
| `ask-sonner` (emilkowalski) | Sonner toast library — Den does not use it |

The Clean Code installer enforces its own exclusions; this family's
selection lives in `UPSTREAM_SKILL_SOURCES` /
`NOT_SELECTED` (`tests/test_ui_skills_install.py`), so a drift between
docs, installer, and disk fails the test suite.

One deviation on purpose: `ui-styling` upstream ships a 5.5 MB
`canvas-fonts/` directory for canvas poster features Den never adopted,
so the installer strips it on copy (`STRIPPED_SUBPATHS`). Refresh behaves
the same as first install.

## Frontend vs shared scope (no backend/ move needed)

All 31 skills live in ONE flat store (`skills/`). Nothing is
renamed and no directories move — the tools tell the families apart
from one scope sentence each installer appends to the description:

| Family | Scope tag in `description:` | Meaning |
|---|---|---|
| Clean Code (`clean-code-*`, 16) | `Scope: shared - applies to backend and frontend code.` | language-agnostic, fires anywhere |
| UI/UX design (15) | `Scope: frontend-only - use only for files under frontend/.` | React/Tailwind/animation, fires only under `frontend/` |

Example (after install):

```
clean-code-ch03-functions: "... command-query separation, error handling,
  and DRY. Scope: shared - applies to backend and frontend code."
break-ui: "... For visual design critique use emil-design-eng; for motion
  use review-animations. Scope: frontend-only - use only for files under
  frontend/."
```

Rules: both families share the 1024-character Cline `description` limit
(worst today is `impeccable` at ~954 tagged); re-running either
installer never doubles the tag and never corrupts already-quoted
descriptions. Scope logic lives in `scripts/skill_scopes.py`
(helpers + `verify_scope_tags`); `tests/test_skill_scopes.py` covers it.

## Maintaining

```bash
python scripts/install_clean_code_skills.py            # refresh Clean Code
python scripts/install_clean_code_skills.py --check    # verify, change nothing
python scripts/install_ui_skills.py                    # refresh UI/UX design
python scripts/install_ui_skills.py --check            # verify, change nothing
```

Both installers **merge** into `skills/` — neither wipes the
other's skill families. `tests/test_skills_install.py`,
`tests/test_ui_skills_install.py`, and `tests/test_skill_scopes.py`
cover them.
