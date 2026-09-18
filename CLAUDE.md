# Python Project — Claude Guide

## Template Setup (delete this entire section once the new repo is stood up)

This repo is a generic starting point, not a finished project. Before doing real
work in a fresh copy of it:

1. **Rename the package.** Search the repo for `myproject` — it appears in
   `src/myproject/`, `pyproject.toml` (`name` and `packages`), and the imports in
   `tests/test_utils.py`, `scripts/hello_world.py`, and `notebooks/hello_world.ipynb`.
   Rename all of these to match the real project.
2. **Decide on the `hello_world` example.** The example script, notebook, and test
   are a working demo of the package/notebook/test pattern — not required
   functionality. Delete them once you have real code, or keep them as a reference
   if that's useful.
3. **Update the title/description** in `README.md` and this file to describe the
   actual project.
4. **Regenerate `uv.lock`** with `uv sync --all-extras` after any dependency changes.
5. **Delete this entire "Template Setup" section** once the above is done and the
   new repository is up and running. Everything below this section is permanent
   project guidance and should stay.

## Project Layout

```
your-project/
├── data/          # Raw and processed data files (large files are gitignored)
├── notebooks/     # Jupyter notebooks for exploration and analysis
├── scripts/       # Standalone Python scripts for running analyses
├── src/myproject/ # The importable Python package — shared functions go here
└── tests/         # Automated tests for the src/ package
```

## Running Things

```bash
# Launch JupyterLab
uv run jupyter lab

# Run a script
uv run python scripts/hello_world.py

# Run tests
uv run pytest

# Lint and type-check (also run in CI and pre-commit)
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Adding a New Package

When adding a new dependency:

```bash
# 1. Add the package
uv add <package-name>

# 2. Update pre-commit hooks to their latest versions (good practice)
uv run pre-commit autoupdate

# 3. Commit the lock file and any config changes together
git add uv.lock pyproject.toml .pre-commit-config.yaml
git commit -m "add <package-name> dependency"
```

The `uv.lock` file is important — it records the exact version of every package
installed, so the environment is reproducible on any machine.

## Adding a New Function to the Package

1. Add your function to `src/myproject/utils.py` (or a new file in `src/myproject/`)
2. Export it in `src/myproject/__init__.py` so it's importable as `from myproject import my_function`
3. Import it in notebooks or scripts: `from myproject import my_function`

## What Is Hatchling?

Hatchling is the build tool that turns the `src/myproject/` folder into an
installable Python package. When you run `uv sync`, UV uses Hatchling to install
`myproject` into the environment so that `import myproject` works from anywhere —
notebooks, scripts, or tests — without needing to juggle relative paths like
`../../src/myproject/utils.py`. You don't interact with Hatchling directly; it
runs automatically in the background.

## What Is Ruff?

Ruff is a linter — it reads your code and flags style problems or common bugs
before they cause trouble. It runs automatically as a pre-commit hook, so it
checks your code every time you make a git commit. If it finds an issue it can
fix automatically, it fixes it; otherwise it tells you what to change.

## What Is Mypy?

Mypy is a static type checker — it reads the type hints in your code and
verifies they're consistent (e.g. you're not passing a `str` where an `int` is
expected) without running the code. It's configured in `strict` mode, which
requires type hints on all functions. It runs as a pre-commit hook and in CI.

## What Runs in CI?

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:
`ruff check`, `ruff format --check`, `mypy`, and `pytest`. This is the same set
of checks pre-commit runs locally — CI exists so they're also enforced for
anyone who pushes without pre-commit installed, or opens a PR from a fork.

## What Is nbstripout?

Jupyter notebooks save their outputs (plots, printed values, etc.) inside the
notebook file. This is convenient for viewing, but terrible for git: the outputs
are large, they change every time you run a cell, and they cause messy merge
conflicts. `nbstripout` is a pre-commit hook that automatically removes outputs
from notebooks before they are committed. Your notebooks will always open cleanly
and run top-to-bottom — outputs will never be stored in git.

## Python Development Standards

These standards apply to all code in `src/`, `scripts/`, `notebooks/`, and `tests/`.

### Data & Types

- Type hints are mandatory on all function signatures, including return types.
- Prefer `@dataclass(frozen=True, slots=True)` for data — immutable by default.
  Avoid mutable containers as class attributes.
- Use Pydantic only at I/O boundaries (parsing external input, config, API
  payloads) — not as a general-purpose data class replacement.
- Prefer sum types (`Enum`, `Literal`, a union of dataclasses) over
  `Optional`/`None`-heavy APIs where the possible states are known ahead of time.

### Functions & Classes

- Prefer pure, stateless functions over methods. If a class holds no state, it
  should be a module of functions instead of a class.
- Keep functions small and single-purpose. Prefer composition over deep
  inheritance hierarchies.
- Never mutate arguments in place — return new values instead.

### Errors & Control Flow

- Fail fast. No bare `except:`, no silent `except: pass`.
- Raise specific exception types, not generic `Exception` or `ValueError` for
  everything.
- Don't add defensive checks, fallbacks, or validation for scenarios that can't
  actually happen — trust internal code and framework guarantees. Only validate
  at real system boundaries (user input, external APIs).

### Naming & Comments

- Favor descriptive names over comments — a well-named function or variable
  should make a comment unnecessary.
- Keep inline comments to a minimum. Only add one when the *why* is genuinely
  non-obvious (a hidden constraint, a workaround, a subtle invariant) — never to
  restate what the code already says.
- Add docstrings to public API functions/classes. Skip them on private/internal
  helpers where the name and types already say enough.

### Testing

- Use `pytest`. Prefer `@pytest.mark.parametrize` over copy-pasted test
  functions that only vary by input.
- Name tests after the behavior being verified (e.g.
  `test_returns_empty_list_when_input_is_none`), not the implementation detail.
- Prefer fixtures over manual setup/teardown code.

### Idioms

- Use `pathlib.Path`, never `os.path`.
- Use f-strings only — no `%`-formatting or `.format()`.
- Use `enum.Enum` or `Literal` instead of magic strings.
- Never use mutable default arguments (`def f(x=[])`).
- Use the `logging` module instead of `print` for anything beyond a script's own
  direct output.
- Load configuration from environment variables or `pydantic-settings`, not
  hardcoded values.
