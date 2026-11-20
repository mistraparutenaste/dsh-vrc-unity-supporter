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

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


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
    return dict(describe(objects), ok=True, file=request["file"])


# --- make: simple shapes ----------------------------------------------------------

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
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*linear, 1)
    mat.diffuse_color = (*linear, 1)
    return mat


def primitive(part, index):
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
    obj.name = part.get("name") or f"{shape}_{index}"
    # Every primitive starts in a 1 m box; size is its box in Unity axes (width x, height y, depth z).
    height = part.get("thickness", 0.2) if shape == "torus" else 1
    obj.scale = (size.x, size.z, size.y / height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.matrix_world = Matrix.Translation(unity_vector(part.get("position", [0, 0, 0]))) @ unity_rotation(
        part.get("rotation", [0, 0, 0])).to_4x4()
    if part.get("bevel", 0) > 0 and shape in ("cube", "cylinder"):
        modifier = obj.modifiers.new("Bevel", "BEVEL")
        modifier.width = part["bevel"]
        modifier.segments = 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    if part.get("smooth", shape in ("sphere", "torus", "cylinder", "cone")):
        bpy.ops.object.shade_smooth()
    obj.data.materials.append(material(part.get("color", "#ffffff")))
    return obj


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
    parts = [primitive(part, i) for i, part in enumerate(request["parts"])]
    if request.get("join", True) and len(parts) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        parts = [bpy.context.active_object]
    root = parts[0] if len(parts) == 1 else None
    if root is not None:
        root.name = request["name"]
    else:
        root = bpy.data.objects.new(request["name"], None)
        bpy.context.scene.collection.objects.link(root)
        for obj in parts:
            obj.parent = root
    export_fbx(request["output"], [root, *parts] if root not in parts else parts)
    result = dict(describe(parts), ok=True, output=request["output"])
    if request.get("preview"):
        result["preview"] = render_preview(request["preview"], parts, [], colors="MATERIAL")
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


def pose_to_avatar(outfit, avatar, pairs, scale_bones, extra_scale=1.0, offset=(0, 0, 0)):
    """Pose each mapped outfit bone so its head and direction match the avatar's rest pose (parents first).

    extra_scale and offset (Unity axes, metres) apply to the top mapped bones: they are for items that match
    the avatar at one bone only (hair or a hat on the head), whose size cannot be read from the skeleton.
    """
    to_outfit = outfit.matrix_world.inverted() @ avatar.matrix_world
    avatar_head = {name: to_outfit @ avatar.data.bones[name].head_local for name in set(pairs.values())}
    shift = outfit.matrix_world.inverted().to_3x3() @ unity_vector(offset)
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
        top = not any(parent.name in pairs for parent in outfit.data.bones[name].parent_recursive)
        if top:
            want = want + shift
            factor *= extra_scale
        moved = (Matrix.Translation(want) @ rotation @ Matrix.Scale(factor, 4) @ Matrix.Translation(-head) @ current)
        pose.matrix = moved
        report.append(name)
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


def find_body(avatar_objects, name):
    meshes = [obj for obj in avatar_objects if obj.type == "MESH"]
    if name:
        match = [obj for obj in meshes if source_name(obj) == name]
        if not match:
            names = ", ".join(source_name(o) for o in meshes[:30])
            raise ValueError(f"The avatar has no mesh named {name}. Meshes: {names}")
        return match[0]
    return max(meshes, key=lambda obj: len(obj.data.vertices)) if meshes else None


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
    body = find_body(avatar_objects, request.get("body", ""))
    tree = body_tree(body) if body else None

    posed = pose_to_avatar(outfit, avatar, pairs, request.get("scaleBones", True), request.get("scale", 1.0),
                           request.get("offset", [0, 0, 0]))
    for obj in meshes:
        bake_deform(obj)
    bpy.context.view_layer.objects.active = outfit
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
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

    exported = [rig, *meshes]
    restore_names(exported, [obj for obj in [*outfit_objects, *avatar_objects] if obj not in exported])
    if request.get("output"):
        export_fbx(request["output"], exported)
    result = {"ok": True, "output": request.get("output", ""), "weights": weights,
              "mappedBones": len(pairs), "humanoidBones": len(humanoid), "posedBones": len(posed),
              "renamedBones": dict(list(renamed.items())[:MAX_LISTED]),
              "unmatchedOutfitBones": [b.name for b in outfit.data.bones if b.name not in pairs and
                                       b.name not in renamed.values()][:MAX_LISTED],
              "body": source_name(body) if body else None,
              "verticesInsideBody": {"afterFit": fitted, "afterPush": pushed}, "push": push,
              "meshes": describe(meshes)["meshes"]}
    if request.get("preview"):
        result["preview"] = render_preview(request["preview"], meshes, [o for o in avatar_objects if o.type == "MESH"])
    return result


# --- preview render -------------------------------------------------------------

def render_preview(path, focus, context, size=512, colors="OBJECT"):
    """Front and side orthographic workbench renders. With OBJECT colours the focus objects are orange and the
    context objects grey; MATERIAL shows the material colours."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = colors
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
    extent = max((high - low).length * 0.65, 0.05)
    camera_data = bpy.data.cameras.new("DSH Preview")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = extent * 2
    camera = bpy.data.objects.new("DSH Preview", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    images = []
    for name, direction in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0)))):
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
