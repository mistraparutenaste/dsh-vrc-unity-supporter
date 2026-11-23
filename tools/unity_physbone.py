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
    return parse_recipe(recipe), path


def parse_recipe(recipe):
    """Check a recipe (as written in recipe.json) and turn it into the Unity request."""
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
    return {"name": recipe["name"], "bones": request_bones, "colliders": request_colliders}


def plan(root, args):
    recipe, path = load_recipe(root, args.recipe)
    summary = {"physBones": len(recipe["bones"]), "values": sum(len(b["values"]) for b in recipe["bones"]),
               "colliders": len(recipe["colliders"])}
    return KIND.plan(root, args, recipe, path, summary)


MOTIONS = ("sway", "walk", "sit")


def simulate(root, args, recipe=None):
    """Play mode run of the PhysBones (see DshPhysBoneSim): swing, settling and depth into the legs."""
    motions = [m.strip() for m in args.motions.split(",") if m.strip()]
    if not motions or any(m not in MOTIONS for m in motions):
        raise WorkflowError(f"--motions must be a comma list of {', '.join(MOTIONS)}.")
    reason = toggle.prepare_sdk_outputs(root)
    if reason:
        raise WorkflowError(reason)
    request = {"motions": ",".join(motions), "views": args.views, "size": args.size, "filter": args.filter,
               "recipeJson": ""}
    if recipe:
        request["recipeJson"] = json.dumps(recipe, ensure_ascii=False)
    return toggle.read_only_task(root, args, request, "Run", "PhysBoneSim", "physbone-sim", "DshPhysBoneSim",
                                 graphics=True, keep_running=True)


GOALS = {"softer": "sway,walk", "stiffer": "sway,walk", "no-clip": "walk,sit"}


def chain_metrics(output, target):
    for chain in (output.get("unity") or {}).get("chains") or []:
        if chain["target"] == target:
            settle = chain["settleSeconds"]
            return {"swing": max(list(chain["maxSwing"].values()) or [0]),
                    "settle": settle if isinstance(settle, (int, float)) else 99.0,
                    "depth": max(list(chain["legDepth"].values()) or [0])}
    raise WorkflowError(f"The simulation did not measure {target}. Use a target from the list command.")


def satisfied(goal, now, base):
    if goal == "softer":
        return now["swing"] >= base["swing"] * 1.25 and 0.25 <= now["settle"] <= 1.5
    if goal == "stiffer":
        return now["swing"] <= base["swing"] * 0.75 and now["settle"] <= max(base["settle"], 0.3)
    return now["depth"] <= 0.01


def number_of(values, field, default):
    try:
        return float(values.get(field, default))
    except (TypeError, ValueError):
        return default


def propose(goal, raw, start, step, radii):
    """The next recipe: one step towards the goal from the values now. Returns False at the end of the range."""
    changed = False
    if goal in ("softer", "stiffer"):
        for target, values in start.items():
            entry = next((b for b in raw["bones"] if b.get("target") == target), None)
            if entry is None:
                entry = {"target": target, "values": {}}
                raw["bones"].append(entry)
            current = dict(values, **entry.get("values", {}))
            pull, stiffness = number_of(current, "pull", 0.2), number_of(current, "stiffness", 0.2)
            spring = number_of(current, "spring", 0.2)
            immobile = number_of(current, "immobile", 0)
            if goal == "softer":
                wanted = {"pull": max(0.05, round(pull * 0.75, 3)), "stiffness": max(0.0, round(stiffness * 0.6, 3)),
                          "spring": min(0.9, round(spring + 0.15, 3))}
                # From the second step, loosen what holds the chain back: its angle limit and immobile.
                if step >= 2:
                    wanted["immobile"] = round(immobile * 0.5, 3)
                    if current.get("limitType", "None") != "None":
                        for axis in ("maxAngleX", "maxAngleZ"):
                            wanted[axis] = min(90.0, number_of(current, axis, 45) + 15)
            else:
                wanted = {"pull": min(0.9, round(pull * 1.3 + 0.05, 3)),
                          "stiffness": min(0.9, round(stiffness + 0.15, 3)), "spring": max(0.0, round(spring * 0.6, 3)),
                          "immobile": min(0.9, round(immobile + 0.15, 3))}
            for field, value in wanted.items():
                if abs(value - number_of(current, field, value)) > 1e-4:
                    entry.setdefault("values", {})[field] = value
                    changed = True
        return changed
    # no-clip: capsules on the thighs, then the shins, a little thicker each step (up to 4 cm over the leg)
    targets = [{"target": t} for t in start]
    for side in ("Left", "Right"):
        for segment, first_step in (("UpperLeg", 1), ("LowerLeg", 3)):
            if step < first_step:
                continue
            name = f"Tune{side}{segment}"
            leg = radii.get(f"{side}{segment}", 0.06)
            radius = round(min(leg + 0.04, leg + 0.01 * (step - first_step + 1)), 3)
            entry = next((c for c in raw["colliders"] if c.get("name") == name), None)
            if entry is None:
                raw["colliders"].append({"name": name, "bone": f"{side}{segment}", "radius": radius, "targets": targets})
                changed = True
            elif entry["radius"] < radius:
                entry["radius"] = radius
                changed = True
    return changed


def copy(value):
    return json.loads(json.dumps(value))


