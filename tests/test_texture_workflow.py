import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import test_unity_workflow as base


GIT_IDENTITIES = base.GIT_IDENTITIES

# A stand-in for photocraft-cli: `info` prints a fixed layer tree, `run` logs its commands and writes --out.
FAKE_PHOTOCRAFT = r'''
import json, os, sys
args = sys.argv[1:]
if args[0] == "info":
    print(open(os.environ["FAKE_PHOTOCRAFT_INFO"], encoding="utf-8").read())
elif args[0] == "run":
    out = args[args.index("--out") + 1]
    commands = [(args[i + 1], json.loads(args[i + 3])) for i, a in enumerate(args) if a == "--cmd"]
    with open(os.environ["FAKE_PHOTOCRAFT_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps({"source": args[1], "commands": commands}) + "\n")
    open(out, "wb").write(b"PNG" + json.dumps(commands).encode())
else:
    sys.exit(2)
'''

LAYERS = {"width": 1000, "height": 500, "layers": [
    {"id": 9, "name": "UV", "kind": "Pixel", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1.0},
    {"id": 8, "name": "Hoodie", "kind": "Group", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1.0,
     "children": [
         {"id": 7, "name": "Line", "kind": "Pixel", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1},
         {"id": 6, "name": "Line", "kind": "Pixel", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1},
         {"id": 5, "name": "Base", "kind": "Pixel", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1},
     ]},
    {"id": 2, "name": "Background", "kind": "Pixel", "visible": True, "blend": "Normal", "clipped": False, "opacity": 1},
]}


