#!/usr/bin/env python3
"""Carry the changes DSH made to an avatar over to a new version of it (an updated avatar package).

inventory  what DSH changed on the avatar (from the receipts in .dsh), and optionally the prefab overrides made
           by hand, which are listed for the user to redo and never copied automatically.
plan       read the new avatar in Unity and check, change by change, that the meshes, shape keys, bones, objects
           and materials each recipe uses are there; suggest close names for missing ones.
apply      re-apply the changes that are ready, in a fixed order, through each workflow's own preview and apply.
"""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


TOOLS = Path(__file__).resolve().parent
HELPER = "DshMigrate"
# Unity task name -> (kind, apply or remove)
TASKS = {
    "OutfitToggle": ("toggle", "apply"), "OutfitToggleRemove": ("toggle", "remove"),
    "TextureVariant": ("variant", "apply"), "TextureVariantRemove": ("variant", "remove"),
    "ShapeRecipe": ("shape", "apply"), "ShapeRemove": ("shape", "remove"),
    "AccessoryApply": ("accessory", "apply"), "AccessoryRemove": ("accessory", "remove"),
    "PhysBoneRecipe": ("physbone", "apply"), "PhysBoneRemove": ("physbone", "remove"),
    "ProportionRecipe": ("proportion", "apply"), "ProportionRemove": ("proportion", "remove"),
    "ExpressionApply": ("expression", "apply"), "ExpressionRemove": ("expression", "remove"),
}
# Re-applied in this order: body shape and attachments first, then what refers to them.
ORDER = ("shape", "accessory", "physbone", "proportion", "toggle", "variant", "expression")
TOOL = {"shape": "unity_shape.py", "accessory": "unity_accessory.py", "physbone": "unity_physbone.py",
        "proportion": "unity_proportion.py", "toggle": "unity_toggle.py", "variant": "unity_texture.py",
        "expression": "unity_expression.py"}
HOLDERS = {"toggle": "DSH Outfit Toggle ", "variant": "DSH Color Variant ", "accessory": "DSH Accessory ",
           "expression": "DSH Expression "}
RECORDS = {"shape": ".dsh/shapes", "physbone": ".dsh/physbones", "proportion": ".dsh/proportions"}


def avatar_path(unity):
    avatar = unity.get("avatar")
    if isinstance(avatar, dict):
        return avatar.get("path", "")
    return avatar if isinstance(avatar, str) else ""


def item_name(kind, unity):
    for key in ("recipe", "accessory", "expression", "variant", "holder"):
        value = unity.get(key)
        if isinstance(value, str) and value:
            prefix = HOLDERS.get(kind, "")
            return value[len(prefix):] if prefix and value.startswith(prefix) and kind != "toggle" else value
    return ""


def inventory(root, scene_path, avatar):
    """The DSH changes in force on one avatar of one scene: the last receipt per change, kept only while the scene
    still shows it (the holder object, or the change's record for that scene)."""
    folder = inside(root, ".dsh/outfits")
    receipts = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    state = {}
    for file in receipts:
        receipt = toggle.read_result(file)
        output = receipt.get("output") if isinstance(receipt.get("output"), dict) else {}
        unity = output.get("unity") if isinstance(output.get("unity"), dict) else {}
        kind_action = TASKS.get(unity.get("task"))
        if not kind_action or not output.get("ok") or (receipt.get("scene") or unity.get("scene")) != scene_path:
            continue
        if avatar and avatar_path(unity) not in ("", avatar):
            continue
        kind, action = kind_action
        name = item_name(kind, unity)
        if not name:
            continue
        if action == "remove":
            state.pop((kind, name), None)
            continue
        entry = {"kind": kind, "name": name}
        if kind == "toggle":
            entry.update({key: unity.get(key) for key in ("outfit", "menu", "defaultOn", "exclusiveTag")
                          if unity.get(key) not in (None, "")})
        state[(kind, name)] = entry
    holders = toggle.scene_holders(root, "DSH ").get(scene_path, [])
    items = []
    for (kind, name), entry in state.items():
        if kind in HOLDERS:
            holder = name if kind == "toggle" else HOLDERS[kind] + name
            if holder not in holders:
                continue
        else:
            record = toggle.read_result(inside(root, f"{RECORDS[kind]}/{name}.json"))
            if not (record.get("scenes") or {}).get(scene_path):
                # Applied before this release kept records (or in another copy): the receipt says it is in force,
                # but the scene cannot show it. It can still be applied again from its recipe.
                entry["unverified"] = True
        items.append(entry)
    return sorted(items, key=lambda e: (ORDER.index(e["kind"]), e["name"]))


