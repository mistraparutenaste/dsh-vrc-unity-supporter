"""DSH tasks that run inside Blender in background mode.

    blender -b --factory-startup --python dsh_blender.py -- <inspect|make|fit> <request.json> <result.json>

The request and result are JSON files. Source files are only read; outputs go to the paths in the request.
Directions in requests use the avatar's axes as Unity shows them: x right, y up, z forward (metres, degrees).
"""

import json
import math
import re
import sys
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


MAX_LISTED = 80


# --- shared -----------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model(path):
    """Import an FBX (or open a .blend) and return the new objects."""
    before = set(bpy.data.objects)
    if path.lower().endswith(".blend"):
        with bpy.data.libraries.load(path, link=False) as (source, target):
            target.objects = list(source.objects)
        for obj in target.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
    else:
        bpy.ops.import_scene.fbx(filepath=path, use_anim=False, ignore_leaf_bones=True,
                                 automatic_bone_orientation=False)
    return [obj for obj in bpy.data.objects if obj not in before]


def triangles(mesh):
    return sum(len(poly.vertices) - 2 for poly in mesh.polygons)


def world_bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    if not points:
        return None
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return low, high


def unity_vector(value):
    """The avatar's axes in Unity (x right, y up, z forward) to Blender, where a model faces -Y and its right
    side is -X. FBX export with -Z forward and Y up turns these back into the Unity axes."""
    x, y, z = (list(value) + [0, 0, 0])[:3]
    return Vector((-x, -z, y))


def unity_rotation(degrees):
    """Unity Euler angles (applied z, x, y about the avatar's axes) as a Blender rotation matrix.

    The axis mapping flips handedness, so each turn keeps its mapped axis and changes the sign of its angle.
    """
    rx, ry, rz = [math.radians(v) for v in degrees]
    axis_x, axis_y, axis_z = unity_vector((1, 0, 0)), unity_vector((0, 1, 0)), unity_vector((0, 0, 1))
    turn = lambda axis, angle: Matrix.Rotation(-angle, 3, axis)
    return turn(axis_y, ry) @ turn(axis_x, rx) @ turn(axis_z, rz)


