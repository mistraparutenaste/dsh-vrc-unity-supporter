#!/usr/bin/env python3
"""Attach an existing prefab or model to an avatar: on a humanoid bone (MA Bone Proxy) or merged with the
avatar's armature (MA Setup Outfit), with an optional VRCFury menu toggle. The assets themselves are not changed."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


ACCESSORIES = Path(toggle.ACCESSORIES)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
HELPER = "DshAccessory"
HOLDER = "DSH Accessory "
MODES = ("auto", "bone", "armature")
ORIGINS = ("auto", "avatar", "bone")
ASSET_SUFFIXES = (".prefab", ".fbx")
# UnityEngine.HumanBodyBones, without LastBone.
BONES = (
    "Hips LeftUpperLeg RightUpperLeg LeftLowerLeg RightLowerLeg LeftFoot RightFoot Spine Chest Neck Head "
    "LeftShoulder RightShoulder LeftUpperArm RightUpperArm LeftLowerArm RightLowerArm LeftHand RightHand "
    "LeftToes RightToes LeftEye RightEye Jaw LeftThumbProximal LeftThumbIntermediate LeftThumbDistal "
    "LeftIndexProximal LeftIndexIntermediate LeftIndexDistal LeftMiddleProximal LeftMiddleIntermediate "
    "LeftMiddleDistal LeftRingProximal LeftRingIntermediate LeftRingDistal LeftLittleProximal "
    "LeftLittleIntermediate LeftLittleDistal RightThumbProximal RightThumbIntermediate RightThumbDistal "
    "RightIndexProximal RightIndexIntermediate RightIndexDistal RightMiddleProximal RightMiddleIntermediate "
    "RightMiddleDistal RightRingProximal RightRingIntermediate RightRingDistal RightLittleProximal "
    "RightLittleIntermediate RightLittleDistal UpperChest"
).split()


def recipe_dir(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise WorkflowError("Use an accessory name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, (ACCESSORIES / name).as_posix())


def vector(recipe, key, limit, label):
    value = recipe.get(key, [0, 0, 0])
    if (not isinstance(value, list) or len(value) != 3 or
            not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= limit
                    for v in value)):
        raise WorkflowError(f"'{key}' must be three numbers ({label}, each within ±{limit}).")
    return [float(v) for v in value]


def load_recipe(root, name):
    """Read and check Assets/DSH/Accessories/<name>/recipe.json; returns the Unity request part and its path."""
    path = recipe_dir(root, name) / "recipe.json"
    try:
        recipe = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise WorkflowError(f"Write the recipe first: {path.relative_to(root).as_posix()}") from None
    except ValueError as error:
        raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
    if not isinstance(recipe, dict) or recipe.get("name") != name:
        raise WorkflowError(f"The recipe must be an object whose name is {name}.")
    asset = recipe.get("asset")
    if (not isinstance(asset, str) or not asset.startswith("Assets/") or "\\" in asset or
            any(part in ("", ".", "..") for part in asset.split("/")) or
            not asset.lower().endswith(ASSET_SUFFIXES)):
        raise WorkflowError("'asset' must be a .prefab or .fbx path under Assets/ (forward slashes).")
    if not inside(root, asset).is_file():
        raise WorkflowError(f"The asset does not exist: {asset}")
    if asset.startswith(ACCESSORIES.as_posix() + "/"):
        raise WorkflowError("Keep the attached asset outside Assets/DSH/Accessories (that folder is removed with the accessory).")
    mode = recipe.get("mode", "auto")
    if mode not in MODES:
        raise WorkflowError(f"'mode' must be one of {', '.join(MODES)}.")
    bone = recipe.get("bone", "Head")
    if bone not in BONES:
        raise WorkflowError(f"'bone' must be a humanoid bone name such as Head, Chest, LeftHand or Hips.")
    origin = recipe.get("origin", "auto")
    if origin not in ORIGINS:
        raise WorkflowError(f"'origin' must be one of {', '.join(ORIGINS)}.")
    scale = recipe.get("scale", 1)
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.01 <= scale <= 100:
        raise WorkflowError("'scale' must be a number from 0.01 to 100.")
    menu = recipe.get("menu", "")
    if not isinstance(menu, str) or len(menu) > 200 or (menu and any(not part.strip() for part in menu.split("/"))):
        raise WorkflowError("'menu' must be empty (always shown) or a menu path such as 'Accessory/Hat'.")
    hide = recipe.get("hide", [])
    if (not isinstance(hide, list) or len(hide) > 50 or
            not all(isinstance(path, str) and path.strip() and not path.startswith("/") for path in hide)):
        raise WorkflowError("'hide' must be a list of object paths under the avatar (for example 'Hair').")
    materials_from = recipe.get("materialsFrom", "")
    if materials_from:
        if (not isinstance(materials_from, str) or not materials_from.startswith("Assets/") or "\\" in materials_from or
                not materials_from.lower().endswith(ASSET_SUFFIXES) or not inside(root, materials_from).is_file()):
            raise WorkflowError("'materialsFrom' must be an existing .prefab or .fbx under Assets/.")
    default_on = recipe.get("defaultOn", True)
    if not isinstance(default_on, bool):
        raise WorkflowError("'defaultOn' must be true or false.")
    request = {"name": name, "asset": asset, "mode": mode, "bone": bone, "origin": origin,
               "position": vector(recipe, "position", 2, "metres from the bone"),
               "rotation": vector(recipe, "rotation", 360, "degrees"),
               "scale": float(scale), "menu": menu, "hide": hide, "materialsFrom": materials_from,
               "defaultOn": default_on,
               "folder": (ACCESSORIES / name).as_posix()}
    return request, path


def fingerprint(root, recipe, path):
    files = [[path.name, digest(path)], [recipe["asset"], digest(inside(root, recipe["asset"]))]]
    if recipe["materialsFrom"]:
        files.append([recipe["materialsFrom"], digest(inside(root, recipe["materialsFrom"]))])
    return files


def scenes_with_holder(root, name):
    """Saved scenes whose YAML names this accessory's object (a text search; Unity is not needed)."""
    needle = f"m_Name: {HOLDER}{name}\n".encode("utf-8")
    found = []
    for scene in sorted((root / "Assets").rglob("*.unity")):
        try:
            if needle in scene.read_bytes().replace(b"\r\n", b"\n"):
                found.append(scene.relative_to(root).as_posix())
        except OSError:
            continue
    return found


