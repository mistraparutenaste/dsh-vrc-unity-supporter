#!/usr/bin/env python3
"""Preview or apply a scene outfit toggle, with a local Git checkpoint."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from unity_inspect import find_project, vpm_inventory


TOOLS = Path(__file__).resolve().parent
TEMPLATES = TOOLS.parent / "templates"
EDITOR = Path("Assets/DSH/Editor")
# Git blob hashes of earlier bundled helpers that may be replaced without a manual merge.
LEGACY = {
    "DshApply.cs": ("ab033a2fb00088a7ac7b1716c5c098ac1deeea71",),
    "DshInspect.cs": (
        "92de7704a6e547f8fdbb6a8abb2c543de0f3b4cc",  # 0.2.x
        "727506060aeef9224f5aa0a8eb6b21054bda6ad3",  # 0.3.0 - 0.4.1
    ),
    "DshOutfitToggle.cs": ("eeb52260a3f2ab8c44a3f46d7a949e8eb0937148",),
    "DshTextureVariant.cs": (),
    "DshCapture.cs": (),
}
HELPERS = tuple(LEGACY)
LOCAL_IGNORE = b"/.dsh/"
VRCFURY_BUILDS = "Packages/com.vrcfury.temp/Builds"
# Folders that SDK preprocessing of a verification copy writes to; kept out of Git locally.
SDK_OUTPUTS = (VRCFURY_BUILDS, "Packages/nadena.dev.ndmf/__Generated")
# Color variants (recipes, rendered textures, copied materials, clips) live here; DSH owns this folder.
VARIANTS = "Assets/DSH/Variants"
# Package files that Unity rewrites whenever it opens the project. lilToon records the graphics API,
# which differs between batch runs with and without -nographics.
UNITY_REWRITES = {"Packages/jp.lilxyzw.liltoon/Editor/CurrentRP.txt"}


class WorkflowError(Exception):
    pass


def git(root, *args, check=True):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    proc = subprocess.run(["git", "-c", "core.longpaths=true", *args], cwd=root, env=env, capture_output=True,
                          encoding="utf-8", errors="replace", check=False)
    if check and proc.returncode:
        lines = (proc.stderr or proc.stdout).strip().splitlines()
        errors = [line for line in lines if not line.startswith("warning:")]
        raise WorkflowError("\n".join((errors or lines)[-10:]) or f"git {args[0]} failed.")
    return proc


def git_state(root):
    probe = git(root, "rev-parse", "--show-toplevel", check=False)
    if probe.returncode:
        if (root / ".git").exists() or "not a git repository" not in probe.stderr.lower():
            raise WorkflowError(probe.stderr.strip())
        return {"state": "no-repository", "head": None, "changes": []}
    if Path(probe.stdout.strip()).resolve() != root:
        return {"state": "parent-repository", "head": None, "changes": []}
    head = git(root, "rev-parse", "--verify", "HEAD", check=False).stdout.strip() or None
    entries = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames").stdout
    changes = [{"status": row[:2], "path": row[3:]} for row in entries.split("\0") if row]
    return {"state": "dirty" if head and changes else "ready" if head else "no-commit",
            "head": head, "changes": changes}


def inside(root, path):
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise WorkflowError(f"Path resolves outside this project: {path}")
    return resolved


def append_rules(path, rules):
    before = path.read_bytes() if path.exists() else b""
    if rules.strip() in before.splitlines():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        if before and not before.endswith(b"\n"):
            stream.write(b"\n")
        stream.write(rules.rstrip() + b"\n")


def read_result(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def checkpoint(root, confirmed):
    state = git_state(root)
    if state["state"] == "parent-repository":
        raise WorkflowError("The project is inside another Git repository. Prepare a project-level checkpoint manually.")
    if state["head"]:
        return {"ok": state["state"] == "ready", "git": state,
                "next": "Record any existing work in Git before applying the toggle."}
    if not confirmed:
        return {"ok": True, "git": state, "needsConfirmation": True,
                "action": "Create a local first commit of project files that Git does not ignore.",
                "plannedPaths": sorted(p.name for p in root.iterdir() if p.name != ".git"),
                "next": "Review existing project files and .gitignore, then run checkpoint --confirm."}
    if state["state"] == "no-repository":
        git(root, "init", "-q")
    if any(row["status"] != "??" for row in git_state(root)["changes"]):
        raise WorkflowError("An initial Git index already contains changes. Review and commit those changes manually.")
    for identity in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        git(root, "var", identity)
    ignore = inside(root, ".gitignore")
    if not ignore.exists():
        ignore.write_bytes((TEMPLATES / "gitignore.template").read_bytes())
    else:
        # Keep project rules and add exclusions for generated data before the first commit.
        for rule in (b"/[Ll]ibrary/", b"/[Tt]emp/", b"/[Oo]bj/", b"/[Ll]ogs/", b"/[Uu]ser[Ss]ettings/", LOCAL_IGNORE):
            append_rules(ignore, rule)
    git(root, "add", "--all", "--", ".")
    git(root, "commit", "-qm", "Record Unity project before DSH changes")
    return {"ok": True, "git": git_state(root)}


def git_blob_hash(data):
    normalized = data.replace(b"\r\n", b"\n")
    git_blob = b"blob " + str(len(normalized)).encode("ascii") + b"\0" + normalized
    return hashlib.sha1(git_blob).hexdigest()


def helper_plan(root):
    helpers = []
    for name in HELPERS:
        path = EDITOR / name
        destination = inside(root, path)
        source = (TEMPLATES / "Editor" / name).read_bytes()
        if not destination.exists():
            helpers.append((path, source, None))
            continue
        actual = destination.read_bytes()
        normalized = actual.replace(b"\r\n", b"\n")
        if normalized == source.replace(b"\r\n", b"\n"):
            continue
        if git_blob_hash(actual) in LEGACY[name]:
            helpers.append((path, source, actual))
        elif name != "DshInspect.cs":
            raise WorkflowError(f"Custom helper {path.as_posix()} needs a manual merge with the bundled template.")
    return helpers


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def scene_asset(root, path):
    scene = inside(root, path)
    relative = scene.relative_to(root).as_posix()
    if not relative.startswith("Assets/") or scene.suffix.lower() != ".unity" or not scene.is_file():
        raise WorkflowError("Choose a saved .unity scene under Assets.")
    return scene, relative


def preview(root, args):
    scene, scene_path = scene_asset(root, args.scene)
    if not all(part.strip() for part in args.menu.split("/")):
        raise WorkflowError("Specify a menu name and nonempty submenu names.")
    if not args.avatar.strip() or not args.outfit.startswith(args.avatar + "/"):
        raise WorkflowError("Use full scene hierarchy paths and select an outfit below the avatar.")
    request = {"scene": scene_path, "avatar": args.avatar, "outfit": args.outfit,
               "avatarId": args.avatar_id, "outfitId": args.outfit_id,
               "menu": args.menu, "defaultOn": args.default_on}
    if args.verify_sdk:
        request["verifySdk"] = True
    helpers = helper_plan(root)
    state = git_state(root)
    owned = owned_scene_changes(root, state)
    state["managedScenes"] = sorted(owned)
    state["blockingChanges"] = list(pending_user_changes(root, state["changes"], owned))
    scene_in_checkpoint = bool(state["head"] and
                               git(root, "cat-file", "-e", f"HEAD:{scene_path}", check=False).returncode == 0)
    planned = [scene_path, *(path.as_posix() for path, _, _ in helpers)]
    meta_paths = {f"{path.as_posix()}.meta" for path, _, before in helpers if before is None}
    if helpers:
        meta_paths.update(f"{path.as_posix()}.meta" for path in (EDITOR, EDITOR.parent)
                          if not inside(root, f"{path.as_posix()}.meta").exists())
    packages, _, _ = vpm_inventory(root)
    scene_digest = digest(scene)
    contents = {"project": str(root), "request": request, "head": state["head"], "sceneDigest": scene_digest,
                "helpers": {p.as_posix(): hashlib.sha256(source).hexdigest() for p, source, _ in helpers}}
    token = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
    return {"ok": True, "project": str(root), "request": request, "git": state, "preview": token, "sceneDigest": scene_digest,
            "plannedPaths": planned, "unityMayCreate": sorted(meta_paths), "sceneInCheckpoint": scene_in_checkpoint,
            "vrcFury": packages.get("com.vrcfury.vrcfury")}, helpers


@contextmanager
def workflow_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise WorkflowError("Another DSH outfit operation is active. Wait for it and retry.") from error
        yield


def ensure_local_ignore(root, example, rule):
    if git(root, "check-ignore", "--no-index", example, check=False).returncode == 0:
        return
    exclude = git(root, "rev-parse", "--git-path", "info/exclude").stdout.strip()
    try:
        append_rules(inside(root, exclude), rule)
    except WorkflowError:
        raise WorkflowError(f"Add {rule.decode('ascii')} to this project's local Git excludes and retry.") from None
    if git(root, "check-ignore", "--no-index", example, check=False).returncode:
        raise WorkflowError(f"Git rules still include {example}. Review the local Git excludes and retry.")


def prepare_sdk_outputs(root):
    """Keep SDK verification outputs out of Git; return why verification must be skipped, if it must."""
    for folder in SDK_OUTPUTS:
        if git(root, "ls-files", "-z", "--", folder, f"{folder}.meta").stdout:
            return f"Build outputs in {folder} are tracked in Git. Verify in Build & Test."
    try:
        for folder in SDK_OUTPUTS:
            ensure_local_ignore(root, f"{folder}/probe", f"/{folder}/".encode("ascii"))
            ensure_local_ignore(root, f"{folder}.meta", f"/{folder}.meta".encode("ascii"))
    except WorkflowError as error:
        return str(error)
    return None


def owned_scene_changes(root, state):
    """Match only unstaged scene contents from successful runs at the current HEAD."""
    modified = {entry["path"] for entry in state["changes"]
                if entry["status"] == " M" and entry["path"].lower().endswith(".unity")}
    if not modified or not state["head"]:
        return {}
    digests = {path: digest(inside(root, path)) for path in modified}
    owned = {}
    for file in inside(root, ".dsh/outfits").glob("*.json"):
        receipt = read_result(file)
        output = receipt.get("output")
        unity = output.get("unity") if isinstance(output, dict) and output.get("ok") is True else None
        if not isinstance(unity, dict) or unity.get("verified") is not True:
            continue
        scene = receipt.get("scene") or unity.get("scene")  # older receipts recorded it in the Unity result
        if (isinstance(scene, str) and scene in digests and receipt.get("checkpoint") == state["head"] and
                receipt.get("sceneDigest") == digests[scene]):
            owned[scene] = digests[scene]
    return owned


def pending_user_changes(root, changes, allowed_scenes=()):
    helper_files = {path: (TEMPLATES / "Editor" / path.name).read_bytes().replace(b"\r\n", b"\n")
                    for path in (EDITOR / name for name in HELPERS)}
    meta_files = {f"{path.as_posix()}.meta" for path in (*helper_files, EDITOR, EDITOR.parent)}
    for entry in changes:
        path, status = entry["path"], entry["status"]
        if status == "??" and (path.startswith(".dsh/") or path in meta_files):
            continue
        if status in ("??", " M") and (path.startswith(VARIANTS + "/") or path == VARIANTS + ".meta"):
            continue
        if status == " M" and path in UNITY_REWRITES:
            continue
        if status == " M" and path in allowed_scenes:
            continue
        expected = helper_files.get(Path(path))
        if status in ("??", " M") and expected is not None:
            actual = inside(root, path).read_bytes()
            if actual.replace(b"\r\n", b"\n") == expected or git_blob_hash(actual) in LEGACY[Path(path).name]:
                continue
        yield entry


def apply(root, args):
    if os.name != "nt":
        raise WorkflowError("Unity batch application requires Windows.")
    plan, _ = preview(root, args)
    if plan["preview"] != args.approved_preview:
        raise WorkflowError("The preview changed. Preview again and confirm the new details before applying.")
    if not plan["git"]["head"]:
        raise WorkflowError("A project Git checkpoint is required. Review the checkpoint command before applying.")
    if not plan["sceneInCheckpoint"]:
        raise WorkflowError("The selected scene is missing from the Git checkpoint. Track and commit that scene before applying.")
    with workflow_lock(inside(root, ".dsh/outfit.lock")):
        return apply_with_lock(root, args)


def apply_with_lock(root, args):
    plan, helpers = preview(root, args)
    if plan["preview"] != args.approved_preview:
        raise WorkflowError("The preview changed. Preview again before applying.")
    request, state = plan["request"], plan["git"]
    scene = inside(root, request["scene"])
    owned = owned_scene_changes(root, state)
    receipt_id = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    receipt = inside(root, f".dsh/outfits/{receipt_id}.json")
    last = read_result(receipt)
    previous = last.get("output")
    blocking = list(pending_user_changes(root, state["changes"], owned))
    if (not args.verify_sdk and isinstance(previous, dict) and previous.get("ok") is True and not blocking and
            last.get("checkpoint") == state["head"] and last.get("sceneDigest") == plan["sceneDigest"]):
        return dict(previous, alreadyApplied=True, changes=state["changes"])
    if blocking:
        return {"ok": False, "blockingChanges": blocking,
                "error": "The project has existing Git changes. Record or set them aside, then preview again."}
    ensure_local_ignore(root, ".dsh/probe", LOCAL_IGNORE)
    skipped_sdk = prepare_sdk_outputs(root) if args.verify_sdk else None

    unity_request = dict(request, expectedSceneDigest=plan["sceneDigest"])
    if skipped_sdk:
        unity_request["verifySdk"] = False
    run, result, log = run_task(root, unity_request, helpers, "Apply", "OutfitToggle", "outfit-toggle")
    if skipped_sdk and result.get("verified") is True:
        result["sdkVerification"] = {"status": "inconclusive", "reason": skipped_sdk, "clientTested": False}
    after = git_state(root)
    allowed = {path for path, before in owned.items() if path != request["scene"] and
               inside(root, path).is_file() and digest(inside(root, path)) == before}
    allowed.add(request["scene"])
    unexpected = list(pending_user_changes(root, after["changes"], allowed))
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
            output["error"] = result.get("error") or run_error(run)
    else:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({"checkpoint": state["head"], "scene": request["scene"],
                                       "sceneDigest": saved_digest, "output": output}), encoding="utf-8")
    return output


def targets(root, args):
    if os.name != "nt":
        raise WorkflowError("Exact Unity target discovery requires Windows.")
    scene, scene_path = scene_asset(root, args.scene)
    helpers = helper_plan(root)
    if helpers and not args.prepare:
        return {"ok": False, "status": "setup-required",
                "plannedPaths": [path.as_posix() for path, _, _ in helpers],
                "error": "Confirm the Editor helper setup and rerun with --prepare to query Unity."}
    request = {"scene": scene_path, "avatar": args.avatar, "avatarId": args.avatar_id, "query": args.query}
    with workflow_lock(inside(root, ".dsh/outfit.lock")):
        before = digest(scene)
        request["expectedSceneDigest"] = before
        run, result, log = run_task(root, request, helpers, "Targets", "OutfitTargets", "outfit-targets")
        unchanged = scene.is_file() and digest(scene) == before
    ok = run.returncode == 0 and result.get("ok") is True and unchanged
    output = {"ok": ok, "status": "ready" if ok else "failed", "log": str(log), "unity": result}
    if not ok:
        output["error"] = (result.get("error") or run_error(run)) if unchanged else "The saved scene changed during discovery. Review it before applying."
    return output


def run_error(run):
    return (run.stderr.strip() or run.stdout.strip())[-4000:]


def run_task(root, request, helpers, method, task, name, helper_class="DshOutfitToggle", graphics=False):
    run_id = uuid.uuid4().hex
    request_path = inside(root, f".dsh/requests/{run_id}.json")
    request_path.parent.mkdir(parents=True, exist_ok=True)
    copy_plan = [{"file": path.name, "before": hashlib.sha256(before).hexdigest() if before is not None else None}
                 for path, _, before in helpers]
    request_path.write_text(json.dumps(dict(request, helpers=copy_plan), ensure_ascii=False), encoding="utf-8")
    run_dir = inside(root, f".dsh/runs/{run_id}")
    result_path = run_dir / "result.json"
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TOOLS / "unity-run.ps1"),
        "-Project", str(root), "-Method", f"DSH.Editor.{helper_class}.{method}", "-Name", name,
        "-RunId", run_id, "-RequestFile", str(request_path), "-ExpectedTask", task,
        "-InstallOutfitHelpers",
    ]
    if graphics:
        command.append("-AllowGraphics")
    run = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=False)
    return run, read_result(result_path), run_dir / f"{name}.log"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "apply", "targets", "checkpoint"):
        action = commands.add_parser(command)
        action.add_argument("--project", default=os.getcwd())
        if command == "checkpoint":
            action.add_argument("--confirm", action="store_true")
            continue
        if command == "targets":
            action.add_argument("--scene", required=True)
            action.add_argument("--avatar", default="")
            action.add_argument("--avatar-id", default="")
            action.add_argument("--query", default="")
            action.add_argument("--prepare", action="store_true")
            continue
        for name in ("scene", "avatar", "outfit", "menu"):
            action.add_argument("--" + name, required=True)
        action.add_argument("--avatar-id", default="")
        action.add_argument("--outfit-id", default="")
        action.add_argument("--default-on", action="store_true")
        action.add_argument("--verify-sdk", action="store_true")
        if command == "apply":
            action.add_argument("--approved-preview", required=True)
    args = parser.parse_args()
    try:
        if not Path(args.project).is_dir():
            raise WorkflowError(f"Project directory does not exist: {args.project}")
        root = find_project(args.project)
        if args.command == "checkpoint":
            output = checkpoint(root, args.confirm)
        elif args.command == "preview":
            output, _ = preview(root, args)
        elif args.command == "targets":
            output = targets(root, args)
        else:
            output = apply(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(bounded_output(output), ensure_ascii=False, separators=(",", ":")))
    return 0 if output["ok"] else 1


MAX_LISTED_CHANGES = 100
COUNT_KEYS = {"changes": "changeCount", "blockingChanges": "blockingChangeCount",
              "unexpectedChanges": "unexpectedChangeCount"}


def bounded_output(output):
    """Return a printable copy whose Git path lists are capped, with their full counts.

    The workflow itself always works on full lists; receipts on disk keep them too.
    """
    def cap(section):
        section = dict(section)
        for key, count_key in COUNT_KEYS.items():
            rows = section.get(key)
            if isinstance(rows, list):
                section[key] = rows[:MAX_LISTED_CHANGES]
                section[count_key] = len(rows)
        return section

    printable = cap(output)
    if isinstance(printable.get("git"), dict):
        printable["git"] = cap(printable["git"])
    return printable


if __name__ == "__main__":
    sys.exit(main())
