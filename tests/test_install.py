import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import install


class ManifestTests(unittest.TestCase):
    def test_manifest_has_19_unique_skills(self):
        skills = install.load_manifest(Path("skills-manifest.json"))

        self.assertEqual(len(skills), 19)
        self.assertEqual(len({skill.name for skill in skills}), 19)
        self.assertEqual(len({skill.destination for skill in skills}), 19)

    def test_manifest_rejects_duplicate_destination(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "skills": [
                            {"name": "one", "category": "x", "repo": "a/b", "path": "skills/one", "destination": "same"},
                            {"name": "two", "category": "x", "repo": "a/b", "path": "skills/two", "destination": "same"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate destination"):
                install.load_manifest(path)


class InstallerTests(unittest.TestCase):
    def build_archive(self, root: Path, name: str = "demo-skill", description: str = "Demo skill") -> Path:
        source_root = root / "repo-main"
        skill_dir = source_root / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n# Demo\n",
            encoding="utf-8",
        )
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "note.md").write_text("supporting file\n", encoding="utf-8")
        archive = root / "repo.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            for file_path in source_root.rglob("*"):
                if file_path.is_file():
                    handle.write(file_path, file_path.relative_to(root))
        return archive

    def test_install_from_local_archive(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self.build_archive(root)
            skill = install.Skill(
                name="demo-skill",
                category="Test",
                repo="local/demo",
                path="skills/demo-skill",
                destination="demo-skill",
                archive_url=archive.as_uri(),
            )
            dest = root / "dest"

            result = install.install_skill(skill, dest, update=False, dry_run=False)

            self.assertEqual(result.status, "installed")
            self.assertTrue((dest / "demo-skill" / "SKILL.md").is_file())
            self.assertTrue((dest / "demo-skill" / "references" / "note.md").is_file())

    def test_existing_skill_is_skipped_without_update(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self.build_archive(root)
            dest = root / "dest"
            existing = dest / "demo-skill"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("---\nname: demo-skill\ndescription: Old\n---\n", encoding="utf-8")
            skill = install.Skill("demo-skill", "Test", "local/demo", "skills/demo-skill", "demo-skill", archive.as_uri())

            result = install.install_skill(skill, dest, update=False, dry_run=False)

            self.assertEqual(result.status, "skipped")
            self.assertIn("Old", (existing / "SKILL.md").read_text(encoding="utf-8"))

    def test_existing_skill_updates_when_requested(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self.build_archive(root, description="New")
            dest = root / "dest"
            existing = dest / "demo-skill"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("---\nname: demo-skill\ndescription: Old\n---\n", encoding="utf-8")
            skill = install.Skill("demo-skill", "Test", "local/demo", "skills/demo-skill", "demo-skill", archive.as_uri())

            result = install.install_skill(skill, dest, update=True, dry_run=False)

            self.assertEqual(result.status, "installed")
            self.assertIn("New", (existing / "SKILL.md").read_text(encoding="utf-8"))

    def test_bad_skill_metadata_fails(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self.build_archive(root, name="wrong-name")
            skill = install.Skill("demo-skill", "Test", "local/demo", "skills/demo-skill", "demo-skill", archive.as_uri())

            result = install.install_skill(skill, root / "dest", update=False, dry_run=False)

            self.assertEqual(result.status, "failed")
            self.assertIn("expected 'demo-skill'", result.message)

    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            skill = install.Skill("demo-skill", "Test", "local/demo", "skills/demo-skill", "demo-skill")
            dest = root / "dest"

            result = install.install_skill(skill, dest, update=False, dry_run=True)

            self.assertEqual(result.status, "dry-run")
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()

