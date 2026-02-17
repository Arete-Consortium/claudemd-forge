"""Tests for codebase analyzers."""

from __future__ import annotations

from pathlib import Path

from claudemd_forge.analyzers import run_all
from claudemd_forge.analyzers.commands import CommandAnalyzer
from claudemd_forge.analyzers.domain import DomainAnalyzer
from claudemd_forge.analyzers.language import LanguageAnalyzer
from claudemd_forge.analyzers.patterns import PatternAnalyzer
from claudemd_forge.models import ForgeConfig
from claudemd_forge.scanner import CodebaseScanner


def _scan(path: Path) -> tuple:
    """Helper: scan a directory and return (structure, config)."""
    config = ForgeConfig(root_path=path)
    scanner = CodebaseScanner(config)
    return scanner.scan(), config


class TestLanguageAnalyzer:
    def test_detects_python(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = LanguageAnalyzer().analyze(structure, config)
        assert result.category == "language"
        assert "Python" in str(result.findings.get("languages", {}))

    def test_detects_react_framework(self, tmp_react_project: Path) -> None:
        structure, config = _scan(tmp_react_project)
        result = LanguageAnalyzer().analyze(structure, config)
        frameworks = result.findings.get("frameworks", [])
        assert "react" in frameworks

    def test_detects_npm_package_manager(self, tmp_react_project: Path) -> None:
        # Create a lockfile to detect npm.
        (tmp_react_project / "package-lock.json").write_text("{}")
        structure, config = _scan(tmp_react_project)
        result = LanguageAnalyzer().analyze(structure, config)
        assert "npm" in result.findings.get("package_managers", [])

    def test_section_content_not_empty(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = LanguageAnalyzer().analyze(structure, config)
        assert "## Tech Stack" in result.section_content

    def test_detects_ci_cd(self, tmp_project: Path) -> None:
        workflows = tmp_project / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("on: push")
        structure, config = _scan(tmp_project)
        result = LanguageAnalyzer().analyze(structure, config)
        assert "GitHub Actions" in result.findings.get("ci_cd", [])

    def test_detects_ruff_toolchain(self, tmp_project: Path) -> None:
        """pyproject.toml with [tool.ruff] should detect ruff as linter."""
        pyproject = tmp_project / "pyproject.toml"
        content = pyproject.read_text()
        content += "\n[tool.ruff]\nline-length = 100\n"
        pyproject.write_text(content)
        structure, config = _scan(tmp_project)
        result = LanguageAnalyzer().analyze(structure, config)
        toolchains = result.findings.get("toolchains", {})
        assert "ruff" in toolchains.get("linters", [])


class TestPatternAnalyzer:
    def test_detects_snake_case(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = PatternAnalyzer().analyze(structure, config)
        assert result.category == "patterns"
        assert result.findings.get("naming") == "snake_case"

    def test_detects_double_quotes(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = PatternAnalyzer().analyze(structure, config)
        # Our fixtures use double quotes predominantly.
        assert result.findings.get("quote_style") in ("double", "mixed")

    def test_detects_type_hints(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = PatternAnalyzer().analyze(structure, config)
        assert result.findings.get("type_hints") in ("present", "partial")

    def test_python_primary_ignores_js_camelcase(self, tmp_path: Path) -> None:
        """Python-primary project shouldn't report camelCase from JS files."""
        # Create a mixed project with more Python files.
        (tmp_path / "app.py").write_text(
            "def get_users():\n    pass\n\ndef fetch_data():\n    pass\n"
        )
        (tmp_path / "utils.py").write_text(
            "def parse_config():\n    pass\n\ndef validate_input():\n    pass\n"
        )
        (tmp_path / "helpers.js").write_text(
            "const getUserName = (u) => u.name;\n"
            "const formatDate = (d) => d.toISO();\n"
            "function fetchData() { return null; }\n"
        )
        structure, config = _scan(tmp_path)
        assert structure.primary_language == "Python"
        result = PatternAnalyzer().analyze(structure, config)
        assert result.findings["naming"] == "snake_case"

    def test_python_primary_with_many_ts_files_alphabetically_first(self, tmp_path: Path) -> None:
        """Python files sampled even when TS files sort first alphabetically."""
        # Create TS files in apps/ (sorts before backend/).
        apps = tmp_path / "apps" / "web"
        apps.mkdir(parents=True)
        for i in range(15):
            (apps / f"component{i}.ts").write_text(
                f"const handle{i} = () => null;\nfunction render{i}(): void {{}}\n"
            )
        # Create Python files in backend/.
        backend = tmp_path / "backend"
        backend.mkdir()
        for i in range(20):
            (backend / f"module{i}.py").write_text(
                f"def get_item_{i}():\n    pass\n\ndef process_data_{i}():\n    pass\n"
            )
        structure, config = _scan(tmp_path)
        assert structure.primary_language == "Python"
        result = PatternAnalyzer().analyze(structure, config)
        assert result.findings["naming"] == "snake_case"

    def test_ts_primary_reports_camelcase(self, tmp_path: Path) -> None:
        """TypeScript-primary project should report camelCase."""
        (tmp_path / "index.ts").write_text(
            "const getUserName = (u: User) => u.name;\nfunction fetchData(): void {}\n"
        )
        (tmp_path / "utils.ts").write_text(
            "const formatDate = (d: Date): string => d.toISOString();\n"
        )
        structure, config = _scan(tmp_path)
        assert structure.primary_language == "TypeScript"
        result = PatternAnalyzer().analyze(structure, config)
        assert result.findings["naming"] == "camelCase"

    def test_rust_fn_detected_as_snake_case(self, tmp_path: Path) -> None:
        """Rust project should detect fn as snake_case."""
        (tmp_path / "main.rs").write_text(
            "fn main() {}\nfn get_user_name() -> String { todo!() }\n"
            "fn parse_config() -> Config { todo!() }\n"
        )
        structure, config = _scan(tmp_path)
        result = PatternAnalyzer().analyze(structure, config)
        assert result.findings["naming"] == "snake_case"

    def test_empty_project_returns_no_content(self, tmp_path: Path) -> None:
        structure, config = _scan(tmp_path)
        result = PatternAnalyzer().analyze(structure, config)
        assert result.confidence == 0.0

    def test_section_content_has_heading(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = PatternAnalyzer().analyze(structure, config)
        assert "## Coding Standards" in result.section_content


class TestCommandAnalyzer:
    def test_extracts_npm_scripts(self, tmp_react_project: Path) -> None:
        structure, config = _scan(tmp_react_project)
        result = CommandAnalyzer().analyze(structure, config)
        npm_scripts = result.findings.get("npm_scripts", {})
        assert "dev" in npm_scripts
        assert "test" in npm_scripts

    def test_extracts_makefile_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test:\n\tpytest tests/\n\nbuild:\n\tpython -m build\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        targets = result.findings.get("makefile_targets", {})
        assert "test" in targets
        assert "build" in targets

    def test_extracts_pyproject_scripts(self, tmp_project: Path) -> None:
        # The tmp_project has a pyproject.toml — add pytest to trigger detection.
        pyproject = tmp_project / "pyproject.toml"
        content = pyproject.read_text()
        content += '\n[tool.ruff]\nline-length = 100\n[tool.mypy]\npython_version = "3.11"\n'
        pyproject.write_text(content)
        structure, config = _scan(tmp_project)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "test" in scripts or "lint" in scripts

    def test_detects_poetry_scripts(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.scripts]\nmyapp = "myapp.cli:main"\n'
        )
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "myapp" in scripts

    def test_detects_coverage_config(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.coverage.run]\nsource = ['src']\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "coverage" in scripts

    def test_detects_isort_config(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.isort]\nprofile = 'black'\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "isort" in scripts

    def test_detects_tox_ini(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (tmp_path / "tox.ini").write_text("[tox]\nenvlist = py311\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "tox" in scripts

    def test_detects_tox_in_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.tox]\nlegacy_tox_ini = '[tox]'\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "tox" in scripts

    def test_setup_cfg_pytest_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text("[tool:pytest]\naddopts = -v\n")
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        scripts = result.findings.get("pyproject_scripts", {})
        assert "test" in scripts

    def test_section_content_has_code_block(self, tmp_react_project: Path) -> None:
        structure, config = _scan(tmp_react_project)
        result = CommandAnalyzer().analyze(structure, config)
        assert "```bash" in result.section_content

    def test_empty_project_returns_empty(self, tmp_path: Path) -> None:
        structure, config = _scan(tmp_path)
        result = CommandAnalyzer().analyze(structure, config)
        assert result.section_content == ""


class TestDomainAnalyzer:
    def test_extracts_class_names(self, tmp_project: Path) -> None:
        # Add a file with a class.
        (tmp_project / "src" / "myapp" / "models.py").write_text(
            "class UserProfile:\n    pass\n\nclass OrderHistory:\n    pass\n"
        )
        structure, config = _scan(tmp_project)
        result = DomainAnalyzer().analyze(structure, config)
        classes = result.findings.get("class_names", [])
        assert "UserProfile" in classes
        assert "OrderHistory" in classes

    def test_extracts_readme_terms(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "# My Project\n\nThis uses the ACME Engine and Big Data Framework.\n"
        )
        structure, config = _scan(tmp_path)
        result = DomainAnalyzer().analyze(structure, config)
        terms = result.findings.get("readme_terms", [])
        assert any("ACME" in t for t in terms) or any("Big Data" in t for t in terms)

    def test_readme_terms_whitespace_normalized(self, tmp_path: Path) -> None:
        """Multi-word terms with irregular whitespace should be normalized."""
        (tmp_path / "README.md").write_text(
            "# Title\n\nCheck out  App  Router  and\nSome  Module here.\n"
        )
        structure, config = _scan(tmp_path)
        result = DomainAnalyzer().analyze(structure, config)
        terms = result.findings.get("readme_terms", [])
        # No term should have consecutive spaces.
        for term in terms:
            assert "  " not in term, f"Term has double spaces: {term!r}"

    def test_extracts_api_routes(self, tmp_path: Path) -> None:
        (tmp_path / "routes.py").write_text(
            "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n"
            '@router.get("/users")\ndef get_users(): ...\n\n'
            '@router.post("/users/{id}")\ndef create_user(): ...\n'
        )
        structure, config = _scan(tmp_path)
        result = DomainAnalyzer().analyze(structure, config)
        routes = result.findings.get("api_routes", [])
        assert "/users" in routes

    def test_empty_project(self, tmp_path: Path) -> None:
        structure, config = _scan(tmp_path)
        result = DomainAnalyzer().analyze(structure, config)
        assert result.category == "domain"

    def test_section_content(self, tmp_project: Path) -> None:
        (tmp_project / "src" / "myapp" / "models.py").write_text("class Widget:\n    pass\n")
        structure, config = _scan(tmp_project)
        result = DomainAnalyzer().analyze(structure, config)
        if result.section_content:
            assert "## Domain Context" in result.section_content


class TestRegistry:
    def test_run_all_returns_four_results(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        assert len(results) == 4

    def test_all_categories_present(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        categories = {r.category for r in results}
        assert categories == {"language", "patterns", "commands", "domain"}

    def test_all_valid_analysis_results(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        for r in results:
            assert 0.0 <= r.confidence <= 1.0
            assert r.category
