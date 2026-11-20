using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DSH.Editor
{
    /// <summary>Scene, avatar and material lookups shared by the color variant and capture helpers.</summary>
    internal static class DshAvatarScene
    {
        public static T ReadRequest<T>() where T : class
        {
            var requestPath = Environment.GetEnvironmentVariable("DSH_UNITY_REQUEST_PATH");
            return JsonUtility.FromJson<T>(File.ReadAllText(requestPath))
                ?? throw new InvalidOperationException("A Unity task request is required.");
        }

        public static void Finish(string task, Dictionary<string, object> result)
        {
            DshApply.WriteResult(task, result);
            EditorApplication.Exit((bool)result["ok"] ? 0 : 1);
        }

        public static string RunDirectory =>
            Path.GetDirectoryName(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH") ?? "") ?? "";

        public static Scene OpenScene(string path, string expectedDigest = "")
        {
            if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) ||
                !path.EndsWith(".unity", StringComparison.OrdinalIgnoreCase) || path.Contains("\\") ||
                path.Split('/').Any(part => part == ".." || part == ".") ||
                AssetDatabase.LoadAssetAtPath<SceneAsset>(path) == null)
                throw new InvalidOperationException($"Select a saved scene underneath Assets: {path}");
            RequireSceneDigest(path, expectedDigest);
            return EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
        }

        public static string SceneDigest(string path)
        {
            using (var sha = SHA256.Create())
            using (var scene = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(scene)).Replace("-", "").ToLowerInvariant();
        }

        public static void RequireSceneDigest(string path, string expectedDigest)
        {
            if (!string.IsNullOrEmpty(expectedDigest) && SceneDigest(path) != expectedDigest)
                throw new InvalidOperationException("The saved scene changed after the preview. Review it and preview again.");
        }

        public static Component Descriptor(GameObject obj) => obj.GetComponents<Component>().FirstOrDefault(c =>
            c != null && (c.GetType().FullName == "VRC.SDK3.Avatars.Components.VRCAvatarDescriptor" ||
                          c.GetType().FullName == "VRCSDK2.VRC_AvatarDescriptor"));

        public static IEnumerable<Transform> Avatars(Scene scene) => scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<Transform>(true))
            .Where(t => Descriptor(t.gameObject) != null);

        /// <summary>Pick the requested avatar, or the only avatar when no path is given.</summary>
        public static GameObject ResolveAvatar(Scene scene, string path, string id, Dictionary<string, object> result)
        {
            var avatars = Avatars(scene).ToArray();
            result["avatars"] = avatars.Take(20).Select(Describe).ToArray();
            var selected = avatars.Where(t => (string.IsNullOrEmpty(path) || HierarchyPath(t) == path) &&
                                              (string.IsNullOrEmpty(id) || ObjectId(t.gameObject) == id)).ToArray();
            if (selected.Length == 1) return selected[0].gameObject;
            throw new InvalidOperationException(selected.Length == 0
                ? $"The avatar '{path}' could not be found in the saved scene."
                : "Several avatars match. Pass --avatar with the hierarchy path, and --avatar-id when names repeat.");
        }

        public static Dictionary<string, object> Describe(Transform target) => new Dictionary<string, object>
        {
            { "name", target.name }, { "path", HierarchyPath(target) }, { "id", ObjectId(target.gameObject) }
        };

        public static string HierarchyPath(Transform transform) =>
            transform.parent == null ? transform.name : HierarchyPath(transform.parent) + "/" + transform.name;

        public static string ObjectId(GameObject obj) => GlobalObjectId.GetGlobalObjectIdSlow(obj).ToString();

        public static IEnumerable<(string property, Texture texture)> Textures(Material material)
        {
            if (material == null) yield break;
            foreach (var property in material.GetTexturePropertyNames())
            {
                var texture = material.HasProperty(property) ? material.GetTexture(property) : null;
                if (texture != null) yield return (property, texture);
            }
        }

        public static string ShaderFamily(Shader shader)
        {
            var name = shader == null ? "" : shader.name;
            if (name.IndexOf("lilToon", StringComparison.OrdinalIgnoreCase) >= 0 ||
                name.StartsWith("_lil/", StringComparison.Ordinal)) return "lilToon";
            if (name.IndexOf("poiyomi", StringComparison.OrdinalIgnoreCase) >= 0 ||
                name.StartsWith("Hidden/Locked/", StringComparison.Ordinal)) return "Poiyomi";
            return "other";
        }

        public static bool IsLocked(Shader shader) =>
            shader != null && shader.name.StartsWith("Hidden/Locked/", StringComparison.Ordinal);

        /// <summary>Material copies whose texture slots point at the variant textures instead of the originals.</summary>
        public static Material VariantCopy(Material original, IDictionary<Texture, Texture> swaps)
        {
            var copy = new Material(original) { name = original.name };  // renamed on save
            foreach (var (property, texture) in Textures(original))
                if (swaps.TryGetValue(texture, out var replacement)) copy.SetTexture(property, replacement);
            return copy;
        }

        public static Dictionary<Texture, Texture> LoadSwaps(IEnumerable<(string from, string to)> pairs)
        {
            var swaps = new Dictionary<Texture, Texture>();
            foreach (var (from, to) in pairs)
            {
                var original = AssetDatabase.LoadAssetAtPath<Texture>(from)
                    ?? throw new InvalidOperationException($"Unity could not load the original texture {from}.");
                var replacement = AssetDatabase.LoadAssetAtPath<Texture>(to)
                    ?? throw new InvalidOperationException($"Unity could not load the variant texture {to}.");
                swaps[original] = replacement;
            }
            return swaps;
        }
    }

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
                var holder = FindHolder(avatar, holderName);
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
                    holder = FindHolder(avatar, holderName);
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

        private static GameObject FindHolder(GameObject avatar, string name)
        {
            var matches = avatar.transform.Cast<Transform>().Where(t => t.name == name).ToArray();
            if (matches.Length > 1) throw new InvalidOperationException($"Several objects use '{name}'.");
            return matches.Length == 1 ? matches[0].gameObject : null;
        }

        private static Type LoadedType(string name) => AppDomain.CurrentDomain.GetAssemblies()
            .Select(assembly => assembly.GetType(name)).FirstOrDefault(type => type != null);

        private static object CallPublic(object target, string name, params object[] args)
        {
            var method = target?.GetType().GetMethod(name, args.Select(arg => arg.GetType()).ToArray())
                ?? throw new InvalidOperationException($"VRCFury API method {name} is unavailable. Update VRCFury in VCC/ALCOM.");
            return method.Invoke(target, args);
        }

        private static void CreateToggle(GameObject holder, AnimationClip clip, Request request)
        {
            var factory = LoadedType("com.vrcfury.api.FuryComponents")?.GetMethod("CreateToggle",
                    BindingFlags.Public | BindingFlags.Static, null, new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("VRCFury Toggle API is unavailable. Install or update VRCFury in VCC/ALCOM.");
            var toggle = factory.Invoke(null, new object[] { holder });
            CallPublic(toggle, "SetMenuPath", request.menu);
            CallPublic(toggle, "SetSaved");
            if (request.defaultOn) CallPublic(toggle, "SetDefaultOn");
            if (!string.IsNullOrEmpty(request.exclusiveTag)) CallPublic(toggle, "AddExclusiveTag", request.exclusiveTag);
            CallPublic(CallPublic(toggle, "GetActions"), "AddAnimationClip", clip);
        }

        private static bool IsFury(Component component) => component != null &&
            component.GetType().FullName == "VF.Model.VRCFury";

        private static SerializedProperty ToggleData(Component component)
        {
            var data = new SerializedObject(component).FindProperty("content");
            return data != null && data.propertyType == SerializedPropertyType.ManagedReference &&
                   data.managedReferenceFullTypename.EndsWith(" VF.Model.Feature.Toggle", StringComparison.Ordinal)
                ? data : null;
        }

        private static void CheckExistingMenus(GameObject avatar, string menu)
        {
            foreach (var component in avatar.GetComponentsInChildren<Component>(true).Where(IsFury))
                if (ToggleData(component)?.FindPropertyRelative("name")?.stringValue == menu)
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
            var components = holder == null ? Array.Empty<Component>() : holder.GetComponents<Component>().Where(IsFury).ToArray();
            var data = components.Length == 1 ? ToggleData(components[0]) : null;
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
                var callback = LoadedType("VRC.SDKBase.Editor.BuildPipeline.VRCBuildPipelineCallbacks")?
                    .GetMethod("OnPreprocessAvatar", BindingFlags.Public | BindingFlags.Static, null,
                        new[] { typeof(GameObject) }, null)
                    ?? throw new InvalidOperationException("The VRChat SDK avatar preprocessing API is unavailable.");
                if (!AssetDatabase.IsValidFolder("Packages/com.vrcfury.temp"))
                    throw new InvalidOperationException("Open the project in Unity once to let VRCFury initialize its temporary package, then close it and retry verification.");
                copy = UnityEngine.Object.Instantiate(avatar);
                copy.name = avatar.name + " (DSH Verification)";
                if (!(callback.Invoke(null, new object[] { copy }) is bool built) || !built)
                    throw new InvalidOperationException("VRChat SDK preprocessing did not complete. See the Unity log.");

                var descriptor = DshAvatarScene.Descriptor(copy);
                var control = FindMenuControl(PublicMember(descriptor, "expressionsMenu"), request.menu);
                if (PublicMember(control, "type")?.ToString() != "Toggle")
                    throw new InvalidOperationException($"The SDK did not generate a unique Toggle at '{request.menu}'.");
                result["menuGenerated"] = true;
                var parameter = PublicMember(PublicMember(control, "parameter"), "name") as string;
                result["parameter"] = parameter;

                // Optimizers may rename or merge materials, so look for any variant material in the generated FX.
                var variantNames = new HashSet<string>(materials.Select(m => Path.GetFileNameWithoutExtension((string)m["to"])));
                var controllers = PublicItems(descriptor, "baseAnimationLayers")
                    .Where(layer => PublicMember(layer, "type")?.ToString() == "FX")
                    .Select(layer => PublicMember(layer, "animatorController")).OfType<AnimatorController>()
                    .Where(controller => controller.parameters.Any(p => p.name == parameter));
                var swapped = controllers.SelectMany(controller => controller.animationClips).Distinct()
                    .Where(clip => clip != null)
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

        private static object FindMenuControl(object menu, string path)
        {
            object control = null;
            foreach (var name in path.Split('/'))
            {
                var matching = PublicItems(menu, "controls").Where(item => PublicMember(item, "name") as string == name).ToArray();
                if (matching.Length != 1) return null;
                control = matching[0];
                menu = PublicMember(control, "subMenu");
            }
            return control;
        }

        private static IEnumerable<object> PublicItems(object target, string name) =>
            PublicMember(target, name) is IEnumerable items ? items.Cast<object>() : Enumerable.Empty<object>();

        private static object PublicMember(object target, string name)
        {
            var type = target?.GetType();
            return type?.GetField(name)?.GetValue(target) ?? type?.GetProperty(name)?.GetValue(target);
        }
    }
}
