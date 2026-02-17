# ClaudeMD Forge — Monetization Strategy

## Tier Structure

### Free (CLI on PyPI + GitHub)

| Command | Description |
|---------|-------------|
| `generate` | Scan project, produce CLAUDE.md |
| `audit` | Score an existing CLAUDE.md |
| `presets` | List available templates |
| `frameworks` | List framework presets |
| `status` | Show license status |

**Community presets included**: default, minimal, full, python-fastapi,
python-cli, django, react-typescript, nextjs, rust, go, node-express.

### Pro ($8/mo or $69/yr via Stripe)

Everything in Free, plus:

| Feature | Description |
|---------|-------------|
| `init --interactive` | Guided setup with smart defaults |
| `diff` | Show drift between CLAUDE.md and current codebase |
| CI integration | GitHub Action that auto-audits CLAUDE.md on PR |
| Premium presets | react-native, data-science, devops, mobile |
| Team templates | Shared org-wide standards (planned) |
| Priority updates | New analyzer modules first |

**License key format**: `CMDF-XXXX-XXXX-XXXX`

**Activation**:
```bash
export CLAUDEMD_FORGE_LICENSE=CMDF-XXXX-XXXX-XXXX
# or
echo "CMDF-XXXX-XXXX-XXXX" > ~/.claudemd-forge-license
```

### One-time Packs ($15–25 on Gumroad)

- Curated CLAUDE.md template packs by domain (web dev, data science,
  DevOps, mobile)
- "Standard Work for AI Agents" guide

## Implementation Architecture

```
licensing.py    — Tier enum, TierConfig, LicenseInfo models
                  License key detection (env var + filesystem)
                  Key format validation (CMDF-XXXX-XXXX-XXXX)
                  Feature/preset access checks

gates.py        — @require_pro decorator for CLI commands
                  check_preset_access() for preset gating
                  get_available_presets() for tier-aware listing

ci.py           — GitHub Action YAML template generation
                  generate_github_action(target_dir) writer

frameworks.py   — FRAMEWORK_PRESETS (free, 8 presets)
                  PREMIUM_PRESETS (pro, 4 presets)
```

## Feature Gate Matrix

| Feature | Free | Pro |
|---------|------|-----|
| `generate` | Yes | Yes |
| `audit` | Yes | Yes |
| `presets` | Yes | Yes |
| `frameworks` | Yes | Yes |
| `status` | Yes | Yes |
| `init` (interactive) | No | Yes |
| `diff` | No | Yes |
| CI integration | No | Yes |
| Premium presets | No | Yes |
| Team templates | No | Yes |
| Priority updates | No | Yes |

## Preset Access Matrix

| Preset | Free | Pro |
|--------|------|-----|
| default | Yes | Yes |
| minimal | Yes | Yes |
| full | Yes | Yes |
| python-fastapi | Yes | Yes |
| python-cli | Yes | Yes |
| django | Yes | Yes |
| react-typescript | Yes | Yes |
| nextjs | Yes | Yes |
| rust | Yes | Yes |
| go | Yes | Yes |
| node-express | Yes | Yes |
| monorepo | No | Yes |
| library | No | Yes |
| react-native | No | Yes |
| data-science | No | Yes |
| devops | No | Yes |
| mobile | No | Yes |

## Revenue Channels

1. **Stripe subscriptions** — Pro tier recurring revenue
2. **Gumroad one-time packs** — Template packs and guides
3. **GitHub Sponsors** — Community support tier

## Key Design Decisions

- Free tier is fully functional for individual use — no crippled features
- Pro gates are on workflow features (init, diff) and premium content
  (presets), not core functionality
- License key validation is local-only (no server calls) for v1
- Server-side validation planned for team features
- All premium presets follow the same `FrameworkPreset` model as free
  ones — no separate code paths
