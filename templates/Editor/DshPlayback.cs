using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace DSH.Editor
{
    /// <summary>
    /// What Gesture Manager does, in batch mode: build a copy of the avatar with the VRChat SDK (VRCFury and Modular
    /// Avatar run as in an upload), drive the built FX controller with parameters (hand gestures, menu items, raw
    /// values) for some frames, and report per state what changed against the resting state: blendshape weights,
    /// objects turned on or off, and constraints frozen in the world. Optional expectations give a pass or fail, and
    /// each state is rendered. Nothing is saved.
    /// </summary>
    public static class DshPlayback
    {
        [Serializable]
        private sealed class Value
        {
            public string name = "";
            public float value = 0;
        }

        [Serializable]
        private sealed class Expect
        {
            public string path = "";
            public string shape = "";
            public float min = float.NaN;
            public float max = float.NaN;
            public string active = "";          // "true" / "false" / ""
            public string freezeToWorld = "";   // "true" / "false" / ""
        }

        [Serializable]
        private sealed class State
        {
            public string label = "";
            public int gestureLeft = -1;
            public int gestureRight = -1;
            public string[] menu = Array.Empty<string>();
            public Value[] parameters = Array.Empty<Value>();
            public Expect[] expect = Array.Empty<Expect>();
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string views = "face";
            public int size = 384;
            public int frames = 30;
            public bool render = true;
            public State[] states = Array.Empty<State>();
        }

        private sealed class Snapshot
        {
            public readonly Dictionary<string, float> Shapes = new Dictionary<string, float>();
            public readonly Dictionary<string, bool> Active = new Dictionary<string, bool>();
            public readonly Dictionary<string, bool> Frozen = new Dictionary<string, bool>();
        }

        private const int MaxListed = 40;

        public static void Test()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            var graphs = new List<PlayableGraph>();
            GameObject built = null;
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                if (request.render) DshCapture.RequireGraphics();
                var views = request.render ? DshCapture.ParseViews(request.views) : Array.Empty<string>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                built = DshVrc.PreprocessCopy(avatar);
                built.SetActive(false);  // a template for the instances below
                var frames = Mathf.Clamp(request.frames, 1, 600);

                var rest = Instance(built, new State { label = "rest" }, frames, graphs, out var restMenu);
                var restShot = Take(rest);
                var reports = new List<object>();
                var failed = 0;
                var rows = new List<(string label, Func<GameObject, GameObject> make)>();
                if (request.render) rows.Add(("rest", _ => rest));
                else UnityEngine.Object.DestroyImmediate(rest);

                foreach (var state in request.states)
                {
                    var instance = Instance(built, state, frames, graphs, out var used);
                    var shot = Take(instance);
                    var report = new Dictionary<string, object> { { "label", state.label }, { "parameters", used } };
                    report["changedShapes"] = shot.Shapes.Where(p => !restShot.Shapes.TryGetValue(p.Key, out var r) || Mathf.Abs(r - p.Value) > 0.5f)
                        .Concat(restShot.Shapes.Where(p => !shot.Shapes.ContainsKey(p.Key)).Select(p => new KeyValuePair<string, float>(p.Key, 0)))
                        .OrderByDescending(p => p.Value).Take(MaxListed)
                        .Select(p => $"{p.Key}: {(restShot.Shapes.TryGetValue(p.Key, out var r) ? r : 0):0.#} -> {p.Value:0.#}").ToArray();
                    report["turnedOn"] = shot.Active.Where(p => p.Value && restShot.Active.TryGetValue(p.Key, out var r) && !r).Select(p => p.Key).Take(MaxListed).ToArray();
                    report["turnedOff"] = shot.Active.Where(p => !p.Value && restShot.Active.TryGetValue(p.Key, out var r) && r).Select(p => p.Key).Take(MaxListed).ToArray();
                    report["frozenInWorld"] = shot.Frozen.Where(p => p.Value).Select(p => p.Key).ToArray();
                    var face = DshAvatarScene.Descriptor(instance)?.GetType().GetField("VisemeSkinnedMesh")
                        ?.GetValue(DshAvatarScene.Descriptor(instance)) as SkinnedMeshRenderer;
                    var facePath = face == null ? "" : DshReflect.PathIn(face.transform, instance.transform);
                    var checks = state.expect.Select(e => Check(e, shot, facePath)).ToArray();
                    if (checks.Length > 0)
                    {
                        report["checks"] = checks;
                        if (checks.Any(c => !(bool)((Dictionary<string, object>)c)["pass"])) failed++;
                    }
                    reports.Add(report);
                    if (request.render) rows.Add((state.label, _ => instance));
                    else UnityEngine.Object.DestroyImmediate(instance);
                }
                result["states"] = reports;
                result["restParameters"] = restMenu;
                result["failedStates"] = failed;
                if (request.render)
                {
                    result["image"] = DshCapture.RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048), rows);
                    result["rows"] = rows.Select(r => r.label).ToArray();
                    result["columns"] = views;
                }
                result["frames"] = frames;
                result["note"] = "Built with the VRChat SDK and driven through the built FX controller; PhysBones, IK and network sync are not simulated.";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            finally
            {
                foreach (var graph in graphs) if (graph.IsValid()) graph.Destroy();
                if (built != null) UnityEngine.Object.DestroyImmediate(built);
            }
            DshAvatarScene.Finish("Playback", result);
        }

        /// <summary>A fresh instance of the built avatar with the FX controller evaluated for the state.</summary>
        private static GameObject Instance(GameObject built, State state, int frames, List<PlayableGraph> graphs,
            out Dictionary<string, object> used)
        {
            var instance = UnityEngine.Object.Instantiate(built);
            instance.name = built.name;
            instance.SetActive(true);
            var descriptor = DshAvatarScene.Descriptor(instance);
            var fx = DshVrc.PublicItems(descriptor, "baseAnimationLayers")
                .Where(layer => DshVrc.PublicMember(layer, "type")?.ToString() == "FX")
                .Select(layer => DshVrc.PublicMember(layer, "animatorController")).OfType<AnimatorController>().FirstOrDefault()
                ?? throw new InvalidOperationException("The built avatar has no FX controller.");
            var animator = instance.GetComponent<Animator>() ?? instance.AddComponent<Animator>();
            animator.enabled = true;
            var graph = PlayableGraph.Create("DSH Playback " + state.label);
            graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            graphs.Add(graph);
            var playable = AnimatorControllerPlayable.Create(graph, fx);
            var output = AnimationPlayableOutput.Create(graph, "FX", animator);
            output.SetSourcePlayable(playable);

            var values = new Dictionary<string, float>();
            // What VRChat sets: the saved defaults of the expression parameters, and a local, grounded player.
            foreach (var item in DshVrc.PublicItems(DshVrc.PublicMember(descriptor, "expressionParameters"), "parameters"))
                if (DshVrc.PublicMember(item, "name") is string name && name.Length > 0 && DshVrc.PublicMember(item, "defaultValue") is float d)
                    values[name] = d;
            values["IsLocal"] = 1;
            values["Grounded"] = 1;
            values["AvatarVersion"] = 3;
            used = new Dictionary<string, object>();
            if (state.gestureLeft >= 0) { values["GestureLeft"] = state.gestureLeft; values["GestureLeftWeight"] = 1; used["GestureLeft"] = state.gestureLeft; }
            if (state.gestureRight >= 0) { values["GestureRight"] = state.gestureRight; values["GestureRightWeight"] = 1; used["GestureRight"] = state.gestureRight; }
            foreach (var item in state.menu)
            {
                // "!Menu/Item" turns the item off (for toggles that start on).
                var off = item.StartsWith("!", StringComparison.Ordinal);
                var path = item.TrimStart('!');
                var (control, parameter, _) = DshVrc.GeneratedToggle(descriptor, path);
                var value = off ? 0f : DshVrc.PublicMember(control, "value") is float v && v != 0 ? v : 1f;
                values[parameter] = value;
                used[item] = $"{parameter} = {value}";
            }
            foreach (var p in state.parameters)
            {
                values[p.name] = p.value;
                used[p.name] = p.value;
            }
            foreach (var parameter in fx.parameters)
            {
                if (!values.TryGetValue(parameter.name, out var value)) continue;
                switch (parameter.type)
                {
                    case AnimatorControllerParameterType.Bool: playable.SetBool(parameter.name, value != 0); break;
                    case AnimatorControllerParameterType.Int: playable.SetInteger(parameter.name, Mathf.RoundToInt(value)); break;
                    case AnimatorControllerParameterType.Float: playable.SetFloat(parameter.name, value); break;
                }
            }
            var missing = state.parameters.Select(p => p.name).Where(n => fx.parameters.All(p => p.name != n)).ToArray();
            if (missing.Length > 0) used["notInFx"] = missing;
            for (var i = 0; i < frames; i++) graph.Evaluate(1f / 60f);
            // The graph runs the state machines, but in edit mode its output is not written to the objects, so the
            // current state of each layer is evaluated here and its values put on the instance (see Apply).
            var layers = new List<string>();
            var final = new Dictionary<EditorCurveBinding, float>();
            for (var i = 0; i < playable.GetLayerCount() && i < fx.layers.Length; i++)
            {
                var info = playable.GetCurrentAnimatorStateInfo(i);
                var node = FindState(fx.layers[i].stateMachine, info.fullPathHash, info.shortNameHash);
                if (node == null) continue;
                var weight = i == 0 ? 1f : playable.GetLayerWeight(i);
                var sampled = new Dictionary<EditorCurveBinding, float>();
                Sample(node.motion, 1f, info.normalizedTime, playable, sampled);
                foreach (var pair in sampled)
                    final[pair.Key] = final.TryGetValue(pair.Key, out var below) ? Mathf.Lerp(below, pair.Value, weight) : pair.Value;
                if (fx.layers[i].name.StartsWith("DSH ", StringComparison.Ordinal) || sampled.Count > 0 && layers.Count < 60)
                    layers.Add(fx.layers[i].name + ": " + node.name);
            }
            used["layerStates"] = layers.Take(60).ToArray();
            Apply(instance, final);
            return instance;
        }

        private static AnimatorState FindState(AnimatorStateMachine machine, int fullHash, int shortHash)
        {
            foreach (var child in machine.states)
                if (child.state.nameHash == shortHash || Animator.StringToHash(machine.name + "." + child.state.name) == fullHash)
                    return child.state;
            foreach (var sub in machine.stateMachines)
            {
                var found = FindState(sub.stateMachine, fullHash, shortHash);
                if (found != null) return found;
            }
            return null;
        }

        private static float Parameter(AnimatorControllerPlayable playable, string name)
        {
            if (string.IsNullOrEmpty(name)) return 0;
            for (var i = 0; i < playable.GetParameterCount(); i++)
            {
                var p = playable.GetParameter(i);
                if (p.name != name) continue;
                switch (p.type)
                {
                    case AnimatorControllerParameterType.Float: return playable.GetFloat(name);
                    case AnimatorControllerParameterType.Int: return playable.GetInteger(name);
                    default: return playable.GetBool(name) ? 1 : 0;
                }
            }
            return 0;
        }

        /// <summary>
        /// Values a motion sets, times its weight: a clip at the state's time, or a blend tree (Direct adds its
        /// children by their parameters; 1D blends the two thresholds around the parameter; 2D takes the closest).
        /// </summary>
        private static void Sample(Motion motion, float weight, float normalizedTime, AnimatorControllerPlayable playable,
            Dictionary<EditorCurveBinding, float> values)
        {
            if (motion == null || weight <= 0) return;
            if (motion is AnimationClip clip)
            {
                var time = clip.length <= 0 ? 0 : (clip.isLooping ? normalizedTime % 1f : Mathf.Clamp01(normalizedTime)) * clip.length;
                foreach (var binding in AnimationUtility.GetCurveBindings(clip))
                {
                    var curve = AnimationUtility.GetEditorCurve(clip, binding);
                    if (curve == null) continue;
                    var v = curve.Evaluate(time) * weight;
                    values[binding] = values.TryGetValue(binding, out var sum) ? sum + v : v;
                }
                return;
            }
            if (!(motion is BlendTree tree) || tree.children.Length == 0) return;
            var children = tree.children;
            switch (tree.blendType)
            {
                case BlendTreeType.Direct:
                    foreach (var child in children)
                        Sample(child.motion, weight * Parameter(playable, child.directBlendParameter), normalizedTime, playable, values);
                    break;
                case BlendTreeType.Simple1D:
                    var x = Parameter(playable, tree.blendParameter);
                    var sorted = children.OrderBy(c => c.threshold).ToArray();
                    if (x <= sorted[0].threshold) { Sample(sorted[0].motion, weight, normalizedTime, playable, values); break; }
                    if (x >= sorted[sorted.Length - 1].threshold) { Sample(sorted[sorted.Length - 1].motion, weight, normalizedTime, playable, values); break; }
                    for (var i = 0; i < sorted.Length - 1; i++)
                    {
                        if (x < sorted[i].threshold || x > sorted[i + 1].threshold) continue;
                        var span = sorted[i + 1].threshold - sorted[i].threshold;
                        var t = span <= 0 ? 0 : (x - sorted[i].threshold) / span;
                        Sample(sorted[i].motion, weight * (1 - t), normalizedTime, playable, values);
                        Sample(sorted[i + 1].motion, weight * t, normalizedTime, playable, values);
                        break;
                    }
                    break;
                default:
                    var point = new Vector2(Parameter(playable, tree.blendParameter), Parameter(playable, tree.blendParameterY));
                    var nearest = children.OrderBy(c => (c.position - point).sqrMagnitude).First();
                    Sample(nearest.motion, weight, normalizedTime, playable, values);
                    break;
            }
        }

        /// <summary>Put the evaluated values on the instance: blendshapes, objects on or off, constraint switches.</summary>
        private static void Apply(GameObject instance, Dictionary<EditorCurveBinding, float> values)
        {
            foreach (var pair in values)
            {
                var binding = pair.Key;
                var target = string.IsNullOrEmpty(binding.path) ? instance.transform : instance.transform.Find(binding.path);
                if (target == null) continue;
                if (binding.type == typeof(GameObject) && binding.propertyName == "m_IsActive")
                    target.gameObject.SetActive(pair.Value > 0.5f);
                else if (binding.type == typeof(SkinnedMeshRenderer) && binding.propertyName.StartsWith("blendShape.", StringComparison.Ordinal))
                {
                    var renderer = target.GetComponent<SkinnedMeshRenderer>();
                    var index = renderer == null || renderer.sharedMesh == null ? -1 : renderer.sharedMesh.GetBlendShapeIndex(binding.propertyName.Substring(11));
                    if (index >= 0) renderer.SetBlendShapeWeight(index, pair.Value);
                }
                else if (binding.propertyName == "FreezeToWorld" || binding.propertyName == "IsActive")
                {
                    var component = target.GetComponent(binding.type);
                    var field = component == null ? null : binding.type.GetField(binding.propertyName);
                    if (field != null && field.FieldType == typeof(bool)) field.SetValue(component, pair.Value > 0.5f);
                }
            }
        }

        private static Snapshot Take(GameObject instance)
        {
            var shot = new Snapshot();
            var root = instance.transform;
            foreach (var renderer in instance.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var mesh = renderer.sharedMesh;
                if (mesh == null) continue;
                var path = DshReflect.PathIn(renderer.transform, root);
                for (var i = 0; i < mesh.blendShapeCount; i++)
                {
                    var weight = renderer.GetBlendShapeWeight(i);
                    if (Mathf.Abs(weight) > 0.01f) shot.Shapes[path + ":" + mesh.GetBlendShapeName(i)] = weight;
                }
            }
            foreach (var t in instance.GetComponentsInChildren<Transform>(true))
                if (t != root) shot.Active[DshReflect.PathIn(t, root)] = t.gameObject.activeSelf;
            var constraint = DshReflect.Find("VRCParentConstraint", "VRC");
            if (constraint != null)
                foreach (var c in instance.GetComponentsInChildren(constraint, true))
                    shot.Frozen[DshReflect.PathIn(c.transform, root)] = constraint.GetField("FreezeToWorld")?.GetValue(c) is bool b && b;
            return shot;
        }

        /// <summary>
        /// The object an expectation names: a path in the built avatar, "@face" (the Lip Sync mesh), or "**/Name"
        /// (any object of that name, for items that build plugins move under a bone).
        /// </summary>
        private static string Resolve(string path, IEnumerable<string> paths, string facePath)
        {
            if (path == "@face") return facePath;
            if (!path.StartsWith("**/", StringComparison.Ordinal)) return path;
            var name = path.Substring(3);
            return paths.FirstOrDefault(p => p == name || p.EndsWith("/" + name, StringComparison.Ordinal)) ?? path;
        }

        private static object Check(Expect expect, Snapshot shot, string facePath)
        {
            var check = new Dictionary<string, object> { { "path", expect.path } };
            bool pass;
            if (!string.IsNullOrEmpty(expect.shape))
            {
                var key = Resolve(expect.path, shot.Active.Keys, facePath) + ":" + expect.shape;
                check["resolved"] = key;
                var value = shot.Shapes.TryGetValue(key, out var w) ? w : 0f;
                check["shape"] = expect.shape;
                check["value"] = Math.Round(value, 2);
                pass = (float.IsNaN(expect.min) || value >= expect.min - 0.01f) && (float.IsNaN(expect.max) || value <= expect.max + 0.01f);
            }
            else if (!string.IsNullOrEmpty(expect.active))
            {
                var path = Resolve(expect.path, shot.Active.Keys, facePath);
                check["resolved"] = path;
                var found = shot.Active.TryGetValue(path, out var on);
                check["active"] = found ? (object)on : "missing";
                pass = found && on == (expect.active == "true");
            }
            else if (!string.IsNullOrEmpty(expect.freezeToWorld))
            {
                var path = Resolve(expect.path, shot.Frozen.Keys, facePath);
                check["resolved"] = path;
                var found = shot.Frozen.TryGetValue(path, out var frozen);
                check["freezeToWorld"] = found ? (object)frozen : "no constraint";
                pass = found && frozen == (expect.freezeToWorld == "true");
            }
            else throw new InvalidOperationException("Each expectation needs shape, active or freezeToWorld.");
            check["pass"] = pass;
            return check;
        }
    }
}
