using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// PhysBone adjustments without touching the source prefab: values of existing VRC PhysBones (how hair, skirts
    /// and tails swing, whether they can be grabbed or posed) are saved as scene overrides, and capsule or sphere
    /// colliders that DSH adds live under the humanoid bone as "DSH Collider &lt;recipe&gt; &lt;name&gt;".
    /// Every change is reported as an undo entry, so remove puts back only what DSH changed.
    /// </summary>
    public static class DshPhysBone
    {
        [Serializable]
        private sealed class Value
        {
            public string field = "";
            public string value = "";
        }

        [Serializable]
        private sealed class Bone
        {
            public string target = "";
            public int index = -1;
            public Value[] values = Array.Empty<Value>();
        }

        [Serializable]
        private sealed class Collider
        {
            public string name = "";
            public string bone = "";
            public string to = "";
            public string shape = "capsule";
            public float radius = 0.05f;
            public float height = 0;
            public float[] offset = new float[3];
            public bool insideBounds = false;
            public Bone[] targets = Array.Empty<Bone>();
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string name = "";
            public string filter = "";
            public bool verifySdk = false;
            public Bone[] bones = Array.Empty<Bone>();
            public Collider[] colliders = Array.Empty<Collider>();
            public DshUndo[] undo = Array.Empty<DshUndo>();
        }

        public const string ColliderPrefix = "DSH Collider ";
        private static readonly string[] Namespaces = { "VRC" };
        private static readonly string[] Listed =
        {
            "version", "integrationType", "pull", "spring", "stiffness", "gravity", "gravityFalloff", "immobileType",
            "immobile", "limitType", "maxAngleX", "maxAngleZ", "radius", "allowCollision", "allowGrabbing",
            "allowPosing", "grabMovement", "maxStretch", "maxSquish", "snapToHand",
        };
        // Humanoid bones and the bone a capsule on them reaches to by default.
        private static readonly Dictionary<string, string> NextBone = new Dictionary<string, string>
        {
            { "Hips", "Spine" }, { "Spine", "Chest" }, { "Chest", "Neck" }, { "UpperChest", "Neck" }, { "Neck", "Head" },
            { "LeftUpperLeg", "LeftLowerLeg" }, { "RightUpperLeg", "RightLowerLeg" },
            { "LeftLowerLeg", "LeftFoot" }, { "RightLowerLeg", "RightFoot" },
            { "LeftUpperArm", "LeftLowerArm" }, { "RightUpperArm", "RightLowerArm" },
            { "LeftLowerArm", "LeftHand" }, { "RightLowerArm", "RightHand" },
        };

        private static Type PhysBoneType => DshReflect.Find("VRCPhysBone", Namespaces)
            ?? throw new InvalidOperationException("The VRChat SDK PhysBone component is unavailable in this project.");

        private static Type ColliderType => DshReflect.Find("VRCPhysBoneCollider", Namespaces)
            ?? throw new InvalidOperationException("The VRChat SDK PhysBone collider is unavailable in this project.");

        /// <summary>Read-only: every PhysBone of the avatar with its values, what it moves, and the colliders.</summary>
        public static void List()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var filter = request.filter ?? "";
                var bones = new List<object>();
                var totalTransforms = 0;
                foreach (var component in avatar.GetComponentsInChildren(PhysBoneType, true))
                {
                    var path = DshReflect.PathIn(component.transform, avatar.transform);
                    var root = RootOf(component);
                    var moved = Moved(component).Count;
                    totalTransforms += moved;
                    if (filter.Length > 0 && path.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0 &&
                        DshReflect.PathIn(root, avatar.transform).IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                    var values = new Dictionary<string, object>();
                    foreach (var field in Listed)
                    {
                        var info = PhysBoneType.GetField(field);
                        if (info != null) values[field] = DshReflect.Format(info.GetValue(component));
                    }
                    bones.Add(new Dictionary<string, object>
                    {
                        { "target", path }, { "index", IndexOf(component) }, { "root", DshReflect.PathIn(root, avatar.transform) },
                        { "part", Part(path + "/" + root.name) }, { "transforms", moved },
                        { "active", component.gameObject.activeInHierarchy && ((Behaviour)component).enabled },
                        { "values", values },
                        { "colliders", Colliders(component).Select(c => c == null ? "(missing)" : DshReflect.PathIn(c.transform, avatar.transform)).ToArray() },
                    });
                }
                result["physBones"] = bones;
                result["colliders"] = avatar.GetComponentsInChildren(ColliderType, true).Select(c => new Dictionary<string, object>
                {
                    { "path", DshReflect.PathIn(c.transform, avatar.transform) },
                    { "shape", DshReflect.Format(ColliderType.GetField("shapeType")?.GetValue(c)) },
                    { "radius", DshReflect.Format(ColliderType.GetField("radius")?.GetValue(c)) },
                    { "height", DshReflect.Format(ColliderType.GetField("height")?.GetValue(c)) },
                    { "dsh", c.gameObject.name.StartsWith(ColliderPrefix, StringComparison.Ordinal) },
                }).ToArray();
                result["counts"] = Counts(avatar);
                result["note"] = "transforms is how many bones each PhysBone moves (the performance rank counts the total).";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("PhysBones", result);
        }

        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["recipe"] = request.name;
                result["countsBefore"] = Counts(avatar);
                var log = new DshUndoLog();
                var changes = ApplyRecipe(avatar, request, log);
                result["applied"] = changes;
                result["undo"] = DshUndo.DescribeAll(log.Entries);
                if (changes.Count > 0)
                {
                    Save(scene, request.expectedSceneDigest, result, $"Applied PhysBone recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = ApplyRecipe(avatar, request, null);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the recipe: " + string.Join("; ", remaining.Take(5)));
                result["counts"] = Counts(avatar);
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar)
                    : new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("PhysBoneRecipe", result);
        }

        public static void Remove()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["recipe"] = request.name;
                var changes = Revert(avatar, request.undo);
                result["reverted"] = changes;
                if (changes.Count > 0)
                {
                    Save(scene, request.expectedSceneDigest, result, $"Removed PhysBone recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Revert(avatar, request.undo);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene still holds part of the recipe: " + string.Join("; ", remaining.Take(5)));
                result["counts"] = Counts(avatar);
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("PhysBoneRemove", result);
        }

        /// <summary>Apply a recipe request (JSON) to an avatar in memory, for the simulation; returns the changes.</summary>
        internal static List<string> TryRecipe(GameObject avatar, string json)
        {
            var recipe = JsonUtility.FromJson<Request>(json) ?? throw new InvalidOperationException("The recipe to try is not valid.");
            return ApplyRecipe(avatar, recipe, null);
        }

        internal static void Save(UnityEngine.SceneManagement.Scene scene, string digest, Dictionary<string, object> result, string note)
        {
            DshAvatarScene.RequireSceneDigest(scene.path, digest);
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene))
                throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
            result["saved"] = true;
            DshApply.Note(result, note);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }

        private static List<string> ApplyRecipe(GameObject avatar, Request recipe, DshUndoLog log)
        {
            var changes = new List<string>();
            foreach (var bone in recipe.bones)
            {
                var component = Resolve(avatar, bone);
                var path = DshReflect.PathIn(component.transform, avatar.transform);
                var index = IndexOf(component);
                foreach (var value in bone.values)
                {
                    if (PhysBoneType.GetField(value.field) == null)
                        throw new InvalidOperationException($"The PhysBone on '{path}' has no '{value.field}' in this SDK version.");
                    var before = DshReflect.Set(component, value.field, value.value);
                    if (before == null) continue;
                    log?.Add(new DshUndo { key = $"value:{path}#{index}:{value.field}", kind = "value", path = path, index = index, field = value.field, before = before });
                    changes.Add($"{path}: {value.field} {before} -> {value.value}");
                }
            }
            foreach (var collider in recipe.colliders)
                changes.AddRange(EnsureCollider(avatar, recipe.name, collider, log));
            return changes;
        }

        private static List<string> EnsureCollider(GameObject avatar, string recipe, Collider spec, DshUndoLog log)
        {
            var changes = new List<string>();
            var bone = DshReflect.Bone(avatar, spec.bone);
            var objectName = ColliderPrefix + recipe + " " + spec.name;
            var existing = bone.Cast<Transform>().Where(t => t.name == objectName).ToArray();
            if (existing.Length > 1) throw new InvalidOperationException($"Several objects are named '{objectName}'.");
            GameObject holder;
            if (existing.Length == 0)
            {
                holder = new GameObject(objectName);
                holder.transform.SetParent(bone, false);
                holder.AddComponent(ColliderType);
                var holderPath = DshReflect.PathIn(holder.transform, avatar.transform);
                log?.Add(new DshUndo { key = "collider:" + holderPath, kind = "collider", path = holderPath });
                changes.Add($"added collider {holderPath}");
            }
            else holder = existing[0].gameObject;
            var component = holder.GetComponent(ColliderType) ?? throw new InvalidOperationException($"'{objectName}' has no PhysBone collider.");
            var colliderPath = DshReflect.PathIn(holder.transform, avatar.transform);

            // Shape: a capsule from the bone towards the next bone (or `to`), or a sphere on the bone.
            var capsule = spec.shape == "capsule";
            var offset = spec.offset != null && spec.offset.Length == 3 ? new Vector3(spec.offset[0], spec.offset[1], spec.offset[2]) : Vector3.zero;
            var position = bone.InverseTransformVector(avatar.transform.rotation * offset) ;
            var rotation = Quaternion.identity;
            var height = 0f;
            if (capsule)
            {
                var toName = string.IsNullOrEmpty(spec.to) ? (NextBone.TryGetValue(spec.bone, out var next) ? next : "") : spec.to;
                if (string.IsNullOrEmpty(toName))
                    throw new InvalidOperationException($"Say which bone the capsule on {spec.bone} reaches to ('to'), or use a sphere.");
                var end = DshReflect.Bone(avatar, toName);
                var local = bone.InverseTransformPoint(end.position);
                if (local.magnitude < 1e-4f) throw new InvalidOperationException($"{spec.bone} and {toName} are at the same place.");
                position += local * 0.5f;
                rotation = Quaternion.FromToRotation(Vector3.up, local.normalized);
                var lossy = Mathf.Max(1e-4f, Mathf.Abs(bone.lossyScale.y));
                height = spec.height > 0 ? spec.height / lossy : local.magnitude + 2 * spec.radius / lossy;
            }
            var lossyRadius = Mathf.Max(1e-4f, Mathf.Abs(bone.lossyScale.x));
            var wanted = new Dictionary<string, object>
            {
                { "shapeType", DshReflect.Parse(ColliderType.GetField("shapeType").FieldType, capsule ? "Capsule" : "Sphere") },
                { "radius", spec.radius / lossyRadius }, { "height", height }, { "position", position },
                { "insideBounds", spec.insideBounds },
            };
            foreach (var pair in wanted)
            {
                var info = DshReflect.Field(ColliderType, pair.Key);
                if (DshReflect.Same(info.GetValue(component), pair.Value)) continue;
                info.SetValue(component, pair.Value);
                DshReflect.Dirty(component);
                changes.Add($"{colliderPath}: {pair.Key} = {DshReflect.Format(pair.Value)}");
            }
            var rotationField = DshReflect.Field(ColliderType, "rotation");
            if (Quaternion.Angle((Quaternion)rotationField.GetValue(component), rotation) > 0.01f)
            {
                rotationField.SetValue(component, rotation);
                DshReflect.Dirty(component);
                changes.Add($"{colliderPath}: rotation");
            }
            var rootField = ColliderType.GetField("rootTransform");
            if (rootField != null && (Transform)rootField.GetValue(component) != bone)
            {
                rootField.SetValue(component, bone);
                DshReflect.Dirty(component);
                changes.Add($"{colliderPath}: follows {spec.bone}");
            }
            // Holder at the bone with no offset; the collider's own position and rotation place the shape.
            if (holder.transform.localPosition != Vector3.zero || holder.transform.localRotation != Quaternion.identity)
            {
                holder.transform.localPosition = Vector3.zero;
                holder.transform.localRotation = Quaternion.identity;
                changes.Add($"{colliderPath}: placed on {spec.bone}");
            }

            foreach (var target in spec.targets)
            {
                var physBone = Resolve(avatar, target);
                var list = DshReflect.List(physBone, "colliders");
                if (list.Cast<object>().Any(c => (c as Component) == component)) continue;
                list.Add(component);
                DshReflect.Dirty(physBone);
                var path = DshReflect.PathIn(physBone.transform, avatar.transform);
                var index = IndexOf(physBone);
                log?.Add(new DshUndo { key = $"uses:{path}#{index}:{colliderPath}", kind = "uses", path = path, index = index, other = colliderPath });
                changes.Add($"{path}: collides with {colliderPath}");
            }
            return changes;
        }

        private static List<string> Revert(GameObject avatar, DshUndo[] undo)
        {
            var changes = new List<string>();
            foreach (var entry in undo.Where(e => e.kind == "uses"))
            {
                var physBone = Find(avatar, entry.path, entry.index);
                var collider = avatar.transform.Find(entry.other)?.GetComponent(ColliderType);
                if (physBone == null || collider == null) continue;
                var list = DshReflect.List(physBone, "colliders");
                var removed = false;
                for (var i = list.Count - 1; i >= 0; i--)
                    if ((list[i] as Component) == collider) { list.RemoveAt(i); removed = true; }
                if (!removed) continue;
                DshReflect.Dirty(physBone);
                DshReflect.RevertIfSource(physBone, "colliders");
                changes.Add($"{entry.path}: no longer collides with {entry.other}");
            }
            foreach (var entry in undo.Where(e => e.kind == "collider"))
            {
                var holder = avatar.transform.Find(entry.path);
                if (holder == null || !holder.name.StartsWith(ColliderPrefix, StringComparison.Ordinal)) continue;
                // Other PhysBones that still point at the collider would keep a missing reference.
                var collider = holder.GetComponent(ColliderType);
                foreach (var physBone in avatar.GetComponentsInChildren(PhysBoneType, true))
                {
                    var list = DshReflect.List(physBone, "colliders");
                    for (var i = list.Count - 1; i >= 0; i--)
                        if ((list[i] as Component) == collider)
                        {
                            list.RemoveAt(i);
                            DshReflect.Dirty(physBone);
                            DshReflect.RevertIfSource(physBone, "colliders");
                        }
                }
                UnityEngine.Object.DestroyImmediate(holder.gameObject);
                changes.Add($"removed collider {entry.path}");
            }
            foreach (var entry in undo.Where(e => e.kind == "value"))
            {
                var physBone = Find(avatar, entry.path, entry.index);
                if (physBone == null || PhysBoneType.GetField(entry.field) == null) continue;
                var before = DshReflect.Set(physBone, entry.field, entry.before);
                DshReflect.RevertIfSource(physBone, entry.field);
                if (before != null) changes.Add($"{entry.path}: {entry.field} = {entry.before}");
            }
            return changes;
        }

        private static Component Find(GameObject avatar, string path, int index)
        {
            var target = string.IsNullOrEmpty(path) ? avatar.transform : avatar.transform.Find(path);
            var components = target == null ? Array.Empty<Component>() : target.GetComponents(PhysBoneType);
            return index >= 0 && index < components.Length ? components[index] : null;
        }

        /// <summary>
        /// The PhysBone a recipe entry means: the one on the object at the path (or the index-th when there are
        /// several), else the one whose root is that object.
        /// </summary>
        private static Component Resolve(GameObject avatar, Bone bone)
        {
            var target = string.IsNullOrEmpty(bone.target) ? avatar.transform : avatar.transform.Find(bone.target)
                ?? throw new InvalidOperationException($"No object at '{bone.target}' under the avatar. Use a path from the list command.");
            var on = target.GetComponents(PhysBoneType);
            if (on.Length == 0)
                on = avatar.GetComponentsInChildren(PhysBoneType, true).Where(c => RootOf(c) == target).ToArray();
            if (on.Length == 0) throw new InvalidOperationException($"'{bone.target}' has no PhysBone and is not the root of one.");
            if (bone.index >= 0)
                return bone.index < on.Length ? on[bone.index] : throw new InvalidOperationException($"'{bone.target}' has {on.Length} PhysBones; index {bone.index} is out of range.");
            if (on.Length > 1) throw new InvalidOperationException($"'{bone.target}' has {on.Length} PhysBones. Add 'index' from the list command.");
            return on[0];
        }

        private static int IndexOf(Component component) => Array.IndexOf(component.GetComponents(component.GetType()), component);

        private static Transform RootOf(Component component) =>
            PhysBoneType.GetField("rootTransform")?.GetValue(component) as Transform ?? component.transform;

        private static IEnumerable<Component> Colliders(Component component) =>
            (PhysBoneType.GetField("colliders")?.GetValue(component) as IEnumerable ?? Array.Empty<object>()).Cast<object>().Select(c => c as Component);

        /// <summary>Transforms the PhysBone moves: its root's descendants, without ignored branches (the root counts).</summary>
        private static List<Transform> Moved(Component component)
        {
            var root = RootOf(component);
            var ignored = (PhysBoneType.GetField("ignoreTransforms")?.GetValue(component) as IEnumerable ?? Array.Empty<object>())
                .Cast<object>().OfType<Transform>().Where(t => t != null).ToArray();
            return root.GetComponentsInChildren<Transform>(true).Where(t => !ignored.Any(i => t.IsChildOf(i))).ToList();
        }

        private static string Part(string path)
        {
            var p = path.ToLowerInvariant();
            if (p.Contains("skirt") || p.Contains("スカート")) return "skirt";
            if (p.Contains("tail") || p.Contains("しっぽ") || p.Contains("尻尾")) return "tail";
            if (p.Contains("ear") || p.Contains("耳")) return "ear";
            if (p.Contains("breast") || p.Contains("bust") || p.Contains("胸")) return "breast";
            if (p.Contains("hair") || p.Contains("髪") || p.Contains("bang") || p.Contains("前髪")) return "hair";
            return "other";
        }

        internal static Dictionary<string, object> Counts(GameObject avatar)
        {
            var bones = avatar.GetComponentsInChildren(PhysBoneType, true);
            return new Dictionary<string, object>
            {
                { "physBones", bones.Length },
                { "transforms", bones.Sum(b => Moved(b).Count) },
                { "colliders", avatar.GetComponentsInChildren(ColliderType, true).Length },
                { "colliderChecks", bones.Sum(b => Colliders(b).Count(c => c != null) * Math.Max(1, Moved(b).Count)) },
            };
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar);
                result["countsAfterBuild"] = Counts(copy);
                result["status"] = "passed";
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            finally
            {
                if (copy != null) UnityEngine.Object.DestroyImmediate(copy);
            }
            return result;
        }
    }
}
