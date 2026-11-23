#!/usr/bin/env python3
"""Check an avatar the way Gesture Manager would, without opening Unity's window: build it with the VRChat SDK,
drive the built FX controller with hand gestures, menu items and parameter values, and report per state what
changed (blendshapes, objects on or off, props frozen in the world), with pass or fail for expectations and a
render of each state. --auto makes the states from the DSH changes on the avatar. Nothing is saved."""

import argparse
import json
import os
from pathlib import Path
import sys

import unity_migrate
import unity_toggle as toggle
from unity_expression import GESTURES
from unity_inspect import find_project
from unity_toggle import WorkflowError, inside


MAX_STATES = 24


def gesture(value, label):
    if value in (None, ""):
        return -1
    if value not in GESTURES and value != "Neutral":
        raise WorkflowError(f"{label} must be one of Neutral, {', '.join(GESTURES)}.")
    return 0 if value == "Neutral" else GESTURES[value]


def expectation(item):
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise WorkflowError("Each expectation needs 'path' (an object path in the avatar, '@face', or '**/<name>').")
    out = {"path": item["path"]}
    if "shape" in item:
        out["shape"] = str(item["shape"])
        for key in ("min", "max"):
            if key in item:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise WorkflowError(f"'{key}' must be a number.")
                out[key] = float(value)
    elif "active" in item or "freezeToWorld" in item:
        key = "active" if "active" in item else "freezeToWorld"
        if not isinstance(item[key], bool):
            raise WorkflowError(f"'{key}' must be true or false.")
        out[key] = "true" if item[key] else "false"
    else:
        raise WorkflowError("Each expectation needs 'shape', 'active' or 'freezeToWorld'.")
    return out


def load_states(spec):
    states = spec.get("states") if isinstance(spec, dict) else None
    if not isinstance(states, list) or not 1 <= len(states) <= MAX_STATES:
        raise WorkflowError(f"The test needs 'states': a list of 1 to {MAX_STATES} states.")
    out = []
    for state in states:
        if not isinstance(state, dict) or not isinstance(state.get("label"), str) or not state["label"].strip():
            raise WorkflowError("Each state needs a 'label'.")
        hands = state.get("gesture", {})
        if not isinstance(hands, dict) or set(hands) - {"left", "right"}:
            raise WorkflowError("'gesture' must be {\"left\": ..., \"right\": ...}.")
        menu = state.get("menu", [])
        if not isinstance(menu, list) or not all(isinstance(m, str) and m.strip("!").strip() for m in menu):
            raise WorkflowError("'menu' must be a list of menu paths (a leading '!' turns that item off).")
        params = state.get("parameters", {})
        if not isinstance(params, dict) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) or isinstance(v, bool)
                                                   for v in params.values()):
            raise WorkflowError("'parameters' must map parameter names to numbers or true/false.")
        out.append({
            "label": state["label"], "gestureLeft": gesture(hands.get("left"), "gesture.left"),
            "gestureRight": gesture(hands.get("right"), "gesture.right"), "menu": menu,
            "parameters": [{"name": k, "value": float(v)} for k, v in params.items()],
            "expect": [expectation(e) for e in state.get("expect", [])],
        })
    return out


