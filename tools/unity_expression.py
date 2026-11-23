#!/usr/bin/env python3
"""Facial expressions for hand gestures, expressions picked from the menu, and shape toggles such as a blush.
DSH generates an FX controller, clips and a menu in the recipe's Generated folder and merges them with Modular
Avatar; the avatar's own expression layers stay, and the DSH layer wins for the shapes the recipe controls."""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


FOLDER = "Assets/DSH/Expressions"
HELPER = "DshExpression"
HOLDER = "DSH Expression "
GESTURES = {"Fist": 1, "Open": 2, "Point": 3, "Peace": 4, "RockNRoll": 5, "Gun": 6, "ThumbsUp": 7}
HANDS = ("left", "right", "either")
MAX_MENU = 8  # a VRChat menu page holds eight controls
MAX_SHAPES = 100


def recipe_dir(root, name):
    if not isinstance(name, str) or not dsh_recipe.NAME.match(name):
        raise WorkflowError("Use an expression name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, f"{FOLDER}/{name}")


def shapes_of(entry, label):
    shapes = entry.get("shapes")
    if not isinstance(shapes, dict) or not 1 <= len(shapes) <= MAX_SHAPES:
        raise WorkflowError(f"Each {label} needs 'shapes': an object of blendshape names and weights (0-100).")
    out = []
    for shape, weight in shapes.items():
        if not shape.strip() or isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 100:
            raise WorkflowError(f"Each {label} shape needs a weight from 0 to 100 ({shape!r}).")
        out.append({"shape": shape, "weight": float(weight)})
    return out


def label_of(entry, label, seen):
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip() or "/" in name or len(name) > 40 or name in seen:
        raise WorkflowError(f"Each {label} needs a unique 'name' (the menu label, without '/').")
    seen.add(name)
    return name


def load_recipe(root, name):
    path = recipe_dir(root, name) / "recipe.json"
    try:
        recipe = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise WorkflowError(f"Write the recipe first: {path.relative_to(root).as_posix()}") from None
    except ValueError as error:
        raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
    if not isinstance(recipe, dict) or recipe.get("name") != name:
        raise WorkflowError(f"The recipe must be an object whose name is {name}.")
    sections = {key: recipe.get(key, []) for key in ("gestures", "locks", "toggles")}
    if any(not isinstance(items, list) or not all(isinstance(i, dict) for i in items) for items in sections.values()):
        raise WorkflowError("gestures, locks and toggles must be lists of objects.")
    if not any(sections.values()):
        raise WorkflowError("The recipe changes nothing. Add gestures, locks or toggles.")
    renderer = recipe.get("renderer", "")
    if not isinstance(renderer, str) or renderer.startswith("/"):
        raise WorkflowError("'renderer' must be the face mesh path under the avatar, or left out for the Lip Sync mesh.")
    override = recipe.get("override", "listed")
    if override not in ("listed", "all"):
        raise WorkflowError("'override' must be listed (only the shapes in this recipe) or all (also every shape the "
                            "avatar's own gesture expressions move).")
    gestures, taken = [], set()
    for entry in sections["gestures"]:
        hand, gesture = entry.get("hand", "either"), entry.get("gesture")
        if hand not in HANDS:
            raise WorkflowError("'hand' must be left, right or either.")
        if gesture not in GESTURES:
            raise WorkflowError(f"'gesture' must be one of {', '.join(GESTURES)}.")
        shapes = shapes_of(entry, "gesture")
        for side in (("left", "right") if hand == "either" else (hand,)):
            if (side, gesture) in taken:
                raise WorkflowError(f"The {side} hand {gesture} appears twice.")
            taken.add((side, gesture))
            gestures.append({"label": f"{side} {gesture}", "hand": side, "gesture": GESTURES[gesture],
                             "shapes": shapes})
    seen = set()
    locks = [{"label": label_of(e, "lock", seen), "shapes": shapes_of(e, "lock")} for e in sections["locks"]]
    toggles = []
    for entry in sections["toggles"]:
        saved = entry.get("saved", True)
        if not isinstance(saved, bool):
            raise WorkflowError("'saved' must be true or false.")
        toggles.append({"label": label_of(entry, "toggle", seen), "shapes": shapes_of(entry, "toggle"), "saved": saved})
    menu = recipe.get("menu", "")
    if locks or toggles:
        if not isinstance(menu, str) or not menu or len(menu) > 200 or any(not p.strip() for p in menu.split("/")):
            raise WorkflowError("Menu expressions and toggles need 'menu': a menu path such as 'Expressions'.")
        if len(locks) + len(toggles) > MAX_MENU:
            raise WorkflowError(f"Put at most {MAX_MENU} locks and toggles in one recipe (one menu page).")
    else:
        menu = ""
    request = {"name": name, "folder": f"{FOLDER}/{name}", "renderer": renderer, "menu": menu, "overrideMode": override,
               "gestures": gestures, "locks": locks, "toggles": toggles}
    return request, path


def scenes_with_holder(root, name):
    return [scene for scene, holders in toggle.scene_holders(root, HOLDER).items() if HOLDER + name in holders]


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = dict(recipe, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
    if args.verify_sdk:
        request["verifySdk"] = True
    planned = [scene_path, f"{recipe['folder']}/Generated/<id>/ (controller, clips and menu; a new <id> when the "
                           "recipe changes, and builds no saved scene uses are deleted)"]
    output, helpers = toggle.scene_plan(root, request, scene, planned, [[path.name, digest(path)]])
    in_scene = scene_path in scenes_with_holder(root, recipe["name"])
    output["alreadyInScene"] = in_scene
    adds = (8 if recipe["locks"] else 0) + len(recipe["toggles"])
    output["parameterBudget"] = toggle.parameter_budget(root, scene_path, args.avatar, 0 if in_scene else adds)
    output["summary"] = {"gestures": len(recipe["gestures"]), "locks": len(recipe["locks"]),
                         "toggles": len(recipe["toggles"]), "override": recipe["overrideMode"]}
    return output, helpers


def remove_plan(root, args):
    folder = recipe_dir(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    in_scene = scene_path in scenes_with_holder(root, args.recipe)
    generated = folder / "Generated"
    if not in_scene and not generated.is_dir():
        raise WorkflowError(f"No expression named {args.recipe} is in {scene_path} or generated in this project.")
    # Generated assets that another saved scene still uses stay (Unity checks the scenes' dependencies).
    others = [s for s in scenes_with_holder(root, args.recipe) if s != scene_path]
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "name": args.recipe,
               "folder": folder.relative_to(root).as_posix(), "remove": True}
    planned = ([scene_path] if in_scene else []) + (
        [f"{request['folder']}/Generated/ (the parts no saved scene uses any more are deleted)"] if generated.is_dir() else [])
    output, helpers = toggle.scene_plan(root, request, scene, planned, [])
    output.update(inScene=in_scene, otherScenes=others,
                  note="The recipe file stays. Generated assets that other scenes use stay with them.")
    return output, helpers


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Expression recipes and the scenes that hold them (no Unity)")
    recipes.add_argument("--project", default=None)
    listing = commands.add_parser("list", help="Face mesh shapes and the avatar's own gesture expressions")
    dsh_recipe.common_arguments(listing, "list", needs_recipe=False)
    listing.add_argument("--filter", default="")
    listing.add_argument("--renderer", default="")
    listing.add_argument("--prepare", action="store_true")
    shot = commands.add_parser("capture")
    dsh_recipe.common_arguments(shot, "capture")
    shot.add_argument("--prepare", action="store_true")
    shot.add_argument("--views", default="face")
    shot.add_argument("--size", type=int, default=384)
    for name in ("preview", "apply", "remove"):
        dsh_recipe.common_arguments(commands.add_parser(name), name)
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        root = find_project(project)
        if args.command == "recipes":
            folder = inside(root, FOLDER)
            names = sorted(p.name for p in folder.glob("*") if p.is_dir()) if folder.is_dir() else []
            output = {"ok": True, "recipes": [{"recipe": n, "scenes": scenes_with_holder(root, n)} for n in names][:100]}
        elif args.command == "list":
            output = toggle.read_only_task(root, args, {"filter": args.filter, "renderer": args.renderer}, "List",
                                           "Expressions", "expressions", HELPER)
        elif args.command == "capture":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            recipe, _ = load_recipe(root, args.recipe)
            output = toggle.read_only_task(root, args, {"recipe": recipe, "views": args.views, "size": args.size},
                                           "Capture", "ExpressionCapture", "expression-capture", HELPER, graphics=True)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = toggle.run_approved(root, args, lambda: plan(root, args), "Apply", "ExpressionApply",
                                         "expression-apply", HELPER, args.verify_sdk)
        elif not args.approved_preview:
            output, _ = remove_plan(root, args)
        else:
            output = toggle.run_approved(root, args, lambda: remove_plan(root, args), "Remove", "ExpressionRemove",
                                         "expression-remove", HELPER)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
