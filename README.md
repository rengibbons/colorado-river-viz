# Colorado River Viz

Data visualization and analytics for the Colorado River: flow rates, Lake Powell
and Lake Mead reservoir levels, and snowpack across the Colorado Plateau and
feeder mountain ranges.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install UV](#2-install-uv)
3. [Clone the Repository](#3-clone-the-repository)
4. [Install Python](#4-install-python)
5. [Install Dependencies](#5-install-dependencies)
6. [Install Pre-Commit Hooks](#6-install-pre-commit-hooks)
7. [Launch JupyterLab](#7-launch-jupyterlab)
8. [Explore the Notebook](#8-explore-the-notebook)
9. [Run the Story Notebook](#9-run-the-story-notebook)
10. [Run Tests](#10-run-tests)
11. [Adding New Packages](#11-adding-new-packages)
12. [Project Layout](#12-project-layout)

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

JupyterLab will open in your browser. Navigate to
`notebooks/data_sources_first_visuals.ipynb` and run the cells top-to-bottom
with **Shift + Enter**.

Or simply open the notebook from the left panel of VS Code. Select the kernel from the upper right of the notebook. Choose "Select a Python environment" From the upper right of the notebook and choose colorado_river_viz. (`.venv/bin/python`)

---

## 8. Explore the Notebook

```bash
uv run jupyter lab notebooks/data_sources_first_visuals.ipynb
```

This notebook pulls sample data from the USGS, Bureau of Reclamation, and USDA
NRCS APIs described below and plots each series so you can inspect it.

---

## 9. Run the Story Notebook

`notebooks/colorado_river_story.ipynb` tells the six-chapter Colorado River
story (snowpack, runoff, dams, reservoirs) with a map and a "2026 at a
glance" KPI panel, all built from data cached locally in `data/cache/`
(gitignored — it's rebuilt from public APIs, not checked into git).

**First time:** build the cache from the live APIs. A full history fetch
takes a few minutes:

```bash
uv run python scripts/build_cache.py --mode full
```

**Later, to bring the cache up to date** (only refetches recent days per
series, seconds to a minute):

```bash
uv run python scripts/build_cache.py --mode incremental
```

Then open and run the notebook top-to-bottom:

```bash
uv run jupyter lab notebooks/colorado_river_story.ipynb
```

The notebook's setup cell has a `REFRESH` variable (`"offline"` by default)
that controls whether it refreshes the cache itself before running — set it
to `"incremental"` or `"full"` there instead of running the script
separately if you'd rather do it from within the notebook. With
`REFRESH = "offline"`, the notebook uses only what's already cached and needs
no network access, which is what CI and a normal read-through use.

---

## 10. Run Tests

```bash
uv run pytest
```

Tests live in the `tests/` folder. They verify that the functions in `src/colorado_river_viz/`
work as expected. You don't need to write tests immediately, but the setup is ready when you want to.

---

## 11. Adding New Packages

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

## 12. Project Layout

```
colorado-river-viz/
│
├── data/                   # Data files. Large files are gitignored — store
│   │                       # big datasets here without worrying about git.
│   └── cache/              # The local pipeline cache (gitignored): one parquet
│                           # file per series plus a manifest.json. Rebuilt from
│                           # public APIs with scripts/build_cache.py -- never
│                           # committed, since it's derived, not source data.
│
├── notebooks/              # Jupyter notebooks for exploration and analysis.
│   ├── data_sources_first_visuals.ipynb  # Frozen; see decision 0011.
│   └── colorado_river_story.ipynb        # The six-chapter story notebook.
│
├── scripts/                # Standalone Python scripts for running analyses.
│   └── build_cache.py      # Builds/refreshes data/cache/ from the live APIs.
│
├── src/
│   └── colorado_river_viz/          # The importable Python package.
│       ├── __init__.py     # Makes `from colorado_river_viz import ...` work.
│       ├── data_sources.py # REST clients for USGS, RISE, and AWDB/SNOTEL data.
│       ├── http_session.py # Shared retrying HTTP session per data source.
│       ├── settings.py     # Pipeline settings, read from `CRV_*` env vars.
│       ├── catalog.py      # The registry of every series the story uses.
│       ├── cache.py        # Cache read/write, refresh planning, manifest.
│       ├── published.py    # Parsers for the natural-flow xlsx and Meko txt.
│       ├── snotel.py       # SNOTEL station discovery and batched fetching.
│       ├── water_year.py   # Water-year and day-of-water-year arithmetic.
│       ├── reservoirs.py, reservoir_geometry.py  # Reservoir reference data.
│       ├── constants.py, errors.py, schema.py    # Shared constants/types.
│       ├── metrics/        # Pure metric functions: flow, snow, timing,
│       │                   # trend, natural-flow bridge, reservoir.
│       ├── story_tables.py # One derived table per chapter, built from the cache.
│       ├── narrative.py    # Takeaway sentences built from table rows.
│       └── charts/         # One `build_*()` chart function per chapter, plus
│                           # a shared theme.py.
│
├── tests/                  # Automated tests for the colorado_river_viz package.
│
├── .gitignore              # Tells git which files to ignore (e.g., .venv/, large data files).
├── .pre-commit-config.yaml # Configuration for pre-commit hooks.
├── .python-version         # Pins the Python version to 3.12 for this project.
├── CLAUDE.md               # Guide for working with Claude Code in this project.
├── pyproject.toml          # Project configuration: dependencies, package name, tool settings.
└── uv.lock                 # Exact package versions — always commit this file.
```

**The key idea behind `src/colorado_river_viz/`:** Instead of copying functions between
notebooks or using messy relative imports (`../../utils.py`), any shared code
lives in `src/colorado_river_viz/`. UV installs it as a proper package, so you can write
`from colorado_river_viz import my_function` from anywhere — a notebook, a script, or a
test — and it just works.

> **What is Hatchling?** You'll see `hatchling` mentioned in `pyproject.toml`.
> It's the build tool that makes `src/colorado_river_viz/` installable as a package.
> When you run `uv sync`, UV uses Hatchling behind the scenes to register the
> package so that `import colorado_river_viz` works. You never interact with it directly.
