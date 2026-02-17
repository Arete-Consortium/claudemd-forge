"""CI integration module for ClaudeMD Forge.

Generates GitHub Action workflows that auto-audit CLAUDE.md on pull
requests and post findings as PR comments. This is a Pro-tier feature.
"""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

logger = logging.getLogger(__name__)

_GITHUB_ACTION_TEMPLATE = dedent("""\
    name: Audit CLAUDE.md

    on:
      pull_request:
        paths:
          - "CLAUDE.md"
          - "src/**"
          - "tests/**"
          - "pyproject.toml"
          - "package.json"

    permissions:
      pull-requests: write
      contents: read

    jobs:
      audit-claudemd:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4

          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: "3.11"

          - name: Install claudemd-forge
            run: pip install claudemd-forge

          - name: Run audit
            id: audit
            run: |
              set +e
              OUTPUT=$(claudemd-forge audit CLAUDE.md -v 2>&1)
              EXIT_CODE=$?
              echo "exit_code=$EXIT_CODE" >> "$GITHUB_OUTPUT"
              {
                echo "audit_output<<EOF"
                echo "$OUTPUT"
                echo "EOF"
              } >> "$GITHUB_OUTPUT"
              exit 0

          - name: Comment on PR
            uses: actions/github-script@v7
            env:
              AUDIT_OUTPUT: ${{ steps.audit.outputs.audit_output }}
              AUDIT_EXIT_CODE: ${{ steps.audit.outputs.exit_code }}
            with:
              script: |
                const output = process.env.AUDIT_OUTPUT;
                const exitCode = process.env.AUDIT_EXIT_CODE;

                let status = 'passed';
                let icon = ':white_check_mark:';
                if (exitCode === '2') {
                  status = 'needs improvement';
                  icon = ':warning:';
                } else if (exitCode === '1') {
                  status = 'failed';
                  icon = ':x:';
                }

                const body = [
                  `## ${icon} CLAUDE.md Audit — ${status}`,
                  '',
                  '```',
                  output,
                  '```',
                  '',
                  '---',
                  '*Powered by [claudemd-forge](https://github.com/AreteDriver/claudemd-forge)*',
                ].join('\\n');

                await github.rest.issues.createComment({
                  issue_number: context.issue.number,
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  body: body,
                });
""")


def generate_github_action(target_dir: Path) -> Path:
    """Write the GitHub Action workflow file to the target directory.

    Creates `.github/workflows/claudemd-audit.yml` under the given
    project root directory.

    Returns the path to the created file.
    """
    workflow_dir = target_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = workflow_dir / "claudemd-audit.yml"
    workflow_path.write_text(_GITHUB_ACTION_TEMPLATE)

    logger.info("Created GitHub Action workflow: %s", workflow_path)
    return workflow_path


def get_action_template() -> str:
    """Return the raw GitHub Action YAML template as a string."""
    return _GITHUB_ACTION_TEMPLATE
