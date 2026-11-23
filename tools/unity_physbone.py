#!/usr/bin/env python3
"""Adjust an avatar's PhysBones without changing its prefab: how hair, skirts and tails swing, whether they can be
grabbed or posed, and colliders on humanoid bones (for example legs that keep a skirt out). Every change is recorded
so remove puts back exactly what DSH changed."""

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


KIND = dsh_recipe.RecipeKind("Assets/DSH/PhysBones", "physbones", "DshPhysBone", ("PhysBoneRecipe", "physbone-recipe"),
                             ("PhysBoneRemove", "physbone-remove"), "PhysBone recipe")
MAX_ITEMS = 100
UNIT = ("pull", "spring", "stiffness", "gravity", "gravityFalloff", "immobile", "grabMovement", "maxSquish")
RANGES = {**{field: (0, 1) for field in UNIT}, "maxStretch": (0, 5), "maxAngleX": (0, 180), "maxAngleZ": (0, 180),
          "radius": (0, 2)}
CHOICES = {"integrationType": ("Simplified", "Advanced"), "immobileType": ("AllMotion", "World"),
           "limitType": ("None", "Angle", "Hinge", "Polar")}
SWITCHES = ("allowCollision", "allowGrabbing", "allowPosing", "snapToHand")
# Starting points for common parts; values in the recipe win over the preset. In PhysBone 1.0 (version
# Version_1_0) stiffness has no effect and spring is the bounce; in 1.1 spring is called momentum.
PRESETS = {
    "soft": {"pull": 0.1, "spring": 0.4, "stiffness": 0.1, "gravity": 0.05},
    "normal": {"pull": 0.2, "spring": 0.2, "stiffness": 0.2, "gravity": 0.05},
    "stiff": {"pull": 0.4, "spring": 0.1, "stiffness": 0.5, "gravity": 0.02},
    "heavy": {"pull": 0.25, "spring": 0.1, "stiffness": 0.1, "gravity": 0.3},
    "skirt": {"pull": 0.3, "spring": 0.1, "stiffness": 0.3, "gravity": 0.15},
}


def text_value(field, value):
    if field in RANGES:
        low, high = RANGES[field]
        return f"{number(value, low, high, f'{field!r}'):g}"
    if field in CHOICES:
        if value not in CHOICES[field]:
            raise WorkflowError(f"'{field}' must be one of {', '.join(CHOICES[field])}.")
        return value
    if field in SWITCHES:
        if not isinstance(value, bool):
            raise WorkflowError(f"'{field}' must be true or false.")
        return "true" if value else "false"
    raise WorkflowError(f"DSH does not change the PhysBone value '{field}'. Use one of "
                        f"{', '.join([*RANGES, *CHOICES, *SWITCHES])}.")


def target(item, label):
    path = item.get("target")
    if not isinstance(path, str) or len(path) > 512 or path.startswith("/"):
        raise WorkflowError(f"Each {label} needs 'target': the object path from the list command.")
    index = item.get("index", -1)
    if isinstance(index, bool) or not isinstance(index, int) or not -1 <= index <= 50:
        raise WorkflowError("'index' must be a whole number from 0 (leave it out when the object has one PhysBone).")
    return {"target": path, "index": index}


def load_recipe(root, name):
    recipe, path = KIND.read(root, name)
    bones, colliders = recipe.get("bones", []), recipe.get("colliders", [])
    if any(not isinstance(items, list) or len(items) > MAX_ITEMS or not all(isinstance(i, dict) for i in items)
           for items in (bones, colliders)):
        raise WorkflowError(f"bones and colliders must be lists of up to {MAX_ITEMS} objects.")
    if not bones and not colliders:
        raise WorkflowError("The recipe changes nothing. Add bones or colliders entries.")
    request_bones = []
    for item in bones:
        preset = item.get("preset", "")
        if preset and preset not in PRESETS:
            raise WorkflowError(f"'preset' must be one of {', '.join(PRESETS)}.")
        values = item.get("values", {})
        if not isinstance(values, dict):
            raise WorkflowError("'values' must be an object such as {\"pull\": 0.2, \"allowGrabbing\": false}.")
        merged = dict(PRESETS.get(preset, {}), **values)
        if not merged:
            raise WorkflowError("Each bones entry needs a preset or values.")
        request_bones.append(dict(target(item, "bones entry"),
                                  values=[{"field": f, "value": text_value(f, v)} for f, v in merged.items()]))
    request_colliders, names = [], set()
    for item in colliders:
        name = item.get("name")
        if not isinstance(name, str) or not dsh_recipe.NAME.match(name) or name in names:
            raise WorkflowError("Each collider needs a unique 'name' of letters, digits, '_' or '-'.")
        names.add(name)
        bone = item.get("bone")
        if bone not in BONES:
            raise WorkflowError("Each collider needs 'bone': a humanoid bone such as LeftUpperLeg or Head.")
        to = item.get("to", "")
        if to and to not in BONES:
            raise WorkflowError("'to' must be a humanoid bone name.")
        shape = item.get("shape", "capsule")
        if shape not in ("capsule", "sphere"):
            raise WorkflowError("'shape' must be capsule or sphere.")
        targets = item.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_ITEMS or not all(isinstance(t, dict) for t in targets):
            raise WorkflowError("Each collider needs 'targets': the PhysBones it keeps out, as {\"target\": path}.")
        inside_bounds = item.get("insideBounds", False)
        if not isinstance(inside_bounds, bool):
            raise WorkflowError("'insideBounds' must be true or false.")
        height = item.get("height", 0)
        request_colliders.append({
            "name": name, "bone": bone, "to": to, "shape": shape,
            "radius": number(item.get("radius", 0.05), 0.005, 0.5, "'radius' (metres)"),
            "height": 0.0 if height == 0 else number(height, 0.01, 2, "'height' (metres, 0 for automatic)"),
            "offset": vector(item.get("offset", [0, 0, 0]), 1, "'offset' (metres)"),
            "insideBounds": inside_bounds,
            "targets": [dict(target(t, "collider target"), values=[]) for t in targets],
        })
    return {"name": recipe["name"], "bones": request_bones, "colliders": request_colliders}, path


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    summary = {"physBones": len(recipe["bones"]), "values": sum(len(b["values"]) for b in recipe["bones"]),
               "colliders": len(recipe["colliders"])}
    return KIND.plan(root, args, recipe, path, summary)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="PhysBone recipes and the scenes they are applied in (no Unity)")
    recipes.add_argument("--project", default=None)
    listing = commands.add_parser("list", help="PhysBones and colliders of the avatar (read-only Unity run)")
    dsh_recipe.common_arguments(listing, "list", needs_recipe=False)
    listing.add_argument("--filter", default="")
    listing.add_argument("--prepare", action="store_true")
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
        elif args.command == "list":
            output = toggle.read_only_task(root, args, {"filter": args.filter}, "List", "PhysBones", "physbones",
                                           KIND.helper)
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
