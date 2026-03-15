"""Shared test fixtures for AnchorMD."""

from __future__ import annotations

from pathlib import Path

import pytest

from anchormd.models import ForgeConfig


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal Python project structure in a temp directory."""
    # Python source files
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('__version__ = "0.1.0"\n')
    (src / "main.py").write_text(
        'def main() -> None:\n    print("hello")\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    (src / "utils.py").write_text(
        "from pathlib import Path\n\n\ndef read_file(p: Path) -> str:\n"
        '    """Read a file and return contents."""\n'
        "    return p.read_text()\n"
    )

    # Tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_main.py").write_text(
        "from myapp.main import main\n\n\ndef test_main():\n    main()\n"
    )

    # Config files
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["fastapi>=0.100", "pydantic>=2.0"]\n\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=7.0", "ruff>=0.1.0"]\n'
    )
    (tmp_path / ".gitignore").write_text("__pycache__/\n.venv/\n")

    return tmp_path


@pytest.fixture
def tmp_react_project(tmp_path: Path) -> Path:
    """Create a minimal React/TypeScript project structure."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text(
        'import React from "react";\n\n'
        "export const App: React.FC = () => {\n"
        "  return <div>Hello</div>;\n"
        "};\n"
    )
    (src / "index.ts").write_text('export { App } from "./App";\n')
    (src / "utils.ts").write_text(
        "export const formatDate = (d: Date): string => d.toISOString();\n"
    )

    (tmp_path / "package.json").write_text(
        "{\n"
        '  "name": "my-react-app",\n'
        '  "version": "1.0.0",\n'
        '  "scripts": {\n'
        '    "dev": "vite",\n'
        '    "build": "tsc && vite build",\n'
        '    "test": "vitest",\n'
        '    "lint": "eslint src/"\n'
        "  },\n"
        '  "dependencies": {\n'
        '    "react": "^18.2.0",\n'
        '    "react-dom": "^18.2.0"\n'
        "  },\n"
        '  "devDependencies": {\n'
        '    "typescript": "^5.0.0",\n'
        '    "vite": "^5.0.0",\n'
        '    "vitest": "^1.0.0",\n'
        '    "eslint": "^8.0.0"\n'
        "  }\n"
        "}\n"
    )
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}\n')

    return tmp_path


@pytest.fixture
def sample_config(tmp_path: Path) -> ForgeConfig:
    """Return a ForgeConfig with sensible defaults pointing at tmp_path."""
    return ForgeConfig(root_path=tmp_path)
