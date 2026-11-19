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
LEGACY = {
    "DshApply.cs": "ab033a2fb00088a7ac7b1716c5c098ac1deeea71",
    "DshInspect.cs": "92de7704a6e547f8fdbb6a8abb2c543de0f3b4cc",
}
HELPERS = (*LEGACY, "DshOutfitToggle.cs")
LOCAL_IGNORE = b"/.dsh/"


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
        git_blob = b"blob " + str(len(normalized)).encode("ascii") + b"\0" + normalized
        if hashlib.sha1(git_blob).hexdigest() == LEGACY.get(name):
            helpers.append((path, source, actual))
        elif name != "DshInspect.cs":
            raise WorkflowError(f"Custom helper {path.as_posix()} needs a manual merge with the bundled template.")
    return helpers


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preview(root, args):
    scene = inside(root, args.scene)
    scene_path = scene.relative_to(root).as_posix()
    if not scene_path.startswith("Assets/") or scene.suffix.lower() != ".unity" or not scene.is_file():
        raise WorkflowError("Choose a saved .unity scene under Assets.")
    if not all(part.strip() for part in args.menu.split("/")):
        raise WorkflowError("Specify a menu name and nonempty submenu names.")
    if not args.avatar.strip() or not args.outfit.startswith(args.avatar + "/"):
        raise WorkflowError("Use full scene hierarchy paths and select an outfit below the avatar.")
    request = {"scene": scene_path, "avatar": args.avatar, "outfit": args.outfit,
               "avatarId": args.avatar_id, "outfitId": args.outfit_id,
               "menu": args.menu, "defaultOn": args.default_on}
    helpers = helper_plan(root)
    state = git_state(root)
    scene_in_checkpoint = bool(state["head"] and
                               git(root, "cat-file", "-e", f"HEAD:{scene_path}", check=False).returncode == 0)
    planned = [scene_path, *(path.as_posix() for path, _, _ in helpers)]
    meta_paths = {f"{path.as_posix()}.meta" for path, _, before in helpers if before is None}
    if helpers:
        meta_paths.update(f"{path.as_posix()}.meta" for path in (EDITOR, EDITOR.parent)
                          if not inside(root, f"{path.as_posix()}.meta").exists())
    packages, _, _ = vpm_inventory(root)
    contents = {"project": str(root), "request": request, "head": state["head"], "sceneDigest": digest(scene),
                "helpers": {p.as_posix(): hashlib.sha256(source).hexdigest() for p, source, _ in helpers}}
    token = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
    return {"ok": True, "project": str(root), "request": request, "git": state, "preview": token,
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


def add_local_ignore(root):
    if git(root, "check-ignore", "--no-index", ".dsh/probe", check=False).returncode == 0:
        return
    exclude = git(root, "rev-parse", "--git-path", "info/exclude").stdout.strip()
    try:
        append_rules(inside(root, exclude), LOCAL_IGNORE)
    except WorkflowError:
        raise WorkflowError("Add /.dsh/ to this project's local Git excludes and retry.") from None
    if git(root, "check-ignore", "--no-index", ".dsh/probe", check=False).returncode:
        raise WorkflowError("Git rules still include .dsh/. Ignore that local directory and retry.")


def pending_user_changes(root, changes, allowed_scene=None):
    helper_files = {path: (TEMPLATES / "Editor" / path.name).read_bytes().replace(b"\r\n", b"\n")
                    for path in (EDITOR / name for name in HELPERS)}
    meta_files = {f"{path.as_posix()}.meta" for path in (*helper_files, EDITOR, EDITOR.parent)}
    for entry in changes:
        path, status = entry["path"], entry["status"]
        if status == "??" and (path.startswith(".dsh/") or path in meta_files):
            continue
        if status == " M" and path == allowed_scene:
            continue
        expected = helper_files.get(Path(path))
        if status in ("??", " M") and expected is not None:
            if inside(root, path).read_bytes().replace(b"\r\n", b"\n") == expected:
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
    receipt_id = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    receipt = inside(root, f".dsh/outfits/{receipt_id}.json")
    last = read_result(receipt)
    previous = last.get("output")
    if (isinstance(previous, dict) and previous.get("ok") is True and
            last.get("checkpoint") == state["head"] and last.get("sceneDigest") == digest(scene) and
            not list(pending_user_changes(root, state["changes"], request["scene"]))):
        return dict(previous, alreadyApplied=True, changes=state["changes"])
    if list(pending_user_changes(root, state["changes"])):
        raise WorkflowError("The project has existing Git changes. Record or set them aside, then preview again.")
    add_local_ignore(root)

    run_id = uuid.uuid4().hex
    request_path = inside(root, f".dsh/requests/{run_id}.json")
    request_path.parent.mkdir(parents=True, exist_ok=True)
    copy_plan = [{"file": path.name, "before": hashlib.sha256(before).hexdigest() if before is not None else None}
                 for path, _, before in helpers]
    request_path.write_text(json.dumps(dict(request, helpers=copy_plan), ensure_ascii=False), encoding="utf-8")
    run_dir = inside(root, f".dsh/runs/{run_id}")
    result_path = run_dir / "result.json"
    run = subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TOOLS / "unity-run.ps1"),
        "-Project", str(root), "-Method", "DSH.Editor.DshOutfitToggle.Apply", "-Name", "outfit-toggle",
        "-RunId", run_id, "-RequestFile", str(request_path), "-ExpectedTask", "OutfitToggle",
        "-InstallOutfitHelpers",
    ], capture_output=True, encoding="utf-8", errors="replace", check=False)
    result = read_result(result_path)
    after = git_state(root)
    unexpected = list(pending_user_changes(root, after["changes"], request["scene"]))
    ok = run.returncode == 0 and result.get("verified") is True and not unexpected and after["head"] == state["head"]
    output = {"ok": ok, "checkpoint": state["head"], "changes": after["changes"],
              "log": str(run_dir / "outfit-toggle.log"), "unity": result,
              "unexpectedChanges": unexpected}
    if not ok:
        output["error"] = result.get("error") or (
            "Additional Git paths changed or HEAD moved. Review Git status before retrying."
            if unexpected or after["head"] != state["head"] else (run.stderr.strip() or run.stdout.strip())[-4000:]
        )
    else:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({"checkpoint": state["head"], "sceneDigest": digest(scene), "output": output}),
                           encoding="utf-8")
    return output


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "apply", "checkpoint"):
        action = commands.add_parser(command)
        action.add_argument("--project", default=os.getcwd())
        if command == "checkpoint":
            action.add_argument("--confirm", action="store_true")
            continue
        for name in ("scene", "avatar", "outfit", "menu"):
            action.add_argument("--" + name, required=True)
        action.add_argument("--avatar-id", default="")
        action.add_argument("--outfit-id", default="")
        action.add_argument("--default-on", action="store_true")
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
        else:
            output = apply(root, args)
    except (WorkflowError, OSError, ValueError, SystemExit) as error:
        output = {"ok": False, "error": str(error)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
