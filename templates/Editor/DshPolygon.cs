using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Fewer polygons at build time with Meshia (Meshia Mesh Simplifier on each renderer, NDMF): the meshes in the
    /// project stay as they are, and the build gets the reduced copies. A recipe gives a triangle goal for the whole
    /// avatar and/or a ratio per renderer; the face (Lip Sync mesh) and small meshes are kept unless named. Every
    /// added component and changed target is an undo entry, so remove puts back what was there before.
    /// </summary>
    public static class DshPolygon
    {
        [Serializable]
        private sealed class Target
        {
            public string path = "";
            public float ratio = 0;       // 0.05 - 1 of the renderer's triangles, or 0
            public int triangles = 0;     // an absolute count, or 0
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
            public int total = 0;             // the triangle goal for the whole avatar, or 0
            public bool keepFace = true;
            public int smallest = 1000;       // in "total", meshes with fewer triangles are left alone
            public bool preserveBorders = false;
            public string[] keep = Array.Empty<string>();
            public Target[] renderers = Array.Empty<Target>();
            public DshUndo[] undo = Array.Empty<DshUndo>();
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

        private const string SimplifierType = "Meshia.MeshSimplification.Ndmf.MeshiaMeshSimplifier";
        private const int AbsoluteTriangleCount = 5;   // MeshSimplificationTargetKind.AbsoluteTriangleCount
        private const float LowestRatio = 0.1f;

        private static Type Simplifier => DshVrc.LoadedType(SimplifierType)
            ?? throw new InvalidOperationException("Meshia is not installed. Add \"Meshia Mesh Simplification\" (com.ramtype0.meshia.mesh-simplification) in VCC/ALCOM.");

        /// <summary>Read-only: every mesh with its triangles, the face, and Meshia components already there.</summary>
        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var type = DshVrc.LoadedType(SimplifierType);
                result["meshia"] = type != null;
                var face = Face(avatar);
                result["renderers"] = Meshes(avatar).OrderByDescending(m => m.triangles).Select(m =>
                {
                    var row = new Dictionary<string, object>
                    {
                        { "path", m.path }, { "triangles", m.triangles }, { "skinned", m.renderer is SkinnedMeshRenderer },
                        { "face", m.renderer == face }, { "blendShapes", m.mesh.blendShapeCount },
                    };
                    var existing = type == null ? null : m.renderer.GetComponent(type);
                    if (existing != null) row["meshia"] = FormatTarget(ReadTarget(existing));
                    return (object)row;
                }).Take(200).ToArray();
                result["counts"] = DshInspect.MeasureCounts(avatar);
                result["note"] = "Counts are of the scene object before the build (Modular Avatar, VRCFury and AAO changes are not in them).";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Polygons", result);
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
                var plan = Plan(avatar, request, result);
                var log = new DshUndoLog();
                var changes = Ensure(avatar, request, plan, log);
                result["applied"] = changes;
                result["undo"] = DshUndo.DescribeAll(log.Entries);
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied polygon recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var earlier = request.undo ?? Array.Empty<DshUndo>();
                request.undo = earlier.Concat(log.Entries.Where(e => earlier.All(u => u.key != e.key))).ToArray();
                var remaining = Ensure(avatar, request, plan, null);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the recipe: " + string.Join("; ", remaining.Take(5)));
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, plan)
                    : new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("PolygonRecipe", result);
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
                var none = new Dictionary<string, int>();
                var changes = Ensure(avatar, request, none, null, write: true);
                result["reverted"] = changes;
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed polygon recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Ensure(avatar, request, none, null);
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
            DshAvatarScene.Finish("PolygonRemove", result);
        }

        /// <summary>Before and after the recipe, each built by the SDK (so Meshia runs), side by side.</summary>
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
                var plan = Plan(avatar, recipe, result);
                var triangles = new Dictionary<string, object>();
                GameObject Make(GameObject source, string label, bool withRecipe)
                {
                    var made = DshVrc.PreprocessCopy(source, copy => { if (withRecipe) Ensure(copy, recipe, plan, null, write: true); });
                    triangles[label] = DshInspect.MeasureCounts(made)["triangles"];
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
                result["trianglesAfterBuild"] = triangles;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("PolygonCapture", result);
        }

        // ---- planning ----

        private struct MeshInfo
        {
            public string path;
            public Renderer renderer;
            public Mesh mesh;
            public int triangles;
        }

        private static SkinnedMeshRenderer Face(GameObject avatar)
        {
            var descriptor = DshAvatarScene.Descriptor(avatar);
            return descriptor?.GetType().GetField("VisemeSkinnedMesh")?.GetValue(descriptor) as SkinnedMeshRenderer;
        }

        private static IEnumerable<MeshInfo> Meshes(GameObject avatar)
        {
            foreach (var renderer in avatar.GetComponentsInChildren<Renderer>(true))
            {
                var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh
                    : renderer is MeshRenderer ? renderer.GetComponent<MeshFilter>()?.sharedMesh : null;
                if (mesh == null) continue;
                var triangles = 0;
                for (var i = 0; i < mesh.subMeshCount; i++)
                    if (mesh.GetTopology(i) == MeshTopology.Triangles) triangles += (int)(mesh.GetIndexCount(i) / 3);
                yield return new MeshInfo { path = DshReflect.PathIn(renderer.transform, avatar.transform), renderer = renderer, mesh = mesh, triangles = triangles };
            }
        }

        /// <summary>The triangle target per renderer path that the recipe asks for.</summary>
        private static Dictionary<string, int> Plan(GameObject avatar, Request request, Dictionary<string, object> result)
        {
            var meshes = Meshes(avatar).ToList();
            var byPath = new Dictionary<string, MeshInfo>();
            foreach (var mesh in meshes)
            {
                if (byPath.ContainsKey(mesh.path))
                    throw new InvalidOperationException($"Two meshes are at '{mesh.path}'. Rename one so DSH can tell them apart.");
                byPath[mesh.path] = mesh;
            }
            var plan = new Dictionary<string, int>();
            foreach (var target in request.renderers)
            {
                if (!byPath.TryGetValue(target.path, out var mesh))
                    throw new InvalidOperationException($"No mesh at '{target.path}'. Read the avatar for the mesh paths.");
                var wanted = target.triangles > 0 ? target.triangles : Mathf.FloorToInt(mesh.triangles * target.ratio);
                plan[target.path] = Math.Max(1, Math.Min(mesh.triangles, wanted));
            }
            var face = Face(avatar);
            var kept = new List<string>();
            if (request.total > 0)
            {
                var keep = new HashSet<string>(request.keep ?? Array.Empty<string>());
                foreach (var path in keep)
                    if (!byPath.ContainsKey(path)) throw new InvalidOperationException($"No mesh at '{path}' to keep.");
                var others = meshes.Where(m => !plan.ContainsKey(m.path) && !keep.Contains(m.path) &&
                                               !(request.keepFace && m.renderer == face) && m.triangles >= request.smallest).ToList();
                kept.AddRange(meshes.Where(m => !plan.ContainsKey(m.path) && !others.Contains(m)).Select(m => m.path));
                var fixedCount = meshes.Where(m => !others.Contains(m)).Sum(m => plan.TryGetValue(m.path, out var t) ? t : m.triangles);
                var reducible = others.Sum(m => m.triangles);
                var before = meshes.Sum(m => m.triangles);
                result["trianglesBefore"] = before;
                if (before <= request.total) result["totalNote"] = $"The meshes have {before} triangles, already within {request.total}; only the named renderers change.";
                else if (reducible == 0) throw new InvalidOperationException("No mesh is left to reduce for the total (all are kept, named or small).");
                else
                {
                    var ratio = (float)(request.total - fixedCount) / reducible;
                    if (ratio < LowestRatio)
                        throw new InvalidOperationException($"Reaching {request.total} would leave only {Math.Max(0, ratio):P0} of the other meshes' triangles " +
                            $"({fixedCount} are kept or named). Raise the total, reduce the kept meshes too, or remove parts with vrc-shape-adjust.");
                    if (ratio < 1)
                        foreach (var mesh in others) plan[mesh.path] = Math.Max(1, Mathf.FloorToInt(mesh.triangles * ratio));
                    result["ratio"] = Math.Round(ratio, 3);
                }
            }
            result["kept"] = kept.Take(100).ToArray();
            result["targets"] = plan.Select(p => (object)new Dictionary<string, object>
            {
                { "path", p.Key }, { "before", byPath[p.Key].triangles }, { "after", p.Value },
            }).ToArray();
            result["trianglesPlanned"] = meshes.Sum(m => plan.TryGetValue(m.path, out var t) ? t : m.triangles);
            return plan;
        }

        // ---- the Meshia components ----

        private static (int kind, float value) ReadTarget(Component component)
        {
            var boxed = component.GetType().GetField("target").GetValue(component);
            var kind = Convert.ToInt32(boxed.GetType().GetField("Kind").GetValue(boxed));
            var value = Convert.ToSingle(boxed.GetType().GetField("Value").GetValue(boxed));
            return (kind, value);
        }

        private static void WriteTarget(Component component, int kind, float value)
        {
            var field = component.GetType().GetField("target")
                ?? throw new InvalidOperationException("This Meshia version stores its target differently. Update Meshia.");
            var boxed = field.GetValue(component);
            var kindField = boxed.GetType().GetField("Kind");
            kindField.SetValue(boxed, Enum.ToObject(kindField.FieldType, kind));
            boxed.GetType().GetField("Value").SetValue(boxed, value);
            field.SetValue(component, boxed);
            EditorUtility.SetDirty(component);
        }

        private static void PreserveBorders(Component component)
        {
            var field = component.GetType().GetField("options");
            if (field == null) return;
            var boxed = field.GetValue(component);
            boxed.GetType().GetField("PreserveBorderEdges")?.SetValue(boxed, true);
            field.SetValue(component, boxed);
        }

        private static string FormatTarget((int kind, float value) target) =>
            target.kind.ToString(CultureInfo.InvariantCulture) + ":" + target.value.ToString("R", CultureInfo.InvariantCulture);

        private static (int kind, float value) ParseTarget(string text)
        {
            var parts = (text ?? "").Split(':');
            return (int.Parse(parts[0], CultureInfo.InvariantCulture), float.Parse(parts[1], CultureInfo.InvariantCulture));
        }

        /// <summary>
        /// Bring the components to the plan; renderers the earlier record touched but the plan no longer names go
        /// back to how they were. With a log (or write) it changes the scene; without, it only lists what differs.
        /// </summary>
        private static List<string> Ensure(GameObject avatar, Request request, Dictionary<string, int> plan, DshUndoLog log, bool write = false)
        {
            write |= log != null;
            var type = Simplifier;
            var changes = new List<string>();
            var earlier = (request.undo ?? Array.Empty<DshUndo>()).Where(e => e.kind == "meshia-added" || e.kind == "meshia-target")
                .GroupBy(e => e.path).ToDictionary(g => g.Key, g => g.First());
            foreach (var entry in earlier.Values.Where(e => !plan.ContainsKey(e.path)))
            {
                var renderer = avatar.transform.Find(entry.path);
                if (renderer == null) continue;
                var component = renderer.GetComponent(type);
                if (entry.kind == "meshia-added")
                {
                    if (component == null) continue;
                    changes.Add($"{entry.path}: remove Meshia");
                    if (write) UnityEngine.Object.DestroyImmediate(component);
                }
                else if (component != null && FormatTarget(ReadTarget(component)) != entry.before)
                {
                    changes.Add($"{entry.path}: Meshia target back to {entry.before}");
                    var (kind, value) = ParseTarget(entry.before);
                    if (write) WriteTarget(component, kind, value);
                }
            }
            foreach (var pair in plan)
            {
                var renderer = avatar.transform.Find(pair.Key)
                    ?? throw new InvalidOperationException($"No mesh at '{pair.Key}'.");
                var component = renderer.GetComponent(type);
                if (component == null)
                {
                    changes.Add($"{pair.Key}: add Meshia ({pair.Value} triangles)");
                    if (!write) continue;
                    component = renderer.gameObject.AddComponent(type);
                    if (request.preserveBorders) PreserveBorders(component);
                    log?.Add(new DshUndo { key = "meshia:" + pair.Key, kind = "meshia-added", path = pair.Key });
                }
                else
                {
                    var current = ReadTarget(component);
                    if (current.kind == AbsoluteTriangleCount && Mathf.RoundToInt(current.value) == pair.Value) continue;
                    changes.Add($"{pair.Key}: Meshia target {FormatTarget(current)} -> {pair.Value} triangles");
                    if (!write) continue;
                    log?.Add(new DshUndo { key = "meshia:" + pair.Key, kind = "meshia-target", path = pair.Key, before = FormatTarget(current) });
                }
                WriteTarget(component, AbsoluteTriangleCount, pair.Value);
            }
            return changes;
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Dictionary<string, int> plan)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                var before = Meshes(avatar).ToDictionary(m => m.path, m => m.triangles);
                copy = DshVrc.PreprocessCopy(avatar);
                var after = Meshes(copy).GroupBy(m => m.path).ToDictionary(g => g.Key, g => g.First().triangles);
                var rows = plan.Select(p => (object)new Dictionary<string, object>
                {
                    { "path", p.Key }, { "before", before.TryGetValue(p.Key, out var b) ? b : -1 }, { "target", p.Value },
                    { "afterBuild", after.TryGetValue(p.Key, out var a) ? a : -1 },
                }).ToArray();
                result["renderers"] = rows;
                result["countsAfterBuild"] = DshInspect.MeasureCounts(copy);
                var unreduced = plan.Where(p => after.TryGetValue(p.Key, out var a) && before.TryGetValue(p.Key, out var b) && p.Value < b && a >= b)
                    .Select(p => p.Key).ToArray();
                if (unreduced.Length > 0)
                    throw new InvalidOperationException("Meshia did not reduce: " + string.Join(", ", unreduced.Take(8)) + ". Check that Meshia and NDMF are installed and up to date.");
                // Modular Avatar moves attached items under bones and Avatar Optimizer merges meshes, so some paths
                // are gone after the build; then the whole avatar's count tells whether Meshia reduced them.
                var missing = plan.Keys.Where(p => !after.ContainsKey(p)).ToArray();
                if (missing.Length > 0)
                {
                    var planned = before.Sum(m => plan.TryGetValue(m.Key, out var t) ? t : m.Value);
                    var built = Convert.ToInt64(((Dictionary<string, object>)result["countsAfterBuild"])["triangles"]);
                    result["movedByBuild"] = missing.Take(20).ToArray();
                    result["trianglesPlanned"] = planned;
                    if (built > planned + Math.Max(50, planned / 100))
                    {
                        result["status"] = "inconclusive";
                        result["reason"] = $"A build plugin merged or moved {string.Join(", ", missing.Take(8))}, and the built avatar has {built} triangles, more than the {planned} planned. Check the rank in the SDK build panel.";
                        return result;
                    }
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
    }
}
