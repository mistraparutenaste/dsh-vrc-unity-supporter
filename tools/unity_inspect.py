#!/usr/bin/env python3
"""Read a Unity project without opening the editor.

Commands:
  report      project summary: SDK packages, avatars, missing scripts, missing .meta
  index       export a GUID -> asset path index (defaults to an OS temp file)
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
SCRIPT_GUID_RE = re.compile(r"m_Script: \{fileID: -?\d+, guid: ([0-9a-f]{32})")
PREFAB_GUID_RE = re.compile(r"m_SourcePrefab: \{fileID: -?\d+, guid: ([0-9a-f]{32})")
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


DEFAULT_MAX_NODES = 300
# Agents read stdout as context. Rows carry full paths, so deep trees grow faster than the node count;
# capped output also stops at this many UTF-8 bytes. --max-nodes 0 prints everything.
OUTPUT_BUDGET_BYTES = 48 * 1024
MAX_REFERENCES = 200
MAX_MISSING_SCRIPTS = 50
MAX_AVATARS = 200


def compact_json(value) -> str:
    """Agents read stdout as context, so JSON output carries no indentation."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def find_project(start: str, search_children: bool = False) -> Path:
    p = Path(start).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return candidate
    if search_children and p.is_dir():
        candidates = sorted(child for child in p.iterdir()
                            if (child / "ProjectSettings" / "ProjectVersion.txt").is_file())
        if len(candidates) == 1:
            return candidates[0].resolve()
        if candidates:
            raise SystemExit("Multiple Unity projects found:\n" + "\n".join(str(path) for path in candidates))
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
    """Read at most `limit` characters. Huge .meta files (FBX imports) are common."""
    try:
        if path.stat().st_size == 0:
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def index_path(root: Path) -> Path:
    """Cache lives in the OS temp directory, never inside the project."""
    import hashlib
    import tempfile
    digest = hashlib.sha1(str(root).lower().encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "dsh-vrc-unity" / f"guid-index-{digest}.json"


def build_index(root: Path, assets) -> tuple[dict[str, str], list[str]]:
    index: dict[str, str] = {}
    no_meta: list[str] = []
    for asset in assets:
        if asset.suffix == ".meta":
            continue
        meta = asset.with_name(asset.name + ".meta")
        if not meta.is_file():
            rel = str(asset.relative_to(root)).replace("\\", "/")
            if rel.startswith("Assets/"):   # embedded packages legitimately ship without .meta
                no_meta.append(rel)
            continue
        m = GUID_RE.search(read_text(meta, 4096))
        if m:
            index[m.group(1)] = str(asset.relative_to(root)).replace("\\", "/")
    return index, no_meta


def cmd_index(args) -> int:
    root = find_project(args.project)
    index, no_meta = build_index(root, iter_assets(root))
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
        return 1
    if args.json:
        print(json.dumps({"indexed": len(index), "noMeta": len(no_meta), "path": str(out_path)}))
    else:
        print(f"indexed {len(index)} assets -> {out_path}")
        if no_meta:
            print(f"WARNING: {len(no_meta)} assets have no .meta (Unity will assign new GUIDs)")
    return 0


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


def build_tree(text: str, index: dict[str, str]) -> tuple[dict[int, dict], dict[int, int]]:
    """Parse one asset's YAML into nodes keyed by file id, plus their parent edges."""
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

    return nodes, parent


def _children_of(parent: dict[int, int]) -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for nid, pid in parent.items():
        children.setdefault(pid, []).append(nid)
    return children


def cmd_hierarchy(args) -> int:
    root = find_project(args.project)
    target = Path(args.asset)
    if not target.is_absolute():
        target = root / target
    text = read_text(target)
    if not text:
        raise SystemExit(f"cannot read {target}")

    index, _ = build_index(root, iter_assets(root))
    nodes, parent = build_tree(text, index)
    children = _children_of(parent)

    depth_limit = max(0, int(getattr(args, "depth", 2)))
    rows: list[dict] = []
    ancestors = {target.resolve()}

    def emit(local_nodes, local_children, nid, depth, path, depth_left):
        node = local_nodes[nid]
        full = f"{path}/{node['name']}" if path else node["name"]
        rows.append({"depth": depth, "path": full, **node})
        for child in local_children.get(nid, []):
            emit(local_nodes, local_children, child, depth + 1, full, depth_left)

        source = node.get("source")
        if node.get("kind") == "prefab-instance" and source and depth_left > 0:
            source_path = (root / source).resolve()
            # Only YAML assets can be expanded; an FBX model has no readable hierarchy here.
            if source_path.suffix.lower() not in (".prefab", ".unity"):
                return
            if source_path in ancestors:
                return
            sub_text = read_text(source_path)
            if not sub_text:
                return
            sub_nodes, sub_parent = build_tree(sub_text, index)
            sub_children = _children_of(sub_parent)
            ancestors.add(source_path)
            try:
                for sub_root in sub_nodes:
                    if sub_root not in sub_parent:
                        emit(sub_nodes, sub_children, sub_root, depth + 1, full, depth_left - 1)
            finally:
                ancestors.remove(source_path)

    for nid in nodes:
        if nid not in parent:
            emit(nodes, children, nid, 0, "", depth_limit)

    # Collect everything first, then narrow and cap only what is printed.
    max_tree_depth = getattr(args, "max_depth", None)
    if max_tree_depth is not None and max_tree_depth >= 0:
        rows = [r for r in rows if r["depth"] <= max_tree_depth]
    needle = (getattr(args, "filter", None) or "").casefold()
    if needle:
        rows = [r for r in rows if needle in r["path"].casefold()]
    total = len(rows)
    max_nodes = max(0, int(getattr(args, "max_nodes", DEFAULT_MAX_NODES)))
    if max_nodes:
        rows = rows[:max_nodes]

    def text_lines(r):
        indent = "  " * r["depth"]
        flag = "" if r["active"] in (True, None) else "  [inactive]"
        yield f"{indent}- {r['name']}{flag}"
        for c in r["components"]:
            off = "" if c["enabled"] in (True, None) else " (disabled)"
            yield f"{indent}    . {c['name']}{off}"

    if max_nodes:
        # Keep the leading rows that fit the byte budget (always at least one).
        size = lambda r: len((compact_json(r) if args.json else "\n".join(text_lines(r))).encode("utf-8")) + 1
        kept, used = [], 0
        for r in rows:
            used += size(r)
            if kept and used > OUTPUT_BUDGET_BYTES:
                break
            kept.append(r)
        rows = kept
    truncated = len(rows) < total

    if args.json:
        print(compact_json({"asset": str(target), "nodes": rows, "nodeCount": total, "truncated": truncated}))
    else:
        for r in rows:
            for line in text_lines(r):
                print(line)
        if truncated:
            print(f"(showing {len(rows)} of {total} nodes; narrow with --filter or --max-depth, "
                  "or print all with --max-nodes 0)")
    return 0


def cmd_refs(args) -> int:
    root = find_project(args.project)
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
    assets = list(iter_assets(root))
    index, _ = build_index(root, assets)
    hits = []
    for asset in assets:
        if asset.suffix not in (".prefab", ".unity", ".asset", ".mat", ".controller", ".overrideController", ".anim"):
            continue
        text = read_text(asset)
        if not text:
            continue
        if f"guid: {guid}" in text:
            hits.append(str(asset.relative_to(root)).replace("\\", "/"))
    limit = max(0, int(getattr(args, "max_refs", MAX_REFERENCES)))
    shown = hits[:limit] if limit else hits
    if args.json:
        print(compact_json({"guid": guid, "target": index.get(guid), "referencedBy": shown,
                            "referencedByCount": len(hits), "truncated": len(shown) < len(hits)}))
    else:
        print(f"{guid} -> {index.get(guid, '<not in index>')}")
        if not hits:
            print("  (no references found)")
        for h in shown:
            print(f"  <- {h}")
        if len(shown) < len(hits):
            print(f"  (showing {len(shown)} of {len(hits)} references; list all with --max-refs 0)")
    return 0


def vpm_inventory(root: Path) -> tuple[dict[str, str], list[str], str | None]:
    """Collect VPM packages from every layout a VPM client may leave behind.

    - VCC / ALCOM 2.x: Packages/manifest.json dependencies
    - legacy vrc-get: Packages/vpm-manifest.json dependencies
    - either client: packages embedded in Packages/<id>/package.json
    Returns (packages, sources, lockfile name).
    """
    pkg_dir = root / "Packages"
    packages: dict[str, str] = {}
    sources: list[str] = []
    for file_name in ("manifest.json", "vpm-manifest.json"):
        path = pkg_dir / file_name
        if not path.is_file():
            continue
        try:
            data = json.loads(read_text(path) or "{}")
        except ValueError:
            continue
        found = False
        for key, value in (data.get("dependencies", {}) or {}).items():
            if key.startswith("com.unity."):
                continue
            if isinstance(value, str):
                version = value
            elif isinstance(value, dict):
                version = str(value.get("version", ""))
            else:
                version = ""
            packages[key] = version
            found = True
        if found:
            sources.append(file_name)

    embedded = 0
    if pkg_dir.is_dir():
        for child in pkg_dir.iterdir():
            manifest = child / "package.json"
            if not child.is_dir() or not manifest.is_file():
                continue
            try:
                meta = json.loads(read_text(manifest) or "{}")
            except ValueError:
                continue
            name = meta.get("name")
            if not name or name.startswith("com.unity."):
                continue
            embedded += 1
            packages.setdefault(name, str(meta.get("version", "")))
    if embedded:
        sources.append(f"embedded({embedded})")

    lock = None
    for candidate in ("vpm-lock.json", "vpm-manifest.json"):
        if (pkg_dir / candidate).is_file():
            lock = candidate
            break
    return packages, sources, lock


def cmd_report(args) -> int:
    root = find_project(args.project, search_children=True)
    version = read_text(root / "ProjectSettings" / "ProjectVersion.txt").strip().splitlines()
    vpm, vpm_sources, lock_name = vpm_inventory(root)
    lock = {}
    if lock_name:
        try:
            data = json.loads(read_text(root / "Packages" / lock_name) or "{}")
            lock = data.get("locked", {}) or {}
        except ValueError:
            lock = {}

    assets = list(iter_assets(root))
    index, meta_missing = build_index(root, assets)
    script_guids: set[str] = set()
    candidates = set()
    referenced_by: dict[str, set[str]] = {}
    avatar_script_guids = {
        guid for guid, path in index.items() if path.endswith("VRC_AvatarDescriptor.cs")
    }
    # SDK 3.x keeps the descriptor inside VRCSDK3A.dll, so the .cs name is not in the index.
    # A prefab that uses any component from that assembly is an avatar for our purposes.
    avatar_assembly_guids = {
        guid for guid, path in index.items() if path.endswith("VRCSDK3A.dll")
    }
    avatar_markers = avatar_script_guids | avatar_assembly_guids

    for asset in assets:
        if asset.suffix not in (".prefab", ".unity"):
            continue
        text = read_text(asset)
        if not text:
            continue
        guids = set(SCRIPT_GUID_RE.findall(text))
        script_guids |= guids
        rel = str(asset.relative_to(root)).replace("\\", "/")
        if avatar_markers & guids:
            candidates.add(rel)
        for guid in PREFAB_GUID_RE.findall(text):
            source = index.get(guid)
            if source:
                referenced_by.setdefault(source, set()).add(rel)

    # An instance or variant can inherit its descriptor without an m_Script of its own.
    pending = list(candidates)
    while pending:
        for parent in referenced_by.get(pending.pop(), ()):
            if parent not in candidates:
                candidates.add(parent)
                pending.append(parent)
    avatars = sorted(path for path in candidates if path.startswith("Assets/"))

    missing_scripts = sorted(
        g for g in script_guids
        if g not in index and g not in BUILTIN_GUIDS
    )

    report = {
        "project": str(root),
        "unity": {"version": version[0].split(": ", 1)[-1] if version else None},
        "vpm": {
            "packages": vpm,
            "sources": vpm_sources,
            "lock": {"file": lock_name, "lockedPackages": len(lock)},
        },
        "avatars": avatars[:MAX_AVATARS],
        "avatarCount": len(avatars),
        "avatarsTruncated": len(avatars) > MAX_AVATARS,
        "scripts": {
            "missing": [{"guid": g, "references": None} for g in missing_scripts[:MAX_MISSING_SCRIPTS]],
            "missingCount": len(missing_scripts),
        },
        "meta": {"missing": meta_missing[:200], "missingCount": len(meta_missing)},
        "git": (root / ".git").exists(),
    }

    if args.json:
        print(compact_json(report))
        return 0

    print(f"project : {root}")
    print(f"unity   : {report['unity']['version']}")
    print(f"git     : {'yes' if report['git'] else 'NO (git init を提案してください)'}")
    print(f"vpm     : {len(vpm)} packages, lock {lock_name or 'MISSING'}")
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


LIMITS = Path(__file__).resolve().parent.parent / "skills" / "vrc-perf-budget" / "assets" / "limits.json"
RANKS = ("excellent", "good", "medium", "poor")
# DshInspect.Perf names that differ from limits.json
COUNT_ALIASES = {"constraints": "constraintCount"}


def rank_counts(counts: dict, limits: dict) -> dict:
    """Rank each measured statistic for PC and Mobile; the avatar's rank is its worst statistic."""
    measured = {COUNT_ALIASES.get(k, k): v for k, v in counts.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)}
    platforms = {}
    for platform in ("pc", "mobile"):
        table = limits[platform]
        items = {}
        for stat, value in measured.items():
            if stat not in table["poor"]:
                continue
            rank = next((r for r in RANKS if stat in table[r] and value <= table[r][stat]), "veryPoor")
            items[stat] = {"value": value, "rank": rank}
        order = RANKS + ("veryPoor",)
        worst = max((item["rank"] for item in items.values()), key=order.index, default=None)
        platforms[platform] = {
            "rank": worst,
            "limitedBy": sorted(stat for stat, item in items.items() if item["rank"] == worst) if worst else [],
            "items": items,
            "notMeasured": sorted(stat for stat in table["poor"] if stat not in items),
        }
        if worst and worst != "excellent":
            better = order[order.index(worst) - 1]
            platforms[platform]["toReach"] = {
                "rank": better,
                "reduce": {stat: {"value": items[stat]["value"], "max": table[better][stat]}
                           for stat in platforms[platform]["limitedBy"] if stat in table[better]}}
    return platforms


