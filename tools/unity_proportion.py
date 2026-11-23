#!/usr/bin/env python3
"""Adjust where the avatar's first-person view sits and the size of single bones (Modular Avatar Scale Adjuster),
without changing its FBX. Every change is recorded so remove puts back exactly what DSH changed."""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
from dsh_recipe import number, vector
import unity_toggle as toggle
from unity_accessory import BONES
from unity_inspect import find_project
from unity_toggle import WorkflowError


KIND = dsh_recipe.RecipeKind("Assets/DSH/Proportions", "proportions", "DshProportion",
                             ("ProportionRecipe", "proportion-recipe"), ("ProportionRemove", "proportion-remove"),
                             "proportion recipe")


def load_recipe(root, name, scene_path=None):
    recipe, path = KIND.read(root, name)
    request = {"name": name, "viewMode": "", "view": [0.0, 0.0, 0.0], "forward": 0.035, "scales": [], "undo": []}
    # Offsets and bone scale factors start from the values before DSH changed them, which the scene's record keeps.
    if scene_path:
        request["undo"] = [e for e in KIND.scenes(root, name).get(scene_path, [])
                           if e.get("kind") in ("view", "boneScale")]
    view = recipe.get("view")
    if view == "auto":
        request["viewMode"] = "auto"
        request["forward"] = number(recipe.get("forward", 0.035), 0, 0.1,
                                    "'forward' (metres in front of the eye bones, which sit inside the eyeballs)")
    elif isinstance(view, list):
        request.update(viewMode="set", view=vector(view, 5, "'view' (metres in the avatar's space)"))
        if request["view"][1] <= 0:
            raise WorkflowError("'view' must be above the avatar's feet (y above 0).")
    elif isinstance(view, dict) and set(view) == {"offset"}:
        request.update(viewMode="offset", view=vector(view["offset"], 0.3, "'offset' (metres)"))
    elif view is not None:
        raise WorkflowError("'view' must be \"auto\", three numbers, or {\"offset\": [x, y, z]}.")
    scales = recipe.get("scales", [])
    if not isinstance(scales, list) or len(scales) > 50 or not all(isinstance(s, dict) for s in scales):
        raise WorkflowError("'scales' must be a list of {\"bone\": ..., \"scale\": ...}.")
    seen = set()
    for item in scales:
        bone = item.get("bone")
        if bone not in BONES or bone in seen:
            raise WorkflowError("Each scale needs a different humanoid 'bone' such as Head, LeftHand or Chest.")
        seen.add(bone)
        scale = item.get("scale")
        values = [scale] * 3 if not isinstance(scale, list) else scale
        if (len(values) != 3 or not all(not isinstance(v, bool) and isinstance(v, (int, float)) and 0.1 <= v <= 5
                                        for v in values)):
            raise WorkflowError("'scale' must be a number from 0.1 to 5, or three such numbers.")
        children = item.get("children", True)
        if not isinstance(children, bool):
            raise WorkflowError("'children' must be true (hair and accessories on the bone grow too) or false "
                                "(only the body around the bone, with Modular Avatar Scale Adjuster).")
        request["scales"].append({"bone": bone, "scale": [float(v) for v in values], "children": children})
    if not request["viewMode"] and not request["scales"]:
        raise WorkflowError("The recipe changes nothing. Add 'view' or 'scales'.")
    return request, path


def plan(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    recipe, path = load_recipe(root, args.recipe, scene_path)
    summary = {"view": recipe["viewMode"] or "unchanged", "scales": len(recipe["scales"])}
    return KIND.plan(root, args, recipe, path, summary)


def capture(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    recipe, _ = load_recipe(root, args.recipe, scene_path)
    if args.build:
        reason = toggle.prepare_sdk_outputs(root)
        if reason:
            raise WorkflowError(reason + " Capture without --build, or keep build outputs out of Git first.")
    request = {"recipe": recipe, "views": args.views, "size": args.size, "build": args.build}
    return toggle.read_only_task(root, args, request, "Capture", "ProportionCapture", "proportion-capture",
                                 KIND.helper, graphics=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Proportion recipes and the scenes they are applied in (no Unity)")
    recipes.add_argument("--project", default=None)
    read = commands.add_parser("read", help="View position, eye position and bone sizes (read-only Unity run)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
    shot = commands.add_parser("capture")
    dsh_recipe.common_arguments(shot, "capture")
    shot.add_argument("--prepare", action="store_true")
    shot.add_argument("--views", default="front,left,face")
    shot.add_argument("--size", type=int, default=512)
    shot.add_argument("--no-build", dest="build", action="store_false")
    for name in ("preview", "apply", "remove"):
        dsh_recipe.common_arguments(commands.add_parser(name), name)
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        root = find_project(project)
        if args.command == "recipes":
            output = KIND.listing(root)
        elif args.command == "read":
            output = toggle.read_only_task(root, args, {}, "Read", "Proportions", "proportions", KIND.helper)
        elif args.command == "capture":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            output = capture(root, args)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = KIND.apply(root, args, lambda: plan(root, args))
        else:
            output = KIND.remove(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
