#!/usr/bin/env python3
"""Make or fit 3D models with Blender in background mode and write them as FBX into Assets/DSH/Models/<name>/.

    inspect  list the meshes, armatures and humanoid bones of an FBX or .blend (read-only)
    list     model recipes and whether their FBX is current
    build    run a model recipe: "make" (accessories from shapes, tubes, lathes and outlines) or "fit" (move an outfit onto the avatar's skeleton)

Source files are never changed. Attach the result with unity_accessory.py (bone mode for made shapes,
armature mode for fitted outfits).
"""

import argparse
import glob
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside, read_result


SCRIPT = Path(__file__).resolve().parent.parent / "templates" / "Blender" / "dsh_blender.py"
MODELS = Path(toggle.MODELS)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SHAPES = ("cube", "sphere", "cylinder", "cone", "torus", "tube", "lathe", "extrude")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
SOURCES = (".fbx", ".blend")
MAX_PARTS = 64
TIMEOUT = 900


# --- Blender ----------------------------------------------------------------------

def find_blender():
    """DSH_BLENDER, then blender on PATH, then the newest standard Windows or Steam install."""
    configured = os.environ.get("DSH_BLENDER")
    if configured:
        if Path(configured).is_file():
            return configured
        raise WorkflowError(f"DSH_BLENDER points to a missing file: {configured}")
    found = shutil.which("blender")
    if found:
        return found
    candidates = []
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if base:
            candidates += glob.glob(os.path.join(base, "Blender Foundation", "Blender*", "blender.exe"))
            candidates += glob.glob(os.path.join(base, "Steam", "steamapps", "common", "Blender", "blender.exe"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += glob.glob(os.path.join(local, "Programs", "Blender Foundation", "Blender*", "blender.exe"))

    def version(path):
        match = re.search(r"Blender\s*(\d+)\.(\d+)", path)
        return tuple(int(part) for part in match.groups()) if match else (0, 0)
    if candidates:
        return max(candidates, key=version)
    raise WorkflowError("Blender was not found. Install Blender (blender.org, free) or set DSH_BLENDER to blender.exe.")


def run_blender(command, request, work):
    work.mkdir(parents=True, exist_ok=True)
    request_path, result_path = work / "request.json", work / "result.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    result_path.unlink(missing_ok=True)
    blender = find_blender()
    try:
        run = subprocess.run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(SCRIPT),
                              "--", command, str(request_path), str(result_path)],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        raise WorkflowError(f"Blender did not finish within {TIMEOUT} seconds.") from None
    (work / "blender.log").write_text(run.stdout + "\n" + run.stderr, encoding="utf-8")
    result = read_result(result_path)
    if not result:
        tail = (run.stderr.strip() or run.stdout.strip())[-2000:]
        raise WorkflowError(f"Blender returned no result (exit {run.returncode}). {tail}")
    if result.get("ok"):
        result.pop("trace", None)
    result["log"] = str(work / "blender.log")
    return result


# --- recipes ----------------------------------------------------------------------

def model_dir(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise WorkflowError("Use a model name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, (MODELS / name).as_posix())


def numbers(value, count, low, high, label):
    if (not isinstance(value, list) or len(value) != count or
            not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and low <= v <= high
                    for v in value)):
        raise WorkflowError(f"{label} must be {count} numbers from {low} to {high}.")
    return [float(v) for v in value]


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise WorkflowError(f"{label} must be a number from {low} to {high}.")
    return value


def source(root, value, label):
    if (not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value or
            any(part in ("", ".", "..") for part in value.split("/")) or not value.lower().endswith(SOURCES)):
        raise WorkflowError(f"'{label}' must be an .fbx or .blend path under Assets/ (forward slashes).")
    path = inside(root, value)
    if not path.is_file():
        raise WorkflowError(f"The {label} file does not exist: {value}")
    if value.startswith(MODELS.as_posix() + "/") and label == "outfit":
        raise WorkflowError("Fit an original outfit, not a model in Assets/DSH/Models.")
    return path


PRIMITIVES = ("cube", "sphere", "cylinder", "cone", "torus")
OUTLINES = ("star", "heart", "circle", "diamond")
BONES = re.compile(r"^(Hips|Spine|Chest|UpperChest|Neck|Head|(Left|Right)(Shoulder|UpperArm|LowerArm|Hand|UpperLeg|"
                   r"LowerLeg|Foot|Toes))$")


def points_list(value, size, low, high, least, most, label):
    if (not isinstance(value, list) or not least <= len(value) <= most or
            not all(isinstance(p, list) for p in value)):
        raise WorkflowError(f"{label} must be a list of {least} to {most} points of {size} numbers.")
    return [numbers(p, size, low, high, label) for p in value]


def flag(part, key, default):
    value = part.get(key, default)
    if not isinstance(value, bool):
        raise WorkflowError(f"{key} must be true or false.")
    return value


def make_part(part, has_avatar):
    shape = part.get("shape")
    if shape not in SHAPES:
        raise WorkflowError(f"Each part needs 'shape': one of {', '.join(SHAPES)}.")
    item = {"shape": shape,
            "position": numbers(part.get("position", [0, 0, 0]), 3, -2, 2, "position"),
            "rotation": numbers(part.get("rotation", [0, 0, 0]), 3, -360, 360, "rotation"),
            "color": part.get("color", "#ffffff"),
            "segments": int(number(part.get("segments", 32), 3, 128, "segments")),
            "mirror": flag(part, "mirror", False),
            "subdivide": int(number(part.get("subdivide", 0), 0, 3, "subdivide")),
            "bevel": number(part.get("bevel", 0), 0, 0.1, "bevel")}
    if not isinstance(item["color"], str) or not COLOR.match(item["color"]):
        raise WorkflowError("color must be '#RRGGBB'.")
    if "smooth" in part:
        item["smooth"] = flag(part, "smooth", True)
    name = part.get("name")
    if name is not None:
        if not isinstance(name, str) or not NAME.match(name) or len(name) > 40:
            raise WorkflowError("A part name uses letters, digits, '_' or '-' (up to 40 characters).")
        item["name"] = name
    if shape in PRIMITIVES:
        item.update(size=numbers(part.get("size", [0.1, 0.1, 0.1]), 3, 0.001, 2, "size"),
                    thickness=number(part.get("thickness", 0.2), 0.02, 0.9, "thickness"),
                    topRatio=number(part.get("topRatio", 0), 0, 1, "topRatio"))
    elif shape == "tube":
        item.update(points=points_list(part.get("points"), 3, -2, 2, 2, 64, "A tube's 'points'"),
                    section=part.get("section", "round"),
                    radius=number(part.get("radius", 0.005), 0.0005, 0.1, "radius"),
                    width=number(part.get("width", 0.02), 0.001, 0.2, "width"),
                    depth=number(part.get("depth", 0.002), 0.0002, 0.05, "depth"),
                    taper=number(part.get("taper", 1), 0, 4, "taper"),
                    tilt=number(part.get("tilt", 0), -360, 360, "tilt"),
                    closed=flag(part, "closed", False))
        if item["section"] not in ("round", "flat"):
            raise WorkflowError("A tube's 'section' must be round or flat.")
        if "face" in part:
            item["face"] = numbers(part["face"], 3, -1, 1, "face")
        if item["closed"] and len(item["points"]) < 3:
            raise WorkflowError("A closed tube needs at least 3 points.")
        sway = part.get("sway", False)
        if sway is True:
            sway = 4
        elif sway is False:
            sway = 0
        sway = int(number(sway, 0, 8, "sway (bones, 1 to 8, or true for 4)"))
        if sway and item["closed"]:
            raise WorkflowError("A closed tube cannot sway; sway is for tails and strings that hang free.")
        item["sway"] = sway
    elif shape == "lathe":
        item.update(profile=points_list(part.get("profile"), 2, -1, 1, 2, 64,
                                        "A lathe's 'profile' ([radius, height])"),
                    caps=flag(part, "caps", True))
        if any(r < 0 for r, _ in item["profile"]):
            raise WorkflowError("A lathe's profile radius cannot be negative.")
    elif shape == "extrude":
        outline = part.get("outline")
        if isinstance(outline, str):
            if outline not in OUTLINES:
                raise WorkflowError(f"An extrude's 'outline' must be a list of [x, y] or one of {', '.join(OUTLINES)}.")
        else:
            outline = points_list(outline, 2, -2, 2, 3, 256, "An extrude's 'outline'")
        item.update(outline=outline, size=numbers(part.get("size", [0.05, 0.05, 0.05]), 3, 0, 2, "size"),
                    depth=number(part.get("depth", 0.005), 0.0005, 0.1, "depth"),
                    corners=int(number(part.get("corners", 5), 3, 12, "corners")),
                    inner=number(part.get("inner", 0.45), 0.1, 0.95, "inner"))
    conform = part.get("conform", "")
    if conform not in ("", "snap", "surface"):
        raise WorkflowError("'conform' must be snap (move the part onto the avatar) or surface (a tube along it).")
    if conform and not has_avatar:
        raise WorkflowError("'conform' needs the recipe's 'avatar' (the avatar FBX) to know where the surface is.")
    if conform == "surface" and shape != "tube":
        raise WorkflowError("conform 'surface' is for tubes; use 'snap' to move other parts onto the avatar.")
    item["conform"] = conform
    if "toward" in part:
        item["toward"] = numbers(part["toward"], 3, -1, 1, "toward")
        if not any(item["toward"]):
            raise WorkflowError("'toward' must point somewhere (not [0, 0, 0]).")
    return item


def make_request(root, recipe):
    parts = recipe.get("parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTS or not all(isinstance(p, dict) for p in parts):
        raise WorkflowError(f"'parts' must be a list of 1 to {MAX_PARTS} shapes.")
    has_avatar = bool(recipe.get("avatar"))
    request = {"parts": [make_part(part, has_avatar) for part in parts], "join": flag(recipe, "join", True)}
    names = [part["name"] for part in request["parts"] if "name" in part]
    if len(set(names)) != len(names):
        raise WorkflowError("Part names must differ (they name the meshes and sway bones).")
    if has_avatar:
        bone = recipe.get("bone", "Head")
        if not isinstance(bone, str) or not BONES.match(bone):
            raise WorkflowError("'bone' must be the humanoid bone the model is attached to (Head, Neck, Chest, "
                                "LeftHand ...), as in vrc-accessory.")
        surfaces = recipe.get("surfaces", [])
        if (not isinstance(surfaces, list) or len(surfaces) > 32 or
                not all(isinstance(s, str) and 0 < len(s) <= 128 for s in surfaces)):
            raise WorkflowError("'surfaces' must be a list of avatar mesh names (from inspect).")
        request.update(avatar=str(source(root, recipe["avatar"], "avatar")), bone=bone, surfaces=surfaces,
                       avatarShapes=shape_values(recipe.get("avatarShapes", {}), "avatarShapes"),
                       gap=number(recipe.get("gap", 0.001), 0, 0.02, "gap"), push=flag(recipe, "push", True),
                       snap=flag(recipe, "snap", False))
        if "toward" in recipe:
            request["toward"] = numbers(recipe["toward"], 3, -1, 1, "toward")
            if not any(request["toward"]):
                raise WorkflowError("'toward' must point somewhere (not [0, 0, 0]).")
    else:
        for key in ("bone", "surfaces", "avatarShapes", "gap", "push", "snap", "toward"):
            if key in recipe:
                raise WorkflowError(f"'{key}' needs the recipe's 'avatar' (the avatar FBX).")
    return request


def shape_values(value, label):
    if (not isinstance(value, dict) or len(value) > 64 or
            not all(isinstance(k, str) and 0 < len(k) <= 128 for k in value) or
            not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100
                    for v in value.values())):
        raise WorkflowError(f"'{label}' must map body shape key names to values from 0 to 100 (as Unity shows).")
    return {k: float(v) for k, v in value.items()}


def fit_request(root, recipe):
    request = {"outfit": str(source(root, recipe.get("outfit"), "outfit")),
               "avatar": str(source(root, recipe.get("avatar"), "avatar"))}
    body = recipe.get("body", "")
    if not isinstance(body, str) or len(body) > 128:
        raise WorkflowError("'body' must be the avatar's body mesh name (or empty to use the largest mesh).")
    bone_map = recipe.get("boneMap", {})
    if (not isinstance(bone_map, dict) or len(bone_map) > 300 or
            not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in bone_map.items())):
        raise WorkflowError("'boneMap' must map outfit bone names to avatar bone names.")
    weights = recipe.get("weights", "keep")
    if weights not in ("keep", "transfer"):
        raise WorkflowError("'weights' must be keep (the outfit's own) or transfer (copied from the body).")
    scale_bones = recipe.get("scaleBones", True)
    if not isinstance(scale_bones, bool):
        raise WorkflowError("'scaleBones' must be true or false.")
    exclude = recipe.get("exclude", [])
    if not isinstance(exclude, list) or not all(isinstance(e, str) for e in exclude):
        raise WorkflowError("'exclude' must be a list of outfit mesh names.")
    if recipe.get("source"):
        request["source"] = str(source(root, recipe["source"], "source"))
    source_body = recipe.get("sourceBody", "")
    if not isinstance(source_body, str) or len(source_body) > 128:
        raise WorkflowError("'sourceBody' must be the source avatar's body mesh name (or empty).")
    follow = recipe.get("followShapes", [])
    if (not isinstance(follow, list) or len(follow) > 64 or
            not all(isinstance(n, str) and 0 < len(n) <= 128 for n in follow) or len(set(follow)) != len(follow)):
        raise WorkflowError("'followShapes' must be a list of up to 64 different body shape key names.")
    request.update(sourceBody=source_body, followShapes=follow,
                   avatarShapes=shape_values(recipe.get("avatarShapes", {}), "avatarShapes"),
                   sourceShapes=shape_values(recipe.get("sourceShapes", {}), "sourceShapes"))
    request.update(body=body, boneMap=bone_map, weights=weights, scaleBones=scale_bones, exclude=exclude,
                   push=number(recipe.get("push", 0.002), 0, 0.02, "push"),
                   # "auto" (default): items matched at the head only are scaled to clear the avatar's head.
                   scale=fit_scale(recipe.get("scale", "auto")),
                   offset=numbers(recipe.get("offset", [0, 0, 0]), 3, -0.5, 0.5, "offset"))
    return request


def fit_scale(value):
    """\"auto\" (items matched at the head only get a size that clears the avatar's head) or a fixed factor."""
    if value == "auto":
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.5 <= value <= 2:
        raise WorkflowError("'scale' must be \"auto\" or a number from 0.5 to 2.")
    return float(value)


def load_recipe(root, name):
    folder = model_dir(root, name)
    path = folder / "recipe.json"
    try:
        recipe = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise WorkflowError(f"Write the recipe first: {path.relative_to(root).as_posix()}") from None
    except ValueError as error:
        raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
    if not isinstance(recipe, dict) or recipe.get("name") != name:
        raise WorkflowError(f"The recipe must be an object whose name is {name}.")
    kind = recipe.get("kind")
    if kind == "make":
        request = make_request(root, recipe)
    elif kind == "fit":
        request = fit_request(root, recipe)
    else:
        raise WorkflowError("'kind' must be make (shapes) or fit (an outfit on the avatar's skeleton).")
    request.update(name=name, kind=kind)
    return request, path


def inputs_digest(root, request, path):
    """Recipe plus source files; the FBX is current while this matches the receipt."""
    hasher = hashlib.sha256(path.read_bytes())
    for key in ("outfit", "avatar", "source"):
        if key in request:
            hasher.update(digest(Path(request[key])).encode())
    hasher.update(SCRIPT.read_bytes())
    return hasher.hexdigest()


def receipt_path(root, name):
    return inside(root, f".dsh/models/{name}.json")


def output_path(root, name):
    return model_dir(root, name) / f"{name}.fbx"


def state(root, name, request, path):
    output = output_path(root, name)
    receipt = read_result(receipt_path(root, name))
    if not output.is_file():
        return "missing"
    if receipt.get("output") != digest(output):
        return "edited"
    return "current" if receipt.get("inputs") == inputs_digest(root, request, path) else "stale"


# --- commands -----------------------------------------------------------------------

def inspect_file(args):
    path = Path(args.file)
    if args.project and not path.is_absolute():
        path = find_project(args.project) / path
    if not path.is_file() or path.suffix.lower() not in SOURCES:
        raise WorkflowError(f"Give an existing .fbx or .blend file: {path}")
    with tempfile.TemporaryDirectory(prefix="dsh-blender-") as work:
        request = {"file": str(path)}
        if args.shapes:
            request.update(shapes=args.shapes, filter=args.filter)
        result = run_blender("inspect", request, Path(work))
        result.pop("log", None)
        return result


def list_models(root):
    folder = inside(root, MODELS.as_posix())
    models = []
    for path in sorted(p for p in folder.glob("*") if p.is_dir()) if folder.is_dir() else []:
        entry = {"model": path.name}
        try:
            request, recipe_path = load_recipe(root, path.name)
            entry.update(kind=request["kind"], fbx=state(root, path.name, request, recipe_path))
            if request["kind"] == "fit":
                entry["outfit"] = Path(request["outfit"]).relative_to(root).as_posix()
        except WorkflowError as error:
            entry["recipeError"] = str(error)
        models.append(entry)
    return {"ok": True, "modelCount": len(models), "models": models[:100]}


def build(root, args):
    request, path = load_recipe(root, args.model)
    output = output_path(root, args.model)
    current = state(root, args.model, request, path)
    if current == "edited":
        raise WorkflowError(f"{output.relative_to(root).as_posix()} was changed outside this tool. "
                            "Move it elsewhere (or delete it) before building again.")
    work = inside(root, f".dsh/runs/{uuid.uuid4().hex}")
    # Written outside Assets first, so an open Unity never imports a half-written file.
    partial = work / output.name
    request = dict(request, output=str(partial))
    if not args.no_preview:
        request["preview"] = str(work / "preview.png")
    with toggle.workflow_lock(inside(root, ".dsh/blender.lock")):
        result = run_blender(request["kind"], request, work)
        if not result.get("ok"):
            partial.unlink(missing_ok=True)
            return result
        if not partial.is_file():
            raise WorkflowError("Blender did not write the FBX.")
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial, output)
        receipt = {"model": args.model, "inputs": inputs_digest(root, request, path), "output": digest(output)}
        receipt_file = receipt_path(root, args.model)
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_file.write_text(json.dumps(receipt), encoding="utf-8")
    result["output"] = output.relative_to(root).as_posix()
    result["next"] = ("Attach it with unity_accessory.py: mode 'armature' for a fitted outfit, "
                      "mode 'bone' with origin 'bone' for a made shape. Unity imports the FBX on its next run.")
    if result.get("sway"):
        result["next"] += (" Its sway bones move once the accessory recipe lists them in 'physBones' "
                           "(root: " + ", ".join(s["root"] for s in result["sway"]) + ").")
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("file")
    inspect_parser.add_argument("--project", default="")
    inspect_parser.add_argument("--shapes", default="", help="Also list the shape key names of this mesh")
    inspect_parser.add_argument("--filter", default="", help="With --shapes: only names containing this text")
    listing = commands.add_parser("list")
    listing.add_argument("--project", default=os.getcwd())
    builder = commands.add_parser("build")
    builder.add_argument("--project", default=os.getcwd())
    builder.add_argument("--model", required=True)
    builder.add_argument("--no-preview", action="store_true", help="Skip the Blender preview renders")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            output = inspect_file(args)
        else:
            if not Path(args.project).is_dir():
                raise WorkflowError(f"Project directory does not exist: {args.project}")
            root = find_project(args.project)
            output = list_models(root) if args.command == "list" else build(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