def auto_states(root, scene_path, avatar):
    """States and expectations from the DSH changes in force on the avatar."""
    import unity_accessory
    import unity_expression
    states = []
    for item in unity_migrate.inventory(root, scene_path, avatar):
        kind, name = item["kind"], item["name"]
        try:
            if kind == "expression":
                recipe, _ = unity_expression.load_recipe(root, name)
                face = recipe["renderer"] or "@face"

                def shapes(entry):
                    return [{"path": face, "shape": s["shape"], "min": s["weight"] - 1, "max": s["weight"] + 1}
                            for s in entry["shapes"]]
                for g in recipe["gestures"]:
                    hand = "left" if g["hand"] == "left" else "right"
                    names = {v: k for k, v in GESTURES.items()}
                    states.append({"label": f"{name}: {g['label']}", "gesture": {hand: names[g["gesture"]]},
                                   "expect": shapes(g)})
                for lock in recipe["locks"]:
                    states.append({"label": f"{name}: {lock['label']}", "menu": [f"{recipe['menu']}/{lock['label']}"],
                                   "expect": shapes(lock)})
                for t in recipe["toggles"]:
                    states.append({"label": f"{name}: {t['label']}", "menu": [f"{recipe['menu']}/{t['label']}"],
                                   "expect": shapes(t)})
            elif kind == "accessory":
                recipe, _ = unity_accessory.load_recipe(root, name)
                if not recipe["menu"]:
                    continue
                item_path = "**/" + Path(recipe["asset"]).stem
                on = [{"path": item_path, "active": True}]
                off = [{"path": item_path, "active": False}]
                states.append({"label": f"{name}: on", "menu": [recipe["menu"]], "expect": on})
                states.append({"label": f"{name}: off", "menu": ["!" + recipe["menu"]], "expect": off})
                if recipe["dropMenu"]:
                    states.append({"label": f"{name}: put down", "menu": [recipe["menu"], recipe["dropMenu"]],
                                   "expect": [{"path": item_path, "freezeToWorld": True}]})
            elif kind == "toggle" and item.get("menu") and item.get("outfit"):
                outfit = item["outfit"].split("/", 1)[1] if "/" in item["outfit"] else item["outfit"]
                states.append({"label": f"outfit {item['menu']}: on", "menu": [item["menu"]],
                               "expect": [{"path": outfit, "active": True}]})
                states.append({"label": f"outfit {item['menu']}: off", "menu": ["!" + item["menu"]],
                               "expect": [{"path": outfit, "active": False}]})
        except WorkflowError:
            continue
    if not states:
        raise WorkflowError("No DSH expressions, accessory menus or outfit toggles were found on this avatar to test. "
                            "Write the states with --spec instead.")
    return {"states": states[:MAX_STATES]}


def run(root, args):
    _, scene_path = toggle.scene_asset(root, args.scene)
    if args.spec:
        path = inside(root, args.spec) if not Path(args.spec).is_absolute() else Path(args.spec)
        try:
            spec = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            raise WorkflowError(f"Could not read the test {args.spec}: {error}") from None
    elif args.auto:
        spec = auto_states(root, scene_path, args.avatar)
    else:
        raise WorkflowError("Give --spec <file> or --auto.")
    states = load_states(spec)
    if args.render:
        reason = toggle.prepare_sdk_outputs(root)
        if reason:
            raise WorkflowError(reason)
    request = {"states": states, "views": args.views, "size": args.size, "frames": args.frames, "render": args.render}
    output = toggle.read_only_task(root, args, request, "Test", "Playback", "playback", "DshPlayback", graphics=True)
    unity = output.get("unity") or {}
    if output.get("ok"):
        output["summary"] = {"states": len(states), "failedStates": unity.get("failedStates", 0)}
        if unity.get("failedStates"):
            output["next"] = ("Some expectations failed. Read each state's checks and changedShapes, fix the recipe, "
                              "apply it again and run the test again.")
    return output


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    test = commands.add_parser("test")
    test.add_argument("--project", default=None)
    test.add_argument("--scene", required=True)
    test.add_argument("--avatar", default="")
    test.add_argument("--avatar-id", default="")
    test.add_argument("--prepare", action="store_true")
    test.add_argument("--spec", default="", help="A JSON file with the states to test")
    test.add_argument("--auto", action="store_true", help="Test the DSH changes on the avatar")
    test.add_argument("--views", default="face")
    test.add_argument("--size", type=int, default=320)
    test.add_argument("--frames", type=int, default=30)
    test.add_argument("--no-render", dest="render", action="store_false")
    args = parser.parse_args()
    try:
        project = args.project or os.getcwd()
        if not Path(project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {project}")
        if not 64 <= args.size <= 2048 or not 1 <= args.frames <= 600:
            raise WorkflowError("--size must be 64-2048 and --frames 1-600.")
        output = run(find_project(project), args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
