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
    /// Shape adjustments that keep the source FBX unchanged: blendshape weights saved in the scene, Modular Avatar
    /// Blendshape Sync (outfits follow the body), and Avatar Optimizer Remove Mesh By BlendShape (hidden body parts
    /// are removed at build time).
    /// </summary>
    public static class DshShape
    {
        [Serializable]
        private sealed class Weight
        {
            public string renderer = "";
            public string shape = "";
            public float weight = 0;
        }

        [Serializable]
        private sealed class Sync
        {
            public string renderer = "";
            public string source = "";
            public string[] shapes = Array.Empty<string>();
        }

        [Serializable]
        private sealed class Removal
        {
            public string renderer = "";
            public string[] shapes = Array.Empty<string>();
            public float tolerance = 0.001f;
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string filter = "";
            public string name = "";
            public bool verifySdk = false;
            public Weight[] weights = Array.Empty<Weight>();
            public Sync[] sync = Array.Empty<Sync>();
            public Removal[] remove = Array.Empty<Removal>();
        }

        private const string SyncType = "nadena.dev.modular_avatar.core.ModularAvatarBlendshapeSync";
        private const string RemoveType = "Anatawa12.AvatarOptimizer.RemoveMeshByBlendShape";
        private const int MaxShapes = 400;

        /// <summary>Read-only: skinned meshes of one avatar with their blendshapes, weights and shape components.</summary>
        public static void Shapes()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var filter = request.filter ?? "";
                var listed = 0;
                var renderers = new List<Dictionary<string, object>>();
                foreach (var renderer in avatar.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    var mesh = renderer.sharedMesh;
                    if (mesh == null) continue;
                    var path = AnimationUtility.CalculateTransformPath(renderer.transform, avatar.transform);
                    var rendererMatches = filter.Length == 0 || path.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0;
                    var shapes = new List<object>();
                    for (var i = 0; i < mesh.blendShapeCount; i++)
                    {
                        var name = mesh.GetBlendShapeName(i);
                        if (!rendererMatches && name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                        if (listed++ >= MaxShapes) break;
                        var weight = renderer.GetBlendShapeWeight(i);
                        shapes.Add(weight == 0 ? (object)name : new Dictionary<string, object> { { "name", name }, { "weight", weight } });
                    }
                    if (!rendererMatches && shapes.Count == 0) continue;
                    var entry = new Dictionary<string, object>
                    {
                        { "renderer", path }, { "active", renderer.gameObject.activeInHierarchy },
                        { "triangles", mesh.triangles.Length / 3 }, { "shapeCount", mesh.blendShapeCount }, { "shapes", shapes }
                    };
                    var sync = SyncBindings(renderer.gameObject);
                    if (sync.Count > 0) entry["blendshapeSync"] = sync;
                    var removing = RemovedShapes(renderer.gameObject);
                    if (removing.Count > 0) entry["removeMeshByBlendShape"] = removing;
                    renderers.Add(entry);
                }
                result["renderers"] = renderers;
                result["truncated"] = listed > MaxShapes;
                result["note"] = "Shapes listed by name have weight 0; others show their saved weight.";
                result["modularAvatar"] = DshVrc.LoadedType(SyncType) != null;
                result["avatarOptimizer"] = DshVrc.LoadedType(RemoveType) != null;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Shapes", result);
        }

        /// <summary>Apply a shape recipe to the avatar in the saved scene, save it, and check it from a fresh load.</summary>
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
                var changes = ApplyRecipe(avatar, request);
                result["applied"] = changes;
                if (changes.Count > 0)
                {
                    DshAvatarScene.RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Applied shape recipe {request.name} ({changes.Count} changes)");
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                // Applying the recipe again to the saved scene must change nothing.
                var remaining = ApplyRecipe(avatar, request);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the recipe: " + string.Join("; ", remaining.Take(5)));
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
            DshAvatarScene.Finish("ShapeRecipe", result);
        }

        /// <summary>
        /// Before/after renders without saving. With build, both rows are SDK-built copies, so Blendshape Sync and
        /// Remove Mesh By BlendShape show as they will in VRChat, and each row reports its triangle count.
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
                GameObject Make(GameObject source, string label, bool withRecipe)
                {
                    Action<GameObject> prepare = copy => { if (withRecipe) ApplyRecipe(copy, recipe); };
                    GameObject made;
                    if (request.build) made = DshVrc.PreprocessCopy(source, prepare);
                    else
                    {
                        made = UnityEngine.Object.Instantiate(source);
                        prepare(made);
                    }
                    triangles[label] = Triangles(made);
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
                result["built"] = request.build;
                result["triangles"] = triangles;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("ShapeCapture", result);
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

        private static int Triangles(GameObject root)
        {
            var total = 0;
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled))
            {
                var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh
                    : renderer.GetComponent<MeshFilter>()?.sharedMesh;
                if (mesh != null) total += mesh.triangles.Length / 3;
            }
            return total;
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                result["trianglesInScene"] = Triangles(avatar);
                copy = DshVrc.PreprocessCopy(avatar);
                result["trianglesAfterBuild"] = Triangles(copy);
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

        /// <summary>Make the avatar (or a copy of it) match the recipe; returns what had to change.</summary>
        private static List<string> ApplyRecipe(GameObject avatar, Request recipe)
        {
            var changes = new List<string>();
            foreach (var item in recipe.weights)
            {
                var renderer = FindRenderer(avatar, item.renderer);
                var index = ShapeIndex(renderer, item.shape, item.renderer);
                var weight = Mathf.Clamp(item.weight, 0, 100);
                if (Mathf.Approximately(renderer.GetBlendShapeWeight(index), weight)) continue;
                renderer.SetBlendShapeWeight(index, weight);
                EditorUtility.SetDirty(renderer);
                changes.Add($"{item.renderer}: {item.shape} = {weight}");
            }
            foreach (var item in recipe.sync)
                changes.AddRange(AddSync(avatar, item));
            foreach (var item in recipe.remove)
                changes.AddRange(AddRemoval(avatar, item));
            return changes;
        }

        private static SkinnedMeshRenderer FindRenderer(GameObject avatar, string path)
        {
            var renderer = avatar.transform.Find(path)?.GetComponent<SkinnedMeshRenderer>();
            if (renderer == null || renderer.sharedMesh == null)
                throw new InvalidOperationException($"No skinned mesh at '{path}' under the avatar. Use a renderer path from the shapes command.");
            return renderer;
        }

        private static int ShapeIndex(SkinnedMeshRenderer renderer, string shape, string path)
        {
            var index = renderer.sharedMesh.GetBlendShapeIndex(shape);
            if (index < 0) throw new InvalidOperationException($"'{path}' has no blendshape named '{shape}'.");
            return index;
        }

        /// <summary>
        /// Pair a source shape with the target's shape: "Source=Target", the same name, or the one target shape that
        /// ends with "_" + the source name (outfits often prefix their copy, e.g. Hoodie_Breasts_big).
        /// </summary>
        private static (string source, string local) SyncPair(SkinnedMeshRenderer target, string value, string path)
        {
            var parts = value.Split(new[] { '=' }, 2);
            var source = parts[0].Trim();
            if (parts.Length == 2) return (source, parts[1].Trim());
            var mesh = target.sharedMesh;
            var names = Enumerable.Range(0, mesh.blendShapeCount).Select(mesh.GetBlendShapeName).ToArray();
            if (names.Contains(source)) return (source, source);
            var suffixed = names.Where(n => n.EndsWith("_" + source, StringComparison.Ordinal)).ToArray();
            if (suffixed.Length == 1) return (source, suffixed[0]);
            throw new InvalidOperationException(suffixed.Length == 0
                ? $"'{path}' has no blendshape for '{source}'. Write 'Source=Target' to pair them."
                : $"'{path}' has several blendshapes ending with '_{source}'. Write 'Source=Target' to pick one.");
        }

        private static List<string> AddSync(GameObject avatar, Sync item)
        {
            var type = DshVrc.LoadedType(SyncType)
                ?? throw new InvalidOperationException("Modular Avatar is not installed. Add it in VCC/ALCOM to sync blendshapes.");
            var target = FindRenderer(avatar, item.renderer);
            var source = FindRenderer(avatar, item.source);
            var field = type.GetField("Bindings");
            var bindingType = field.FieldType.GetGenericArguments()[0];
            var referenceType = bindingType.GetField("ReferenceMesh").FieldType;
            var component = target.GetComponent(type);
            var changes = new List<string>();
            foreach (var value in item.shapes)
            {
                var (sourceShape, local) = SyncPair(target, value, item.renderer);
                ShapeIndex(source, sourceShape, item.source);
                var localIndex = ShapeIndex(target, local, item.renderer);
                var existing = component == null ? Enumerable.Empty<object>()
                    : ((IEnumerable)field.GetValue(component)).Cast<object>();
                var bound = existing.FirstOrDefault(b => (string)bindingType.GetField("LocalBlendshape").GetValue(b) == local
                    || (string.IsNullOrEmpty((string)bindingType.GetField("LocalBlendshape").GetValue(b)) &&
                        (string)bindingType.GetField("Blendshape").GetValue(b) == local));
                if (bound != null)
                {
                    var reference = bindingType.GetField("ReferenceMesh").GetValue(bound);
                    var boundSource = (string)bindingType.GetField("Blendshape").GetValue(bound);
                    var boundPath = referenceType.GetField("referencePath").GetValue(reference) as string;
                    if (boundSource == sourceShape && boundPath == item.source) continue;
                    throw new InvalidOperationException($"'{item.renderer}:{local}' already follows '{boundPath}:{boundSource}'.");
                }
                if (component == null) component = target.gameObject.AddComponent(type);
                var reference2 = Activator.CreateInstance(referenceType);
                referenceType.GetMethod("Set", new[] { typeof(GameObject) }).Invoke(reference2, new object[] { source.gameObject });
                var binding = Activator.CreateInstance(bindingType);
                bindingType.GetField("ReferenceMesh").SetValue(binding, reference2);
                bindingType.GetField("Blendshape").SetValue(binding, sourceShape);
                bindingType.GetField("LocalBlendshape").SetValue(binding, local);
                ((IList)field.GetValue(component)).Add(binding);
                // Show the synced value right away; MA keeps it in sync at build time.
                target.SetBlendShapeWeight(localIndex, source.GetBlendShapeWeight(ShapeIndex(source, sourceShape, item.source)));
                EditorUtility.SetDirty(component);
                EditorUtility.SetDirty(target);
                changes.Add($"{item.renderer}: {local} follows {item.source}:{sourceShape}");
            }
            return changes;
        }

        private static List<string> AddRemoval(GameObject avatar, Removal item)
        {
            var type = DshVrc.LoadedType(RemoveType)
                ?? throw new InvalidOperationException("Avatar Optimizer is not installed. Add it in VCC/ALCOM to remove hidden meshes.");
            var renderer = FindRenderer(avatar, item.renderer);
            foreach (var shape in item.shapes) ShapeIndex(renderer, shape, item.renderer);
            var changes = new List<string>();
            var component = renderer.GetComponent(type);
            if (component == null)
            {
                component = renderer.gameObject.AddComponent(type);
                type.GetMethod("Initialize")?.Invoke(component, new object[] { 1 });
                changes.Add($"{item.renderer}: added Remove Mesh By BlendShape");
            }
            var tolerance = (double)Mathf.Clamp(item.tolerance, 0.000001f, 1f);
            var toleranceProperty = type.GetProperty("Tolerance");
            if (Math.Abs((double)toleranceProperty.GetValue(component) - tolerance) > 1e-9)
            {
                toleranceProperty.SetValue(component, tolerance);
                changes.Add($"{item.renderer}: tolerance {tolerance}");
            }
            var keys = (ICollection<string>)type.GetProperty("ShapeKeys").GetValue(component);
            foreach (var shape in item.shapes.Where(s => !keys.Contains(s)))
            {
                keys.Add(shape);
                changes.Add($"{item.renderer}: remove mesh moved by {shape}");
            }
            if (changes.Count > 0) EditorUtility.SetDirty(component);
            return changes;
        }

        private static List<string> SyncBindings(GameObject target)
        {
            var found = new List<string>();
            var type = DshVrc.LoadedType(SyncType);
            if (type == null) return found;
            foreach (var component in target.GetComponents(type))
                foreach (var binding in (IEnumerable)type.GetField("Bindings").GetValue(component))
                {
                    var reference = binding.GetType().GetField("ReferenceMesh").GetValue(binding);
                    var source = reference?.GetType().GetField("referencePath")?.GetValue(reference) as string;
                    found.Add($"{source}:{binding.GetType().GetField("Blendshape").GetValue(binding)}");
                }
            return found;
        }

        private static List<string> RemovedShapes(GameObject target)
        {
            var found = new List<string>();
            var type = DshVrc.LoadedType(RemoveType);
            if (type == null) return found;
            foreach (var component in target.GetComponents(type))
                if (type.GetProperty("ShapeKeys")?.GetValue(component) is IEnumerable<string> keys)
                    found.AddRange(keys);
            return found;
        }
    }
}
