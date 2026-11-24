import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


TUBE = {"shape": "tube", "points": [[0, 0, 0], [0, -0.05, 0]]}

FAKE_BLENDER = r'''
import json, sys
args = sys.argv[sys.argv.index("--") + 1:]
command, request_path, result_path = args
request = json.load(open(request_path, encoding="utf-8"))
with open(sys.argv[0] + ".calls", "a", encoding="utf-8") as calls:
    calls.write(command + "\n")
if command == "inspect":
    result = {"ok": True, "meshes": [{"name": "Body"}], "armatures": [],
              "asked": {k: request[k] for k in ("shapes", "filter") if k in request}}
else:
    with open(request["output"], "w", encoding="utf-8") as fbx:
        fbx.write("fbx " + request["kind"] + " " + json.dumps(request.get("parts", []))[:40])
    result = {"ok": True, "kind": request["kind"]}
    if any(p.get("sway") for p in request.get("parts", [])):
        result["sway"] = [{"root": "Tail_Sway", "bones": 4}]
json.dump(result, open(result_path, "w", encoding="utf-8"))
'''


class BlenderModelTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output

    def fake_blender(self):
        script = self.write("Library/fake_blender.py", FAKE_BLENDER)
        launcher = self.write("Library/blender.cmd", f'@"{sys.executable}" -B "{script}" %*\n')
        return dict(os.environ, DSH_BLENDER=str(launcher)), Path(str(script) + ".calls")

    def recipe(self, name="Ribbon", **fields):
        self.write(f"Assets/DSH/Models/{name}/recipe.json", json.dumps(dict({"name": name}, **fields)))

    def build(self, name="Ribbon", env=None):
        return self.cli("blender_model.py", "build", "--model", name, "--no-preview", env=env)

    def test_recipe_errors_are_reported_before_blender_runs(self):
        env, calls = self.fake_blender()
        self.write("Assets/Items/Outfit.fbx", "fbx\n")
        cases = [
            ({}, "'kind'"),
            ({"kind": "make"}, "'parts'"),
            ({"kind": "make", "parts": [{"shape": "star"}]}, "'shape'"),
            ({"kind": "make", "parts": [{"shape": "cube", "size": [0, 1, 1]}]}, "size"),
            ({"kind": "make", "parts": [{"shape": "cube", "color": "red"}]}, "#RRGGBB"),
            ({"kind": "make", "parts": [{"shape": "cube", "position": [0, 5, 0]}]}, "position"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Missing.fbx"}, "does not exist"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.png", "avatar": "Assets/Items/Outfit.fbx"}, ".fbx or .blend"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "weights": "auto"}, "'weights'"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "push": 0.5}, "push"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "scale": 3}, "scale"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "offset": [0, 1, 0]}, "offset"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "source": "Assets/Items/Missing.fbx"}, "source file does not exist"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "avatarShapes": {"Breasts_big": 150}}, "'avatarShapes'"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "sourceShapes": ["Breasts_big"]}, "'sourceShapes'"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "followShapes": ["Waist_slim", "Waist_slim"]}, "'followShapes'"),
            ({"kind": "fit", "outfit": "Assets/Items/Outfit.fbx", "avatar": "Assets/Items/Outfit.fbx",
              "sourceBody": 3}, "'sourceBody'"),
            ({"kind": "make", "parts": [{"shape": "tube"}]}, "points"),
            ({"kind": "make", "parts": [dict(TUBE, name="Tail"), dict(TUBE, name="Tail")]}, "must differ"),
            ({"kind": "make", "parts": [{"shape": "tube", "points": [[0, 0, 0]]}]}, "points"),
            ({"kind": "make", "parts": [dict(TUBE, section="square")]}, "'section'"),
            ({"kind": "make", "parts": [dict(TUBE, closed=True)]}, "at least 3"),
            ({"kind": "make", "parts": [dict(TUBE, sway=9)]}, "sway"),
            ({"kind": "make", "parts": [dict(TUBE, points=[[0, 0, 0], [0, 1, 0], [1, 0, 0]], closed=True, sway=2)]},
             "cannot sway"),
            ({"kind": "make", "parts": [{"shape": "lathe", "profile": [[-0.1, 0], [0, 0.1]]}]}, "negative"),
            ({"kind": "make", "parts": [{"shape": "extrude", "outline": "moon"}]}, "'outline'"),
            ({"kind": "make", "parts": [{"shape": "extrude", "outline": [[0, 0], [1, 0]]}]}, "outline"),
            ({"kind": "make", "parts": [{"shape": "cube", "mirror": "yes"}]}, "mirror"),
            ({"kind": "make", "parts": [{"shape": "cube", "subdivide": 5}]}, "subdivide"),
            ({"kind": "make", "parts": [dict(TUBE, conform="surface")]}, "'avatar'"),
            ({"kind": "make", "parts": [{"shape": "cube"}], "snap": True}, "'snap' needs"),
            ({"kind": "make", "avatar": "Assets/Items/Outfit.fbx", "parts": [{"shape": "cube", "conform": "surface"}]},
             "for tubes"),
            ({"kind": "make", "avatar": "Assets/Items/Outfit.fbx", "parts": [{"shape": "cube", "conform": "glue"}]},
             "'conform'"),
            ({"kind": "make", "avatar": "Assets/Items/Outfit.fbx", "bone": "Hat", "parts": [{"shape": "cube"}]}, "'bone'"),
            ({"kind": "make", "avatar": "Assets/Items/Outfit.fbx", "toward": [0, 0, 0], "parts": [{"shape": "cube"}]},
             "'toward'"),
            ({"kind": "make", "avatar": "Assets/Items/Outfit.fbx", "gap": 0.5, "parts": [{"shape": "cube"}]}, "gap"),
        ]
        for fields, message in cases:
            self.recipe(**fields)
            failed = self.build(env=env)
            self.assertNotEqual(failed.returncode, 0, fields)
            self.assertIn(message, json.loads(failed.stdout)["error"], fields)
        self.assertFalse(calls.exists())
        missing = self.build("Other", env=env)
        self.assertIn("Write the recipe first", json.loads(missing.stdout)["error"])

    def test_missing_blender_is_reported(self):
        self.recipe(kind="make", parts=[{"shape": "cube"}])
        env = dict(os.environ, DSH_BLENDER=str(self.project / "nope" / "blender.exe"))
        failed = self.build(env=env)
        self.assertIn("DSH_BLENDER points to a missing file", json.loads(failed.stdout)["error"])

    def test_build_writes_the_fbx_and_tracks_whether_it_is_current(self):
        env, calls = self.fake_blender()
        self.recipe(kind="make", parts=[{"shape": "sphere", "size": [0.03, 0.03, 0.03], "color": "#e05a7a"}])
        built = self.json_output(self.build(env=env))
        self.assertEqual(built["output"], "Assets/DSH/Models/Ribbon/Ribbon.fbx")
        fbx = self.project / built["output"]
        self.assertTrue(fbx.read_text().startswith("fbx make"))
        self.assertEqual(list((self.project / "Assets/DSH/Models/Ribbon").glob("*.partial*")), [])
        listed = self.json_output(self.cli("blender_model.py", "list"))
        self.assertEqual(listed["models"][0]["fbx"], "current")

        self.recipe(kind="make", parts=[{"shape": "cube"}])
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "stale")
        self.json_output(self.build(env=env))

        fbx.write_text("edited by hand")
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "edited")
        refused = self.build(env=env)
        self.assertIn("changed outside this tool", json.loads(refused.stdout)["error"])
        self.assertEqual(fbx.read_text(), "edited by hand")
        self.assertEqual(calls.read_text().split(), ["make", "make"])

    def test_fit_passes_the_source_avatar_and_shapes_and_tracks_the_source_file(self):
        env, calls = self.fake_blender()
        self.write("Assets/Items/Outfit.fbx", "outfit\n")
        self.write("Assets/Items/Avatar.fbx", "avatar\n")
        source = self.write("Assets/Items/Source.fbx", "source\n")
        self.recipe("Coat_Fit", kind="fit", outfit="Assets/Items/Outfit.fbx", avatar="Assets/Items/Avatar.fbx",
                    source="Assets/Items/Source.fbx", avatarShapes={"Breasts_big": 40},
                    followShapes=["Waist_slim"])
        self.json_output(self.build("Coat_Fit", env=env))
        request = json.loads(next((self.project / ".dsh/runs").glob("*/request.json")).read_text(encoding="utf-8"))
        self.assertEqual(Path(request["source"]), self.project / "Assets/Items/Source.fbx")
        self.assertEqual(request["avatarShapes"], {"Breasts_big": 40.0})
        self.assertEqual(request["followShapes"], ["Waist_slim"])
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "current")
        source.write_text("source changed\n")
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "stale")
        self.assertEqual(calls.read_text().split(), ["fit"])

    def test_make_on_the_avatar_passes_placement_and_tracks_the_avatar_file(self):
        env, calls = self.fake_blender()
        avatar = self.write("Assets/Items/Avatar.fbx", "avatar\n")
        self.recipe("Bow", kind="make", avatar="Assets/Items/Avatar.fbx", bone="Head", snap=True, toward=[0, 0, 1],
                    parts=[{"shape": "sphere", "size": [0.02, 0.02, 0.02]},
                           dict(TUBE, section="flat", mirror=True, sway=True, conform="surface")])
        built = self.json_output(self.build("Bow", env=env))
        self.assertIn("physBones", built["next"])
        self.assertIn("Tail_Sway", built["next"])
        request = json.loads(next((self.project / ".dsh/runs").glob("*/request.json")).read_text(encoding="utf-8"))
        self.assertEqual(Path(request["avatar"]), self.project / "Assets/Items/Avatar.fbx")
        self.assertEqual((request["bone"], request["snap"], request["toward"], request["gap"], request["push"]),
                         ("Head", True, [0, 0, 1], 0.001, True))
        sphere, tube = request["parts"]
        self.assertEqual((tube["sway"], tube["section"], tube["mirror"], tube["conform"]), (4, "flat", True, "surface"))
        self.assertEqual(sphere["conform"], "")
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "current")
        avatar.write_text("avatar changed\n")
        self.assertEqual(self.json_output(self.cli("blender_model.py", "list"))["models"][0]["fbx"], "stale")
        self.assertEqual(calls.read_text().split(), ["make"])

    def test_fit_scale_is_automatic_unless_a_number_is_given(self):
        env, calls = self.fake_blender()
        self.write("Assets/Items/Hair.fbx", "hair\n")
        self.write("Assets/Items/Avatar.fbx", "avatar\n")
        self.recipe("Hair_Fit", kind="fit", outfit="Assets/Items/Hair.fbx", avatar="Assets/Items/Avatar.fbx")
        self.json_output(self.build("Hair_Fit", env=env))
        runs = sorted((self.project / ".dsh/runs").glob("*/request.json"), key=lambda p: p.stat().st_mtime)
        self.assertEqual(json.loads(runs[-1].read_text(encoding="utf-8"))["scale"], "auto")
        self.recipe("Hair_Fit", kind="fit", outfit="Assets/Items/Hair.fbx", avatar="Assets/Items/Avatar.fbx", scale=1.1)
        self.json_output(self.build("Hair_Fit", env=env))
        runs = sorted((self.project / ".dsh/runs").glob("*/request.json"), key=lambda p: p.stat().st_mtime)
        self.assertEqual(json.loads(runs[-1].read_text(encoding="utf-8"))["scale"], 1.1)
        self.recipe("Hair_Fit", kind="fit", outfit="Assets/Items/Hair.fbx", avatar="Assets/Items/Avatar.fbx", scale="big")
        self.assertIn("'scale'", json.loads(self.build("Hair_Fit", env=env).stdout)["error"])

    def test_inspect_reads_a_project_file(self):
        env, calls = self.fake_blender()
        self.write("Assets/Items/Outfit.fbx", "fbx\n")
        result = self.json_output(self.cli("blender_model.py", "inspect", "Assets/Items/Outfit.fbx",
                                           "--project", str(self.project), env=env))
        self.assertEqual(result["meshes"], [{"name": "Body"}])
        self.assertEqual(result["asked"], {})
        shapes = self.json_output(self.cli("blender_model.py", "inspect", "Assets/Items/Outfit.fbx", "--project",
                                           str(self.project), "--shapes", "Body_base", "--filter", "OFF", env=env))
        self.assertEqual(shapes["asked"], {"shapes": "Body_base", "filter": "OFF"})
        self.assertEqual(calls.read_text().split(), ["inspect", "inspect"])


if __name__ == "__main__":
    unittest.main()
