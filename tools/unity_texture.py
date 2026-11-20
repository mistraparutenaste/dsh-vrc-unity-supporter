#!/usr/bin/env python3
"""Make color and skin variants from layered PSDs with PhotoCraft, and switch them from the avatar menu."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import unity_toggle as toggle
from unity_inspect import find_project
from unity_toggle import WorkflowError, digest, inside, read_result


VARIANTS = Path(toggle.VARIANTS)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
UV_LAYER = re.compile(r"^uv(?:[\s_-].*)?$", re.IGNORECASE)
MAX_LAYERS = 300
MAX_TEXTURES = 8
MAX_OPS = 64
TEXTURE_SUFFIXES = {".png", ".psd", ".tga", ".jpg", ".jpeg", ".tif", ".tiff", ".exr"}
PSD_SUFFIXES = {".psd", ".psb", ".png"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".psd"}


# --- PhotoCraft --------------------------------------------------------------

def photocraft_cli():
    configured = os.environ.get("PHOTOCRAFT_CLI")
    if configured:
        if not Path(configured).is_file():
            raise WorkflowError(f"PHOTOCRAFT_CLI does not point to a file: {configured}")
        return configured
    candidates = [shutil.which("photocraft-cli")]
    for base, folder in (("LOCALAPPDATA", "Programs/ArtCraft/PhotoCraft"), ("ProgramFiles", "ArtCraft/PhotoCraft")):
        if os.environ.get(base):
            candidates.append(str(Path(os.environ[base]) / folder / "photocraft-cli.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise WorkflowError("PhotoCraft CLI was not found. Install PhotoCraft (https://getartcraft.com/apps/photocraft), "
                        "or set PHOTOCRAFT_CLI to photocraft-cli.exe.")


def photocraft(*args, timeout=900):
    cli = photocraft_cli()
    command = [sys.executable, "-B", cli] if cli.endswith(".py") else [cli]  # .py: test double
    try:
        run = subprocess.run([*command, *args], capture_output=True, encoding="utf-8", errors="replace",
                             stdin=subprocess.DEVNULL, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise WorkflowError(f"PhotoCraft did not finish within {timeout} s.") from None
    if run.returncode:
        raise WorkflowError("PhotoCraft failed: " + (run.stderr.strip() or run.stdout.strip())[-2000:])
    return run


def psd_info(path):
    try:
        info = json.loads(photocraft("info", str(path)).stdout)
    except ValueError:
        raise WorkflowError(f"PhotoCraft returned unreadable document info for {path}.") from None
    if not isinstance(info, dict) or not isinstance(info.get("layers"), list):
        raise WorkflowError(f"PhotoCraft returned no layer tree for {path}.")
    return info


def flatten_layers(layers, parent=""):
    """Yield every layer in document walk order with its slash-joined path."""
    for layer in layers:
        path = f"{parent}/{layer.get('name', '')}" if parent else str(layer.get("name", ""))
        yield {"id": layer.get("id"), "path": path, "kind": layer.get("kind"), "visible": layer.get("visible"),
               "blend": layer.get("blend"), "clipped": layer.get("clipped"),
               "opacity": round(layer["opacity"], 3) if isinstance(layer.get("opacity"), (int, float)) else None}
        yield from flatten_layers(layer.get("children") or [], path)


def layer_index(layers):
    index = {}
    for layer in layers:
        index.setdefault(layer["path"], []).append(layer["id"])
    return index


def resolve_layer(index, reference):
    """Resolve 'Group/Layer' or 'Group/Layer#2' (zero-based occurrence for duplicate paths) to a layer id."""
    path, occurrence = reference, None
    match = re.fullmatch(r"(.*)#(\d+)", reference)
    if match and match.group(1) in index:
        path, occurrence = match.group(1), int(match.group(2))
    ids = index.get(path)
    if not ids:
        raise WorkflowError(f"Layer not found in the PSD: {reference}. Run the psd command to list layer paths.")
    if occurrence is None:
        if len(ids) > 1:
            raise WorkflowError(f"Several layers use the path {path}. Add #0..#{len(ids) - 1} to pick one.")
        return ids[0]
    if occurrence >= len(ids):
        raise WorkflowError(f"The PSD has {len(ids)} layer(s) at {path}; #{occurrence} does not exist.")
    return ids[occurrence]


def describe_psd(path, max_layers=MAX_LAYERS, query=""):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in PSD_SUFFIXES:
        raise WorkflowError(f"Choose an existing .psd, .psb or .png file: {path}")
    info = psd_info(path)
    layers = list(flatten_layers(info["layers"]))
    index = layer_index(layers)
    listed = [layer for layer in layers if query.lower() in layer["path"].lower()] if query else layers
    return {"ok": True, "file": str(path), "sha256": digest(path), "width": info.get("width"),
            "height": info.get("height"), "layerCount": len(layers), "matchCount": len(listed),
            "truncated": len(listed) > max_layers > 0,
            "layers": listed[:max_layers] if max_layers > 0 else listed,
            "uvLayers": [layer["path"] for layer in layers if UV_LAYER.match(layer["path"].rsplit("/", 1)[-1])],
            "duplicatePaths": sorted(path for path, ids in index.items() if len(ids) > 1)[:50],
            "warnings": info.get("warnings") or []}


# --- recipes -----------------------------------------------------------------

def variant_dir(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise WorkflowError("Use a variant name of letters, digits, '_' or '-' (up to 64 characters).")
    return inside(root, (VARIANTS / name).as_posix())


def number(op, key, low, high, default=0):
    value = op.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise WorkflowError(f"'{key}' must be a number from {low} to {high} in {op.get('op')} operations.")
    return value


def source_path(root, folder, value, suffixes, label):
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"Specify the {label} path.")
    path = Path(value)
    if not path.is_absolute():
        path = (folder / path) if label == "image" else (root / path)
    path = path.resolve()
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise WorkflowError(f"The {label} file is missing or has an unsupported type: {value}")
    return path


def load_recipe(root, name):
    folder = variant_dir(root, name)
    recipe_path = folder / "recipe.json"
    try:
        recipe = json.loads(recipe_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise WorkflowError(f"Write the recipe first: {recipe_path.relative_to(root).as_posix()}") from None
    except ValueError as error:
        raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
    if not isinstance(recipe, dict) or recipe.get("name") != name:
        raise WorkflowError(f"The recipe must be an object whose name is {name}.")
    menu = recipe.get("menu")
    if not isinstance(menu, str) or not all(part.strip() for part in menu.split("/")):
        raise WorkflowError("Specify a menu name and nonempty submenu names in the recipe.")
    tag = recipe.get("exclusiveTag", "")
    if not isinstance(tag, str) or len(tag) > 64:
        raise WorkflowError("exclusiveTag must be a short string.")
    if not isinstance(recipe.get("defaultOn", False), bool):
        raise WorkflowError("defaultOn must be true or false.")
    textures = recipe.get("textures")
    if not isinstance(textures, list) or not 1 <= len(textures) <= MAX_TEXTURES:
        raise WorkflowError(f"List 1 to {MAX_TEXTURES} textures to replace in the recipe.")
    outputs = set()
    for texture in textures:
        if not isinstance(texture, dict):
            raise WorkflowError("Each recipe texture must be an object.")
        replace = texture.get("replace")
        original = inside(root, replace) if isinstance(replace, str) else None
        if (original is None or not replace.startswith("Assets/") or not original.is_file() or
                original.suffix.lower() not in TEXTURE_SUFFIXES or original.is_relative_to(folder)):
            raise WorkflowError(f"'replace' must name an existing texture under Assets (not a variant): {replace}")
        texture["_original"] = original
        texture["_psd"] = source_path(root, folder, texture.get("psd"), PSD_SUFFIXES, "psd")
        expected = texture.get("sha256")
        if expected is not None and (not isinstance(expected, str) or expected.lower() != digest(texture["_psd"])):
            raise WorkflowError(f"The PSD changed after the recipe was written: {texture['_psd']}. Check the layers again.")
        if not isinstance(texture.get("hideUv", True), bool):
            raise WorkflowError("hideUv must be true or false.")
        output = Path(replace).stem + ".png"
        if output.lower() in outputs:
            raise WorkflowError(f"Two recipe textures would both write {output}.")
        outputs.add(output.lower())
        texture["_output"] = folder / output
        ops = texture.get("ops", [])
        if not isinstance(ops, list) or len(ops) > MAX_OPS:
            raise WorkflowError(f"List at most {MAX_OPS} operations per texture.")
        for op in ops:
            check_op(root, folder, op)
    return recipe, folder


def check_op(root, folder, op):
    if not isinstance(op, dict) or not isinstance(op.get("layer" if op.get("op") != "place" else "above"), str):
        raise WorkflowError("Each operation needs an 'op' and a layer path ('above' for place).")
    kind = op.get("op")
    if kind == "visibility":
        if not isinstance(op.get("visible"), bool):
            raise WorkflowError("visibility operations need visible: true or false.")
    elif kind == "hsl":
        colorize = op.get("colorize", False)
        if not isinstance(colorize, bool):
            raise WorkflowError("colorize must be true or false.")
        number(op, "hue", 0 if colorize else -180, 360 if colorize else 180)
        number(op, "saturation", 0 if colorize else -100, 100, 25 if colorize else 0)
        number(op, "lightness", -100, 100)
    elif kind == "place":
        op["_image"] = source_path(root, folder, op.get("image"), IMAGE_SUFFIXES, "image")
        number(op, "scale", 1, 1000, 100)
        positions = [key for key in ("center", "uv") if key in op]
        if len(positions) != 1 or not isinstance(op[positions[0]], list) or len(op[positions[0]]) != 2:
            raise WorkflowError("place needs either center: [x, y] in pixels or uv: [u, v] from 0 to 1.")
        limit = 1 if positions[0] == "uv" else 1 << 16
        for value in op[positions[0]]:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= limit:
                raise WorkflowError(f"place {positions[0]} values must be from 0 to {limit}.")
        if not isinstance(op.get("clip", True), bool):
            raise WorkflowError("clip must be true or false.")
    else:
        raise WorkflowError(f"Unknown operation '{kind}'. Use visibility, hsl or place.")


def commands_for(texture, info):
    """Translate one recipe texture into PhotoCraft engine commands."""
    layers = list(flatten_layers(info["layers"]))
    index = layer_index(layers)
    commands = []
    if texture.get("hideUv", True):
        for layer in layers:
            if UV_LAYER.match(layer["path"].rsplit("/", 1)[-1]) and layer["visible"]:
                commands.append(("layer.setProps", {"layer": layer["id"], "visible": False}))
    width, height = info.get("width"), info.get("height")
    for op in texture.get("ops", []):
        kind = op["op"]
        if kind == "visibility":
            commands.append(("layer.setProps", {"layer": resolve_layer(index, op["layer"]), "visible": op["visible"]}))
        elif kind == "hsl":
            colorize = op.get("colorize", False)
            commands.append(("layer.select", {"layer": resolve_layer(index, op["layer"])}))
            commands.append(("layer.newAdjustmentLayer.hueSaturation", {
                "hue": op.get("hue", 0), "saturation": op.get("saturation", 25 if colorize else 0),
                "lightness": op.get("lightness", 0), "colorize": colorize, "clipToPrevious": True,
                "name": "DSH " + op["layer"].rsplit("/", 1)[-1]}))
        else:
            if "uv" in op:
                if not isinstance(width, int) or not isinstance(height, int):
                    raise WorkflowError("PhotoCraft did not report the PSD size needed for UV placement.")
                u, v = op["uv"]
                center = [round(u * width), round((1 - v) * height)]  # UV origin is bottom-left
            else:
                center = op["center"]
            commands.append(("layer.select", {"layer": resolve_layer(index, op["above"])}))
            commands.append(("file.placeEmbedded", {"path": str(op["_image"]), "scale": op.get("scale", 100),
                                                    "center": center, "smartObject": False}))
            if op.get("clip", True):
                commands.append(("layer.createClippingMask", {}))
    return commands


def recipe_digest(recipe):
    """Hash the recipe as written plus the bytes of every image it places, ignoring parsed helper keys."""
    def public(value):
        if isinstance(value, dict):
            return {key: public(item) for key, item in value.items() if not key.startswith("_")}
        if isinstance(value, list):
            return [public(item) for item in value]
        return value

    images = sorted(digest(op["_image"]) for texture in recipe["textures"]
                    for op in texture.get("ops", []) if "_image" in op)
    payload = {"recipe": public(recipe), "images": images}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def render_receipt_path(root, name):
    return inside(root, f".dsh/variants/{name}.json")


def render(root, name):
    recipe, folder = load_recipe(root, name)
    outputs = []
    for texture in recipe["textures"]:
        info = psd_info(texture["_psd"])
        commands = commands_for(texture, info)
        target = texture["_output"]
        if target.resolve() == texture["_psd"]:
            raise WorkflowError("The output would replace the source PSD.")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.stem + ".partial.png")
        arguments = ["run", str(texture["_psd"])]
        for command, params in commands:
            arguments += ["--cmd", command, "--params", json.dumps(params, ensure_ascii=False)]
        photocraft(*arguments, "--out", str(partial))
        if not partial.is_file():
            raise WorkflowError(f"PhotoCraft did not write {partial.name}.")
        os.replace(partial, target)
        outputs.append({"replace": texture["replace"], "texture": target.relative_to(root).as_posix(),
                        "psd": str(texture["_psd"]), "psdSha256": digest(texture["_psd"]),
                        "sha256": digest(target), "commands": len(commands),
                        "width": info.get("width"), "height": info.get("height")})
    receipt = {"variant": name, "recipe": recipe_digest(recipe), "outputs": outputs}
    path = render_receipt_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "variant": name, "outputs": outputs,
            "next": "Capture a before/after preview, then preview and apply the variant."}


def rendered(root, name):
    """Return the recipe and the textures it produced, refusing stale or edited renders."""
    recipe, folder = load_recipe(root, name)
    receipt = read_result(render_receipt_path(root, name))
    outputs = receipt.get("outputs") if receipt.get("recipe") == recipe_digest(recipe) else None
    if not isinstance(outputs, list) or len(outputs) != len(recipe["textures"]):
        raise WorkflowError(f"Render the variant first (render --variant {name}); the recipe changed since the last render.")
    for output in outputs:
        texture = inside(root, output["texture"])
        if not texture.is_file() or digest(texture) != output["sha256"]:
            raise WorkflowError(f"{output['texture']} changed after rendering. Render the variant again.")
    return recipe, folder, outputs


# --- Unity tasks ---------------------------------------------------------------

def materials(root, args):
    output = toggle.read_only_task(root, args, {"filter": args.filter}, "Materials", "TextureMaterials",
                                   "texture-materials", "DshTextureVariant")
    if output.get("ok"):
        roots = [Path(value) for value in args.psd_dir] + [root / "Assets"]
        textures = output["unity"].get("textures") or []
        for texture in textures:
            if isinstance(texture, dict) and isinstance(texture.get("path"), str):
                texture["psdCandidates"] = psd_candidates(texture["path"], roots)
    return output


def psd_candidates(texture, roots, limit=5):
    stem = Path(texture).stem.lower()
    if Path(texture).suffix.lower() == ".psd":
        return [texture]
    found = []
    for folder in roots:
        if not folder.is_dir():
            continue
        for candidate in folder.rglob("*"):
            if candidate.suffix.lower() in (".psd", ".psb") and candidate.stem.lower() == stem:
                found.append(str(candidate))
                if len(found) >= limit:
                    return found
    return found


def capture_request(root, name):
    if not name:
        return {}
    _, _, outputs = rendered(root, name)
    return {"variant": name, "swaps": [{"from": output["replace"], "to": output["texture"]} for output in outputs]}


def capture(root, args):
    request = dict(capture_request(root, args.variant), views=args.views, size=args.size)
    return toggle.read_only_task(root, args, request, "Capture", "Capture", "capture", "DshCapture", graphics=True)


def uv_map(root, args):
    request = {"texture": args.texture, "size": args.size}
    return toggle.read_only_task(root, args, request, "Uv", "UvMap", "uv-map", "DshCapture")


def variant_request(root, args):
    recipe, folder, outputs = rendered(root, args.variant)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "variant": args.variant,
               "folder": folder.relative_to(root).as_posix(), "menu": recipe["menu"],
               "exclusiveTag": recipe.get("exclusiveTag", ""), "defaultOn": recipe.get("defaultOn", False),
               "swaps": [{"from": output["replace"], "to": output["texture"]} for output in outputs]}
    if args.verify_sdk:
        request["verifySdk"] = True
    return request, scene, outputs


def overlapping_variants(root, name, recipe):
    """Other variants that replace one of the same textures but can be switched on together with this one.

    Both would animate the same material slots, so only one of them would show in VRChat.
    """
    replaced = {texture["replace"] for texture in recipe["textures"]}
    tag = recipe.get("exclusiveTag", "")
    found = []
    for path in sorted(inside(root, VARIANTS.as_posix()).glob("*/recipe.json")):
        if path.parent.name == name:
            continue
        try:
            other = json.loads(path.read_text(encoding="utf-8-sig"))
            shared = sorted(replaced & {t.get("replace") for t in other.get("textures", []) if isinstance(t, dict)})
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        if shared and (not tag or other.get("exclusiveTag", "") != tag):
            found.append({"variant": path.parent.name, "textures": shared, "exclusiveTag": other.get("exclusiveTag", "")})
    return found


def preview(root, args):
    request, scene, outputs = variant_request(root, args)
    recipe, _ = load_recipe(root, args.variant)
    overlaps = overlapping_variants(root, args.variant, recipe)
    output, helpers = toggle.scene_plan(root, request, scene,
                                 [request["scene"], request["folder"] + "/ (materials, animation clip)"],
                                 [o["sha256"] for o in outputs])
    if overlaps:
        output["overlappingVariants"] = overlaps
        output["warning"] = ("These variants replace the same textures and can be on at the same time, so only one "
                             "would show. Give them the same exclusiveTag, or combine the changes into one recipe.")
    return output, helpers


def apply(root, args):
    return toggle.run_approved(root, args, lambda: preview(root, args), "Apply", "TextureVariant",
                               "texture-variant", "DshTextureVariant", args.verify_sdk)


# --- list and remove -------------------------------------------------------------

HOLDER = "DSH Color Variant "
REFERENCING_SUFFIXES = {".unity", ".prefab", ".mat", ".controller", ".anim", ".asset", ".overrideController"}


def scenes_with_holder(root, name):
    """Saved scenes whose YAML names this variant's toggle object (a text search; Unity is not needed)."""
    needle = f"m_Name: {HOLDER}{name}\n".encode("utf-8")
    found = []
    for scene in sorted((root / "Assets").rglob("*.unity")):
        try:
            if needle in scene.read_bytes().replace(b"\r\n", b"\n"):
                found.append(scene.relative_to(root).as_posix())
        except OSError:
            continue
    return found


