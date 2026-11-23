using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Facial expressions without touching the avatar's own animators: hand gestures, expressions picked from the
    /// menu (a lock that wins over gestures) and single shape toggles such as a blush. DSH writes an FX controller,
    /// its clips and a menu to the recipe's Generated folder and adds one "DSH Expression &lt;name&gt;" object
    /// with Modular Avatar Merge Animator, Parameters and Menu Installer. The author's expression layers stay; the
    /// DSH layer comes after them and sets every shape it controls in every state, so it wins for those shapes.
    /// </summary>
    public static class DshExpression
    {
        [Serializable]
        private sealed class Shape
        {
            public string shape = "";
            public float weight = 0;
        }

        [Serializable]
        private sealed class Entry
        {
            public string label = "";
            public string hand = "";    // gestures: left or right
            public int gesture = 0;     // gestures: GestureLeft / GestureRight value 1-7
            public bool saved = false;  // toggles
            public Shape[] shapes = Array.Empty<Shape>();
        }

        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string name = "";
            public string folder = "";
            public string renderer = "";
            public string menu = "";
            public string overrideMode = "listed";
            public bool verifySdk = false;
            public string filter = "";
            public Entry[] gestures = Array.Empty<Entry>();
            public Entry[] locks = Array.Empty<Entry>();
            public Entry[] toggles = Array.Empty<Entry>();
        }

        [Serializable]
        private sealed class CaptureRequest
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string views = "face";
            public int size = 384;
            public Request recipe = new Request();
        }

        public const string HolderPrefix = "DSH Expression ";
        private const string MergeAnimatorType = "nadena.dev.modular_avatar.core.ModularAvatarMergeAnimator";
        private const string ParametersType = "nadena.dev.modular_avatar.core.ModularAvatarParameters";
        private const string InstallerType = "nadena.dev.modular_avatar.core.ModularAvatarMenuInstaller";
        private const string MenuType = "VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu";
        private static readonly string[] GestureNames = { "Neutral", "Fist", "Open", "Point", "Peace", "RockNRoll", "Gun", "ThumbsUp" };
        private const float Fade = 0.1f;

        /// <summary>Read-only: the face mesh, its blendshapes, and what the avatar's own gesture layers do.</summary>
        public static void List()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var face = Face(avatar, request.renderer);
                var path = DshReflect.PathIn(face.transform, avatar.transform);
                result["renderer"] = path;
                var filter = request.filter ?? "";
                var names = Enumerable.Range(0, face.sharedMesh.blendShapeCount).Select(face.sharedMesh.GetBlendShapeName)
                    .Where(n => filter.Length == 0 || n.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0).ToArray();
                result["shapeCount"] = face.sharedMesh.blendShapeCount;
                result["shapes"] = names.Take(400).ToArray();
                result["truncated"] = names.Length > 400;
                result["authorGestures"] = AuthorGestures(avatar).Take(60).ToArray();
                result["attached"] = avatar.transform.Cast<Transform>().Where(t => t.name.StartsWith(HolderPrefix, StringComparison.Ordinal))
                    .Select(t => t.name.Substring(HolderPrefix.Length)).ToArray();
                result["modularAvatar"] = DshVrc.LoadedType(MergeAnimatorType) != null;
                result["note"] = "authorGestures lists, per gesture layer state, the hand condition and the face shapes its clip sets (non-zero).";
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Expressions", result);
        }

        public static void Apply()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                CheckFolder(request);
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["expression"] = request.name;
                var changes = ApplyRecipe(avatar, request, true, out var plan);
                result["applied"] = changes;
                result["controlled"] = plan.Controlled.Select(s => s.shape).ToArray();
                if (changes.Count > 0)
                {
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Applied expression {request.name} ({changes.Count} changes)");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                }
                var remaining = ApplyRecipe(avatar, request, false, out _);
                if (remaining.Count > 0)
                    throw new InvalidOperationException("The saved scene does not hold the expression: " + string.Join("; ", remaining.Take(5)));
                result["holder"] = HolderPrefix + request.name;
                var inUse = System.IO.Path.GetDirectoryName(AssetDatabase.GetAssetPath(
                    AssetDatabase.LoadAssetAtPath<UnityEngine.Object>($"{request.folder}/Generated/{plan.Fingerprint.Substring(0, 8)}/{request.name}.controller")))?.Replace('\\', '/');
                result["generated"] = inUse;
                result["deletedUnused"] = DeleteUnused(request.folder + "/Generated", inUse ?? "");
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
            DshAvatarScene.Finish("ExpressionApply", result);
        }

        /// <summary>Remove the expression object and the generated assets; the recipe file stays.</summary>
        public static void Remove()
        {
            var result = new Dictionary<string, object> { { "ok", false }, { "saved", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                CheckFolder(request);
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["scene"] = scene.path;
                result["expression"] = request.name;
                var holder = DshVrc.FindHolder(avatar, HolderPrefix + request.name);
                result["holderRemoved"] = holder != null;
                if (holder != null)
                {
                    UnityEngine.Object.DestroyImmediate(holder);
                    DshPhysBone.Save(scene, request.expectedSceneDigest, result, $"Removed expression {request.name}");
                    scene = DshAvatarScene.OpenScene(request.scene);
                    avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                    if (DshVrc.FindHolder(avatar, HolderPrefix + request.name) != null)
                        throw new InvalidOperationException("The expression is still in the saved scene.");
                }
                result["deleted"] = DeleteUnused(request.folder + "/Generated", "");
                result["sceneDigest"] = DshAvatarScene.SceneDigest(scene.path);
                result["ok"] = true;
                result["verified"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("ExpressionRemove", result);
        }

        /// <summary>One face render per expression (gestures, locks, toggles) next to the face as it is.</summary>
        public static void Capture()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                DshCapture.RequireGraphics();
                var request = DshAvatarScene.ReadRequest<CaptureRequest>();
                var views = DshCapture.ParseViews(request.views);
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                var recipe = JsonUtility.FromJson<Request>(JsonUtility.ToJson(request.recipe));
                var plan = Plan(avatar, recipe);
                var rows = new List<(string label, Func<GameObject, GameObject> make)>
                {
                    ("as it is", source => UnityEngine.Object.Instantiate(source)),
                };
                foreach (var state in plan.States.Where(s => s.Kind != "neutral").Take(15))
                    rows.Add((state.Label, source =>
                    {
                        var copy = UnityEngine.Object.Instantiate(source);
                        Pose(copy, plan.RendererPath, state.Values);
                        return copy;
                    }));
                result["image"] = DshCapture.RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048), rows);
                result["columns"] = views;
                result["rows"] = rows.Select(r => r.label).ToArray();
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("ExpressionCapture", result);
        }

        private static void CheckFolder(Request request)
        {
            if (string.IsNullOrEmpty(request.name) || request.folder != "Assets/DSH/Expressions/" + request.name)
                throw new InvalidOperationException("The request does not describe an expression under Assets/DSH/Expressions.");
        }

        private static SkinnedMeshRenderer Face(GameObject avatar, string path)
        {
            SkinnedMeshRenderer face;
            if (!string.IsNullOrEmpty(path))
                face = avatar.transform.Find(path)?.GetComponent<SkinnedMeshRenderer>();
            else
                face = DshReflect.Field(DshAvatarScene.Descriptor(avatar).GetType(), "VisemeSkinnedMesh")
                    .GetValue(DshAvatarScene.Descriptor(avatar)) as SkinnedMeshRenderer;
            if (face == null || face.sharedMesh == null || !face.transform.IsChildOf(avatar.transform))
                throw new InvalidOperationException(string.IsNullOrEmpty(path)
                    ? "The avatar descriptor names no face mesh (Lip Sync mesh). Give 'renderer' in the recipe."
                    : $"No skinned mesh at '{path}' under the avatar.");
            return face;
        }

        private sealed class State
        {
            public string Kind;    // neutral, gesture, lock, toggle-off, toggle-on
            public string Label;
            public string Hand;
            public int Gesture;
            public int Index;
            public Dictionary<string, float> Values;
        }

        private sealed class Planned
        {
            public string RendererPath;
            public List<Shape> Controlled = new List<Shape>();  // gesture/lock shapes with their resting weight
            public List<State> States = new List<State>();
            public string Fingerprint;
        }

        /// <summary>The states DSH builds, each with the weight of every shape it controls.</summary>
        private static Planned Plan(GameObject avatar, Request request)
        {
            var face = Face(avatar, request.renderer);
            var plan = new Planned { RendererPath = DshReflect.PathIn(face.transform, avatar.transform) };
            var mesh = face.sharedMesh;
            float Rest(string shape)
            {
                var index = mesh.GetBlendShapeIndex(shape);
                if (index < 0) throw new InvalidOperationException($"'{plan.RendererPath}' has no blendshape named '{shape}'.");
                return face.GetBlendShapeWeight(index);
            }
            var controlled = request.gestures.Concat(request.locks).SelectMany(e => e.shapes).Select(s => s.shape).ToList();
            if (request.overrideMode == "all")
                controlled.AddRange(AuthorShapes(avatar, plan.RendererPath));
            foreach (var shape in controlled.Distinct())
                plan.Controlled.Add(new Shape { shape = shape, weight = Rest(shape) });
            var toggleShapes = request.toggles.SelectMany(t => t.shapes).Select(s => s.shape).ToArray();
            var both = toggleShapes.Where(s => plan.Controlled.Any(c => c.shape == s)).Distinct().ToArray();
            if (both.Length > 0)
                throw new InvalidOperationException($"Shapes used by a toggle cannot also be in a gesture or menu expression: {string.Join(", ", both.Take(5))}.");
            foreach (var s in toggleShapes) Rest(s);

            Dictionary<string, float> Values(Entry entry)
            {
                var values = plan.Controlled.ToDictionary(c => c.shape, c => c.weight);
                foreach (var s in entry?.shapes ?? Array.Empty<Shape>()) values[s.shape] = Mathf.Clamp(s.weight, 0, 100);
                return values;
            }
            plan.States.Add(new State { Kind = "neutral", Label = "neutral", Values = Values(null) });
            foreach (var entry in request.gestures)
                plan.States.Add(new State { Kind = "gesture", Label = entry.label, Hand = entry.hand, Gesture = entry.gesture, Values = Values(entry) });
            for (var i = 0; i < request.locks.Length; i++)
                plan.States.Add(new State { Kind = "lock", Label = request.locks[i].label, Index = i + 1, Values = Values(request.locks[i]) });
            for (var i = 0; i < request.toggles.Length; i++)
            {
                var entry = request.toggles[i];
                plan.States.Add(new State { Kind = "toggle-off", Label = entry.label + " off", Index = i,
                    Values = entry.shapes.ToDictionary(s => s.shape, s => Rest(s.shape)) });
                plan.States.Add(new State { Kind = "toggle-on", Label = entry.label, Index = i,
                    Values = entry.shapes.ToDictionary(s => s.shape, s => Mathf.Clamp(s.weight, 0, 100)) });
            }
            // Only what shapes the generated assets counts (not the scene digest or SDK switch of this run).
            var recipeOnly = new Request
            {
                name = request.name, folder = request.folder, renderer = request.renderer, menu = request.menu,
                overrideMode = request.overrideMode, gestures = request.gestures, locks = request.locks, toggles = request.toggles,
            };
            plan.Fingerprint = Hash(JsonUtility.ToJson(recipeOnly) + "|" + plan.RendererPath + "|" +
                string.Join(";", plan.States.Select(s => s.Kind + s.Label + s.Hand + s.Gesture + s.Index + ":" +
                    string.Join(",", s.Values.OrderBy(v => v.Key, StringComparer.Ordinal).Select(v => v.Key + "=" + v.Value.ToString("0.###"))))));
            return plan;
        }

        private static string Hash(string text)
        {
            using (var sha = System.Security.Cryptography.SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(text))).Replace("-", "").Substring(0, 32).ToLowerInvariant();
        }

        private static string Parameter(Request request, string what) => $"DSH/{request.name}/{what}";

        private static List<string> ApplyRecipe(GameObject avatar, Request request, bool write, out Planned plan)
        {
            plan = Plan(avatar, request);
            var changes = new List<string>();
            // One folder per fingerprint: another scene (or another version of the avatar) may still use an
            // earlier build, so a change never rewrites assets in place.
            var generated = $"{request.folder}/Generated/{plan.Fingerprint.Substring(0, 8)}";
            var controllerPath = $"{generated}/{request.name}.controller";
            var importer = AssetImporter.GetAtPath(controllerPath);
            var current = importer != null && importer.userData == "dsh:" + plan.Fingerprint;
            if (!current)
            {
                if (!write) return new List<string> { "the generated controller does not match the recipe" };
                BuildAssets(avatar, request, plan, generated, controllerPath);
                changes.Add($"generated {controllerPath} ({plan.States.Count} states)");
            }
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            var menu = AssetDatabase.LoadAssetAtPath<ScriptableObject>($"{generated}/{request.name}_Menu.asset");

            var holderName = HolderPrefix + request.name;
            var holder = DshVrc.FindHolder(avatar, holderName);
            if (holder == null)
            {
                if (!write) return new List<string> { $"{holderName} is missing" };
                holder = new GameObject(holderName);
                holder.transform.SetParent(avatar.transform, false);
                changes.Add($"added {holderName}");
            }
            changes.AddRange(EnsureMergeAnimator(holder, controller, write));
            changes.AddRange(EnsureParameters(holder, request, write));
            changes.AddRange(EnsureInstaller(holder, menu, write));
            return changes;
        }

        /// <summary>
        /// Delete the generated folders (one per fingerprint) that no saved scene depends on, except the one in use;
        /// the Generated folder goes too once it is empty. Returns what was deleted.
        /// </summary>
        internal static string[] DeleteUnused(string generated, string keep)
        {
            if (!AssetDatabase.IsValidFolder(generated)) return Array.Empty<string>();
            var used = new HashSet<string>(AssetDatabase.FindAssets("t:Scene", new[] { "Assets" })
                .SelectMany(guid => AssetDatabase.GetDependencies(AssetDatabase.GUIDToAssetPath(guid), true)));
            var deleted = new List<string>();
            foreach (var folder in AssetDatabase.GetSubFolders(generated))
            {
                if (folder == keep || used.Any(p => p.StartsWith(folder + "/", StringComparison.Ordinal))) continue;
                if (AssetDatabase.DeleteAsset(folder)) deleted.Add(folder);
            }
            // 0.15.0 wrote the assets straight into Generated; drop those once no scene uses them.
            foreach (var path in AssetDatabase.FindAssets("", new[] { generated }).Select(AssetDatabase.GUIDToAssetPath).Distinct()
                         .Where(p => !AssetDatabase.IsValidFolder(p) && System.IO.Path.GetDirectoryName(p)?.Replace('\\', '/') == generated).ToArray())
                if (!used.Contains(path) && AssetDatabase.DeleteAsset(path)) deleted.Add(path);
            if (AssetDatabase.GetSubFolders(generated).Length == 0 &&
                AssetDatabase.FindAssets("", new[] { generated }).Length == 0 && AssetDatabase.DeleteAsset(generated))
                deleted.Add(generated);
            return deleted.ToArray();
        }

        private static Component Ensure(GameObject holder, string typeName, string what, bool write, List<string> changes)
        {
            var type = DshVrc.LoadedType(typeName)
                ?? throw new InvalidOperationException($"Modular Avatar {what} is unavailable. Install or update Modular Avatar in VCC/ALCOM.");
            var component = holder.GetComponent(type);
            if (component != null || !write) return component;
            changes.Add($"added MA {what}");
            return holder.AddComponent(type);
        }

        private static void SetField(Component component, string field, object value, List<string> changes)
        {
            var info = DshReflect.Field(component.GetType(), field);
            if (Equals(info.GetValue(component), value)) return;
            info.SetValue(component, value);
            EditorUtility.SetDirty(component);
            changes.Add($"{component.GetType().Name}.{field} = {DshReflect.Format(value)}");
        }

        private static List<string> EnsureMergeAnimator(GameObject holder, AnimatorController controller, bool write)
        {
            var changes = new List<string>();
            var merge = Ensure(holder, MergeAnimatorType, "Merge Animator", write, changes);
            if (merge == null) return new List<string> { "Merge Animator is missing" };
            var type = merge.GetType();
            SetField(merge, "animator", controller, changes);
            SetField(merge, "layerType", Enum.Parse(DshReflect.Field(type, "layerType").FieldType, "FX"), changes);
            SetField(merge, "pathMode", Enum.Parse(DshReflect.Field(type, "pathMode").FieldType, "Absolute"), changes);
            SetField(merge, "matchAvatarWriteDefaults", true, changes);
            SetField(merge, "deleteAttachedAnimator", true, changes);
            // After the avatar's own layers and other merged layers, so DSH wins for the shapes it controls.
            SetField(merge, "layerPriority", 100, changes);
            return write ? changes : changes.Select(c => "differs: " + c).ToList();
        }

        private static List<string> EnsureParameters(GameObject holder, Request request, bool write)
        {
            var changes = new List<string>();
            var wanted = new List<(string name, string sync, bool saved)>();
            if (request.locks.Length > 0) wanted.Add((Parameter(request, "Lock"), "Int", false));
            for (var i = 0; i < request.toggles.Length; i++) wanted.Add((Parameter(request, "Toggle" + i), "Bool", request.toggles[i].saved));
            var type = DshVrc.LoadedType(ParametersType);
            var component = type == null ? null : holder.GetComponent(type);
            if (wanted.Count == 0)
            {
                if (component != null) changes.Add(write ? "kept MA Parameters" : "differs: MA Parameters");
                return write ? new List<string>() : changes;
            }
            component = Ensure(holder, ParametersType, "Parameters", write, changes);
            if (component == null) return new List<string> { "MA Parameters is missing" };
            var list = DshReflect.List(component, "parameters");
            var configType = list.GetType().GetGenericArguments()[0];
            var syncType = configType.GetField("syncType").FieldType;
            bool Matches(object config, (string name, string sync, bool saved) w) =>
                (string)configType.GetField("nameOrPrefix").GetValue(config) == w.name &&
                configType.GetField("syncType").GetValue(config).ToString() == w.sync &&
                (bool)configType.GetField("saved").GetValue(config) == w.saved;
            if (list.Count == wanted.Count && wanted.Select((w, i) => Matches(list[i], w)).All(m => m)) return changes;
            if (!write) return new List<string> { "differs: MA Parameters" };
            list.Clear();
            foreach (var w in wanted)
            {
                var config = Activator.CreateInstance(configType);
                configType.GetField("nameOrPrefix").SetValue(config, w.name);
                configType.GetField("syncType").SetValue(config, Enum.Parse(syncType, w.sync));
                configType.GetField("saved").SetValue(config, w.saved);
                configType.GetField("defaultValue").SetValue(config, 0f);
                list.Add(config);
            }
            EditorUtility.SetDirty(component);
            changes.Add($"MA Parameters: {string.Join(", ", wanted.Select(w => w.name + " (" + w.sync + ")"))}");
            return changes;
        }

        private static List<string> EnsureInstaller(GameObject holder, ScriptableObject menu, bool write)
        {
            var changes = new List<string>();
            var type = DshVrc.LoadedType(InstallerType);
            var component = type == null ? null : holder.GetComponent(type);
            if (menu == null)
            {
                if (component == null) return changes;
                if (!write) return new List<string> { "differs: MA Menu Installer" };
                UnityEngine.Object.DestroyImmediate(component);
                return new List<string> { "removed MA Menu Installer" };
            }
            component = Ensure(holder, InstallerType, "Menu Installer", write, changes);
            if (component == null) return new List<string> { "MA Menu Installer is missing" };
            SetField(component, "menuToAppend", menu, changes);
            return write ? changes : changes.Select(c => "differs: " + c).ToList();
        }

        /// <summary>
        /// Write the controller, its clips and the menu. The Generated folder belongs to DSH: it is emptied and
        /// written again whenever the recipe (or the face's resting weights) change.
        /// </summary>
        private static void BuildAssets(GameObject avatar, Request request, Planned plan, string generated, string controllerPath)
        {
            if (!AssetDatabase.IsValidFolder(request.folder))
                throw new InvalidOperationException($"The recipe folder {request.folder} is missing.");
            var parent = request.folder + "/Generated";
            if (!AssetDatabase.IsValidFolder(parent)) AssetDatabase.CreateFolder(request.folder, "Generated");
            if (AssetDatabase.IsValidFolder(generated) && !AssetDatabase.DeleteAsset(generated))
                throw new InvalidOperationException($"Unity could not empty {generated}.");
            AssetDatabase.CreateFolder(parent, generated.Substring(parent.Length + 1));

            AnimationClip Clip(string file, Dictionary<string, float> values)
            {
                var clip = new AnimationClip { name = file };
                foreach (var pair in values.OrderBy(p => p.Key, StringComparer.Ordinal))
                    AnimationUtility.SetEditorCurve(clip,
                        EditorCurveBinding.FloatCurve(plan.RendererPath, typeof(SkinnedMeshRenderer), "blendShape." + pair.Key),
                        AnimationCurve.Constant(0, 1f / 60f, pair.Value));
                AssetDatabase.CreateAsset(clip, $"{generated}/{file}.anim");
                return clip;
            }

            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
            controller.RemoveLayer(0);
            controller.AddParameter("GestureLeft", AnimatorControllerParameterType.Int);
            controller.AddParameter("GestureRight", AnimatorControllerParameterType.Int);
            var lockParameter = Parameter(request, "Lock");
            if (request.locks.Length > 0) controller.AddParameter(lockParameter, AnimatorControllerParameterType.Int);

            var stateful = plan.States.Where(s => s.Kind == "neutral" || s.Kind == "gesture" || s.Kind == "lock").ToList();
            if (plan.Controlled.Count > 0 && stateful.Count > 1)
            {
                var machine = AddLayer(controller, $"DSH {request.name} Expression");
                var neutral = AddState(machine, "Neutral", Clip($"{request.name}_Neutral", stateful[0].Values));
                machine.defaultState = neutral;
                var rights = stateful.Where(s => s.Kind == "gesture" && s.Hand == "right").Select(s => s.Gesture).Distinct().ToArray();
                var lefts = stateful.Where(s => s.Kind == "gesture" && s.Hand == "left").Select(s => s.Gesture).Distinct().ToArray();
                var toNeutral = AnyTransition(machine, neutral);
                if (request.locks.Length > 0) toNeutral.AddCondition(AnimatorConditionMode.Equals, 0, lockParameter);
                foreach (var g in rights) toNeutral.AddCondition(AnimatorConditionMode.NotEqual, g, "GestureRight");
                foreach (var g in lefts) toNeutral.AddCondition(AnimatorConditionMode.NotEqual, g, "GestureLeft");
                var number = 0;
                foreach (var state in stateful.Skip(1))
                {
                    var name = state.Kind == "lock" ? $"Lock {state.Index} {state.Label}" : $"{state.Hand} {GestureNames[state.Gesture]}";
                    var node = AddState(machine, name, Clip($"{request.name}_{++number:00}", state.Values));
                    var transition = AnyTransition(machine, node);
                    if (state.Kind == "lock")
                    {
                        transition.AddCondition(AnimatorConditionMode.Equals, state.Index, lockParameter);
                        continue;
                    }
                    if (request.locks.Length > 0) transition.AddCondition(AnimatorConditionMode.Equals, 0, lockParameter);
                    if (state.Hand == "right")
                        transition.AddCondition(AnimatorConditionMode.Equals, state.Gesture, "GestureRight");
                    else
                    {
                        // The right hand wins when both hands show a sign DSH handles.
                        transition.AddCondition(AnimatorConditionMode.Equals, state.Gesture, "GestureLeft");
                        foreach (var g in rights) transition.AddCondition(AnimatorConditionMode.NotEqual, g, "GestureRight");
                    }
                }
            }
            for (var i = 0; i < request.toggles.Length; i++)
            {
                var parameter = Parameter(request, "Toggle" + i);
                controller.AddParameter(parameter, AnimatorControllerParameterType.Bool);
                var machine = AddLayer(controller, $"DSH {request.name} {request.toggles[i].label}");
                var off = AddState(machine, "Off", Clip($"{request.name}_T{i}_Off", plan.States.First(s => s.Kind == "toggle-off" && s.Index == i).Values));
                var on = AddState(machine, "On", Clip($"{request.name}_T{i}_On", plan.States.First(s => s.Kind == "toggle-on" && s.Index == i).Values));
                machine.defaultState = off;
                var up = off.AddTransition(on);
                up.hasExitTime = false;
                up.duration = Fade;
                up.AddCondition(AnimatorConditionMode.If, 0, parameter);
                var down = on.AddTransition(off);
                down.hasExitTime = false;
                down.duration = Fade;
                down.AddCondition(AnimatorConditionMode.IfNot, 0, parameter);
            }
            EditorUtility.SetDirty(controller);

            var menu = BuildMenu(request, generated);
            AssetDatabase.SaveAssets();
            var importer = AssetImporter.GetAtPath(controllerPath);
            importer.userData = "dsh:" + plan.Fingerprint;
            importer.SaveAndReimport();
            if (menu == null && (request.locks.Length > 0 || request.toggles.Length > 0))
                throw new InvalidOperationException("The expression menu could not be written.");
        }

        private static AnimatorStateMachine AddLayer(AnimatorController controller, string name)
        {
            var machine = new AnimatorStateMachine { name = name, hideFlags = HideFlags.HideInHierarchy };
            AssetDatabase.AddObjectToAsset(machine, controller);
            controller.AddLayer(new AnimatorControllerLayer { name = name, defaultWeight = 1f, stateMachine = machine });
            return machine;
        }

        private static AnimatorState AddState(AnimatorStateMachine machine, string name, AnimationClip clip)
        {
            var state = machine.AddState(name);
            state.motion = clip;
            state.writeDefaultValues = false;
            return state;
        }

        private static AnimatorStateTransition AnyTransition(AnimatorStateMachine machine, AnimatorState target)
        {
            var transition = machine.AddAnyStateTransition(target);
            transition.hasExitTime = false;
            transition.duration = Fade;
            transition.canTransitionToSelf = false;
            return transition;
        }

        /// <summary>
        /// The menu the installer appends: a submenu for each part of the recipe's menu path, holding one toggle per
        /// menu expression (on the lock parameter, value 1, 2, ...) and per shape toggle.
        /// </summary>
        private static ScriptableObject BuildMenu(Request request, string generated)
        {
            if (request.locks.Length == 0 && request.toggles.Length == 0) return null;
            var menuType = DshVrc.LoadedType(MenuType) ?? throw new InvalidOperationException("The VRChat SDK menu type is unavailable.");
            var controlType = menuType.GetNestedType("Control") ?? throw new InvalidOperationException("The VRChat SDK menu has no Control type.");
            var parameterType = controlType.GetNestedType("Parameter") ?? throw new InvalidOperationException("The VRChat SDK menu control has no Parameter type.");
            var kind = controlType.GetNestedType("ControlType");
            object Control(string name, string typeName, string parameter, float value, ScriptableObject subMenu)
            {
                var control = Activator.CreateInstance(controlType);
                controlType.GetField("name").SetValue(control, name);
                controlType.GetField("type").SetValue(control, Enum.Parse(kind, typeName));
                var p = Activator.CreateInstance(parameterType);
                parameterType.GetField("name").SetValue(p, parameter ?? "");
                controlType.GetField("parameter").SetValue(control, p);
                controlType.GetField("value").SetValue(control, value);
                controlType.GetField("subMenu").SetValue(control, subMenu);
                var subParameters = controlType.GetField("subParameters");
                subParameters?.SetValue(control, Array.CreateInstance(parameterType, 0));
                var labels = controlType.GetField("labels");
                if (labels != null && labels.FieldType.IsArray)
                    labels.SetValue(control, Array.CreateInstance(labels.FieldType.GetElementType(), 0));
                return control;
            }
            ScriptableObject Menu(string file, IEnumerable<object> controls)
            {
                var menu = ScriptableObject.CreateInstance(menuType);
                var list = (IList)menuType.GetField("controls").GetValue(menu);
                foreach (var c in controls) list.Add(c);
                AssetDatabase.CreateAsset(menu, $"{generated}/{file}.asset");
                return menu;
            }
            var leaf = new List<object>();
            for (var i = 0; i < request.locks.Length; i++)
                leaf.Add(Control(request.locks[i].label, "Toggle", Parameter(request, "Lock"), i + 1, null));
            for (var i = 0; i < request.toggles.Length; i++)
                leaf.Add(Control(request.toggles[i].label, "Toggle", Parameter(request, "Toggle" + i), 1, null));
            var parts = request.menu.Split('/').Where(p => p.Length > 0).ToArray();
            var current = Menu($"{request.name}_Menu_{parts.Length}", leaf);
            for (var depth = parts.Length - 1; depth >= 0; depth--)
                current = Menu(depth == 0 ? $"{request.name}_Menu" : $"{request.name}_Menu_{depth}",
                    new[] { Control(parts[depth], "SubMenu", "", 0, current) });
            return current;
        }

        private static IEnumerable<AnimatorController> FxControllers(GameObject avatar) =>
            DshVrc.PublicItems(DshAvatarScene.Descriptor(avatar), "baseAnimationLayers")
                .Where(layer => DshVrc.PublicMember(layer, "type")?.ToString() == "FX")
                .Select(layer => DshVrc.PublicMember(layer, "animatorController")).OfType<AnimatorController>();

        /// <summary>States of the avatar's own FX layers entered on a hand gesture, with the face shapes their clips set.</summary>
        private static IEnumerable<Dictionary<string, object>> AuthorGestures(GameObject avatar)
        {
            foreach (var controller in FxControllers(avatar))
                foreach (var layer in controller.layers)
                {
                    var transitions = layer.stateMachine.anyStateTransitions
                        .Concat(layer.stateMachine.states.SelectMany(s => s.state.transitions)).ToArray();
                    foreach (var transition in transitions)
                    {
                        var hand = transition.conditions.Where(c => c.parameter == "GestureLeft" || c.parameter == "GestureRight")
                            .Where(c => c.mode == AnimatorConditionMode.Equals).ToArray();
                        if (hand.Length == 0 || transition.destinationState == null) continue;
                        var clip = transition.destinationState.motion as AnimationClip;
                        var shapes = clip == null ? Array.Empty<string>() : AnimationUtility.GetCurveBindings(clip)
                            .Where(b => b.type == typeof(SkinnedMeshRenderer) && b.propertyName.StartsWith("blendShape.", StringComparison.Ordinal))
                            .Select(b => (b, value: AnimationUtility.GetEditorCurve(clip, b)?.keys.FirstOrDefault().value ?? 0))
                            .Where(x => x.value != 0)
                            .Select(x => $"{x.b.path}:{x.b.propertyName.Substring("blendShape.".Length)}={x.value:0.#}").ToArray();
                        yield return new Dictionary<string, object>
                        {
                            { "layer", layer.name }, { "state", transition.destinationState.name },
                            { "when", string.Join(" & ", hand.Select(c => $"{c.parameter}={GestureName((int)c.threshold)}")) },
                            { "shapes", shapes.Take(20).ToArray() },
                        };
                    }
                }
        }

        private static string GestureName(int value) => value >= 0 && value < GestureNames.Length ? GestureNames[value] : value.ToString();

        /// <summary>Face shapes the avatar's own gesture layers animate (for override "all").</summary>
        private static IEnumerable<string> AuthorShapes(GameObject avatar, string rendererPath) =>
            FxControllers(avatar).SelectMany(c => c.layers)
                .Where(l => l.stateMachine.anyStateTransitions.Concat(l.stateMachine.states.SelectMany(s => s.state.transitions))
                    .Any(t => t.conditions.Any(c => c.parameter == "GestureLeft" || c.parameter == "GestureRight")))
                .SelectMany(l => l.stateMachine.states).Select(s => s.state.motion).OfType<AnimationClip>()
                .SelectMany(AnimationUtility.GetCurveBindings)
                .Where(b => b.path == rendererPath && b.type == typeof(SkinnedMeshRenderer) && b.propertyName.StartsWith("blendShape.", StringComparison.Ordinal))
                .Select(b => b.propertyName.Substring("blendShape.".Length)).Distinct();

        private static void Pose(GameObject copy, string rendererPath, Dictionary<string, float> values)
        {
            var face = copy.transform.Find(rendererPath)?.GetComponent<SkinnedMeshRenderer>();
            if (face == null) return;
            foreach (var pair in values)
            {
                var index = face.sharedMesh.GetBlendShapeIndex(pair.Key);
                if (index >= 0) face.SetBlendShapeWeight(index, pair.Value);
            }
        }

        private static Dictionary<string, object> VerifySdk(GameObject avatar, Request request)
        {
            var result = new Dictionary<string, object> { { "stage", "sdk-preprocess" }, { "status", "failed" }, { "clientTested", false } };
            GameObject copy = null;
            try
            {
                copy = DshVrc.PreprocessCopy(avatar);
                var layers = FxControllers(copy).SelectMany(c => c.layers)
                    .Where(l => l.name.StartsWith($"DSH {request.name}", StringComparison.Ordinal)).ToArray();
                result["layers"] = layers.Select(l => l.name).ToArray();
                if (layers.Length == 0) throw new InvalidOperationException("After the build the FX controller has no DSH expression layer.");
                var bindings = layers.SelectMany(l => l.stateMachine.states).Select(s => s.state.motion).OfType<AnimationClip>()
                    .SelectMany(AnimationUtility.GetCurveBindings).Select(b => b.path).Distinct().ToArray();
                var missing = bindings.Where(p => copy.transform.Find(p) == null).ToArray();
                result["animatedMeshes"] = bindings;
                if (missing.Length > 0)
                {
                    result["status"] = "inconclusive";
                    result["reason"] = "A build plugin moved or renamed the face mesh: " + string.Join(", ", missing) + ". Check the expressions in Gesture Manager.";
                    return result;
                }
                // The DSH layer must come after the avatar's own gesture layers to win for its shapes.
                var all = FxControllers(copy).SelectMany(c => c.layers).ToList();
                var mine = all.FindIndex(l => l.name == $"DSH {request.name} Expression");
                var author = all.Select((l, i) => (l, i)).Where(x => !x.l.name.StartsWith("DSH ", StringComparison.Ordinal) &&
                        x.l.stateMachine.anyStateTransitions.Concat(x.l.stateMachine.states.SelectMany(s => s.state.transitions))
                            .Any(t => t.conditions.Any(c => c.parameter == "GestureLeft" || c.parameter == "GestureRight")))
                    .Select(x => x.i).ToArray();
                result["layerOrder"] = new Dictionary<string, object> { { "dsh", mine }, { "authorGestureLayers", author } };
                if (mine >= 0 && author.Any(i => i > mine))
                    throw new InvalidOperationException("After the build an avatar gesture layer comes after the DSH expression layer, so it would win.");
                if (request.locks.Length > 0)
                {
                    var (_, parameter, location) = DshVrc.GeneratedToggle(DshAvatarScene.Descriptor(copy), request.menu + "/" + request.locks[0].label);
                    result["menuLocation"] = location;
                    result["lockParameter"] = parameter;
                }
                else if (request.toggles.Length > 0)
                {
                    var (_, parameter, location) = DshVrc.GeneratedToggle(DshAvatarScene.Descriptor(copy), request.menu + "/" + request.toggles[0].label);
                    result["menuLocation"] = location;
                    result["toggleParameter"] = parameter;
                }
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
