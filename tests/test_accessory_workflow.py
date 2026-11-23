import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


GIT_IDENTITIES = base.GIT_IDENTITIES
ARGS = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--recipe", "Hat")


class AccessoryWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output
    editor_fixture = base.UnityWorkflowTests.editor_fixture

    def recipe(self, **fields):
        self.write("Assets/DSH/Accessories/Hat/recipe.json",
                   json.dumps(dict({"name": "Hat", "asset": "Assets/Items/Hat.prefab"}, **fields)))

    def test_recipe_errors_are_reported_before_unity_runs(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        cases = [
            ({"asset": "Assets/Items/Missing.prefab"}, "does not exist"),
            ({"asset": "Assets/Items/Hat.png"}, ".prefab or .fbx"),
            ({"asset": "Assets/../Hat.prefab"}, ".prefab or .fbx"),
            ({"mode": "glue"}, "'mode'"),
            ({"bone": "Hat"}, "humanoid bone"),
            ({"origin": "world"}, "'origin'"),
            ({"position": [0, 3, 0]}, "'position'"),
            ({"rotation": [0, 0]}, "'rotation'"),
            ({"scale": 0}, "'scale'"),
            ({"scale": "big"}, "'scale'"),
            ({"scale": "auto", "bone": "Chest"}, "Head bone"),
            ({"scale": "auto", "origin": "avatar"}, "Head bone"),
            ({"menu": "Accessory//Hat"}, "'menu'"),
            ({"hide": "Hair", "menu": "Hat"}, "'hide'"),
            ({"defaultOn": "yes"}, "'defaultOn'"),
            ({"materialsFrom": "Assets/Items/Missing.prefab"}, "'materialsFrom'"),
        ]
        for fields, message in cases:
            self.recipe(**fields)
            failed = self.cli("unity_accessory.py", "preview", *ARGS)
            self.assertNotEqual(failed.returncode, 0, fields)
            self.assertIn(message, json.loads(failed.stdout)["error"], fields)
        missing = self.cli("unity_accessory.py", "preview", *ARGS[:-1], "Other")
        self.assertIn("Write the recipe first", json.loads(missing.stdout)["error"])

    def test_preview_follows_the_recipe_and_the_asset(self):
        self.write("Assets/Avatar.unity", "scene\n")
        asset = self.write("Assets/Items/Hat.prefab", "prefab\n")
        self.recipe(bone="Head", position=[0, 0.1, 0], menu="Accessory/Hat", hide=["Hair"])
        plan = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertEqual(plan["request"]["origin"], "auto")
        self.assertEqual(plan["request"]["folder"], "Assets/DSH/Accessories/Hat")
        self.assertIn("Assets/DSH/Accessories/Hat/Hat_hide.anim", plan["plannedPaths"])
        self.assertFalse(plan["alreadyInScene"])
        asset.write_text("prefab changed\n")
        changed = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertNotEqual(changed["preview"], plan["preview"])

    def test_auto_scale_asks_unity_to_size_the_item_to_the_head(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        self.recipe(bone="Head", scale="auto", position=[0, -0.01, 0])
        request = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))["request"]
        self.assertEqual((request["fitHead"], request["scale"], request["position"]), (True, 1.0, [0, -0.01, 0]))
        self.recipe(bone="Head", scale=0.2)
        request = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))["request"]
        self.assertEqual((request["fitHead"], request["scale"]), (False, 0.2))

    def test_preview_reports_materials_the_prefab_refers_to_but_the_project_lacks(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        have, lack = "a" * 32, "b" * 32
        self.write("Assets/Items/Hat Skin.prefab",
                   f"  m_Materials:\n  - {{fileID: 2100000, guid: {have}, type: 2}}\n"
                   f"  - {{fileID: 2100000, guid: {lack}, type: 2}}\n"
                   f"  m_Script: {{fileID: 11500000, guid: {'c' * 32}, type: 3}}\n")
        self.write("Assets/Items/Hat.mat.meta", f"fileFormatVersion: 2\nguid: {have}\n")
        self.recipe(bone="Head", materialsFrom="Assets/Items/Hat Skin.prefab")
        plan = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertEqual(plan["missingMaterials"]["guids"], [lack])
        self.write("Assets/Shared/_Material/Hat2.mat.meta", f"fileFormatVersion: 2\nguid: {lack}\n")
        plan = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertNotIn("missingMaterials", plan)

    def test_always_worn_accessory_hides_without_a_clip_and_remove_turns_them_back_on(self):
        self.write("Assets/Avatar.unity", "--- !u!1 &1\nGameObject:\n  m_Name: DSH Accessory Hat\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        self.recipe(bone="Head", hide=["Costume_Hoodie"])
        plan = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertIn("Assets/Avatar.unity", plan["plannedPaths"])
        self.assertFalse([p for p in plan["plannedPaths"] if p.endswith(".anim")])
        removal = self.json_output(self.cli("unity_accessory.py", "remove", *ARGS))
        self.assertEqual(removal["request"]["hide"], ["Costume_Hoodie"])
        self.recipe(bone="Head", menu="Accessory/Hat", hide=["Hair"])
        removal = self.json_output(self.cli("unity_accessory.py", "remove", *ARGS))
        self.assertNotIn("hide", removal["request"])

    def test_list_and_remove_preview_find_the_accessory_in_saved_scenes(self):
        self.write("Assets/Avatar.unity", "--- !u!1 &1\nGameObject:\n  m_Name: DSH Accessory Hat\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        self.recipe(mode="bone", bone="Head")
        listed = self.json_output(self.cli("unity_accessory.py", "list"))
        self.assertEqual(listed["accessories"][0]["scenes"], ["Assets/Avatar.unity"])
        self.assertEqual(listed["accessories"][0]["bone"], "Head")
        removal = self.json_output(self.cli("unity_accessory.py", "remove", *ARGS))
        self.assertTrue(removal["inScene"])
        self.assertTrue(removal["deletesFiles"])
        kept = self.json_output(self.cli("unity_accessory.py", "remove", *ARGS, "--keep-files"))
        self.assertFalse(kept["deletesFiles"])
        none = self.cli("unity_accessory.py", "remove", *ARGS[:-1], "Nothing")
        self.assertIn("No accessory named Nothing", json.loads(none.stdout)["error"])

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_apply_saves_the_scene_and_the_recipe_folder_does_not_block_later_tasks(self):
        scene = self.write("Assets/Avatar.unity", "original\n")
        self.write("Assets/Items/Hat.prefab", "prefab\n")
        self.recipe(bone="Head", menu="Accessory/Hat")
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        self.recipe(bone="Head", menu="Accessory/Hat", position=[0, 0.02, 0])  # edited after the commit
        unity = self.editor_fixture(r'''
            if (Array.IndexOf(args, "DSH.Editor.DshAccessory.Apply") < 0) Environment.Exit(4);
            Directory.CreateDirectory("Assets/DSH/Accessories/Hat");
            File.WriteAllText("Assets/DSH/Accessories/Hat/Hat_hide.anim", "clip\n");
            File.AppendAllText("Assets/Avatar.unity", "accessory\n");
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"AccessoryApply\",\"verified\":true,\"saved\":true,\"sceneDigest\":\"" +
                Checksum("Assets/Avatar.unity") + "\"}");
        ''')
        plan = self.json_output(self.cli("unity_accessory.py", "preview", *ARGS))
        self.assertEqual(plan["git"]["blockingChanges"], [])
        applied = self.json_output(self.cli("unity_accessory.py", "apply", *ARGS, "--approved-preview",
                                            plan["preview"], env=unity))
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(scene.read_text(), "original\naccessory\n")
        # Blender output in the managed models folder does not block either.
        self.write("Assets/DSH/Models/Ribbon/Ribbon.fbx", "fbx\n")
        shape = self.json_output(self.cli("unity_toggle.py", "preview", "--scene", "Assets/Avatar.unity",
                                          "--avatar", "Avatar", "--outfit", "Avatar/Hoodie", "--menu", "衣装/服"))
        self.assertEqual(shape["git"]["managedScenes"], ["Assets/Avatar.unity"])
        self.assertEqual(shape["git"]["blockingChanges"], [])


if __name__ == "__main__":
    unittest.main()