def list_variants(root):
    folder = inside(root, VARIANTS.as_posix())
    variants = []
    for path in sorted(p for p in folder.glob("*") if p.is_dir()) if folder.is_dir() else []:
        name, entry = path.name, {"variant": path.name}
        try:
            recipe, _ = load_recipe(root, name)
            entry.update(menu=recipe["menu"], exclusiveTag=recipe.get("exclusiveTag", ""),
                         textures=[texture["replace"] for texture in recipe["textures"]])
            if not render_receipt_path(root, name).is_file():
                entry["render"] = "missing"
            else:
                try:
                    rendered(root, name)
                    entry["render"] = "current"
                except WorkflowError:
                    entry["render"] = "stale"  # the recipe, PSD or rendered PNG changed since the last render
            overlaps = overlapping_variants(root, name, recipe)
            if overlaps:
                entry["overlappingVariants"] = [overlap["variant"] for overlap in overlaps]
        except WorkflowError as error:
            entry["recipeError"] = str(error)
        entry["scenes"] = scenes_with_holder(root, name)
        entry["files"] = sum(1 for item in path.rglob("*") if item.is_file() and item.suffix != ".meta")
        variants.append(entry)
    return {"ok": True, "variantCount": len(variants), "variants": variants[:100]}


def asset_guids(folder):
    guids = {}
    for meta in folder.rglob("*.meta"):
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("guid: "):
                guids[line[6:].strip()] = meta.with_suffix("")
                break
    return guids


