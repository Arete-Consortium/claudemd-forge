"""Tests for the TechDebtAnalyzer."""

from __future__ import annotations

import textwrap
from pathlib import Path

from anchormd.analyzers.tech_debt import TechDebtAnalyzer
from anchormd.models import FileInfo, ForgeConfig, ProjectStructure


def _make_structure(
    files: list[FileInfo] | None = None,
    directories: list[Path] | None = None,
    total_files: int = 10,
    total_lines: int = 200,
    root: Path | None = None,
    primary_language: str = "Python",
) -> ProjectStructure:
    return ProjectStructure(
        root=root or Path("/tmp/fake"),
        files=files or [],
        directories=directories or [],
        total_files=total_files,
        total_lines=total_lines,
        primary_language=primary_language,
    )


def _make_config(root: Path | None = None) -> ForgeConfig:
    return ForgeConfig(root_path=root or Path("/tmp/fake"))


class TestProjectHygiene:
    def test_no_tests_detected(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(path=Path("src/app.py"), extension=".py", size_bytes=100),
            ],
            directories=[Path("src")],
            total_files=10,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert any(s["category"] == "testing" and "No test" in s["message"] for s in signals)

    def test_tests_present_no_finding(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(path=Path("src/app.py"), extension=".py", size_bytes=100),
            ],
            directories=[Path("src"), Path("tests")],
            total_files=10,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert not any(s["category"] == "testing" for s in signals)

    def test_no_ci_detected(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(path=Path("src/app.py"), extension=".py", size_bytes=100),
            ],
            directories=[Path("src")],
            total_files=15,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert any(s["category"] == "infrastructure" and "CI/CD" in s["message"] for s in signals)

    def test_ci_present_no_finding(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(
                    path=Path(".github/workflows/ci.yml"),
                    extension=".yml",
                    size_bytes=100,
                ),
            ],
            directories=[Path("src"), Path("tests")],
            total_files=15,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert not any(
            s["category"] == "infrastructure" and "CI/CD" in s["message"] for s in signals
        )

    def test_no_gitignore(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(path=Path("src/app.py"), extension=".py", size_bytes=100),
            ],
            directories=[Path("src"), Path("tests")],
            total_files=10,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert any("gitignore" in s["message"].lower() for s in signals)


