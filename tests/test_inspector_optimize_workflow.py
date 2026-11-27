"""Inspector reading and build-time optimization workflows (the Python side; Unity is not run)."""

import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


SCENE = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar")
ROOT = base.TOOLS.parent


class InspectorOptimizeWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output

    def recipe(self, name, **body):
        self.write(f"Assets/DSH/Optimize/{name}/recipe.json", json.dumps(dict({"name": name}, **body)))

    def error(self, *args):
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)["error"]

    def test_inspector_arguments_are_checked_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        for extra, message in [
            (("--path", "/Armature"), "--path"),
            (("--path", "Armature\\Hips"), "--path"),
            (("--max-depth", "40"), "--max-depth"),
            (("--max-properties", "5"), "--max-properties"),
            (("--array-items", "0"), "--array-items"),
            (("--component", "x" * 201), "--component"),
        ]:
            self.assertIn(message, self.error("unity_inspector.py", "read", *SCENE, *extra))
        self.assertIn("--type", self.error("unity_inspector.py", "find", *SCENE, "--type", "  "))

    def test_optimize_recipe_errors_are_reported_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_optimize.py", "preview", *SCENE, "--recipe", "Light")
        for body, message in [
            ({}, "changes nothing"),
            ({"traceAndOptimize": "yes"}, "true or false"),
            ({"aaoOptions": {"mergeSkinnedMesh": True}}, "needs \"traceAndOptimize\""),
            ({"traceAndOptimize": True, "aaoOptions": {"merge": "on"}}, "option path"),
            ({"traceAndOptimize": True, "aaoOptions": {"a b": True}}, "option path"),
            ({"textures": {"size": 1000}}, "'textures.size'"),
            ({"textures": {"size": 1024, "materials": []}}, "different material names"),
            ({"textures": {"size": 1024, "materials": ["*", "Body"]}}, "'*' alone"),
            ({"textures": {"size": 1024, "exclude": ["*"]}}, "cannot use '*'"),
            ({"textures": {"size": 1024, "quality": 1}}, "'textures' must be"),
            ({"atlas": [{"materials": ["Body"]}]}, "merges one material"),
            ({"atlas": [{"materials": ["A", "B"], "size": 3000}]}, "'size'"),
            ({"atlas": [{"materials": ["A", "B"]}, {"materials": ["B", "C"]}]}, "two atlas groups"),
            ({"atlas": [{"materials": ["A", "B"], "padding": 4}]}, "takes only"),
            ({"atlas": [{"materials": ["A", "A"]}]}, "different material names"),
            ({"traceAndOptimize": True, "lod": 2}, "Unknown recipe keys"),
        ]:
            self.recipe("Light", **body)
            self.assertIn(message, self.error(*args), body)

    def test_optimize_preview_builds_the_unity_request(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe("Light", traceAndOptimize=True, aaoOptions={"mergeSkinnedMesh": False},
                    textures={"size": 1024, "exclude": ["Face"]},
                    atlas=[{"materials": ["Hoodie", "Pants"], "size": 2048}])
        plan = self.json_output(self.cli("unity_optimize.py", "preview", *SCENE, "--recipe", "Light"))
        request = plan["request"]
        self.assertTrue(request["traceAndOptimize"])
        self.assertEqual(request["aaoOptions"], [{"path": "mergeSkinnedMesh", "value": False}])
        self.assertEqual(request["textureSize"], 1024)
        self.assertEqual(request["textureMaterials"], ["*"])
        self.assertEqual(request["textureExclude"], ["Face"])
        self.assertEqual(request["atlas"], [{"materials": ["Hoodie", "Pants"], "size": 2048, "merge": True}])
        self.assertEqual(request["undo"], [])
        self.assertEqual(plan["summary"], {"traceAndOptimize": True, "aaoOptions": 1, "textureSize": 1024, "atlas": 1})
        self.assertIn("Assets/DSH/Editor/DshOptimize.cs", plan["plannedPaths"])
        first = plan["preview"]
        self.recipe("Light", traceAndOptimize=True)
        plan = self.json_output(self.cli("unity_optimize.py", "preview", *SCENE, "--recipe", "Light"))
        self.assertNotEqual(plan["preview"], first, "a changed recipe must need a new confirmation")
        self.assertEqual(plan["summary"]["textureSize"], "unchanged")

    def test_optimize_remove_needs_a_record_and_recipes_lists_scenes(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe("Light", traceAndOptimize=True)
        self.assertIn("no record", self.error("unity_optimize.py", "remove", *SCENE, "--recipe", "Light"))
        record = self.write(".dsh/optimize/Light.json", json.dumps(
            {"recipe": "Light", "scenes": {"Assets/Avatar.unity": [{"key": "aao:trace", "kind": "aao-trace", "path": ""}]}}))
        listing = self.json_output(self.cli("unity_optimize.py", "recipes"))
        self.assertEqual(listing["recipes"], [{"recipe": "Light", "appliedIn": ["Assets/Avatar.unity"]}])
        plan = self.json_output(self.cli("unity_optimize.py", "remove", *SCENE, "--recipe", "Light"))
        self.assertEqual(plan["summary"], {"aao-trace": 1})
        self.assertTrue(record.is_file())
        preview = self.json_output(self.cli("unity_optimize.py", "preview", *SCENE, "--recipe", "Light"))
        self.assertEqual(preview["request"]["undo"], [{"key": "aao:trace", "kind": "aao-trace", "path": ""}])

    def test_new_helpers_are_installed_and_allowed(self):
        sys.path.insert(0, str(base.TOOLS))
        import unity_toggle
        for name in ("DshInspector.cs", "DshOptimize.cs"):
            self.assertIn(name, unity_toggle.HELPERS)
            self.assertTrue((ROOT / "templates" / "Editor" / name).is_file())
        self.assertIn("Assets/DSH/Optimize", unity_toggle.MANAGED_FOLDERS)
        run = (base.TOOLS / "unity-run.ps1").read_text(encoding="utf-8-sig")
        allowed = set(re.findall(r"'(Dsh\w+\.cs)'", run))
        self.assertEqual(allowed, set(unity_toggle.HELPERS), "unity-run.ps1 must allow exactly the bundled helpers")

    def test_new_skills_are_listed_in_every_entry_skill(self):
        for path in ("claude/skills/vrc-avatar/SKILL.md", "codex/skills/vrc-avatar/SKILL.md", "cordis.patch.yml",
                     "skills/vrc-avatar-edit/SKILL.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            for skill in ("vrc-optimize", "vrc-inspector"):
                self.assertIn(skill, text, f"{path} does not mention {skill}")

    def test_migrate_knows_optimize_recipes(self):
        sys.path.insert(0, str(base.TOOLS))
        import unity_migrate
        self.assertEqual(unity_migrate.TASKS["OptimizeRecipe"], ("optimize", "apply"))
        self.assertIn("optimize", unity_migrate.ORDER)
        self.assertEqual(unity_migrate.TOOL["optimize"], "unity_optimize.py")


if __name__ == "__main__":
    unittest.main()
