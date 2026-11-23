"""PhysBone, proportion and parameter workflows (the Python side; Unity is a fake console program)."""

import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


GIT_IDENTITIES = base.GIT_IDENTITIES
SCENE = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar")


class DynamicsWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output
    editor_fixture = base.UnityWorkflowTests.editor_fixture

    def recipe(self, folder, name, **body):
        self.write(f"Assets/DSH/{folder}/{name}/recipe.json", json.dumps(dict({"name": name}, **body)))

    def error(self, *args):
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)["error"]

    def test_physbone_recipe_errors_are_reported_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_physbone.py", "preview", *SCENE, "--recipe", "Soft")
        cases = [
            ({}, "changes nothing"),
            ({"bones": [{"target": "Hair", "preset": "floppy"}]}, "'preset'"),
            ({"bones": [{"target": "Hair", "values": {"pull": 2}}]}, "'pull'"),
            ({"bones": [{"target": "Hair", "values": {"radius_curve": 1}}]}, "does not change"),
            ({"bones": [{"target": "Hair", "values": {"limitType": "Cone"}}]}, "Angle"),
            ({"bones": [{"target": "Hair", "values": {"allowGrabbing": "no"}}]}, "true or false"),
            ({"bones": [{"target": "Hair"}]}, "preset or values"),
            ({"colliders": [{"name": "Leg", "bone": "Knee", "targets": [{"target": "Skirt"}]}]}, "'bone'"),
            ({"colliders": [{"name": "Leg", "bone": "LeftUpperLeg", "targets": []}]}, "'targets'"),
            ({"colliders": [{"name": "Leg", "bone": "LeftUpperLeg", "radius": 3, "targets": [{"target": "S"}]}]}, "'radius'"),
        ]
        for body, message in cases:
            self.recipe("PhysBones", "Soft", **body)
            self.assertIn(message, self.error(*args))

    def test_physbone_preview_merges_presets_and_values(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.recipe("PhysBones", "Soft", bones=[{"target": "Hair", "preset": "soft", "values": {"pull": 0.3,
                                                                                               "allowGrabbing": False}}],
                    colliders=[{"name": "LegL", "bone": "LeftUpperLeg", "targets": [{"target": "Skirt", "index": 1}]}])
        plan = self.json_output(self.cli("unity_physbone.py", "preview", *SCENE, "--recipe", "Soft"))
        values = {v["field"]: v["value"] for v in plan["request"]["bones"][0]["values"]}
        self.assertEqual(values["pull"], "0.3")
        self.assertEqual(values["spring"], "0.4")
        self.assertEqual(values["allowGrabbing"], "false")
        collider = plan["request"]["colliders"][0]
        self.assertEqual((collider["shape"], collider["radius"], collider["height"]), ("capsule", 0.05, 0.0))
        self.assertEqual(collider["targets"][0]["index"], 1)
        self.assertEqual(plan["summary"], {"physBones": 1, "values": 5, "colliders": 1})

    def test_proportion_recipe_errors_and_preview(self):
        self.write("Assets/Avatar.unity", "scene\n")
        args = ("unity_proportion.py", "preview", *SCENE, "--recipe", "View")
        for body, message in [({}, "changes nothing"), ({"view": "eyes"}, "'view'"),
                              ({"view": [0, -1, 0]}, "above the avatar's feet"),
                              ({"scales": [{"bone": "Head", "scale": 9}]}, "'scale'"),
                              ({"scales": [{"bone": "Head", "scale": 1.1}, {"bone": "Head", "scale": 1.2}]}, "different"),
                              ({"scales": [{"bone": "Head", "scale": 1.1, "children": "yes"}]}, "'children'")]:
            self.recipe("Proportions", "View", **body)
            self.assertIn(message, self.error(*args))
        self.recipe("Proportions", "View", view="auto", scales=[{"bone": "Head", "scale": [1, 1.1, 1]}])
        plan = self.json_output(self.cli(*args))
        self.assertEqual(plan["request"]["viewMode"], "auto")
        self.assertEqual(plan["request"]["forward"], 0.035)
        self.assertEqual(plan["request"]["scales"], [{"bone": "Head", "scale": [1.0, 1.1, 1.0], "children": True}])

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_physbone_apply_records_undo_and_remove_sends_it_back(self):
        scene = self.write("Assets/Avatar.unity", "original\n")
        self.recipe("PhysBones", "Soft", bones=[{"target": "Hair", "preset": "stiff"}])
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        unity = self.editor_fixture(r'''
            string request = File.ReadAllText(Environment.GetEnvironmentVariable("DSH_UNITY_REQUEST_PATH"));
            bool remove = Array.IndexOf(args, "DSH.Editor.DshPhysBone.Remove") >= 0;
            if (!remove && Array.IndexOf(args, "DSH.Editor.DshPhysBone.Apply") < 0) Environment.Exit(4);
            string undo = "[{\"key\":\"value:Hair#0:pull\",\"kind\":\"value\",\"path\":\"Hair\",\"index\":0,\"field\":\"pull\",\"before\":\"0.2\"}]";
            if (remove) {
                if (!request.Contains("value:Hair#0:pull")) Environment.Exit(6);
                File.WriteAllText("Assets/Avatar.unity", "original\n");
            } else {
                File.AppendAllText("Assets/Avatar.unity", "physbone\n");
            }
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"" + (remove ? "PhysBoneRemove" : "PhysBoneRecipe") + "\",\"verified\":true," +
                "\"saved\":true,\"scene\":\"Assets/Avatar.unity\"," + (remove ? "" : "\"undo\":" + undo + ",") +
                "\"sceneDigest\":\"" + Checksum("Assets/Avatar.unity") + "\"}");
        ''')
        args = (*SCENE, "--recipe", "Soft")
        self.assertIn("no record", self.error("unity_physbone.py", "remove", *args))
        plan = self.json_output(self.cli("unity_physbone.py", "preview", *args))
        applied = self.json_output(self.cli("unity_physbone.py", "apply", *args, "--approved-preview", plan["preview"],
                                            env=unity))
        self.assertTrue(applied["ok"], applied)
        record = json.loads((self.project / ".dsh/physbones/Soft.json").read_text(encoding="utf-8"))
        self.assertEqual(record["scenes"]["Assets/Avatar.unity"][0]["before"], "0.2")
        listing = self.json_output(self.cli("unity_physbone.py", "recipes"))
        self.assertEqual(listing["recipes"], [{"recipe": "Soft", "appliedIn": ["Assets/Avatar.unity"]}])

        preview = self.json_output(self.cli("unity_physbone.py", "remove", *args))
        self.assertEqual(preview["summary"], {"value": 1})
        removed = self.json_output(self.cli("unity_physbone.py", "remove", *args, "--approved-preview",
                                            preview["preview"], env=unity))
        self.assertTrue(removed["ok"], removed)
        self.assertEqual(scene.read_text(), "original\n")
        record = json.loads((self.project / ".dsh/physbones/Soft.json").read_text(encoding="utf-8"))
        self.assertEqual(record["scenes"], {})

    def test_undo_entries_keep_the_first_value_per_key(self):
        sys.path.insert(0, str(base.TOOLS))
        import dsh_recipe
        merged = dsh_recipe.RecipeKind.merge([{"key": "a", "before": "1"}],
                                             [{"key": "a", "before": "2"}, {"key": "b", "before": "3"}])
        self.assertEqual(merged, [{"key": "a", "before": "1"}, {"key": "b", "before": "3"}])

    def test_parameter_budget_warns_and_stops_over_the_limit(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        toggle_args = ("unity_toggle.py", "preview", *SCENE, "--outfit", "Avatar/Hoodie", "--menu", "Outfit/Hoodie")
        plan = self.json_output(self.cli(*toggle_args))
        self.assertEqual(plan["parameterBudget"]["measured"], False)

        sys.path.insert(0, str(base.TOOLS))
        import unity_params
        from unity_toggle import digest
        cache = unity_params.cache_path(self.project, "Assets/Avatar.unity", "Avatar")
        cache.parent.mkdir(parents=True, exist_ok=True)
        record = {"scene": "Assets/Avatar.unity", "avatar": "Avatar", "built": True, "usedBits": 256, "limit": 256,
                  "sceneDigest": digest(self.project / "Assets/Avatar.unity")}
        cache.write_text(json.dumps(record), encoding="utf-8")
        plan = self.json_output(self.cli(*toggle_args))
        self.assertEqual((plan["parameterBudget"]["afterBits"], plan["parameterBudget"]["overLimit"]), (257, True))
        refused = self.error("unity_toggle.py", "apply", *toggle_args[2:], "--approved-preview", plan["preview"])
        self.assertIn("parameter bits", refused)

        self.write("Assets/Avatar.unity", "edited\n")  # measured before this edit: warn, do not stop
        plan = self.json_output(self.cli(*toggle_args))
        self.assertTrue(plan["parameterBudget"]["stale"])
        self.assertFalse(plan["parameterBudget"]["overLimit"])


if __name__ == "__main__":
    unittest.main()