def describe(objects):
    meshes, armatures = [], []
    for obj in objects:
        if obj.type == "MESH":
            entry = {"name": obj.name, "vertices": len(obj.data.vertices), "triangles": triangles(obj.data),
                     "materials": [slot.material.name for slot in obj.material_slots if slot.material][:16]}
            keys = obj.data.shape_keys
            if keys:
                entry["shapeKeys"] = len(keys.key_blocks) - 1
            armature = next((m.object for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
            if armature:
                entry["armature"] = armature.name
                entry["vertexGroups"] = len(obj.vertex_groups)
            meshes.append(entry)
        elif obj.type == "ARMATURE":
            bones = obj.data.bones
            mapped = humanoid_map(obj)
            armatures.append({"name": obj.name, "bones": len(bones),
                              "humanoid": sorted(mapped)[:MAX_LISTED],
                              "roots": [b.name for b in bones if b.parent is None][:10]})
    bounds = world_bounds(objects)
    size = None
    if bounds:
        low, high = bounds
        size = [round(high.x - low.x, 4), round(high.z - low.z, 4), round(high.y - low.y, 4)]
    return {"meshes": meshes[:MAX_LISTED], "meshCount": len(meshes), "armatures": armatures,
            "sizeUnity": size}


# --- humanoid bone names ----------------------------------------------------------

# Core humanoid names and the spellings rigs use for them (compared after removing case, digits and separators).
SYNONYMS = {
    "hips": ("hips", "hip", "pelvis"),
    "spine": ("spine",),
    "chest": ("chest", "spine1"),
    "upperchest": ("upperchest", "spine2"),
    "neck": ("neck",),
    "head": ("head",),
    "shoulder": ("shoulder", "clavicle"),
    "upperarm": ("upperarm", "arm"),
    "lowerarm": ("lowerarm", "forearm", "elbow"),
    "hand": ("hand", "wrist"),
    "upperleg": ("upperleg", "thigh", "upleg"),
    "lowerleg": ("lowerleg", "calf", "knee", "shin", "leg"),
    "foot": ("foot", "ankle"),
    "toes": ("toes", "toe", "toebase"),
}
SIDED = {"shoulder", "upperarm", "lowerarm", "hand", "upperleg", "lowerleg", "foot", "toes"}
LOOKUP = {spelling: core for core, spellings in SYNONYMS.items() for spelling in spellings}
PREFIX = re.compile(r"^(mixamorig|j_bip_[clr]_|bip0?1_?|def[-_]|armature[._:])", re.IGNORECASE)


def humanoid_key(name):
    """'Left_UpperArm', 'UpperArm.L', 'mixamorig:LeftArm' -> 'left upperarm'; None if not a main humanoid bone."""
    raw = PREFIX.sub("", name.split(":")[-1])
    side = ""
    match = re.search(r"(^|[._\s-])(l|r|left|right)$", raw, re.IGNORECASE)
    if match:
        side = "left" if match.group(2).lower().startswith("l") else "right"
        raw = raw[:match.start()]
    else:
        match = re.match(r"^(left|right|l|r)(?=[._\s-]|[A-Z])", raw, re.IGNORECASE)
        if match:
            side = "left" if match.group(1).lower().startswith("l") else "right"
            raw = raw[match.end():]
    core = LOOKUP.get(re.sub(r"[^a-z]", "", raw.lower()))
    if core is None:
        return None
    if core in SIDED:
        return f"{side} {core}" if side else None
    return None if side else core


def humanoid_map(armature):
    found = {}
    for bone in armature.data.bones:
        key = humanoid_key(bone.name)
        if key and key not in found:
            found[key] = bone.name
    return found


# --- inspect ----------------------------------------------------------------------

def inspect(request):
    reset_scene()
    objects = import_model(request["file"])
    result = dict(describe(objects), ok=True, file=request["file"])
    wanted = request.get("shapes")
    if wanted:
        mesh = next((o for o in objects if o.type == "MESH" and o.name == wanted), None)
        if mesh is None:
            raise ValueError(f"No mesh named {wanted!r} in the file.")
        keys = mesh.data.shape_keys
        text = (request.get("filter") or "").lower()
        names = [k.name for k in keys.key_blocks[1:]] if keys else []
        names = [n for n in names if text in n.lower()]
        result["shapeKeyNames"] = {"mesh": wanted, "count": len(names), "names": names[:300]}
    return result


# --- make: shapes for accessories ----------------------------------------------------
#
# A part is a primitive (cube, sphere, cylinder, cone, torus), a tube swept along points (ribbon tails, strings,
# horns, headbands, chokers), a lathe (a profile turned about the up axis: buttons, beads, bells, cups) or an
# extruded outline (stars, hearts, badges). Parts can be mirrored to the avatar's other side, subdivided, placed
# against the avatar's surface (with an avatar), and given a chain of bones to sway with a PhysBone.

SMOOTH_ANGLE = 40       # degrees: edges sharper than this stay crisp when a part is smooth-shaded
MANY_TRIANGLES = 10000  # an accessory with more is worth a look in the performance budget


def material(color):
    """One material per colour, named after it (Unity imports each as a material of that name)."""
    name = "DSH_" + color.lstrip("#").lower()
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    value = color.lstrip("#")
    rgb = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*linear, 1)
    mat.diffuse_color = (*linear, 1)
    return mat


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def link_mesh(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def part_matrix(part):
    return Matrix.Translation(unity_vector(part.get("position", [0, 0, 0]))) @ unity_rotation(
        part.get("rotation", [0, 0, 0])).to_4x4()


def primitive(part, name):
    shape, segments = part["shape"], part.get("segments", 32)
    size = Vector(part.get("size", [0.1, 0.1, 0.1]))
    if shape == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1)
    elif shape == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=max(4, segments // 2), radius=0.5)
    elif shape == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=0.5, depth=1)
    elif shape == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=segments, radius1=0.5, radius2=part.get("topRatio", 0) * 0.5, depth=1)
    elif shape == "torus":
        # A flat ring (in the avatar's x-z plane) whose tube is "thickness" of its outer width.
        tube = part.get("thickness", 0.2) / 2
        bpy.ops.mesh.primitive_torus_add(major_segments=segments, minor_segments=max(6, segments // 3),
                                         major_radius=0.5 - tube, minor_radius=tube)
    else:
        raise ValueError(f"Unknown shape {shape}")
    obj = bpy.context.active_object
    obj.name = name
    # Every primitive starts in a 1 m box; size is its box in Unity axes (width x, height y, depth z).
    height = part.get("thickness", 0.2) if shape == "torus" else 1
    obj.scale = (size.x, size.z, size.y / height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if part.get("bevel", 0) > 0 and shape in ("cube", "cylinder"):
        modifier = obj.modifiers.new("Bevel", "BEVEL")
        modifier.width = part["bevel"]
        modifier.segments = 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.matrix_world = part_matrix(part)
    return obj


def lathe(part, name):
    """The profile [[radius, height], ...] (bottom to top, metres) turned about the up axis."""
    segments = part.get("segments", 32)
    bm = bmesh.new()
    rings = []
    for radius, height in part["profile"]:
        if radius < 1e-5:
            rings.append([bm.verts.new((0, 0, height))])
        else:
            rings.append([bm.verts.new((radius * math.cos(2 * math.pi * k / segments),
                                        radius * math.sin(2 * math.pi * k / segments), height))
                          for k in range(segments)])
    for low, high in zip(rings, rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            if len(low) == 1 and len(high) == 1:
                break
            if len(low) == 1:
                bm.faces.new((low[0], high[j], high[k]))
            elif len(high) == 1:
                bm.faces.new((low[k], low[j], high[0]))
            else:
                bm.faces.new((low[k], low[j], high[j], high[k]))
    if part.get("caps", True):
        for ring in (rings[0], rings[-1]):
            if len(ring) > 2:
                bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    obj = link_mesh(name, bm)
    obj.matrix_world = part_matrix(part)
    return obj


def outline_points(part):
    """The 2D outline of an extruded part (Unity x right, y up, metres): a list, or a named shape in size x, y."""
    outline = part["outline"]
    if isinstance(outline, list):
        return [tuple(p) for p in outline]
    width, height = part.get("size", [0.1, 0.1, 0.1])[:2]
    if outline == "star":
        corners, inner = part.get("corners", 5), part.get("inner", 0.45)
        points = [((1 if k % 2 == 0 else inner) * math.cos(math.pi / 2 + k * math.pi / corners),
                   (1 if k % 2 == 0 else inner) * math.sin(math.pi / 2 + k * math.pi / corners))
                  for k in range(corners * 2)]
    elif outline == "heart":
        points = []
        for k in range(64):
            t = 2 * math.pi * k / 64
            points.append((16 * math.sin(t) ** 3,
                           13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
    elif outline == "circle":
        points = [(math.cos(2 * math.pi * k / 48), math.sin(2 * math.pi * k / 48)) for k in range(48)]
    elif outline == "diamond":
        points = [(0, 1), (-1, 0), (0, -1), (1, 0)]
    else:
        raise ValueError(f"Unknown outline {outline}")
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    sx, sy = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    return [((x - cx) / sx * width, (y - cy) / sy * height) for x, y in points]


def extrude(part, name):
    """An outline in the avatar's front plane, extruded depth metres front to back (centred)."""
    depth = part.get("depth", 0.005)
    points = outline_points(part)
    bm = bmesh.new()
    front = [bm.verts.new(unity_vector((x, y, depth / 2))) for x, y in points]
    back = [bm.verts.new(unity_vector((x, y, -depth / 2))) for x, y in points]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    count = len(points)
    for k in range(count):
        j = (k + 1) % count
        bm.faces.new((front[k], back[k], back[j], front[j]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    obj = link_mesh(name, bm)
    if part.get("bevel", 0) > 0:
        select_only(obj)
        modifier = obj.modifiers.new("Bevel", "BEVEL")
        modifier.width = min(part["bevel"], depth * 0.45)
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.matrix_world = part_matrix(part)
    return obj


# --- tubes ------------------------------------------------------------------------------

def catmull_rom(points, closed, steps):
    """A smooth path through the points (centripetal Catmull-Rom), steps samples per span."""
    count = len(points)
    if count == 2 and not closed:
        return [points[0].lerp(points[1], i / steps) for i in range(steps + 1)]
    get = (lambda i: points[i % count]) if closed else (lambda i: points[max(0, min(count - 1, i))])
    spans = count if closed else count - 1
    samples = []
    for span in range(spans):
        p0, p1, p2, p3 = get(span - 1), get(span), get(span + 1), get(span + 2)
        if not closed and span == 0:
            p0 = p1 + (p1 - p2)
        if not closed and span == spans - 1:
            p3 = p2 + (p2 - p1)
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length, 1e-6) ** 0.5
        t2 = t1 + max((p2 - p1).length, 1e-6) ** 0.5
        t3 = t2 + max((p3 - p2).length, 1e-6) ** 0.5
        for i in range(steps):
            t = t1 + (t2 - t1) * i / steps
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            samples.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    if not closed:
        samples.append(points[-1].copy())
    return samples


def perpendicular(vector, axis):
    flat = vector - axis * vector.dot(axis)
    if flat.length < 1e-6:
        flat = axis.orthogonal()
    return flat.normalized()


def tube_profile(part):
    """Cross-section points (across, out) before taper: a circle, or a soft-cornered flat band."""
    segments = part.get("segments", 32)
    if part.get("section", "round") == "flat":
        half_w, half_d = part.get("width", 0.02) / 2, part.get("depth", 0.002) / 2
        points = []
        for k in range(12):
            a = 2 * math.pi * k / 12
            c, s = math.cos(a), math.sin(a)
            points.append((half_w * math.copysign(abs(c) ** 0.5, c), half_d * math.copysign(abs(s) ** 0.5, s)))
        return points, half_d
    radius = part.get("radius", 0.005)
    count = max(6, segments // 3)
    return [(radius * math.cos(2 * math.pi * k / count), radius * math.sin(2 * math.pi * k / count))
            for k in range(count)], radius


def tube(part, name, context=None, gap=0.0):
    """A profile swept along a smooth path through the points. The band's flat side faces `face` (Unity axes,
    default forward), or the avatar's surface when the part conforms to it. Returns the object and the sweep
    (sample positions and the distance along the path of each vertex), for sway bones."""
    matrix = part_matrix(part)
    points = [matrix @ unity_vector(p) for p in part["points"]]
    closed = part.get("closed", False)
    profile, thickness = tube_profile(part)
    taper = part.get("taper", 1.0)
    steps = max(2, min(16, part.get("segments", 32) // 5))
    samples = catmull_rom(points, closed, steps)
    count = len(samples)
    lengths = [0.0]
    for a, b in zip(samples, samples[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1] + ((samples[0] - samples[-1]).length if closed else 0)
    factors = [1 + (taper - 1) * (s / total if total > 0 else 0) for s in lengths]
    normals = None
    if context is not None:
        # Rest the path on the avatar: each sample goes onto the outermost surface on its line toward the
        # avatar (so hair layers and ears are not passed through), then out by its half thickness and the gap,
        # and the band's flat side lies against the surface.
        hits = [rest_on(context["tree"], point, toward(context, part, point)) for point in samples]
        found = [i for i, hit in enumerate(hits) if hit[0] is not None]
        normals = [None] * count
        for i in found:
            # Hair is uneven: average each normal with its neighbours so the band does not wobble.
            near = [hits[j][1] for j in (i - 1, i, i + 1) if 0 <= j < count and hits[j][1] is not None]
            normals[i] = (sum(near, Vector()) / len(near)).normalized()
        for i in found:
            samples[i] = hits[i][0] + normals[i] * (thickness * factors[i] + gap)
        lengths = [0.0]
        for a, b in zip(samples, samples[1:]):
            lengths.append(lengths[-1] + (b - a).length)
    tangents = []
    for i in range(count):
        if closed:
            forward = samples[(i + 1) % count] - samples[i - 1]
        else:
            forward = samples[min(count - 1, i + 1)] - samples[max(0, i - 1)]
        tangents.append(forward.normalized() if forward.length > 1e-9 else Vector((0, 0, 1)))
    hint = unity_vector(part.get("face", [0, 0, 1]))
    if hint.length < 1e-6:
        hint = unity_vector((0, 0, 1))
    hint.normalize()
    frames, out = [], perpendicular(hint, tangents[0])
    for i, tangent in enumerate(tangents):
        if normals is not None and normals[i] is not None:
            out = perpendicular(normals[i], tangent)
        elif i > 0:
            # Parallel transport: turn the previous frame by the turn of the path, so the band does not twist.
            out = perpendicular(tangents[i - 1].rotation_difference(tangent) @ out, tangent)
        tilt = Matrix.Rotation(math.radians(part.get("tilt", 0)), 3, tangent)
        out_tilted = tilt @ out
        frames.append((tangent.cross(out_tilted).normalized(), out_tilted))
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rings = []
    for i, (across, outward) in enumerate(frames):
        f = max(factors[i], 0.0)
        rings.append([bm.verts.new(samples[i] + across * (x * f) + outward * (y * f)) for x, y in profile])
    width = len(profile)
    length = max(lengths[-1], 1e-6)
    spans = count if closed else count - 1
    for i in range(spans):
        a, b = rings[i], rings[(i + 1) % count]
        va, vb = lengths[i] / length, (lengths[i + 1] / length if i + 1 < count else 1.0)
        for k in range(width):
            j = (k + 1) % width
            face = bm.faces.new((a[k], a[j], b[j], b[k]))
            for loop, (u, v) in zip(face.loops, ((k / width, va), ((k + 1) / width, va),
                                                 ((k + 1) / width, vb), (k / width, vb))):
                loop[uv].uv = (u, v)
    if not closed:
        for ring in (rings[0], rings[-1]):
            if max((v.co - ring[0].co).length for v in ring) > 1e-6:
                face = bm.faces.new(ring)
                for loop in face.loops:
                    loop[uv].uv = (0.5, 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    along = [lengths[i] for i in range(count) for _ in profile]
    obj = link_mesh(name, bm)
    return obj, {"samples": samples, "lengths": lengths, "along": along, "closed": closed}


# --- placing parts against the avatar ------------------------------------------------

def avatar_context(request):
    """Import the avatar with the attach bone at the origin (the made model's origin, as vrc-accessory places it
    with origin "bone"), set its body shapes, and build one surface from the chosen meshes."""
    objects = import_named(request["avatar"], "DSH_avatar_")
    armature = armature_of(objects, "avatar")
    key = humanoid_key(request.get("bone") or "Head")
    bone_name = humanoid_map(armature).get(key or "")
    if not bone_name:
        raise ValueError(f"The avatar has no {request.get('bone')} bone that DSH can read. "
                         f"Humanoid bones found: {', '.join(sorted(humanoid_map(armature))[:30])}")
    origin = armature.matrix_world @ armature.data.bones[bone_name].head_local
    for obj in objects:
        if obj.parent is None:
            obj.matrix_world = Matrix.Translation(-origin) @ obj.matrix_world
    meshes = [obj for obj in objects if obj.type == "MESH"]
    region = {bone_name} | {b.name for b in armature.data.bones[bone_name].children_recursive}
    wanted = request.get("surfaces") or []
    if wanted:
        missing = [name for name in wanted if not any(source_name(o) == name for o in meshes)]
        if missing:
            raise ValueError(f"The avatar has no mesh {', '.join(missing[:5])}. "
                             f"Meshes: {', '.join(source_name(o) for o in meshes[:30])}")
        surfaces = [o for o in meshes if source_name(o) in wanted]
    else:
        # The skin, hair and ears around the bone; the avatar's own clothes (often hidden or swapped) are left out.
        skin = [o for o in meshes if not CLOTHES.search(source_name(o))]
        surfaces = [o for o in skin if weighted_vertices(o, region) >= 20] or skin or meshes
    shapes = request.get("avatarShapes", {})
    for name, value in shapes.items():
        owners = [o for o in surfaces if o.data.shape_keys and name in o.data.shape_keys.key_blocks]
        if not owners:
            raise ValueError(f"No avatar surface mesh has the shape key {name}.")
        for obj in owners:
            block = obj.data.shape_keys.key_blocks[name]
            block.slider_max = max(1.0, value / 100)
            block.value = value / 100
    bpy.context.view_layer.update()
    vertices, polygons = [], []
    for obj in surfaces:
        points, _, faces = evaluated_surface(obj)
        base = len(vertices)
        vertices += points
        polygons += [tuple(base + i for i in face) for face in faces]
    if not polygons:
        raise ValueError("The avatar surface has no faces.")
    centre = head_center(objects, bone_name) or Vector()
    return {"tree": BVHTree.FromPolygons(vertices, polygons), "objects": objects, "surfaces": surfaces,
            "bone": bone_name, "origin": origin, "centre": centre}


CLOTHES = re.compile(r"cloth|costume|outfit|wear|hood|shoe|sneaker|boot|sock|skirt|shirt|jacket|coat|glove|dress",
                     re.IGNORECASE)


def weighted_vertices(obj, bones):
    indices = {group.index for group in obj.vertex_groups if group.name in bones}
    if not indices:
        return 0
    return sum(1 for v in obj.data.vertices if any(g.group in indices and g.weight > 0.3 for g in v.groups))


def signed_gap(tree, point, limit=0.3):
    location, normal, _, distance = tree.find_nearest(point, limit)
    if location is None:
        return limit
    return distance if (point - location).dot(normal) >= 0 else -distance


SHALLOW = 0.02  # metres: deeper "inside" readings are layered hair or ears seen from behind, not a real clash


def mesh_gap(tree, points):
    """Closest distance of the points to the avatar's surface, and how many lie just under it (within SHALLOW).
    Hair and ears are open shells, so a point can only be told to be inside when it is close to the surface."""
    gaps = [signed_gap(tree, p) for p in points]
    return (min(abs(g) for g in gaps) if gaps else 0.3), sum(1 for g in gaps if -SHALLOW < g < 0)


def rest_on(tree, point, direction, reach=0.12):
    """The first avatar surface met on the line through point along direction (toward the avatar), coming from
    reach metres outside it, with its normal turned back out. None when the line meets nothing."""
    location, normal, _, _ = tree.ray_cast(point - direction * reach, direction, reach * 2.5)
    if location is None:
        return None, None
    return location, (-normal if normal.dot(direction) > 0 else normal)


def toward(context, part, point):
    """The direction a part is moved to meet the avatar: the part's toward (Unity axes), else to the centre of
    the attach bone's region of the avatar (the skull for Head, the neck for Neck)."""
    if part.get("toward"):
        return unity_vector(part["toward"]).normalized()
    direction = context["centre"] - point
    return direction.normalized() if direction.length > 1e-6 else Vector((0, 0, -1))


def snap(objects, context, part, gap):
    """Move the part (or the whole model) in a straight line until its first point to touch the avatar's outer
    surface is gap metres from it. Returns the report and the move (Blender axes)."""
    points = [v.co.copy() for obj in objects for v in obj.data.vertices]
    sample = points[::max(1, len(points) // 3000)]
    centre = sum(points, Vector()) / len(points)
    direction = toward(context, part, centre)
    reach = 0.15
    distances = []
    for point in sample:
        location, _, _, distance = context["tree"].ray_cast(point - direction * reach, direction, reach * 2)
        if location is not None:
            distances.append(distance - reach)
    if not distances:
        return {"moved": False, "why": "no avatar surface within 15 cm in that direction"}, Vector()
    move = direction * max(-reach, min(reach, min(distances) - gap))
    for obj in objects:
        for vertex in obj.data.vertices:
            vertex.co += move
        obj.data.update()
    return {"moved": True, "movedMm": round(move.length * 1000, 1),
            "offset": [round(-move.x, 4), round(move.z, 4), round(-move.y, 4)]}, move


# --- sway bones ----------------------------------------------------------------------

def sway_joints(sweep, bones):
    """bones + 1 points at equal distances along the swept path."""
    samples, lengths = sweep["samples"], sweep["lengths"]
    total = lengths[-1]
    joints = []
    for i in range(bones + 1):
        target = total * i / bones
        k = next((k for k in range(1, len(lengths)) if lengths[k] >= target), len(lengths) - 1)
        span = lengths[k] - lengths[k - 1]
        t = 0 if span <= 0 else (target - lengths[k - 1]) / span
        joints.append(samples[k - 1].lerp(samples[k], max(0.0, min(1.0, t))))
    return joints


def sway_weights(obj, name, sweep, bones):
    """Weights that blend between neighbouring bones along the path, so the tube bends smoothly."""
    total = max(sweep["lengths"][-1], 1e-6)
    groups = [obj.vertex_groups.new(name=f"{name}_Sway{i + 1}") for i in range(bones)]
    for index, along in enumerate(sweep["along"]):
        f = along / total * bones - 0.5
        if f <= 0:
            groups[0].add([index], 1.0, "REPLACE")
        elif f >= bones - 1:
            groups[-1].add([index], 1.0, "REPLACE")
        else:
            low = int(f)
            frac = f - low
            groups[low].add([index], 1.0 - frac, "REPLACE")
            groups[low + 1].add([index], frac, "REPLACE")


def build_armature(chains):
    """An armature with a Root bone at the origin and, per swaying part, <part>_Sway (the PhysBone root, which
    stays put), <part>_Sway1..N along the path and <part>_SwayEnd (so the last bone has a direction to swing)."""
    data = bpy.data.armatures.new("Armature")
    rig = bpy.data.objects.new("Armature", data)
    bpy.context.scene.collection.objects.link(rig)
    select_only(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    edit = data.edit_bones
    root = edit.new("Root")
    root.head, root.tail = Vector((0, 0, 0)), Vector((0, 0, 0.02))
    for name, joints in chains:
        first = (joints[1] - joints[0]).normalized()
        anchor = edit.new(f"{name}_Sway")
        anchor.head, anchor.tail = joints[0], joints[0] + first * 0.005
        anchor.parent = root
        previous = anchor
        for i in range(1, len(joints)):
            bone = edit.new(f"{name}_Sway{i}")
            bone.head, bone.tail = joints[i - 1], joints[i]
            bone.parent = previous
            previous = bone
        last = (joints[-1] - joints[-2]).normalized()
        end = edit.new(f"{name}_SwayEnd")
        end.head, end.tail = joints[-1], joints[-1] + last * 0.01
        end.parent = previous
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


# --- finishing ------------------------------------------------------------------------

def smooth_shading(obj, mode):
    """'all' (round shapes), 'angle' (smooth with crisp edges), or 'flat'."""
    select_only(obj)
    if mode == "flat":
        bpy.ops.object.shade_flat()
        return
    if mode == "angle":
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(SMOOTH_ANGLE))
            return
        except (AttributeError, RuntimeError, TypeError):
            pass
    bpy.ops.object.shade_smooth()


def tidy(obj):
    """Merge doubled vertices, drop loose ones, point every face outward, and triangulate faces of more than
    four sides (Unity would otherwise triangulate concave outlines its own way)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def smart_uv(obj):
    select_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def pack_uv(obj):
    select_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.pack_islands(rotate=False, margin=0.01)
    except (RuntimeError, TypeError):
        bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")


def quality(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    report = {"mesh": obj.name, "triangles": sum(len(f.verts) - 2 for f in bm.faces),
              "openEdges": sum(1 for e in bm.edges if e.is_boundary),
              "nonManifoldEdges": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary),
              "tinyFaces": sum(1 for f in bm.faces if f.calc_area() < 1e-10),
              "uv": bool(obj.data.uv_layers), "materials": len(obj.material_slots)}
    bm.free()
    return report


def expand(part, index):
    """The part, and its mirror image on the avatar's other side when mirror is set. A mirrored pair is named
    <name>_R (avatar's right, +x) and <name>_L."""
    name = part.get("name") or f"{part['shape']}_{index}"
    if not part.get("mirror"):
        return [(part, name)]
    copy = dict(part)
    x, (rx, ry, rz) = part.get("position", [0, 0, 0])[0], part.get("rotation", [0, 0, 0])
    copy["position"] = [-x, *part.get("position", [0, 0, 0])[1:]]
    copy["rotation"] = [rx, -ry, -rz]
    if "points" in part:
        copy["points"] = [[-p[0], p[1], p[2]] for p in part["points"]]
    if isinstance(part.get("outline"), list):
        copy["outline"] = [[-p[0], p[1]] for p in reversed(part["outline"])]
    if "face" in part:
        copy["face"] = [-part["face"][0], *part["face"][1:]]
    copy["tilt"] = -part.get("tilt", 0)
    side = x if "points" not in part else sum(p[0] for p in part["points"]) / len(part["points"]) + x
    right, left = (part, copy) if side >= 0 else (copy, part)
    return [(right, f"{name}_R"), (left, f"{name}_L")]


def export_fbx(path, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "ARMATURE", "EMPTY"},
                             axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_ALL", bake_space_transform=False,
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", armature_nodetype="NULL",
                             bake_anim=False, path_mode="AUTO")


def make(request):
    reset_scene()
    context = avatar_context(request) if request.get("avatar") else None
    tree = context["tree"] if context else None
    gap = request.get("gap", 0.001)
    built, reports, chains = [], [], []
    for index, recipe_part in enumerate(request["parts"]):
        for part, name in expand(recipe_part, index):
            shape, conform = part["shape"], part.get("conform", "")
            sweep = None
            if shape == "tube":
                obj, sweep = tube(part, name, context if conform == "surface" else None, gap)
            elif shape == "lathe":
                obj = lathe(part, name)
            elif shape == "extrude":
                obj = extrude(part, name)
            else:
                obj = primitive(part, name)
            select_only(obj)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            report = {"part": name, "shape": shape}
            if conform == "snap":
                report["snap"], shift = snap([obj], context, part, gap)
                if sweep is not None:
                    # The sway bones follow the part: shift the swept samples by the same move.
                    sweep["samples"] = [p + shift for p in sweep["samples"]]
            bones = part.get("sway", 0)
            if bones and sweep is not None:
                sway_weights(obj, name, sweep, bones)
                chains.append((name, sway_joints(sweep, bones)))
                report["sway"] = {"root": f"{name}_Sway", "bones": bones,
                                  "lengthM": round(sweep["lengths"][-1], 4)}
            else:
                obj.vertex_groups.new(name="Root").add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
            if part.get("subdivide", 0) > 0:
                select_only(obj)
                modifier = obj.modifiers.new("Subdivide", "SUBSURF")
                modifier.levels = modifier.render_levels = part["subdivide"]
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            if shape != "tube":
                smart_uv(obj)
            smooth = part.get("smooth")
            if smooth is False:
                mode = "flat"
            elif shape in ("sphere", "torus") or part.get("subdivide", 0) > 0:
                mode = "all"
            elif shape == "cube" and not part.get("bevel") and smooth is None:
                mode = "flat"
            else:
                mode = "angle"
            smooth_shading(obj, mode)
            obj.data.materials.append(material(part.get("color", "#ffffff")))
            if tree is not None:
                gap_now, inside = mesh_gap(tree, [v.co for v in obj.data.vertices])
                report.update(gapMm=round(gap_now * 1000, 1), insideVertices=inside)
            built.append(obj)
            reports.append(report)

    snapped = None
    if request.get("snap"):
        # The whole model moves as one (a bow's knot, loops and tails stay together).
        snapped, shift = snap(built, context, {"toward": request.get("toward")}, gap)
        chains = [(name, [p + shift for p in joints]) for name, joints in chains]
        for obj, report in zip(built, reports):
            if "gapMm" in report:
                gap_now, inside = mesh_gap(tree, [v.co for v in obj.data.vertices])
                report.update(gapMm=round(gap_now * 1000, 1), insideVertices=inside)

    meshes = built
    if request.get("join", True) and len(built) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in built:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = built[0]
        bpy.ops.object.join()
        meshes = [bpy.context.active_object]
        meshes[0].name = request["name"]
    elif len(built) == 1:
        built[0].name = request["name"]

    pushed = None
    if tree is not None and request.get("push", True):
        before = sum(mesh_gap(tree, [v.co for v in obj.data.vertices])[1] for obj in meshes)
        for obj in meshes:
            for vertex, move in zip(obj.data.vertices, push_out(tree, obj, gap, limit=SHALLOW)):
                vertex.co += move
            obj.data.update()
        after = sum(mesh_gap(tree, [v.co for v in obj.data.vertices])[1] for obj in meshes)
        pushed = {"insideBefore": before, "insideAfter": after, "gapMm": round(gap * 1000, 2)}

    for obj in meshes:
        tidy(obj)
        if len(built) > 1 and obj.data.uv_layers:
            pack_uv(obj)

    rig = build_armature(chains) if chains else None
    if rig is not None:
        for obj in meshes:
            obj.parent = rig
            obj.modifiers.new("Armature", "ARMATURE").object = rig
        exported = [rig, *meshes]
        rig.name = request["name"] + "_Armature"
    else:
        for obj in meshes:
            group = obj.vertex_groups.get("Root")
            if group:
                obj.vertex_groups.remove(group)
        if len(meshes) == 1:
            exported = meshes
        else:
            root = bpy.data.objects.new(request["name"], None)
            bpy.context.scene.collection.objects.link(root)
            for obj in meshes:
                obj.parent = root
            exported = [root, *meshes]
    export_fbx(request["output"], exported)

    checks = [quality(obj) for obj in meshes]
    warnings = [f"The model was not snapped: {snapped['why']}."] if snapped and not snapped.get("moved") else []
    triangles_total = sum(c["triangles"] for c in checks)
    if triangles_total > MANY_TRIANGLES:
        warnings.append(f"{triangles_total} triangles: lower segments or subdivide (vrc-perf-budget).")
    if any(c["materials"] > 4 for c in checks):
        warnings.append("More than 4 materials (colours) on one mesh: each is a draw call in VRChat.")
    if any(c["nonManifoldEdges"] for c in checks):
        warnings.append("Some edges join more than two faces (parts that overlap exactly); check the preview.")
    for report in reports:
        if report.get("snap") and not report["snap"].get("moved"):
            warnings.append(f"{report['part']} was not snapped: {report['snap']['why']}.")
    if pushed and pushed["insideAfter"]:
        warnings.append(f"{pushed['insideAfter']} vertices are still inside the avatar after the push.")

    result = dict(describe(meshes), ok=True, output=request["output"], parts=reports, quality=checks,
                  warnings=warnings)
    if chains:
        result["sway"] = [{"root": f"{name}_Sway", "bones": len(joints) - 1} for name, joints in chains]
    if context:
        result["avatar"] = {"bone": context["bone"], "surfaces": [source_name(o) for o in context["surfaces"]][:30]}
        if snapped:
            result["snap"] = snapped
        result["push"] = pushed
    if request.get("preview"):
        shown = context["surfaces"] if context else []
        result["preview"] = render_preview(request["preview"], meshes, shown, colors="MATERIAL",
                                           min_extent=0.12 if context else 0.0, top=bool(context))
    return result


# --- fit: move an outfit onto another avatar's skeleton -----------------------------

def armature_of(objects, label):
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise ValueError(f"The {label} must contain exactly one armature (found {len(armatures)}).")
    return armatures[0]


def bone_pairs(outfit, avatar, overrides):
    """Outfit bone name -> avatar bone name: explicit map, then the same name, then humanoid spelling."""
    avatar_names = {bone.name for bone in avatar.data.bones}
    avatar_humanoid = humanoid_map(avatar)
    pairs = {}
    for bone in outfit.data.bones:
        target = overrides.get(bone.name)
        if target is None and bone.name in avatar_names:
            target = bone.name
        if target is None:
            key = humanoid_key(bone.name)
            target = avatar_humanoid.get(key) if key else None
        if target is not None:
            if target not in avatar_names:
                raise ValueError(f"boneMap points {bone.name} at {target}, which the avatar does not have.")
            pairs[bone.name] = target
    return pairs


def bone_order(armature):
    order = []

    def visit(bone):
        order.append(bone.name)
        for child in bone.children:
            visit(child)
    for bone in armature.data.bones:
        if bone.parent is None:
            visit(bone)
    return order


PRIMARY_CHILD = ("spine", "chest", "upperchest", "neck", "head")


def main_child(armature, name, pairs):
    """The mapped child whose head marks where this bone points (spine before legs for the hips)."""
    children = [child.name for child in armature.data.bones[name].children_recursive if child.name in pairs]
    direct = [c for c in children if armature.data.bones[c].parent.name == name] or children[:1]
    if not direct:
        return None
    for core in PRIMARY_CHILD:
        for child in direct:
            if humanoid_key(child) == core:
                return child
    return direct[0] if len(direct) == 1 else None


SCALES = {}
BODY_SCALE = [None, None, None]  # used, height ratio, width ratio
# Torso bones are short and their joints sit in different places on different rigs (the spine joint just above
# the hips on one avatar, well above it on another), so their own length ratio is not a size: one short hips
# segment scaled a whole coat skirt by 1.9. They keep the body scale instead.
TORSO = {"hips", "spine", "chest", "upperchest", "neck", "left shoulder", "right shoulder"}
LIMB_RANGE = (0.8, 1.25)  # limbs follow their own length, within this range of the body scale


def body_scale(outfit, avatar, pairs, to_outfit):
    """The avatar's body size over the outfit's: the geometric mean of the hips-to-head height ratio and the
    shoulder width ratio (either alone when the other is missing). None when the outfit spans neither, as with
    hair or a hat that matches at the head only."""
    by_key = {}
    for name, target in pairs.items():
        key = humanoid_key(target) or humanoid_key(name)
        if key and key not in by_key:
            by_key[key] = name

    def ratio(a, b):
        if a not in by_key or b not in by_key:
            return None
        have = (outfit.data.bones[by_key[a]].head_local - outfit.data.bones[by_key[b]].head_local).length
        want = (to_outfit @ avatar.data.bones[pairs[by_key[a]]].head_local -
                to_outfit @ avatar.data.bones[pairs[by_key[b]]].head_local).length
        return want / have if have > 1e-5 and want > 1e-5 else None

    height = ratio("hips", "head") or ratio("hips", "neck")
    width = ratio("left upperarm", "right upperarm")
    found = [value for value in (height, width) if value]
    if not found:
        BODY_SCALE[:] = [None, None, None]
        return None
    body = max(0.5, min(2.0, (found[0] * found[-1]) ** 0.5))
    BODY_SCALE[:] = [round(body, 3), round(height, 3) if height else None, round(width, 3) if width else None]
    return body


def pose_to_avatar(outfit, avatar, pairs, scale_bones, extra_scale=1.0, offset=(0, 0, 0), pivot_shift=None):
    """Pose each mapped outfit bone so its head and direction match the avatar's rest pose (parents first).

    extra_scale and offset (Unity axes, metres) apply to the top mapped bones: they are for items that match
    the avatar at one bone only (hair or a hat on the head), whose size cannot be read from the skeleton.
    With scale_bones, a whole outfit takes the avatar's body scale (hips to head) and each limb follows its own
    length within LIMB_RANGE of it; unmapped bones (skirts, sleeves, ribbons) inherit their parent's scale.
    """
    to_outfit = outfit.matrix_world.inverted() @ avatar.matrix_world
    avatar_head = {name: to_outfit @ avatar.data.bones[name].head_local for name in set(pairs.values())}
    shift = outfit.matrix_world.inverted().to_3x3() @ unity_vector(offset)
    body = body_scale(outfit, avatar, pairs, to_outfit) if scale_bones else None
    cumulative = {}
    report = []
    bpy.context.view_layer.objects.active = outfit
    bpy.ops.object.mode_set(mode="POSE")
    for name in bone_order(outfit):
        if name not in pairs:
            continue
        pose = outfit.pose.bones[name]
        bpy.context.view_layer.update()
        current = pose.matrix.copy()
        head = current.translation.copy()
        want = avatar_head[pairs[name]]
        rotation = Matrix.Identity(4)
        factor = 1.0
        child = main_child(outfit, name, pairs)
        if child is not None:
            have_vector = outfit.pose.bones[child].matrix.translation - head
            want_vector = avatar_head[pairs[child]] - want
            if have_vector.length > 1e-5 and want_vector.length > 1e-5:
                rotation = have_vector.rotation_difference(want_vector).to_matrix().to_4x4()
                if scale_bones:
                    factor = max(0.5, min(2.0, want_vector.length / have_vector.length))
        mapped_parent = next((parent.name for parent in outfit.data.bones[name].parent_recursive
                              if parent.name in pairs), None)
        inherited = cumulative.get(mapped_parent, 1.0)
        if body is not None:
            key = humanoid_key(pairs[name]) or humanoid_key(name)
            if key in TORSO:
                factor = body / inherited
            else:
                total = max(body * LIMB_RANGE[0], min(body * LIMB_RANGE[1], inherited * factor))
                factor = total / inherited
        top = mapped_parent is None
        if top:
            want = want + shift + (pivot_shift if pivot_shift is not None else Vector())
            factor *= extra_scale
        cumulative[name] = inherited * factor
        moved = (Matrix.Translation(want) @ rotation @ Matrix.Scale(factor, 4) @ Matrix.Translation(-head) @ current)
        pose.matrix = moved
        report.append(name)
        SCALES[name] = round(cumulative[name], 3)
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")
    return report


def bake_deform(obj, extra_offset=None):
    """Apply the evaluated deformation of obj to its mesh and every shape key (modifiers keep the topology).

    extra_offset: optional per-vertex displacement added to the basis and every shape key.
    """
    dependencies = bpy.context.evaluated_depsgraph_get()
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
    saved = (obj.show_only_shape_key, obj.active_shape_key_index)
    coordinates = []
    if keys:
        obj.show_only_shape_key = True
        for index in range(len(keys)):
            obj.active_shape_key_index = index
            dependencies.update()
            evaluated = obj.evaluated_get(dependencies)
            mesh = evaluated.to_mesh()
            coordinates.append([v.co.copy() for v in mesh.vertices])
            evaluated.to_mesh_clear()
        obj.show_only_shape_key, obj.active_shape_key_index = saved
    else:
        dependencies.update()
        evaluated = obj.evaluated_get(dependencies)
        mesh = evaluated.to_mesh()
        coordinates.append([v.co.copy() for v in mesh.vertices])
        evaluated.to_mesh_clear()
    if any(len(points) != len(obj.data.vertices) for points in coordinates):
        raise ValueError(f"{obj.name}: a modifier changes the vertex count; apply it in Blender first.")
    if extra_offset is not None:
        coordinates = [[p + d for p, d in zip(points, extra_offset)] for points in coordinates]
    if keys:
        for block, points in zip(keys, coordinates):
            for vertex, point in zip(block.data, points):
                vertex.co = point
    for vertex, point in zip(obj.data.vertices, coordinates[0]):
        vertex.co = point
    obj.data.update()


def body_tree(body):
    dependencies = bpy.context.evaluated_depsgraph_get()
    evaluated = body.evaluated_get(dependencies)
    mesh = evaluated.to_mesh()
    vertices = [body.matrix_world @ v.co for v in mesh.vertices]
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices, polygons)


def inside_count(tree, obj, limit=0.05):
    """Vertices of obj that lie under the body surface (within limit metres of it)."""
    count = 0
    matrix = obj.matrix_world
    for vertex in obj.data.vertices:
        point = matrix @ vertex.co
        location, normal, _, distance = tree.find_nearest(point, limit)
        if location is not None and (point - location).dot(normal) < 0:
            count += 1
    return count


def push_out(tree, obj, offset, limit=0.05):
    """Per-vertex displacement (object space) that moves vertices under the body to offset above it."""
    matrix = obj.matrix_world
    inverse = matrix.inverted().to_3x3()
    moves = []
    for vertex in obj.data.vertices:
        point = matrix @ vertex.co
        location, normal, _, distance = tree.find_nearest(point, limit)
        if location is None:
            moves.append(Vector())
            continue
        depth = (point - location).dot(normal)
        moves.append(inverse @ (normal * (offset - depth)) if depth < offset else Vector())
    return moves


def find_body(avatar_objects, name, bones=None, label="avatar"):
    """The named mesh, or the one that covers the most of the given bones (the bones the outfit uses), then has
    the most vertices on them: a full outfit picks the body, hair picks the head mesh. A name containing 'body'
    counts a little more."""
    meshes = [obj for obj in avatar_objects if obj.type == "MESH"]
    if name:
        match = [obj for obj in meshes if source_name(obj) == name]
        if not match:
            names = ", ".join(source_name(o) for o in meshes[:30])
            raise ValueError(f"The {label} has no mesh named {name}. Meshes: {names}")
        return match[0]
    if not meshes:
        return None

    def score(obj):
        if not bones:
            return len(obj.data.vertices)
        indices = {group.index for group in obj.vertex_groups if group.name in bones}
        per_bone = {}
        for vertex in obj.data.vertices:
            for g in vertex.groups:
                if g.group in indices and g.weight > 0.3:
                    per_bone[g.group] = per_bone.get(g.group, 0) + 1
        covered = sum(1 for n in per_bone.values() if n >= 20)
        count = sum(per_bone.values()) * (1.5 if "body" in source_name(obj).lower() else 1.0)
        return covered, count
    return max(meshes, key=score)


def set_shapes(obj, values, label):
    """Zero every shape key, then set the given ones (0-100, as Unity shows them)."""
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else {}
    for block in list(keys)[1:]:
        block.value = 0.0
    missing = [name for name in values if name not in keys]
    if missing:
        raise ValueError(f"The {label} mesh {source_name(obj)} has no shape key {', '.join(missing[:5])}.")
    for name, value in values.items():
        keys[name].slider_max = max(1.0, value / 100)
        keys[name].value = value / 100


def evaluated_surface(obj):
    """World positions and normals of obj as it is now deformed (armature and shape keys), plus its polygons."""
    dependencies = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(dependencies)
    mesh = evaluated.to_mesh()
    matrix = obj.matrix_world
    normal_matrix = matrix.to_3x3().inverted().transposed()
    points = [matrix @ v.co for v in mesh.vertices]
    normals = [(normal_matrix @ v.normal).normalized() for v in mesh.vertices]
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    evaluated.to_mesh_clear()
    return points, normals, polygons


def make_field(points, moves):
    tree = KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    return tree, moves


def body_difference(source_body, target_tree, limit=0.08):
    """How far each point of the (skeleton-aligned) source body must move to reach the target body's surface.

    Only points whose nearest target surface faces the same way count, so a leg never snaps to the other leg.
    """
    points, normals, _ = evaluated_surface(source_body)
    kept, moves = [], []
    for point, normal in zip(points, normals):
        location, target_normal, _, _ = target_tree.find_nearest(point, limit)
        if location is not None and target_normal.dot(normal) > 0.3:
            kept.append(point)
            moves.append(location - point)
    if len(kept) < 50:
        raise ValueError("The source body does not line up with the avatar body after the skeleton fit. "
                         "Check 'source' (the avatar the outfit was made for) and 'sourceBody'.")
    return make_field(kept, moves), len(kept), len(points)


def field_offsets(field, obj, count=12):
    """Per-vertex displacement (object space) of obj, interpolated from the nearest field points."""
    tree, moves = field
    matrix = obj.matrix_world
    inverse = matrix.inverted().to_3x3()
    offsets = []
    for vertex in obj.data.vertices:
        total, weight = Vector(), 0.0
        for _, index, distance in tree.find_n(matrix @ vertex.co, count):
            w = 1.0 / (distance + 0.005) ** 2
            total += moves[index] * w
            weight += w
        offsets.append(inverse @ (total / weight) if weight else Vector())
    return offsets


def follow_shapes(body, meshes, names, min_move=0.0005):
    """Make each named body shape key on the outfit meshes as well (same name), by carrying the body's
    displacement to the nearest outfit vertices. Meshes that hardly move, or already have the key, are skipped."""
    keys = body.data.shape_keys.key_blocks if body.data.shape_keys else {}
    missing = [name for name in names if name not in keys]
    if missing:
        raise ValueError(f"The body {source_name(body)} has no shape key {', '.join(missing[:5])}.")
    points, _, _ = evaluated_surface(body)
    rotation = body.matrix_world.to_3x3()
    made = {}
    for name in names:
        block = keys[name]
        relative = block.relative_key
        moves = [rotation @ (a.co - b.co) for a, b in zip(block.data, relative.data)]
        field = make_field(points, moves)
        for obj in meshes:
            existing = obj.data.shape_keys.key_blocks if obj.data.shape_keys else {}
            if name in existing:
                continue
            offsets = field_offsets(field, obj)
            if max((o.length for o in offsets), default=0) < min_move:
                continue
            if not obj.data.shape_keys:
                obj.shape_key_add(name="Basis", from_mix=False)
            basis = obj.data.shape_keys.key_blocks[0]
            key = obj.shape_key_add(name=name, from_mix=False)
            # New keys may start at 1.0 (Blender 5), and the FBX keeps that as the default weight in Unity.
            key.value = 0.0
            for target, base, offset in zip(key.data, basis.data, offsets):
                target.co = base.co + offset
            made.setdefault(source_name(obj), []).append(name)
    return made


def transfer_weights(body, meshes, avatar):
    """Replace the outfit meshes' weights with the body's (nearest surface), bound to the avatar's armature."""
    for obj in meshes:
        obj.vertex_groups.clear()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        body.select_set(True)
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.data_transfer(data_type="VGROUP_WEIGHTS", use_create=True, vert_mapping="POLYINTERP_NEAREST",
                                     layers_select_src="NAME", layers_select_dst="ALL", mix_mode="REPLACE")
        for modifier in [m for m in obj.modifiers if m.type == "ARMATURE"]:
            obj.modifiers.remove(modifier)
        world = obj.matrix_world.copy()
        obj.parent = avatar
        obj.matrix_world = world
        obj.modifiers.new("Armature", "ARMATURE").object = avatar


def source_name(obj):
    return obj.get("dsh_name", obj.name)


def import_named(path, prefix):
    """Import a file and record each object's own name; the objects are renamed with prefix so a second import
    (which may contain the same names) keeps its names too."""
    objects = import_model(path)
    for obj in objects:
        obj["dsh_name"] = obj.name
    for obj in objects:
        obj.name = prefix + obj.name
    return objects


def restore_names(keep, others):
    """Give the exported objects their source names back (others step aside first)."""
    for obj in others:
        obj.name = "DSH_unused_" + source_name(obj)
    for obj in keep:
        obj.name = source_name(obj)


def inside_count_evaluated(tree, obj, limit=0.05, min_z=None):
    """inside_count on the posed (evaluated) mesh, before the pose is baked; with min_z, only vertices above it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        count = 0
        for vertex in mesh.vertices:
            point = evaluated.matrix_world @ vertex.co
            if min_z is not None and point.z < min_z:
                continue
            location, normal, _, _ = tree.find_nearest(point, limit)
            if location is not None and (point - location).dot(normal) < 0:
                count += 1
        return count
    finally:
        evaluated.to_mesh_clear()


def head_center(avatar_objects, bone_name):
    """World-space centre of the avatar vertices that follow the head bone (the skull, not the neck joint)."""
    total, count = Vector(), 0
    for obj in avatar_objects:
        if obj.type != "MESH" or bone_name not in obj.vertex_groups:
            continue
        index = obj.vertex_groups[bone_name].index
        for vertex in obj.data.vertices:
            if any(g.group == index and g.weight > 0.5 for g in vertex.groups):
                total += obj.matrix_world @ vertex.co
                count += 1
    return total / count if count >= 20 else None


def head_needs(tree, meshes, centre, min_z, limit=0.05):
    """For each posed vertex above min_z that sits inside the body: the scale about centre that would bring it
    out to the surface (radially)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    needs = []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            for vertex in mesh.vertices:
                point = evaluated.matrix_world @ vertex.co
                if point.z < min_z:
                    continue
                location, normal, _, _ = tree.find_nearest(point, limit)
                if location is None or (point - location).dot(normal) >= 0:
                    continue
                reach = (point - centre).length
                if reach > 1e-4:
                    needs.append(((location - centre).length + 0.002) / reach)
        finally:
            evaluated.to_mesh_clear()
    return needs


HEAD_COVER = 0.8   # the scale clears this share of the vertices inside the head; the push handles the rest
HEAD_RANGE = (0.8, 1.35)


def auto_head_scale(outfit, avatar, pairs, meshes, tree, avatar_objects, offset):
    """For items matched at one bone (hair, hats), whose size the skeleton cannot tell: the scale about the centre
    of the avatar's head that brings HEAD_COVER of the vertices inside the head out to its surface, or, when
    almost none are inside, the smallest scale that keeps it so. Only vertices above the head joint count: long
    hair resting on the neck and back touches the body by design. Returns (scale, pivot_shift, detail)."""
    top = [name for name in pairs
           if not any(parent.name in pairs for parent in outfit.data.bones[name].parent_recursive)]
    if len(top) != 1:
        return None
    joint_name = pairs[top[0]]
    centre_world = head_center(avatar_objects, joint_name)
    if centre_world is None:
        return None
    to_outfit = outfit.matrix_world.inverted()
    joint_world = avatar.matrix_world @ avatar.data.bones[joint_name].head_local
    pivot = to_outfit @ centre_world - to_outfit @ joint_world
    vertices = sum(len(obj.data.vertices) for obj in meshes)
    allowed = max(5, vertices // 200)

    def pose(scale):
        for bone in outfit.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        pose_to_avatar(outfit, avatar, pairs, False, scale, offset, (1 - scale) * pivot)
        bpy.context.view_layer.update()
        return head_needs(tree, meshes, centre_world, joint_world.z)

    needs = pose(1.0)
    detail = {"insideAt1": len(needs)}
    if len(needs) > allowed:
        needs.sort()
        scale = needs[min(len(needs) - 1, int(len(needs) * HEAD_COVER))]
    else:
        scale = 1.0
        while scale - 0.02 >= HEAD_RANGE[0] and len(pose(round(scale - 0.02, 2))) <= allowed:
            scale = round(scale - 0.02, 2)
    scale = round(max(HEAD_RANGE[0], min(HEAD_RANGE[1], scale)), 3)
    detail["insideAfter"] = len(pose(scale))
    for bone in outfit.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return scale, (1 - scale) * pivot, detail


def fit(request):
    reset_scene()
    # The outfit comes first so its materials keep their names when the avatar uses the same ones.
    outfit_objects = import_named(request["outfit"], "DSH_outfit_")
    avatar_objects = import_named(request["avatar"], "DSH_avatar_")
    avatar = armature_of(avatar_objects, "avatar")
    outfit = armature_of(outfit_objects, "outfit")
    exclude = set(request.get("exclude", []))
    meshes = [obj for obj in outfit_objects if obj.type == "MESH" and source_name(obj) not in exclude]
    if not meshes:
        raise ValueError("The outfit has no meshes to fit.")
    pairs = bone_pairs(outfit, avatar, request.get("boneMap", {}))
    if not pairs:
        raise ValueError("No outfit bone matches an avatar bone. Map them with boneMap.")
    humanoid = [name for name in pairs if humanoid_key(pairs[name])]
    body = find_body(avatar_objects, request.get("body", ""), set(pairs.values()))
    shapes = request.get("avatarShapes", {})
    if body is not None:
        set_shapes(body, shapes, "avatar")
    elif shapes:
        raise ValueError("avatarShapes needs the avatar body mesh.")
    bpy.context.view_layer.update()
    tree = body_tree(body) if body else None
    auto_scale = request.get("scale", 1.0) == "auto"
    pose_args = (request.get("scaleBones", True), 1.0 if auto_scale else request.get("scale", 1.0),
                 request.get("offset", [0, 0, 0]))

    # The avatar the outfit was made for, posed the same way: the gap between its body and the avatar's body
    # is carried onto the outfit (chest, waist, arm thickness: what the skeleton alone cannot tell).
    surface = None
    if request.get("source"):
        if tree is None:
            raise ValueError("'source' needs the avatar body mesh.")
        source_objects = import_named(request["source"], "DSH_source_")
        source_rig = armature_of(source_objects, "source avatar")
        source_pairs = bone_pairs(source_rig, avatar, request.get("boneMap", {}))
        source_body = find_body(source_objects, request.get("sourceBody", ""), set(source_pairs),
                                "source avatar")
        if source_body is None:
            raise ValueError("The source avatar has no mesh.")
        set_shapes(source_body, request.get("sourceShapes", {}), "source avatar")
        pose_to_avatar(source_rig, avatar, source_pairs, *pose_args)
        bpy.context.view_layer.update()
        field, matched, total = body_difference(source_body, tree)
        surface = {"sourceBody": source_name(source_body), "matchedPoints": f"{matched}/{total}"}

    head_scale = None
    if auto_scale and tree is not None and body_scale(outfit, avatar, pairs,
                                                       outfit.matrix_world.inverted() @ avatar.matrix_world) is None:
        found = auto_head_scale(outfit, avatar, pairs, meshes, tree, avatar_objects, pose_args[2])
        if found is not None:
            head_scale = dict(found[2], scale=found[0])
            pose_args = (False, found[0], pose_args[2], found[1])
    posed = pose_to_avatar(outfit, avatar, pairs, *pose_args)
    for obj in meshes:
        bake_deform(obj)
    bpy.context.view_layer.objects.active = outfit
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if surface is not None:
        moved = []
        for obj in meshes:
            offsets = field_offsets(field, obj)
            rotation = obj.matrix_world.to_3x3()
            moved += [(rotation @ o).length for o in offsets]
            bake_deform(obj, offsets)
        moved.sort()
        surface.update(meanMoveMm=round(sum(moved) / len(moved) * 1000, 1),
                       maxMoveMm=round(moved[-1] * 1000, 1))
    fitted = {source_name(obj): inside_count(tree, obj) for obj in meshes} if tree else {}

    renamed = {}
    weights = request.get("weights", "keep")
    if weights == "transfer":
        if body is None:
            raise ValueError("weights 'transfer' needs the avatar body mesh.")
        transfer_weights(body, meshes, avatar)
        rig = avatar
    else:
        # Mapped bones take the avatar's names so Modular Avatar merges them; vertex groups follow the rename.
        for name, target in sorted(pairs.items()):
            if name != target and target not in outfit.data.bones:
                outfit.data.bones[name].name = target
                renamed[name] = target
        rig = outfit

    push = request.get("push", 0.0)
    pushed = {}
    if tree and push > 0:
        for obj in meshes:
            bake_deform(obj, push_out(tree, obj, push))
        pushed = {source_name(obj): inside_count(tree, obj) for obj in meshes}

    followed = {}
    if request.get("followShapes"):
        if body is None:
            raise ValueError("followShapes needs the avatar body mesh.")
        followed = follow_shapes(body, meshes, request["followShapes"])

    exported = [rig, *meshes]
    others = [obj for obj in bpy.data.objects if obj not in exported and obj.type in ("MESH", "ARMATURE")]
    restore_names(exported, others)
    if request.get("output"):
        export_fbx(request["output"], exported)
    unmatched = [b.name for b in outfit.data.bones if b.name not in pairs and b.name not in renamed.values()]
    result = {"ok": True, "output": request.get("output", ""), "weights": weights,
              "mappedBones": len(pairs), "humanoidBones": len(humanoid), "posedBones": len(posed), "bodyScale": dict(zip(("used", "height", "width"), BODY_SCALE)), "headScale": head_scale,
              # Bones whose own length set a scale other than the body scale (limbs within LIMB_RANGE).
              "boneScales": {k: v for k, v in SCALES.items() if not BODY_SCALE[0] or abs(v - BODY_SCALE[0]) > 0.03},
              "renamedBones": dict(list(renamed.items())[:MAX_LISTED]),
              # Swaying bones (skirt, hair, strings) need no match; a main bone left here does.
              "unmatchedHumanoidBones": [name for name in unmatched if humanoid_key(name)][:MAX_LISTED],
              "unmatchedOtherBones": len([name for name in unmatched if not humanoid_key(name)]),
              "body": source_name(body) if body else None, "avatarShapes": shapes,
              "surfaceFit": surface, "followedShapes": followed,
              "verticesInsideBody": {"afterFit": fitted, "afterPush": pushed}, "push": push,
              "meshes": describe(meshes)["meshes"]}
    if request.get("preview"):
        # Only the body (and a separate head or face mesh): the avatar's own clothes and hair would hide the outfit.
        skin = [obj for obj in avatar_objects if obj.type == "MESH" and
                re.search(r"body|face|head", source_name(obj), re.IGNORECASE)]
        result["preview"] = render_preview(request["preview"], meshes, list({*skin, *([body] if body else [])}))
    return result


# --- preview render -------------------------------------------------------------

def render_preview(path, focus, context, size=512, colors="OBJECT", min_extent=0.0, top=False):
    """Front and side orthographic workbench renders. With OBJECT colours the focus objects are orange and the
    context objects grey; MATERIAL shows the material colours."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = colors
    shown = set(focus) | set(context)
    for obj in scene.objects:
        obj.hide_render = obj.type == "MESH" and obj not in shown
    for obj in context:
        obj.color = (0.55, 0.55, 0.58, 1)
    for obj in focus:
        obj.color = (0.95, 0.45, 0.35, 1)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("World")
    bounds = world_bounds(focus)
    if bounds is None:
        return []
    low, high = bounds
    centre = (low + high) / 2
    extent = max((high - low).length * 0.65, 0.05, min_extent)
    camera_data = bpy.data.cameras.new("DSH Preview")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = extent * 2
    camera = bpy.data.objects.new("DSH Preview", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    images = []
    views = [("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0)))]
    if top:
        views.append(("top", Vector((0, -0.35, 1)).normalized()))
    for name, direction in views:
        camera.location = centre + direction * 10
        camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = path.replace(".png", f"-{name}.png")
        bpy.ops.render.render(write_still=True)
        images.append(scene.render.filepath)
    return images


# --- entry --------------------------------------------------------------------------

def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    command, request_path, result_path = args
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    try:
        result = {"inspect": inspect, "make": make, "fit": fit}[command](request)
    except Exception as error:  # reported to the caller as JSON
        result = {"ok": False, "error": f"{type(error).__name__}: {error}",
                  "trace": traceback.format_exc()[-3000:]}
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)


if __name__ == "__main__":
    main()
