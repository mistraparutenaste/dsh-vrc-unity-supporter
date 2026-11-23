#!/usr/bin/env python3
"""Measure the avatar's synced expression parameters (VRChat allows 256 bits), in the scene and after an SDK build
that adds what VRCFury and Modular Avatar generate. The last measurement is kept in .dsh/params so toggle, accessory
and expression previews can warn before a change goes over the limit."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside


LIMIT = 256


def cache_path(root, scene_path, avatar):
    key = hashlib.sha256(json.dumps([scene_path, avatar]).encode("utf-8")).hexdigest()[:24]
    return inside(root, f".dsh/params/{key}.json")


def measure(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    if args.build:
        reason = toggle.prepare_sdk_outputs(root)
        if reason:
            raise WorkflowError(reason + " Measure with --no-build, or keep build outputs out of Git first.")
    output = toggle.read_only_task(root, args, {"build": args.build}, "Measure", "Parameters", "parameters",
                                   "DshParameters", graphics=args.build)
    unity = output.get("unity") or {}
    if output.get("ok"):
        counted = unity.get("built") or unity.get("scene") or {}
        avatar = (unity.get("avatar") or {}).get("path") or args.avatar
        record = {"scene": scene_path, "avatar": avatar, "sceneDigest": digest(inside(root, scene_path)),
                  "built": bool(unity.get("built")), "usedBits": counted.get("usedBits", 0), "limit": LIMIT}
        for name in {args.avatar, avatar}:
            path = cache_path(root, scene_path, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")
        output["summary"] = {"usedBits": record["usedBits"], "freeBits": LIMIT - record["usedBits"],
                             "afterBuild": record["built"]}
        if record["usedBits"] > LIMIT:
            output["next"] = ("Over the limit: VRChat refuses the upload. Make toggles that only you need local "
                              "(not synced), join outfit toggles that exclude each other, or add VRCFury's Parameter "
                              "Compressor. See vrc-perf-budget.")
    return output


def budget(root, scene_path, avatar, adds):
    """What a change that adds `adds` synced bits does to the last measurement, for a preview to show."""
    record = toggle.read_result(cache_path(root, scene_path, avatar))
    if not isinstance(record.get("usedBits"), int):
        return {"measured": False, "adds": adds,
                "next": "Measure with unity_params.py measure to check the 256-bit parameter limit."}
    after = record["usedBits"] + adds
    stale = record.get("sceneDigest") != digest(inside(root, scene_path))
    result = {"measured": True, "usedBits": record["usedBits"], "adds": adds, "afterBits": after, "limit": LIMIT,
              "afterBuild": record.get("built", False), "overLimit": after > LIMIT and not stale}
    if stale:
        result["stale"] = True
        result["next"] = "The scene changed after the last measurement; measure again for an exact count."
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    action = commands.add_parser("measure")
    action.add_argument("--project", default=None)
    action.add_argument("--scene", required=True)
    action.add_argument("--avatar", default="")
    action.add_argument("--avatar-id", default="")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--no-build", dest="build", action="store_false",
                        help="Count only the scene's parameters (what VRCFury and MA add at build time is left out)")
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        output = measure(find_project(project), args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
