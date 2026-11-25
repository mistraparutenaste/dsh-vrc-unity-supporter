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
    /// An Android (Quest) version of the avatar with VRCQuestTools, without a copy in the scene: "VQT Avatar
    /// Converter Settings" on the avatar root makes the Android build use mobile shaders and smaller textures, and
    /// "VQT Platform Component Remover" on chosen objects drops their PhysBones, colliders and contacts from the
    /// Android build only. PC builds are not changed. Try builds a scene copy as Android (VQT Platform Target
    /// Settings on the copy) and measures it, so the rank can be seen before anything is saved.
    /// </summary>
    public static class DshQuest
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string name = "";
            public bool verifySdk = false;
            public string shader = "toonStandard";   // toonStandard or toonLit
            public int textureSize = 1024;           // 256, 512, 1024 or 2048
            public float brightness = 0.83f;         // toonLit only
            public string[] removeOnAndroid = Array.Empty<string>();
            public DshUndo[] undo = Array.Empty<DshUndo>();
            public bool withRecipe = true;           // try: false measures the Android build as the scene is
        }

        private const string ConverterType = "KRT.VRCQuestTools.Components.AvatarConverterSettings";
        private const string RemoverType = "KRT.VRCQuestTools.Components.PlatformComponentRemover";
        private const string TargetType = "KRT.VRCQuestTools.Components.PlatformTargetSettings";
        private const string ToonStandardType = "KRT.VRCQuestTools.Models.ToonStandardConvertSettings";
        private const string ToonLitType = "KRT.VRCQuestTools.Models.ToonLitConvertSettings";
        private static readonly string[] Dynamics = { "VRCPhysBone", "VRCPhysBoneCollider", "VRCContactSender", "VRCContactReceiver" };

        private static Type Required(string name) => DshVrc.LoadedType(name)
            ?? throw new InvalidOperationException("VRCQuestTools is not installed (or is older than 2.x). Add VRCQuestTools (com.github.kurotu.vrc-quest-tools) in VCC/ALCOM.");

        /// <summary>Read-only: materials and shaders, PhysBones and contacts, and what is set up for Android already.</summary>
        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                result["vrcQuestTools"] = DshVrc.LoadedType(ConverterType) != null;
                result["androidModule"] = BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android);
                result["activeBuildTarget"] = EditorUserBuildSettings.activeBuildTarget.ToString();
                var converter = DshVrc.LoadedType(ConverterType);
                result["converterSettings"] = converter != null && avatar.GetComponent(converter) != null;
                result["dynamics"] = DynamicsOf(avatar).Take(200).ToArray();
                result["materials"] = Materials(avatar).Take(200).ToArray();
                result["counts"] = DshInspect.MeasureCounts(avatar);
                result["note"] = "Counts are of the PC avatar in the scene; 'try' builds it as Android and measures that.";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Quest", result);
        }

        /// <summary>Read-only: build a copy as Android (with the recipe, unless withRecipe is off) and measure it.</summary>
        public static void Try()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["android"] = BuildAndroid(avatar, request.withRecipe ? request : null);
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("QuestTry", result);
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
                var log = new DshUndoLog();
                var changes = Ensure(avatar, request, log, true);
                result["applied"] = changes;
                result["undo"] = DshUndo.DescribeAll(log.Entries);
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied Quest recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var earlier = request.undo ?? Array.Empty<DshUndo>();
                request.undo = earlier.Concat(log.Entries.Where(e => earlier.All(u => u.key != e.key))).ToArray();
                var remaining = Ensure(avatar, request, null, false);
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
            DshAvatarScene.Finish("QuestRecipe", result);
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
                var changes = Revert(avatar, request.undo, true);
                result["reverted"] = changes;
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed Quest recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Revert(avatar, request.undo, false);
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
            DshAvatarScene.Finish("QuestRemove", result);
        }

        // ---- reading ----

        private static IEnumerable<object> DynamicsOf(GameObject avatar) =>
            avatar.GetComponentsInChildren<Component>(true).Where(c => c != null && Dynamics.Contains(c.GetType().Name))
                .GroupBy(c => c.gameObject).Select(g => (object)new Dictionary<string, object>
                {
                    { "path", DshReflect.PathIn(g.Key.transform, avatar.transform) },
                    { "components", g.Select(c => c.GetType().Name).ToArray() },
                    { "transforms", g.Key.GetComponentsInChildren<Transform>(true).Length },
                });

        private static IEnumerable<object> Materials(GameObject avatar) =>
            avatar.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Distinct()
                .Select(m => (object)new Dictionary<string, object>
                {
                    { "material", m.name }, { "shader", m.shader != null ? m.shader.name : "" },
                    { "mobile", IsMobile(m) },
                });

        private static bool IsMobile(Material material) =>
            material.shader != null && material.shader.name.StartsWith("VRChat/Mobile/", StringComparison.Ordinal);

        // ---- the VQT components ----

        private static object Field(object target, string name) =>
            target?.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(target);

        private static void Set(object target, string name, object value)
        {
            var field = target.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                ?? throw new InvalidOperationException($"This VRCQuestTools version has no '{name}' on {target.GetType().Name}. Update VRCQuestTools.");
            field.SetValue(target, field.FieldType.IsEnum ? Enum.ToObject(field.FieldType, value) : value);
        }

        private static string Describe(object settings)
        {
            if (settings == null) return "none";
            var size = Convert.ToInt32(Field(settings, "maxTextureSize") ?? 0);
            var text = settings.GetType().Name + " " + size.ToString(CultureInfo.InvariantCulture);
            if (settings.GetType().FullName == ToonLitType)
                text += " " + Convert.ToSingle(Field(settings, "mainTextureBrightness") ?? 0f).ToString("0.###", CultureInfo.InvariantCulture);
            return text;
        }

        private static object NewSettings(Request request)
        {
            var lit = request.shader == "toonLit";
            var type = Required(lit ? ToonLitType : ToonStandardType);
            var settings = type.GetProperty("Default", BindingFlags.Public | BindingFlags.Static)?.GetValue(null)
                           ?? Activator.CreateInstance(type, true);
            Set(settings, "maxTextureSize", request.textureSize);
            if (lit) Set(settings, "mainTextureBrightness", request.brightness);
            type.GetMethod("LoadDefaultAssets", BindingFlags.Public | BindingFlags.Instance)?.Invoke(settings, null);
            return settings;
        }

        private static bool Recorded(DshUndo[] undo, string key) => (undo ?? Array.Empty<DshUndo>()).Any(e => e.key == key);

        /// <summary>Bring the avatar to the recipe; with write it changes the scene, otherwise lists what differs.</summary>
        private static List<string> Ensure(GameObject avatar, Request request, DshUndoLog log, bool write)
        {
            var changes = new List<string>();
            var converterType = Required(ConverterType);
            var removerType = Required(RemoverType);
            var converter = avatar.GetComponent(converterType);
            if (converter != null && !Recorded(request.undo, "vqt:converter"))
                throw new InvalidOperationException("The avatar already has VQT Avatar Converter Settings that DSH did not add. Change them in Unity, or remove them first.");
            var wanted = Describe(NewSettings(request));
            if (converter == null)
            {
                changes.Add($"add VQT Avatar Converter Settings ({wanted})");
                if (write)
                {
                    converter = avatar.AddComponent(converterType);
                    log?.Add(new DshUndo { key = "vqt:converter", kind = "vqt-converter", path = "" });
                }
            }
            if (converter != null && Describe(Field(converter, "defaultMaterialConvertSettings")) != wanted)
            {
                if (!changes.Any()) changes.Add($"materials: {Describe(Field(converter, "defaultMaterialConvertSettings"))} -> {wanted}");
                if (write)
                {
                    Set(converter, "defaultMaterialConvertSettings", NewSettings(request));
                    EditorUtility.SetDirty(converter);
                }
            }

            // Platform Component Removers: one per named object; earlier ones the recipe no longer names go.
            var named = new HashSet<string>(request.removeOnAndroid ?? Array.Empty<string>());
            foreach (var entry in (request.undo ?? Array.Empty<DshUndo>()).Where(e => e.kind == "vqt-remover" && !named.Contains(e.path)))
            {
                var holder = avatar.transform.Find(entry.path);
                var component = holder == null ? null : holder.GetComponent(removerType);
                if (component == null) continue;
                changes.Add($"{entry.path}: keep its dynamics on Android again");
                if (write) UnityEngine.Object.DestroyImmediate(component);
            }
            foreach (var path in named)
            {
                var target = avatar.transform.Find(path) ?? throw new InvalidOperationException($"No object at '{path}'.");
                var found = target.GetComponents<Component>().Where(c => c != null && Dynamics.Contains(c.GetType().Name)).ToArray();
                if (found.Length == 0) throw new InvalidOperationException($"'{path}' has no PhysBone, collider or contact.");
                var remover = target.GetComponent(removerType);
                if (remover != null && !Recorded(request.undo, "vqt:remover:" + path))
                    throw new InvalidOperationException($"'{path}' already has a VQT Platform Component Remover that DSH did not add. Set it in Unity instead.");
                if (remover == null)
                {
                    changes.Add($"{path}: remove {string.Join(", ", found.Select(c => c.GetType().Name))} on Android");
                    if (!write) continue;
                    remover = target.gameObject.AddComponent(removerType);
                    log?.Add(new DshUndo { key = "vqt:remover:" + path, kind = "vqt-remover", path = path });
                }
                var items = Field(remover, "componentSettings") as IEnumerable;
                var removed = items?.Cast<object>().Where(i => Convert.ToBoolean(Field(i, "removeOnAndroid")))
                    .Select(i => Field(i, "component") as Component).ToArray() ?? Array.Empty<Component>();
                if (found.All(removed.Contains)) continue;
                if (!changes.Any(c => c.StartsWith(path + ":", StringComparison.Ordinal)))
                    changes.Add($"{path}: remove {string.Join(", ", found.Select(c => c.GetType().Name))} on Android");
                if (!write) continue;
                remover.GetType().GetMethod("UpdateComponentSettings", BindingFlags.Public | BindingFlags.Instance)?.Invoke(remover, null);
                foreach (var item in (Field(remover, "componentSettings") as IEnumerable)?.Cast<object>() ?? Enumerable.Empty<object>())
                    if (Field(item, "component") is Component c && Dynamics.Contains(c.GetType().Name))
                        Set(item, "removeOnAndroid", true);
                EditorUtility.SetDirty(remover);
            }
            return changes;
        }

        private static List<string> Revert(GameObject avatar, DshUndo[] undo, bool write)
        {
            var changes = new List<string>();
            foreach (var entry in undo ?? Array.Empty<DshUndo>())
            {
                var type = DshVrc.LoadedType(entry.kind == "vqt-converter" ? ConverterType : RemoverType);
                if (type == null || (entry.kind != "vqt-converter" && entry.kind != "vqt-remover")) continue;
                var holder = entry.path == "" ? avatar.transform : avatar.transform.Find(entry.path);
                var component = holder == null ? null : holder.GetComponent(type);
                if (component == null) continue;
                changes.Add($"remove {type.Name} from '{(entry.path == "" ? avatar.name : entry.path)}'");
                if (write) UnityEngine.Object.DestroyImmediate(component);
            }
            return changes;
        }

        // ---- building as Android ----

        /// <summary>
        /// Build a copy with VQT Platform Target Settings set to Android, so VQT converts it as for an Android
        /// upload while Unity stays on the PC target, and measure the result.
        /// </summary>
        private static Dictionary<string, object> BuildAndroid(GameObject avatar, Request recipe)
        {
            var targetType = Required(TargetType);
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar, made =>
                {
                    if (recipe != null)
                    {
                        // The record of earlier applies comes with the recipe, so DSH's own components are known.
                        Ensure(made, JsonUtility.FromJson<Request>(JsonUtility.ToJson(recipe)), null, true);
                    }
                    var target = made.GetComponent(targetType) ?? made.AddComponent(targetType);
                    Set(target, "buildTarget", 2);   // KRT.VRCQuestTools.Models.BuildTarget.Android
                });
                var materials = Materials(copy).Cast<Dictionary<string, object>>().ToArray();
                var notMobile = materials.Where(m => !(bool)m["mobile"]).ToArray();
                return new Dictionary<string, object>
                {
                    { "counts", DshInspect.MeasureCounts(copy) },
                    { "materials", materials.Length },
                    { "shaders", materials.GroupBy(m => (string)m["shader"]).ToDictionary(g => g.Key, g => (object)g.Count()) },
                    { "notMobile", notMobile.Take(20).ToArray() },
                    { "dynamics", DynamicsOf(copy).Take(100).ToArray() },
                    { "note", "textureMemoryMB counts textures uncompressed; Android textures are ASTC and smaller. The SDK build panel on the Android target has the final rank." },
                };
            }
            finally
            {
                if (copy != null) UnityEngine.Object.DestroyImmediate(copy);
            }
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                var android = BuildAndroid(avatar, null);
                result["android"] = android;
                if (((Array)android["notMobile"]).Length > 0)
                    throw new InvalidOperationException("After the Android build some materials still use PC shaders (see notMobile).");
                // The PC build must not change: VQT acts only on Android builds.
                var before = Materials(avatar).Cast<Dictionary<string, object>>().Count(m => (bool)m["mobile"]);
                copy = DshVrc.PreprocessCopy(avatar);
                var after = Materials(copy).Cast<Dictionary<string, object>>().Count(m => (bool)m["mobile"]);
                result["pcMobileMaterials"] = new Dictionary<string, object> { { "before", before }, { "afterBuild", after } };
                if (after > before) throw new InvalidOperationException("The PC build also got mobile shaders. Check VQT Platform Target Settings on the avatar.");
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
