
## Code change workflow

### Python virtual environment

When a change involves Python (application code, tooling, or running tests against a Python tree), locate a `.venv` directory before running any Python-related commands. Check the repository root and any Python package directory you are working in (for example `backend/`), since the venv may live in either place.

If a `.venv` directory exists, activate it in the same shell session **before** invoking `python`, `pip`, `python -m pip`, test runners (`pytest`, `unittest`), linters, formatters, or other tools installed into that environment.

- **macOS / Linux (bash, zsh):** from the directory that contains `.venv`, run `source .venv/bin/activate`. Example from the repo root if the venv is under `backend/`: `source backend/.venv/bin/activate`.
- **Windows Command Prompt:** `backend\.venv\Scripts\activate.bat` (adjust the path to match where `.venv` lives).
- **Windows PowerShell:** `backend\.venv\Scripts\Activate.ps1` (same path adjustment).

Alternatively, you may call the venv's executables by path without activating—for example `backend/.venv/bin/python -m pytest` or `backend/.venv/bin/pip install -r backend/requirements.txt`—as long as every Python-related command uses that prefix consistently.

After every code change, the agent MUST:

1. **Run tests** — execute the relevant test suite and confirm it passes
2. **Verify output** — check that the feature or fix works as expected (console output, return values, logs)
3. **View console output** — inspect for errors, warnings, or unexpected output
4. **Screenshot affected pages** — when the change touches UI, take a screenshot to visually verify the result

If the change is entirely UI-related and only browser-related code was changed, do not test the web app by running the server unless the user explicitly asks you to do so. Instead, verify whether the web app is already running and notify the user of that status.

### Git commits

When creating commits, use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]
```

- **type** — `feat` (new feature), `fix` (bug fix), `docs`, `style` (formatting only), `refactor`, `test`, `chore` (build, tooling, deps), `perf`, `ci`
- **scope** — optional area of change in parentheses, e.g. `feat(cli):`, `fix(db):`
- **description** — imperative, lowercase, no trailing period; summarize the *why*, not just the *what*
- **body** — optional; use when the subject line alone is not enough context

Examples:

- `feat(web): add experiment run dashboard`
- `fix(analysis): handle missing score artifacts`
- `chore: update pytest in dev dependencies`
- `docs: document conventional commit format in AGENTS.md`

Do not commit unless the user explicitly requests it.

### Code generation quality guardrails

When generating or modifying code, the agent MUST:

1. **Keep the big picture in view** — align local changes with the overall architecture and product intent
2. **Avoid duplication and loose ends** — do not introduce duplicate logic, dead paths, or half-finished integration points
3. **Prioritize reusability** — prefer shared abstractions and existing utilities over one-off implementations
4. **Protect behavior when fixing bugs** — avoid unexpected behavior changes outside the intended fix scope
5. **Prioritize integrity** — preserve data correctness, invariants, and system consistency over speed of implementation
6. **Validate component-level intent** — when adding or removing a component, check for other components with similar function and confirm whether the user intends targeted isolation or a broader change across all similar components

### User-facing UI and design

Whenever you produce code that **affects or changes user-facing components** (for example marketing pages, app shell UI, shared styles, copy, or assets users see), you **must** read **`STYLES.md`** at the repository root and apply layout, typography, colors, and vocabulary **consistent with that document**, unless the user **explicitly overrides** those choices in their request.

### Cadybara API

When making code changes relating to the Cadybara API, consult **`agent-api.md`** for instructions.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
