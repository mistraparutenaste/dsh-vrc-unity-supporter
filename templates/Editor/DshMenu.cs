using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// The avatar's Expressions menu as VRChat sees it after the build (VRCFury and Modular Avatar items included),
    /// and tidying it without touching the author's menu assets: one "DSH Menu &lt;name&gt;" object under the avatar
    /// holds only VRCFury "Move or Rename Menu Item", "Set Menu Item Icon" and "Reorder Menu Item" components,
    /// which VRCFury applies to the finished menu at build time. Remove deletes that object.
    /// </summary>
    public static class DshMenu
    {
        [Serializable]
        private sealed class Move
        {
            public string from = "";
            public string to = "";
        }

        [Serializable]
        private sealed class Icon
        {
            public string path = "";
            public string icon = "";
        }

        [Serializable]
        private sealed class Order
        {
            public string path = "";
            public int position = 0;
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
            public bool build = true;
            public Move[] moves = Array.Empty<Move>();
            public Icon[] icons = Array.Empty<Icon>();
            public Order[] order = Array.Empty<Order>();
        }

        public const string HolderPrefix = "DSH Menu ";
        private const string FuryType = "VF.Model.VRCFury";
        private const string MoveType = "VF.Model.Feature.MoveMenuItem";
        private const string IconType = "VF.Model.Feature.SetIcon";
        private const string OrderType = "VF.Model.Feature.ReorderMenuItem";
        private const string GuidTextureType = "VF.Model.GuidTexture2d";
        private const int MaxItems = 400;

        /// <summary>Read-only: the menu tree after the SDK build (or the descriptor's own menu with build off).</summary>
        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            GameObject copy = null;
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                result["holders"] = avatar.transform.Cast<Transform>().Where(t => t.name.StartsWith(HolderPrefix, StringComparison.Ordinal))
                    .Select(t => (object)new Dictionary<string, object> { { "name", t.name }, { "features", Features(t.gameObject).Select(Describe).ToArray() } }).ToArray();
                var source = avatar;
                if (request.build)
                {
                    copy = DshVrc.PreprocessCopy(avatar);
                    source = copy;
                }
                var items = Tree(DshAvatarScene.Descriptor(source));
                result["built"] = request.build;
                result["itemCount"] = items.Count;
                result["truncated"] = items.Count > MaxItems;
                result["items"] = items.Take(MaxItems).Select(i => (object)i).ToArray();
                result["note"] = request.build
                    ? "Paths are as VRCFury menu paths use them (pages left out). 'page' shows the Next links in front of an item."
                    : "The avatar's own menu asset only; VRCFury and Modular Avatar add their items at build time.";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            finally
            {
                if (copy != null) UnityEngine.Object.DestroyImmediate(copy);
            }
            DshAvatarScene.Finish("Menu", result);
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
                var changes = Ensure(avatar, request, true);
                result["applied"] = changes;
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied menu recipe {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = Ensure(avatar, request, false);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the menu recipe: " + string.Join("; ", remaining.Take(5)));
                result["holder"] = HolderPrefix + request.name;
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["sdkVerification"] = request.verifySdk ? VerifySdk(avatar, request)
                    : new Dictionary<string, object> { { "status", "not-requested" }, { "clientTested", false } };
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("MenuApply", result);
        }

        /// <summary>Remove the DSH menu object; the recipe file and the author's menus are untouched.</summary>
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
                var holder = DshVrc.FindHolder(avatar, HolderPrefix + request.name);
                result["holderRemoved"] = holder != null;
                if (holder != null)
                {
                    RequireOwned(holder);
                    UnityEngine.Object.DestroyImmediate(holder);
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed menu recipe {request.name}");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                    if (DshVrc.FindHolder(avatar, HolderPrefix + request.name) != null)
                        throw new InvalidOperationException("The menu object is still in the saved scene.");
                }
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("MenuRemove", result);
        }

        // ---- the holder and its VRCFury components ----

        private static Type Required(string name) => DshVrc.LoadedType(name)
            ?? throw new InvalidOperationException($"VRCFury ({name}) is unavailable. Install or update VRCFury in VCC/ALCOM.");

        /// <summary>The features the recipe asks for, in the order VRCFury should see them.</summary>
        private static List<(string kind, string a, string b, Texture2D icon)> Wanted(Request request)
        {
            var wanted = new List<(string, string, string, Texture2D)>();
            foreach (var move in request.moves) wanted.Add(("move", move.from, move.to, null));
            foreach (var icon in request.icons)
            {
                var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(icon.icon)
                    ?? throw new InvalidOperationException($"The icon is not a texture in the project: {icon.icon}");
                wanted.Add(("icon", icon.path, icon.icon, texture));
            }
            foreach (var order in request.order) wanted.Add(("order", order.path, order.position.ToString(), null));
            return wanted;
        }

        private static IEnumerable<Component> Features(GameObject holder) =>
            holder.GetComponents<Component>().Where(c => c != null && c.GetType().FullName == FuryType);

        private static object Content(Component component) =>
            component.GetType().GetField("content", BindingFlags.Public | BindingFlags.Instance)?.GetValue(component);

        private static object Field(object target, string name) =>
            target?.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(target);

        /// <summary>What a VRCFury component on the holder does, as (kind, a, b) to compare with the recipe.</summary>
        private static (string kind, string a, string b) Inspect(Component component)
        {
            var content = Content(component);
            switch (content?.GetType().FullName)
            {
                case MoveType:
                    return ("move", Field(content, "fromPath") as string ?? "", Field(content, "toPath") as string ?? "");
                case IconType:
                    var texture = Field(Field(content, "icon"), "objRef") as UnityEngine.Object;
                    return ("icon", Field(content, "path") as string ?? "", texture != null ? AssetDatabase.GetAssetPath(texture) : "");
                case OrderType:
                    return ("order", Field(content, "path") as string ?? "", Field(content, "position")?.ToString() ?? "");
                default:
                    return ("other", content?.GetType().FullName ?? "empty", "");
            }
        }

        private static object Describe(Component component)
        {
            var (kind, a, b) = Inspect(component);
            return new Dictionary<string, object> { { "kind", kind }, { "a", a }, { "b", b } };
        }

        /// <summary>Only a holder that holds nothing but VRCFury menu components and no children is DSH's.</summary>
        private static void RequireOwned(GameObject holder)
        {
            var others = holder.GetComponents<Component>().Where(c => c != null && !(c is Transform) && c.GetType().FullName != FuryType).ToArray();
            if (others.Length > 0 || holder.transform.childCount > 0 || Features(holder).Any(c => Inspect(c).kind == "other"))
                throw new InvalidOperationException($"'{holder.name}' holds more than DSH menu changes. Inspect it in Unity before changing it.");
        }

        /// <summary>Make the holder match the recipe (write) or list what differs (check).</summary>
        private static List<string> Ensure(GameObject avatar, Request request, bool write)
        {
            var changes = new List<string>();
            var wanted = Wanted(request);
            var name = HolderPrefix + request.name;
            var holder = DshVrc.FindHolder(avatar, name);
            if (holder != null) RequireOwned(holder);
            var current = holder == null ? new List<(string, string, string)>() : Features(holder).Select(Inspect).ToList();
            var desired = wanted.Select(w => (w.kind, w.a, w.b)).ToList();
            if (holder != null && current.SequenceEqual(desired)) return changes;
            changes.Add(holder == null ? $"add {name} with {desired.Count} VRCFury menu changes"
                : $"replace the {current.Count} menu changes on {name} with {desired.Count}");
            if (!write) return changes;
            if (holder == null)
            {
                holder = new GameObject(name);
                holder.transform.SetParent(avatar.transform, false);
            }
            foreach (var component in Features(holder).ToArray()) UnityEngine.Object.DestroyImmediate(component);
            var fury = Required(FuryType);
            var contentField = fury.GetField("content", BindingFlags.Public | BindingFlags.Instance)
                ?? throw new InvalidOperationException("This VRCFury version stores its features differently. Update VRCFury.");
            foreach (var (kind, a, b, icon) in wanted)
            {
                object feature;
                switch (kind)
                {
                    case "move":
                        feature = Activator.CreateInstance(Required(MoveType), true);
                        Set(feature, "fromPath", a);
                        Set(feature, "toPath", b);
                        break;
                    case "icon":
                        feature = Activator.CreateInstance(Required(IconType), true);
                        Set(feature, "path", a);
                        var wrapperType = Required(GuidTextureType);
                        var convert = wrapperType.GetMethod("op_Implicit", BindingFlags.Public | BindingFlags.Static, null, new[] { typeof(Texture2D) }, null)
                            ?? throw new InvalidOperationException("This VRCFury version sets icons differently. Update VRCFury.");
                        Set(feature, "icon", convert.Invoke(null, new object[] { icon }));
                        break;
                    default:
                        feature = Activator.CreateInstance(Required(OrderType), true);
                        Set(feature, "path", a);
                        Set(feature, "position", int.Parse(b));
                        break;
                }
                var component = holder.AddComponent(fury);
                contentField.SetValue(component, feature);
                EditorUtility.SetDirty(component);
            }
            return changes;
        }

        private static void Set(object target, string name, object value)
        {
            var field = target.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                ?? throw new InvalidOperationException($"This VRCFury version has no '{name}' on {target.GetType().Name}. Update VRCFury.");
            field.SetValue(target, value);
        }

        // ---- the menu tree ----

        private static string Escape(string name) => (name ?? "").Replace("/", "\\/");

        private static List<Dictionary<string, object>> Tree(Component descriptor)
        {
            var items = new List<Dictionary<string, object>>();
            var visited = new HashSet<object>();
            void Walk(object menu, string prefix, int depth)
            {
                if (menu == null || depth > 12 || !visited.Add(menu)) return;
                var index = 0;
                foreach (var (control, via) in DshVrc.PagedControls(menu))
                {
                    var label = DshVrc.PublicMember(control, "name") as string ?? "";
                    var path = prefix + Escape(label);
                    var type = DshVrc.PublicMember(control, "type")?.ToString() ?? "";
                    var icon = DshVrc.PublicMember(control, "icon") as Texture2D;
                    var item = new Dictionary<string, object>
                    {
                        { "path", path }, { "type", type }, { "index", index++ },
                        { "parameter", DshVrc.PublicMember(DshVrc.PublicMember(control, "parameter"), "name") as string ?? "" },
                        { "value", DshVrc.PublicMember(control, "value") },
                        { "icon", icon == null ? "" : (AssetDatabase.GetAssetPath(icon) is string p && p.Length > 0 ? p : icon.name) },
                    };
                    if (via.Length > 0) item["page"] = string.Join("/", via);
                    items.Add(item);
                    if (type == "SubMenu") Walk(DshVrc.PublicMember(control, "subMenu"), path + "/", depth + 1);
                }
            }
            Walk(DshVrc.PublicMember(descriptor, "expressionsMenu"), "", 0);
            return items;
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Request request)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar);
                var items = Tree(DshAvatarScene.Descriptor(copy));
                var byPath = items.GroupBy(i => (string)i["path"]).ToDictionary(g => g.Key, g => g.First());
                var problems = new List<string>();
                var checks = new List<object>();
                foreach (var move in request.moves)
                {
                    var found = byPath.ContainsKey(move.to);
                    var gone = !byPath.ContainsKey(move.from) || move.from == move.to;
                    checks.Add(new Dictionary<string, object> { { "move", move.from + " -> " + move.to }, { "found", found }, { "fromGone", gone } });
                    if (!found) problems.Add($"'{move.to}' is not in the built menu (was '{move.from}' there?)");
                }
                foreach (var icon in request.icons)
                {
                    var has = byPath.TryGetValue(icon.path, out var item) && (item["icon"] as string ?? "") != "";
                    checks.Add(new Dictionary<string, object> { { "icon", icon.path }, { "set", has }, { "built", has ? item["icon"] : "" } });
                    if (!has) problems.Add($"'{icon.path}' has no icon in the built menu");
                }
                foreach (var order in request.order)
                {
                    if (!byPath.TryGetValue(order.path, out var item)) { problems.Add($"'{order.path}' is not in the built menu"); continue; }
                    var folder = order.path.Contains("/") ? order.path.Substring(0, order.path.LastIndexOf('/') + 1) : "";
                    var count = items.Count(i => ((string)i["path"]).StartsWith(folder, StringComparison.Ordinal) &&
                                                 !((string)i["path"]).Substring(folder.Length).Replace("\\/", "").Contains("/"));
                    var expected = order.position >= 0 ? Math.Min(order.position, count - 1) : Math.Max(0, count - 1 + order.position);
                    checks.Add(new Dictionary<string, object> { { "order", order.path }, { "index", item["index"] }, { "expected", expected }, { "of", count } });
                    if ((int)item["index"] != expected) problems.Add($"'{order.path}' is at {item["index"]}, not {expected}");
                }
                result["checks"] = checks.ToArray();
                result["itemCount"] = items.Count;
                if (problems.Count > 0) throw new InvalidOperationException(string.Join("; ", problems.Take(8)));
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
