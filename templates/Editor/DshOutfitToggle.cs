using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
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
            public bool defaultOn = false;
        }

        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var requestPath = Environment.GetEnvironmentVariable("DSH_UNITY_REQUEST_PATH");
                var request = JsonUtility.FromJson<Request>(File.ReadAllText(requestPath));
                if (request == null || string.IsNullOrWhiteSpace(request.menu) ||
                    request.menu.Split('/').Any(string.IsNullOrWhiteSpace))
                    throw new InvalidOperationException("Specify a menu name and nonempty submenu names.");
                var scene = OpenScene(request.scene);
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
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }

            DshApply.WriteResult("OutfitToggle", result);
            EditorApplication.Exit((bool)result["ok"] ? 0 : 1);
        }

        private static Scene OpenScene(string path)
        {
            if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) ||
                !path.EndsWith(".unity", StringComparison.OrdinalIgnoreCase) || path.Contains("\\") ||
                path.Split('/').Any(part => part == ".." || part == ".") ||
                AssetDatabase.LoadAssetAtPath<SceneAsset>(path) == null)
                throw new InvalidOperationException($"Select a saved scene underneath Assets: {path}");
            return EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
        }

        private static (GameObject avatar, GameObject outfit) Resolve(
            Scene scene, Request request, Dictionary<string, object> result)
        {
            var objects = scene.GetRootGameObjects().SelectMany(root => root.GetComponentsInChildren<Transform>(true));
            var avatar = ResolveTarget(objects.Where(t => HasDescriptor(t.gameObject)),
                request.avatar, request.avatarId, "avatar", result);
            var outfits = avatar.GetComponentsInChildren<Transform>(true)
                .Where(t => t != avatar.transform && GetAvatar(t) == avatar);
            var outfit = ResolveTarget(outfits, request.outfit, request.outfitId, "outfit", result);
            result["scene"] = scene.path;
            result["avatar"] = request.avatar;
            result["outfit"] = request.outfit;
            result["menu"] = request.menu;
            result["defaultOn"] = request.defaultOn;
            return (avatar, outfit);
        }

        private static GameObject ResolveTarget(IEnumerable<Transform> objects, string path, string id,
            string label, Dictionary<string, object> result)
        {
            var matches = objects.Where(t => HierarchyPath(t) == path).ToArray();
            var selected = string.IsNullOrEmpty(id) ? matches : matches.Where(t => ObjectId(t.gameObject) == id).ToArray();
            if (selected.Length == 1) return selected[0].gameObject;
            result["candidates"] = matches.Select(t => new Dictionary<string, object>
            {
                { "path", HierarchyPath(t) }, { "id", ObjectId(t.gameObject) },
                { "siblingPath", SiblingPath(t) }, { "active", t.gameObject.activeInHierarchy }
            }).ToArray();
            result["targetKind"] = label;
            throw new InvalidOperationException(selected.Length == 0
                ? $"The {label} '{path}' could not be found. Check the saved scene and hierarchy path."
                : $"More than one {label} is named '{path}'. Select a candidate by ID and retry.");
        }

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
            return obj.GetComponents<Component>().Any(c => c != null &&
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
            var factory = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("com.vrcfury.api.FuryComponents"))
                .FirstOrDefault(t => t != null);
            return factory?.GetMethod("CreateToggle", BindingFlags.Public | BindingFlags.Static,
                null, new[] { typeof(GameObject) }, null)
                ?? throw new InvalidOperationException("VRCFury Toggle API is unavailable. Install or update VRCFury in VCC/ALCOM.");
        }

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
    }
}