def outside_references(root, folder, scene_path):
    """Assets outside the variant folder (other than the scene) that still point at its files."""
    guids = asset_guids(folder)
    if not guids:
        return []
    found = []
    for path in (root / "Assets").rglob("*"):
        if (path.suffix not in REFERENCING_SUFFIXES or path.is_relative_to(folder) or
                path.relative_to(root).as_posix() == scene_path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        used = sorted(guids[guid].relative_to(root).as_posix() for guid in guids if guid in text)
        if used:
            found.append({"path": path.relative_to(root).as_posix(), "uses": used[:10]})
            if len(found) >= 50:
                break
    return found


def remove_plan(root, args):
    folder = variant_dir(root, args.variant)
    scene, scene_path = toggle.scene_asset(root, args.scene)
    exists = folder.is_dir()
    in_scene = scene_path in scenes_with_holder(root, args.variant)
    if not exists and not in_scene:
        raise WorkflowError(f"No variant named {args.variant} exists in this project or scene.")
    references = outside_references(root, folder, scene_path) if exists and not args.keep_files else []
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "variant": args.variant,
               "folder": folder.relative_to(root).as_posix(), "keepFiles": bool(args.keep_files), "remove": True}
    files = sorted(item.relative_to(root).as_posix() for item in folder.rglob("*") if item.is_file()) if exists else []
    fingerprint = [[path, digest(root / path)] for path in files]
    planned = [scene_path] if in_scene else []
    if exists and not args.keep_files:
        planned.append(request["folder"] + "/ (deleted with its .meta files)")
    output, helpers = toggle.scene_plan(root, request, scene, planned, fingerprint)
    output.update(toggleInScene=in_scene, deletesFiles=exists and not args.keep_files,
                  fileCount=sum(1 for path in files if not path.endswith(".meta")))
    if references:
        output.update(ok=False, otherReferences=references,
                      error="Other assets still use files of this variant. Change them back in Unity first, "
                            "or keep the files with --keep-files.")
    return output, helpers