DSH_COMPONENTS = {"ModularAvatarBlendshapeSync", "RemoveMeshByBlendShape", "ModularAvatarScaleAdjuster",
                  "VRCPhysBoneCollider"}


def own_changes(root, scene_path, items):
    """What DSH records as its own in this scene, to tell hand-made overrides apart."""
    owned = set()
    for item in items:
        if item["kind"] in RECORDS:
            record = toggle.read_result(inside(root, f"{RECORDS[item['kind']]}/{item['name']}.json"))
            undo = (record.get("scenes") or {}).get(scene_path)
            entries = undo if isinstance(undo, list) else []
            if isinstance(undo, dict):  # shape records
                entries = [{"kind": "blendShape", "path": w.get("renderer"), "field": "blendShape." + w.get("shape", "")}
                           for w in undo.get("weights") or []]
            for entry in entries:
                kind = entry.get("kind")
                if kind == "value":
                    owned.add((entry.get("path"), entry.get("field")))
                elif kind == "uses":  # a collider DSH added to a PhysBone's list
                    owned.add((entry.get("path"), "colliders"))
                elif kind == "view":
                    owned.add(("", "ViewPosition"))
                elif kind == "boneScale":
                    owned.add((entry.get("path"), "m_LocalScale"))
                elif kind == "blendShape":
                    owned.add((entry.get("path"), entry.get("field")))
    return owned


def manual_overrides(root, data, scene_path, items):
    owned = own_changes(root, scene_path, items)
    hidden = set()
    for item in items:
        if item["kind"] == "accessory":
            try:
                import unity_accessory
                recipe, _ = unity_accessory.load_recipe(root, item["name"])
                hidden.update(recipe["hide"])
            except WorkflowError:
                pass

    def dsh_path(path):
        return any(part.startswith("DSH ") for part in (path or "").split("/"))

    values = []
    for row in data.get("values") or []:
        path, prop = row.get("path", ""), row.get("property", "")
        if dsh_path(path):
            continue
        base = prop.split(".Array")[0].rsplit(".", 1)[0] if prop.endswith((".x", ".y", ".z")) else prop.split(".Array")[0]
        if (path, prop) in owned or (path, base) in owned:
            continue
        if path in hidden and prop == "m_IsActive":
            continue
        values.append(row)
    added_objects = [p for p in data.get("addedObjects") or [] if not dsh_path(p)]
    added_components = [c for c in data.get("addedComponents") or []
                        if not dsh_path(c.get("path")) and c.get("type") not in DSH_COMPONENTS]
    return {"values": values[:200], "valueCount": len(values), "addedObjects": added_objects[:100],
            "addedComponents": added_components[:100], "removedComponents": (data.get("removedComponents") or [])[:100]}


def unity_read(root, args, method, task, name, scene, avatar):
    ns = argparse.Namespace(scene=scene, avatar=avatar, avatar_id="", prepare=args.prepare)
    output = toggle.read_only_task(root, ns, {}, method, task, name, HELPER)
    if not output.get("ok"):
        raise WorkflowError(output.get("error") or f"Unity could not read the avatar ({task}).")
    return output["unity"]


