"""Carrying DSH changes over to a new version of an avatar (the Python side; Unity is not needed)."""

import json
import os
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402

sys.path.insert(0, str(base.TOOLS))
import unity_migrate  # noqa: E402

SCENE = "Assets/Avatar.unity"


class MigrateTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output

    def receipt(self, number, task, **unity):
        path = self.write(f".dsh/outfits/{number:04d}.json", json.dumps({
            "scene": SCENE, "output": {"ok": True, "unity": dict({"task": task, "avatar": {"path": "Avatar"}}, **unity)}}))
        stamp = time.time() - 1000 + number
        os.utime(path, (stamp, stamp))

    def test_inventory_keeps_what_is_still_in_the_scene(self):
        self.write(SCENE, "--- !u!1 &1\nGameObject:\n  m_Name: DSH Accessory Hat\n"
                          "--- !u!1 &2\nGameObject:\n  m_Name: DSH Outfit Toggle 123\n")
        self.receipt(1, "AccessoryApply", accessory="Hat")
        self.receipt(2, "AccessoryApply", accessory="Bag")          # not in the scene any more (restored from Git)
        self.receipt(3, "OutfitToggle", holder="DSH Outfit Toggle 123", outfit="Avatar/Hoodie", menu="Outfit/Hoodie",
                     defaultOn=True)
        self.receipt(4, "PhysBoneRecipe", recipe="Soft")
        self.receipt(5, "PhysBoneRecipe", recipe="Gone")
        self.receipt(6, "PhysBoneRemove", recipe="Gone")            # removed later
        self.receipt(7, "ShapeRecipe", recipe="Old")                # applied before records existed
        self.receipt(8, "ExpressionApply", expression="Face", avatar={"path": "Other"})  # another avatar
        self.write(".dsh/physbones/Soft.json", json.dumps({"scenes": {SCENE: [{"key": "a", "kind": "value"}]}}))
        items = unity_migrate.inventory(self.project, SCENE, "Avatar")
        self.assertEqual(items, [
            {"kind": "shape", "name": "Old", "unverified": True},
            {"kind": "accessory", "name": "Hat"},
            {"kind": "physbone", "name": "Soft"},
            {"kind": "toggle", "name": "DSH Outfit Toggle 123", "outfit": "Avatar/Hoodie", "menu": "Outfit/Hoodie",
             "defaultOn": True},
        ])
        output = self.json_output(self.cli("unity_migrate.py", "inventory", "--scene", SCENE, "--avatar", "Avatar"))
        self.assertEqual(len(output["changes"]), 4)

    def test_checks_report_missing_names_with_close_candidates(self):
        self.write("Assets/DSH/Shapes/Fit/recipe.json", json.dumps({
            "name": "Fit", "weights": [{"renderer": "Body", "shape": "Breasts_big", "weight": 50}],
            "remove": [{"renderer": "Body", "shapes": ["Chest_OFF"]}]}))
        info = {"paths": ["Body", "Hair_v2", "Armature/Hips"], "renderers": {"Body": ["Breast_big", "Chest_OFF"]},
                "humanoidBones": {"Hips": "Armature/Hips"}}
        check = unity_migrate.Check(info)
        unity_migrate.check_item(self.project, {"kind": "shape", "name": "Fit"}, check, "Avatar", "Avatar_v2")
        self.assertEqual(check.problems, [{"missing": "shape key", "name": "Body:Breasts_big", "suggest": ["Breast_big"]}])

        self.write("Assets/Hat.prefab", "prefab\n")
        self.write("Assets/DSH/Accessories/Hat/recipe.json", json.dumps({
            "name": "Hat", "asset": "Assets/Hat.prefab", "mode": "bone", "bone": "Head", "menu": "Hat", "hide": ["Hair"]}))
        check = unity_migrate.Check(info)
        unity_migrate.check_item(self.project, {"kind": "accessory", "name": "Hat"}, check, "Avatar", "Avatar_v2")
        self.assertEqual([p["missing"] for p in check.problems], ["humanoid bone", "object to hide"])
        self.assertEqual(check.problems[1]["suggest"], ["Hair_v2"])

        toggle = {"kind": "toggle", "name": "DSH Outfit Toggle 1", "outfit": "Avatar/Armature/Hips", "menu": "X"}
        check = unity_migrate.Check(info)
        unity_migrate.check_item(self.project, toggle, check, "Avatar", "Avatar_v2")
        self.assertEqual((check.problems, toggle["newOutfit"]), ([], "Avatar_v2/Armature/Hips"))

    def test_hand_made_overrides_leave_out_what_dsh_recorded(self):
        self.write(".dsh/physbones/Soft.json", json.dumps({"scenes": {SCENE: [
            {"key": "v", "kind": "value", "path": "PB/Hair", "field": "pull"},
            {"key": "u", "kind": "uses", "path": "PB/Skirt", "other": "Armature/Hips/DSH Collider Soft Leg"}]}}))
        self.write(".dsh/shapes/Fit.json", json.dumps({"scenes": {SCENE: {
            "weights": [{"renderer": "Body", "shape": "Breasts_big", "weight": 0}]}}}))
        items = [{"kind": "physbone", "name": "Soft"}, {"kind": "shape", "name": "Fit"}]
        data = {"values": [
            {"path": "PB/Hair", "property": "pull", "value": "0.1"},
            {"path": "PB/Skirt", "property": "colliders.Array.size", "value": "1"},
            {"path": "Body", "property": "blendShape.Breasts_big", "value": "60"},
            {"path": "Body", "property": "blendShape.Waist_slim", "value": "30"},         # by hand
            {"path": "Armature/Hips/DSH Collider Soft Leg", "property": "radius", "value": "1"},
        ], "addedComponents": [{"path": "Body", "type": "RemoveMeshByBlendShape"}, {"path": "Hair", "type": "Light"}],
            "addedObjects": ["DSH Accessory Hat", "Props"]}
        manual = unity_migrate.manual_overrides(self.project, data, SCENE, items)
        self.assertEqual(manual["values"], [{"path": "Body", "property": "blendShape.Waist_slim", "value": "30"}])
        self.assertEqual(manual["addedComponents"], [{"path": "Hair", "type": "Light"}])
        self.assertEqual(manual["addedObjects"], ["Props"])

    def test_steps_turn_into_each_workflows_arguments(self):
        args = unity_migrate.tool_args({"kind": "toggle", "name": "DSH Outfit Toggle 1", "newOutfit": "V2/Hoodie",
                                        "menu": "Outfit/Hoodie", "defaultOn": True}, "Assets/V2.unity", "V2", True)
        self.assertEqual(args, ["--scene", "Assets/V2.unity", "--avatar", "V2", "--outfit", "V2/Hoodie", "--menu",
                                "Outfit/Hoodie", "--default-on", "--verify-sdk"])
        self.assertEqual(unity_migrate.tool_args({"kind": "variant", "name": "Blue"}, "S", "A", False)[-2:],
                         ["--variant", "Blue"])
        self.assertEqual(list(unity_migrate.ORDER), ["shape", "accessory", "physbone", "proportion", "toggle",
                                                     "variant", "expression", "polygon", "quest", "menu"])


if __name__ == "__main__":
    unittest.main()