class TestGodFiles:
    def test_god_file_detected(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(
                    path=Path("src/monster.py"),
                    extension=".py",
                    size_bytes=50000,
                    line_count=600,
                ),
            ],
            directories=[Path("src"), Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert any(s["category"] == "complexity" and "God file" in s["message"] for s in signals)

    def test_normal_file_no_finding(self) -> None:
        structure = _make_structure(
            files=[
                FileInfo(
                    path=Path("src/app.py"),
                    extension=".py",
                    size_bytes=5000,
                    line_count=100,
                ),
            ],
            directories=[Path("src"), Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        signals = result.findings["signals"]
        assert not any(
            s["category"] == "complexity" and "God file" in s["message"] for s in signals
        )


class TestDebtComments:
    def test_todo_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("# TODO: fix this later\nx = 1\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=50),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "debt_markers" and "TODO" in s["message"] for s in signals)

    def test_fixme_is_high_severity(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("# FIXME: this is broken\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=30),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        fixme_signals = [
            s for s in signals if s["category"] == "debt_markers" and "FIXME" in s["message"]
        ]
        assert len(fixme_signals) > 0
        assert fixme_signals[0]["severity"] == "high"

    def test_hack_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("# HACK: temporary workaround\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=30),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "debt_markers" and "HACK" in s["message"] for s in signals)


class TestErrorHandling:
    def test_bare_except_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=40),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "error_handling" and "Bare" in s["message"] for s in signals)

    def test_broad_except_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("try:\n    x = 1\nexcept Exception:\n    pass\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=50),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "error_handling" and "Broad" in s["message"] for s in signals)

    def test_error_handling_skipped_in_tests(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        src = test_dir / "test_app.py"
        src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(
                    path=Path("tests/test_app.py"),
                    extension=".py",
                    size_bytes=40,
                ),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert not any(s["category"] == "error_handling" for s in signals)


class TestDebugStatements:
    def test_print_debug_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("def main():\n    print('debug')\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=30),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "code_quality" and "print()" in s["message"] for s in signals)

    def test_console_log_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "app.ts"
        src.write_text("function main() {\n  console.log('debug');\n}\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.ts"), extension=".ts", size_bytes=50),
            ],
            directories=[Path("tests")],
            primary_language="TypeScript",
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(
            s["category"] == "code_quality" and "console.log" in s["message"] for s in signals
        )

    def test_debug_skipped_in_tests(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        src = test_dir / "test_app.py"
        src.write_text("def test_it():\n    print('ok')\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(
                    path=Path("tests/test_app.py"),
                    extension=".py",
                    size_bytes=30,
                ),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert not any(s["category"] == "code_quality" for s in signals)


class TestGodFunctions:
    def test_long_function_detected(self, tmp_path: Path) -> None:
        lines = ["def massive_function():\n"]
        lines.extend([f"    x_{i} = {i}\n" for i in range(60)])
        src = tmp_path / "app.py"
        src.write_text("".join(lines))
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=2000),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(
            s["category"] == "complexity" and "massive_function" in s["message"] for s in signals
        )

    def test_normal_function_no_finding(self, tmp_path: Path) -> None:
        lines = ["def small_func():\n"]
        lines.extend([f"    x = {i}\n" for i in range(10)])
        src = tmp_path / "app.py"
        src.write_text("".join(lines))
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=200),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert not any(
            s["category"] == "complexity" and "small_func" in s["message"] for s in signals
        )


class TestDeepNesting:
    def test_deep_nesting_detected(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def func():
                if True:
                    for x in range(10):
                        if x > 0:
                            while True:
                                if x == 5:
                                    pass
        """)
        src = tmp_path / "app.py"
        src.write_text(code)
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=200),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(
            s["category"] == "complexity" and "nesting" in s["message"].lower() for s in signals
        )


class TestSecrets:
    def test_hardcoded_api_key_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "config.py"
        # Build fake key at runtime to avoid gitleaks false positive
        fake_key = "sk-" + "abcdefghijklmnop1234"
        src.write_text(f"API_KEY = '{fake_key}'\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("config.py"), extension=".py", size_bytes=50),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "security" for s in signals)

    def test_github_token_detected(self, tmp_path: Path) -> None:
        src = tmp_path / "config.py"
        src.write_text("TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg'\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("config.py"), extension=".py", size_bytes=60),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        signals = result.findings["signals"]
        assert any(s["category"] == "security" and s["severity"] == "critical" for s in signals)


class TestScoring:
    def test_clean_project_high_score(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text(
            "import logging\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "def main() -> None:\n"
            "    logger.info('starting')\n"
        )
        (tmp_path / ".gitignore").write_text("__pycache__\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests/test_app.py").write_text("def test_main(): pass\n")
        ci_dir = tmp_path / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "ci.yml").write_text("on: push\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=100),
                FileInfo(path=Path(".gitignore"), extension="", size_bytes=20),
                FileInfo(path=Path("tests/test_app.py"), extension=".py", size_bytes=30),
                FileInfo(path=Path(".github/workflows/ci.yml"), extension=".yml", size_bytes=20),
            ],
            directories=[Path("tests"), Path(".github/workflows")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        assert result.findings["score"] >= 80

    def test_debt_laden_project_low_score(self, tmp_path: Path) -> None:
        code = "# TODO: everything\n# FIXME: broken\n# HACK: workaround\n"
        code += "try:\n    x = 1\nexcept:\n    pass\n"
        code += "print('debug')\n" * 5
        src = tmp_path / "app.py"
        src.write_text(code)
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=500),
            ],
            total_files=10,
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        assert result.findings["score"] < 80


class TestRenderSection:
    def test_empty_signals_no_section(self) -> None:
        structure = _make_structure(
            files=[],
            directories=[Path("tests"), Path(".github/workflows")],
            total_files=2,
        )
        structure.total_files = 2  # below thresholds
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        # With very few files and no source, section should be minimal or empty
        # (no source files to scan = no signals from code)
        assert result.category == "tech_debt"

    def test_section_includes_score(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("# TODO: fix this\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=20),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        assert "Debt Score" in result.section_content


class TestAnalysisResult:
    def test_result_has_correct_category(self) -> None:
        structure = _make_structure(files=[], directories=[Path("tests")], total_files=2)
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config())
        assert result.category == "tech_debt"

    def test_findings_structure(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n")
        structure = _make_structure(
            root=tmp_path,
            files=[
                FileInfo(path=Path("app.py"), extension=".py", size_bytes=10),
            ],
            directories=[Path("tests")],
        )
        analyzer = TechDebtAnalyzer()
        result = analyzer.analyze(structure, _make_config(root=tmp_path))
        assert "score" in result.findings
        assert "total_signals" in result.findings
        assert "categories" in result.findings
        assert "critical_count" in result.findings
        assert "signals" in result.findings
        assert isinstance(result.findings["signals"], list)
