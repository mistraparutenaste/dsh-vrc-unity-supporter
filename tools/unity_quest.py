#!/usr/bin/env python3
"""An Android (Quest) version of the avatar with VRCQuestTools, built from the same scene: VQT converts materials
to mobile shaders and drops chosen PhysBones and contacts in Android builds only; PC builds stay as they are.
'try' builds a copy as Android and measures its Mobile rank before anything is saved."""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
from dsh_recipe import number
import unity_toggle as toggle
from unity_inspect import find_project
from unity_polygon import with_rank
from unity_toggle import WorkflowError


KIND = dsh_recipe.RecipeKind(toggle.QUEST, "quest", "DshQuest",
                             ("QuestRecipe", "quest-recipe"), ("QuestRemove", "quest-remove"), "Quest recipe")
KEYS = {"name", "shader", "textureSize", "brightness", "removeOnAndroid", "note"}
SHADERS = ("toonStandard", "toonLit")
SIZES = (256, 512, 1024, 2048)


def load_recipe(root, name, scene_path=None):
    recipe, path = KIND.read(root, name)
    unknown = set(recipe) - KEYS
    if unknown:
        raise WorkflowError(f"Unknown recipe keys: {', '.join(sorted(unknown))}.")
    request = {"name": name, "shader": recipe.get("shader", "toonStandard"),
               "textureSize": recipe.get("textureSize", 1024), "brightness": 0.83, "removeOnAndroid": [], "undo": []}
    if scene_path:
        request["undo"] = [e for e in KIND.scenes(root, name).get(scene_path, [])
                           if e.get("kind") in ("vqt-converter", "vqt-remover")]
    if request["shader"] not in SHADERS:
        raise WorkflowError("'shader' must be toonStandard (VRChat Toon Standard, keeps normal maps, rim and matcaps) "
                            "or toonLit (VRChat Toon Lit, the lightest).")
    if request["textureSize"] not in SIZES:
        raise WorkflowError("'textureSize' must be 256, 512, 1024 or 2048 (the largest Android texture side).")
    if "brightness" in recipe:
        if request["shader"] != "toonLit":
            raise WorkflowError("'brightness' applies to toonLit only.")
        request["brightness"] = number(recipe["brightness"], 0, 1, "'brightness'")
    remove = recipe.get("removeOnAndroid", [])
    if (not isinstance(remove, list) or len(remove) > 200 or len(set(map(str, remove))) != len(remove) or
            not all(isinstance(p, str) and p and not p.startswith("/") for p in remove)):
        raise WorkflowError("'removeOnAndroid' must be a list of different object paths under the avatar "
                            "(objects with PhysBones, colliders or contacts).")
    request["removeOnAndroid"] = remove
    return request, path


def plan(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    recipe, path = load_recipe(root, args.recipe, scene_path)
    summary = {"shader": recipe["shader"], "textureSize": recipe["textureSize"],
               "removeOnAndroid": len(recipe["removeOnAndroid"])}
    output, helpers = KIND.plan(root, args, recipe, path, summary)
    output["note"] = ("PC builds do not change. To upload the Android version, switch the project to Android in "
                      "VCC/ALCOM or Unity (Build Settings) and upload from the SDK panel.")
    return output, helpers


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Quest recipes and the scenes they are applied in (no Unity)")
    recipes.add_argument("--project", default=None)
    read = commands.add_parser("read", help="Materials, PhysBones and contacts, and the Android setup (read-only)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
    attempt = commands.add_parser("try", help="Build a copy as Android and measure it (read-only)")
    dsh_recipe.common_arguments(attempt, "try", needs_recipe=False)
    attempt.add_argument("--recipe", default="", help="Without it, measure the Android build of the scene as it is")
    attempt.add_argument("--prepare", action="store_true")
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
            output = toggle.read_only_task(root, args, {}, "Read", "Quest", "quest", KIND.helper)
            with_rank(output, "counts")
        elif args.command == "try":
            reason = toggle.prepare_sdk_outputs(root)
            if reason:
                raise WorkflowError(reason)
            request = {"withRecipe": False}
            if args.recipe:
                _, scene_path = toggle.scene_asset(root, args.scene)
                request, _ = load_recipe(root, args.recipe, scene_path)
                request["withRecipe"] = True
            # VQT bakes the Android textures with compute shaders, so this build needs a graphics device.
            output = toggle.read_only_task(root, args, request, "Try", "QuestTry", "quest-try", KIND.helper,
                                           graphics=True)
            with_rank(output, "android.counts")
            if output.get("ok"):
                output["mobileRank"] = output["rank"]["android.counts"]["mobile"]
                output["note"] = ("On Mobile, Poor and Very Poor avatars are shown to others as a fallback by default; "
                                  "aim for Medium or better. textureMemoryMB is an uncompressed estimate and runs "
                                  "high; the SDK panel on the Android target has the final rank.")
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = KIND.apply(root, args, lambda: plan(root, args))
            with_rank(output, "sdkVerification.android.counts")
        else:
            output = KIND.remove(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