def cmd_rank(args) -> int:
    limits = json.loads(LIMITS.read_text(encoding="utf-8"))
    data = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and isinstance(data.get("avatars"), list):  # a DshInspect.Perf result.json
        targets = [(a.get("prefab"), a.get("counts") or {}) for a in data["avatars"] if isinstance(a, dict)]
        stage = data.get("measurementStage")
    elif isinstance(data, dict):
        targets, stage = [(None, data.get("counts", data))], None
    else:
        raise SystemExit("Pass a DshInspect.Perf result.json or a JSON object of counts.")
    output = {
        "ok": True, "source": limits.get("source"), "measurementStage": stage,
        "avatars": [dict({"prefab": prefab} if prefab else {}, **rank_counts(counts, limits))
                    for prefab, counts in targets[:20]],
        "note": ("Ranks follow limits.json; textureMemoryMB from Perf is an uncompressed estimate and runs high. "
                 "notMeasured items are not counted here. Counts taken before the build (source prefab) do not "
                 "include Modular Avatar, VRCFury or Avatar Optimizer changes; the SDK build panel has the final rank."),
    }
    print(compact_json(output) if args.json else json.dumps(output, ensure_ascii=False, indent=2))
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
    p_report.add_argument("project", nargs="?", default=os.getcwd())
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
    p_hier.add_argument("--depth", type=int, default=2,
                        help="how many prefab-instance levels to resolve (default 2, 0 = none)")
    p_hier.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES,
                        help=f"print at most this many nodes (default {DEFAULT_MAX_NODES}, 0 = all)")
    p_hier.add_argument("--filter", help="only nodes whose full path contains this text (case-insensitive)")
    p_hier.add_argument("--max-depth", type=int,
                        help="only nodes at this tree depth or shallower (0 = roots)")
    p_hier.add_argument("--json", action="store_true")
    p_hier.set_defaults(func=cmd_hierarchy)

    p_rank = sub.add_parser("rank", help="performance rank from DshInspect.Perf counts (limits.json)")
    p_rank.add_argument("file", help="a DshInspect.Perf result.json, or a JSON object of counts")
    p_rank.add_argument("--json", action="store_true")
    p_rank.set_defaults(func=cmd_rank)

    p_refs = sub.add_parser("refs", help="find references to a GUID")
    p_refs.add_argument("--guid")
    p_refs.add_argument("--path")
    p_refs.add_argument("--project", default=os.getcwd())
    p_refs.add_argument("--json", action="store_true")
    p_refs.add_argument("--max-refs", type=int, default=MAX_REFERENCES,
                        help=f"list at most this many referencing assets (default {MAX_REFERENCES}, 0 = all)")
    p_refs.set_defaults(func=cmd_refs)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