def run_inventory(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    items = inventory(root, scene_path, args.avatar)
    output = {"ok": True, "scene": scene_path, "avatar": args.avatar, "changes": items,
              "note": "Only changes made through this plugin's commands are listed here and can be carried over."}
    if args.overrides:
        unity = unity_read(root, args, "Overrides", "MigrateOverrides", "migrate-overrides", args.scene, args.avatar)
        data = toggle.read_result(Path(unity["overrides"])) if unity.get("overrides") else {}
        output["prefab"] = unity.get("prefab")
        output["manual"] = manual_overrides(root, data, scene_path, items)
        output["manualNote"] = ("Changes made by hand (not by DSH). They are not carried over; show them to the user "
                                "as a list to redo on the new avatar, or as edit-script work.")
    return output


# ---- checks against the new avatar --------------------------------------------------------------------------


def close(name, candidates):
    return difflib.get_close_matches(name, list(candidates), n=3, cutoff=0.6)


class Check:
    def __init__(self, info):
        self.info = info
        self.paths = set(info.get("paths") or [])
        self.renderers = {k: set(v) for k, v in (info.get("renderers") or {}).items()}
        self.bones = info.get("humanoidBones") or {}
        self.problems = []

    def path(self, path, what):
        if path and path not in self.paths:
            leaf = path.split("/")[-1]
            same_leaf = [p for p in self.paths if p.split("/")[-1] == leaf]
            self.problems.append({"missing": what, "name": path, "suggest": same_leaf[:3] or close(path, self.paths)})

    def renderer(self, path):
        if path not in self.renderers:
            self.problems.append({"missing": "skinned mesh", "name": path, "suggest": close(path, self.renderers)})
            return None
        return self.renderers[path]

    def shapes(self, renderer, shapes):
        names = self.renderer(renderer)
        if names is None:
            return
        for shape in shapes:
            if shape not in names:
                self.problems.append({"missing": "shape key", "name": f"{renderer}:{shape}", "suggest": close(shape, names)})

    def bone(self, bone):
        if bone and bone not in self.bones:
            self.problems.append({"missing": "humanoid bone", "name": bone, "suggest": []})


def check_item(root, item, check, old_avatar, new_avatar):
    kind, name = item["kind"], item["name"]
    if kind == "shape":
        import unity_shape
        recipe, _ = unity_shape.load_recipe(root, name)
        for w in recipe["weights"]:
            check.shapes(w["renderer"], [w["shape"]])
        for s in recipe["sync"]:
            check.shapes(s["source"], [v.split("=")[0] for v in s["shapes"]])
            check.renderer(s["renderer"])
        for r in recipe["remove"]:
            check.shapes(r["renderer"], r["shapes"])
    elif kind == "accessory":
        import unity_accessory
        recipe, _ = unity_accessory.load_recipe(root, name)
        if recipe["mode"] != "armature":
            check.bone(recipe["bone"])
        for path in recipe["hide"]:
            check.path(path, "object to hide")
    elif kind == "physbone":
        import unity_physbone
        recipe, _ = unity_physbone.load_recipe(root, name)
        targets = {pb["target"] for pb in check.info.get("physBones") or []} | {pb["root"] for pb in check.info.get("physBones") or []}
        for bone in recipe["bones"] + [t for c in recipe["colliders"] for t in c["targets"]]:
            if bone["target"] not in targets:
                check.problems.append({"missing": "PhysBone", "name": bone["target"], "suggest": close(bone["target"], targets)})
        for collider in recipe["colliders"]:
            check.bone(collider["bone"])
            check.bone(collider["to"])
    elif kind == "proportion":
        import unity_proportion
        recipe, _ = unity_proportion.load_recipe(root, name)
        for scale in recipe["scales"]:
            check.bone(scale["bone"])
        if recipe["viewMode"] == "auto":
            check.bone("LeftEye")
            check.bone("RightEye")
    elif kind == "expression":
        import unity_expression
        recipe, _ = unity_expression.load_recipe(root, name)
        face = recipe["renderer"] or check.info.get("face") or ""
        if not face:
            check.problems.append({"missing": "face mesh (Lip Sync mesh)", "name": "", "suggest": []})
        else:
            check.shapes(face, sorted({s["shape"] for section in ("gestures", "locks", "toggles")
                                       for e in recipe[section] for s in e["shapes"]}))
    elif kind == "toggle":
        outfit = item.get("outfit") or ""
        relative = outfit[len(old_avatar) + 1:] if outfit.startswith(old_avatar + "/") else outfit
        item["newOutfit"] = f"{new_avatar}/{relative}"
        check.path(relative, "outfit")
    elif kind == "variant":
        import unity_texture
        recipe = unity_texture.load_recipe(root, name)
        recipe = recipe[0] if isinstance(recipe, tuple) else recipe
        materials = check.info.get("materials") or {}
        textures = {t for ts in materials.values() for t in ts}
        for texture in recipe.get("textures", []):
            if texture.get("replace") not in textures:
                check.problems.append({"missing": "texture used by the avatar", "name": texture.get("replace"),
                                       "suggest": close(texture.get("replace", ""), textures)})
        for entry in recipe.get("materials", []):
            if entry.get("material") not in materials:
                check.problems.append({"missing": "material used by the avatar", "name": entry.get("material"),
                                       "suggest": close(entry.get("material", ""), materials)})


def plan(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    _, to_scene = toggle.scene_asset(root, args.to_scene or args.scene)
    items = inventory(root, scene_path, args.avatar)
    unity = unity_read(root, args, "Describe", "MigrateDescribe", "migrate-describe", to_scene, args.to_avatar)
    info = json.loads(Path(unity["describe"]).read_text(encoding="utf-8"))
    new_avatar = (unity.get("avatar") or {}).get("path") or args.to_avatar
    steps = []
    for item in items:
        check = Check(info)
        try:
            check_item(root, item, check, args.avatar, new_avatar)
        except WorkflowError as error:
            check.problems.append({"missing": "recipe", "name": str(error), "suggest": []})
        step = dict(item, status="ready" if not check.problems else "needs-attention")
        if check.problems:
            step["problems"] = check.problems[:20]
        if item["kind"] == "variant" and check.problems:
            step["next"] = ("The new avatar uses other textures or materials. Make the variant again from the new "
                            "version's PSD (vrc-texture-variant) or the new materials (vrc-material-adjust).")
        steps.append(step)
    ready = [s for s in steps if s["status"] == "ready"]
    contents = {"scene": to_scene, "avatar": new_avatar, "steps": ready, "sceneDigest": digest(inside(root, to_scene)),
                "head": toggle.git_state(root)["head"]}
    token = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
    return {"ok": True, "from": {"scene": scene_path, "avatar": args.avatar}, "to": {"scene": to_scene, "avatar": new_avatar},
            "steps": steps, "summary": {"ready": len(ready), "needsAttention": len(steps) - len(ready)},
            "plan": token,
            "next": ("Show the steps. Fix or copy recipes for steps that need attention (or leave them out), then run "
                     "apply with --approved-plan. Hand-made changes come from inventory --overrides.")}


def tool_args(step, scene, avatar, verify_sdk):
    args = ["--scene", scene, "--avatar", avatar]
    kind = step["kind"]
    if kind == "toggle":
        args += ["--outfit", step["newOutfit"], "--menu", step.get("menu", "")]
        if step.get("defaultOn"):
            args.append("--default-on")
        if step.get("exclusiveTag"):
            args += ["--exclusive-tag", step["exclusiveTag"]]
    elif kind == "variant":
        args += ["--variant", step["name"]]
    else:
        args += ["--recipe", step["name"]]
    if verify_sdk:
        args.append("--verify-sdk")
    return args


def call(root, tool, command, args):
    run = subprocess.run([sys.executable, "-B", str(TOOLS / tool), command, "--project", str(root), *args],
                         capture_output=True, encoding="utf-8", errors="replace", check=False)
    try:
        return json.loads(run.stdout)
    except ValueError:
        return {"ok": False, "error": (run.stderr or run.stdout).strip()[-2000:]}


def apply(root, args):
    planned = plan(root, args)
    if planned["plan"] != args.approved_plan:
        raise WorkflowError("The plan changed. Run plan again and confirm the new steps before applying.")
    scene, avatar = planned["to"]["scene"], planned["to"]["avatar"]
    done = []
    for step in [s for s in planned["steps"] if s["status"] == "ready"]:
        tool = TOOL[step["kind"]]
        args_ = tool_args(step, scene, avatar, args.verify_sdk)
        preview = call(root, tool, "preview", args_)
        if not preview.get("ok"):
            return {"ok": False, "done": done, "failed": step, "error": preview.get("error") or "Preview failed.",
                    "next": "Earlier steps stay applied. Fix this one and run plan again."}
        applied = call(root, tool, "apply", [*args_, "--approved-preview", preview["preview"]])
        result = {"kind": step["kind"], "name": step["name"], "ok": bool(applied.get("ok")),
                  "sdk": (applied.get("unity") or {}).get("sdkVerification", {}).get("status")}
        done.append(result)
        if not applied.get("ok"):
            return {"ok": False, "done": done, "failed": step, "error": applied.get("error") or "Apply failed.",
                    "next": "Earlier steps stay applied. Fix this one and run plan again."}
    skipped = [{"kind": s["kind"], "name": s["name"]} for s in planned["steps"] if s["status"] != "ready"]
    return {"ok": True, "done": done, "skipped": skipped, "to": planned["to"]}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "plan", "apply"):
        action = commands.add_parser(name)
        action.add_argument("--project", default=None)
        action.add_argument("--scene", required=True, help="The scene with the avatar DSH changed")
        action.add_argument("--avatar", required=True, help="Hierarchy path of the avatar DSH changed")
        action.add_argument("--prepare", action="store_true")
        if name == "inventory":
            action.add_argument("--overrides", action="store_true", help="Also list hand-made prefab overrides (Unity)")
        else:
            action.add_argument("--to-scene", default="", help="The scene with the new avatar (default: the same)")
            action.add_argument("--to-avatar", required=True, help="Hierarchy path of the new avatar")
        if name == "apply":
            action.add_argument("--approved-plan", required=True)
            action.add_argument("--verify-sdk", action="store_true")
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        root = find_project(project)
        if args.command == "inventory":
            output = run_inventory(root, args)
        elif args.command == "plan":
            output = plan(root, args)
        else:
            output = apply(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
