# Prompt 02 — Codebase Scanner

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompt 01 (foundation) is complete — models, config, and project structure exist.

## Task
Build the codebase scanner that walks a project directory, catalogs files, and produces a `ProjectStructure` model.

## Steps

1. **Create `src/anchormd/scanner.py`**:

   ```python
   class CodebaseScanner:
       """Walks a project directory and produces a structured inventory."""

       def __init__(self, config: ForgeConfig): ...

       def scan(self) -> ProjectStructure:
           """Main entry point. Returns complete project structure."""

       def _should_include(self, path: Path) -> bool:
           """Check path against include/exclude patterns and size limits."""

       def _detect_languages(self, files: list[FileInfo]) -> dict[str, int]:
           """Count files per language using LANGUAGE_EXTENSIONS mapping."""

       def _count_lines(self, path: Path) -> int | None:
           """Count lines in a text file. Returns None for binary files.
           Use a 8KB read buffer — do NOT read entire file into memory."""

       def _is_binary(self, path: Path) -> bool:
           """Check first 8KB for null bytes to detect binary files."""

       def _get_primary_language(self, languages: dict[str, int]) -> str | None:
           """Return language with most files, excluding config/markup."""
   ```

2. **Key behaviors**:
   - Respect `config.exclude_patterns` — skip matching dirs/files
   - Respect `config.max_file_size_kb` — skip oversized files but count them
   - Respect `config.max_files` — stop scanning after limit (warn user)
   - Handle permission errors gracefully (log warning, skip file)
   - Handle symlinks: follow but detect cycles
   - Sort files by path for deterministic output
   - Detect `.gitignore` and optionally respect it

3. **Performance requirements**:
   - Scan a 10K file project in < 5 seconds
   - Never hold more than one file's content in memory at a time
   - Use `pathlib.Path.rglob()` or `os.scandir()` — not `os.walk()`

4. **Create `tests/test_scanner.py`**:
   - Test: Empty directory returns zero files
   - Test: Excluded directories are skipped (create node_modules/ with files, verify not in results)
   - Test: Binary files detected correctly (create a file with null bytes)
   - Test: Language detection maps .py → Python, .ts → TypeScript, .rs → Rust
   - Test: Primary language is correctly identified
   - Test: Max file size limit is respected
   - Test: Line counting is accurate for a known file
   - Test: Symlink cycles don't cause infinite loops
   - Test: Permission errors are handled without crashing

## Acceptance Criteria
- `pytest tests/test_scanner.py -v` — all pass
- Scanner produces correct `ProjectStructure` for the `anchormd` project itself (dogfood test)
- `ruff check src/anchormd/scanner.py` — clean
- No bare `except:` clauses
