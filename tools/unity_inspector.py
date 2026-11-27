#!/usr/bin/env python3
"""Read components as the Unity Inspector shows them (read-only Unity runs).

read: one object's components, each property with the Inspector's label, its serialized path, the value (enums by
their shown names, references as asset or object paths) and whether a prefab override changed it.
find: the objects under the avatar that have a component, by type name (part of it is enough).
"""

import argparse
import json
import os
from pathlib import Path
import sys

import dsh_recipe
import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError


HELPER = "DshInspector"


def object_path(value):
    if not isinstance(value, str) or value.startswith("/") or len(value) > 400 or "\\" in value:
        raise WorkflowError("--path must be an object path under the avatar, such as 'Armature/Hips' ('' is the avatar).")
    return value


def text_filter(value, label):
    if not isinstance(value, str) or len(value) > 200:
        raise WorkflowError(f"{label} must be up to 200 characters.")
    return value.strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    read = commands.add_parser("read", help="One object's components and their Inspector values (read-only)")
    dsh_recipe.common_arguments(read, "read", needs_recipe=False)
    read.add_argument("--prepare", action="store_true")
    read.add_argument("--path", default="", help="Object under the avatar; empty for the avatar root")
    read.add_argument("--component", default="", help="Only components whose type name contains this")
    read.add_argument("--field", default="", help="Only properties whose label or path contains this")
    read.add_argument("--hidden", action="store_true", help="Also properties the Inspector hides")
    read.add_argument("--max-properties", type=int, default=400)
    read.add_argument("--max-depth", type=int, default=6)
    read.add_argument("--array-items", type=int, default=20)
    find = commands.add_parser("find", help="Objects under the avatar with a component type (read-only)")
    dsh_recipe.common_arguments(find, "find", needs_recipe=False)
    find.add_argument("--prepare", action="store_true")
    find.add_argument("--type", required=True, help="Component type name, e.g. ModularAvatarMenuItem or VRCPhysBone")
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        root = find_project(project)
        if args.command == "read":
            for value, low, high, label in ((args.max_properties, 10, 3000, "--max-properties"),
                                            (args.max_depth, 0, 20, "--max-depth"),
                                            (args.array_items, 1, 500, "--array-items")):
                if not low <= value <= high:
                    raise WorkflowError(f"{label} must be from {low} to {high}.")
            request = {"path": object_path(args.path), "component": text_filter(args.component, "--component"),
                       "field": text_filter(args.field, "--field"), "hidden": args.hidden,
                       "maxProperties": args.max_properties, "maxDepth": args.max_depth,
                       "arrayItems": args.array_items}
            output = toggle.read_only_task(root, args, request, "Read", "Inspector", "inspector", HELPER)
        else:
            kind = text_filter(args.type, "--type")
            if not kind:
                raise WorkflowError("--type must name a component type, such as VRCPhysBone.")
            output = toggle.read_only_task(root, args, {"find": kind}, "Find", "InspectorFind", "inspector-find",
                                           HELPER)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
