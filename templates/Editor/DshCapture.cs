using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace DSH.Editor
{
    /// <summary>
    /// Read-only views of an avatar: before/after renders of a color variant, and UV wireframes of a texture.
    /// Nothing here saves the scene or any asset; images go to the run folder next to result.json.
    /// </summary>
    public static class DshCapture
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
            public string variant = "";
            public string views = "front,back,left,face";
            public string texture = "";
            public int size = 512;
            public Swap[] swaps = Array.Empty<Swap>();
            public DshMaterialEdit.Edit[] edits = Array.Empty<DshMaterialEdit.Edit>();
        }

        private const int CaptureLayer = 31;
        private static readonly string[] KnownViews = { "front", "back", "left", "right", "face" };

        /// <summary>Render the avatar from fixed angles; with a variant, a second row shows it swapped in.</summary>
        public static void Capture()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                RequireGraphics();
                var request = DshAvatarScene.ReadRequest<Request>();
                var views = ParseViews(request.views);
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var swaps = DshAvatarScene.LoadSwaps(request.swaps.Select(s => (s.from, s.to)));
                var edits = DshMaterialEdit.Load(request.edits);

                var swapped = 0;
                var visible = 0;
                var rows = new List<(string label, Func<GameObject, GameObject> make)>
                {
                    ("original", source => UnityEngine.Object.Instantiate(source))
                };
                if (swaps.Count + edits.Count > 0)
                    rows.Add((request.variant, source =>
                    {
                        var copy = UnityEngine.Object.Instantiate(source);
                        (swapped, visible) = SwapMaterials(copy, swaps, edits);
                        return copy;
                    }));
                var output = RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048), rows);
                if (rows.Count > 1 && swapped == 0)
                    throw new InvalidOperationException("No material on this avatar uses the original textures or materials of the variant.");
                result["image"] = output;
                result["columns"] = views;
                result["rows"] = rows.Select(r => r.label).ToArray();
                result["swappedSlots"] = swapped;
                if (rows.Count > 1)
                {
                    result["visibleSwappedSlots"] = visible;
                    if (visible == 0)
                        result["warning"] = "Every changed slot is on a hidden or disabled renderer, so both rows look the same. " +
                            "Check slots[].active in the materials output and change the material the visible renderer uses.";
                }
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Capture", result);
        }

        internal static void RequireGraphics()
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                throw new InvalidOperationException("Unity started without graphics. Capture needs a GPU (run without -nographics).");
        }

        internal static string[] ParseViews(string value)
        {
            var views = (value ?? "").Split(',').Select(v => v.Trim().ToLowerInvariant())
                .Where(v => v.Length > 0).Distinct().ToArray();
            if (views.Length == 0 || views.Any(v => !KnownViews.Contains(v)))
                throw new InvalidOperationException("Choose views from: " + string.Join(", ", KnownViews));
            return views;
        }

        /// <summary>
        /// Render one row per entry, top to bottom, into capture.png in the run folder. Each entry makes its own copy
        /// of the avatar (for example a material swap, or an SDK-built copy); the copy is destroyed after rendering.
        /// </summary>
        internal static string RenderSheet(GameObject avatar, string[] views, int size,
            IList<(string label, Func<GameObject, GameObject> make)> rows)
        {
            var sheet = new Texture2D(size * views.Length, size * rows.Count, TextureFormat.RGBA32, false);
            for (var row = 0; row < rows.Count; row++)
            {
                var copy = rows[row].make(avatar);
                try
                {
                    copy.transform.SetPositionAndRotation(new Vector3(0, -1000, 0), avatar.transform.rotation);
                    foreach (var t in copy.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = CaptureLayer;
                    foreach (var animator in copy.GetComponentsInChildren<Animator>(true)) animator.enabled = false;
                    for (var column = 0; column < views.Length; column++)
                    {
                        var pixels = Render(copy, avatar, views[column], size);
                        // Texture rows start at the bottom; put the first row on top.
                        sheet.SetPixels32(column * size, (rows.Count - 1 - row) * size, size, size, pixels);
                    }
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(copy);
                }
            }
            var output = Path.Combine(DshAvatarScene.RunDirectory, "capture.png");
            File.WriteAllBytes(output, sheet.EncodeToPNG());
            return output;
        }

        private static (int swapped, int visible) SwapMaterials(GameObject copy, Dictionary<Texture, Texture> swaps,
            Dictionary<Material, DshMaterialEdit.Edit[]> edits)
        {
            var copies = new Dictionary<Material, Material>();
            var count = 0;
            var visible = 0;
            foreach (var renderer in copy.GetComponentsInChildren<Renderer>(true))
            {
                var materials = renderer.sharedMaterials;
                var changed = false;
                for (var slot = 0; slot < materials.Length; slot++)
                {
                    var original = materials[slot];
                    if (!DshAvatarScene.InVariant(original, swaps, edits)) continue;
                    if (!copies.TryGetValue(original, out var variant))
                        copies[original] = variant = DshAvatarScene.VariantCopy(original, swaps, edits);
                    materials[slot] = variant;
                    changed = true;
                    count++;
                    if (renderer.enabled && renderer.gameObject.activeInHierarchy) visible++;
                }
                if (changed) renderer.sharedMaterials = materials;
            }
            return (count, visible);
        }

        private static Color32[] Render(GameObject copy, GameObject avatar, string view, int size)
        {
            var renderers = copy.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled).ToArray();
            if (renderers.Length == 0) throw new InvalidOperationException("The avatar has no active renderers to capture.");
            var bounds = renderers[0].bounds;
            foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);

            var root = copy.transform;
            var forward = root.forward;
            // Renderer bounds can be loose (skinned bounds, accessories); the eye height frames a body better.
            var descriptor = DshAvatarScene.Descriptor(avatar);
            var eyes = descriptor?.GetType().GetField("ViewPosition")?.GetValue(descriptor) is Vector3 v && v.y > 0.1f
                ? v : new Vector3(0, bounds.size.y * 0.9f, 0);
            var height = Mathf.Min(bounds.size.y, eyes.y * root.lossyScale.y / 0.9f);
            var target = new Vector3(bounds.center.x, root.position.y + height * 0.5f, bounds.center.z);
            var halfHeight = height * 0.56f;
            var direction = forward;
            if (view == "back") direction = -forward;
            else if (view == "left") direction = -root.right;
            else if (view == "right") direction = root.right;
            else if (view == "face")
            {
                target = root.TransformPoint(eyes);
                halfHeight = Mathf.Max(0.08f, height * 0.16f);
            }

            var cameraObject = new GameObject("DSH Capture Camera");
            var lightObject = new GameObject("DSH Capture Light");
            var texture = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB)
                { antiAliasing = 4 };
            var previous = RenderTexture.active;
            var ambientMode = RenderSettings.ambientMode;
            var ambientLight = RenderSettings.ambientLight;
            try
            {
                var camera = cameraObject.AddComponent<Camera>();
                camera.orthographic = true;
                camera.orthographicSize = halfHeight;
                camera.aspect = 1;
                camera.cullingMask = 1 << CaptureLayer;
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0.32f, 0.33f, 0.36f, 1);
                camera.nearClipPlane = 0.01f;
                camera.farClipPlane = 100;
                camera.transform.position = target + direction * 10;
                camera.transform.LookAt(target, Vector3.up);
                camera.targetTexture = texture;

                var light = lightObject.AddComponent<Light>();
                light.type = LightType.Directional;
                light.intensity = 1;
                light.color = Color.white;
                light.cullingMask = 1 << CaptureLayer;
                light.transform.rotation = Quaternion.LookRotation(-direction + Vector3.down * 0.6f, Vector3.up);
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(0.45f, 0.45f, 0.45f);

                camera.Render();
                RenderTexture.active = texture;
                var readback = new Texture2D(size, size, TextureFormat.RGBA32, false);
                readback.ReadPixels(new Rect(0, 0, size, size), 0, 0);
                readback.Apply();
                var pixels = readback.GetPixels32();
                UnityEngine.Object.DestroyImmediate(readback);
                return pixels;
            }
            finally
            {
                RenderTexture.active = previous;
                RenderSettings.ambientMode = ambientMode;
                RenderSettings.ambientLight = ambientLight;
                UnityEngine.Object.DestroyImmediate(cameraObject);
                UnityEngine.Object.DestroyImmediate(lightObject);
                texture.Release();
                UnityEngine.Object.DestroyImmediate(texture);
            }
        }

        /// <summary>Draw the UV edges of every mesh slot that uses one texture, to place decals and logos.</summary>
        public static void Uv()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var size = Mathf.Clamp(request.size, 256, 8192);
                var texture = AssetDatabase.LoadAssetAtPath<Texture>(request.texture)
                    ?? throw new InvalidOperationException($"Unity could not load the texture {request.texture}.");
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                var pixels = new Color32[size * size];
                var used = new List<Dictionary<string, object>>();
                foreach (var renderer in avatar.GetComponentsInChildren<Renderer>(true))
                {
                    var mesh = renderer is SkinnedMeshRenderer skinned ? skinned.sharedMesh
                        : renderer.GetComponent<MeshFilter>()?.sharedMesh;
                    if (mesh == null) continue;
                    var materials = renderer.sharedMaterials;
                    var uvs = mesh.uv;
                    for (var slot = 0; slot < materials.Length && slot < mesh.subMeshCount; slot++)
                    {
                        if (materials[slot] == null || !DshAvatarScene.Textures(materials[slot]).Any(t => t.texture == texture))
                            continue;
                        var triangles = mesh.GetTriangles(slot);
                        for (var i = 0; i + 2 < triangles.Length; i += 3)
                            for (var edge = 0; edge < 3; edge++)
                                Line(pixels, size, uvs[triangles[i + edge]], uvs[triangles[i + (edge + 1) % 3]]);
                        used.Add(new Dictionary<string, object>
                        {
                            { "renderer", AnimationUtility.CalculateTransformPath(renderer.transform, avatar.transform) },
                            { "slot", slot }, { "triangles", triangles.Length / 3 }
                        });
                    }
                }
                if (used.Count == 0) throw new InvalidOperationException($"No mesh slot on this avatar uses {request.texture}.");
                var image = new Texture2D(size, size, TextureFormat.RGBA32, false);
                image.SetPixels32(pixels);
                var output = Path.Combine(DshAvatarScene.RunDirectory, "uv.png");
                File.WriteAllBytes(output, image.EncodeToPNG());
                result["image"] = output;
                result["size"] = size;
                result["slots"] = used;
                result["note"] = "UV (0,0) is the bottom-left corner of the image. Recipes place images with uv: [u, v].";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("UvMap", result);
        }

        private static void Line(Color32[] pixels, int size, Vector2 a, Vector2 b)
        {
            int x0 = Pixel(a.x, size), y0 = Pixel(a.y, size), x1 = Pixel(b.x, size), y1 = Pixel(b.y, size);
            int dx = Math.Abs(x1 - x0), dy = -Math.Abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
            var error = dx + dy;
            var ink = new Color32(255, 64, 160, 255);
            for (var steps = 0; steps <= 2 * size; steps++)
            {
                pixels[y0 * size + x0] = ink;
                if (x0 == x1 && y0 == y1) break;
                var doubled = 2 * error;
                if (doubled >= dy) { error += dy; x0 += sx; }
                if (doubled <= dx) { error += dx; y0 += sy; }
            }
        }

        // UVs outside 0..1 wrap like a repeating texture.
        private static int Pixel(float value, int size) =>
            Mathf.Clamp(Mathf.FloorToInt((value - Mathf.Floor(value)) * size), 0, size - 1);
    }
}
