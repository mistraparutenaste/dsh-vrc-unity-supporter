using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// A lighter avatar at build time, without changing the meshes, materials or textures in the project:
    /// Avatar Optimizer's Trace and Optimize on the avatar root (merges skinned meshes, removes unused bones,
    /// objects and blendshapes), and TexTransTool AtlasTexture components under one DSH holder object, which shrink
    /// textures (one atlas per material, or per group of materials that share textures) and merge materials into
    /// one slot. Both are NDMF tools: the scene only holds their components, and the upload build uses the result.
    ///
    /// TexTransTool's serialized layout changes between versions, so the fields DSH writes (the target material
    /// list, the atlas size and the merge switch) are looked up on a real AtlasTexture by their type and name, and
    /// Read reports what was found. Every added component and object is an undo entry, so remove takes them out.
    /// </summary>
    public static class DshOptimize
    {
        [Serializable]
        private sealed class Option
        {
            public string path = "";
            public bool value = false;
        }

        [Serializable]
        private sealed class Group
        {
            public string[] materials = Array.Empty<string>();
            public int size = 2048;
            public bool merge = false;
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
            public bool traceAndOptimize = false;
            public Option[] aaoOptions = Array.Empty<Option>();
            public int textureSize = 0;                         // 0: no per-material texture shrinking
            public string[] textureMaterials = Array.Empty<string>();
            public string[] textureExclude = Array.Empty<string>();
            public Group[] atlas = Array.Empty<Group>();
            public DshUndo[] undo = Array.Empty<DshUndo>();
            public bool withRecipe = true;                      // try: false measures the build as the scene is
        }

        [Serializable]
        private sealed class CaptureRequest
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string views = "front,back";
            public int size = 512;
            public Request recipe = new Request();
        }

        private const string TraceType = "Anatawa12.AvatarOptimizer.TraceAndOptimize";
        private const string AtlasName = "AtlasTexture";
        private const string AtlasNamespace = "net.rs64.TexTransTool";
        private const string HolderPrefix = "DSH Optimize ";

        private static Type Trace => DshVrc.LoadedType(TraceType)
            ?? throw new InvalidOperationException("Avatar Optimizer is not installed. Add \"Avatar Optimizer\" (com.anatawa12.avatar-optimizer) in VCC/ALCOM.");

        private static Type AtlasOrNull => DshReflect.Find(AtlasName, AtlasNamespace);

        private static Type Atlas => AtlasOrNull
            ?? throw new InvalidOperationException("TexTransTool is not installed. Add \"TexTransTool\" (net.rs64.tex-trans-tool) in VCC/ALCOM.");

        // ---- entry points ----

        /// <summary>Read-only: materials and their textures, meshes and bones, the tools and their settings.</summary>
        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                result["materials"] = DescribeMaterials(avatar).Take(200).ToArray();
                result["renderers"] = DescribeRenderers(avatar).Take(200).ToArray();
                result["counts"] = Counts(avatar);
                result["aao"] = DescribeTrace(avatar);
                result["ttt"] = DescribeAtlas(avatar);
                result["note"] = "Counts are of the scene object before the build. textureMemoryMB uses each texture's size as imported " +
                                 "(format and mipmaps); textureMemoryMBUncompressed is the older 4-bytes-per-pixel estimate.";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Optimize", result);
        }

        /// <summary>Read-only: build a copy with the recipe (and one without it) and compare their counts.</summary>
        public static void Try()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                if (request.withRecipe)
                {
                    var groups = Plan(avatar, request, result);
                    result["compare"] = Compare(avatar, request, groups, inScene: false);
                }
                else
                {
                    result["built"] = BuiltCounts(avatar, null);
                }
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("OptimizeTry", result);
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
                var groups = Plan(avatar, request, result);
                var log = new DshUndoLog();
                var changes = Ensure(avatar, request, groups, log, true);
                result["applied"] = changes;
                result["undo"] = DshUndo.DescribeAll(log.Entries);
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied optimize recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var earlier = request.undo ?? Array.Empty<DshUndo>();
                request.undo = earlier.Concat(log.Entries.Where(e => earlier.All(u => u.key != e.key))).ToArray();
                groups = Plan(avatar, request, new Dictionary<string, object>());
                var remaining = Ensure(avatar, request, groups, null, false);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the recipe: " + string.Join("; ", remaining.Take(5)));
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, request, groups)
                    : new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("OptimizeRecipe", result);
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
                var changes = Revert(avatar, request, true);
                result["reverted"] = changes;
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed optimize recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Revert(avatar, request, false);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene still holds part of the recipe: " + string.Join("; ", remaining.Take(5)));
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("OptimizeRemove", result);
        }

        /// <summary>Before and after the recipe, each built by the SDK (so AAO and TexTransTool run), side by side.</summary>
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
                var groups = Plan(avatar, recipe, result);
                var counts = new Dictionary<string, object>();
                GameObject Make(GameObject source, string label, bool withRecipe)
                {
                    var made = DshVrc.PreprocessCopy(source, copy => Prepare(copy, recipe, groups, withRecipe));
                    counts[label] = Counts(made);
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
                result["countsAfterBuild"] = counts;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("OptimizeCapture", result);
        }

        // ---- reading ----

        private static IEnumerable<Material> AvatarMaterials(GameObject avatar) =>
            avatar.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Distinct();

        private static string MaterialKey(Material material)
        {
            var path = AssetDatabase.GetAssetPath(material);
            return string.IsNullOrEmpty(path) ? material.name : path;
        }

        private static IEnumerable<object> DescribeMaterials(GameObject avatar)
        {
            var users = new Dictionary<Material, List<string>>();
            foreach (var renderer in avatar.GetComponentsInChildren<Renderer>(true))
                foreach (var material in renderer.sharedMaterials.Where(m => m != null))
                {
                    if (!users.TryGetValue(material, out var list)) users[material] = list = new List<string>();
                    var path = DshReflect.PathIn(renderer.transform, avatar.transform);
                    if (!list.Contains(path)) list.Add(path);
                }
            var byTexture = new Dictionary<Texture, List<Material>>();
            foreach (var material in users.Keys)
                foreach (var (_, texture) in DshAvatarScene.Textures(material))
                {
                    if (!byTexture.TryGetValue(texture, out var list)) byTexture[texture] = list = new List<Material>();
                    if (!list.Contains(material)) list.Add(material);
                }
            foreach (var pair in users)
            {
                var material = pair.Key;
                var textures = DshAvatarScene.Textures(material).GroupBy(t => t.texture).Select(g => (object)new Dictionary<string, object>
                {
                    { "properties", g.Select(t => t.property).ToArray() },
                    { "texture", g.Key.name }, { "path", AssetDatabase.GetAssetPath(g.Key) },
                    { "size", $"{g.Key.width}x{g.Key.height}" },
                    { "format", g.Key is Texture2D t2 ? t2.format.ToString() : g.Key.GetType().Name },
                    { "mb", Math.Round(TextureBytes(g.Key) / 1048576.0, 2) },
                }).ToArray();
                var shared = DshAvatarScene.Textures(material).SelectMany(t => byTexture[t.texture]).Where(m => m != material)
                    .Distinct().Select(m => (object)m.name).ToArray();
                var row = new Dictionary<string, object>
                {
                    { "material", material.name }, { "path", AssetDatabase.GetAssetPath(material) },
                    { "shader", material.shader != null ? material.shader.name : "" },
                    { "family", DshAvatarScene.ShaderFamily(material.shader) },
                    { "renderers", pair.Value.Take(20).ToArray() },
                    { "largest", DshAvatarScene.Textures(material).Select(t => Math.Max(t.texture.width, t.texture.height)).DefaultIfEmpty(0).Max() },
                    { "textures", textures },
                };
                if (shared.Length > 0) row["sharesTexturesWith"] = shared;
                yield return row;
            }
        }

        private static IEnumerable<object> DescribeRenderers(GameObject avatar) =>
            avatar.GetComponentsInChildren<Renderer>(true).Where(r => r is SkinnedMeshRenderer || r is MeshRenderer).Select(r =>
            {
                var skinned = r as SkinnedMeshRenderer;
                var mesh = skinned != null ? skinned.sharedMesh : r.GetComponent<MeshFilter>()?.sharedMesh;
                return (object)new Dictionary<string, object>
                {
                    { "path", DshReflect.PathIn(r.transform, avatar.transform) }, { "skinned", skinned != null },
                    { "active", r.gameObject.activeInHierarchy },
                    { "materials", r.sharedMaterials.Count(m => m != null) },
                    { "bones", skinned != null ? skinned.bones.Count(b => b != null) : 0 },
                    { "blendShapes", mesh != null ? mesh.blendShapeCount : 0 },
                };
            });

        /// <summary>The perf counts, with texture memory from each texture's imported size and the bone count.</summary>
        private static Dictionary<string, object> Counts(GameObject avatar)
        {
            var counts = DshInspect.MeasureCounts(avatar);
            counts["textureMemoryMBUncompressed"] = counts["textureMemoryMB"];
            var textures = new HashSet<Texture>();
            foreach (var material in AvatarMaterials(avatar))
                foreach (var (_, texture) in DshAvatarScene.Textures(material)) textures.Add(texture);
            counts["textureMemoryMB"] = Math.Round(textures.Sum(TextureBytes) / 1048576.0, 1);
            counts["textures"] = textures.Count;
            counts["bones"] = avatar.GetComponentsInChildren<SkinnedMeshRenderer>(true).SelectMany(s => s.bones)
                .Where(b => b != null).Distinct().Count();
            return counts;
        }

        private static MethodInfo storageSize;
        private static bool storageLooked;

        /// <summary>Bytes the texture takes as imported (format, mipmaps), as the Inspector's preview shows.</summary>
        private static long TextureBytes(Texture texture)
        {
            if (texture == null) return 0;
            if (!storageLooked)
            {
                storageLooked = true;
                storageSize = typeof(EditorGUI).Assembly.GetType("UnityEditor.TextureUtil")?
                    .GetMethod("GetStorageMemorySizeLong", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static,
                        null, new[] { typeof(Texture) }, null);
            }
            try
            {
                if (storageSize != null && storageSize.Invoke(null, new object[] { texture }) is long bytes && bytes > 0) return bytes;
            }
            catch
            {
                // fall back to the estimate below
            }
            var mips = texture.mipmapCount > 1 ? 4.0 / 3.0 : 1.0;
            return (long)(texture.width * (long)texture.height * 4 * mips);
        }

        // ---- Avatar Optimizer ----

        private static Dictionary<string, object> DescribeTrace(GameObject avatar)
        {
            var type = DshVrc.LoadedType(TraceType);
            var row = new Dictionary<string, object> { { "installed", type != null } };
            if (type == null) return row;
            var existing = avatar.GetComponent(type);
            row["traceAndOptimize"] = existing != null;
            row["elsewhere"] = avatar.GetComponentsInChildren(type, true).Where(c => c.gameObject != avatar)
                .Select(c => (object)DshReflect.PathIn(c.transform, avatar.transform)).Take(20).ToArray();
            WithTemporary(type, existing, component => row["options"] = BoolOptions(component).ToArray());
            return row;
        }

        /// <summary>The top-level true/false options of a component, as the Inspector labels them.</summary>
        private static IEnumerable<object> BoolOptions(Component component)
        {
            var it = new SerializedObject(component).GetIterator();
            var enter = true;
            while (it.Next(enter))
            {
                enter = it.depth < 2;
                if (it.propertyType != SerializedPropertyType.Boolean || it.propertyPath.StartsWith("m_", StringComparison.Ordinal)) continue;
                yield return new Dictionary<string, object> { { "path", it.propertyPath }, { "label", it.displayName }, { "value", it.boolValue } };
            }
        }

        /// <summary>Run with the existing component, or with one on a temporary object that is destroyed after.</summary>
        private static void WithTemporary(Type type, Component existing, Action<Component> use)
        {
            if (existing != null)
            {
                use(existing);
                return;
            }
            var temporary = new GameObject("DSH Temporary") { hideFlags = HideFlags.HideAndDontSave };
            try
            {
                use(temporary.AddComponent(type));
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(temporary);
            }
        }

        private static string SetOptions(Component component, Option[] options, bool write)
        {
            var serialized = new SerializedObject(component);
            var changed = new List<string>();
            foreach (var option in options ?? Array.Empty<Option>())
            {
                var property = serialized.FindProperty(option.path);
                if (property == null || property.propertyType != SerializedPropertyType.Boolean)
                    throw new InvalidOperationException($"Trace and Optimize has no true/false option '{option.path}' in this Avatar Optimizer version. Read the avatar for the options ('aao.options').");
                if (property.boolValue == option.value) continue;
                changed.Add($"{property.displayName} = {(option.value ? "on" : "off")}");
                if (write) property.boolValue = option.value;
            }
            if (write && changed.Count > 0) serialized.ApplyModifiedPropertiesWithoutUndo();
            return string.Join(", ", changed);
        }

        // ---- TexTransTool ----

        /// <summary>Where DSH writes in an AtlasTexture: found by type and name, so it follows TexTransTool's changes.</summary>
        private sealed class AtlasLayout
        {
            public string materials;       // the target material list (an array of Material, or of items holding one)
            public string materialChild;   // in each item, the Material reference ("" when the items are Materials)
            public string size;            // the atlas texture size (int)
            public string merge;           // merge the materials into one (bool), or null
            public string targetRoot;      // older versions: the object whose renderers are atlased, or null
            public readonly List<string> problems = new List<string>();
        }

        private static AtlasLayout layoutCache;

        private static bool IsMaterialReference(SerializedProperty p) =>
            p.propertyType == SerializedPropertyType.ObjectReference && (p.type == "PPtr<Material>" || p.type == "PPtr<$Material>");

        private static AtlasLayout Layout(Component atlas)
        {
            if (layoutCache != null) return layoutCache;
            var layout = new AtlasLayout();
            var serialized = new SerializedObject(atlas);
            var lists = new List<(string path, string child)>();
            var sizes = new List<string>();
            var merges = new List<string>();
            var it = serialized.GetIterator();
            var enter = true;
            while (it.Next(enter))
            {
                enter = it.depth < 3 && !it.propertyPath.Contains(".Array.data[");
                var name = it.name;
                if (it.isArray && it.propertyType == SerializedPropertyType.Generic && !it.propertyPath.Contains(".Array"))
                {
                    var holder = it.Copy();
                    holder.arraySize = Math.Max(holder.arraySize, 1);   // look at one item; nothing is applied
                    var item = holder.GetArrayElementAtIndex(0);
                    if (IsMaterialReference(item)) lists.Add((it.propertyPath, ""));
                    else
                    {
                        var child = item.Copy();
                        var end = item.GetEndProperty();
                        if (child.NextVisible(true))
                            do
                            {
                                if (SerializedProperty.EqualContents(child, end)) break;
                                if (IsMaterialReference(child)) { lists.Add((it.propertyPath, child.name)); break; }
                            } while (child.NextVisible(false));
                    }
                }
                else if (it.propertyType == SerializedPropertyType.Integer &&
                         name.IndexOf("TextureSize", StringComparison.OrdinalIgnoreCase) >= 0 &&
                         name.IndexOf("Offset", StringComparison.OrdinalIgnoreCase) < 0 &&
                         !it.propertyPath.Contains(".Array"))
                    sizes.Add(it.propertyPath);
                else if (it.propertyType == SerializedPropertyType.Boolean &&
                         name.IndexOf("MergeMaterial", StringComparison.OrdinalIgnoreCase) >= 0 && !it.propertyPath.Contains(".Array"))
                    merges.Add(it.propertyPath);
                else if (it.propertyType == SerializedPropertyType.ObjectReference && it.depth == 0 &&
                         name.IndexOf("TargetRoot", StringComparison.OrdinalIgnoreCase) >= 0)
                    layout.targetRoot = it.propertyPath;
            }
            serialized.Dispose();
            var chosen = lists.OrderByDescending(l => l.path.IndexOf("Select", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                                      l.path.IndexOf("Target", StringComparison.OrdinalIgnoreCase) >= 0)
                .FirstOrDefault(l => l.path.IndexOf("Limit", StringComparison.OrdinalIgnoreCase) < 0);
            if (chosen.path == null) layout.problems.Add("no list of target materials");
            else { layout.materials = chosen.path; layout.materialChild = chosen.child; }
            layout.size = sizes.OrderByDescending(s => s.IndexOf("Atlas", StringComparison.OrdinalIgnoreCase) >= 0).FirstOrDefault();
            if (layout.size == null) layout.problems.Add("no atlas texture size");
            layout.merge = merges.FirstOrDefault(m => m.EndsWith("MergeMaterials", StringComparison.OrdinalIgnoreCase)) ?? merges.FirstOrDefault();
            if (layout.problems.Count == 0) layoutCache = layout;
            return layout;
        }

        private static AtlasLayout RequireLayout(Component atlas, bool needsMerge)
        {
            var layout = Layout(atlas);
            var problems = layout.problems.ToList();
            if (needsMerge && layout.merge == null) problems.Add("no merge-materials switch");
            if (problems.Count > 0)
                throw new InvalidOperationException("DSH cannot set this TexTransTool version's AtlasTexture (" + string.Join(", ", problems) +
                    "). Read the avatar ('ttt') and set AtlasTexture up in Unity instead, or update DSH.");
            return layout;
        }

        private static Dictionary<string, object> DescribeAtlas(GameObject avatar)
        {
            var type = AtlasOrNull;
            var row = new Dictionary<string, object> { { "installed", type != null } };
            if (type == null) return row;
            row["type"] = type.FullName;
            row["components"] = avatar.GetComponentsInChildren<Component>(true)
                .Where(c => c != null && (c.GetType().Namespace ?? "").StartsWith(AtlasNamespace, StringComparison.Ordinal))
                .Select(c => (object)$"{DshReflect.PathIn(c.transform, avatar.transform)}: {c.GetType().Name}").Take(50).ToArray();
            WithTemporary(type, null, component =>
            {
                var layout = Layout(component);
                row["layout"] = new Dictionary<string, object>
                {
                    { "materials", layout.materials ?? "" }, { "materialChild", layout.materialChild ?? "" },
                    { "size", layout.size ?? "" }, { "merge", layout.merge ?? "" }, { "targetRoot", layout.targetRoot ?? "" },
                };
                row["supported"] = layout.problems.Count == 0;
                if (layout.problems.Count > 0) row["problems"] = layout.problems.ToArray();
            });
            return row;
        }

        private static void WriteAtlas(Component atlas, GameObject avatar, Material[] materials, int size, bool merge)
        {
            var layout = RequireLayout(atlas, merge);
            var serialized = new SerializedObject(atlas);
            if (layout.targetRoot != null) serialized.FindProperty(layout.targetRoot).objectReferenceValue = avatar;
            serialized.FindProperty(layout.size).intValue = size;
            if (layout.merge != null) serialized.FindProperty(layout.merge).boolValue = merge;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            // The material list: items are made with the item type's own defaults, so values such as a per-material
            // size factor are not left at zero, then the Material reference is set.
            var top = layout.materials.Split('.')[0];
            var field = atlas.GetType().GetField(top, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (field != null && !layout.materials.Contains(".") && typeof(IList).IsAssignableFrom(field.FieldType))
            {
                var itemType = field.FieldType.IsArray ? field.FieldType.GetElementType()
                    : field.FieldType.GetGenericArguments().FirstOrDefault()
                      ?? throw new InvalidOperationException("The AtlasTexture material list has no item type.");
                var items = materials.Select(material =>
                {
                    if (layout.materialChild == "") return (object)material;
                    var item = Activator.CreateInstance(itemType, true);
                    var child = itemType.GetField(layout.materialChild, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                        ?? throw new InvalidOperationException($"AtlasTexture items have no '{layout.materialChild}'.");
                    child.SetValue(item, material);
                    return item;
                }).ToArray();
                object list;
                if (field.FieldType.IsArray)
                {
                    var array = Array.CreateInstance(itemType, items.Length);
                    for (var i = 0; i < items.Length; i++) array.SetValue(items[i], i);
                    list = array;
                }
                else
                {
                    var made = (IList)Activator.CreateInstance(field.FieldType);
                    foreach (var item in items) made.Add(item);
                    list = made;
                }
                field.SetValue(atlas, list);
            }
            else
            {
                serialized.Update();
                var property = serialized.FindProperty(layout.materials);
                property.arraySize = materials.Length;
                for (var i = 0; i < materials.Length; i++)
                {
                    var item = property.GetArrayElementAtIndex(i);
                    (layout.materialChild == "" ? item : item.FindPropertyRelative(layout.materialChild)).objectReferenceValue = materials[i];
                }
                serialized.ApplyModifiedPropertiesWithoutUndo();
            }
            EditorUtility.SetDirty(atlas);
        }

        private static string ReadAtlas(Component atlas)
        {
            var layout = Layout(atlas);
            if (layout.problems.Count > 0) return "unknown";
            var serialized = new SerializedObject(atlas);
            var property = serialized.FindProperty(layout.materials);
            var materials = new List<string>();
            for (var i = 0; i < property.arraySize; i++)
            {
                var item = property.GetArrayElementAtIndex(i);
                var reference = (layout.materialChild == "" ? item : item.FindPropertyRelative(layout.materialChild))?.objectReferenceValue as Material;
                materials.Add(reference == null ? "None" : MaterialKey(reference));
            }
            var merge = layout.merge != null && serialized.FindProperty(layout.merge).boolValue;
            return GroupKey(materials, serialized.FindProperty(layout.size).intValue, merge);
        }

        private static string GroupKey(IEnumerable<string> materials, int size, bool merge) =>
            $"{size.ToString(CultureInfo.InvariantCulture)} {(merge ? "merge" : "keep")} [{string.Join(" | ", materials)}]";

        // ---- planning ----

        private sealed class GroupPlan
        {
            public Material[] materials;
            public int size;
            public bool merge;
            public string Key => GroupKey(materials.Select(MaterialKey), size, merge);
        }

        private static Material Resolve(Material[] all, string name)
        {
            var byPath = all.Where(m => AssetDatabase.GetAssetPath(m) == name).ToArray();
            if (byPath.Length == 1) return byPath[0];
            var byName = all.Where(m => m.name == name).ToArray();
            if (byName.Length == 1) return byName[0];
            throw new InvalidOperationException(byName.Length == 0
                ? $"The avatar has no material '{name}'. Read the avatar for the material names."
                : $"Several materials are named '{name}'. Use the asset path instead.");
        }

        /// <summary>The AtlasTexture groups the recipe asks for, in a fixed order.</summary>
        private static List<GroupPlan> Plan(GameObject avatar, Request request, Dictionary<string, object> result)
        {
            var all = AvatarMaterials(avatar).ToArray();
            var groups = new List<GroupPlan>();
            var used = new HashSet<Material>();
            foreach (var group in request.atlas ?? Array.Empty<Group>())
            {
                var materials = group.materials.Select(n => Resolve(all, n)).Distinct().ToArray();
                foreach (var m in materials)
                    if (!used.Add(m)) throw new InvalidOperationException($"'{m.name}' is in two atlas groups.");
                groups.Add(new GroupPlan { materials = materials, size = group.size, merge = group.merge });
            }
            var skipped = new List<object>();
            if (request.textureSize > 0)
            {
                var named = request.textureMaterials ?? Array.Empty<string>();
                var candidates = named.Contains("*") ? all : named.Select(n => Resolve(all, n)).Distinct().ToArray();
                var excluded = new HashSet<Material>((request.textureExclude ?? Array.Empty<string>()).Select(n => Resolve(all, n)));
                candidates = candidates.Where(m => !excluded.Contains(m) && !used.Contains(m)).ToArray();
                // Materials that share a texture go into one atlas, so the shared texture is not made twice.
                var sets = candidates.Select(m => new HashSet<Material> { m }).ToList();
                for (var merged = true; merged;)
                {
                    merged = false;
                    for (var i = 0; i < sets.Count && !merged; i++)
                        for (var j = i + 1; j < sets.Count && !merged; j++)
                        {
                            var a = new HashSet<Texture>(sets[i].SelectMany(m => DshAvatarScene.Textures(m).Select(t => t.texture)));
                            if (!sets[j].SelectMany(m => DshAvatarScene.Textures(m).Select(t => t.texture)).Any(a.Contains)) continue;
                            sets[i].UnionWith(sets[j]);
                            sets.RemoveAt(j);
                            merged = true;
                        }
                }
                foreach (var set in sets)
                {
                    var ordered = candidates.Where(set.Contains).ToArray();
                    var largest = ordered.SelectMany(m => DshAvatarScene.Textures(m)).Select(t => Math.Max(t.texture.width, t.texture.height))
                        .DefaultIfEmpty(0).Max();
                    if (largest <= request.textureSize)
                    {
                        skipped.AddRange(ordered.Select(m => (object)$"{m.name}: textures are {largest} or smaller"));
                        continue;
                    }
                    groups.Add(new GroupPlan { materials = ordered, size = request.textureSize, merge = false });
                }
            }
            result["groups"] = groups.Select(g => (object)new Dictionary<string, object>
            {
                { "materials", g.materials.Select(m => (object)m.name).ToArray() }, { "size", g.size }, { "merge", g.merge },
            }).ToArray();
            if (skipped.Count > 0) result["skipped"] = skipped.Take(50).ToArray();
            if (request.textureSize > 0 && !groups.Any() && !request.traceAndOptimize && !(request.atlas ?? Array.Empty<Group>()).Any())
                throw new InvalidOperationException($"Every chosen material's textures are already {request.textureSize} or smaller; nothing would change.");
            return groups;
        }

        // ---- the components ----

        private static bool Recorded(DshUndo[] undo, string key) => (undo ?? Array.Empty<DshUndo>()).Any(e => e.key == key);

        private static string HolderName(Request request) => HolderPrefix + request.name;

        /// <summary>Bring the avatar to the recipe; with write it changes the scene, otherwise lists what differs.</summary>
        private static List<string> Ensure(GameObject avatar, Request request, List<GroupPlan> groups, DshUndoLog log, bool write)
        {
            var changes = new List<string>();
            var traceRecorded = Recorded(request.undo, "aao:trace");
            if (request.traceAndOptimize || traceRecorded)
            {
                var type = request.traceAndOptimize ? Trace : DshVrc.LoadedType(TraceType);
                var trace = type == null ? null : avatar.GetComponent(type);
                if (request.traceAndOptimize)
                {
                    if (trace != null && !traceRecorded)
                    {
                        if ((request.aaoOptions ?? Array.Empty<Option>()).Length > 0)
                            throw new InvalidOperationException("The avatar already has Trace and Optimize that DSH did not add. Change its options in Unity, or leave 'aaoOptions' out.");
                    }
                    else
                    {
                        if (trace == null)
                        {
                            changes.Add("add AAO Trace and Optimize to the avatar");
                            if (write)
                            {
                                trace = avatar.AddComponent(type);
                                log?.Add(new DshUndo { key = "aao:trace", kind = "aao-trace", path = "" });
                            }
                        }
                        if (trace != null)
                        {
                            var set = SetOptions(trace, request.aaoOptions, write);
                            if (set.Length > 0) changes.Add("Trace and Optimize: " + set);
                        }
                    }
                }
                else if (trace != null)
                {
                    changes.Add("remove AAO Trace and Optimize");
                    if (write) UnityEngine.Object.DestroyImmediate(trace);
                }
            }

            var name = HolderName(request);
            var holder = DshVrc.FindHolder(avatar, name);
            var holderRecorded = Recorded(request.undo, "optimize:holder");
            if (holder != null && !holderRecorded)
                throw new InvalidOperationException($"The avatar already has an object named '{name}' that DSH did not add. Rename it or use another recipe name.");
            var wanted = groups.Select(g => g.Key).ToArray();
            var current = holder == null ? Array.Empty<string>() : holder.transform.Cast<Transform>()
                .Select(t => AtlasOrNull is Type atlasType && t.GetComponent(atlasType) is Component c ? ReadAtlas(c) : "none").ToArray();
            if (wanted.SequenceEqual(current) && (holder != null || wanted.Length == 0)) return changes;
            if (wanted.Length == 0)
            {
                changes.Add($"remove '{name}' (the TexTransTool atlases)");
                if (write) UnityEngine.Object.DestroyImmediate(holder);
                return changes;
            }
            changes.Add(holder == null ? $"add '{name}' with {wanted.Length} TexTransTool atlas(es)" : $"set up the atlases in '{name}' again");
            changes.AddRange(groups.Select((g, i) => $"  atlas {i + 1}: {g.materials.Length} material(s) at {g.size}{(g.merge ? ", merged into one" : "")}"));
            if (!write) return changes;
            var tttType = Atlas;
            if (holder != null) UnityEngine.Object.DestroyImmediate(holder);
            holder = new GameObject(name);
            holder.transform.SetParent(avatar.transform, false);
            log?.Add(new DshUndo { key = "optimize:holder", kind = "optimize-holder", path = name });
            for (var i = 0; i < groups.Count; i++)
            {
                var child = new GameObject($"Atlas {i + 1}");
                child.transform.SetParent(holder.transform, false);
                WriteAtlas(child.AddComponent(tttType), avatar, groups[i].materials, groups[i].size, groups[i].merge);
            }
            return changes;
        }

        private static List<string> Revert(GameObject avatar, Request request, bool write)
        {
            var changes = new List<string>();
            foreach (var entry in request.undo ?? Array.Empty<DshUndo>())
            {
                if (entry.kind == "aao-trace")
                {
                    var type = DshVrc.LoadedType(TraceType);
                    var trace = type == null ? null : avatar.GetComponent(type);
                    if (trace == null) continue;
                    changes.Add("remove AAO Trace and Optimize");
                    if (write) UnityEngine.Object.DestroyImmediate(trace);
                }
                else if (entry.kind == "optimize-holder")
                {
                    var holder = DshVrc.FindHolder(avatar, entry.path);
                    if (holder == null) continue;
                    changes.Add($"remove '{entry.path}'");
                    if (write) UnityEngine.Object.DestroyImmediate(holder);
                }
            }
            return changes;
        }

        // ---- building and measuring ----

        /// <summary>On a copy before its build: with the recipe, or with DSH's earlier components taken out.</summary>
        private static void Prepare(GameObject copy, Request request, List<GroupPlan> groups, bool withRecipe)
        {
            var recipe = JsonUtility.FromJson<Request>(JsonUtility.ToJson(request));
            if (withRecipe)
            {
                // The copy's materials are the same assets, so the plan's groups still apply.
                Ensure(copy, recipe, groups, null, true);
            }
            else
            {
                Revert(copy, recipe, true);
            }
        }

        private static Dictionary<string, object> BuiltCounts(GameObject avatar, Action<GameObject> prepare)
        {
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar, prepare);
                return Counts(copy);
            }
            finally
            {
                if (copy != null) UnityEngine.Object.DestroyImmediate(copy);
            }
        }

        private static readonly string[] Compared =
            { "triangles", "skinnedMeshes", "basicMeshes", "materialSlots", "textureMemoryMB", "textures", "bones", "physBoneComponents" };

        /// <summary>Counts of two built copies: without DSH's components and with the recipe.</summary>
        private static Dictionary<string, object> Compare(GameObject avatar, Request request, List<GroupPlan> groups, bool inScene)
        {
            var before = BuiltCounts(avatar, copy => Prepare(copy, request, groups, false));
            var after = inScene ? BuiltCounts(avatar, null) : BuiltCounts(avatar, copy => Prepare(copy, request, groups, true));
            var changes = Compared.ToDictionary(k => k, k => (object)$"{Format(before[k])} -> {Format(after[k])}");
            return new Dictionary<string, object>
            {
                { "before", before }, { "after", after }, { "changes", changes },
            };
        }

        private static string Format(object value) => Convert.ToString(value, CultureInfo.InvariantCulture);

        private static double Number(Dictionary<string, object> counts, string key) => Convert.ToDouble(counts[key], CultureInfo.InvariantCulture);

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Request request, List<GroupPlan> groups)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            try
            {
                var compare = Compare(avatar, request, groups, inScene: true);
                var before = (Dictionary<string, object>)compare["before"];
                var after = (Dictionary<string, object>)compare["after"];
                result["countsBeforeRecipe"] = before;
                result["countsAfterBuild"] = after;
                result["changes"] = compare["changes"];
                var problems = new List<string>();
                if (groups.Any() && Number(after, "textureMemoryMB") >= Number(before, "textureMemoryMB") &&
                    Number(after, "materialSlots") >= Number(before, "materialSlots"))
                    problems.Add("TexTransTool did not shrink textures or merge materials (check that TexTransTool and NDMF are installed and up to date, and look at the Unity log)");
                if (groups.Any(g => g.merge && g.materials.Length > 1) && Number(after, "materialSlots") >= Number(before, "materialSlots"))
                    problems.Add("the merged atlas did not lower the material slots");
                if (problems.Count > 0) throw new InvalidOperationException(string.Join("; ", problems) + ".");
                if (request.traceAndOptimize && !groups.Any() && Compared.All(k => Format(before[k]) == Format(after[k])))
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "Trace and Optimize changed none of the counts. The avatar may already be optimized, or AAO did not run; check the Unity log.";
                    return result;
                }
                result["status"] = "passed";
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            return result;
        }
    }
}
