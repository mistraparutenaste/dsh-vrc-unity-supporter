using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Editor
{
    public static class DshTextureVariant
    {
        [Serializable]
        private sealed class Swap
        {
            public string from = "";
            public string to = "";
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string filter = "";
            public string variant = "";
            public string folder = "";
            public string menu = "";
            public string exclusiveTag = "";
            public bool defaultOn = false;
            public bool verifySdk = false;
            public Swap[] swaps = Array.Empty<Swap>();
        }

        private const int MaxSlots = 200;

        /// <summary>Read-only: renderer slots, shaders and textures of one avatar in a saved scene.</summary>
        public static void Materials()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var filter = request.filter ?? "";
                var slots = new List<Dictionary<string, object>>();
                var textures = new Dictionary<string, Dictionary<string, object>>();
                foreach (var renderer in avatar.GetComponentsInChildren<Renderer>(true))
                {
                    var rendererPath = AnimationUtility.CalculateTransformPath(renderer.transform, avatar.transform);
                    var materials = renderer.sharedMaterials;
                    for (var slot = 0; slot < materials.Length; slot++)
                    {
                        var material = materials[slot];
                        if (material == null) continue;
                        var materialPath = AssetDatabase.GetAssetPath(material);
                        if (filter.Length > 0 && rendererPath.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0 &&
                            material.name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                        var used = DshAvatarScene.Textures(material)
                            .Select(t => (t.property, path: AssetDatabase.GetAssetPath(t.texture), t.texture))
                            .Where(t => t.path.StartsWith("Assets/", StringComparison.Ordinal)).ToArray();
                        slots.Add(new Dictionary<string, object>
                        {
                            { "renderer", rendererPath }, { "slot", slot }, { "material", materialPath },
                            { "shader", material.shader != null ? material.shader.name : "" },
                            { "family", DshAvatarScene.ShaderFamily(material.shader) },
                            { "locked", DshAvatarScene.IsLocked(material.shader) },
                            { "mainTexture", used.Where(t => t.property == "_MainTex").Select(t => t.path).FirstOrDefault() ?? "" },
                            { "active", renderer.gameObject.activeInHierarchy },
                        });
                        foreach (var (property, path, texture) in used)
                        {
                            if (!textures.TryGetValue(path, out var entry))
                                textures[path] = entry = new Dictionary<string, object>
                                {
                                    { "path", path }, { "width", texture.width }, { "height", texture.height },
                                    { "properties", new List<string>() }, { "materials", new List<string>() }
                                };
                            var properties = (List<string>)entry["properties"];
                            var owners = (List<string>)entry["materials"];
                            if (!properties.Contains(property)) properties.Add(property);
                            if (!owners.Contains(materialPath)) owners.Add(materialPath);
                        }
                    }
                }
                result["slotCount"] = slots.Count;
                result["truncated"] = slots.Count > MaxSlots;
                result["slots"] = slots.Take(MaxSlots).ToArray();
                // Main textures first: they are the ones a color variant usually replaces.
                result["textures"] = textures.Values
                    .OrderByDescending(t => ((List<string>)t["properties"]).Contains("_MainTex"))
                    .ThenBy(t => (string)t["path"], StringComparer.Ordinal).Take(MaxSlots).ToArray();
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("TextureMaterials", result);
        }

        /// <summary>Copy the materials that use the original textures, and switch to them from a menu toggle.</summary>
        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                if (string.IsNullOrWhiteSpace(request.menu) || request.menu.Split('/').Any(string.IsNullOrWhiteSpace))
                    throw new InvalidOperationException("Specify a menu name and nonempty submenu names.");
                if (string.IsNullOrEmpty(request.variant) || !request.folder.StartsWith("Assets/DSH/Variants/", StringComparison.Ordinal) ||
                    request.folder != "Assets/DSH/Variants/" + request.variant || request.swaps.Length == 0)
                    throw new InvalidOperationException("The request does not describe a variant under Assets/DSH/Variants.");
                foreach (var swap in request.swaps)
                    if (!swap.to.StartsWith(request.folder + "/", StringComparison.Ordinal))
                        throw new InvalidOperationException($"Variant textures must be inside {request.folder}.");

                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["avatar"] = request.avatar;
                result["menu"] = request.menu;
                result["variant"] = request.variant;

                foreach (var swap in request.swaps) CopyImportSettings(swap.from, swap.to);
                var swaps = DshAvatarScene.LoadSwaps(request.swaps.Select(s => (s.from, s.to)));
                var (clip, materials, bindings) = BuildVariant(avatar, request, swaps);
                result["materials"] = materials;
                result["bindings"] = bindings;
                result["clip"] = AssetDatabase.GetAssetPath(clip);

                var holderName = "DSH Color Variant " + request.variant;
                result["holder"] = holderName;
                var holder = DshVrc.FindHolder(avatar, holderName);
                if (holder == null)
                {
                    CheckExistingMenus(avatar, request.menu);
                    holder = new GameObject(holderName);
                    holder.transform.SetParent(avatar.transform, false);
                    CreateToggle(holder, clip, request);
                    VerifyToggle(holder, clip, request);
                    DshAvatarScene.RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Added {request.menu} for color variant {request.variant}");

                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                    holder = DshVrc.FindHolder(avatar, holderName);
                }
                VerifyToggle(holder, clip, request);
                AssetDatabase.SaveAssets();
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, request, materials) :
                    new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("TextureVariant", result);
        }

        private static void CopyImportSettings(string from, string to)
        {
            AssetDatabase.ImportAsset(to, ImportAssetOptions.ForceSynchronousImport);
            var source = AssetImporter.GetAtPath(from) as TextureImporter;
            var target = AssetImporter.GetAtPath(to) as TextureImporter
                ?? throw new InvalidOperationException($"Unity did not import {to} as a texture.");
            if (source == null) return;
            var settings = new TextureImporterSettings();
            source.ReadTextureSettings(settings);
            target.SetTextureSettings(settings);
            target.maxTextureSize = source.maxTextureSize;
            target.textureCompression = source.textureCompression;
            target.crunchedCompression = source.crunchedCompression;
            target.compressionQuality = source.compressionQuality;
            foreach (var platform in new[] { "Standalone", "Android", "iPhone" })
            {
                var settingsForPlatform = source.GetPlatformTextureSettings(platform);
                if (settingsForPlatform.overridden) target.SetPlatformTextureSettings(settingsForPlatform);
            }
            target.SaveAndReimport();
        }

        private static (AnimationClip clip, List<Dictionary<string, object>> materials, int bindings) BuildVariant(
            GameObject avatar, Request request, Dictionary<Texture, Texture> swaps)
        {
            var copies = new Dictionary<Material, Material>();
            var used = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var report = new List<Dictionary<string, object>>();
            var curves = new List<(EditorCurveBinding binding, Material material)>();
            foreach (var renderer in avatar.GetComponentsInChildren<Renderer>(true))
            {
                var materials = renderer.sharedMaterials;
                for (var slot = 0; slot < materials.Length; slot++)
                {
                    var original = materials[slot];
                    if (original == null || !DshAvatarScene.Textures(original).Any(t => swaps.ContainsKey(t.texture))) continue;
                    if (DshAvatarScene.IsLocked(original.shader))
                        throw new InvalidOperationException($"{original.name} uses a locked Poiyomi shader. Unlock it in Unity, then retry.");
                    if (!copies.TryGetValue(original, out var copy))
                    {
                        var name = original.name;
                        for (var n = 2; !used.Add(name); n++) name = $"{original.name}_{n}";
                        copies[original] = copy = SaveCopy(original, $"{request.folder}/{name}.mat", swaps);
                        report.Add(new Dictionary<string, object>
                        {
                            { "from", AssetDatabase.GetAssetPath(original) }, { "to", AssetDatabase.GetAssetPath(copy) },
                            { "family", DshAvatarScene.ShaderFamily(original.shader) }
                        });
                    }
                    var path = AnimationUtility.CalculateTransformPath(renderer.transform, avatar.transform);
                    curves.Add((EditorCurveBinding.PPtrCurve(path, renderer.GetType(), $"m_Materials.Array.data[{slot}]"), copy));
                }
            }
            if (curves.Count == 0)
                throw new InvalidOperationException("No material on this avatar uses the original textures of the recipe.");

            var clipPath = $"{request.folder}/{request.variant}.anim";
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            if (clip == null)
            {
                clip = new AnimationClip { name = request.variant };
                AssetDatabase.CreateAsset(clip, clipPath);
            }
            clip.ClearCurves();
            foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                AnimationUtility.SetObjectReferenceCurve(clip, binding, null);
            foreach (var (binding, material) in curves)
                AnimationUtility.SetObjectReferenceCurve(clip, binding,
                    new[] { new ObjectReferenceKeyframe { time = 0, value = material } });
            EditorUtility.SetDirty(clip);
            AssetDatabase.SaveAssets();
            return (clip, report, curves.Count);
        }

        private static Material SaveCopy(Material original, string path, Dictionary<Texture, Texture> swaps)
        {
            var copy = DshAvatarScene.VariantCopy(original, swaps);
            var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing == null)
            {
                AssetDatabase.CreateAsset(copy, path);
                return copy;
            }
            EditorUtility.CopySerialized(copy, existing);
            existing.name = Path.GetFileNameWithoutExtension(path);
            EditorUtility.SetDirty(existing);
            UnityEngine.Object.DestroyImmediate(copy);
            return existing;
        }

        private static void CreateToggle(GameObject holder, AnimationClip clip, Request request)
        {
            var toggle = DshVrc.CreateFuryToggle(holder);
            DshVrc.CallPublic(toggle, "SetMenuPath", request.menu);
            DshVrc.CallPublic(toggle, "SetSaved");
            if (request.defaultOn) DshVrc.CallPublic(toggle, "SetDefaultOn");
            if (!string.IsNullOrEmpty(request.exclusiveTag)) DshVrc.CallPublic(toggle, "AddExclusiveTag", request.exclusiveTag);
            DshVrc.CallPublic(DshVrc.CallPublic(toggle, "GetActions"), "AddAnimationClip", clip);
        }

        private static void CheckExistingMenus(GameObject avatar, string menu)
        {
            foreach (var component in avatar.GetComponentsInChildren<Component>(true).Where(DshVrc.IsFury))
                if (DshVrc.ToggleData(component)?.FindPropertyRelative("name")?.stringValue == menu)
                    throw new InvalidOperationException(
                        $"An existing VRCFury toggle on '{DshAvatarScene.HierarchyPath(component.transform)}' uses the menu {menu}.");
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

        private static void VerifyToggle(GameObject holder, AnimationClip clip, Request request)
        {
            var components = holder == null ? Array.Empty<Component>() : holder.GetComponents<Component>().Where(DshVrc.IsFury).ToArray();
            var data = components.Length == 1 ? DshVrc.ToggleData(components[0]) : null;
            var actions = data?.FindPropertyRelative("state.actions");
            var action = actions != null && actions.arraySize == 1 ? actions.GetArrayElementAtIndex(0) : null;
            if (data == null || data.FindPropertyRelative("name")?.stringValue != request.menu ||
                data.FindPropertyRelative("defaultOn")?.boolValue != request.defaultOn ||
                action == null || !action.managedReferenceFullTypename.EndsWith("AnimationClipAction", StringComparison.Ordinal) ||
                !References(action, clip))
                throw new InvalidOperationException("The DSH color toggle settings differ or VRCFury uses an unsupported format. Inspect the scene and Git diff before retrying.");
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Request request,
            List<Dictionary<string, object>> materials)
        {
            var result = new Dictionary<string, object>
            {
                { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false }, { "menu", request.menu }
            };
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar);
                var descriptor = DshAvatarScene.Descriptor(copy);
                var (_, parameter) = DshVrc.GeneratedToggle(descriptor, request.menu);
                result["menuGenerated"] = true;
                result["parameter"] = parameter;

                // Optimizers may rename or merge materials, so look for any variant material in the generated FX.
                var variantNames = new HashSet<string>(materials.Select(m => Path.GetFileNameWithoutExtension((string)m["to"])));
                var swapped = DshVrc.FxClips(descriptor, parameter)
                    .SelectMany(clip => AnimationUtility.GetObjectReferenceCurveBindings(clip)
                        .Where(binding => binding.propertyName.StartsWith("m_Materials.Array.data[", StringComparison.Ordinal))
                        .SelectMany(binding => AnimationUtility.GetObjectReferenceCurve(clip, binding)))
                    .Select(key => key.value).OfType<Material>()
                    .Where(material => variantNames.Contains(material.name.Replace(" (Clone)", "")))
                    .Select(material => material.name).Distinct().OrderBy(name => name).ToArray();
                result["variantMaterials"] = swapped;
                if (swapped.Length > 0)
                    result["status"] = "passed";
                else
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "The generated FX did not show the variant materials as clip keys. Check switching in Build & Test.";
                }
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
