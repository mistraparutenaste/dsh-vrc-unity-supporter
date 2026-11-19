// Shared helpers for batch-mode tasks in this project.
// Copy this file (and DshInspect.cs) to <Project>/Assets/DSH/Editor/.
//
// A task script writes its outcome through DshApply.WriteResult so a human, or an
// agent, can read what happened without parsing the Unity log.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace DSH
{
    public static class DshApply
    {
        public static string ResultsDirectory => Path.Combine(Application.dataPath, "DSH", "Results");

        /// <summary>Writes the current runner's result, or the legacy file for direct Unity invocations.</summary>
        public static string WriteResult(string task, Dictionary<string, object> data)
        {
            data["task"] = task;
            var path = Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH");
            if (string.IsNullOrEmpty(path)) path = Path.Combine(ResultsDirectory, task + ".json");
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllText(path, MiniJson.Serialize(data), new UTF8Encoding(false));
            Debug.Log($"[DSH] result written: {path}");
            return path;
        }

        /// <summary>Adds a reviewable line to a result's "changes" list.</summary>
        public static void Note(Dictionary<string, object> data, string change)
        {
            if (!data.TryGetValue("changes", out var list) || !(list is List<string> changes))
            {
                changes = new List<string>();
                data["changes"] = changes;
            }
            changes.Add(change);
        }
    }

    /// <summary>Just enough JSON for task results. Keeps the template dependency-free.</summary>
    public static class MiniJson
    {
        public static string Serialize(object value)
        {
            var sb = new StringBuilder();
            Write(sb, value);
            return sb.ToString();
        }

        private static void Write(StringBuilder sb, object value)
        {
            switch (value)
            {
                case null:
                    sb.Append("null");
                    break;
                case string s:
                    WriteString(sb, s);
                    break;
                case bool b:
                    sb.Append(b ? "true" : "false");
                    break;
                case int i:
                    sb.Append(i.ToString(CultureInfo.InvariantCulture));
                    break;
                case long l:
                    sb.Append(l.ToString(CultureInfo.InvariantCulture));
                    break;
                case float f:
                    sb.Append(f.ToString("R", CultureInfo.InvariantCulture));
                    break;
                case double d:
                    sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
                    break;
                case IDictionary<string, object> map:
                    sb.Append('{');
                    var first = true;
                    foreach (var kv in map)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteString(sb, kv.Key);
                        sb.Append(':');
                        Write(sb, kv.Value);
                    }
                    sb.Append('}');
                    break;
                case IEnumerable seq:
                    sb.Append('[');
                    var firstItem = true;
                    foreach (var item in seq)
                    {
                        if (!firstItem) sb.Append(',');
                        firstItem = false;
                        Write(sb, item);
                    }
                    sb.Append(']');
                    break;
                default:
                    WriteString(sb, value.ToString());
                    break;
            }
        }

        private static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }
}