def remove(root, args):
    if not args.approved_preview:
        output, _ = remove_plan(root, args)
        return output
    output = toggle.run_approved(root, args, lambda: remove_plan(root, args), "Remove", "TextureVariantRemove",
                                 "texture-remove", "DshTextureVariant")
    if output.get("ok") and not args.keep_files:
        render_receipt_path(root, args.variant).unlink(missing_ok=True)
    return output


# --- command line ---------------------------------------------------------------

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    psd = commands.add_parser("psd", help="List the layers of a PSD (read-only)")
    psd.add_argument("file")
    psd.add_argument("--filter", default="")
    psd.add_argument("--max-layers", type=int, default=MAX_LAYERS)

    render_parser = commands.add_parser("render", help="Render a recipe into variant textures")
    render_parser.add_argument("--project", default=os.getcwd())
    render_parser.add_argument("--variant", required=True)

    list_parser = commands.add_parser("list", help="List the color variants of a project (read-only)")
    list_parser.add_argument("--project", default=os.getcwd())

    for name in ("materials", "capture", "uv", "preview", "apply", "remove"):
        action = commands.add_parser(name)
        action.add_argument("--project", default=os.getcwd())
        action.add_argument("--scene", required=True)
        action.add_argument("--avatar", required=name in ("preview", "apply", "remove"), default="")
        action.add_argument("--avatar-id", default="")
        if name in ("materials", "capture", "uv"):
            action.add_argument("--prepare", action="store_true")
        if name == "materials":
            action.add_argument("--filter", default="")
            action.add_argument("--psd-dir", action="append", default=[])
        if name == "capture":
            action.add_argument("--variant", default="")
            action.add_argument("--views", default="front,back,left,face")
            action.add_argument("--size", type=int, default=512)
        if name == "uv":
            action.add_argument("--texture", required=True)
            action.add_argument("--size", type=int, default=2048)
        if name in ("preview", "apply"):
            action.add_argument("--variant", required=True)
            action.add_argument("--verify-sdk", action="store_true")
        if name == "apply":
            action.add_argument("--approved-preview", required=True)
        if name == "remove":
            action.add_argument("--variant", required=True)
            action.add_argument("--keep-files", action="store_true",
                                help="Only take the toggle out of the scene; keep the recipe and generated files")
            action.add_argument("--approved-preview", default="",
                                help="Without this, remove only previews what it would change")

    args = parser.parse_args()
    try:
        if args.command == "psd":
            output = describe_psd(args.file, args.max_layers, args.filter)
        else:
            if not Path(args.project).is_dir():
                raise WorkflowError(f"Project directory does not exist: {args.project}")
            root = find_project(args.project)
            if args.command == "render":
                output = render(root, args.variant)
            elif args.command == "list":
                output = list_variants(root)
            elif args.command == "remove":
                output = remove(root, args)
            elif args.command == "materials":
                output = materials(root, args)
            elif args.command == "capture":
                if not 64 <= args.size <= 2048:
                    raise WorkflowError("--size must be from 64 to 2048.")
                output = capture(root, args)
            elif args.command == "uv":
                if not 256 <= args.size <= 8192:
                    raise WorkflowError("--size must be from 256 to 8192.")
                output = uv_map(root, args)
            elif args.command == "preview":
                output, _ = preview(root, args)
            else:
                output = apply(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(toggle.bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
