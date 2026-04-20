"""Tests for codebase analyzers."""

from __future__ import annotations

from pathlib import Path

from anchormd.analyzers import run_all
from anchormd.analyzers.commands import CommandAnalyzer
from anchormd.analyzers.domain import DomainAnalyzer
from anchormd.analyzers.language import LanguageAnalyzer
from anchormd.analyzers.opsec import OpsecAnalyzer
from anchormd.analyzers.patterns import PatternAnalyzer
from anchormd.analyzers.skills import SkillsAnalyzer
from anchormd.models import ForgeConfig
from anchormd.scanner import CodebaseScanner


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
    def test_run_all_returns_eight_results(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        assert len(results) == 8

    def test_all_categories_present(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        categories = {r.category for r in results}
        assert categories == {
            "language",
            "patterns",
            "commands",
            "domain",
            "skills",
            "tech_debt",
            "github",
            "opsec",
        }

    def test_all_valid_analysis_results(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        results = run_all(structure, config)
        for r in results:
            assert 0.0 <= r.confidence <= 1.0
            assert r.category


class TestSkillsAnalyzer:
    def test_returns_skills_category(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer().analyze(structure, config)
        assert result.category == "skills"
        assert 0.0 <= result.confidence <= 1.0

    def test_detects_installed_skills(self, tmp_project: Path, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "code-reviewer").mkdir()
        (skills_dir / "code-reviewer" / "SKILL.md").write_text("---\nname: code-reviewer\n---")
        (skills_dir / "composite-scorer").mkdir()
        (skills_dir / "composite-scorer" / "SKILL.md").write_text(
            "---\nname: composite-scorer\n---"
        )

        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer(skills_dir=skills_dir).analyze(structure, config)
        installed = result.findings["installed_skills"]
        assert "code-reviewer" in installed
        assert "composite-scorer" in installed
        assert result.findings["installed_count"] == 2

    def test_empty_skills_dir(self, tmp_project: Path, tmp_path: Path) -> None:
        skills_dir = tmp_path / "empty_skills"
        skills_dir.mkdir()
        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer(skills_dir=skills_dir).analyze(structure, config)
        assert result.findings["installed_skills"] == []

    def test_nonexistent_skills_dir(self, tmp_project: Path, tmp_path: Path) -> None:
        skills_dir = tmp_path / "no_such_dir"
        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer(skills_dir=skills_dir).analyze(structure, config)
        assert result.findings["installed_skills"] == []

    def test_detects_project_skills(self, tmp_project: Path, tmp_path: Path) -> None:
        claude_dir = tmp_project / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        (claude_dir / "deploy.md").write_text("Deploy command")

        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer(skills_dir=tmp_path / "none").analyze(structure, config)
        assert "commands/deploy" in result.findings["project_skills"]

    def test_recommends_bundles_for_fastapi(self, tmp_project: Path, tmp_path: Path) -> None:
        (tmp_project / "pyproject.toml").write_text('[project]\nname="test"\n[tool.ruff]\n')
        (tmp_project / "requirements.txt").write_text("fastapi\nuvicorn\n")

        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer(skills_dir=tmp_path / "none").analyze(structure, config)
        bundles = result.findings["recommended_bundles"]
        assert "api-integration" in bundles or "full-stack-dev" in bundles

    def test_section_content_includes_heading(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = SkillsAnalyzer().analyze(structure, config)
        if result.section_content:
            assert "## AI Skills" in result.section_content


class TestOpsecAnalyzer:
    def test_clean_project_scores_100(self, tmp_project: Path) -> None:
        structure, config = _scan(tmp_project)
        result = OpsecAnalyzer().analyze(structure, config)
        assert result.category == "opsec"
        assert result.findings["score"] == 100
        assert result.findings["total_findings"] == 0

    def test_detects_local_home_path(self, tmp_path: Path) -> None:
        src = tmp_path / "deploy.sh"
        src.write_text('FLYCTL="/home/james/.fly/bin/flyctl"\n')
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        assert result.findings["total_findings"] > 0
        found = result.findings["findings"]
        assert any(f["category"] == "local_paths" for f in found)

    def test_detects_api_key(self, tmp_path: Path) -> None:
        src = tmp_path / "config.py"
        src.write_text('API_KEY = "sk-ant-abc123defghijklmnopqrstuvwxyz"\n')
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        found = result.findings["findings"]
        assert any(f["category"] == "secrets" for f in found)
        assert any(f["severity"] == "critical" for f in found)

    def test_skips_env_example(self, tmp_path: Path) -> None:
        src = tmp_path / ".env.example"
        src.write_text("API_KEY=sk-ant-your-key-here\n")
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        secrets = [f for f in result.findings["findings"] if f["category"] == "secrets"]
        assert len(secrets) == 0

    def test_skips_grep_patterns(self, tmp_path: Path) -> None:
        src = tmp_path / "check.sh"
        src.write_text('#!/bin/bash\ngrep -rn "sk-ant-" --include="*.py" .\n')
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        secrets = [f for f in result.findings["findings"] if f["category"] == "secrets"]
        assert len(secrets) == 0

    def test_detects_strategy_doc(self, tmp_path: Path) -> None:
        (tmp_path / "outreach.md").write_text("# Sales strategy\n")
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        found = result.findings["findings"]
        assert any(f["category"] == "strategy_docs" for f in found)

    def test_detects_tracked_env(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=foo\n")
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        found = result.findings["findings"]
        assert any(f["category"] == "credentials" and "Real .env" in f["message"] for f in found)

    def test_detects_private_key(self, tmp_path: Path) -> None:
        (tmp_path / "key.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\nfoo\n")
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        found = result.findings["findings"]
        assert any(f["message"] == "Private key material found in tracked file" for f in found)

    def test_detects_db_connection_string(self, tmp_path: Path) -> None:
        (tmp_path / "config.py").write_text('DB_URL = "postgres://admin:s3cret@db.host:5432/app"\n')
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        found = result.findings["findings"]
        assert any(f["category"] == "credentials" for f in found)

    def test_score_decreases_with_findings(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text(
            'KEY = "sk-ant-reallylongfakeapikeyvalue1234567890"\n'
            'FLYCTL = "/home/dev/.fly/bin/flyctl"\n'
        )
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        assert result.findings["score"] < 100

    def test_confidence_scales_with_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("print('hello')\n")
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        assert 0.0 < result.confidence <= 1.0

    def test_skips_placeholder_passwords(self, tmp_path: Path) -> None:
        (tmp_path / "config.py").write_text('password = "changeme"\n')
        structure, config = _scan(tmp_path)
        result = OpsecAnalyzer().analyze(structure, config)
        creds = [f for f in result.findings["findings"] if f["category"] == "credentials"]
        assert len(creds) == 0
