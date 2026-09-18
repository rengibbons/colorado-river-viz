# Python Project Template

A Python project template for reproducible, easy-to-maintain projects.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install UV](#2-install-uv)
3. [Clone the Repository](#3-clone-the-repository)
4. [Install Python](#4-install-python)
5. [Install Dependencies](#5-install-dependencies)
6. [Install Pre-Commit Hooks](#6-install-pre-commit-hooks)
7. [Launch JupyterLab](#7-launch-jupyterlab)
8. [Run the Example Script](#8-run-the-example-script)
9. [Run Tests](#9-run-tests)
10. [Adding New Packages](#10-adding-new-packages)
11. [Project Layout](#11-project-layout)

---

## 1. Prerequisites

You need **Homebrew**, a package manager for macOS. Open the **Terminal** app and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts. When it finishes, close and reopen Terminal.

> **What is Homebrew?** It's the standard way to install developer tools on a Mac —
> think of it like an App Store for command-line software.

---

## 2. Install UV

UV is the tool that manages your Python environment and packages for this project.
Install it with Homebrew:

```bash
brew install uv
```

Verify it worked:

```bash
uv --version
```

You should see something like `uv 0.x.x`.

> **What is UV?** UV replaces older tools like `pip` and `conda`. It's fast,
> reliable, and keeps your project's packages isolated from the rest of your Mac.

---

## 3. Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

Replace `<your-username>` and `<your-repo-name>` with your actual GitHub username and repository name.

---

## 4. Install Python

UV manages Python versions for you. This project requires Python 3.12. Install it with:

```bash
uv python install 3.12
```

UV will use the `.python-version` file in this project to automatically select Python 3.12
whenever you run a `uv` command inside this folder.

---

## 5. Install Dependencies

Install all packages (NumPy, pandas, SciPy, Matplotlib, JupyterLab, and development tools):

```bash
uv sync --all-extras
```

This creates a `.venv/` folder inside the project with everything installed. You
never need to activate it manually — `uv run` handles that automatically.

> UV also creates a `uv.lock` file. This file records the exact version of every
> package installed, so the environment is perfectly reproducible on any machine.
> **Commit `uv.lock` to git whenever it changes.**

---

## 6. Install Pre-Commit Hooks

Pre-commit hooks are small checks that run automatically every time you make a
git commit. They catch problems before they land in your repository.

Install them with:

```bash
uv run pre-commit install
```

You should see: `pre-commit installed at .git/hooks/pre-commit`

That's it — the hooks will now run silently in the background every time you commit.

**What do the hooks do?**

| Hook | What it does |
|---|---|
| **ruff** | Checks Python code for style issues and common bugs. Fixes most problems automatically. |
| **nbstripout** | Removes outputs from Jupyter notebooks before they're committed. This keeps git diffs clean and prevents giant merge conflicts. Your notebooks will always open without stale outputs from a previous run. |
| **trailing-whitespace** | Removes invisible trailing spaces at the end of lines. |
| **end-of-file-fixer** | Ensures every file ends with a newline (a Unix convention). |

> **A note on nbstripout:** When you commit a notebook, the outputs (plots,
> printed numbers) are automatically stripped. The notebook file stored in git
> will be clean and runnable, but won't show old outputs. This is the right
> behavior — outputs are always generated fresh by running the notebook.

---

## 7. Launch JupyterLab

```bash
uv run jupyter lab
```

JupyterLab will open in your browser. Navigate to `notebooks/hello_world.ipynb`
and run the cells top-to-bottom with **Shift + Enter**.

Or simply open the notebook from the left panel of VS Code. Select the kernel from the upper right of the notebook. Choose "Select a Python environment" From the upper right of the notebook and choose myproject. (`.venv/bin/python`)

---

## 8. Run the Example Script

```bash
uv run python scripts/hello_world.py
```

This imports a function from the `myproject` package, generates some sample data,
and saves a histogram to `hello_world.png`.

---

## 9. Run Tests

```bash
uv run pytest
```

Tests live in the `tests/` folder. They verify that the functions in `src/myproject/`
work as expected. You don't need to write tests immediately, but the setup is ready when you want to.

---

## 10. Adding New Packages

When you want to use a new Python package (e.g., `seaborn`):

**Step 1 — Add the package:**
```bash
uv add seaborn
```

UV will install the package, update `pyproject.toml`, and update `uv.lock`.

**Step 2 — Update pre-commit hooks** (good practice after changing dependencies):
```bash
uv run pre-commit autoupdate
```

This updates the pre-commit hook versions to stay current.

**Step 3 — Commit the changes together:**
```bash
git add uv.lock pyproject.toml .pre-commit-config.yaml
git commit -m "add seaborn dependency"
```

Always commit `uv.lock` when it changes. Anyone who clones the repo will then
get the exact same package versions.

---

## 11. Project Layout

```
your-project/
│
├── data/                   # Data files. Large files are gitignored — store
│                           # big datasets here without worrying about git.
│
├── notebooks/              # Jupyter notebooks for exploration and analysis.
│   └── hello_world.ipynb
│
├── scripts/                # Standalone Python scripts for running analyses.
│   └── hello_world.py
│
├── src/
│   └── myproject/          # The importable Python package.
│       ├── __init__.py     # Makes `from myproject import ...` work.
│       └── utils.py        # Shared functions used across notebooks and scripts.
│
├── tests/                  # Automated tests for the myproject package.
│   └── test_utils.py
│
├── .gitignore              # Tells git which files to ignore (e.g., .venv/, large data files).
├── .pre-commit-config.yaml # Configuration for pre-commit hooks.
├── .python-version         # Pins the Python version to 3.12 for this project.
├── CLAUDE.md               # Guide for working with Claude Code in this project.
├── pyproject.toml          # Project configuration: dependencies, package name, tool settings.
└── uv.lock                 # Exact package versions — always commit this file.
```

**The key idea behind `src/myproject/`:** Instead of copying functions between
notebooks or using messy relative imports (`../../utils.py`), any shared code
lives in `src/myproject/`. UV installs it as a proper package, so you can write
`from myproject import my_function` from anywhere — a notebook, a script, or a
test — and it just works.

> **What is Hatchling?** You'll see `hatchling` mentioned in `pyproject.toml`.
> It's the build tool that makes `src/myproject/` installable as a package.
> When you run `uv sync`, UV uses Hatchling behind the scenes to register the
> package so that `import myproject` works. You never interact with it directly.
