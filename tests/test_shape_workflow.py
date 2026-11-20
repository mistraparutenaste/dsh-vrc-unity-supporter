import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


GIT_IDENTITIES = base.GIT_IDENTITIES
ARGS = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--recipe", "Fit")


class ShapeWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output
    editor_fixture = base.UnityWorkflowTests.editor_fixture

    def recipe(self, **sections):
        self.write("Assets/DSH/Shapes/Fit/recipe.json", json.dumps(dict({"name": "Fit"}, **sections)))

    def test_recipe_errors_are_reported_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        cases = [
            ({}, "changes nothing"),
            ({"weights": [{"renderer": "Body", "shape": "Chest", "weight": 150}]}, "from 0 to 100"),
            ({"weights": [{"renderer": "Body", "weight": 10}]}, "'shape'"),
            ({"sync": [{"renderer": "Hoodie", "source": "Body", "shapes": []}]}, "list of blendshape names"),
            ({"remove": [{"renderer": "Body", "shapes": ["Chest_OFF"], "tolerance": 0}]}, "tolerance"),
        ]
        for sections, message in cases:
            self.recipe(**sections)
            failed = self.cli("unity_shape.py", "preview", *ARGS)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(message, json.loads(failed.stdout)["error"])
        missing = self.cli("unity_shape.py", "preview", *ARGS[:-1], "Other")
        self.assertIn("Write the recipe first", json.loads(missing.stdout)["error"])

    def test_preview_summarises_the_recipe_and_changes_with_it(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe(weights=[{"renderer": "Body", "shape": "Breasts_big", "weight": 60}],
                    sync=[{"renderer": "Hoodie", "source": "Body", "shapes": ["Breasts_big"]}],
                    remove=[{"renderer": "Body", "shapes": ["Chest_1_OFF", "Spine_1_OFF"]}])
        plan = self.json_output(self.cli("unity_shape.py", "preview", *ARGS))
        self.assertEqual(plan["summary"], {"weights": 1, "syncShapes": 1, "removeShapes": 2})
        self.assertEqual(plan["request"]["remove"][0]["tolerance"], 0.001)
        self.recipe(weights=[{"renderer": "Body", "shape": "Breasts_big", "weight": 70}])
        changed = self.json_output(self.cli("unity_shape.py", "preview", *ARGS))
        self.assertNotEqual(changed["preview"], plan["preview"])

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_apply_saves_the_scene_and_recipes_do_not_block_later_tasks(self):
        scene = self.write("Assets/Avatar.unity", "original\n")
        self.recipe(weights=[{"renderer": "Body", "shape": "Breasts_big", "weight": 60}])
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        self.recipe(weights=[{"renderer": "Body", "shape": "Breasts_big", "weight": 65}])  # edited after the commit
        unity = self.editor_fixture(r'''
            if (Array.IndexOf(args, "DSH.Editor.DshShape.Apply") < 0) Environment.Exit(4);
            if (Array.IndexOf(args, "-nographics") < 0) Environment.Exit(5);  // no SDK check: no graphics needed
            File.AppendAllText("Assets/Avatar.unity", "shape\n");
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"ShapeRecipe\",\"verified\":true,\"saved\":true,\"sceneDigest\":\"" +
                Checksum("Assets/Avatar.unity") + "\"}");
        ''')
        plan = self.json_output(self.cli("unity_shape.py", "preview", *ARGS))
        self.assertEqual(plan["git"]["blockingChanges"], [])
        applied = self.json_output(self.cli("unity_shape.py", "apply", *ARGS, "--approved-preview", plan["preview"],
                                            env=unity))
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(scene.read_text(), "original\nshape\n")
        toggle = self.json_output(self.cli("unity_toggle.py", "preview", "--scene", "Assets/Avatar.unity",
                                           "--avatar", "Avatar", "--outfit", "Avatar/Hoodie", "--menu", "衣装/服"))
        self.assertEqual(toggle["git"]["managedScenes"], ["Assets/Avatar.unity"])
        self.assertEqual(toggle["git"]["blockingChanges"], [])


if __name__ == "__main__":
    unittest.main()
