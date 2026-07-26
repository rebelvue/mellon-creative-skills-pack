#!/usr/bin/env python3
"""Install the Mellon Creative Skills Pack."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "skills-manifest.json"


def https_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    repo: str
    path: str
    destination: str
    archive_url: str | None = None


@dataclass
class Result:
    status: str
    skill: str
    category: str
    message: str


def load_manifest(path: Path) -> list[Skill]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise ValueError("manifest must contain a top-level skills list")

    skills: list[Skill] = []
    seen_names: set[str] = set()
    seen_destinations: set[str] = set()
    for index, raw in enumerate(data["skills"], start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"skill #{index} must be an object")
        for field in ("name", "category", "repo", "path"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ValueError(f"skill #{index} missing required string field: {field}")
        name = raw["name"].strip()
        destination = raw.get("destination", name).strip()
        if name in seen_names:
            raise ValueError(f"duplicate skill name: {name}")
        if destination in seen_destinations:
            raise ValueError(f"duplicate destination: {destination}")
        seen_names.add(name)
        seen_destinations.add(destination)
        archive_url = raw.get("archive_url")
        if archive_url is not None and not isinstance(archive_url, str):
            raise ValueError(f"skill {name} has non-string archive_url")
        skills.append(
            Skill(
                name=name,
                category=raw["category"].strip(),
                repo=raw["repo"].strip(),
                path=raw["path"].strip().strip("/"),
                destination=destination,
                archive_url=archive_url,
            )
        )
    return skills


def choose_destination(target: str | None, explicit_dest: str | None) -> Path:
    if explicit_dest:
        return Path(os.path.expanduser(explicit_dest)).resolve()

    home = Path.home()
    if target == "claude":
        return home / ".claude" / "skills"
    if target == "codex":
        return home / ".codex" / "skills"
    if target == "agents":
        return home / ".agents" / "skills"

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE"):
        return home / ".claude" / "skills"
    if os.environ.get("CODEX_HOME") or (home / ".codex").exists():
        return home / ".codex" / "skills"
    return home / ".agents" / "skills"


def read_json_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "mellon-creative-skills-pack"})
    with urllib.request.urlopen(request, timeout=30, context=https_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def default_branch(repo: str) -> str:
    data = read_json_url(f"https://api.github.com/repos/{repo}")
    branch = data.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise ValueError(f"could not determine default branch for {repo}")
    return branch


def archive_url_for(skill: Skill) -> str:
    if skill.archive_url:
        return skill.archive_url
    branch = default_branch(skill.repo)
    return f"https://codeload.github.com/{skill.repo}/zip/refs/heads/{branch}"


def download_archive(skill: Skill, temp_dir: Path) -> Path:
    archive_path = temp_dir / f"{skill.repo.replace('/', '-')}.zip"
    request = urllib.request.Request(
        archive_url_for(skill),
        headers={"User-Agent": "mellon-creative-skills-pack"},
    )
    with urllib.request.urlopen(request, timeout=120, context=https_context()) as response:
        archive_path.write_bytes(response.read())
    return archive_path


def extract_archive(archive_path: Path, temp_dir: Path) -> Path:
    extract_dir = temp_dir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(children) != 1:
        raise ValueError(f"archive {archive_path.name} did not contain one top-level directory")
    return children[0]


def parse_skill_metadata(skill_md: Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("SKILL.md is empty")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with front matter")
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2).strip().strip('"')
    return metadata


def validate_skill_dir(path: Path, expected_name: str) -> None:
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError("missing SKILL.md")
    metadata = parse_skill_metadata(skill_md)
    if metadata.get("name") != expected_name:
        raise ValueError(f"SKILL.md name is {metadata.get('name')!r}, expected {expected_name!r}")
    if not metadata.get("description"):
        raise ValueError("SKILL.md description is missing")


def stage_skill(skill: Skill, temp_dir: Path) -> Path:
    archive_path = download_archive(skill, temp_dir)
    repo_root = extract_archive(archive_path, temp_dir)
    source = repo_root / skill.path
    if not source.is_dir():
        raise ValueError(f"declared path not found: {skill.path}")
    staged = temp_dir / "staged" / skill.destination
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staged)
    validate_skill_dir(staged, skill.name)
    return staged


def install_skill(skill: Skill, destination_root: Path, update: bool, dry_run: bool) -> Result:
    target = destination_root / skill.destination
    if dry_run:
        state = "would update" if target.exists() and update else "would skip" if target.exists() else "would install"
        return Result("dry-run", skill.name, skill.category, f"{state}: {target}")

    if target.exists() and not update:
        return Result("skipped", skill.name, skill.category, f"already exists: {target}")

    try:
        destination_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"mellon-{skill.destination}-") as temp_name:
            staged = stage_skill(skill, Path(temp_name))
            replacement = destination_root / f".{skill.destination}.staged"
            if replacement.exists():
                shutil.rmtree(replacement)
            shutil.move(str(staged), str(replacement))
            validate_skill_dir(replacement, skill.name)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(replacement), str(target))
        return Result("installed", skill.name, skill.category, str(target))
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        return Result("failed", skill.name, skill.category, str(exc))


def print_summary(results: list[Result], destination: Path) -> None:
    print(f"Destination: {destination}")
    for category in sorted({result.category for result in results}):
        print(f"\n{category}")
        for result in [item for item in results if item.category == category]:
            print(f"  {result.status:9} {result.skill}: {result.message}")

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    print("\nSummary")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the Mellon Creative Skills Pack.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to skills-manifest.json")
    parser.add_argument("--dest", help="Destination skills directory")
    parser.add_argument("--target", choices=("claude", "codex", "agents"), help="Choose a standard skills directory")
    parser.add_argument("--update", action="store_true", help="Replace existing installed skills after validation")
    parser.add_argument("--dry-run", action="store_true", help="Show planned work without downloading or writing skills")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        skills = load_manifest(Path(args.manifest))
        destination = choose_destination(args.target, args.dest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"manifest error: {exc}", file=sys.stderr)
        return 2

    results = [install_skill(skill, destination, args.update, args.dry_run) for skill in skills]
    print_summary(results, destination)
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
