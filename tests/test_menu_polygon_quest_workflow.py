"""Menu tidying, polygon reduction and Quest workflows (the Python side; Unity is not run)."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


SCENE = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar")


class MenuPolygonQuestWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output

    def recipe(self, folder, name, **body):
        self.write(f"Assets/DSH/{folder}/{name}/recipe.json", json.dumps(dict({"name": name}, **body)))

    def error(self, *args):
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)["error"]

    def test_menu_recipe_errors_are_reported_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_menu.py", "preview", *SCENE, "--recipe", "Tidy")
        for body, message in [
            ({}, "changes nothing"),
            ({"moves": [{"from": "A", "to": "A"}]}, "different"),
            ({"moves": [{"from": "A//B", "to": "C"}]}, "empty part"),
            ({"moves": [{"from": "A"}]}, "'to'"),
            ({"icons": [{"path": "A", "icon": "C:/x.png"}]}, "under Assets"),
            ({"icons": [{"path": "A", "icon": "Assets/missing.png"}]}, "does not exist"),
            ({"order": [{"path": "A", "position": "first"}]}, "whole number"),
            ({"order": [{"path": "A", "position": -20}]}, "whole number"),
            ({"rename": []}, "Unknown recipe keys"),
        ]:
            self.recipe("Menus", "Tidy", **body)
            self.assertIn(message, self.error(*args))

    def test_menu_preview_keeps_paths_and_fingerprints_icons(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Icons/pink.png", "png")
        self.recipe("Menus", "Tidy", moves=[{"from": "Color/Hair Pink", "to": "Hair/Pink\\/Rose"}],
                    icons=[{"path": "Hair/Pink\\/Rose", "icon": "Assets/Icons/pink.png"}],
                    order=[{"path": "Facial Set", "position": 0}])
        plan = self.json_output(self.cli("unity_menu.py", "preview", *SCENE, "--recipe", "Tidy"))
        self.assertEqual(plan["request"]["moves"], [{"from": "Color/Hair Pink", "to": "Hair/Pink\\/Rose"}])
        self.assertEqual(plan["summary"], {"moves": 1, "icons": 1, "order": 1})
        self.assertFalse(plan["alreadyInScene"])
        first = plan["preview"]
        self.write("Assets/Icons/pink.png", "another png")
        plan = self.json_output(self.cli("unity_menu.py", "preview", *SCENE, "--recipe", "Tidy"))
        self.assertNotEqual(plan["preview"], first, "a changed icon file must need a new confirmation")

    def test_menu_remove_needs_the_holder_in_the_scene(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe("Menus", "Tidy", order=[{"path": "A", "position": 0}])
        self.assertIn("No menu recipe", self.error("unity_menu.py", "remove", *SCENE, "--recipe", "Tidy"))
        self.write("Assets/Avatar.unity", "  m_Name: DSH Menu Tidy\n")
        listing = self.json_output(self.cli("unity_menu.py", "recipes"))
        self.assertEqual(listing["recipes"], [{"recipe": "Tidy", "scenes": ["Assets/Avatar.unity"]}])

    def test_polygon_recipe_errors_and_preview(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_polygon.py", "preview", *SCENE, "--recipe", "Light")
        for body, message in [
            ({}, "changes nothing"),
            ({"total": 10}, "'total'"),
            ({"renderers": [{"path": "Body"}]}, "either 'ratio'"),
            ({"renderers": [{"path": "Body", "ratio": 0.5, "triangles": 100}]}, "either 'ratio'"),
            ({"renderers": [{"path": "Body", "ratio": 0.01}]}, "'ratio'"),
            ({"renderers": [{"path": "Body", "ratio": 0.5}], "keep": ["Body"]}, "named twice"),
            ({"total": 50000, "keepFace": "yes"}, "true or false"),
            ({"total": 50000, "lod": 2}, "Unknown recipe keys"),
        ]:
            self.recipe("Polygons", "Light", **body)
            self.assertIn(message, self.error(*args))
        self.recipe("Polygons", "Light", total=69000, keep=["Body"], renderers=[{"path": "Hair", "ratio": 0.6}])
        plan = self.json_output(self.cli(*args))
        self.assertEqual(plan["request"]["total"], 69000)
        self.assertEqual(plan["request"]["renderers"], [{"path": "Hair", "ratio": 0.6, "triangles": 0}])
        self.assertTrue(plan["request"]["keepFace"])
        self.assertEqual(plan["request"]["undo"], [])
        self.assertEqual(plan["summary"], {"total": 69000, "renderers": 1, "keepFace": True})

    def test_polygon_remove_needs_a_record(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe("Polygons", "Light", total=69000)
        self.assertIn("no record", self.error("unity_polygon.py", "remove", *SCENE, "--recipe", "Light"))

    def test_quest_recipe_errors_and_preview(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_quest.py", "preview", *SCENE, "--recipe", "Quest")
        for body, message in [
            ({"shader": "standard"}, "'shader'"),
            ({"textureSize": 4096}, "'textureSize'"),
            ({"brightness": 0.5}, "toonLit only"),
            ({"shader": "toonLit", "brightness": 2}, "'brightness'"),
            ({"removeOnAndroid": ["A", "A"]}, "different object paths"),
            ({"removeOnAndroid": ["/Armature"]}, "different object paths"),
            ({"platform": "ios"}, "Unknown recipe keys"),
        ]:
            self.recipe("Quest", "Quest", **body)
            self.assertIn(message, self.error(*args))
        self.recipe("Quest", "Quest", shader="toonLit", brightness=0.9, removeOnAndroid=["Armature/Hips/Skirt"])
        plan = self.json_output(self.cli(*args))
        self.assertEqual(plan["summary"], {"shader": "toonLit", "textureSize": 1024, "removeOnAndroid": 1})
        self.assertEqual(plan["request"]["brightness"], 0.9)
        self.assertIn("PC builds do not change", plan["note"])

    def test_rank_is_added_to_counts(self):
        sys.path.insert(0, str(base.TOOLS))
        import unity_polygon
        ranked = unity_polygon.rank({"triangles": 69000, "skinnedMeshes": 1, "materialSlots": 4})
        self.assertEqual(ranked["pc"]["rank"], "good")
        self.assertEqual(ranked["pc"]["limitedBy"], ["triangles"])
        self.assertEqual(ranked["mobile"]["rank"], "veryPoor")


if __name__ == "__main__":
    unittest.main()
