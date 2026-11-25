#!/usr/bin/env python3
"""Read the avatar's Expressions menu as VRChat sees it after the build, and tidy it: move or rename items, set
icons and change their order. DSH adds one "DSH Menu <name>" object with VRCFury menu components, so the author's
menu assets and the items other tools add stay as they are; remove takes the object out again."""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


FOLDER = toggle.MENUS
HELPER = "DshMenu"
HOLDER = "DSH Menu "
MAX_ENTRIES = 50
ICON_TYPES = (".png", ".jpg", ".jpeg", ".tga", ".psd", ".tif", ".tiff", ".bmp", ".exr")


def recipe_dir(root, name):
    if not isinstance(name, str) or not dsh_recipe.NAME.match(name):
        raise WorkflowError("Use a menu recipe name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, f"{FOLDER}/{name}")


def menu_path(value, label):
    """A VRCFury menu path: segments split by '/', a '/' inside a label written as '\\/'."""
    if not isinstance(value, str) or not value or len(value) > 300:
        raise WorkflowError(f"{label} must be a menu path such as 'Clothes/Hoodie'.")
    segments = value.replace("\\/", "\0").split("/")
    if any(not s.strip() for s in segments) or len(segments) > 12:
        raise WorkflowError(f"{label} has an empty part: {value!r}. Write a '/' inside a label as '\\/'.")
    return value


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
    unknown = set(recipe) - {"name", "moves", "icons", "order", "note"}
    if unknown:
        raise WorkflowError(f"Unknown recipe keys: {', '.join(sorted(unknown))}. Use moves, icons and order.")
    sections = {key: recipe.get(key, []) for key in ("moves", "icons", "order")}
    if any(not isinstance(v, list) or not all(isinstance(i, dict) for i in v) for v in sections.values()):
        raise WorkflowError("moves, icons and order must be lists of objects.")
    if not any(sections.values()):
        raise WorkflowError("The recipe changes nothing. Add moves, icons or order.")
    if sum(len(v) for v in sections.values()) > MAX_ENTRIES:
        raise WorkflowError(f"Put at most {MAX_ENTRIES} changes in one menu recipe.")
    moves, seen = [], set()
    for entry in sections["moves"]:
        source = menu_path(entry.get("from"), "'from'")
        target = menu_path(entry.get("to"), "'to'")
        if source == target or source in seen:
            raise WorkflowError(f"Each move needs a different 'from' and 'to' ({source!r}).")
        seen.add(source)
        moves.append({"from": source, "to": target})
    icons = []
    for entry in sections["icons"]:
        item = menu_path(entry.get("path"), "The icon's 'path'")
        icon = entry.get("icon")
        if (not isinstance(icon, str) or not icon.startswith("Assets/") or "\\" in icon or ".." in icon.split("/")
                or not icon.lower().endswith(ICON_TYPES)):
            raise WorkflowError("'icon' must be an image under Assets, such as 'Assets/Icons/hoodie.png'.")
        if not inside(root, icon).is_file():
            raise WorkflowError(f"The icon file does not exist: {icon}")
        icons.append({"path": item, "icon": icon})
    order = []
    for entry in sections["order"]:
        item = menu_path(entry.get("path"), "The order's 'path'")
        position = entry.get("position")
        if isinstance(position, bool) or not isinstance(position, int) or not -8 <= position <= 999:
            raise WorkflowError("'position' must be a whole number: 0 first, 1 second, 999 last, -1 second to last.")
        order.append({"path": item, "position": position})
    return {"name": name, "moves": moves, "icons": icons, "order": order}, path


def scenes_with_holder(root, name):
    return [scene for scene, holders in toggle.scene_holders(root, HOLDER).items() if HOLDER + name in holders]


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = dict(recipe, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
    if args.verify_sdk:
        request["verifySdk"] = True
    files = [[path.name, digest(path)]] + [[i["icon"], digest(inside(root, i["icon"]))] for i in recipe["icons"]]
    output, helpers = toggle.scene_plan(root, request, scene, [scene_path], files)
    output["alreadyInScene"] = scene_path in scenes_with_holder(root, recipe["name"])
    output["summary"] = {"moves": len(recipe["moves"]), "icons": len(recipe["icons"]), "order": len(recipe["order"])}
    output["note"] = ("VRCFury applies these changes to the finished menu at build time. Items other tools add "
                      "(VRCFury toggles, Modular Avatar menus) can be moved too; the author's menu assets stay.")
    return output, helpers


def remove_plan(root, args):
    recipe_dir(root, args.recipe)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    if scene_path not in scenes_with_holder(root, args.recipe):
        raise WorkflowError(f"No menu recipe named {args.recipe} is in {scene_path}.")
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "name": args.recipe}
    output, helpers = toggle.scene_plan(root, request, scene, [scene_path], [])
    output["note"] = "Only the DSH Menu object goes; the recipe file stays and the menu is as before."
    return output, helpers


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recipes = commands.add_parser("recipes", help="Menu recipes and the scenes that hold them (no Unity)")
    recipes.add_argument("--project", default=None)
    read = commands.add_parser("read", help="The menu after the SDK build (read-only Unity run)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
    read.add_argument("--no-build", dest="build", action="store_false",
                      help="Read the avatar's own menu asset only (no VRCFury or Modular Avatar items)")
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
        elif args.command == "read":
            if args.build:
                reason = toggle.prepare_sdk_outputs(root)
                if reason:
                    raise WorkflowError(reason + " Read with --no-build, or keep build outputs out of Git first.")
            # Build plugins (Avatar Optimizer, VRCQuestTools) need a graphics device, as in Build & Test.
            output = toggle.read_only_task(root, args, {"build": args.build}, "Read", "Menu", "menu", HELPER,
                                           graphics=args.build)
        elif args.command == "preview":
            output, _ = plan(root, args)
        elif args.command == "apply":
            output = toggle.run_approved(root, args, lambda: plan(root, args), "Apply", "MenuApply", "menu-apply",
                                         HELPER, args.verify_sdk)
        elif not args.approved_preview:
            output, _ = remove_plan(root, args)
        else:
            output = toggle.run_approved(root, args, lambda: remove_plan(root, args), "Remove", "MenuRemove",
                                         "menu-remove", HELPER)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
