import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unity_workflow as base  # noqa: E402


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

    def test_preview_warns_when_variants_on_the_same_texture_can_be_on_together(self):
        self.write("Assets/Avatar.unity", "scene\n")
        env = self.photocraft_env()
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}], name="Skin", exclusiveTag="skin")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 90}], name="Eyes", exclusiveTag="eyes")
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Eyes", env=env))
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Eyes")
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args, env=env))
        self.assertEqual(plan["overlappingVariants"],
                         [{"variant": "Skin", "textures": ["Assets/Tex/Costume.png"], "exclusiveTag": "skin"}])
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 90}], name="Eyes", exclusiveTag="skin")
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Eyes", env=env))
        self.assertNotIn("overlappingVariants", self.json_output(self.cli("unity_texture.py", "preview", *args, env=env)))

    def test_list_reports_render_state_scenes_and_overlaps_without_unity(self):
        env = self.photocraft_env()
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}], name="Skin", exclusiveTag="skin")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 90}], name="Eyes", exclusiveTag="eyes")
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Eyes", env=env))
        self.write("Assets/Avatar.unity", "--- !u!1 &1\nGameObject:\n  m_Name: DSH Color Variant Eyes\n")
        listed = self.json_output(self.cli("unity_texture.py", "list", env=env))
        by_name = {entry["variant"]: entry for entry in listed["variants"]}
        self.assertEqual(by_name["Eyes"]["render"], "current")
        self.assertEqual(by_name["Skin"]["render"], "missing")
        self.assertEqual(by_name["Eyes"]["scenes"], ["Assets/Avatar.unity"])
        self.assertEqual(by_name["Skin"]["scenes"], [])
        self.assertEqual(by_name["Eyes"]["overlappingVariants"], ["Skin"])

    def test_remove_previews_and_refuses_while_other_assets_use_the_variant(self):
        self.write("Assets/Avatar.unity", "--- !u!1 &1\nGameObject:\n  m_Name: DSH Color Variant Hoodie_Blue\n")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}])
        self.write("Assets/DSH/Variants/Hoodie_Blue/Costume.mat", "material")
        self.write("Assets/DSH/Variants/Hoodie_Blue/Costume.mat.meta", "fileFormatVersion: 2\nguid: " + "a" * 32 + "\n")
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hoodie_Blue")
        plan = self.json_output(self.cli("unity_texture.py", "remove", *args))
        self.assertTrue(plan["toggleInScene"] and plan["deletesFiles"])
        self.assertIn("Assets/DSH/Variants/Hoodie_Blue/ (deleted with its .meta files)", plan["plannedPaths"])
        self.write("Assets/Other.prefab", "m_Materials:\n  - {fileID: 2100000, guid: " + "a" * 32 + ", type: 2}\n")
        blocked = self.cli("unity_texture.py", "remove", *args)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(json.loads(blocked.stdout)["otherReferences"],
                         [{"path": "Assets/Other.prefab", "uses": ["Assets/DSH/Variants/Hoodie_Blue/Costume.mat"]}])
        kept = self.json_output(self.cli("unity_texture.py", "remove", *args, "--keep-files"))
        self.assertFalse(kept["deletesFiles"])
        self.assertTrue((self.project / "Assets/DSH/Variants/Hoodie_Blue/recipe.json").exists())

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_remove_deletes_a_committed_variant_and_later_tasks_continue(self):
        scene = self.write("Assets/Avatar.unity", "--- !u!1 &1\nGameObject:\n  m_Name: DSH Color Variant Hoodie_Blue\n")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}])
        env = self.photocraft_env()
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env))
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        unity = self.editor_fixture(r'''
            if (Array.IndexOf(args, "DSH.Editor.DshTextureVariant.Remove") < 0) Environment.Exit(4);
            File.WriteAllText("Assets/Avatar.unity", "removed\n");
            Directory.Delete("Assets/DSH/Variants/Hoodie_Blue", true);
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"TextureVariantRemove\",\"verified\":true,\"saved\":true,\"sceneDigest\":\"" +
                Checksum("Assets/Avatar.unity") + "\"}");
        ''')
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hoodie_Blue")
        plan = self.json_output(self.cli("unity_texture.py", "remove", *args))
        removed = self.json_output(self.cli("unity_texture.py", "remove", *args, "--approved-preview", plan["preview"],
                                            env=unity))
        self.assertTrue(removed["ok"], removed)
        self.assertEqual(scene.read_text(), "removed\n")
        self.assertFalse((self.project / ".dsh/variants/Hoodie_Blue.json").exists())
        self.assertIn(" D", {row["status"] for row in removed["changes"]})  # committed variant files deleted

        toggle = self.json_output(self.cli("unity_toggle.py", "preview", "--scene", "Assets/Avatar.unity",
                                           "--avatar", "Avatar", "--outfit", "Avatar/Hoodie", "--menu", "衣装/服"))
        self.assertEqual(toggle["git"]["blockingChanges"], [])

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


    # --- lilToon material values -------------------------------------------------------

    def material_variant(self, values, name="Hair_Ash", material="Assets/Mat/Hair.mat", create=True, **extra):
        if create and not (self.project / material).exists():
            self.write(material, "material")
        recipe = dict({"name": name, "menu": "色/髪", "materials": [{"material": material, "set": values}]}, **extra)
        self.write(f"Assets/DSH/Variants/{name}/recipe.json", json.dumps(recipe, ensure_ascii=False))

    def test_material_values_become_unity_edits_without_a_render(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.material_variant({"_ShadowColor": "#336699", "_RimColor": [0.5, 1, 2, 0.25],
                               "_MainTexHSVG": {"hue": -0.1, "value": 0.8}, "_UseRim": True, "_ShadowStrength": 0.4})
        rendered = self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hair_Ash"))
        self.assertEqual(rendered["outputs"], [])
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hair_Ash")
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args))
        self.assertEqual(plan["request"]["swaps"], [])
        edits = {edit["property"]: edit for edit in plan["request"]["edits"]}
        self.assertEqual({k: edits["_ShadowColor"][k] for k in "xyzw"} | {"mask": edits["_ShadowColor"]["mask"]},
                         {"x": 0.2, "y": 0.4, "z": 0.6, "w": 0, "mask": 7})  # no alpha: keep the material's
        self.assertEqual([edits["_RimColor"][k] for k in "xyzw"] + [edits["_RimColor"]["mask"]], [0.5, 1, 2, 0.25, 15])
        self.assertEqual((edits["_MainTexHSVG"]["kind"], edits["_MainTexHSVG"]["x"], edits["_MainTexHSVG"]["z"],
                          edits["_MainTexHSVG"]["mask"]), ("hsvg", -0.1, 0.8, 0b101))
        self.assertEqual((edits["_UseRim"]["kind"], edits["_UseRim"]["x"]), ("toggle", 1))
        self.assertEqual((edits["_ShadowStrength"]["kind"], edits["_ShadowStrength"]["x"]), ("float", 0.4))
        self.assertTrue(all(edit["material"] == "Assets/Mat/Hair.mat" for edit in edits.values()))

        listed = self.json_output(self.cli("unity_texture.py", "list"))["variants"][0]
        self.assertEqual((listed["render"], listed["materials"], listed["textures"]),
                         ("not-needed", ["Assets/Mat/Hair.mat"], []))

        # Editing the source material after the preview invalidates the approval token.
        (self.project / "Assets/Mat/Hair.mat").write_text("edited in Unity", encoding="utf-8")
        self.assertNotEqual(self.json_output(self.cli("unity_texture.py", "preview", *args))["preview"], plan["preview"])

    def test_material_recipe_errors_are_reported_at_preview(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Mat/Hair.mat", "material")
        self.write("Assets/Mat/Hair.png", "texture")
        self.write("Assets/DSH/Variants/Other/Copy.mat", "variant material")
        cases = [
            ({"_SrcBlend": 1}, "not a lilToon value"),
            ({"_UseRim": 1}, "true or false"),
            ({"_ShadowStrength": 2}, "from 0 to 1"),
            ({"_ShadowColor": "blue"}, "is a color"),
            ({"_RimColor": [1, 1, 1, 2]}, "is a color"),
            ({"_MainTexHSVG": {"hue": 0.9}}, "hue must be from -0.5 to 0.5"),
            ({"_MainTexHSVG": {"tint": 1}}, "color correction"),
            ({}, "1 to 48"),
        ]
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hair_Ash")
        for values, message in cases:
            self.material_variant(values)
            failed = self.cli("unity_texture.py", "preview", *args)
            self.assertNotEqual(failed.returncode, 0, values)
            self.assertIn(message, json.loads(failed.stdout)["error"])
        for material in ("Assets/Mat/Hair.png", "Assets/DSH/Variants/Other/Copy.mat", "Assets/Mat/Missing.mat"):
            self.material_variant({"_UseRim": True}, material=material, create=False)
            self.assertIn("existing .mat under Assets",
                          json.loads(self.cli("unity_texture.py", "preview", *args).stdout)["error"])
        recipe = {"name": "Hair_Ash", "menu": "色/髪", "materials": [
            {"material": "Assets/Mat/Hair.mat", "set": {"_UseRim": True}},
            {"material": "Assets/Mat/Hair.mat", "set": {"_RimBorder": 0.2}}]}
        self.write("Assets/DSH/Variants/Hair_Ash/recipe.json", json.dumps(recipe))
        self.assertIn("listed twice", json.loads(self.cli("unity_texture.py", "preview", *args).stdout)["error"])
        self.write("Assets/DSH/Variants/Hair_Ash/recipe.json", json.dumps({"name": "Hair_Ash", "menu": "色/髪"}))
        self.assertIn("changes nothing", json.loads(self.cli("unity_texture.py", "preview", *args).stdout)["error"])

    def test_variants_on_the_same_material_are_reported_as_overlapping(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.material_variant({"_UseRim": True}, name="Rim", exclusiveTag="rim")
        self.material_variant({"_ShadowColor": "#000000"}, name="Shade", exclusiveTag="shade")
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Shade")
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args))
        self.assertEqual(plan["overlappingVariants"], [{"variant": "Rim", "textures": [], "exclusiveTag": "rim",
                                                        "materials": ["Assets/Mat/Hair.mat"]}])

    def test_adding_material_values_keeps_an_earlier_texture_render_current(self):
        self.write("Assets/Avatar.unity", "scene\n")
        self.write("Assets/Mat/Hair.mat", "material")
        self.variant([{"op": "hsl", "layer": "Hoodie/Base", "hue": 30}])
        env = self.photocraft_env()
        self.json_output(self.cli("unity_texture.py", "render", "--variant", "Hoodie_Blue", env=env))
        recipe_path = self.project / "Assets/DSH/Variants/Hoodie_Blue/recipe.json"
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["materials"] = [{"material": "Assets/Mat/Hair.mat", "set": {"_OutlineWidth": 0.02}}]
        recipe_path.write_text(json.dumps(recipe, ensure_ascii=False), encoding="utf-8")
        args = ("--scene", "Assets/Avatar.unity", "--avatar", "Avatar", "--variant", "Hoodie_Blue")
        plan = self.json_output(self.cli("unity_texture.py", "preview", *args, env=env))
        self.assertEqual(len(plan["request"]["swaps"]), 1)
        self.assertEqual([edit["property"] for edit in plan["request"]["edits"]], ["_OutlineWidth"])

    def test_python_and_unity_allow_the_same_liltoon_values(self):
        import re
        sys.path.insert(0, str(base.TOOLS))
        import unity_texture
        source = (base.TOOLS.parent / "templates/Editor/DshAvatarTools.cs").read_text(encoding="utf-8")
        block = source[source.index("Allowed = new Dictionary"):]
        block = block[:block.index("};")]
        unity = dict(re.findall(r'\{\s*"(_\w+)",\s*"(\w+)"\s*\}', block))
        self.assertEqual(unity, {name: spec[0] for name, spec in unity_texture.LILTOON.items()})


if __name__ == "__main__":
    unittest.main()
