#!/usr/bin/env python3
"""A lighter avatar at build time: Avatar Optimizer's Trace and Optimize (merges skinned meshes, removes unused
bones, objects and blendshapes) and TexTransTool atlases (smaller textures, merged materials). The meshes,
materials and textures in the project stay as they are; the upload build uses the results. Every added component
and object is recorded, so remove takes out exactly what DSH added."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import dsh_recipe
import unity_toggle as toggle
from unity_inspect import find_project
from unity_polygon import with_rank
from unity_toggle import WorkflowError


KIND = dsh_recipe.RecipeKind(toggle.OPTIMIZE, "optimize", "DshOptimize",
                             ("OptimizeRecipe", "optimize-recipe"), ("OptimizeRemove", "optimize-remove"),
                             "optimize recipe")
KEYS = {"name", "traceAndOptimize", "aaoOptions", "textures", "atlas", "note"}
SIZES = (256, 512, 1024, 2048, 4096)
OPTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
UNDO_KINDS = ("aao-trace", "optimize-holder")


def material_names(value, label, allow_all=False):
    if (not isinstance(value, list) or not value or len(value) > 200 or
            not all(isinstance(m, str) and m.strip() and len(m) <= 400 for m in value) or
            len(set(value)) != len(value)):
        raise WorkflowError(f"{label} must be a list of different material names (or asset paths).")
    if "*" in value and (not allow_all or len(value) > 1):
        raise WorkflowError(f"{label} takes '*' alone, for every material." if allow_all else
                            f"{label} cannot use '*'; name the materials.")
    return value


def size(value, label):
    if value not in SIZES:
        raise WorkflowError(f"{label} must be one of {', '.join(map(str, SIZES))} (the longest texture side).")
    return value


def load_recipe(root, name, scene_path=None):
    recipe, path = KIND.read(root, name)
    unknown = set(recipe) - KEYS
    if unknown:
        raise WorkflowError(f"Unknown recipe keys: {', '.join(sorted(unknown))}.")
    request = {"name": name, "traceAndOptimize": False, "aaoOptions": [], "textureSize": 0,
               "textureMaterials": [], "textureExclude": [], "atlas": [], "undo": []}
    if scene_path:
        request["undo"] = [e for e in KIND.scenes(root, name).get(scene_path, []) if e.get("kind") in UNDO_KINDS]
    trace = recipe.get("traceAndOptimize", False)
    if not isinstance(trace, bool):
        raise WorkflowError("'traceAndOptimize' must be true or false.")
    request["traceAndOptimize"] = trace
    options = recipe.get("aaoOptions", {})
    if not isinstance(options, dict) or len(options) > 40:
        raise WorkflowError("'aaoOptions' must be an object of option names (from read: aao.options[].path) to true or false.")
    if options and not trace:
        raise WorkflowError("'aaoOptions' needs \"traceAndOptimize\": true.")
    for key, value in options.items():
        if not OPTION.match(key) or not isinstance(value, bool):
            raise WorkflowError(f"'aaoOptions' {key!r} must be an option path from read, set to true or false.")
        request["aaoOptions"].append({"path": key, "value": value})
    textures = recipe.get("textures")
    if textures is not None:
        if not isinstance(textures, dict) or set(textures) - {"size", "materials", "exclude"}:
            raise WorkflowError("'textures' must be {\"size\": 1024, \"materials\": [\"*\"], \"exclude\": [...]}.")
        request["textureSize"] = size(textures.get("size"), "'textures.size'")
        request["textureMaterials"] = material_names(textures.get("materials", ["*"]), "'textures.materials'", True)
        exclude = textures.get("exclude", [])
        request["textureExclude"] = material_names(exclude, "'textures.exclude'") if exclude else []
    atlas = recipe.get("atlas", [])
    if not isinstance(atlas, list) or len(atlas) > 20 or not all(isinstance(g, dict) for g in atlas):
        raise WorkflowError("'atlas' must be a list of {\"materials\": [...], \"size\": 2048, \"merge\": true}.")
    seen = set()
    for index, group in enumerate(atlas, 1):
        if set(group) - {"materials", "size", "merge"}:
            raise WorkflowError(f"Atlas {index} takes only 'materials', 'size' and 'merge'.")
        materials = material_names(group.get("materials"), f"Atlas {index} 'materials'")
        twice = seen.intersection(materials)
        if twice:
            raise WorkflowError(f"{', '.join(sorted(twice))} is in two atlas groups.")
        seen.update(materials)
        merge = group.get("merge", True)
        if not isinstance(merge, bool):
            raise WorkflowError(f"Atlas {index} 'merge' must be true or false.")
        if merge and len(materials) < 2:
            raise WorkflowError(f"Atlas {index} merges one material; name two or more, or set \"merge\": false.")
        request["atlas"].append({"materials": materials, "size": size(group.get("size", 2048), f"Atlas {index} 'size'"),
                                 "merge": merge})
    if not trace and not request["textureSize"] and not request["atlas"]:
        raise WorkflowError("The recipe changes nothing. Add 'traceAndOptimize', 'textures' or 'atlas'.")
    return request, path


def plan(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    recipe, path = load_recipe(root, args.recipe, scene_path)
    summary = {"traceAndOptimize": recipe["traceAndOptimize"], "aaoOptions": len(recipe["aaoOptions"]),
               "textureSize": recipe["textureSize"] or "unchanged", "atlas": len(recipe["atlas"])}
    output, helpers = KIND.plan(root, args, recipe, path, summary)
    output["note"] = ("The atlas groups are worked out in Unity from the materials' textures; try or capture shows "
                      "them ('groups') and the counts after the build before anything is saved.")
    return output, helpers


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Optimize recipes and the scenes they are applied in (no Unity)")
    recipes.add_argument("--project", default=None)
    read = commands.add_parser("read", help="Materials, textures, meshes, bones and the tools' settings (read-only)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
    attempt = commands.add_parser("try", help="Build copies with and without the recipe and compare (read-only)")
    dsh_recipe.common_arguments(attempt, "try", needs_recipe=False)
    attempt.add_argument("--recipe", default="", help="Without it, measure the build of the scene as it is")
    attempt.add_argument("--prepare", action="store_true")
    shot = commands.add_parser("capture", help="Before and after, both built by the SDK (needs a GPU)")
    dsh_recipe.common_arguments(shot, "capture")
    shot.add_argument("--prepare", action="store_true")
    shot.add_argument("--views", default="front,back")
    shot.add_argument("--size", type=int, default=512)
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
            output = toggle.read_only_task(root, args, {}, "Read", "Optimize", "optimize", KIND.helper)
            with_rank(output, "counts")
        elif args.command in ("try", "capture"):
            if args.command == "capture" and not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            reason = toggle.prepare_sdk_outputs(root)
            if reason:
                raise WorkflowError(reason)
            request = {"withRecipe": False}
            if args.recipe:
                _, scene_path = toggle.scene_asset(root, args.scene)
                request, _ = load_recipe(root, args.recipe, scene_path)
                request["withRecipe"] = True
            # Avatar Optimizer's mesh passes and TexTransTool's texture baking need a graphics device.
            if args.command == "try":
                output = toggle.read_only_task(root, args, request, "Try", "OptimizeTry", "optimize-try", KIND.helper,
                                               graphics=True)
                with_rank(output, "compare.before", "compare.after", "built")
            else:
                output = toggle.read_only_task(root, args, {"recipe": request, "views": args.views, "size": args.size},
                                               "Capture", "OptimizeCapture", "optimize-capture", KIND.helper,
                                               graphics=True)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = KIND.apply(root, args, lambda: plan(root, args))
            with_rank(output, "sdkVerification.countsBeforeRecipe", "sdkVerification.countsAfterBuild")
        else:
            output = KIND.remove(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
