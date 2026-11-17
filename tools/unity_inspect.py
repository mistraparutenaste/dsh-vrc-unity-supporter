#!/usr/bin/env python3
"""Read a Unity project without opening the editor.

Commands:
  report      project summary: SDK packages, avatars, missing scripts, missing .meta
  index       build a GUID -> asset path index under <project>/.dsh/guid-index.json
  hierarchy   dump the object tree of a .prefab or .unity file
  refs        find files that reference a GUID

Everything here is read-only. It never writes inside Assets/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    "Library", "Temp", "obj", "Logs", "Build", "Builds", "UserSettings",
    ".git", ".dsh", "node_modules", "Recordings",
}

DOC_RE = re.compile(r"^--- !u!(\d+) &(-?\d+)(?: stripped)?\s*$", re.M)
REF_RE = re.compile(r"\{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}))?(?:, type: \d+)?\}")
GUID_RE = re.compile(r"^guid: ([0-9a-f]{32})\s*$", re.M)
NAME_RE = re.compile(r"^  m_Name: (.*)$", re.M)
CLASS_GAMEOBJECT = 1
CLASS_TRANSFORM = {4, 224}
BUILTIN_GUIDS = {
    "0000000000000000f000000000000000",
    "0000000000000000e000000000000000",
    "0000000000000000d000000000000000",
}

# Built-in Unity component class ids, so a tree reads without a script GUID.
BUILTIN_CLASSES = {
    1: "GameObject",
    4: "Transform",
    20: "Camera",
    21: "Material",
    23: "MeshRenderer",
    33: "MeshFilter",
    54: "Rigidbody",
    64: "MeshCollider",
    65: "BoxCollider",
    81: "AudioListener",
    82: "AudioSource",
    95: "Animator",
    96: "TrailRenderer",
    108: "Light",
    111: "Animation",
    114: "MonoBehaviour",
    120: "LineRenderer",
    135: "SphereCollider",
    136: "CapsuleCollider",
    137: "SkinnedMeshRenderer",
    143: "CharacterController",
    198: "ParticleSystem",
    199: "ParticleSystemRenderer",
    222: "CanvasRenderer",
    223: "Canvas",
    225: "CanvasGroup",
    1001: "PrefabInstance",
}


def find_project(start: str) -> Path:
    p = Path(start).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return candidate
    raise SystemExit(f"not a Unity project (no ProjectSettings/ProjectVersion.txt): {start}")


def iter_assets(root: Path):
    for base in ("Assets", "Packages"):
        d = root / base
        if not d.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [n for n in dirnames if n not in SKIP_DIRS]
            for name in filenames:
                yield Path(dirpath) / name


def read_text(path: Path, limit: int = 32 * 1024 * 1024) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text("utf-8", errors="replace")
    except OSError:
        return ""


def index_path(root: Path) -> Path:
    """Cache lives in the OS temp directory, never inside the project."""
    import hashlib
    import tempfile
    digest = hashlib.sha1(str(root).lower().encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "dsh-vrc-unity" / f"guid-index-{digest}.json"


def cmd_index(args) -> int:
    root = find_project(args.project)
    index: dict[str, str] = {}
    no_meta: list[str] = []
    for asset in iter_assets(root):
        if asset.suffix == ".meta":
            continue
        meta = asset.with_name(asset.name + ".meta")
        if not meta.is_file():
            no_meta.append(str(asset.relative_to(root)).replace("\\", "/"))
            continue
        m = GUID_RE.search(read_text(meta, 4096))
        if m:
            index[m.group(1)] = str(asset.relative_to(root)).replace("\\", "/")
    out_path = Path(args.out) if getattr(args, "out", None) else index_path(root)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"project": str(root), "index": index, "noMeta": no_meta},
                       indent=2, ensure_ascii=False),
            "utf-8",
        )
    except OSError as e:
        if args.json:
            print(json.dumps({"indexed": len(index), "noMeta": len(no_meta),
                              "path": None, "error": str(e)}))
        else:
            print(f"indexed {len(index)} assets (cache not written: {e})")
        return 0
    if args.json:
        print(json.dumps({"indexed": len(index), "noMeta": len(no_meta), "path": str(out_path)}))
    else:
        print(f"indexed {len(index)} assets -> {out_path}")
        if no_meta:
            print(f"WARNING: {len(no_meta)} assets have no .meta (Unity will assign new GUIDs)")
    return 0


def load_index(root: Path) -> dict[str, str]:
    path = index_path(root)
    if not path.is_file():
        cmd_index(argparse.Namespace(project=str(root), json=True, out=None))
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("index", {})


def script_docs(text: str):
    """Yield (classId, fileId, body) for every YAML document in a Unity asset."""
    matches = list(DOC_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield int(m.group(1)), int(m.group(2)), text[m.end():end]


def first_ref(body: str, key: str) -> tuple[int, str | None] | None:
    m = re.search(rf"^  {key}: \{{fileID: (-?\d+)(?:, guid: ([0-9a-f]{{32}}))?", body, re.M)
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def child_refs(body: str) -> list[int]:
    block = re.search(r"^  m_Children:\n((?:  - \{fileID: -?\d+\}\n)+)", body, re.M)
    if not block:
        return []
    return [int(x) for x in re.findall(r"fileID: (-?\d+)", block.group(1))]


def cmd_hierarchy(args) -> int:
    root = find_project(args.project)
    target = Path(args.asset)
    if not target.is_absolute():
        target = root / target
    text = read_text(target)
    if not text:
        raise SystemExit(f"cannot read {target}")

    index = load_index(root)
    docs = list(script_docs(text))

    def is_stub(body: str) -> bool:
        m = re.search(r"^  m_CorrespondingSourceObject: \{fileID: (-?\d+)", body, re.M)
        return bool(m and m.group(1) != "0")

    gameobjects = {fid: b for cid, fid, b in docs if cid == CLASS_GAMEOBJECT and not is_stub(b)}
    transforms = {fid: b for cid, fid, b in docs if cid in CLASS_TRANSFORM and not is_stub(b)}
    prefab_instances = {fid: b for cid, fid, b in docs if cid == 1001}

    # A stub transform is an attachment point owned by a prefab instance.
    stub_owner: dict[int, int] = {}
    for cid, fid, body in docs:
        if cid in CLASS_TRANSFORM and is_stub(body):
            owner = re.search(r"^  m_PrefabInstance: \{fileID: (-?\d+)", body, re.M)
            if owner and owner.group(1) != "0":
                stub_owner[fid] = int(owner.group(1))

    comps: dict[int, list[dict]] = {}
    for cid, fid, body in docs:
        if cid == CLASS_GAMEOBJECT or cid in CLASS_TRANSFORM or cid == 1001 or is_stub(body):
            continue
        owner = first_ref(body, "m_GameObject")
        if not owner or owner[0] == 0:
            continue
        script = first_ref(body, "m_Script")
        name = BUILTIN_CLASSES.get(cid, f"class{cid}")
        guid = None
        if script and script[1]:
            guid = script[1]
            path = index.get(guid)
            name = Path(path).stem if path else f"missing:{guid[:8]}"
        enabled = re.search(r"^  m_Enabled: (\d)", body, re.M)
        comps.setdefault(owner[0], []).append({
            "name": name,
            "classId": cid,
            "enabled": None if not enabled else enabled.group(1) == "1",
            "guid": guid,
        })

    nodes: dict[int, dict] = {}
    parent: dict[int, int] = {}

    for tid, body in transforms.items():
        go = first_ref(body, "m_GameObject")
        gob = gameobjects.get(go[0], "") if go else ""
        m = NAME_RE.search(gob)
        active = re.search(r"^  m_IsActive: (\d)", gob, re.M) if gob else None
        nodes[tid] = {
            "name": m.group(1) if m else f"<{tid}>",
            "kind": "gameobject",
            "active": None if not active else active.group(1) == "1",
            "components": comps.get(go[0], []) if go else [],
            "ref": tid,
        }
        father = first_ref(body, "m_Father")
        if father and father[0] != 0:
            parent[tid] = father[0]

    for pid, body in prefab_instances.items():
        m = re.search(r"propertyPath: m_Name\s*\n\s*value: (.*)", body)
        src = re.search(r"m_SourcePrefab: \{fileID: -?\d+, guid: ([0-9a-f]{32})", body)
        src_path = index.get(src.group(1)) if src else None
        label = (m.group(1).strip() if m else None) or (Path(src_path).stem if src_path else "prefab")
        active = re.search(r"propertyPath: m_IsActive\s*\n\s*value: (\d)", body)
        nodes[pid] = {
            "name": f"[prefab] {label}",
            "kind": "prefab-instance",
            "active": None if not active else active.group(1) == "1",
            "components": [],
            "source": src_path,
            "ref": pid,
        }
        tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)", body)
        if tp and tp.group(1) != "0":
            parent[pid] = int(tp.group(1))

    # Parents that point at a stub transform belong to the enclosing prefab instance.
    for nid, p in list(parent.items()):
        guard = 0
        while p in stub_owner and guard < 32:
            p = stub_owner[p]
            guard += 1
        if p == nid or p not in nodes:
            parent.pop(nid, None)
        else:
            parent[nid] = p

    children: dict[int, list[int]] = {}
    for nid, p in parent.items():
        children.setdefault(p, []).append(nid)

    rows: list[dict] = []

    def walk(nid: int, depth: int, path: str):
        node = nodes[nid]
        full = f"{path}/{node['name']}" if path else node["name"]
        rows.append({"depth": depth, "path": full, **node})
        for child in children.get(nid, []):
            walk(child, depth + 1, full)

    for nid in nodes:
        if nid not in parent:
            walk(nid, 0, "")

    if args.json:
        print(json.dumps({"asset": str(target), "nodes": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            indent = "  " * r["depth"]
            flag = "" if r["active"] in (True, None) else "  [inactive]"
            print(f"{indent}- {r['name']}{flag}")
            for c in r["components"]:
                off = "" if c["enabled"] in (True, None) else " (disabled)"
                print(f"{indent}    . {c['name']}{off}")
    return 0


def cmd_refs(args) -> int:
    root = find_project(args.project)
    index = load_index(root)
    guid = args.guid
    if args.path:
        target = Path(args.path)
        if not target.is_absolute():
            target = root / target
        meta = target.with_name(target.name + ".meta")
        m = GUID_RE.search(read_text(meta, 4096))
        if not m:
            raise SystemExit(f"no guid in {meta}")
        guid = m.group(1)
    if not guid:
        raise SystemExit("pass --guid or --path")
    hits = []
    for asset in iter_assets(root):
        if asset.suffix not in (".prefab", ".unity", ".asset", ".mat", ".controller", ".overrideController", ".anim"):
            continue
        text = read_text(asset)
        if not text:
            continue
        if f"guid: {guid}" in text:
            hits.append(str(asset.relative_to(root)).replace("\\", "/"))
    if args.json:
        print(json.dumps({"guid": guid, "target": index.get(guid), "referencedBy": hits}, ensure_ascii=False, indent=2))
    else:
        print(f"{guid} -> {index.get(guid, '<not in index>')}")
        if not hits:
            print("  (no references found)")
        for h in hits:
            print(f"  <- {h}")
    return 0


def cmd_report(args) -> int:
    root = find_project(args.project)
    version = read_text(root / "ProjectSettings" / "ProjectVersion.txt").strip().splitlines()
    manifest_path = root / "Packages" / "manifest.json"
    manifest = json.loads(read_text(manifest_path) or "{}")
    deps = manifest.get("dependencies", {})
    vpm = {k: v for k, v in deps.items() if not k.startswith("com.unity.")}
    lock_path = root / "Packages" / "vpm-lock.json"
    lock = {}
    if lock_path.is_file():
        lock = json.loads(read_text(lock_path) or "{}").get("locked", {}) or {}

    index = load_index(root)
    meta_missing = []
    script_guids: set[str] = set()
    avatars = []
    avatar_script_guids = {
        guid for guid, path in index.items() if path.endswith("VRC_AvatarDescriptor.cs")
    }

    for asset in iter_assets(root):
        if asset.suffix == ".meta":
            continue
        if not asset.with_name(asset.name + ".meta").is_file():
            rel = str(asset.relative_to(root)).replace("\\", "/")
            if rel.startswith("Assets/"):
                meta_missing.append(rel)
        if asset.suffix not in (".prefab", ".unity"):
            continue
        text = read_text(asset)
        if not text:
            continue
        guids = set(re.findall(r"m_Script: \{fileID: -?\d+, guid: ([0-9a-f]{32})", text))
        script_guids |= guids
        rel = str(asset.relative_to(root)).replace("\\", "/")
        if avatar_script_guids & guids:
            avatars.append(rel)

    missing_scripts = sorted(
        g for g in script_guids
        if g not in index and g not in BUILTIN_GUIDS
    )

    report = {
        "project": str(root),
        "unity": {"version": version[0].split(": ", 1)[-1] if version else None},
        "vpm": {
            "packages": vpm,
            "lock": {"present": lock_path.is_file(), "lockedPackages": len(lock)},
        },
        "avatars": sorted(avatars),
        "scripts": {
            "missing": [{"guid": g, "references": None} for g in missing_scripts],
            "missingCount": len(missing_scripts),
        },
        "meta": {"missing": meta_missing[:200], "missingCount": len(meta_missing)},
        "git": (root / ".git").exists(),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"project : {root}")
    print(f"unity   : {report['unity']['version']}")
    print(f"git     : {'yes' if report['git'] else 'NO (git init を提案してください)'}")
    print(f"vpm     : {len(vpm)} packages, lock {'present' if lock_path.is_file() else 'MISSING'}")
    for k, v in sorted(vpm.items()):
        print(f"          {k} {v}")
    print(f"avatars : {len(avatars)}")
    for a in avatars[:20]:
        print(f"          {a}")
    print(f"missing scripts : {len(missing_scripts)}")
    for g in missing_scripts[:10]:
        print(f"          {g}")
    print(f"missing .meta   : {len(meta_missing)}")
    for m in meta_missing[:10]:
        print(f"          {m}")
    if not vpm:
        print("\nWARNING: VPM パッケージが 1 つもありません（VRChat SDK 未導入の可能性）")
    return 0


def main(argv: list[str]) -> int:
    try:  # keep UTF-8 on Windows consoles and pipes
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Read a Unity project without opening Unity.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="project summary")
    p_report.add_argument("project")
    p_report.add_argument("--json", action="store_true")
    p_report.set_defaults(func=cmd_report)

    p_index = sub.add_parser("index", help="build the GUID index")
    p_index.add_argument("project")
    p_index.add_argument("--out", help="write the index here instead of the temp cache")
    p_index.add_argument("--json", action="store_true")
    p_index.set_defaults(func=cmd_index)

    p_hier = sub.add_parser("hierarchy", help="dump a prefab or scene tree")
    p_hier.add_argument("asset")
    p_hier.add_argument("--project", default=os.getcwd())
    p_hier.add_argument("--json", action="store_true")
    p_hier.set_defaults(func=cmd_hierarchy)

    p_refs = sub.add_parser("refs", help="find references to a GUID")
    p_refs.add_argument("--guid")
    p_refs.add_argument("--path")
    p_refs.add_argument("--project", default=os.getcwd())
    p_refs.add_argument("--json", action="store_true")
    p_refs.set_defaults(func=cmd_refs)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
