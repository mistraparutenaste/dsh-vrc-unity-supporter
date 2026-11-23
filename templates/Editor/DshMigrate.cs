using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Read-only views used to carry DSH changes over to a new version of an avatar: what the avatar holds
    /// (paths, blendshapes, humanoid bones, PhysBones), and the prefab overrides on it that were made by hand.
    /// Large lists go to describe.json / overrides.json beside the result.
    /// </summary>
    public static class DshMigrate
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
        }

        public static void Describe()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                var root = avatar.transform;
                result["avatar"] = DshAvatarScene.Describe(root);
                var animator = avatar.GetComponent<Animator>();
                var bones = animator != null && animator.isHuman
                    ? Enum.GetValues(typeof(HumanBodyBones)).Cast<HumanBodyBones>()
                        .Where(b => b != HumanBodyBones.LastBone && animator.GetBoneTransform(b) != null)
                        .ToDictionary(b => b.ToString(), b => (object)DshReflect.PathIn(animator.GetBoneTransform(b), root))
                    : new Dictionary<string, object>();
                var descriptor = DshAvatarScene.Descriptor(avatar);
                var face = descriptor?.GetType().GetField("VisemeSkinnedMesh")?.GetValue(descriptor) as SkinnedMeshRenderer;
                var physBone = DshReflect.Find("VRCPhysBone", "VRC");
                var description = new Dictionary<string, object>
                {
                    { "paths", root.GetComponentsInChildren<Transform>(true).Where(t => t != root).Select(t => (object)DshReflect.PathIn(t, root)).ToArray() },
                    { "humanoidBones", bones },
                    { "face", face == null ? "" : DshReflect.PathIn(face.transform, root) },
                    { "renderers", root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Where(r => r.sharedMesh != null)
                        .GroupBy(r => DshReflect.PathIn(r.transform, root)).Select(g => g.First())
                        .ToDictionary(r => DshReflect.PathIn(r.transform, root),
                            r => (object)Enumerable.Range(0, r.sharedMesh.blendShapeCount).Select(i => (object)r.sharedMesh.GetBlendShapeName(i)).ToArray()) },
                    // Materials the avatar's renderers use, with their textures, for color variants.
                    { "materials", root.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials)
                        .Where(m => m != null && AssetDatabase.GetAssetPath(m).Length > 0).Distinct()
                        .GroupBy(m => AssetDatabase.GetAssetPath(m))  // materials inside one FBX share its path
                        .ToDictionary(g => g.Key, g => (object)g.SelectMany(DshAvatarScene.Textures)
                            .Select(t => AssetDatabase.GetAssetPath(t.texture)).Where(p => p.Length > 0).Distinct().Cast<object>().ToArray()) },
                    { "physBones", physBone == null ? Array.Empty<object>() : avatar.GetComponentsInChildren(physBone, true)
                        .Select(c => (object)new Dictionary<string, object>
                        {
                            { "target", DshReflect.PathIn(c.transform, root) },
                            { "root", DshReflect.PathIn(physBone.GetField("rootTransform")?.GetValue(c) as Transform ?? c.transform, root) },
                        }).ToArray() },
                };
                var file = Path.Combine(DshAvatarScene.RunDirectory, "describe.json");
                File.WriteAllText(file, MiniJson.Serialize(description));
                result["describe"] = file;
                result["counts"] = new Dictionary<string, object>
                {
                    { "paths", ((object[])description["paths"]).Length }, { "humanoidBones", bones.Count },
                    { "renderers", ((Dictionary<string, object>)description["renderers"]).Count },
                };
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("MigrateDescribe", result);
        }

        /// <summary>
        /// Prefab overrides on the avatar instance: changed values (blendshape weights by name), added objects and
        /// components, and removed components. The Python side drops the ones DSH records as its own.
        /// </summary>
        public static void Overrides()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                var root = avatar.transform;
                result["avatar"] = DshAvatarScene.Describe(root);
                if (!PrefabUtility.IsPartOfPrefabInstance(avatar))
                {
                    result["prefab"] = null;
                    result["note"] = "The avatar is not a prefab instance, so every part of it was made in the scene.";
                    result["ok"] = true;
                    DshAvatarScene.Finish("MigrateOverrides", result);
                    return;
                }
                var instanceRoot = PrefabUtility.GetOutermostPrefabInstanceRoot(avatar);
                result["prefab"] = PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(instanceRoot);
                var values = new List<object>();
                // Each modification names the prefab's object; find the scene object it belongs to.
                var bySource = new Dictionary<UnityEngine.Object, UnityEngine.Object>();
                foreach (var t in instanceRoot.GetComponentsInChildren<Transform>(true))
                {
                    foreach (var o in t.GetComponents<Component>().Cast<UnityEngine.Object>().Append(t.gameObject))
                    {
                        if (o == null) continue;
                        var source = PrefabUtility.GetCorrespondingObjectFromSource(o);
                        if (source != null && !bySource.ContainsKey(source)) bySource[source] = o;
                    }
                }
                foreach (var modification in PrefabUtility.GetPropertyModifications(instanceRoot) ?? Array.Empty<PropertyModification>())
                {
                    if (modification.target == null || !bySource.TryGetValue(modification.target, out var instance)) continue;
                    var transform = instance is Component c ? c.transform : instance is GameObject g ? g.transform : null;
                    if (transform == null || !transform.IsChildOf(root) && transform != root) continue;
                    var property = modification.propertyPath;
                    if (instance is SkinnedMeshRenderer smr && property.StartsWith("m_BlendShapeWeights.Array.data[", StringComparison.Ordinal) &&
                        int.TryParse(property.Substring(31).TrimEnd(']'), out var index) && smr.sharedMesh != null && index < smr.sharedMesh.blendShapeCount)
                        property = "blendShape." + smr.sharedMesh.GetBlendShapeName(index);
                    if (Ignored(instance, property)) continue;
                    values.Add(new Dictionary<string, object>
                    {
                        { "path", DshReflect.PathIn(transform, root) }, { "type", instance.GetType().Name },
                        { "property", property },
                        { "value", modification.objectReference != null ? AssetDatabase.GetAssetPath(modification.objectReference) is string p && p.Length > 0 ? p : modification.objectReference.name : modification.value },
                    });
                }
                result["values"] = values;
                result["addedObjects"] = PrefabUtility.GetAddedGameObjects(instanceRoot)
                    .Where(a => a.instanceGameObject.transform.IsChildOf(root))
                    .Select(a => (object)DshReflect.PathIn(a.instanceGameObject.transform, root)).ToArray();
                result["addedComponents"] = PrefabUtility.GetAddedComponents(instanceRoot)
                    .Where(a => a.instanceComponent != null && a.instanceComponent.transform.IsChildOf(root))
                    .Select(a => (object)new Dictionary<string, object>
                    {
                        { "path", DshReflect.PathIn(a.instanceComponent.transform, root) }, { "type", a.instanceComponent.GetType().Name },
                    }).ToArray();
                result["removedComponents"] = PrefabUtility.GetRemovedComponents(instanceRoot)
                    .Where(r => r.containingInstanceGameObject != null && r.containingInstanceGameObject.transform.IsChildOf(root))
                    .Select(r => (object)new Dictionary<string, object>
                    {
                        { "path", DshReflect.PathIn(r.containingInstanceGameObject.transform, root) },
                        { "type", r.assetComponent == null ? "" : r.assetComponent.GetType().Name },
                    }).ToArray();
                var file = Path.Combine(DshAvatarScene.RunDirectory, "overrides.json");
                File.WriteAllText(file, MiniJson.Serialize(new Dictionary<string, object>
                {
                    { "values", values }, { "addedObjects", result["addedObjects"] },
                    { "addedComponents", result["addedComponents"] }, { "removedComponents", result["removedComponents"] },
                }));
                result.Remove("values");
                result["overrides"] = file;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("MigrateOverrides", result);
        }

        /// <summary>Overrides every prefab instance carries (its name and place in the scene), not changes to the avatar.</summary>
        private static bool Ignored(UnityEngine.Object instance, string property)
        {
            if (instance is GameObject && property == "m_Name") return true;
            if (instance is Transform t && t.parent == null) return true;  // where the avatar stands in the scene
            return property == "m_RootOrder";
        }
    }
}
