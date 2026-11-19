using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
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
                var request = ReadRequest();
                var scene = OpenScene(request.scene, request.expectedSceneDigest);
                var avatars = SceneAvatars(scene).ToArray();
                result["scene"] = scene.path;
                result["avatars"] = avatars.Select(DescribeTarget).ToArray();
                var selected = avatars.Where(t =>
                    (string.IsNullOrEmpty(request.avatar) || HierarchyPath(t) == request.avatar) &&
                    (string.IsNullOrEmpty(request.avatarId) || ObjectId(t.gameObject) == request.avatarId)).ToArray();
                if (selected.Length == 1)
                {
                    var query = request.query ?? "";
                    var outfits = OutfitObjects(selected[0].gameObject)
                        .Where(t => t.name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0)
                        .OrderByDescending(t => t.name.Equals(query, StringComparison.OrdinalIgnoreCase))
                        .ThenBy(HierarchyPath, StringComparer.Ordinal).ToArray();
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
            Finish("OutfitTargets", result);
        }

        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = ReadRequest();
                if (string.IsNullOrWhiteSpace(request.menu) ||
                    request.menu.Split('/').Any(string.IsNullOrWhiteSpace))
                    throw new InvalidOperationException("Specify a menu name and nonempty submenu names.");
                var scene = OpenScene(request.scene, request.expectedSceneDigest);
                var (avatar, outfit) = Resolve(scene, request, result);
                var holderName = HolderName(outfit);
                result["holder"] = holderName;
                var holder = FindHolder(avatar, holderName);

                if (holder == null)
                {
                    CheckExistingToggles(avatar, outfit, request.menu);
                    var factory = FindFactory();
                    holder = new GameObject(holderName);
                    holder.transform.SetParent(avatar.transform, false);
                    CreateToggle(factory, holder, outfit, request);
                    VerifyToggle(holder, outfit, request);
                    RequireSceneDigest(scene.path, request.expectedSceneDigest);
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (!EditorSceneManager.SaveScene(scene))
                        throw new IOException($"Unity could not save {scene.path}. Check write access and retry.");
                    result["saved"] = true;
                    DshApply.Note(result, $"Added {request.menu} for {request.outfit}");

                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    scene = OpenScene(request.scene);
                    (avatar, outfit) = Resolve(scene, request, result);
                    holder = FindHolder(avatar, holderName);
                }
                VerifyToggle(holder, outfit, request);
                result["sceneDigest"] = SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, outfit, request) :
                    new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }

            Finish("OutfitToggle", result);
        }

        private static Request ReadRequest()
        {
            var requestPath = Environment.GetEnvironmentVariable("DSH_UNITY_REQUEST_PATH");
            return JsonUtility.FromJson<Request>(File.ReadAllText(requestPath))
                ?? throw new InvalidOperationException("A Unity task request is required.");
        }

        private static void Finish(string task, Dictionary<string, object> result)
        {
            DshApply.WriteResult(task, result);
            EditorApplication.Exit((bool)result["ok"] ? 0 : 1);
        }

        private static Scene OpenScene(string path, string expectedDigest = "")
        {
            if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) ||
                !path.EndsWith(".unity", StringComparison.OrdinalIgnoreCase) || path.Contains("\\") ||
                path.Split('/').Any(part => part == ".." || part == ".") ||
                AssetDatabase.LoadAssetAtPath<SceneAsset>(path) == null)
                throw new InvalidOperationException($"Select a saved scene underneath Assets: {path}");
            RequireSceneDigest(path, expectedDigest);
            return EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
        }

        private static string SceneDigest(string path)
        {
            using (var sha = SHA256.Create())
            using (var scene = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(scene)).Replace("-", "").ToLowerInvariant();
        }

        private static void RequireSceneDigest(string path, string expectedDigest)
        {
            if (!string.IsNullOrEmpty(expectedDigest) && SceneDigest(path) != expectedDigest)
                throw new InvalidOperationException("The saved scene changed after the preview. Review it and preview again.");
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
            var matches = objects.Where(t => HierarchyPath(t) == path).ToArray();
            var selected = string.IsNullOrEmpty(id) ? matches : matches.Where(t => ObjectId(t.gameObject) == id).ToArray();
            if (selected.Length == 1) return selected[0].gameObject;
            result["candidates"] = matches.Select(DescribeTarget).ToArray();
            result["targetKind"] = label;
            throw new InvalidOperationException(selected.Length == 0
                ? $"The {label} '{path}' could not be found. Check the saved scene and hierarchy path."
                : $"More than one {label} is named '{path}'. Select a candidate by ID and retry.");
        }

        private static Dictionary<string, object> DescribeTarget(Transform target) => new Dictionary<string, object>
        {
            { "name", target.name }, { "path", HierarchyPath(target) }, { "id", ObjectId(target.gameObject) },
            { "siblingPath", SiblingPath(target) }, { "active", target.gameObject.activeInHierarchy }
        };

        private static string HierarchyPath(Transform transform)
        {
            return transform.parent == null ? transform.name : HierarchyPath(transform.parent) + "/" + transform.name;
        }

        private static string SiblingPath(Transform transform)
        {
            return transform.parent == null ? transform.GetSiblingIndex().ToString() :
                SiblingPath(transform.parent) + "/" + transform.GetSiblingIndex();
        }

        private static bool HasDescriptor(GameObject obj)
        {
            return AvatarDescriptor(obj) != null;
        }

        private static Component AvatarDescriptor(GameObject obj)
        {
            return obj.GetComponents<Component>().FirstOrDefault(c => c != null &&
                (c.GetType().FullName == "VRC.SDK3.Avatars.Components.VRCAvatarDescriptor" ||
                 c.GetType().FullName == "VRCSDK2.VRC_AvatarDescriptor"));
        }

        private static GameObject GetAvatar(Transform transform)
        {
            for (var current = transform; current != null; current = current.parent)
                if (HasDescriptor(current.gameObject)) return current.gameObject;
            return null;
        }

        private static string ObjectId(GameObject obj) => GlobalObjectId.GetGlobalObjectIdSlow(obj).ToString();

        private static string HolderName(GameObject outfit)
        {
            using (var sha = SHA256.Create())
            {
                var hash = sha.ComputeHash(Encoding.UTF8.GetBytes(ObjectId(outfit)));
                return "DSH Outfit Toggle " + BitConverter.ToString(hash, 0, 8).Replace("-", "");
            }
        }

        private static GameObject FindHolder(GameObject avatar, string name)
        {
            var matches = avatar.transform.Cast<Transform>().Where(t => t.name == name).ToArray();
            if (matches.Length > 1) throw new InvalidOperationException($"Several objects use '{name}'.");
            return matches.Length == 1 ? matches[0].gameObject : null;
        }

        private static MethodInfo FindFactory()
        {
            var factory = LoadedType("com.vrcfury.api.FuryComponents");
            return factory?.GetMethod("CreateToggle", BindingFlags.Public | BindingFlags.Static,
                null, new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("VRCFury Toggle API is unavailable. Install or update VRCFury in VCC/ALCOM.");
        }

        private static Type LoadedType(string name) => AppDomain.CurrentDomain.GetAssemblies()
            .Select(assembly => assembly.GetType(name)).FirstOrDefault(type => type != null);

        private static void CreateToggle(MethodInfo factory, GameObject holder, GameObject outfit, Request request)
        {
            var toggle = factory.Invoke(null, new object[] { holder });
            CallPublic(toggle, "SetMenuPath", request.menu);
            if (request.defaultOn) CallPublic(toggle, "SetDefaultOn");
            var actions = CallPublic(toggle, "GetActions");
            CallPublic(actions, "AddTurnOn", outfit);
        }

        private static object CallPublic(object target, string name, params object[] args)
        {
            var method = target?.GetType().GetMethod(name, args.Select(arg => arg.GetType()).ToArray())
                ?? throw new InvalidOperationException($"VRCFury API method {name} is unavailable. Update VRCFury in VCC/ALCOM.");
            return method.Invoke(target, args);
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

        private static void CheckExistingToggles(GameObject avatar, GameObject outfit, string menu)
        {
            foreach (var component in avatar.GetComponentsInChildren<Component>(true).Where(IsFury))
            {
                var data = ToggleData(component);
                if (data == null) continue;
                var actions = data.FindPropertyRelative("state.actions");
                if (data.FindPropertyRelative("name")?.stringValue == menu ||
                    (actions != null && Enumerable.Range(0, actions.arraySize).Any(i =>
                        actions.GetArrayElementAtIndex(i).FindPropertyRelative("obj")?.objectReferenceValue == outfit)))
                    throw new InvalidOperationException($"An existing VRCFury toggle on '{HierarchyPath(component.transform)}' uses that menu or outfit.");
            }
        }

        private static void VerifyToggle(GameObject holder, GameObject outfit, Request request)
        {
            var components = holder == null ? Array.Empty<Component>() : holder.GetComponents<Component>().Where(IsFury).ToArray();
            var data = components.Length == 1 ? ToggleData(components[0]) : null;
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
                var callback = LoadedType("VRC.SDKBase.Editor.BuildPipeline.VRCBuildPipelineCallbacks")?
                    .GetMethod("OnPreprocessAvatar", BindingFlags.Public | BindingFlags.Static, null,
                        new[] { typeof(GameObject) }, null)
                    ?? throw new InvalidOperationException("The VRChat SDK avatar preprocessing API is unavailable.");
                if (!AssetDatabase.IsValidFolder("Packages/com.vrcfury.temp"))
                    throw new InvalidOperationException("Open the project in Unity once to let VRCFury initialize its temporary package, then close it and retry verification.");

                // Sibling indices preserve the identity of same-name children in the copy.
                var indices = new Stack<int>();
                for (var node = outfit.transform; node != avatar.transform; node = node.parent)
                    indices.Push(node.GetSiblingIndex());
                copy = UnityEngine.Object.Instantiate(avatar);
                copy.name = avatar.name + " (DSH Verification)";
                var copyOutfit = copy.transform;
                foreach (var index in indices) copyOutfit = copyOutfit.GetChild(index);
                if (!(callback.Invoke(null, new object[] { copy }) is bool built) || !built)
                    throw new InvalidOperationException("VRChat SDK preprocessing did not complete. See the Unity log.");

                var descriptor = AvatarDescriptor(copy);
                var menu = PublicMember(descriptor, "expressionsMenu");
                var control = FindMenuControl(menu, request.menu);
                if (PublicMember(control, "type")?.ToString() != "Toggle")
                    throw new InvalidOperationException($"The SDK did not generate a unique Toggle at '{request.menu}'.");
                result["menuGenerated"] = true;

                var parameter = PublicMember(PublicMember(control, "parameter"), "name") as string;
                var parameters = PublicItems(PublicMember(descriptor, "expressionParameters"), "parameters")
                    .Where(item => PublicMember(item, "name") as string == parameter).ToArray();
                if (string.IsNullOrEmpty(parameter) || parameters.Length != 1 ||
                    !(PublicMember(parameters[0], "defaultValue") is float defaultValue) ||
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
                var controllers = PublicItems(descriptor, "baseAnimationLayers")
                    .Where(layer => PublicMember(layer, "type")?.ToString() == "FX")
                    .Select(layer => PublicMember(layer, "animatorController")).OfType<AnimatorController>()
                    .Where(controller => controller.parameters.Any(p => p.name == parameter));
                var values = controllers.SelectMany(controller => controller.animationClips).Distinct()
                    .Where(clip => clip != null)
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
