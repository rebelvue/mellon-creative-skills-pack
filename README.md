# Mellon Creative Skills Pack

One installer for the creative and workflow skills collected for Mellon. It is meant for Claude Code, Codex, and other Agent Skills-compatible environments.

The pack does not vendor third-party skill files. It downloads each skill from its original GitHub repository, installs only the declared skill directory, and validates `SKILL.md` before reporting success.

## Install

Clone this repository, inspect it, then run:

```bash
python3 install.py
```

Install to a specific skills directory:

```bash
python3 install.py --dest ~/.claude/skills
python3 install.py --dest ~/.codex/skills
python3 install.py --dest ~/.agents/skills
```

Preview what would happen without downloading or writing skills:

```bash
python3 install.py --dry-run
```

Update existing installed skills:

```bash
python3 install.py --update
```

## What It Installs

Design and UI:

- `design-taste-frontend`
- `emil-design-eng`
- `impeccable`
- `ui-ux-pro-max`
- `frontend-design`
- `brand-guidelines`
- `theme-factory`
- `canvas-design`

Video editing and motion graphics:

- `hyperframes`
- `remotion-create`
- `remotion-markup`
- `remotion-captions`
- `remotion-render`

Planning and workflow:

- `grill-me`
- `grilling`
- `to-spec`
- `to-tickets`
- `tdd`
- `improve-codebase-architecture`
- `setup-matt-pocock-skills`

## Safety Model

- Existing skills are skipped unless `--update` is set.
- Downloaded repositories are never executed.
- Only repositories and paths declared in `skills-manifest.json` are used.
- Every installed skill must contain a readable `SKILL.md` with matching `name` metadata and a non-empty `description`.
- A failed skill does not stop unrelated skills from installing.
- The command exits non-zero if any requested skill fails.

## Claude Prompt

Use this prompt with Claude:

> Install the complete Mellon Creative Skills Pack from this repository.
>
> First inspect `README.md`, `skills-manifest.json`, and `install.py`. Confirm that the installer only downloads the declared skills from their original GitHub repositories, does not execute downloaded scripts, and does not overwrite existing skills unless update mode is explicitly requested.
>
> Detect whether you are running in Claude Code, Codex, or another Agent Skills-compatible environment. Run the installer for the correct user-wide skills directory. Do not install into the current project unless user-wide installation is unavailable.
>
> After installation, verify every installed directory contains a readable `SKILL.md` with valid `name` and `description` metadata. Report installed, already-present, and failed skills separately. Do not claim completion if verification fails.

## Troubleshooting

If installation fails for a skill, read the failure row in the summary. Common causes are network errors, a changed upstream repository path, or a destination directory that is not writable.

Use `--dry-run` to confirm the destination and manifest. Use `--update` only when you want this installer to replace existing copies of the declared skills.
