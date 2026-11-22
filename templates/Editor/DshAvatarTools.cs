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
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace DSH.Editor
{
    /// <summary>Scene, avatar and material lookups shared by the DSH Editor helpers.</summary>
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

        /// <summary>
        /// Material copies whose texture slots point at the variant textures instead of the originals, with the
        /// variant's material edits (lilToon values) applied when the original has any.
        /// </summary>
        public static Material VariantCopy(Material original, IDictionary<Texture, Texture> swaps,
            IDictionary<Material, DshMaterialEdit.Edit[]> edits = null)
        {
            var copy = new Material(original) { name = original.name };  // renamed on save
            foreach (var (property, texture) in Textures(original))
                if (swaps.TryGetValue(texture, out var replacement)) copy.SetTexture(property, replacement);
            if (edits != null && edits.TryGetValue(original, out var changes)) DshMaterialEdit.Apply(copy, changes);
            return copy;
        }

        /// <summary>Whether a variant changes this material: it uses a replaced texture or has material edits.</summary>
        public static bool InVariant(Material material, IDictionary<Texture, Texture> swaps,
            IDictionary<Material, DshMaterialEdit.Edit[]> edits) =>
            material != null && ((edits != null && edits.ContainsKey(material)) ||
                                 Textures(material).Any(t => swaps.ContainsKey(t.texture)));

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

    /// <summary>
    /// VRChat SDK and VRCFury access through reflection, so the helpers compile without either package
    /// and report a clear error when one is missing or changed.
    /// </summary>
    internal static class DshVrc
    {
        public static Type LoadedType(string name) => AppDomain.CurrentDomain.GetAssemblies()
            .Select(assembly => assembly.GetType(name)).FirstOrDefault(type => type != null);

        public static object CallPublic(object target, string name, params object[] args)
        {
            var method = target?.GetType().GetMethod(name, args.Select(arg => arg.GetType()).ToArray())
                ?? throw new InvalidOperationException($"VRCFury API method {name} is unavailable. Update VRCFury in VCC/ALCOM.");
            return method.Invoke(target, args);
        }

        public static object PublicMember(object target, string name)
        {
            var type = target?.GetType();
            return type?.GetField(name)?.GetValue(target) ?? type?.GetProperty(name)?.GetValue(target);
        }

        public static IEnumerable<object> PublicItems(object target, string name) =>
            PublicMember(target, name) is IEnumerable items ? items.Cast<object>() : Enumerable.Empty<object>();

        /// <summary>A new VRCFury Toggle component on the holder (com.vrcfury.api.FuryComponents.CreateToggle).</summary>
        public static object CreateFuryToggle(GameObject holder)
        {
            var factory = LoadedType("com.vrcfury.api.FuryComponents")?.GetMethod("CreateToggle",
                    BindingFlags.Public | BindingFlags.Static, null, new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("VRCFury Toggle API is unavailable. Install or update VRCFury in VCC/ALCOM.");
            return factory.Invoke(null, new object[] { holder });
        }

        public static bool IsFury(Component component) => component != null &&
            component.GetType().FullName == "VF.Model.VRCFury";

        public static SerializedProperty ToggleData(Component component)
        {
            var data = new SerializedObject(component).FindProperty("content");
            return data != null && data.propertyType == SerializedPropertyType.ManagedReference &&
                   data.managedReferenceFullTypename.EndsWith(" VF.Model.Feature.Toggle", StringComparison.Ordinal)
                ? data : null;
        }

        public static GameObject FindHolder(GameObject avatar, string name)
        {
            var matches = avatar.transform.Cast<Transform>().Where(t => t.name == name).ToArray();
            if (matches.Length > 1) throw new InvalidOperationException($"Several objects use '{name}'.");
            return matches.Length == 1 ? matches[0].gameObject : null;
        }

        /// <summary>
        /// Run the SDK avatar build preprocess on a copy; the caller destroys the copy. The callback sees the
        /// copy before build plugins move or remove objects in it.
        /// </summary>
        public static GameObject PreprocessCopy(GameObject avatar, Action<GameObject> beforePreprocess = null)
        {
            var callback = LoadedType("VRC.SDKBase.Editor.BuildPipeline.VRCBuildPipelineCallbacks")?
                .GetMethod("OnPreprocessAvatar", BindingFlags.Public | BindingFlags.Static, null,
                    new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("The VRChat SDK avatar preprocessing API is unavailable.");
            // Only VRCFury needs its temporary package; projects with Modular Avatar alone build without it.
            if (LoadedType("VF.Model.VRCFury") != null && !AssetDatabase.IsValidFolder("Packages/com.vrcfury.temp"))
                throw new InvalidOperationException("Open the project in Unity once to let VRCFury initialize its temporary package, then close it and retry verification.");
            var copy = UnityEngine.Object.Instantiate(avatar);
            copy.name = avatar.name + " (DSH Verification)";
            try
            {
                beforePreprocess?.Invoke(copy);
                if (!(callback.Invoke(null, new object[] { copy }) is bool built) || !built)
                    throw new InvalidOperationException("VRChat SDK preprocessing did not complete. See the Unity log.");
            }
            catch
            {
                UnityEngine.Object.DestroyImmediate(copy);
                throw;
            }
            return copy;
        }

        /// <summary>
        /// The generated menu Toggle at a slash-separated path, its parameter name, and where it appears in the
        /// VRChat menu, including any "Next" page links in front of it (for example "Next/Outfit/Hood").
        /// </summary>
        public static (object control, string parameter, string location) GeneratedToggle(Component descriptor, string path)
        {
            object control = null;
            var menu = PublicMember(descriptor, "expressionsMenu");
            var names = Array.Empty<string>();
            var location = new List<string>();
            foreach (var name in path.Split('/'))
            {
                var controls = PagedControls(menu).ToArray();
                names = controls.Select(item => PublicMember(item.control, "name") as string).ToArray();
                var matching = controls.Where(item => PublicMember(item.control, "name") as string == name).ToArray();
                control = matching.Length == 1 ? matching[0].control : null;
                if (control == null) break;
                location.AddRange(matching[0].via);
                location.Add(name);
                menu = PublicMember(control, "subMenu");
            }
            if (PublicMember(control, "type")?.ToString() != "Toggle")
                throw new InvalidOperationException($"The SDK did not generate a unique Toggle at '{path}'. " +
                    $"The generated menu level has: {string.Join(", ", names.Take(24))}");
            return (control, PublicMember(PublicMember(control, "parameter"), "name") as string, string.Join("/", location));
        }

        /// <summary>
        /// Controls of a menu including its continuation pages. When a menu has more controls than fit, VRCFury
        /// moves the rest to a submenu asset named "&lt;menu&gt; (Page N)" behind a last "Next" control. Build steps
        /// may rename the menu assets afterwards, and the label can be changed in VRCFury's menu settings, so the
        /// last submenu counts as a page when its asset name has " (Page " or its label is "Next".
        /// </summary>
        public static IEnumerable<(object control, string[] via)> PagedControls(object menu)
        {
            var visited = new HashSet<object>();
            var via = new List<string>();
            while (menu != null && visited.Add(menu))
            {
                var controls = PublicItems(menu, "controls").ToArray();
                object nextPage = null;
                string nextLabel = null;
                if (controls.Length > 0)
                {
                    var last = controls[controls.Length - 1];
                    var subMenu = PublicMember(last, "subMenu");
                    var subName = PublicMember(subMenu, "name") as string ?? "";
                    if (subMenu != null && PublicMember(last, "type")?.ToString() == "SubMenu" &&
                        (subName.Contains(" (Page ") || PublicMember(last, "name") as string == "Next"))
                    {
                        nextPage = subMenu;
                        nextLabel = PublicMember(last, "name") as string ?? "Next";
                        controls = controls.Take(controls.Length - 1).ToArray();
                    }
                }
                var path = via.ToArray();
                foreach (var control in controls) yield return (control, path);
                if (nextLabel != null) via.Add(nextLabel);
                menu = nextPage;
            }
        }

        /// <summary>Clips of the generated FX controllers that use the parameter.</summary>
        public static IEnumerable<AnimationClip> FxClips(Component descriptor, string parameter) =>
            PublicItems(descriptor, "baseAnimationLayers")
                .Where(layer => PublicMember(layer, "type")?.ToString() == "FX")
                .Select(layer => PublicMember(layer, "animatorController")).OfType<AnimatorController>()
                .Where(controller => controller.parameters.Any(p => p.name == parameter))
                .SelectMany(controller => controller.animationClips).Where(clip => clip != null).Distinct();
    }

    /// <summary>
    /// lilToon material values a variant may change: colors, color correction (HSVG), feature switches and
    /// strengths. Only these properties are read or written, so render mode, blending, stencil and texture slots
    /// stay as the material's author set them. unity_texture.py keeps the same list (a test compares them).
    /// </summary>
    internal static class DshMaterialEdit
    {
        [Serializable]
        public sealed class Edit
        {
            public string material = "";
            public string property = "";
            public string kind = "";  // color, hsvg, toggle or float
            public float x;
            public float y;
            public float z;
            public float w;
            public int mask = 15;     // which of x, y, z, w to write; the rest keep the material's value
        }

        public static readonly Dictionary<string, string> Allowed = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { "_Color", "color" }, { "_MainTexHSVG", "hsvg" }, { "_MainGradationStrength", "float" },
            { "_UseShadow", "toggle" }, { "_ShadowStrength", "float" }, { "_ShadowColor", "color" },
            { "_ShadowBorder", "float" }, { "_ShadowBlur", "float" }, { "_Shadow2ndColor", "color" },
            { "_Shadow2ndBorder", "float" }, { "_Shadow2ndBlur", "float" }, { "_Shadow3rdColor", "color" },
            { "_Shadow3rdBorder", "float" }, { "_Shadow3rdBlur", "float" }, { "_ShadowBorderColor", "color" },
            { "_ShadowBorderRange", "float" }, { "_ShadowMainStrength", "float" }, { "_ShadowEnvStrength", "float" },
            { "_UseBacklight", "toggle" }, { "_BacklightColor", "color" },
            { "_UseReflection", "toggle" }, { "_Smoothness", "float" }, { "_Metallic", "float" },
            { "_Reflectance", "float" }, { "_ReflectionColor", "color" },
            { "_UseMatCap", "toggle" }, { "_MatCapColor", "color" }, { "_MatCapBlend", "float" },
            { "_UseRim", "toggle" }, { "_RimColor", "color" }, { "_RimBorder", "float" }, { "_RimBlur", "float" },
            { "_RimFresnelPower", "float" }, { "_RimEnableLighting", "float" },
            { "_UseEmission", "toggle" }, { "_EmissionColor", "color" }, { "_EmissionMainStrength", "float" },
            { "_EmissionBlend", "float" },
            { "_OutlineColor", "color" }, { "_OutlineWidth", "float" }, { "_OutlineTexHSVG", "hsvg" },
            { "_AsUnlit", "float" }, { "_LightMinLimit", "float" }, { "_LightMaxLimit", "float" },
            { "_MonochromeLighting", "float" },
        };

        public static bool IsMulti(Shader shader) =>
            shader != null && shader.name.IndexOf("lilToonMulti", StringComparison.OrdinalIgnoreCase) >= 0;

        public static bool HasOutline(Shader shader) =>
            shader != null && shader.name.IndexOf("Outline", StringComparison.OrdinalIgnoreCase) >= 0;

        /// <summary>Load and check every edit before anything is written; the key is the original material.</summary>
        public static Dictionary<Material, Edit[]> Load(IEnumerable<Edit> edits)
        {
            var loaded = new Dictionary<Material, List<Edit>>();
            foreach (var edit in edits ?? Enumerable.Empty<Edit>())
            {
                var material = AssetDatabase.LoadAssetAtPath<Material>(edit.material)
                    ?? throw new InvalidOperationException($"Unity could not load the material {edit.material}.");
                if (DshAvatarScene.ShaderFamily(material.shader) != "lilToon")
                    throw new InvalidOperationException($"{edit.material} does not use lilToon ({material.shader?.name}). Only lilToon values can be changed.");
                Check(material, edit);
                if (!loaded.TryGetValue(material, out var list)) loaded[material] = list = new List<Edit>();
                list.Add(edit);
            }
            return loaded.ToDictionary(pair => pair.Key, pair => pair.Value.ToArray());
        }

        private static void Check(Material material, Edit edit)
        {
            if (!Allowed.TryGetValue(edit.property, out var kind) || kind != edit.kind)
                throw new InvalidOperationException($"{edit.property} is not a lilToon value DSH changes as '{edit.kind}'.");
            var shader = material.shader;
            var index = shader.FindPropertyIndex(edit.property);
            if (index < 0 || !material.HasProperty(edit.property))
                throw new InvalidOperationException($"The shader {shader.name} of {edit.material} has no {edit.property}.");
            var type = shader.GetPropertyType(index);
            var expected = kind == "color" ? type == ShaderPropertyType.Color :
                kind == "hsvg" ? type == ShaderPropertyType.Vector :
                type == ShaderPropertyType.Float || type == ShaderPropertyType.Range || type == ShaderPropertyType.Int;
            if (!expected)
                throw new InvalidOperationException($"{edit.property} of {shader.name} is a {type} property, not {kind}.");
            if (kind == "float" && type == ShaderPropertyType.Range)
            {
                var limits = shader.GetPropertyRangeLimits(index);
                if (edit.x < limits.x - 1e-4f || edit.x > limits.y + 1e-4f)
                    throw new InvalidOperationException($"{edit.property} must be from {limits.x} to {limits.y} on {shader.name}.");
            }
            if (kind == "toggle" && IsMulti(shader) && SetupMulti == null)
                throw new InvalidOperationException("This lilToon version has no SetupMultiMaterial, so features of lilToon Multi materials cannot be switched. Change them in Unity.");
        }

        public static void Apply(Material copy, Edit[] edits)
        {
            foreach (var edit in edits)
            {
                switch (edit.kind)
                {
                    case "color":
                        var color = copy.GetColor(edit.property);
                        copy.SetColor(edit.property, new Color(Pick(edit, 0, color.r), Pick(edit, 1, color.g),
                            Pick(edit, 2, color.b), Pick(edit, 3, color.a)));
                        break;
                    case "hsvg":
                        var vector = copy.GetVector(edit.property);
                        copy.SetVector(edit.property, new Vector4(Pick(edit, 0, vector.x), Pick(edit, 1, vector.y),
                            Pick(edit, 2, vector.z), Pick(edit, 3, vector.w)));
                        break;
                    default:
                        var index = copy.shader.FindPropertyIndex(edit.property);
                        if (copy.shader.GetPropertyType(index) == ShaderPropertyType.Int)
                            copy.SetInteger(edit.property, Mathf.RoundToInt(edit.x));
                        else
                            copy.SetFloat(edit.property, edit.x);
                        break;
                }
            }
            // lilToon Multi compiles features as keywords; let lilToon set them from the new values.
            if (IsMulti(copy.shader) && SetupMulti != null) SetupMulti.Invoke(null, new object[] { copy });
        }

        private static float Pick(Edit edit, int component, float current)
        {
            if ((edit.mask & (1 << component)) == 0) return current;
            return component == 0 ? edit.x : component == 1 ? edit.y : component == 2 ? edit.z : edit.w;
        }

        private static MethodInfo SetupMulti => DshVrc.LoadedType("lilToon.lilMaterialUtils")?.GetMethod(
            "SetupMultiMaterial", BindingFlags.Public | BindingFlags.Static, null, new[] { typeof(Material) }, null);

        /// <summary>The allowed values present on a lilToon material, in the forms a recipe uses.</summary>
        public static Dictionary<string, object> Read(Material material, Dictionary<string, object> ranges)
        {
            var values = new Dictionary<string, object>();
            var shader = material.shader;
            foreach (var pair in Allowed)
            {
                var index = shader.FindPropertyIndex(pair.Key);
                if (index < 0 || !material.HasProperty(pair.Key)) continue;
                switch (pair.Value)
                {
                    case "color":
                        values[pair.Key] = ColorValue(material.GetColor(pair.Key));
                        break;
                    case "hsvg":
                        var v = material.GetVector(pair.Key);
                        values[pair.Key] = new Dictionary<string, object>
                        {
                            { "hue", Round(v.x) }, { "saturation", Round(v.y) }, { "value", Round(v.z) }, { "gamma", Round(v.w) }
                        };
                        break;
                    case "toggle":
                        values[pair.Key] = material.GetFloat(pair.Key) != 0f;
                        break;
                    default:
                        values[pair.Key] = Round(material.GetFloat(pair.Key));
                        if (shader.GetPropertyType(index) == ShaderPropertyType.Range && !ranges.ContainsKey(pair.Key))
                        {
                            var limits = shader.GetPropertyRangeLimits(index);
                            ranges[pair.Key] = new[] { Round(limits.x), Round(limits.y) };
                        }
                        break;
                }
            }
            return values;
        }

        private static object ColorValue(Color color)
        {
            var c = new[] { color.r, color.g, color.b, color.a };
            if (c.All(component => component >= 0f && component <= 1f))
                return "#" + string.Concat(c.Select(component => Mathf.RoundToInt(component * 255).ToString("X2")));
            return c.Select(Round).ToArray();  // HDR
        }

        private static double Round(float value) => Math.Round(value, 4);
    }
}