def tune(root, args):
    """Try recipes in memory until the targets meet the goal (or the steps run out); write the best as a recipe."""
    goal = args.goal
    base_raw = KIND.read(root, args.recipe)[0] if args.recipe else {"bones": [], "colliders": []}
    out = args.out or (f"{args.recipe}_{goal}" if args.recipe else f"Tuned_{goal}").replace("-", "_")
    folder = KIND.recipe_dir(root, out)
    listing = toggle.read_only_task(root, args, {"filter": ""}, "List", "PhysBones", "physbones", KIND.helper)
    if not listing.get("ok"):
        return listing
    bones = listing["unity"].get("physBones") or []
    found = {b["target"]: b["values"] for b in bones}
    roots = {b["root"]: b["target"] for b in bones}
    targets = [roots.get(t, t) for t in args.target]
    missing = [t for t in targets if t not in found]
    if missing:
        raise WorkflowError(f"No PhysBone at {', '.join(missing)}. Use a target from the list command.")
    start = {t: found[t] for t in targets}
    args.motions = GOALS[goal]
    raw = copy(dict(base_raw, name=out))
    raw.setdefault("bones", [])
    raw.setdefault("colliders", [])

    def run(recipe_raw):
        has = recipe_raw["bones"] or recipe_raw["colliders"]
        result = simulate(root, args, parse_recipe(recipe_raw) if has else None)
        if not result.get("ok"):
            raise WorkflowError(result.get("error") or "The simulation failed.")
        return result

    last = run(raw)
    radii = (last.get("unity") or {}).get("legRadii") or {}
    base = {t: chain_metrics(last, t) for t in targets}
    history = [{"step": 0, "metrics": base, "recipe": args.recipe or "as it is"}]
    best, best_raw = last, copy(raw)
    met = goal == "no-clip" and all(satisfied(goal, base[t], base[t]) for t in targets)
    for step in range(1, args.iterations + 1):
        if met:
            break
        if not propose(goal, raw, start, step, radii):
            history.append({"step": step, "stopped": "the values reached the end of the allowed range"})
            break
        last = run(raw)
        metrics = {t: chain_metrics(last, t) for t in targets}
        history.append({"step": step, "metrics": metrics, "values": copy(
            {"bones": [b for b in raw["bones"] if b.get("target") in targets], "colliders": raw["colliders"]})})
        if goal == "softer" and any(m["settle"] > 1.5 for m in metrics.values()):
            history[-1]["stopped"] = "too bouncy (still moving 1.5 s after stopping); the step before is kept"
            break
        best, best_raw = last, copy(raw)
        met = all(satisfied(goal, metrics[t], base[t]) for t in targets)
    output = {"ok": True, "goal": goal, "targets": targets, "met": met, "history": history,
              "image": (best.get("unity") or {}).get("image")}
    if best_raw["bones"] or best_raw["colliders"]:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "recipe.json").write_text(json.dumps(best_raw, ensure_ascii=False, indent=2), encoding="utf-8")
        output["recipe"] = folder.relative_to(root).as_posix() + "/recipe.json"
        output["next"] = (f"Show the history and the image, then preview and apply the recipe {out} as usual "
                          "(nothing has been saved to the scene)." + ("" if met else " The goal was not fully met; say so."))
    return output


def compare(before, after):
    """Per chain: the measurements without and with the recipe, side by side."""
    rows = {}
    for label, output in (("now", before), ("recipe", after)):
        for chain in (output.get("unity") or {}).get("chains") or []:
            rows.setdefault(chain["target"], {"part": chain["part"]})[label] = {
                key: chain[key] for key in ("maxSwing", "settleSeconds", "legDepth")}
    return [dict({"target": target}, **row) for target, row in rows.items()]


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
    sim = commands.add_parser("simulate", help="Run the PhysBones in play mode and measure them (Unity with graphics)")
    dsh_recipe.common_arguments(sim, "simulate", needs_recipe=False)
    sim.add_argument("--prepare", action="store_true")
    sim.add_argument("--recipe", default="", help="Try this recipe in memory (nothing is saved)")
    sim.add_argument("--compare", action="store_true", help="With --recipe: also run without it and compare")
    sim.add_argument("--motions", default="sway,walk,sit")
    sim.add_argument("--filter", default="")
    sim.add_argument("--views", default="front,left")
    sim.add_argument("--size", type=int, default=384)
    tuning = commands.add_parser("tune", help="Try recipes in play mode until the targets meet a goal; write the best")
    dsh_recipe.common_arguments(tuning, "tune", needs_recipe=False)
    tuning.add_argument("--prepare", action="store_true")
    tuning.add_argument("--goal", required=True, choices=sorted(GOALS))
    tuning.add_argument("--target", action="append", required=True, help="A PhysBone target or root from list")
    tuning.add_argument("--recipe", default="", help="Start from this recipe (it is not changed)")
    tuning.add_argument("--out", default="", help="Name of the recipe to write (default <recipe>_<goal>)")
    tuning.add_argument("--iterations", type=int, default=4)
    tuning.add_argument("--views", default="front,left")
    tuning.add_argument("--size", type=int, default=320)
    tuning.add_argument("--filter", default="")
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
        elif args.command == "tune":
            if not 1 <= args.iterations <= 8:
                raise WorkflowError("--iterations must be from 1 to 8 (each step runs Unity for about a minute).")
            output = tune(root, args)
        elif args.command == "simulate":
            if not 64 <= args.size <= 2048:
                raise WorkflowError("--size must be from 64 to 2048.")
            if args.compare and not args.recipe:
                raise WorkflowError("--compare needs --recipe.")
            output = simulate(root, args, load_recipe(root, args.recipe)[0] if args.recipe else None)
            if args.compare and output.get("ok"):
                before = simulate(root, args, None)
                output = {"ok": before.get("ok", False), "recipe": output, "now": before,
                          "comparison": compare(before, output)}
                if not before.get("ok"):
                    output["error"] = before.get("error")
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
