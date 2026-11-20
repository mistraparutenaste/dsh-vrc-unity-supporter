using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DSH.Editor
{
    public static class DshOutfitToggle
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string outfit = "";
            public string avatarId = "";
            public string outfitId = "";
            public string menu = "";
            public string query = "";
            public string expectedSceneDigest = "";
            public bool defaultOn = false;
            public bool verifySdk = false;
        }

        public static void Targets()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatars = SceneAvatars(scene).ToArray();
                result["scene"] = scene.path;
                result["avatars"] = avatars.Select(DescribeTarget).ToArray();
                var selected = avatars.Where(t =>
                    (string.IsNullOrEmpty(request.avatar) || DshAvatarScene.HierarchyPath(t) == request.avatar) &&
                    (string.IsNullOrEmpty(request.avatarId) || DshAvatarScene.ObjectId(t.gameObject) == request.avatarId)).ToArray();
                if (selected.Length == 1)
                {
                    var query = request.query ?? "";
                    var outfits = OutfitObjects(selected[0].gameObject)
                        .Where(t => t.name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0)
                        .OrderByDescending(t => t.name.Equals(query, StringComparison.OrdinalIgnoreCase))
                        .ThenBy(DshAvatarScene.HierarchyPath, StringComparer.Ordinal).ToArray();
                    result["selectedAvatar"] = DescribeTarget(selected[0]);
                    result["outfitMatchCount"] = outfits.Length;
                    result["outfits"] = outfits.Take(50).Select(DescribeTarget).ToArray();
                }
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("OutfitTargets", result);
        }

        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                if (string.IsNullOrWhiteSpace(request.menu) ||
                    request.menu.Split('/').Any(string.IsNullOrWhiteSpace))
                    throw new InvalidOperationException("Specify a menu name and nonempty submenu names.");
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var (avatar, outfit) = Resolve(scene, request, result);
                var holderName = HolderName(outfit);
                result["holder"] = holderName;
                var holder = DshVrc.FindHolder(avatar, holderName);

                if (holder == null)
                {
                    CheckExistingToggles(avatar, outfit, request.menu);
                    holder = new GameObject(holderName);
                    holder.transform.SetParent(avatar.transform, false);
                    CreateToggle(holder, outfit, request);
                    VerifyToggle(holder, outfit, request);
                    DshAvatarScene.RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Added {request.menu} for {request.outfit}");

                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = DshAvatarScene.OpenScene(request.scene);
                    (avatar, outfit) = Resolve(scene, request, result);
                    holder = DshVrc.FindHolder(avatar, holderName);
                }
                VerifyToggle(holder, outfit, request);
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, outfit, request) :
                    new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }

            DshAvatarScene.Finish("OutfitToggle", result);
        }

        private static (GameObject avatar, GameObject outfit) Resolve(
            Scene scene, Request request, Dictionary<string, object> result)
        {
            var avatar = ResolveTarget(SceneAvatars(scene),
                request.avatar, request.avatarId, "avatar", result);
            var outfit = ResolveTarget(OutfitObjects(avatar), request.outfit, request.outfitId, "outfit", result);
            result["scene"] = scene.path;
            result["avatar"] = request.avatar;
            result["outfit"] = request.outfit;
            result["menu"] = request.menu;
            result["defaultOn"] = request.defaultOn;
            return (avatar, outfit);
        }

        private static IEnumerable<Transform> SceneAvatars(Scene scene) => scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<Transform>(true)).Where(t => HasDescriptor(t.gameObject));

        private static IEnumerable<Transform> OutfitObjects(GameObject avatar) => avatar.GetComponentsInChildren<Transform>(true)
            .Where(t => t != avatar.transform && GetAvatar(t) == avatar);

        private static GameObject ResolveTarget(IEnumerable<Transform> objects, string path, string id,
            string label, Dictionary<string, object> result)
        {
            var matches = objects.Where(t => DshAvatarScene.HierarchyPath(t) == path).ToArray();
            var selected = string.IsNullOrEmpty(id) ? matches : matches.Where(t => DshAvatarScene.ObjectId(t.gameObject) == id).ToArray();
            if (selected.Length == 1) return selected[0].gameObject;
            result["candidates"] = matches.Select(DescribeTarget).ToArray();
            result["targetKind"] = label;
            throw new InvalidOperationException(selected.Length == 0
                ? $"The {label} '{path}' could not be found. Check the saved scene and hierarchy path."
                : $"More than one {label} is named '{path}'. Select a candidate by ID and retry.");
        }

        private static Dictionary<string, object> DescribeTarget(Transform target) => new Dictionary<string, object>
        {
            { "name", target.name }, { "path", DshAvatarScene.HierarchyPath(target) }, { "id", DshAvatarScene.ObjectId(target.gameObject) },
            { "siblingPath", SiblingPath(target) }, { "active", target.gameObject.activeInHierarchy }
        };

        private static string SiblingPath(Transform transform)
        {
            return transform.parent == null ? transform.GetSiblingIndex().ToString() :
                SiblingPath(transform.parent) + "/" + transform.GetSiblingIndex();
        }

        private static bool HasDescriptor(GameObject obj)
        {
            return DshAvatarScene.Descriptor(obj) != null;
        }

        private static GameObject GetAvatar(Transform transform)
        {
            for (var current = transform; current != null; current = current.parent)
                if (HasDescriptor(current.gameObject)) return current.gameObject;
            return null;
        }

        private static string HolderName(GameObject outfit)
        {
            using (var sha = SHA256.Create())
            {
                var hash = sha.ComputeHash(Encoding.UTF8.GetBytes(DshAvatarScene.ObjectId(outfit)));
                return "DSH Outfit Toggle " + BitConverter.ToString(hash, 0, 8).Replace("-", "");
            }
        }

        private static void CreateToggle(GameObject holder, GameObject outfit, Request request)
        {
            var toggle = DshVrc.CreateFuryToggle(holder);
            DshVrc.CallPublic(toggle, "SetMenuPath", request.menu);
            if (request.defaultOn) DshVrc.CallPublic(toggle, "SetDefaultOn");
            DshVrc.CallPublic(DshVrc.CallPublic(toggle, "GetActions"), "AddTurnOn", outfit);
        }

        private static void CheckExistingToggles(GameObject avatar, GameObject outfit, string menu)
        {
            foreach (var component in avatar.GetComponentsInChildren<Component>(true).Where(DshVrc.IsFury))
            {
                var data = DshVrc.ToggleData(component);
                if (data == null) continue;
                var actions = data.FindPropertyRelative("state.actions");
                if (data.FindPropertyRelative("name")?.stringValue == menu ||
                    (actions != null && Enumerable.Range(0, actions.arraySize).Any(i =>
                        actions.GetArrayElementAtIndex(i).FindPropertyRelative("obj")?.objectReferenceValue == outfit)))
                    throw new InvalidOperationException($"An existing VRCFury toggle on '{DshAvatarScene.HierarchyPath(component.transform)}' uses that menu or outfit.");
            }
        }

        private static void VerifyToggle(GameObject holder, GameObject outfit, Request request)
        {
            var components = holder == null ? Array.Empty<Component>() : holder.GetComponents<Component>().Where(DshVrc.IsFury).ToArray();
            var data = components.Length == 1 ? DshVrc.ToggleData(components[0]) : null;
            var actions = data?.FindPropertyRelative("state.actions");
            var action = actions != null && actions.arraySize == 1 ? actions.GetArrayElementAtIndex(0) : null;
            var mode = action?.FindPropertyRelative("mode");
            if (data == null || data.FindPropertyRelative("name")?.stringValue != request.menu ||
                data.FindPropertyRelative("defaultOn")?.boolValue != request.defaultOn ||
                action?.FindPropertyRelative("obj")?.objectReferenceValue != outfit ||
                mode == null || mode.enumNames[mode.enumValueIndex] != "TurnOn")
                throw new InvalidOperationException("The DSH toggle settings differ or VRCFury uses an unsupported format. Inspect the scene and Git diff before retrying.");
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, GameObject outfit, Request request)
        {
            var result = new Dictionary<string, object>
            {
                { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false },
                { "menu", request.menu }
            };
            GameObject copy = null;
            try
            {
                // Sibling indices preserve the identity of same-name children in the copy.
                var indices = new Stack<int>();
                for (var node = outfit.transform; node != avatar.transform; node = node.parent)
                    indices.Push(node.GetSiblingIndex());
                Transform copyOutfit = null;
                copy = DshVrc.PreprocessCopy(avatar, clone =>
                {
                    copyOutfit = clone.transform;
                    foreach (var index in indices) copyOutfit = copyOutfit.GetChild(index);
                });

                var descriptor = DshAvatarScene.Descriptor(copy);
                var (_, parameter) = DshVrc.GeneratedToggle(descriptor, request.menu);
                result["menuGenerated"] = true;

                var parameters = DshVrc.PublicItems(DshVrc.PublicMember(descriptor, "expressionParameters"), "parameters")
                    .Where(item => DshVrc.PublicMember(item, "name") as string == parameter).ToArray();
                if (string.IsNullOrEmpty(parameter) || parameters.Length != 1 ||
                    !(DshVrc.PublicMember(parameters[0], "defaultValue") is float defaultValue) ||
                    !Mathf.Approximately(defaultValue, request.defaultOn ? 1f : 0f))
                    throw new InvalidOperationException("The generated menu parameter is missing or does not have the requested default.");
                result["parameter"] = parameter;
                result["defaultOn"] = request.defaultOn;

                if (copyOutfit == null || !copyOutfit.IsChildOf(copy.transform))
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "A build plugin removed or moved the target outfit. Check switching in Build & Test.";
                    return result;
                }
                var relativePath = AnimationUtility.CalculateTransformPath(copyOutfit, copy.transform);
                if (copy.transform.Find(relativePath) != copyOutfit || copy.GetComponentsInChildren<Transform>(true)
                    .Count(node => AnimationUtility.CalculateTransformPath(node, copy.transform) == relativePath) != 1)
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "Several objects share the generated animation path, or it cannot be resolved uniquely. Rename the conflicting objects in Unity before testing.";
                    return result;
                }
                var values = DshVrc.FxClips(descriptor, parameter)
                    .SelectMany(clip => AnimationUtility.GetCurveBindings(clip)
                        .Where(binding => binding.path == relativePath && binding.propertyName == "m_IsActive")
                        .SelectMany(binding => AnimationUtility.GetEditorCurve(clip, binding).keys)
                        .Select(key => key.value)).Distinct().OrderBy(value => value).ToArray();
                result["outfitAnimationPath"] = relativePath;
                result["activeValues"] = values;
                if (values.Any(value => Mathf.Approximately(value, 0f)) &&
                    values.Any(value => Mathf.Approximately(value, 1f)))
                    result["status"] = "passed";
                else
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "The generated FX did not expose both active states as clip keys. Check switching in Build & Test.";
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