class TextureWorkflowTests(unittest.TestCase):
    setUp = base.UnityWorkflowTests.setUp
    write = base.UnityWorkflowTests.write
    cli = base.UnityWorkflowTests.cli
    json_output = base.UnityWorkflowTests.json_output
    git = base.UnityWorkflowTests.git
    editor_fixture = base.UnityWorkflowTests.editor_fixture

    def photocraft_env(self, extra=None):
        tools = Path(tempfile.mkdtemp(prefix="dsh fake "))
        self.addCleanup(lambda: [p.unlink() for p in tools.iterdir()] and tools.rmdir())
        (tools / "photocraft.py").write_text(FAKE_PHOTOCRAFT, encoding="utf-8")
        (tools / "info.json").write_text(json.dumps(LAYERS), encoding="utf-8")
        self.log = tools / "log.jsonl"
        return dict(os.environ, **(extra or {}), PHOTOCRAFT_CLI=str(tools / "photocraft.py"),
                    FAKE_PHOTOCRAFT_INFO=str(tools / "info.json"), FAKE_PHOTOCRAFT_LOG=str(self.log))

    def variant(self, ops, name="Hoodie_Blue", **extra):
        psd = self.write("Source/衣装.psd", "layered")
        self.write("Assets/Tex/Costume.png", "original texture")
        recipe = dict({"name": name, "menu": "色/青", "textures": [
            {"replace": "Assets/Tex/Costume.png", "psd": "Source/衣装.psd", "ops": ops}]}, **extra)
        self.write(f"Assets/DSH/Variants/{name}/recipe.json", json.dumps(recipe, ensure_ascii=False))
        return psd

    def logged(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_psd_lists_layer_paths_uv_layers_and_duplicates_with_a_cap(self):
        psd = self.write("Source/a.psd", "layered")
        env = self.photocraft_env()
        listed = self.json_output(self.cli("unity_texture.py", "psd", str(psd), "--max-layers", "3", env=env))
        self.assertEqual(listed["layerCount"], 6)
        self.assertTrue(listed["truncated"])
        self.assertEqual([layer["path"] for layer in listed["layers"]], ["UV", "Hoodie", "Hoodie/Line"])
        self.assertEqual(listed["uvLayers"], ["UV"])
        self.assertEqual(listed["duplicatePaths"], ["Hoodie/Line"])
        self.assertEqual(listed["sha256"], hashlib.sha256(b"layered").hexdigest())

    def test_render_translates_the_recipe_and_keeps_the_source_psd(self):
        logo = self.write("Assets/DSH/Variants/Hoodie_Blue/logo.png", "logo")
        psd = self.variant([
            {"op": "hsl", "layer": "Hoodie/Base", "colorize": True, "hue": 210, "saturation": 50},
            {"op": "visibility", "layer": "Hoodie/Line#1", "visible": False},
            {"op": "place", "image": "logo.png", "above": "Hoodie/Base", "uv": [0.25, 0.2], "scale": 20},
        ])
        env = self.photocraft_env()
        output = self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env))
        commands = self.logged()[0]["commands"]
        self.assertEqual(commands[0], ["layer.setProps", {"layer": 9, "visible": False}])  # UV hidden first
        self.assertEqual(commands[1], ["layer.select", {"layer": 5}])
        self.assertEqual(commands[2][0], "layer.newAdjustmentLayer.hueSaturation")
        self.assertTrue(commands[2][1]["colorize"] and commands[2][1]["clipToPrevious"])
        self.assertEqual(commands[3], ["layer.setProps", {"layer": 6, "visible": False}])
        self.assertEqual(commands[5][1]["center"], [250, 400])  # UV origin is bottom-left
        self.assertEqual(commands[5][1]["path"], str(logo.resolve()))
        self.assertEqual(commands[6][0], "layer.createClippingMask")
        rendered = self.project / output["outputs"][0]["texture"]
        self.assertEqual(rendered.relative_to(self.project).as_posix(), "Assets/DSH/Variants/Hoodie_Blue/Costume.png")
        self.assertEqual(psd.read_text(encoding="utf-8"), "layered")

    def test_recipe_errors_are_reported_before_photocraft_runs(self):
        cases = [
            ([{"op": "visibility", "layer": "Hoodie/Line", "visible": False}], "#0..#1"),
            ([{"op": "hsl", "layer": "Hoodie/Missing"}], "Layer not found"),
            ([{"op": "blur", "layer": "Hoodie/Base"}], "Unknown operation"),
            ([{"op": "hsl", "layer": "Hoodie/Base", "hue": 400}], "'hue'"),
            ([{"op": "place", "image": "missing.png", "above": "Hoodie/Base", "uv": [0, 0]}], "image file"),
        ]
        env = self.photocraft_env()
        for ops, message in cases:
            self.variant(ops)
            failed = self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(message, json.loads(failed.stdout)["error"])
        self.assertFalse((self.project / "Assets/DSH/Variants/Hoodie_Blue/Costume.png").exists())

    def test_changed_psd_and_textures_outside_assets_are_refused(self):
        env = self.photocraft_env()
        self.variant([])
        recipe_path = self.project / "Assets/DSH/Variants/Hoodie_Blue/recipe.json"
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["textures"][0]["sha256"] = "0" * 64
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        failed = self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env)
        self.assertIn("PSD changed", json.loads(failed.stdout)["error"])
        recipe["textures"][0].pop("sha256")
        recipe["textures"][0]["replace"] = "Source/衣装.psd"
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        failed = self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env)
        self.assertIn("under Assets", json.loads(failed.stdout)["error"])

    def test_preview_requires_a_current_render(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}])
        env = self.photocraft_env()
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hoodie_Blue")
        self.assertIn("Render the variant first",
                      json.loads(self.cli("unity_texture.py", "preview", *args, env=env).stdout)["error"])
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env))
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args, env=env))
        self.assertEqual(plan["request"]["swaps"],
                         [{"from": "Assets/Tex/Costume.png", "to": "Assets/DSH/Variants/Hoodie_Blue/Costume.png"}])
        (self.project / "Assets/DSH/Variants/Hoodie_Blue/Costume.png").write_bytes(b"edited")
        self.assertIn("changed after rendering",
                      json.loads(self.cli("unity_texture.py", "preview", *args, env=env).stdout)["error"])

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_apply_saves_the_variant_and_a_later_outfit_toggle_continues_on_that_scene(self):
        scene = self.write("Assets/Avatar.unity", "original\n")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}])
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        env = self.photocraft_env()
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env))
        unity = self.editor_fixture(r'''
            if (Array.IndexOf(args, "DSH.Editor.DshTextureVariant.Apply") < 0) Environment.Exit(4);
            File.AppendAllText("Assets/Avatar.unity", "variant\n");
            Directory.CreateDirectory("Assets/DSH/Variants/Hoodie_Blue");
            File.WriteAllText("Assets/DSH/Variants/Hoodie_Blue/Costume.mat", "material");
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"TextureVariant\",\"verified\":true,\"saved\":true,\"sceneDigest\":\"" +
                Checksum("Assets/Avatar.unity") + "\"}");
        ''')
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hoodie_Blue")
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args, env=env))
        self.assertEqual(plan["git"]["blockingChanges"], [])  # rendered files in the variant folder are managed
        applied = self.json_output(self.cli("unity_texture.py", "apply", *args, "--approved-preview", plan["preview"],
                                            env=dict(unity, **{k: env[k] for k in env if k.startswith(("PHOTOCRAFT", "FAKE"))})))
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(scene.read_text(), "original\nvariant\n")

        toggle = self.json_output(self.cli("unity_toggle.py", "preview", "--scene", "Assets/Avatar.unity",
                                           "--avatar", "Avatar", "--outfit", "Avatar/Hoodie", "--menu", "衣装/服"))
        self.assertEqual(toggle["git"]["managedScenes"], ["Assets/Avatar.unity"])
        self.assertEqual(toggle["git"]["blockingChanges"], [])


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    unittest.main()
