using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Read-only: an object's components as the Unity Inspector shows them. Values come from each component's
    /// SerializedObject, so they are what Unity saved (with prefab overrides applied), labelled with the
    /// Inspector's own names, with enums by their shown names and references as asset paths or object paths.
    /// Find lists the objects under the avatar that have a component, so the agent can find where a setting is.
    /// Nothing here changes the project.
    /// </summary>
    public static class DshInspector
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string path = "";          // object under the avatar ("" is the avatar root)
            public string component = "";     // only components whose type name contains this
            public string field = "";         // only properties whose path or label contains this
            public string find = "";          // Find: component type name (part of it is enough)
            public bool hidden = false;       // also properties the Inspector hides
            public int maxProperties = 400;
            public int maxDepth = 6;
            public int arrayItems = 20;
        }

        private const int MaxSteps = 50000;
        private const int MaxFound = 300;
        private static readonly Regex Element = new Regex(@"\.Array\.data\[(\d+)\]", RegexOptions.Compiled);

        public static void Read()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var target = string.IsNullOrEmpty(request.path) ? avatar.transform : avatar.transform.Find(request.path);
                if (target == null)
                    throw new InvalidOperationException($"No object at '{request.path}' under the avatar. Use find, or the hierarchy from vrc-asset-read.");
                result["object"] = DescribeObject(target, avatar.transform);
                result["children"] = target.Cast<Transform>().Take(200).Select(t => (object)t.name).ToArray();
                var budget = Math.Max(10, Math.Min(request.maxProperties, 3000));
                var components = new List<object>();
                var truncated = false;
                var index = 0;
                foreach (var component in target.GetComponents<Component>())
                {
                    var row = DescribeComponent(component, index++, avatar.transform);
                    var name = component == null ? "" : component.GetType().FullName ?? "";
                    if (!string.IsNullOrEmpty(request.component) && name.IndexOf(request.component, StringComparison.OrdinalIgnoreCase) < 0)
                        continue;
                    if (component != null)
                    {
                        var properties = Properties(component, request, avatar.transform, ref budget, out var cut);
                        row["properties"] = properties;
                        truncated |= cut;
                        if (component is Transform transform)
                            row["inspector"] = new Dictionary<string, object>
                            {
                                { "Position", Vector(transform.localPosition) },
                                { "Rotation", Vector(transform.localEulerAngles) },
                                { "Scale", Vector(transform.localScale) },
                            };
                    }
                    components.Add(row);
                }
                result["components"] = components;
                result["truncated"] = truncated;
                if (truncated)
                    result["note"] = "Some properties were left out (maxProperties, maxDepth or arrayItems). Narrow with --component or --field.";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Inspector", result);
        }

        /// <summary>Objects under the avatar that have a component whose type name contains request.find.</summary>
        public static void Find()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                if (string.IsNullOrWhiteSpace(request.find))
                    throw new InvalidOperationException("Give the component type to find, such as ModularAvatarMenuItem or VRCPhysBone.");
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var found = new List<object>();
                var total = 0;
                var missing = 0;
                foreach (var transform in avatar.GetComponentsInChildren<Transform>(true))
                {
                    var components = transform.GetComponents<Component>();
                    missing += components.Count(c => c == null);
                    var matches = components.Where(c => c != null &&
                        (c.GetType().FullName ?? "").IndexOf(request.find, StringComparison.OrdinalIgnoreCase) >= 0).ToArray();
                    if (matches.Length == 0) continue;
                    total += matches.Length;
                    if (found.Count >= MaxFound) continue;
                    found.Add(new Dictionary<string, object>
                    {
                        { "path", DshReflect.PathIn(transform, avatar.transform) },
                        { "active", transform.gameObject.activeInHierarchy },
                        { "components", matches.Select(c => (object)TypeLabel(c)).ToArray() },
                    });
                }
                result["found"] = found;
                result["componentCount"] = total;
                result["truncated"] = found.Count >= MaxFound;
                if (missing > 0) result["missingScripts"] = missing;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("InspectorFind", result);
        }

        // ---- describing ----

        private static Dictionary<string, object> DescribeObject(Transform target, Transform avatar)
        {
            var go = target.gameObject;
            var row = new Dictionary<string, object>
            {
                { "path", DshReflect.PathIn(target, avatar) }, { "name", go.name },
                { "active", go.activeSelf }, { "activeInHierarchy", go.activeInHierarchy },
                { "tag", go.tag }, { "layer", LayerMask.LayerToName(go.layer) },
            };
            if (PrefabUtility.IsPartOfPrefabInstance(go))
            {
                var source = PrefabUtility.GetCorrespondingObjectFromOriginalSource(go);
                row["prefab"] = source == null ? "" : AssetDatabase.GetAssetPath(source);
                row["addedInScene"] = PrefabUtility.IsAddedGameObjectOverride(go);
            }
            return row;
        }

        private static Dictionary<string, object> DescribeComponent(Component component, int index, Transform avatar)
        {
            if (component == null)
                return new Dictionary<string, object>
                {
                    { "index", index }, { "type", "Missing Script" }, { "missing", true },
                    { "note", "The script of this component cannot be loaded (a package or file is missing). Unity shows 'Missing (Mono Script)'." },
                };
            var row = new Dictionary<string, object>
            {
                { "index", index }, { "type", TypeLabel(component) }, { "fullType", component.GetType().FullName },
                { "title", ObjectNames.GetInspectorTitle(component) },
            };
            if (component is Behaviour behaviour) row["enabled"] = behaviour.enabled;
            else if (component is Renderer renderer) row["enabled"] = renderer.enabled;
            if (component is MonoBehaviour mono)
            {
                var script = MonoScript.FromMonoBehaviour(mono);
                if (script != null) row["script"] = AssetDatabase.GetAssetPath(script);
            }
            if (PrefabUtility.IsPartOfPrefabInstance(component))
            {
                row["addedInScene"] = PrefabUtility.IsAddedComponentOverride(component);
                var overrides = 0;
                var it = new SerializedObject(component).GetIterator();
                for (var steps = 0; it.Next(true) && steps < MaxSteps; steps++)
                    if (it.prefabOverride && !it.hasChildren) overrides++;
                row["overrides"] = overrides;
            }
            return row;
        }

        private static string TypeLabel(Component component) => ObjectNames.NicifyVariableName(component.GetType().Name);

        private static List<object> Properties(Component component, Request request, Transform avatar, ref int budget, out bool truncated)
        {
            truncated = false;
            var rows = new List<object>();
            var serialized = new SerializedObject(component);
            var it = serialized.GetIterator();
            var maxDepth = Math.Max(0, Math.Min(request.maxDepth, 20));
            var items = Math.Max(1, Math.Min(request.arrayItems, 500));
            var enter = true;
            var filter = request.field ?? "";
            for (var steps = 0; (request.hidden ? it.Next(enter) : it.NextVisible(enter)); steps++)
            {
                if (steps >= MaxSteps) { truncated = true; break; }
                enter = true;
                if (it.depth >= maxDepth)
                {
                    enter = false;
                    if (it.hasChildren) truncated = true;
                }
                var skip = false;
                foreach (Match m in Element.Matches(it.propertyPath))
                    if (int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) >= items) { skip = true; break; }
                if (skip)
                {
                    enter = false;
                    truncated = true;
                    continue;
                }
                if (it.propertyType == SerializedPropertyType.ArraySize) continue;   // the size is on the array row
                if (it.propertyPath == "m_Script") continue;                          // shown as "script"
                if (filter.Length > 0 && it.propertyPath.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0 &&
                    it.displayName.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                if (budget-- <= 0) { truncated = true; break; }
                rows.Add(Describe(it, avatar));
            }
            return rows;
        }

        private static Dictionary<string, object> Describe(SerializedProperty p, Transform avatar)
        {
            var row = new Dictionary<string, object>
            {
                { "path", p.propertyPath }, { "label", p.displayName }, { "depth", p.depth },
                { "type", p.propertyType == SerializedPropertyType.Generic ? p.type : p.propertyType.ToString() },
            };
            var value = Value(p, avatar);
            if (value != null) row["value"] = value;
            if (p.isArray && p.propertyType != SerializedPropertyType.String) row["size"] = p.arraySize;
            if (p.prefabOverride) row["override"] = true;
            if (!string.IsNullOrEmpty(p.tooltip)) row["tooltip"] = p.tooltip.Length > 200 ? p.tooltip.Substring(0, 200) + "..." : p.tooltip;
            return row;
        }

        private static object Value(SerializedProperty p, Transform avatar)
        {
            switch (p.propertyType)
            {
                case SerializedPropertyType.Integer:
                case SerializedPropertyType.LayerMask:
                    return p.type == "long" || p.type == "ulong" ? (object)p.longValue : p.intValue;
                case SerializedPropertyType.Boolean: return p.boolValue;
                case SerializedPropertyType.Float: return Math.Round(p.doubleValue, 6);
                case SerializedPropertyType.String: return p.stringValue.Length > 500 ? p.stringValue.Substring(0, 500) + "..." : p.stringValue;
                case SerializedPropertyType.Character: return ((char)p.intValue).ToString();
                case SerializedPropertyType.Enum:
                    var names = p.enumDisplayNames;
                    return p.enumValueIndex >= 0 && p.enumValueIndex < names.Length ? names[p.enumValueIndex] : (object)p.intValue;
                case SerializedPropertyType.Color:
                    var c = p.colorValue;
                    return "#" + ColorUtility.ToHtmlStringRGBA(c) + $" ({Num(c.r)}, {Num(c.g)}, {Num(c.b)}, {Num(c.a)})";
                case SerializedPropertyType.Vector2: return Vector(p.vector2Value);
                case SerializedPropertyType.Vector3: return Vector(p.vector3Value);
                case SerializedPropertyType.Vector4: return Vector(p.vector4Value);
                case SerializedPropertyType.Vector2Int: return Vector((Vector2)p.vector2IntValue);
                case SerializedPropertyType.Vector3Int: return Vector((Vector3)p.vector3IntValue);
                case SerializedPropertyType.Quaternion: return Vector(p.quaternionValue.eulerAngles) + " (euler)";
                case SerializedPropertyType.Rect: var r = p.rectValue; return $"x {Num(r.x)}, y {Num(r.y)}, w {Num(r.width)}, h {Num(r.height)}";
                case SerializedPropertyType.Bounds: var b = p.boundsValue; return $"center {Vector(b.center)}, extent {Vector(b.extents)}";
                case SerializedPropertyType.AnimationCurve: return $"curve with {p.animationCurveValue?.length ?? 0} keys";
                case SerializedPropertyType.Gradient: return "gradient";
                case SerializedPropertyType.ExposedReference:
                case SerializedPropertyType.ObjectReference:
                    return p.propertyType == SerializedPropertyType.ObjectReference
                        ? Reference(p.objectReferenceValue, p.objectReferenceInstanceIDValue, avatar)
                        : Reference(p.exposedReferenceValue, 0, avatar);
                case SerializedPropertyType.ManagedReference:
                    return string.IsNullOrEmpty(p.managedReferenceFullTypename) ? "None" : p.managedReferenceFullTypename.Split(' ').Last();
                default: return null;
            }
        }

        private static object Reference(UnityEngine.Object o, int instanceId, Transform avatar)
        {
            if (o == null) return instanceId != 0 ? "Missing" : "None";
            var type = o.GetType().Name;
            var asset = AssetDatabase.GetAssetPath(o);
            if (!string.IsNullOrEmpty(asset))
                return $"{o.name} ({type}) {asset}";
            var transform = o is Component component ? component.transform : o is GameObject go ? go.transform : null;
            if (transform == null) return $"{o.name} ({type})";
            var inAvatar = transform == avatar || transform.IsChildOf(avatar);
            return inAvatar ? $"{o.name} ({type}) avatar:{DshReflect.PathIn(transform, avatar)}"
                            : $"{o.name} ({type}) scene:{DshAvatarScene.HierarchyPath(transform)}";
        }

        private static string Num(float value) => value.ToString("0.####", CultureInfo.InvariantCulture);

        private static string Vector(Vector2 v) => $"{Num(v.x)}, {Num(v.y)}";
        private static string Vector(Vector3 v) => $"{Num(v.x)}, {Num(v.y)}, {Num(v.z)}";
        private static string Vector(Vector4 v) => $"{Num(v.x)}, {Num(v.y)}, {Num(v.z)}, {Num(v.w)}";
    }
}
