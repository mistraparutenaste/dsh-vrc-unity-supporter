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
    /// Reflection helpers for VRChat SDK and Modular Avatar components that the PhysBone, proportion, expression
    /// and parameter helpers change. Types are found by name so the helpers compile without those packages.
    /// Values travel as invariant text ("0.25", "true", "Angle", "0,1.4,0.05") so recipes and undo records
    /// stay plain JSON.
    /// </summary>
    internal static class DshReflect
    {
        private static readonly Dictionary<string, Type> Cache = new Dictionary<string, Type>();

        /// <summary>A loaded type by its full name, or by its short name inside one of the given namespaces.</summary>
        public static Type Find(string name, params string[] namespaces)
        {
            if (Cache.TryGetValue(name, out var cached) && cached != null) return cached;
            var found = DshVrc.LoadedType(name);
            if (found == null && !name.Contains("."))
            {
                foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    Type[] types;
                    try { types = assembly.GetTypes(); }
                    catch (ReflectionTypeLoadException error) { types = error.Types.Where(t => t != null).ToArray(); }
                    catch { continue; }
                    found = types.FirstOrDefault(t => t.Name == name && typeof(Component).IsAssignableFrom(t) &&
                        (namespaces.Length == 0 || namespaces.Any(n => (t.Namespace ?? "").StartsWith(n, StringComparison.Ordinal))));
                    if (found != null) break;
                }
            }
            Cache[name] = found;
            return found;
        }

        public static FieldInfo Field(Type type, string name) =>
            type.GetField(name, BindingFlags.Public | BindingFlags.Instance)
            ?? throw new InvalidOperationException($"{type.Name} has no field '{name}' in this SDK version.");

        public static string Format(object value)
        {
            switch (value)
            {
                case null: return "";
                case float f: return f.ToString("0.#####", CultureInfo.InvariantCulture);
                case double d: return d.ToString("0.#####", CultureInfo.InvariantCulture);
                case bool b: return b ? "true" : "false";
                case Vector3 v: return string.Join(",", new[] { v.x, v.y, v.z }.Select(c => c.ToString("0.#####", CultureInfo.InvariantCulture)));
                case UnityEngine.Object o: return o == null ? "" : o.name;
                default: return value.ToString();
            }
        }

        public static object Parse(Type type, string text)
        {
            text = (text ?? "").Trim();
            if (type == typeof(float)) return float.Parse(text, NumberStyles.Float, CultureInfo.InvariantCulture);
            if (type == typeof(int)) return int.Parse(text, NumberStyles.Integer, CultureInfo.InvariantCulture);
            if (type == typeof(bool)) return bool.Parse(text);
            if (type == typeof(Vector3)) return Vector(text);
            if (type.IsEnum)
            {
                var name = Enum.GetNames(type).FirstOrDefault(n => string.Equals(n, text, StringComparison.OrdinalIgnoreCase));
                if (name == null)
                    throw new InvalidOperationException($"'{text}' is not one of {string.Join(", ", Enum.GetNames(type))}.");
                return Enum.Parse(type, name);
            }
            throw new InvalidOperationException($"DSH cannot set a {type.Name} value from text.");
        }

        public static Vector3 Vector(string text)
        {
            var parts = (text ?? "").Split(',').Select(p => float.Parse(p.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture)).ToArray();
            if (parts.Length != 3) throw new InvalidOperationException($"'{text}' is not three numbers.");
            return new Vector3(parts[0], parts[1], parts[2]);
        }

        public static bool Same(object a, object b)
        {
            if (a is float fa && b is float fb) return Mathf.Abs(fa - fb) <= 1e-5f;
            if (a is Vector3 va && b is Vector3 vb) return (va - vb).sqrMagnitude <= 1e-10f;
            return Equals(a, b);
        }

        /// <summary>Set a public field from text; returns the earlier value as text when it changed, else null.</summary>
        public static string Set(Component component, string field, string text)
        {
            var info = Field(component.GetType(), field);
            var value = Parse(info.FieldType, text);
            var before = info.GetValue(component);
            if (Same(before, value)) return null;
            info.SetValue(component, value);
            Dirty(component);
            return Format(before);
        }

        public static void Dirty(UnityEngine.Object target)
        {
            EditorUtility.SetDirty(target);
            if (target is Component component && PrefabUtility.IsPartOfPrefabInstance(component))
                PrefabUtility.RecordPrefabInstancePropertyModifications(component);
        }

        /// <summary>
        /// After remove puts a value back: when it now equals the prefab's own value, drop the scene override too,
        /// so the scene file goes back to how it was (an override holding the prefab's value is still a change).
        /// Lists match when each item is the instance of the prefab's item at the same place.
        /// </summary>
        public static void RevertIfSource(Component component, string field)
        {
            if (component == null || !PrefabUtility.IsPartOfPrefabInstance(component)) return;
            var source = PrefabUtility.GetCorrespondingObjectFromSource(component);
            if (source == null) return;
            var info = component.GetType().GetField(field, BindingFlags.Public | BindingFlags.Instance);
            if (info == null) return;
            var mine = info.GetValue(component);
            var theirs = info.GetValue(source);
            bool same;
            if (mine is IList a && theirs is IList b)
                same = a.Count == b.Count && Enumerable.Range(0, a.Count).All(i =>
                    a[i] is UnityEngine.Object x && x != null && b[i] is UnityEngine.Object y && y != null
                        ? PrefabUtility.GetCorrespondingObjectFromSource(x) == y || x == y
                        : Equals(a[i], b[i]) || (a[i] as UnityEngine.Object == null && b[i] as UnityEngine.Object == null));
            else same = Same(mine, theirs);
            if (!same) return;
            var property = new SerializedObject(component).FindProperty(field);
            if (property != null && property.prefabOverride)
                PrefabUtility.RevertPropertyOverride(property, InteractionMode.AutomatedAction);
        }

        public static IList List(Component component, string field) =>
            Field(component.GetType(), field).GetValue(component) as IList
            ?? throw new InvalidOperationException($"{component.GetType().Name}.{field} is not a list.");

        /// <summary>Components that belong to a prefab asset cannot be destroyed in the scene; scene additions can.</summary>
        public static bool AddedInScene(Component component) =>
            !PrefabUtility.IsPartOfPrefabInstance(component) || PrefabUtility.IsAddedComponentOverride(component);

        public static string PathIn(Transform target, Transform avatar) =>
            target == null ? "" : target == avatar ? "" : AnimationUtility.CalculateTransformPath(target, avatar);

        public static Transform Bone(GameObject avatar, string bone)
        {
            var animator = avatar.GetComponent<Animator>();
            if (animator == null || !animator.isHuman)
                throw new InvalidOperationException("This needs a humanoid avatar (Animator with a humanoid Avatar).");
            if (!Enum.TryParse<HumanBodyBones>(bone, out var id) || id == HumanBodyBones.LastBone)
                throw new InvalidOperationException($"Unknown humanoid bone '{bone}'.");
            return animator.GetBoneTransform(id) ?? throw new InvalidOperationException($"The avatar has no {id} bone.");
        }
    }

    /// <summary>
    /// One undo entry, the same shape for every helper: what kind of change, where, and the value before it.
    /// The first entry per key is kept across applies, so remove goes back to the value before DSH changed it.
    /// </summary>
    [Serializable]
    internal sealed class DshUndo
    {
        public string key = "";
        public string kind = "";
        public string path = "";
        public int index = -1;
        public string field = "";
        public string before = "";
        public string other = "";

        public Dictionary<string, object> Describe() => new Dictionary<string, object>
        {
            { "key", key }, { "kind", kind }, { "path", path }, { "index", index }, { "field", field },
            { "before", before }, { "other", other },
        };

        public static object[] DescribeAll(IEnumerable<DshUndo> entries) => entries.Select(e => (object)e.Describe()).ToArray();
    }

    internal sealed class DshUndoLog
    {
        public readonly List<DshUndo> Entries = new List<DshUndo>();

        public void Add(DshUndo entry)
        {
            if (Entries.All(e => e.key != entry.key)) Entries.Add(entry);
        }
    }
}
