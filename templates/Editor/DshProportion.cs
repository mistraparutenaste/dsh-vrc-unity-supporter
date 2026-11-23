using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// The avatar's view position (where the first-person camera sits) and per-bone sizes through Modular Avatar
    /// Scale Adjuster (a bigger head, smaller hands), without changing the FBX. Each change is an undo entry.
    /// </summary>
    public static class DshProportion
    {
        [Serializable]
        private sealed class Scale
        {
            public string bone = "";
            public float[] scale = { 1, 1, 1 };
            public bool children = true;   // true: the bone's own scale (hair and ears on the head grow too)
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string name = "";
            public bool verifySdk = false;
            public string viewMode = "";      // "", auto, set or offset
            public float[] view = new float[3];
            public float forward = 0.035f;
            public Scale[] scales = Array.Empty<Scale>();
            public DshUndo[] undo = Array.Empty<DshUndo>();
        }

        [Serializable]
        private sealed class CaptureRequest
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string views = "front,face";
            public int size = 512;
            public bool build = true;
            public Request recipe = new Request();
        }

        private const string AdjusterType = "nadena.dev.modular_avatar.core.ModularAvatarScaleAdjuster";

        /// <summary>Read-only: the current view position, where the eyes are, and the bones that already have a size.</summary>
        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                result["viewPosition"] = DshReflect.Format(View(avatar));
                var eyes = Eyes(avatar);
                result["eyes"] = eyes.HasValue ? DshReflect.Format(eyes.Value) : null;
                result["suggested"] = eyes.HasValue ? DshReflect.Format(Auto(avatar, request.forward)) : null;
                if (eyes.HasValue) result["viewToEyes"] = Math.Round((View(avatar) - eyes.Value).magnitude, 4);
                var type = DshVrc.LoadedType(AdjusterType);
                result["modularAvatar"] = type != null;
                result["scaleAdjusters"] = type == null ? Array.Empty<object>() : avatar.GetComponentsInChildren(type, true)
                    .Select(c => (object)new Dictionary<string, object>
                    {
                        { "path", DshReflect.PathIn(c.transform, avatar.transform) },
                        { "scale", DshReflect.Format(type.GetProperty("Scale").GetValue(c)) },
                    }).ToArray();
                result["note"] = "Positions are in the avatar's space (x right, y up, z forward; metres).";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Proportions", result);
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
                result["viewBefore"] = DshReflect.Format(View(avatar));
                var log = new DshUndoLog();
                var changes = ApplyRecipe(avatar, request, log);
                result["applied"] = changes;
                result["undo"] = DshUndo.DescribeAll(log.Entries);
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied proportion recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                // Factors and offsets start from the values before DSH changed them, which now include this apply's.
                var earlier = request.undo ?? Array.Empty<DshUndo>();
                request.undo = earlier.Concat(log.Entries.Where(e => earlier.All(u => u.key != e.key))).ToArray();
                var remaining = ApplyRecipe(avatar, request, null);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the recipe: " + string.Join("; ", remaining.Take(5)));
                result["viewPosition"] = DshReflect.Format(View(avatar));
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
            DshAvatarScene.Finish("ProportionRecipe", result);
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
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed proportion recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Revert(avatar, request.undo);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene still holds part of the recipe: " + string.Join("; ", remaining.Take(5)));
                result["viewPosition"] = DshReflect.Format(View(avatar));
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("ProportionRemove", result);
        }

        /// <summary>
        /// Before/after renders, with a small red ball where the view position is. With build, both rows are SDK-built
        /// copies, so Scale Adjuster sizes show as they will in VRChat.
        /// </summary>
        public static void Capture()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                DshCapture.RequireGraphics();
                var request = DshAvatarScene.ReadRequest<CaptureRequest>();
                var views = DshCapture.ParseViews(request.views);
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                var recipe = JsonUtility.FromJson<Request>(JsonUtility.ToJson(request.recipe));
                var positions = new Dictionary<string, object>();
                GameObject Make(GameObject source, string label, bool withRecipe)
                {
                    Action<GameObject> prepare = copy => { if (withRecipe) ApplyRecipe(copy, recipe, null); };
                    GameObject made;
                    if (request.build) made = DshVrc.PreprocessCopy(source, prepare);
                    else
                    {
                        made = UnityEngine.Object.Instantiate(source);
                        prepare(made);
                    }
                    var view = View(made);
                    positions[label] = DshReflect.Format(view);
                    var marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    UnityEngine.Object.DestroyImmediate(marker.GetComponent<UnityEngine.Collider>());
                    marker.name = "DSH View Marker";
                    marker.transform.SetParent(made.transform, false);
                    marker.transform.localPosition = view;
                    marker.transform.localScale = Vector3.one * 0.015f;
                    var material = new Material(Shader.Find("Unlit/Color") ?? Shader.Find("Standard")) { color = Color.red };
                    marker.GetComponent<Renderer>().sharedMaterial = material;
                    return made;
                }
                var rows = new List<(string label, Func<GameObject, GameObject> make)>
                {
                    ("original", source => Make(source, "original", false)),
                    (recipe.name, source => Make(source, recipe.name, true)),
                };
                result["image"] = DshCapture.RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048), rows);
                result["columns"] = views;
                result["rows"] = rows.Select(r => r.label).ToArray();
                result["viewPositions"] = positions;
                result["built"] = request.build;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("ProportionCapture", result);
        }

        private static Component Descriptor(GameObject avatar) => DshAvatarScene.Descriptor(avatar)
            ?? throw new InvalidOperationException("The avatar has no VRC Avatar Descriptor.");

        private static Vector3 View(GameObject avatar) =>
            (Vector3)DshReflect.Field(Descriptor(avatar).GetType(), "ViewPosition").GetValue(Descriptor(avatar));

        /// <summary>Midpoint of the eye bones in the avatar's space, when the avatar has both.</summary>
        private static Vector3? Eyes(GameObject avatar)
        {
            var animator = avatar.GetComponent<Animator>();
            if (animator == null || !animator.isHuman) return null;
            var left = animator.GetBoneTransform(HumanBodyBones.LeftEye);
            var right = animator.GetBoneTransform(HumanBodyBones.RightEye);
            if (left == null || right == null) return null;
            return avatar.transform.InverseTransformPoint((left.position + right.position) * 0.5f);
        }

        /// <summary>Between the eyes and a little in front of them, where VRChat expects the view.</summary>
        private static Vector3 Auto(GameObject avatar, float forward)
        {
            var eyes = Eyes(avatar) ?? throw new InvalidOperationException(
                "The avatar has no LeftEye and RightEye bones, so the view position cannot be placed automatically. Give it as numbers.");
            return eyes + new Vector3(0, 0, forward / Mathf.Max(1e-4f, Mathf.Abs(avatar.transform.lossyScale.z)));
        }

        private static List<string> ApplyRecipe(GameObject avatar, Request recipe, DshUndoLog log)
        {
            var changes = new List<string>();
            // Sizes first: an automatic view position follows the eyes of the resized head.
            foreach (var item in recipe.scales)
            {
                var bone = DshReflect.Bone(avatar, item.bone);
                var path = DshReflect.PathIn(bone, avatar.transform);
                var wanted = item.scale != null && item.scale.Length == 3 ? new Vector3(item.scale[0], item.scale[1], item.scale[2]) : Vector3.one;
                if (item.children)
                {
                    // The bone's own scale, so everything on it (hair, ears, accessories) grows with it. The factor
                    // applies to the scale before DSH changed it, so applying again does not multiply it twice.
                    var entry = (recipe.undo ?? Array.Empty<DshUndo>()).FirstOrDefault(e => e.kind == "boneScale" && e.path == path);
                    var original = entry != null ? DshReflect.Vector(entry.before) : bone.localScale;
                    var target = Vector3.Scale(original, wanted);
                    if (DshReflect.Same(bone.localScale, target)) continue;
                    log?.Add(new DshUndo { key = "bone:" + path, kind = "boneScale", path = path, before = DshReflect.Format(bone.localScale) });
                    changes.Add($"{path}: bone scale {DshReflect.Format(bone.localScale)} -> {DshReflect.Format(target)}");
                    bone.localScale = target;
                    DshReflect.Dirty(bone);
                    continue;
                }
                var type = DshVrc.LoadedType(AdjusterType)
                    ?? throw new InvalidOperationException("Modular Avatar is not installed. Add it in VCC/ALCOM to size a bone without its children.");
                var property = type.GetProperty("Scale") ?? throw new InvalidOperationException("This Modular Avatar has no Scale Adjuster Scale.");
                var component = bone.GetComponent(type);
                if (component == null)
                {
                    component = bone.gameObject.AddComponent(type);
                    log?.Add(new DshUndo { key = "scale:" + path, kind = "scaleAdded", path = path });
                    changes.Add($"{path}: added Scale Adjuster");
                }
                var current = (Vector3)property.GetValue(component);
                if (DshReflect.Same(current, wanted)) continue;
                log?.Add(new DshUndo { key = "scale:" + path, kind = "scale", path = path, before = DshReflect.Format(current) });
                property.SetValue(component, wanted);
                DshReflect.Dirty(component);
                changes.Add($"{path}: Scale Adjuster {DshReflect.Format(current)} -> {DshReflect.Format(wanted)}");
            }
            if (!string.IsNullOrEmpty(recipe.viewMode))
            {
                var current = View(avatar);
                var values = recipe.view != null && recipe.view.Length == 3 ? new Vector3(recipe.view[0], recipe.view[1], recipe.view[2]) : Vector3.zero;
                Vector3 wanted;
                switch (recipe.viewMode)
                {
                    case "auto": wanted = Auto(avatar, recipe.forward); break;
                    case "set": wanted = values; break;
                    case "offset":
                        // An offset applies to the position before DSH changed it, so a second apply does not add it again.
                        wanted = OriginalView(avatar, recipe) + values;
                        break;
                    default: throw new InvalidOperationException("viewMode must be auto, set or offset.");
                }
                if (!DshReflect.Same(current, wanted))
                {
                    var descriptor = Descriptor(avatar);
                    DshReflect.Field(descriptor.GetType(), "ViewPosition").SetValue(descriptor, wanted);
                    DshReflect.Dirty(descriptor);
                    log?.Add(new DshUndo { key = "view", kind = "view", before = DshReflect.Format(current) });
                    changes.Add($"view position {DshReflect.Format(current)} -> {DshReflect.Format(wanted)}");
                }
            }
            return changes;
        }

        /// <summary>The view position before DSH changed it (from the recipe's earlier undo record), else the current one.</summary>
        private static Vector3 OriginalView(GameObject avatar, Request recipe)
        {
            var entry = (recipe.undo ?? Array.Empty<DshUndo>()).FirstOrDefault(e => e.kind == "view");
            return entry != null ? DshReflect.Vector(entry.before) : View(avatar);
        }

        private static List<string> Revert(GameObject avatar, DshUndo[] undo)
        {
            var changes = new List<string>();
            var type = DshVrc.LoadedType(AdjusterType);
            foreach (var entry in undo)
            {
                switch (entry.kind)
                {
                    case "view":
                        var descriptor = Descriptor(avatar);
                        var wanted = DshReflect.Vector(entry.before);
                        var field = DshReflect.Field(descriptor.GetType(), "ViewPosition");
                        if (DshReflect.Same(field.GetValue(descriptor), wanted))
                        {
                            DshReflect.RevertIfSource(descriptor, "ViewPosition");
                            break;
                        }
                        field.SetValue(descriptor, wanted);
                        DshReflect.Dirty(descriptor);
                        DshReflect.RevertIfSource(descriptor, "ViewPosition");
                        changes.Add($"view position = {entry.before}");
                        break;
                    case "boneScale":
                        var bone = avatar.transform.Find(entry.path);
                        if (bone == null) break;
                        var scale = DshReflect.Vector(entry.before);
                        if (!DshReflect.Same(bone.localScale, scale))
                        {
                            bone.localScale = scale;
                            DshReflect.Dirty(bone);
                            changes.Add($"{entry.path}: bone scale = {entry.before}");
                        }
                        var source = PrefabUtility.IsPartOfPrefabInstance(bone) ? PrefabUtility.GetCorrespondingObjectFromSource(bone) : null;
                        if (source != null && DshReflect.Same(source.localScale, bone.localScale))
                        {
                            var serialized = new SerializedObject(bone).FindProperty("m_LocalScale");
                            if (serialized != null && serialized.prefabOverride)
                                PrefabUtility.RevertPropertyOverride(serialized, InteractionMode.AutomatedAction);
                        }
                        break;
                    case "scaleAdded":
                        var added = type == null ? null : avatar.transform.Find(entry.path)?.GetComponent(type);
                        if (added == null || !DshReflect.AddedInScene(added)) break;
                        UnityEngine.Object.DestroyImmediate(added);
                        changes.Add($"{entry.path}: removed Scale Adjuster");
                        break;
                    case "scale":
                        var component = type == null ? null : avatar.transform.Find(entry.path)?.GetComponent(type);
                        if (component == null) break;
                        var scaleProperty = type.GetProperty("Scale");
                        var before = DshReflect.Vector(entry.before);
                        if (DshReflect.Same(scaleProperty.GetValue(component), before)) break;
                        scaleProperty.SetValue(component, before);
                        DshReflect.Dirty(component);
                        changes.Add($"{entry.path}: scale = {entry.before}");
                        break;
                }
            }
            return changes;
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar);
                result["viewPositionAfterBuild"] = DshReflect.Format(View(copy));
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
