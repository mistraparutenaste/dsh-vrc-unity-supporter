"""Shared parts of the recipe workflows whose Unity helper reports undo entries (PhysBones, proportions).

A recipe lives at Assets/DSH/<Kind>/<name>/recipe.json. Apply saves the scene and records, per scene, the undo
entries Unity reported in .dsh/<kind>/<name>.json; the first entry per key is kept across applies, so remove puts
back the value from before DSH changed it. Remove sends the record back to Unity and forgets that scene.
"""

import json
import re

import unity_toggle as toggle
from unity_toggle import WorkflowError, digest, inside


NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class RecipeKind:
    def __init__(self, folder, record, helper, apply_task, remove_task, label):
        self.folder = folder          # Assets/DSH/PhysBones
        self.record = record          # physbones (under .dsh/)
        self.helper = helper          # DshPhysBone
        self.apply_task = apply_task  # (task name, log name), e.g. ("PhysBoneRecipe", "physbone-recipe")
        self.remove_task = remove_task
        self.label = label            # "PhysBone recipe"

    def recipe_dir(self, root, name):
        if not isinstance(name, str) or not NAME.match(name):
            raise WorkflowError("Use a recipe name of letters, digits, '_' or '-' (up to 64 characters).")
        return inside(root, f"{self.folder}/{name}")

    def read(self, root, name):
        path = self.recipe_dir(root, name) / "recipe.json"
        try:
            recipe = json.loads(path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            raise WorkflowError(f"Write the recipe first: {path.relative_to(root).as_posix()}") from None
        except ValueError as error:
            raise WorkflowError(f"The recipe is not valid JSON: {error}") from None
        if not isinstance(recipe, dict) or recipe.get("name") != name:
            raise WorkflowError(f"The recipe must be an object whose name is {name}.")
        return recipe, path

    def undo_path(self, root, name):
        self.recipe_dir(root, name)
        return inside(root, f".dsh/{self.record}/{name}.json")

    def scenes(self, root, name):
        scenes = toggle.read_result(self.undo_path(root, name)).get("scenes")
        return scenes if isinstance(scenes, dict) else {}

    def write_scenes(self, root, name, scenes):
        path = self.undo_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"recipe": name, "scenes": scenes}, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def merge(earlier, later):
        merged = [entry for entry in earlier if isinstance(entry, dict)]
        keys = {entry.get("key") for entry in merged}
        for entry in later or []:
            if isinstance(entry, dict) and entry.get("key") not in keys:
                merged.append(entry)
                keys.add(entry.get("key"))
        return merged

    def plan(self, root, args, request, path, summary, extra_files=()):
        scene, scene_path = toggle.scene_asset(root, args.scene)
        request = dict(request, scene=scene_path, avatar=args.avatar, avatarId=args.avatar_id)
        if getattr(args, "verify_sdk", False):
            request["verifySdk"] = True
        files = [[path.name, digest(path)], *extra_files]
        output, helpers = toggle.scene_plan(root, request, scene, [scene_path], files)
        output["summary"] = summary
        return output, helpers

    def apply(self, root, args, make_plan):
        task, log = self.apply_task
        output = toggle.run_approved(root, args, make_plan, "Apply", task, log, self.helper, args.verify_sdk)
        undo = output.get("unity", {}).get("undo") if output.get("ok") else None
        if isinstance(undo, list):
            scenes = self.scenes(root, args.recipe)
            scene = output["unity"].get("scene") or args.scene
            scenes[scene] = self.merge(scenes.get(scene, []), undo)
            self.write_scenes(root, args.recipe, scenes)
        return output

    def remove_plan(self, root, args):
        scene, scene_path = toggle.scene_asset(root, args.scene)
        undo = self.scenes(root, args.recipe).get(scene_path)
        if not undo:
            raise WorkflowError(f"There is no record of what {args.recipe} changed in {scene_path} (it was not applied "
                                "there, or in another copy of the project). Restore the scene from Git instead.")
        request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "name": args.recipe,
                   "undo": undo}
        output, helpers = toggle.scene_plan(root, request, scene, [scene_path], [])
        kinds = {}
        for entry in undo:
            kinds[entry.get("kind")] = kinds.get(entry.get("kind"), 0) + 1
        output["summary"] = kinds
        output["next"] = (f"Confirm what goes back, then rerun with --approved-preview. Only what this {self.label} "
                          "changed is put back; the recipe file stays.")
        return output, helpers

    def remove(self, root, args):
        if not args.approved_preview:
            output, _ = self.remove_plan(root, args)
            return output
        task, log = self.remove_task
        output = toggle.run_approved(root, args, lambda: self.remove_plan(root, args), "Remove", task, log, self.helper)
        if output.get("ok"):
            scenes = self.scenes(root, args.recipe)
            scenes.pop(output.get("unity", {}).get("scene") or args.scene, None)
            self.write_scenes(root, args.recipe, scenes)
        return output

    def listing(self, root):
        folder = inside(root, self.folder)
        items = []
        for path in sorted(p for p in folder.glob("*") if p.is_dir()) if folder.is_dir() else []:
            try:
                scenes = sorted(self.scenes(root, path.name))
            except WorkflowError:
                continue
            items.append({"recipe": path.name, "appliedIn": scenes})
        return {"ok": True, "recipeCount": len(items), "recipes": items[:100]}


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise WorkflowError(f"{label} must be a number from {low} to {high}.")
    return float(value)


def vector(value, limit, label):
    if (not isinstance(value, list) or len(value) != 3 or
            not all(not isinstance(v, bool) and isinstance(v, (int, float)) and abs(v) <= limit for v in value)):
        raise WorkflowError(f"{label} must be three numbers, each within ±{limit}.")
    return [float(v) for v in value]


def common_arguments(action, name, needs_recipe=True):
    action.add_argument("--project", default=None)
    action.add_argument("--scene", required=True)
    action.add_argument("--avatar", required=name in ("preview", "apply", "remove"), default="")
    action.add_argument("--avatar-id", default="")
    if needs_recipe:
        action.add_argument("--recipe", required=True)
    if name in ("preview", "apply"):
        action.add_argument("--verify-sdk", action="store_true")
    if name == "apply":
        action.add_argument("--approved-preview", required=True)
    if name == "remove":
        action.add_argument("--approved-preview", default="",
                            help="Without this, remove only previews what it would change")
