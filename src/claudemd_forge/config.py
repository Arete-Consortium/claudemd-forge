"""Configuration constants and defaults for ClaudeMD Forge."""

from __future__ import annotations

DEFAULT_EXCLUDE_DIRS: list[str] = [
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "target",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".eggs",
    "*.egg-info",
    ".idea",
    ".vscode",
    ".DS_Store",
    ".coverage",
    "htmlcov",
    "*.pyc",
    "*.pyo",
]

# File-level patterns to exclude from the architecture tree display.
ARCHITECTURE_EXCLUDE_FILES: set[str] = {
    "*.db",
    "*.db-journal",
    "*.db-shm",
    "*.db-wal",
    ".coverage",
    ".env",
    ".envrc",
}

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".scala": "Scala",
    ".zig": "Zig",
    ".lua": "Lua",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".clj": "Clojure",
    ".r": "R",
    ".R": "R",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

# Files that indicate a framework is present.
# Format: "framework_name": ["indicator_file_or_pattern", ...]
# Indicators with ":" mean "file contains string" (e.g., "package.json:react").
FRAMEWORK_INDICATORS: dict[str, list[str]] = {
    "react": ["package.json:react", "src/App.tsx", "src/App.jsx"],
    "nextjs": ["next.config.js", "next.config.ts", "next.config.mjs"],
    "vue": ["package.json:vue", "src/App.vue"],
    "svelte": ["package.json:svelte", "svelte.config.js"],
    "angular": ["angular.json", "package.json:@angular/core"],
    "fastapi": ["requirements.txt:fastapi", "pyproject.toml:fastapi"],
    "django": ["manage.py", "settings.py", "django"],
    "flask": ["requirements.txt:flask", "pyproject.toml:flask"],
    "express": ["package.json:express"],
    "nestjs": ["package.json:@nestjs/core"],
    "rust": ["Cargo.toml"],
    "bevy": ["Cargo.toml:bevy"],
    "go": ["go.mod"],
    "spring": ["pom.xml:spring", "build.gradle:spring"],
}

# Recommended sections in CLAUDE.md, in order.
SECTION_ORDER: list[str] = [
    "header",
    "project_overview",
    "current_state",
    "architecture",
    "tech_stack",
    "coding_standards",
    "common_commands",
    "anti_patterns",
    "dependencies",
    "domain_context",
    "git_conventions",
]

# Config languages to exclude when determining "primary language".
CONFIG_LANGUAGES: set[str] = {
    "HTML",
    "CSS",
    "SCSS",
    "SASS",
    "LESS",
    "SQL",
    "Shell",
    "Markdown",
}
