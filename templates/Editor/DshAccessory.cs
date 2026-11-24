using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Attach an existing prefab or model to an avatar without changing either asset. Rigid items (hats, ribbons,
    /// props) follow one humanoid bone through Modular Avatar Bone Proxy; items with their own armature (hair or
    /// outfits made for the avatar, or fitted in Blender) are merged with Modular Avatar Setup Outfit. Everything
    /// lives under one "DSH Accessory &lt;name&gt;" object, which can carry a VRCFury menu toggle.
    /// </summary>
    public static class DshAccessory
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string filter = "";
            public string name = "";
            public string asset = "";
            public string mode = "auto";
            public string bone = "Head";
            public string origin = "auto";
            public float[] position = new float[3];
            public float[] rotation = new float[3];
            public float scale = 1;
            public bool fitHead = false;
            public string menu = "";
            public string[] hide = Array.Empty<string>();
            public string materialsFrom = "";
            public bool defaultOn = true;
            public bool verifySdk = false;
            public string folder = "";
            public bool keepFiles = false;
            public string follow = "proxy";   // proxy (MA Bone Proxy), constraint (held: VRC Parent Constraint), world
            public string dropMenu = "";      // with constraint: a menu toggle that leaves the item where it is
            public PhysBoneSpec[] physBones = Array.Empty<PhysBoneSpec>();
        }

        [Serializable]
        private sealed class PhysBoneValue
        {
            public string field = "";
            public string value = "";
        }

        /// <summary>A PhysBone the accessory adds on one of its own bones (sway bones of a model made in Blender).</summary>
        [Serializable]
        private sealed class PhysBoneSpec
        {
            public string root = "";
            public PhysBoneValue[] values = Array.Empty<PhysBoneValue>();
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

        public const string HolderPrefix = "DSH Accessory ";
        private const string BoneProxyType = "nadena.dev.modular_avatar.core.ModularAvatarBoneProxy";
        private const string MergeArmatureType = "nadena.dev.modular_avatar.core.ModularAvatarMergeArmature";
        private const string SetupOutfitType = "nadena.dev.modular_avatar.core.editor.SetupOutfit";
        private const string WorldFixedType = "nadena.dev.modular_avatar.core.ModularAvatarWorldFixedObject";
        public const string DropHolder = "DSH Drop";
        private const int MaxCandidates = 60;
        private const float Tolerance = 1e-4f;
        // An asset whose meshes already sit this close to the bone was made in the avatar's space (hair or
        // accessories for this avatar); others are moved so their origin is on the bone.
        private const float AvatarSpaceDistance = 0.5f;

        /// <summary>Read-only: prefabs and models that match a filter, how each would attach, and the avatar's bones.</summary>
        public static void Candidates()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var animator = avatar.GetComponent<Animator>();
                result["humanoid"] = animator != null && animator.isHuman;
                result["bones"] = animator != null && animator.isHuman
                    ? Enum.GetValues(typeof(HumanBodyBones)).Cast<HumanBodyBones>()
                        .Where(b => b != HumanBodyBones.LastBone && animator.GetBoneTransform(b) != null)
                        .Select(b => b.ToString()).ToArray()
                    : Array.Empty<string>();
                result["attached"] = avatar.transform.Cast<Transform>()
                    .Where(t => t.name.StartsWith(HolderPrefix, StringComparison.Ordinal))
                    .Select(t => t.name.Substring(HolderPrefix.Length)).ToArray();

                var filter = request.filter ?? "";
                var found = new List<Dictionary<string, object>>();
                var total = 0;
                foreach (var guid in AssetDatabase.FindAssets("t:GameObject " + filter, new[] { "Assets" }))
                {
                    var path = AssetDatabase.GUIDToAssetPath(guid);
                    if (path.StartsWith("Assets/DSH/Editor/", StringComparison.Ordinal)) continue;
                    var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                    if (root == null || DshAvatarScene.Descriptor(root) != null) continue;
                    var renderers = root.GetComponentsInChildren<Renderer>(true);
                    if (renderers.Length == 0) continue;
                    if (total++ >= MaxCandidates) continue;
                    found.Add(new Dictionary<string, object>
                    {
                        { "asset", path }, { "kind", Kind(root) }, { "renderers", renderers.Length },
                        { "triangles", Triangles(root, true) }
                    });
                }
                result["assets"] = found;
                result["assetCount"] = total;
                result["truncated"] = total > MaxCandidates;
                result["modularAvatar"] = DshVrc.LoadedType(BoneProxyType) != null;
                result["note"] = "kind 'armature' merges with the avatar's bones (Setup Outfit); 'rigid' follows one bone (Bone Proxy).";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("AccessoryCandidates", result);
        }

        /// <summary>Attach the accessory in the saved scene (or update its offset), save, and check it from a fresh load.</summary>
        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["accessory"] = request.name;
                var changes = ApplyRecipe(avatar, request, true, out var mode);
                result["mode"] = mode;
                if (mode == "bone") result["origin"] = Origin(avatar, request);
                if (request.fitHead && LastHeadFit != null) result["headFit"] = LastHeadFit;
                result["applied"] = changes;
                if (changes.Count > 0)
                {
                    DshAvatarScene.RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Attached accessory {request.name} ({changes.Count} changes)");
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                // Applying the recipe again to the saved scene must change nothing.
                var remaining = ApplyRecipe(avatar, request, true, out _);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the accessory: " + string.Join("; ", remaining.Take(5)));
                result["holder"] = HolderPrefix + request.name;
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, request, mode)
                    : new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("AccessoryApply", result);
        }

        /// <summary>Remove the accessory object (and its toggle) from the saved scene; optionally delete the recipe folder.</summary>
        public static void Remove()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                if (string.IsNullOrEmpty(request.name) || request.folder != "Assets/DSH/Accessories/" + request.name)
                    throw new InvalidOperationException("The request does not describe an accessory under Assets/DSH/Accessories.");
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["accessory"] = request.name;
                var holderName = HolderPrefix + request.name;
                var holder = DshVrc.FindHolder(avatar, holderName);
                result["holderRemoved"] = holder != null;
                if (holder != null)
                {
                    // Turn back on what an always-worn accessory turned off.
                    foreach (var path in request.hide ?? Array.Empty<string>())
                    {
                        var hidden = avatar.transform.Find(path);
                        if (hidden == null || hidden.gameObject.activeSelf || hidden.IsChildOf(holder.transform)) continue;
                        SetActive(hidden.gameObject, true);
                        DshApply.Note(result, $"Turned on {path}");
                    }
                    UnityEngine.Object.DestroyImmediate(holder);
                    DshAvatarScene.RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Removed accessory {request.name}");
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                    if (DshVrc.FindHolder(avatar, holderName) != null)
                        throw new InvalidOperationException("The accessory is still in the saved scene.");
                }
                if (!request.keepFiles && AssetDatabase.IsValidFolder(request.folder))
                {
                    if (!AssetDatabase.DeleteAsset(request.folder))
                        throw new IOException($"Unity could not delete {request.folder}.");
                    DshApply.Note(result, $"Deleted {request.folder}");
                    result["deleted"] = request.folder;
                }
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("AccessoryRemove", result);
        }

        /// <summary>
        /// Before/after renders without saving. With build, both rows are SDK-built copies, so Bone Proxy and Merge
        /// Armature place the accessory as they will in VRChat.
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
                var triangles = new Dictionary<string, object>();
                var mode = "";
                GameObject Make(GameObject source, string label, bool withAccessory)
                {
                    Action<GameObject> prepare = copy =>
                    {
                        // An earlier apply of the same accessory is replaced by the recipe being tried.
                        var old = DshVrc.FindHolder(copy, HolderPrefix + recipe.name);
                        if (old != null) UnityEngine.Object.DestroyImmediate(old);
                        if (withAccessory) ApplyRecipe(copy, recipe, false, out mode);
                    };
                    GameObject made;
                    if (request.build) made = DshVrc.PreprocessCopy(source, prepare);
                    else
                    {
                        made = UnityEngine.Object.Instantiate(source);
                        prepare(made);
                    }
                    triangles[label] = Triangles(made, false);
                    return made;
                }
                var rows = new List<(string label, Func<GameObject, GameObject> make)>
                {
                    ("without", source => Make(source, "without", false)),
                    (recipe.name, source => Make(source, recipe.name, true)),
                };
                result["image"] = DshCapture.RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048), rows);
                result["columns"] = views;
                result["rows"] = rows.Select(r => r.label).ToArray();
                result["mode"] = mode;
                if (mode == "bone") result["origin"] = Origin(avatar, recipe);
                if (recipe.fitHead && LastHeadFit != null) result["headFit"] = LastHeadFit;
                result["built"] = request.build;
                result["triangles"] = triangles;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("AccessoryCapture", result);
        }

        private static string Kind(GameObject root)
        {
            var hasHips = root.GetComponentsInChildren<Transform>(true)
                .Any(t => t.name.IndexOf("hips", StringComparison.OrdinalIgnoreCase) >= 0);
            var skinned = root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Any(r => r.bones.Length > 1);
            return hasHips && skinned ? "armature" : "rigid";
        }

        private static string ResolveMode(Request request, GameObject asset)
        {
            if (request.mode == "bone" || request.mode == "armature") return request.mode;
            if (request.mode != "auto") throw new InvalidOperationException("mode must be auto, bone or armature.");
            return Kind(asset) == "armature" ? "armature" : "bone";
        }

        private static bool IsInstanceOf(GameObject candidate, string assetPath) =>
            PrefabUtility.IsOutermostPrefabInstanceRoot(candidate) &&
            PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(candidate) == assetPath;

        /// <summary>Make the avatar (or a copy of it) hold the accessory as the recipe says; returns what had to change.</summary>
        private static List<string> ApplyRecipe(GameObject avatar, Request request, bool inScene, out string mode)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(request.asset)
                ?? throw new InvalidOperationException($"No prefab or model at '{request.asset}'.");
            if (DshAvatarScene.Descriptor(asset) != null)
                throw new InvalidOperationException($"'{request.asset}' is an avatar, not an accessory.");
            mode = ResolveMode(request, asset);
            var changes = new List<string>();
            var holderName = HolderPrefix + request.name;
            var holder = DshVrc.FindHolder(avatar, holderName);
            if (inScene && !string.IsNullOrEmpty(request.menu) && DshVrc.LoadedType("com.vrcfury.api.FuryComponents") == null)
                throw new InvalidOperationException("A menu toggle needs VRCFury. Install it in VCC/ALCOM, or leave 'menu' empty to always wear the accessory.");
            if (holder == null)
            {
                if (inScene) CheckMenu(avatar, request.menu);
                holder = new GameObject(holderName);
                holder.transform.SetParent(avatar.transform, false);
                changes.Add($"added {holderName}");
            }
            var items = holder.transform.Cast<Transform>().Select(t => t.gameObject)
                .Where(child => IsInstanceOf(child, request.asset)).ToArray();
            if (items.Length > 1) throw new InvalidOperationException($"'{holderName}' holds several copies of the asset.");
            GameObject item;
            if (items.Length == 0)
            {
                if (holder.transform.childCount > 0)
                    throw new InvalidOperationException($"'{holderName}' holds other objects. Remove the accessory, then apply the recipe again.");
                // The saved scene keeps a prefab link; render copies get a plain copy, because the SDK build
                // refuses avatars that contain prefab instances.
                item = inScene ? (GameObject)PrefabUtility.InstantiatePrefab(asset, holder.transform)
                    : UnityEngine.Object.Instantiate(asset, holder.transform);
                item.name = asset.name;
                item.transform.localPosition = asset.transform.localPosition;
                item.transform.localRotation = asset.transform.localRotation;
                item.transform.localScale = asset.transform.localScale;
                changes.Add($"placed {request.asset}");
                if (mode == "armature")
                {
                    SetupOutfit(item);
                    changes.Add("merged its armature with Modular Avatar Setup Outfit");
                }
            }
            else item = items[0];

            changes.AddRange(CopyMaterials(item, request));
            changes.AddRange(EnsurePhysBones(item, request));
            if (mode != "bone" && request.follow != "proxy")
                throw new InvalidOperationException("Holding or fixing in the world works for items attached to a bone (mode 'bone').");
            if (mode == "bone") changes.AddRange(PlaceOnBone(avatar, item, asset, request, out _));
            else
            {
                var merge = DshVrc.LoadedType(MergeArmatureType);
                if (merge == null || item.GetComponentsInChildren(merge, true).Length == 0)
                    throw new InvalidOperationException("The accessory has no Modular Avatar Merge Armature. Remove it, then apply again.");
                if (item.GetComponent(DshVrc.LoadedType(BoneProxyType)) != null)
                    throw new InvalidOperationException("The accessory was attached to a bone before. Remove it, then apply again in armature mode.");
            }
            if (inScene) changes.AddRange(EnsureDropToggle(avatar, holder, item, request));
            if (inScene && !string.IsNullOrEmpty(request.menu))
            {
                var clip = HideClip(avatar, holder, request, changes);
                changes.AddRange(EnsureToggle(holder, item, clip, request));
            }
            else
            {
                if (inScene) changes.AddRange(EnsureToggle(holder, item, null, request));
                // Always worn: the hidden objects stay off in the scene (remove turns them back on).
                foreach (var hidden in HiddenObjects(avatar, holder, request))
                {
                    if (!hidden.activeSelf) continue;
                    SetActive(hidden, false);
                    changes.Add($"turned off {AnimationUtility.CalculateTransformPath(hidden.transform, avatar.transform)}");
                }
            }
            return changes;
        }

        /// <summary>
        /// Add a VRC PhysBone on each named bone of the accessory (the root stays put, the bones under it sway) and
        /// set its values. Saved as added components on the scene's instance; the asset is not changed.
        /// </summary>
        private static List<string> EnsurePhysBones(GameObject item, Request request)
        {
            var changes = new List<string>();
            if (request.physBones.Length == 0) return changes;
            var type = DshReflect.Find("VRCPhysBone", "VRC")
                ?? throw new InvalidOperationException("The VRChat SDK PhysBone component is unavailable in this project.");
            var transforms = item.GetComponentsInChildren<Transform>(true);
            foreach (var spec in request.physBones)
            {
                var matches = transforms.Where(t => t.name == spec.root).ToArray();
                if (matches.Length != 1)
                    throw new InvalidOperationException(matches.Length == 0
                        ? $"The accessory has no bone named '{spec.root}' for a PhysBone. Build the model again, or check the name in the build result's sway list."
                        : $"The accessory has several objects named '{spec.root}'.");
                var component = matches[0].GetComponent(type);
                if (component == null)
                {
                    component = matches[0].gameObject.AddComponent(type);
                    changes.Add($"added a PhysBone on {spec.root}");
                }
                foreach (var value in spec.values)
                {
                    var before = DshReflect.Set(component, value.field, value.value);
                    if (before != null) changes.Add($"{spec.root}: PhysBone {value.field} {before} -> {value.value}");
                }
            }
            return changes;
        }

        /// <summary>
        /// Give each renderer the materials of the same-named renderer in another prefab or model (for example the
        /// original outfit, when a fitted FBX from Blender arrives with plain materials). Saved as scene overrides.
        /// </summary>
        private static List<string> CopyMaterials(GameObject item, Request request)
        {
            var changes = new List<string>();
            if (string.IsNullOrEmpty(request.materialsFrom)) return changes;
            var source = AssetDatabase.LoadAssetAtPath<GameObject>(request.materialsFrom)
                ?? throw new InvalidOperationException($"No prefab or model at '{request.materialsFrom}' to take materials from.");
            var byName = new Dictionary<string, Material[]>();
            foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
                if (!byName.ContainsKey(renderer.name)) byName[renderer.name] = renderer.sharedMaterials;
            var matched = 0;
            var broken = new List<string>();
            foreach (var renderer in item.GetComponentsInChildren<Renderer>(true))
            {
                if (!byName.TryGetValue(renderer.name, out var materials) || materials.Length != renderer.sharedMaterials.Length) continue;
                matched++;
                // A prefab imported without its Materials or Textures folder keeps missing references, which render magenta.
                if (materials.Any(m => m == null || m.shader == null || m.shader.name == "Hidden/InternalErrorShader"))
                {
                    broken.Add(renderer.name);
                    continue;
                }
                if (renderer.sharedMaterials.SequenceEqual(materials)) continue;
                renderer.sharedMaterials = materials;
                EditorUtility.SetDirty(renderer);
                if (PrefabUtility.IsPartOfPrefabInstance(renderer)) PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
                changes.Add($"materials of {renderer.name} from {request.materialsFrom}");
            }
            if (matched == 0)
                throw new InvalidOperationException($"No renderer of the accessory has a same-named renderer with as many material slots in '{request.materialsFrom}'.");
            if (broken.Count > 0)
                throw new InvalidOperationException(
                    $"'{request.materialsFrom}' has missing materials or shaders on {string.Join(", ", broken.Take(8))}. " +
                    "Import the whole outfit package (its Materials and Textures folders, and the shader it uses such as lilToon), then retry. " +
                    "If the outfit came as several packages, the materials are often in a separate shared package of the same product.");
            return changes;
        }

        private static string Origin(GameObject avatar, Request request)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(request.asset);
            Enum.TryParse<HumanBodyBones>(request.bone, out var boneId);
            var bone = avatar.GetComponent<Animator>()?.GetBoneTransform(boneId);
            return asset == null || bone == null ? "" : ResolveOrigin(avatar, asset, bone, request.origin);
        }

        private static Vector3 Vector(float[] values) =>
            values != null && values.Length == 3 ? new Vector3(values[0], values[1], values[2]) : Vector3.zero;

        internal static Dictionary<string, object> LastHeadFit;
        private const float HeadLoose = 1.12f;    // the item is this much wider than the head
        private const float BrowHeight = 0.12f;   // its lower edge sits this far (of the head height) above the head's centre
        private const float BackMargin = 0.08f;   // its back edge this far (of the head depth) behind the back of the head

        /// <summary>
        /// Size and seat a generic head item (a cap, beret or hat made at any size): its width becomes HeadLoose
        /// times the width of the avatar's head (the vertices that follow the Head bone), centred left to right,
        /// its back just behind the head and its lower edge a little above the eyes. The item is at the bone with
        /// scale 1 when this is called; returns the scale factor and world position for its root.
        /// </summary>
        private static (float scale, Vector3 position, Dictionary<string, object> report) FitToHead(
            GameObject avatar, GameObject item, Transform headBone)
        {
            var head = HeadBounds(avatar, headBone)
                ?? throw new InvalidOperationException("'scale': 'auto' could not find the avatar's head mesh (vertices on the Head bone). Give a number instead.");
            var space = avatar.transform;
            var itemBounds = BoundsIn(space, item.GetComponentsInChildren<Renderer>(true))
                ?? throw new InvalidOperationException("The item has no mesh to size.");
            if (itemBounds.size.x < 1e-4f) throw new InvalidOperationException("The item has no width to size.");
            var factor = head.size.x * HeadLoose / itemBounds.size.x;
            // The root moves with the scale around itself, so measure where the scaled bounds would be.
            var root = space.InverseTransformPoint(item.transform.position);
            var scaledMin = root + (itemBounds.min - root) * factor;
            var scaledMax = root + (itemBounds.max - root) * factor;
            var target = new Vector3(
                head.center.x - ((scaledMin.x + scaledMax.x) / 2 - root.x),
                head.center.y + head.size.y * BrowHeight - (scaledMin.y - root.y),
                head.min.z - head.size.z * BackMargin - (scaledMin.z - root.z));
            var report = new Dictionary<string, object>
            {
                { "scale", Math.Round(factor, 4) },
                { "headSize", new[] { Math.Round(head.size.x, 3), Math.Round(head.size.y, 3), Math.Round(head.size.z, 3) } },
                { "itemSizeBefore", new[] { Math.Round(itemBounds.size.x, 3), Math.Round(itemBounds.size.y, 3), Math.Round(itemBounds.size.z, 3) } },
            };
            return (factor, space.TransformPoint(target), report);
        }

        /// <summary>Bounds, in the avatar's space, of the avatar's vertices that mostly follow the head bone.</summary>
        private static Bounds? HeadBounds(GameObject avatar, Transform headBone)
        {
            Bounds? found = null;
            foreach (var skinned in avatar.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var mesh = skinned.sharedMesh;
                var index = Array.IndexOf(skinned.bones, headBone);
                if (mesh == null || index < 0 || !mesh.isReadable && mesh.boneWeights.Length == 0) continue;
                var weights = mesh.boneWeights;
                if (weights.Length != mesh.vertexCount) continue;
                var baked = new Mesh();
                skinned.BakeMesh(baked, true);
                var vertices = baked.vertices;
                for (var i = 0; i < vertices.Length; i++)
                {
                    var w = weights[i];
                    var onHead = (w.boneIndex0 == index ? w.weight0 : 0) + (w.boneIndex1 == index ? w.weight1 : 0) +
                                 (w.boneIndex2 == index ? w.weight2 : 0) + (w.boneIndex3 == index ? w.weight3 : 0);
                    if (onHead < 0.5f) continue;
                    var point = avatar.transform.InverseTransformPoint(skinned.transform.TransformPoint(vertices[i]));
                    if (found.HasValue) { var b = found.Value; b.Encapsulate(point); found = b; }
                    else found = new Bounds(point, Vector3.zero);
                }
                UnityEngine.Object.DestroyImmediate(baked);
            }
            return found.HasValue && found.Value.size.x > 0.02f ? found : null;
        }

        private static Bounds? BoundsIn(Transform space, IEnumerable<Renderer> renderers)
        {
            Bounds? found = null;
            foreach (var renderer in renderers)
            {
                var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh : renderer.GetComponent<MeshFilter>()?.sharedMesh;
                if (mesh == null) continue;
                var local = mesh.bounds;
                for (var corner = 0; corner < 8; corner++)
                {
                    var p = local.center + Vector3.Scale(local.extents,
                        new Vector3((corner & 1) == 0 ? -1 : 1, (corner & 2) == 0 ? -1 : 1, (corner & 4) == 0 ? -1 : 1));
                    var point = space.InverseTransformPoint(renderer.transform.TransformPoint(p));
                    if (found.HasValue) { var b = found.Value; b.Encapsulate(point); found = b; }
                    else found = new Bounds(point, Vector3.zero);
                }
            }
            return found;
        }

        /// <summary>Centre of the asset's meshes in the asset's own space (its root at the asset's saved pose).</summary>
        private static Vector3? MeshCentre(GameObject asset)
        {
            var points = new List<Vector3>();
            foreach (var renderer in asset.GetComponentsInChildren<Renderer>(true))
            {
                var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh : renderer.GetComponent<MeshFilter>()?.sharedMesh;
                if (mesh != null) points.Add(renderer.transform.TransformPoint(mesh.bounds.center));
            }
            if (points.Count == 0) return null;
            return points.Aggregate(Vector3.zero, (sum, p) => sum + p) / points.Count;
        }

        private static string ResolveOrigin(GameObject avatar, GameObject asset, Transform bone, string origin)
        {
            if (origin == "avatar" || origin == "bone") return origin;
            if (origin != "auto") throw new InvalidOperationException("origin must be auto, avatar or bone.");
            var centre = MeshCentre(asset);
            return centre.HasValue && Vector3.Distance(avatar.transform.TransformPoint(centre.Value), bone.position) <=
                AvatarSpaceDistance * avatar.transform.lossyScale.y ? "avatar" : "bone";
        }

        /// <summary>
        /// The base pose is the asset's saved pose in the avatar's space (origin "avatar") or its origin moved to the
        /// bone (origin "bone"). The recipe then rotates and scales it around the bone and moves it, in the avatar's
        /// axes (x right, y up, z forward; metres and degrees). Bone Proxy keeps this world pose when it moves the
        /// object under the bone at build time.
        /// </summary>
        private static List<string> PlaceOnBone(GameObject avatar, GameObject item, GameObject asset, Request request, out string origin)
        {
            var changes = new List<string>();
            var animator = avatar.GetComponent<Animator>();
            if (animator == null || !animator.isHuman)
                throw new InvalidOperationException("Bone attachment needs a humanoid avatar (Animator with a humanoid Avatar).");
            if (!Enum.TryParse<HumanBodyBones>(request.bone, out var boneId) || boneId == HumanBodyBones.LastBone)
                throw new InvalidOperationException($"Unknown humanoid bone '{request.bone}'. Use a name from the candidates command.");
            var bone = animator.GetBoneTransform(boneId)
                ?? throw new InvalidOperationException($"The avatar has no {boneId} bone.");
            origin = ResolveOrigin(avatar, asset, bone, request.origin);
            var basis = avatar.transform.rotation;
            var pivot = bone.position;
            var basePosition = origin == "avatar" ? avatar.transform.TransformPoint(asset.transform.localPosition) : pivot;
            var turn = basis * Quaternion.Euler(Vector(request.rotation)) * Quaternion.Inverse(basis);
            var factor = Mathf.Clamp(request.scale, 0.01f, 100f);
            var position = pivot + turn * ((basePosition - pivot) * factor) + basis * Vector(request.position);
            var rotation = turn * basis * asset.transform.localRotation;
            var scale = asset.transform.localScale * factor;
            var t = item.transform;
            if (request.fitHead)
            {
                // Seat the item on the avatar's head first, then apply the recipe's offset, turn and scale on top.
                // It is measured in its base pose and put back, so an item already placed reads as unchanged.
                var (savedPosition, savedRotation, savedScale) = (t.position, t.rotation, t.localScale);
                t.SetPositionAndRotation(pivot, turn * basis * asset.transform.localRotation);
                t.localScale = asset.transform.localScale;
                var fit = FitToHead(avatar, item, bone);
                t.SetPositionAndRotation(savedPosition, savedRotation);
                t.localScale = savedScale;
                LastHeadFit = fit.report;
                var seated = fit.position + basis * Vector(request.position);
                position = pivot + (seated - pivot) * factor;
                scale = asset.transform.localScale * fit.scale * factor;
            }
            if ((t.position - position).sqrMagnitude > Tolerance * Tolerance ||
                Quaternion.Angle(t.rotation, rotation) > 0.01f || (t.localScale - scale).sqrMagnitude > Tolerance * Tolerance)
            {
                t.SetPositionAndRotation(position, rotation);
                t.localScale = scale;
                changes.Add($"placed on {boneId} (origin {origin}) offset {Vector(request.position)} rotation {Vector(request.rotation)} scale {factor}");
            }

            if (request.follow != "proxy")
            {
                if (DshVrc.LoadedType(BoneProxyType) is Type existing && item.GetComponent(existing) != null)
                    throw new InvalidOperationException("The accessory follows its bone through Bone Proxy from an earlier apply. Remove it, then apply again.");
                if (changes.Count > 0) PrefabUtility.RecordPrefabInstancePropertyModifications(t);
                changes.AddRange(request.follow == "world" ? EnsureWorldFixed(item) : EnsureHoldConstraint(item, bone));
                return changes;
            }
            var proxyType = DshVrc.LoadedType(BoneProxyType)
                ?? throw new InvalidOperationException("Modular Avatar is not installed. Add it in VCC/ALCOM to attach accessories.");
            var proxy = item.GetComponent(proxyType);
            if (proxy == null)
            {
                proxy = item.AddComponent(proxyType);
                changes.Add("added MA Bone Proxy");
            }
            var keepWorldPose = Enum.Parse(proxyType.GetField("attachmentMode").FieldType, "AsChildKeepWorldPose");
            void Set(string field, object value)
            {
                var info = proxyType.GetField(field);
                if (Equals(info.GetValue(proxy), value)) return;
                info.SetValue(proxy, value);
                changes.Add($"Bone Proxy {field} = {value}");
            }
            Set("boneReference", boneId);
            Set("subPath", "");
            Set("attachmentMode", keepWorldPose);
            Set("matchScale", false);
            if (changes.Count > 0)
            {
                EditorUtility.SetDirty(proxy);
                PrefabUtility.RecordPrefabInstancePropertyModifications(proxy);
                PrefabUtility.RecordPrefabInstancePropertyModifications(t);
            }
            return changes;
        }

        private static Type ParentConstraintType => DshReflect.Find("VRCParentConstraint", "VRC")
            ?? throw new InvalidOperationException("VRChat constraints are unavailable. Update the VRChat SDK to 3.7 or later in VCC/ALCOM.");

        /// <summary>
        /// A held item stays under the accessory object and follows the hand through a VRC Parent Constraint whose
        /// offsets keep its current pose. Its path never changes at build time, so the drop animation can find it.
        /// </summary>
        private static List<string> EnsureHoldConstraint(GameObject item, Transform bone)
        {
            var changes = new List<string>();
            var type = ParentConstraintType;
            var constraints = item.GetComponents(type);
            if (constraints.Length > 1) throw new InvalidOperationException("The accessory has several parent constraints.");
            var constraint = constraints.FirstOrDefault();
            if (constraint != null)
            {
                var sources = ConstraintSources(constraint);
                if (sources.Count != 1 || sources[0] != bone)
                    throw new InvalidOperationException("The accessory's parent constraint follows another bone. Remove it, then apply again.");
                return changes;
            }
            constraint = item.AddComponent(type);
            var sourceType = DshVrc.LoadedType("VRC.Dynamics.VRCConstraintSource")
                ?? throw new InvalidOperationException("The VRChat SDK constraint source type is unavailable.");
            var source = Activator.CreateInstance(sourceType);
            void SetSource(string name, object value) =>
                (sourceType.GetField(name) ?? throw new InvalidOperationException($"VRCConstraintSource has no {name}."))
                    .SetValue(source, value);
            SetSource("SourceTransform", bone);
            SetSource("Weight", 1f);
            var sourcesField = DshReflect.Field(type, "Sources");
            var list = sourcesField.GetValue(constraint);
            var add = list.GetType().GetMethod("Add", new[] { sourceType })
                ?? throw new InvalidOperationException("The VRChat SDK constraint source list cannot be added to.");
            add.Invoke(list, new[] { source });
            sourcesField.SetValue(constraint, list);
            // ActivateConstraint bakes the offsets from the current pose, locks and turns the constraint on.
            var activate = type.GetMethod("ActivateConstraint", Type.EmptyTypes)
                ?? throw new InvalidOperationException("The VRChat SDK constraint has no ActivateConstraint.");
            activate.Invoke(constraint, null);
            DshReflect.Field(type, "FreezeToWorld").SetValue(constraint, false);
            DshReflect.Dirty(constraint);
            changes.Add($"added VRC Parent Constraint following {bone.name}");
            return changes;
        }

        private static List<Transform> ConstraintSources(Component constraint)
        {
            var found = new List<Transform>();
            if (!(DshReflect.Field(constraint.GetType(), "Sources").GetValue(constraint) is IEnumerable sources)) return found;
            foreach (var source in sources)
                found.Add(source?.GetType().GetField("SourceTransform")?.GetValue(source) as Transform);
            return found;
        }

        private static List<string> EnsureWorldFixed(GameObject item)
        {
            var type = DshVrc.LoadedType(WorldFixedType)
                ?? throw new InvalidOperationException("This Modular Avatar has no World Fixed Object. Update Modular Avatar in VCC/ALCOM.");
            if (item.GetComponent(type) != null) return new List<string>();
            item.AddComponent(type);
            return new List<string> { "added MA World Fixed Object" };
        }

        /// <summary>
        /// "Drop": a second menu toggle on a child object that plays a clip setting the hold constraint's Freeze To
        /// World, so the item stays where it is in the world until the toggle is turned off again.
        /// </summary>
        private static List<string> EnsureDropToggle(GameObject avatar, GameObject holder, GameObject item, Request request)
        {
            var changes = new List<string>();
            var existing = holder.transform.Cast<Transform>().Where(t => t.name == DropHolder).ToArray();
            if (string.IsNullOrEmpty(request.dropMenu))
            {
                if (existing.Length > 0)
                    throw new InvalidOperationException("The accessory has a drop toggle but the recipe has none. Remove it, then apply again.");
                return changes;
            }
            if (request.follow != "constraint")
                throw new InvalidOperationException("A drop toggle needs a held item (hold).");
            var path = AnimationUtility.CalculateTransformPath(item.transform, avatar.transform);
            var clipPath = $"{request.folder}/{request.name}_drop.anim";
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            var binding = EditorCurveBinding.FloatCurve(path, ParentConstraintType, "FreezeToWorld");
            var current = clip == null ? null : AnimationUtility.GetEditorCurve(clip, binding);
            if (clip == null || current == null || AnimationUtility.GetCurveBindings(clip).Length != 1)
            {
                if (request.folder != "Assets/DSH/Accessories/" + request.name || !AssetDatabase.IsValidFolder(request.folder))
                    throw new InvalidOperationException("The recipe folder Assets/DSH/Accessories/<name> is missing.");
                if (clip == null)
                {
                    clip = new AnimationClip { name = request.name + "_drop" };
                    AssetDatabase.CreateAsset(clip, clipPath);
                }
                clip.ClearCurves();
                AnimationUtility.SetEditorCurve(clip, binding, AnimationCurve.Constant(0, 0, 1));
                EditorUtility.SetDirty(clip);
                AssetDatabase.SaveAssets();
                changes.Add($"drop clip {clipPath}");
            }
            if (existing.Length == 0)
            {
                if (DshVrc.LoadedType("com.vrcfury.api.FuryComponents") == null)
                    throw new InvalidOperationException("A drop toggle needs VRCFury. Install it in VCC/ALCOM, or leave out 'drop'.");
                CheckMenu(avatar, request.dropMenu);
                var dropObject = new GameObject(DropHolder);
                dropObject.transform.SetParent(holder.transform, false);
                var toggle = DshVrc.CreateFuryToggle(dropObject);
                DshVrc.CallPublic(toggle, "SetMenuPath", request.dropMenu);
                DshVrc.CallPublic(DshVrc.CallPublic(toggle, "GetActions"), "AddAnimationClip", clip);
                changes.Add($"added drop toggle {request.dropMenu}");
                return changes;
            }
            var data = existing.Length == 1
                ? existing[0].GetComponents<Component>().Where(DshVrc.IsFury).Select(DshVrc.ToggleData).FirstOrDefault(d => d != null)
                : null;
            if (data == null || data.FindPropertyRelative("name")?.stringValue != request.dropMenu)
                throw new InvalidOperationException("The accessory's drop toggle differs from the recipe. Remove the accessory, then apply again.");
            return changes;
        }

        private static void SetupOutfit(GameObject item)
        {
            if (Kind(item) != "armature")
                throw new InvalidOperationException("The asset has no skinned armature with a Hips bone. Attach it with mode 'bone' instead.");
            var setup = DshVrc.LoadedType(SetupOutfitType)?.GetMethod("SetupOutfitUI", BindingFlags.Public | BindingFlags.Static,
                    null, new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("Modular Avatar Setup Outfit is unavailable. Install or update Modular Avatar in VCC/ALCOM.");
            setup.Invoke(null, new object[] { item });
            var merge = DshVrc.LoadedType(MergeArmatureType);
            if (merge == null || item.GetComponentsInChildren(merge, true).Length == 0)
                throw new InvalidOperationException("Modular Avatar could not match the accessory's armature to the avatar. " +
                    "Check that its bone names follow the avatar (Hips, Spine, ...), or attach it with mode 'bone'.");
        }

        private static void CheckMenu(GameObject avatar, string menu)
        {
            if (string.IsNullOrEmpty(menu)) return;
            foreach (var component in avatar.GetComponentsInChildren<Component>(true).Where(DshVrc.IsFury))
                if (DshVrc.ToggleData(component)?.FindPropertyRelative("name")?.stringValue == menu)
                    throw new InvalidOperationException($"An existing VRCFury toggle on '{DshAvatarScene.HierarchyPath(component.transform)}' uses the menu '{menu}'.");
        }

        private static void SetActive(GameObject target, bool active)
        {
            target.SetActive(active);
            EditorUtility.SetDirty(target);
            if (PrefabUtility.IsPartOfPrefabInstance(target)) PrefabUtility.RecordPrefabInstancePropertyModifications(target);
        }

        /// <summary>Avatar objects the recipe hides while the accessory is on (for example the original hair).</summary>
        private static List<GameObject> HiddenObjects(GameObject avatar, GameObject holder, Request request)
        {
            var found = new List<GameObject>();
            foreach (var path in request.hide ?? Array.Empty<string>())
            {
                var target = avatar.transform.Find(path)
                    ?? throw new InvalidOperationException($"No object at '{path}' under the avatar to hide.");
                if (target.IsChildOf(holder.transform) || holder.transform.IsChildOf(target))
                    throw new InvalidOperationException($"'{path}' contains or is part of the accessory; it cannot be hidden.");
                found.Add(target.gameObject);
            }
            return found;
        }

        /// <summary>
        /// The VRCFury public API can only turn objects on, so hiding is an animation clip in the recipe folder that
        /// sets the hidden objects inactive; the toggle plays it while the accessory is on.
        /// </summary>
        private static AnimationClip HideClip(GameObject avatar, GameObject holder, Request request, List<string> changes)
        {
            var hidden = HiddenObjects(avatar, holder, request);
            if (hidden.Count == 0) return null;
            if (request.folder != "Assets/DSH/Accessories/" + request.name || !AssetDatabase.IsValidFolder(request.folder))
                throw new InvalidOperationException("The recipe folder Assets/DSH/Accessories/<name> is missing.");
            var clipPath = $"{request.folder}/{request.name}_hide.anim";
            var wanted = hidden.Select(o => AnimationUtility.CalculateTransformPath(o.transform, avatar.transform))
                .OrderBy(p => p, StringComparer.Ordinal).ToArray();
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            var current = clip == null ? Array.Empty<string>() : AnimationUtility.GetCurveBindings(clip)
                .Where(b => b.type == typeof(GameObject) && b.propertyName == "m_IsActive")
                .Where(b => AnimationUtility.GetEditorCurve(clip, b).keys.All(k => Mathf.Approximately(k.value, 0)))
                .Select(b => b.path).OrderBy(p => p, StringComparer.Ordinal).ToArray();
            if (clip != null && current.SequenceEqual(wanted) && AnimationUtility.GetCurveBindings(clip).Length == wanted.Length)
                return clip;
            if (clip == null)
            {
                clip = new AnimationClip { name = request.name + "_hide" };
                AssetDatabase.CreateAsset(clip, clipPath);
            }
            clip.ClearCurves();
            foreach (var path in wanted)
                AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(path, typeof(GameObject), "m_IsActive"),
                    AnimationCurve.Constant(0, 0, 0));
            EditorUtility.SetDirty(clip);
            AssetDatabase.SaveAssets();
            changes.Add($"hide clip {clipPath}: {string.Join(", ", wanted)}");
            return clip;
        }

        private static bool References(SerializedProperty property, UnityEngine.Object target)
        {
            var end = property.GetEndProperty();
            var iterator = property.Copy();
            for (var enter = true; iterator.Next(enter) && !SerializedProperty.EqualContents(iterator, end); enter = true)
                if (iterator.propertyType == SerializedPropertyType.ObjectReference && iterator.objectReferenceValue == target)
                    return true;
            return false;
        }

        private static List<string> EnsureToggle(GameObject holder, GameObject item, AnimationClip clip, Request request)
        {
            var changes = new List<string>();
            var components = holder.GetComponents<Component>().Where(DshVrc.IsFury).ToArray();
            if (string.IsNullOrEmpty(request.menu))
            {
                if (components.Length > 0)
                    throw new InvalidOperationException("The accessory has a menu toggle but the recipe has no menu. Remove it, then apply again.");
                return changes;
            }
            if (components.Length == 0)
            {
                var toggle = DshVrc.CreateFuryToggle(holder);
                DshVrc.CallPublic(toggle, "SetMenuPath", request.menu);
                DshVrc.CallPublic(toggle, "SetSaved");
                if (request.defaultOn) DshVrc.CallPublic(toggle, "SetDefaultOn");
                var actions = DshVrc.CallPublic(toggle, "GetActions");
                DshVrc.CallPublic(actions, "AddTurnOn", item);
                if (clip != null) DshVrc.CallPublic(actions, "AddAnimationClip", clip);
                changes.Add($"added menu toggle {request.menu}");
                return changes;
            }
            var data = components.Length == 1 ? DshVrc.ToggleData(components[0]) : null;
            var list = data?.FindPropertyRelative("state.actions");
            var expected = clip == null ? 1 : 2;
            var turnOn = list != null && list.arraySize == expected ? list.GetArrayElementAtIndex(0) : null;
            var play = clip != null && turnOn != null ? list.GetArrayElementAtIndex(1) : null;
            if (data == null || data.FindPropertyRelative("name")?.stringValue != request.menu ||
                data.FindPropertyRelative("defaultOn")?.boolValue != request.defaultOn ||
                turnOn?.FindPropertyRelative("obj")?.objectReferenceValue != item ||
                (clip != null && (play == null || !play.managedReferenceFullTypename.EndsWith("AnimationClipAction", StringComparison.Ordinal) ||
                                  !References(play, clip))))
                throw new InvalidOperationException("The accessory's menu toggle differs from the recipe. Remove the accessory, then apply again.");
            return changes;
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Request request, string mode)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                var holder = DshVrc.FindHolder(avatar, HolderPrefix + request.name);
                var item = holder.transform.Cast<Transform>().First(child => IsInstanceOf(child.gameObject, request.asset));
                var indices = new Stack<int>();
                for (var node = item; node != avatar.transform; node = node.parent) indices.Push(node.GetSiblingIndex());
                Transform copyItem = null;
                result["trianglesInScene"] = Triangles(avatar, false);
                copy = DshVrc.PreprocessCopy(avatar, clone =>
                {
                    copyItem = clone.transform;
                    foreach (var index in indices) copyItem = copyItem.GetChild(index);
                });
                result["trianglesAfterBuild"] = Triangles(copy, false);
                if (request.physBones.Length > 0)
                {
                    // The added PhysBones must survive the build (an optimiser may merge them, not drop them).
                    var physBoneType = DshReflect.Find("VRCPhysBone", "VRC");
                    var built = physBoneType == null ? 0 : copy.GetComponentsInChildren(physBoneType, true)
                        .Count(c => request.physBones.Any(spec => c.transform.name == spec.root));
                    result["physBones"] = $"{built}/{request.physBones.Length}";
                }
                if (!string.IsNullOrEmpty(request.menu))
                {
                    var (_, parameter, location) = DshVrc.GeneratedToggle(DshAvatarScene.Descriptor(copy), request.menu);
                    result["menuLocation"] = location;
                    result["parameter"] = parameter;
                    // Build plugins may move the item (World Fixed Object); the toggle must still reach it.
                    var shown = DshVrc.FxClips(DshAvatarScene.Descriptor(copy), parameter)
                        .SelectMany(AnimationUtility.GetCurveBindings)
                        .Where(b => b.type == typeof(GameObject) && b.propertyName == "m_IsActive").Select(b => b.path).Distinct().ToArray();
                    var missing = shown.Where(p => copy.transform.Find(p) == null).ToArray();
                    result["toggleAnimation"] = $"{shown.Length - missing.Length}/{shown.Length}";
                    if (missing.Length > 0)
                        throw new InvalidOperationException("After the build the menu toggle animates objects that are not there: " + string.Join(", ", missing.Take(3)));
                }
                if (copyItem == null || !copyItem.IsChildOf(copy.transform))
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "A build plugin removed or moved the accessory object. Check it in Build & Test.";
                    return result;
                }
                if (!string.IsNullOrEmpty(request.dropMenu))
                {
                    var (_, dropParameter, dropLocation) = DshVrc.GeneratedToggle(DshAvatarScene.Descriptor(copy), request.dropMenu);
                    result["dropMenuLocation"] = dropLocation;
                    result["dropParameter"] = dropParameter;
                    // The built drop animation must reach the constraint on the item.
                    var bindings = DshVrc.FxClips(DshAvatarScene.Descriptor(copy), dropParameter)
                        .SelectMany(AnimationUtility.GetCurveBindings).Where(b => b.propertyName == "FreezeToWorld").ToArray();
                    var reaches = bindings.Count(b => copy.transform.Find(b.path)?.GetComponent(ParentConstraintType) != null);
                    result["dropAnimation"] = $"{reaches}/{bindings.Length}";
                    if (reaches == 0)
                        throw new InvalidOperationException("After the build the drop animation does not reach the accessory's constraint.");
                }
                if (mode == "bone" && request.follow == "constraint")
                {
                    Enum.TryParse<HumanBodyBones>(request.bone, out var holdId);
                    var hand = copy.GetComponent<Animator>()?.GetBoneTransform(holdId);
                    var constraint = copyItem.GetComponent(ParentConstraintType);
                    var sources = constraint == null ? new List<Transform>() : ConstraintSources(constraint);
                    result["follows"] = sources.Count == 1 && sources[0] != null ? sources[0].name : null;
                    if (hand == null || sources.Count != 1 || sources[0] != hand)
                        throw new InvalidOperationException($"After the build the accessory's constraint does not follow the {holdId} bone.");
                }
                else if (mode == "bone" && request.follow == "world")
                {
                    result["parentAfterBuild"] = copyItem.parent == null ? "" : copyItem.parent.name;
                }
                else if (mode == "bone")
                {
                    Enum.TryParse<HumanBodyBones>(request.bone, out var boneId);
                    var bone = copy.GetComponent<Animator>()?.GetBoneTransform(boneId);
                    result["attachedTo"] = bone == null ? null : bone.name;
                    if (bone == null || !copyItem.IsChildOf(bone))
                        throw new InvalidOperationException($"After the build the accessory is not under the {boneId} bone.");
                }
                else
                {
                    var renderers = copyItem.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                    var merged = renderers.Count(r => r.bones.Length > 0 && r.bones.All(b => b == null || !b.IsChildOf(copyItem)));
                    result["mergedRenderers"] = $"{merged}/{renderers.Length}";
                    if (renderers.Length > 0 && merged == 0)
                        throw new InvalidOperationException("After the build no accessory mesh follows the avatar's bones.");
                }
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

        private static int Triangles(GameObject root, bool includeInactive)
        {
            var total = 0;
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(includeInactive).Where(r => includeInactive || r.enabled))
            {
                var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh
                    : renderer.GetComponent<MeshFilter>()?.sharedMesh;
                if (mesh != null) total += (int)(Enumerable.Range(0, mesh.subMeshCount).Sum(i => (long)mesh.GetIndexCount(i)) / 3);
            }
            return total;
        }
    }
}
