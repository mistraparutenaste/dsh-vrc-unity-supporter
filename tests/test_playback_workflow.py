"""Playback tests: the states and expectations sent to Unity (Unity itself is not needed here)."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402

sys.path.insert(0, str(base.TOOLS))
import unity_playback  # noqa: E402
from unity_toggle import WorkflowError  # noqa: E402

SCENE = "Assets/Avatar.unity"


class PlaybackTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli

    def test_states_are_checked_and_converted(self):
        states = unity_playback.load_states({"states": [
            {"label": "smile", "gesture": {"right": "Fist", "left": "Neutral"},
             "expect": [{"path": "@face", "shape": "smile", "min": 90}]},
            {"label": "hat off", "menu": ["!Props/Hat"], "parameters": {"Hoodie": False, "Hair": 2},
             "expect": [{"path": "**/Hat", "active": False}, {"path": "**/Cup", "freezeToWorld": True}]},
        ]})
        self.assertEqual((states[0]["gestureRight"], states[0]["gestureLeft"]), (1, 0))
        self.assertEqual(states[0]["expect"], [{"path": "@face", "shape": "smile", "min": 90.0}])
        self.assertEqual(states[1]["parameters"], [{"name": "Hoodie", "value": 0.0}, {"name": "Hair", "value": 2.0}])
        self.assertEqual(states[1]["expect"][0], {"path": "**/Hat", "active": "false"})
        self.assertEqual(states[1]["expect"][1], {"path": "**/Cup", "freezeToWorld": "true"})
        for bad, message in [({"states": []}, "1 to"), ({"states": [{"label": "x", "gesture": {"right": "Wave"}}]}, "gesture.right"),
                             ({"states": [{"label": "x", "expect": [{"path": "a"}]}]}, "'shape'"),
                             ({"states": [{"label": "x", "menu": ["!"]}]}, "menu paths")]:
            with self.assertRaises(WorkflowError) as raised:
                unity_playback.load_states(bad)
            self.assertIn(message, str(raised.exception))

    def test_auto_states_come_from_the_dsh_changes_on_the_avatar(self):
        self.write(SCENE, "  m_Name: DSH Expression Face\n  m_Name: DSH Accessory Cup\n")
        self.write("Assets/Cup.prefab", "prefab\n")
        self.write("Assets/DSH/Expressions/Face/recipe.json", json.dumps({
            "name": "Face", "menu": "Face", "gestures": [{"hand": "right", "gesture": "Peace", "shapes": {"smile": 80}}],
            "locks": [{"name": "Jito", "shapes": {"jito": 100}}]}))
        self.write("Assets/DSH/Accessories/Cup/recipe.json", json.dumps({
            "name": "Cup", "asset": "Assets/Cup.prefab", "mode": "bone", "bone": "RightHand", "menu": "Props/Cup",
            "hold": {"drop": "Props/Put down"}}))
        for number, (task, key, name) in enumerate([("ExpressionApply", "expression", "Face"),
                                                     ("AccessoryApply", "accessory", "Cup")]):
            self.write(f".dsh/outfits/{number}.json", json.dumps({"scene": SCENE, "output": {"ok": True, "unity": {
                "task": task, key: name, "avatar": {"path": "Avatar"}}}}))
        spec = unity_playback.auto_states(self.project, SCENE, "Avatar")
        labels = [s["label"] for s in spec["states"]]
        self.assertEqual(labels, ["Cup: on", "Cup: off", "Cup: put down", "Face: right Peace", "Face: Jito"])
        self.assertEqual(spec["states"][2]["expect"], [{"path": "**/Cup", "freezeToWorld": True}])
        self.assertEqual(spec["states"][3]["expect"], [{"path": "@face", "shape": "smile", "min": 79.0, "max": 81.0}])
        self.assertEqual(spec["states"][4]["menu"], ["Face/Jito"])
        unity_playback.load_states(spec)  # the generated states pass the same checks

        failed = self.cli("unity_playback.py", "test", "--scene", SCENE)
        self.assertIn("--spec", json.loads(failed.stdout)["error"])

    def test_mixing_reports_face_shapes_the_recipe_does_not_set(self):
        spec = {"states": [{"label": "Face: right Fist", "recipeShapes": ["smile"], "fix": "Face: gesture right Fist"},
                           {"label": "hat"}]}
        output = {"unity": {"states": [
            {"label": "Face: right Fist", "checks": [{"resolved": "Body:smile"}],
             "changedShapes": ["Body:smile: 0 -> 100", "Body:eye_close: 0 -> 100", "Hair:wind: 0 -> 5"]},
            {"label": "hat", "changedShapes": ["Body:x: 0 -> 1"]}]}}
        hints = unity_playback.mixed_shapes(output, spec)
        self.assertEqual([(h["state"], h["mixedShapes"]) for h in hints], [("Face: right Fist", ["eye_close"])])
        self.assertEqual(output["unity"]["states"][0]["mixedShapes"], ["eye_close"])

if __name__ == "__main__":
    unittest.main()
