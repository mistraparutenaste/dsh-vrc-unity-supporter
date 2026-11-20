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
from unity_toggle import WorkflowError, digest, git_state, inside, read_result


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

def unity_ready(root, prepare):
    if os.name != "nt":
        raise WorkflowError("Unity batch tasks require Windows.")
    helpers = toggle.helper_plan(root)
    if helpers and not prepare:
        return helpers, {"ok": False, "status": "setup-required",
                         "plannedPaths": [path.as_posix() for path, _, _ in helpers],
                         "error": "Confirm the Editor helper setup and rerun with --prepare to query Unity."}
    return helpers, None


def read_only_task(root, args, request, method, task, name, helper_class="DshTextureVariant", graphics=False):
    helpers, blocked = unity_ready(root, args.prepare)
    if blocked:
        return blocked
    scene, scene_path = toggle.scene_asset(root, args.scene)
    request = dict(request, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
    with toggle.workflow_lock(inside(root, ".dsh/outfit.lock")):
        before = digest(scene)
        request["expectedSceneDigest"] = before
        run, result, log = toggle.run_task(root, request, helpers, method, task, name,
                                           helper_class=helper_class, graphics=graphics)
        unchanged = scene.is_file() and digest(scene) == before
    ok = run.returncode == 0 and result.get("ok") is True and unchanged
    output = {"ok": ok, "log": str(log), "unity": result}
    if not ok:
        output["error"] = (result.get("error") or toggle.run_error(run)) if unchanged else \
            "The saved scene changed during a read-only task. Review it before applying."
    return output


def materials(root, args):
    output = read_only_task(root, args, {"filter": args.filter}, "Materials", "TextureMaterials", "texture-materials")
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
    return read_only_task(root, args, request, "Capture", "Capture", "capture", "DshCapture", graphics=True)


def uv_map(root, args):
    request = {"texture": args.texture, "size": args.size}
    return read_only_task(root, args, request, "Uv", "UvMap", "uv-map", "DshCapture")


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
    helpers = toggle.helper_plan(root)
    state = git_state(root)
    owned = toggle.owned_scene_changes(root, state)
    state["managedScenes"] = sorted(owned)
    state["blockingChanges"] = list(toggle.pending_user_changes(root, state["changes"], owned))
    scene_in_checkpoint = bool(state["head"] and toggle.git(root, "cat-file", "-e", f"HEAD:{request['scene']}",
                                                            check=False).returncode == 0)
    scene_digest = digest(scene)
    contents = {"project": str(root), "request": request, "head": state["head"], "sceneDigest": scene_digest,
                "textures": [output["sha256"] for output in outputs],
                "helpers": {p.as_posix(): hashlib.sha256(source).hexdigest() for p, source, _ in helpers}}
    token = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
    planned = [request["scene"], request["folder"] + "/ (materials, animation clip)",
               *(path.as_posix() for path, _, _ in helpers)]
    output = {"ok": True, "project": str(root), "request": request, "git": state, "preview": token,
              "sceneDigest": scene_digest, "plannedPaths": planned, "sceneInCheckpoint": scene_in_checkpoint}
    if overlaps:
        output["overlappingVariants"] = overlaps
        output["warning"] = ("These variants replace the same textures and can be on at the same time, so only one "
                             "would show. Give them the same exclusiveTag, or combine the changes into one recipe.")
    return output, helpers


def apply(root, args):
    if os.name != "nt":
        raise WorkflowError("Unity batch application requires Windows.")
    plan, _ = preview(root, args)
    if plan["preview"] != args.approved_preview:
        raise WorkflowError("The preview changed. Preview again and confirm the new details before applying.")
    if not plan["git"]["head"]:
        raise WorkflowError("A project Git checkpoint is required. Run unity_toggle.py checkpoint first.")
    if not plan["sceneInCheckpoint"]:
        raise WorkflowError("The selected scene is missing from the Git checkpoint. Track and commit that scene before applying.")
    with toggle.workflow_lock(inside(root, ".dsh/outfit.lock")):
        plan, helpers = preview(root, args)
        if plan["preview"] != args.approved_preview:
            raise WorkflowError("The preview changed. Preview again before applying.")
        return apply_with_lock(root, args, plan, helpers)


def apply_with_lock(root, args, plan, helpers):
    request, state = plan["request"], plan["git"]
    scene = inside(root, request["scene"])
    owned = toggle.owned_scene_changes(root, state)
    blocking = list(toggle.pending_user_changes(root, state["changes"], owned))
    if blocking:
        return {"ok": False, "blockingChanges": blocking,
                "error": "The project has existing Git changes. Record or set them aside, then preview again."}
    toggle.ensure_local_ignore(root, ".dsh/probe", toggle.LOCAL_IGNORE)
    skipped_sdk = toggle.prepare_sdk_outputs(root) if args.verify_sdk else None
    unity_request = dict(request, expectedSceneDigest=plan["sceneDigest"])
    if skipped_sdk:
        unity_request["verifySdk"] = False
    run, result, log = toggle.run_task(root, unity_request, helpers, "Apply", "TextureVariant", "texture-variant",
                                       helper_class="DshTextureVariant")
    if skipped_sdk and result.get("verified") is True:
        result["sdkVerification"] = {"status": "inconclusive", "reason": skipped_sdk, "clientTested": False}
    after = git_state(root)
    allowed = {path for path, before in owned.items() if path != request["scene"] and
               inside(root, path).is_file() and digest(inside(root, path)) == before}
    allowed.add(request["scene"])
    unexpected = list(toggle.pending_user_changes(root, after["changes"], allowed))
    saved_digest = digest(scene) if scene.is_file() else None
    matches_saved_scene = saved_digest is not None and result.get("sceneDigest") == saved_digest
    sdk_reported = not args.verify_sdk or isinstance(result.get("sdkVerification"), dict)
    ok = (run.returncode == 0 and result.get("verified") is True and matches_saved_scene and sdk_reported and
          not unexpected and after["head"] == state["head"])
    output = {"ok": ok, "checkpoint": state["head"], "changes": after["changes"],
              "log": str(log), "unity": result, "unexpectedChanges": unexpected}
    if not ok:
        if unexpected or after["head"] != state["head"]:
            output["error"] = "Additional Git paths changed or HEAD moved. Review Git status before retrying."
        elif result.get("verified") is True and not matches_saved_scene:
            output["error"] = "The saved scene changed after Unity verification. Review the scene before retrying."
        elif result.get("verified") is True and not sdk_reported:
            output["error"] = "The requested SDK verification result is missing. Review the Unity log."
        else:
            output["error"] = result.get("error") or toggle.run_error(run)
        return output
    # The outfit receipt format lets both workflows continue on this saved scene without a commit.
    receipt_id = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    receipt = inside(root, f".dsh/outfits/{receipt_id}.json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"checkpoint": state["head"], "scene": request["scene"],
                                   "sceneDigest": saved_digest, "output": output}), encoding="utf-8")
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

    for name in ("materials", "capture", "uv", "preview", "apply"):
        action = commands.add_parser(name)
        action.add_argument("--project", default=os.getcwd())
        action.add_argument("--scene", required=True)
        action.add_argument("--avatar", required=name in ("preview", "apply"), default="")
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
