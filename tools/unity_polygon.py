#!/usr/bin/env python3
"""Fewer polygons at build time with Meshia: a triangle goal for the whole avatar and/or a ratio per mesh. The
meshes in the project stay as they are; Meshia makes reduced copies when the avatar is built. Every added
component and changed target is recorded, so remove puts back exactly what was there before."""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
from dsh_recipe import number
import unity_inspect
import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError


KIND = dsh_recipe.RecipeKind(toggle.POLYGONS, "polygons", "DshPolygon",
                             ("PolygonRecipe", "polygon-recipe"), ("PolygonRemove", "polygon-remove"),
                             "polygon recipe")
KEYS = {"name", "total", "keepFace", "keep", "smallest", "preserveBorders", "renderers", "note"}


def mesh_path(value, label):
    if not isinstance(value, str) or not value or value.startswith("/") or len(value) > 400:
        raise WorkflowError(f"{label} must be a mesh path under the avatar, such as 'Body' or 'Hair/Hair_Back'.")
    return value


def load_recipe(root, name, scene_path=None):
    recipe, path = KIND.read(root, name)
    unknown = set(recipe) - KEYS
    if unknown:
        raise WorkflowError(f"Unknown recipe keys: {', '.join(sorted(unknown))}.")
    request = {"name": name, "total": 0, "keepFace": True, "smallest": 1000, "preserveBorders": False,
               "keep": [], "renderers": [], "undo": []}
    if scene_path:
        request["undo"] = [e for e in KIND.scenes(root, name).get(scene_path, [])
                           if e.get("kind") in ("meshia-added", "meshia-target")]
    if "total" in recipe:
        request["total"] = int(number(recipe["total"], 1000, 2_000_000, "'total' (triangles for the whole avatar)"))
    for key in ("keepFace", "preserveBorders"):
        if not isinstance(recipe.get(key, request[key]), bool):
            raise WorkflowError(f"'{key}' must be true or false.")
        request[key] = recipe.get(key, request[key])
    if "smallest" in recipe:
        request["smallest"] = int(number(recipe["smallest"], 0, 100_000, "'smallest' (meshes below it are kept)"))
    keep = recipe.get("keep", [])
    if not isinstance(keep, list) or len(keep) > 100:
        raise WorkflowError("'keep' must be a list of mesh paths.")
    request["keep"] = [mesh_path(k, "Each 'keep'") for k in keep]
    renderers = recipe.get("renderers", [])
    if not isinstance(renderers, list) or len(renderers) > 100 or not all(isinstance(r, dict) for r in renderers):
        raise WorkflowError("'renderers' must be a list of {\"path\": ..., \"ratio\": ...} or {\"path\": ..., \"triangles\": ...}.")
    seen = set()
    for item in renderers:
        path_ = mesh_path(item.get("path"), "Each renderer's 'path'")
        if path_ in seen or path_ in request["keep"]:
            raise WorkflowError(f"'{path_}' is named twice (renderers and keep).")
        seen.add(path_)
        if ("ratio" in item) == ("triangles" in item):
            raise WorkflowError(f"Give '{path_}' either 'ratio' (0.05-1) or 'triangles', not both.")
        ratio = number(item["ratio"], 0.05, 1, "'ratio'") if "ratio" in item else 0
        triangles = int(number(item["triangles"], 100, 2_000_000, "'triangles'")) if "triangles" in item else 0
        request["renderers"].append({"path": path_, "ratio": ratio, "triangles": triangles})
    if not request["total"] and not request["renderers"]:
        raise WorkflowError("The recipe changes nothing. Add 'total' or 'renderers'.")
    return request, path


def rank(counts):
    limits = json.loads(unity_inspect.LIMITS.read_text(encoding="utf-8"))
    ranked = unity_inspect.rank_counts(counts or {}, limits)
    return {platform: {"rank": r["rank"], "limitedBy": r["limitedBy"]} for platform, r in ranked.items()}


def plan(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    recipe, path = load_recipe(root, args.recipe, scene_path)
    summary = {"total": recipe["total"] or "unchanged", "renderers": len(recipe["renderers"]),
               "keepFace": recipe["keepFace"]}
    output, helpers = KIND.plan(root, args, recipe, path, summary)
    output["note"] = ("The per-mesh targets are worked out in Unity from the meshes' triangles; apply reports them "
                      "('targets'). Capture first to see the result.")
    return output, helpers


def with_rank(output, *keys):
    unity = output.get("unity", {})
    for key in keys:
        node = unity
        for part in key.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict) and node:
            output.setdefault("rank", {})[key] = rank(node)
    return output


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Polygon recipes and the scenes they are applied in (no Unity)")
    recipes.add_argument("--project", default=None)
    read = commands.add_parser("read", help="Meshes, their triangles and the face (read-only Unity run)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
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
            output = toggle.read_only_task(root, args, {}, "Read", "Polygons", "polygons", KIND.helper)
            with_rank(output, "counts")
        elif args.command == "capture":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            _, scene_path = toggle.scene_asset(root, args.scene)
            recipe, _ = load_recipe(root, args.recipe, scene_path)
            reason = toggle.prepare_sdk_outputs(root)
            if reason:
                raise WorkflowError(reason)
            output = toggle.read_only_task(root, args, {"recipe": recipe, "views": args.views, "size": args.size},
                                           "Capture", "PolygonCapture", "polygon-capture", KIND.helper, graphics=True)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = KIND.apply(root, args, lambda: plan(root, args))
            with_rank(output, "sdkVerification.countsAfterBuild")
        else:
            output = KIND.remove(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