def list_accessories(root):
    folder = inside(root, ACCESSORIES.as_posix())
    items = []
    for path in sorted(p for p in folder.glob("*") if p.is_dir()) if folder.is_dir() else []:
        entry = {"accessory": path.name}
        try:
            recipe, _ = load_recipe(root, path.name)
            entry.update(asset=recipe["asset"], mode=recipe["mode"], menu=recipe["menu"])
            if recipe["mode"] != "armature":
                entry["bone"] = recipe["bone"]
        except WorkflowError as error:
            entry["recipeError"] = str(error)
        entry["scenes"] = scenes_with_holder(root, path.name)
        items.append(entry)
    return {"ok": True, "accessoryCount": len(items), "accessories": items[:100]}


def candidates(root, args):
    return toggle.read_only_task(root, args, {"filter": args.filter}, "Candidates", "AccessoryCandidates",
                                 "accessory-candidates", HELPER)


def capture(root, args):
    recipe, _ = load_recipe(root, args.recipe)
    if args.build:
        reason = toggle.prepare_sdk_outputs(root)
        if reason:
            raise WorkflowError(reason + " Capture without --build, or keep build outputs out of Git first.")
    request = {"recipe": recipe, "views": args.views, "size": args.size, "build": args.build}
    return toggle.read_only_task(root, args, request, "Capture", "AccessoryCapture", "accessory-capture", HELPER,
                                 graphics=True)


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = dict(recipe, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
    if args.verify_sdk:
        request["verifySdk"] = True
    planned = [scene_path]
    if recipe["hide"] and recipe["menu"]:
        planned.append(f"{recipe['folder']}/{recipe['name']}_hide.anim")
    output, helpers = toggle.scene_plan(root, request, scene, planned, fingerprint(root, recipe, path))
    output["alreadyInScene"] = scene_path in scenes_with_holder(root, recipe["name"])
    return output, helpers


def apply(root, args):
    return toggle.run_approved(root, args, lambda: plan(root, args), "Apply", "AccessoryApply", "accessory-apply",
                               HELPER, args.verify_sdk)


def remove_plan(root, args):
    folder = recipe_dir(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    exists = folder.is_dir()
    in_scene = scene_path in scenes_with_holder(root, args.recipe)
    if not exists and not in_scene:
        raise WorkflowError(f"No accessory named {args.recipe} exists in this project or scene.")
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "name": args.recipe,
               "folder": folder.relative_to(root).as_posix(), "keepFiles": bool(args.keep_files), "remove": True}
    if exists:
        # Without a menu the hidden objects were turned off in the scene; removing turns them back on.
        try:
            recipe, _ = load_recipe(root, args.recipe)
            if not recipe["menu"]:
                request["hide"] = recipe["hide"]
        except WorkflowError:
            pass
    files = sorted(item.relative_to(root).as_posix() for item in folder.rglob("*") if item.is_file()) if exists else []
    planned = [scene_path] if in_scene else []
    if exists and not args.keep_files:
        planned.append(request["folder"] + "/ (the recipe, deleted with its .meta files)")
    output, helpers = toggle.scene_plan(root, request, scene, planned, [[p, digest(root / p)] for p in files])
    output.update(inScene=in_scene, deletesFiles=exists and not args.keep_files,
                  note="The attached prefab or model itself is kept.")
    return output, helpers


def remove(root, args):
    if not args.approved_preview:
        output, _ = remove_plan(root, args)
        return output
    return toggle.run_approved(root, args, lambda: remove_plan(root, args), "Remove", "AccessoryRemove",
                               "accessory-remove", HELPER)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="Accessory recipes and the scenes that hold them (no Unity)")
    listing.add_argument("--project", default=os.getcwd())
    for name in ("candidates", "capture", "preview", "apply", "remove"):
        action = commands.add_parser(name)
        action.add_argument("--project", default=os.getcwd())
        action.add_argument("--scene", required=True)
        action.add_argument("--avatar", required=name in ("preview", "apply", "remove"), default="")
        action.add_argument("--avatar-id", default="")
        if name in ("candidates", "capture"):
            action.add_argument("--prepare", action="store_true")
        if name == "candidates":
            action.add_argument("--filter", default="")
        else:
            action.add_argument("--recipe", required=True)
        if name == "capture":
            action.add_argument("--views", default="front,left,face")
            action.add_argument("--size", type=int, default=512)
            action.add_argument("--no-build", dest="build", action="store_false",
                                help="Render the scene copy directly instead of an SDK-built copy")
        if name in ("preview", "apply"):
            action.add_argument("--verify-sdk", action="store_true")
        if name == "apply":
            action.add_argument("--approved-preview", required=True)
        if name == "remove":
            action.add_argument("--approved-preview", default="",
                                help="Without this, remove only previews what it would change")
            action.add_argument("--keep-files", action="store_true")
    args = parser.parse_args()
    try:
        if not Path(args.project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {args.project}")
        root = find_project(args.project)
        if args.command == "list":
            output = list_accessories(root)
        elif args.command == "candidates":
            output = candidates(root, args)
        elif args.command == "capture":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            output = capture(root, args)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = apply(root, args)
        else:
            output = remove(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
