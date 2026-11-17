// Read-only inspections that run in batch mode.
// Copy this file (and DshApply.cs) to <Project>/Assets/DSH/Editor/.
//
//   Unity.exe -batchmode -nographics -quit -projectPath <proj> \
//     -executeMethod DSH.Editor.DshInspect.CompileCheck
//
//   ... -executeMethod DSH.Editor.DshInspect.Perf
//   ... -executeMethod DSH.Editor.DshInspect.Dump
//
// Nothing here modifies the project.

using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Editor
{
    public static class DshInspect
    {
        // ---- entry points -------------------------------------------------

        public static void CompileCheck()
        {
            var data = NewResult("CompileCheck");
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
            var failed = EditorUtility.scriptCompilationFailed;
            data["ok"] = !failed;
            data["compileFailed"] = failed;
            if (failed)
            {
                data["error"] = "スクリプトのコンパイルに失敗しています。Unity のコンソールを確認してください。";
            }
            Finish("CompileCheck", data);
        }

        public static void Perf()
        {
            var data = NewResult("Perf");
            try
            {
                var records = new List<object>();
                foreach (var prefabPath in AvatarPrefabPaths())
                {
                    records.Add(MeasureAvatar(prefabPath, data));
                }
                data["avatars"] = records;
                data["ok"] = true;
                if (records.Count == 0)
                {
                    data["warning"] = "VRC_AvatarDescriptor を持つ prefab が見つかりませんでした。";
                }
            }
            catch (Exception e)
            {
                data["ok"] = false;
                data["error"] = e.ToString();
            }
            Finish("Perf", data);
        }

        public static void Dump()
        {
            var data = NewResult("Dump");
            try
            {
                var assets = new List<object>();
                foreach (var path in AvatarPrefabPaths())
                {
                    assets.Add(DumpPrefab(path));
                }
                data["assets"] = assets;
                data["ok"] = true;
            }
            catch (Exception e)
            {
                data["ok"] = false;
                data["error"] = e.ToString();
            }
            Finish("Dump", data);
        }

        // ---- helpers ------------------------------------------------------

        private static Dictionary<string, object> NewResult(string task)
        {
            return new Dictionary<string, object>
            {
                { "task", task },
                { "unity", Application.unityVersion },
                { "changes", new List<string>() },
            };
        }

        private static void Finish(string task, Dictionary<string, object> data)
        {
            var ok = data.TryGetValue("ok", out var v) && v is bool b && b;
            DSH.DshApply.WriteResult(task, data);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        private static bool IsAvatarDescriptor(Component c)
        {
            // SDK 3.x names the component VRCAvatarDescriptor; older SDKs used VRC_AvatarDescriptor.
            var name = c.GetType().Name;
            return name == "VRCAvatarDescriptor" || name == "VRC_AvatarDescriptor";
        }

        private static IEnumerable<string> AvatarPrefabPaths()
        {
            foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { "Assets" }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (string.IsNullOrEmpty(path) || !path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (go == null) continue;
                var hasDescriptor = go.GetComponentsInChildren<Component>(true)
                    .Any(c => c != null && IsAvatarDescriptor(c));
                if (hasDescriptor) yield return path;
            }
        }

        private static Dictionary<string, object> MeasureAvatar(string prefabPath, Dictionary<string, object> data)
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            var components = root.GetComponentsInChildren<Component>(true).Where(c => c != null).ToArray();

            long triangles = 0;
            int unreadableMeshes = 0;
            int materialSlots = 0;
            int skinnedMeshes = 0;
            int basicMeshes = 0;
            long textureBytes = 0;
            var textures = new HashSet<int>();

            foreach (var c in components)
            {
                Mesh mesh = null;
                Material[] materials = null;

                if (c is SkinnedMeshRenderer smr)
                {
                    skinnedMeshes++;
                    mesh = smr.sharedMesh;
                    materials = smr.sharedMaterials;
                }
                else if (c is MeshRenderer mr)
                {
                    basicMeshes++;
                    var mf = mr.GetComponent<MeshFilter>();
                    mesh = mf != null ? mf.sharedMesh : null;
                    materials = mr.sharedMaterials;
                }

                if (mesh != null)
                {
                    try
                    {
                        triangles += mesh.triangles.LongLength / 3;
                    }
                    catch
                    {
                        unreadableMeshes++; // Read/Write disabled: VRChat ranks this Very Poor anyway
                    }
                }

                if (materials != null)
                {
                    materialSlots += materials.Count(m => m != null);
                    foreach (var mat in materials)
                    {
                        if (mat == null) continue;
                        foreach (var texName in mat.GetTexturePropertyNames())
                        {
                            var tex = mat.GetTexture(texName);
                            if (tex == null) continue;
                            if (textures.Add(tex.GetInstanceID()))
                            {
                                textureBytes += (long)tex.width * tex.height * 4;
                            }
                        }
                    }
                }
            }

            int Count(string typeName) => components.Count(c => c.GetType().Name == typeName);

            var counts = new Dictionary<string, object>
            {
                { "triangles", triangles },
                { "unreadableMeshes", unreadableMeshes },
                { "skinnedMeshes", skinnedMeshes },
                { "basicMeshes", basicMeshes },
                { "materialSlots", materialSlots },
                { "textureMemoryMB", Math.Round(textureBytes / 1024.0 / 1024.0, 1) },
                { "physBoneComponents", Count("VRCPhysBone") },
                { "physBoneColliders", Count("VRCPhysBoneCollider") },
                { "contactSenders", Count("VRCContactSender") },
                { "contactReceivers", Count("VRCContactReceiver") },
                { "contacts", Count("VRCContactSender") + Count("VRCContactReceiver") },
                { "constraints", components.Count(c => c.GetType().Name.EndsWith("Constraint", StringComparison.Ordinal)) },
                { "animators", Count("Animator") },
                { "lights", Count("Light") },
                { "particleSystems", Count("ParticleSystem") },
                { "trailRenderers", Count("TrailRenderer") },
                { "lineRenderers", Count("LineRenderer") },
                { "audioSources", Count("AudioSource") },
            };

            DSH.DshApply.Note(data, $"measured {prefabPath}");
            return new Dictionary<string, object>
            {
                { "prefab", prefabPath },
                { "counts", counts },
            };
        }

        private static Dictionary<string, object> DumpPrefab(string prefabPath)
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            var nodes = new List<object>();
            void Walk(Transform t, int depth)
            {
                nodes.Add(new Dictionary<string, object>
                {
                    { "depth", depth },
                    { "name", t.name },
                    { "active", t.gameObject.activeSelf },
                    { "components", t.GetComponents<Component>()
                        .Where(c => c != null)
                        .Select(c => (object)c.GetType().Name)
                        .ToList() },
                });
                foreach (Transform child in t) Walk(child, depth + 1);
            }
            Walk(root.transform, 0);
            return new Dictionary<string, object> { { "prefab", prefabPath }, { "nodes", nodes } };
        }
    }
}
