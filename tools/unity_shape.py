#!/usr/bin/env python3
"""Adjust an avatar's shape without changing its FBX: blendshape weights, outfit sync and hidden-mesh removal."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


SHAPES = Path(toggle.SHAPES)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
MAX_ITEMS = 200
HELPER = "DshShape"


def recipe_dir(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise WorkflowError("Use a recipe name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, (SHAPES / name).as_posix())


def text(item, key, label):
    value = item.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise WorkflowError(f"Each {label} needs a '{key}' text value.")
    return value


def shape_list(item, label):
    shapes = item.get("shapes")
    if (not isinstance(shapes, list) or not 1 <= len(shapes) <= MAX_ITEMS or
            not all(isinstance(shape, str) and shape.strip() for shape in shapes)):
        raise WorkflowError(f"Each {label} needs 'shapes': a list of blendshape names.")
    return shapes


def load_recipe(root, name):
    """Read and check Assets/DSH/Shapes/<name>/recipe.json; returns the Unity request part of it."""
    path = recipe_dir(root, name) / "recipe.json"
    try:
        recipe = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise WorkflowError(f"Write the recipe first: {path.relative_to(root).as_posix()}") from None
    except ValueError as error:
        raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
    if not isinstance(recipe, dict) or recipe.get("name") != name:
        raise WorkflowError(f"The recipe must be an object whose name is {name}.")
    sections = {key: recipe.get(key, []) for key in ("weights", "sync", "remove")}
    if any(not isinstance(items, list) or len(items) > MAX_ITEMS or
           not all(isinstance(item, dict) for item in items) for items in sections.values()):
        raise WorkflowError(f"weights, sync and remove must be lists of up to {MAX_ITEMS} objects.")
    if not any(sections.values()):
        raise WorkflowError("The recipe changes nothing. Add weights, sync or remove entries.")
    weights = []
    for item in sections["weights"]:
        weight = item.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 100:
            raise WorkflowError("Each weight needs 'weight' from 0 to 100.")
        weights.append({"renderer": text(item, "renderer", "weight"), "shape": text(item, "shape", "weight"),
                        "weight": weight})
    sync = [{"renderer": text(item, "renderer", "sync entry"), "source": text(item, "source", "sync entry"),
             "shapes": shape_list(item, "sync entry")} for item in sections["sync"]]
    remove = []
    for item in sections["remove"]:
        tolerance = item.get("tolerance", 0.001)
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not 0 < tolerance <= 1:
            raise WorkflowError("tolerance must be a number above 0 and at most 1.")
        remove.append({"renderer": text(item, "renderer", "remove entry"),
                       "shapes": shape_list(item, "remove entry"), "tolerance": tolerance})
    return {"name": name, "weights": weights, "sync": sync, "remove": remove}, path


def shapes(root, args):
    return toggle.read_only_task(root, args, {"filter": args.filter}, "Shapes", "Shapes", "shapes", HELPER)


def capture(root, args):
    recipe, _ = load_recipe(root, args.recipe)
    if args.build:
        reason = toggle.prepare_sdk_outputs(root)
        if reason:
            raise WorkflowError(reason + " Capture without --build, or keep build outputs out of Git first.")
    request = {"recipe": recipe, "views": args.views, "size": args.size, "build": args.build}
    return toggle.read_only_task(root, args, request, "Capture", "ShapeCapture", "shape-capture", HELPER,
                                 graphics=True)


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = dict(recipe, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
    if args.verify_sdk:
        request["verifySdk"] = True
    output, helpers = toggle.scene_plan(root, request, scene, [scene_path], [[path.name, digest(path)]])
    output["summary"] = {"weights": len(recipe["weights"]), "syncShapes": sum(len(s["shapes"]) for s in recipe["sync"]),
                         "removeShapes": sum(len(r["shapes"]) for r in recipe["remove"])}
    return output, helpers


def apply(root, args):
    return toggle.run_approved(root, args, lambda: plan(root, args), "Apply", "ShapeRecipe", "shape-recipe",
                               HELPER, args.verify_sdk)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("shapes", "capture", "preview", "apply"):
        action = commands.add_parser(name)
        action.add_argument("--project", default=os.getcwd())
        action.add_argument("--scene", required=True)
        action.add_argument("--avatar", required=name in ("preview", "apply"), default="")
        action.add_argument("--avatar-id", default="")
        if name in ("shapes", "capture"):
            action.add_argument("--prepare", action="store_true")
        if name == "shapes":
            action.add_argument("--filter", default="")
        if name in ("capture", "preview", "apply"):
            action.add_argument("--recipe", required=True)
        if name == "capture":
            action.add_argument("--views", default="front,face")
            action.add_argument("--size", type=int, default=512)
            action.add_argument("--no-build", dest="build", action="store_false",
                                help="Render the scene copy directly instead of an SDK-built copy")
        if name in ("preview", "apply"):
            action.add_argument("--verify-sdk", action="store_true")
        if name == "apply":
            action.add_argument("--approved-preview", required=True)
    args = parser.parse_args()
    try:
        if not Path(args.project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {args.project}")
        root = find_project(args.project)
        if args.command == "shapes":
            output = shapes(root, args)
        elif args.command == "capture":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            output = capture(root, args)
        elif args.command == "preview":
            output, _ = plan(root, args)
        else:
            output = apply(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
