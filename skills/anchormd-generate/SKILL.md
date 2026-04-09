---
name: anchormd-generate
description: Generate a CLAUDE.md file for the current project. Use when setting up a new project for AI-assisted development, when a project lacks a CLAUDE.md, when the user asks to create project context for Claude Code, or when onboarding a codebase for agent use. Scans the codebase to detect languages, frameworks, testing patterns, build commands, and conventions, then produces a structured CLAUDE.md with coding standards, anti-patterns, and project-specific instructions.
license: MIT
---

# Generate CLAUDE.md

Generate a production-grade CLAUDE.md for the current project using anchormd.

## Prerequisites

anchormd must be installed: `pip install anchormd`

## Workflow

1. Run the generator against the project root:
   ```bash
   anchormd generate .
   ```

2. Review the generated CLAUDE.md output. The generator scans for:
   - Programming languages and frameworks in use
   - Build systems and package managers
   - Testing frameworks and patterns
   - CI/CD configuration
   - Code style and linting setup
   - Project structure and architecture

3. If the output needs refinement, iterate:
   ```bash
   anchormd generate . --preset fastapi   # Use a framework-specific preset
   anchormd generate . --format markdown  # Control output format
   ```

4. Audit the generated file for quality:
   ```bash
   anchormd audit CLAUDE.md
   ```

## Available Presets

Community presets (free): django, flask, fastapi, react, nextjs, express, rails, spring, go-api, rust-cli, generic

Pro presets (license required): terraform, kubernetes, monorepo, microservices, mobile, data-pipeline

## When NOT to Use

- If a well-maintained CLAUDE.md already exists, prefer manual updates over regeneration
- For monorepos, run per-package rather than at the root
