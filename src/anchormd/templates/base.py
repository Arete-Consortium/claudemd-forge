"""Base CLAUDE.md template with Jinja2 rendering."""

from __future__ import annotations

from jinja2 import BaseLoader, Environment

_ENV = Environment(loader=BaseLoader(), autoescape=False)

# Section templates as Jinja2 strings.
_TEMPLATES: dict[str, str] = {
    "header": "# CLAUDE.md — {{ project_name }}\n\n{{ description }}",
    "project_overview": "## Project Overview\n\n{{ overview_text }}\n",
    "current_state": (
        "## Current State\n\n"
        "- **Phase**: {{ phase }}\n"
        "- **Version**: {{ version }}\n"
        "- **Language**: {{ primary_language }}\n"
        "- **Files**: {{ total_files }} across {{ language_count }} languages\n"
    ),
    "architecture": "## Architecture\n\n```\n{{ tree }}\n```\n",
    "tech_stack": "## Tech Stack\n\n{{ tech_stack_items }}\n",
    "coding_standards": "## Coding Standards\n\n{{ standards_items }}\n",
    "common_commands": "## Common Commands\n\n```bash\n{{ commands }}\n```\n",
    "anti_patterns": "## Anti-Patterns (Do NOT Do)\n\n{{ anti_pattern_items }}\n",
    "dependencies": "## Dependencies\n\n{{ dependency_items }}\n",
    "git_conventions": (
        "## Git Conventions\n\n"
        "- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)\n"
        "- Branch naming: `feat/description`, `fix/description`\n"
        "- Run tests before committing\n"
    ),
}


class BaseTemplate:
    """Base CLAUDE.md template with all available sections."""

    @classmethod
    def get_section_template(cls, section_name: str) -> str:
        """Return Jinja2 template string for a named section."""
        return _TEMPLATES.get(section_name, "")

    @classmethod
    def render_section(cls, section_name: str, **context: object) -> str:
        """Render a section template with context variables."""
        template_str = cls.get_section_template(section_name)
        if not template_str:
            return ""
        template = _ENV.from_string(template_str)
        return template.render(**context)

    @classmethod
    def available_sections(cls) -> list[str]:
        """Return list of available section names."""
        return list(_TEMPLATES.keys())
