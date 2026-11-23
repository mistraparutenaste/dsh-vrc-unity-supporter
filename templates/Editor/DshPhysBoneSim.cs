using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Run the avatar's PhysBones for real: enter play mode (VRCFury and Modular Avatar run their play-mode builds,
    /// the VRChat SDK runs the PhysBones), move the avatar through a few motions with humanoid poses (sway, walk,
    /// sit, then stand still), and measure each PhysBone chain: how far its tip swings, how long it takes to settle,
    /// and how deep its bones go into the legs. Key moments are rendered. A recipe can be tried in memory first;
    /// nothing is saved. Unity is started without -quit and this class exits it when done.
    /// </summary>
    [InitializeOnLoad]
    public static class DshPhysBoneSim
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public string motions = "sway,walk,sit";
            public string views = "front,left";
            public int size = 384;
            public string filter = "";
            public string recipeJson = "";   // a PhysBone recipe request, applied in memory before play mode
        }

        private const string ActiveKey = "DSH_PHYSBONE_SIM_ACTIVE";
        private const float Dt = 1f / 60f;
        private const int Rest = 90, Motion = 150, SitIn = 40, SitHold = 90, Settle = 240;

        static DshPhysBoneSim()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Tick;
        }

        /// <summary>Entry point (-executeMethod): open the scene, try the recipe in memory, enter play mode.</summary>
        public static void Run()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                DshCapture.RequireGraphics();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                if (!string.IsNullOrEmpty(request.recipeJson))
                    SessionState.SetString(ActiveKey + "_tried", string.Join("; ", DshPhysBone.TryRecipe(avatar, request.recipeJson).Take(40)));
                SessionState.SetString(ActiveKey + "_avatar", DshAvatarScene.HierarchyPath(avatar.transform));
                SessionState.SetBool(ActiveKey, true);
                EditorApplication.update += Tick;
                EditorApplication.EnterPlaymode();
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
                SessionState.EraseBool(ActiveKey);
                DshAvatarScene.Finish("PhysBoneSim", result);
            }
        }

        // ---- play mode ------------------------------------------------------------------------------------------

        private sealed class Chain
        {
            public Component Bone;
            public string Target;
            public string Part;
            public List<Transform> Moved;
            public List<Transform> Tips;
            public Transform Frame;   // swing is measured in the space of the chain root's parent
            public Vector3[] RestTips;
            public Vector3[] LastTips;
            public readonly Dictionary<string, float> Swing = new Dictionary<string, float>();
            public readonly Dictionary<string, float> Depth = new Dictionary<string, float>();
            public readonly Dictionary<string, int> Frames = new Dictionary<string, int>();
            public int StillFrames;
            public int SettledAt = -1;
        }

        private sealed class Segment
        {
            public string Name;
            public Transform From, To;
            public float Radius;
        }

        private static int frame, waited;
        private static Request request;
        private static GameObject avatar;
        private static HumanPoseHandler handler;
        private static HumanPose basePose;
        private static Vector3 basePosition;
        private static Quaternion baseRotation;
        private static List<Chain> chains;
        private static List<Segment> legs;
        private static List<string> motions;
        private static readonly List<(string label, GameObject snapshot)> Shots = new List<(string, GameObject)>();
        private static Dictionary<string, object> result;

        private static void Tick()
        {
            try
            {
                if (!EditorApplication.isPlaying)
                {
                    if (++waited > 3000) throw new InvalidOperationException("Unity did not enter play mode.");
                    return;
                }
                if (avatar == null) Setup();
                Step();
            }
            catch (Exception error)
            {
                result = result ?? new Dictionary<string, object> { { "ok", false } };
                result["error"] = error.GetBaseException().Message;
                Done();
            }
        }

        private static void Setup()
        {
            request = DshAvatarScene.ReadRequest<Request>();
            result = new Dictionary<string, object> { { "ok", false } };
            var path = SessionState.GetString(ActiveKey + "_avatar", "");
            var candidates = UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects()
                .SelectMany(r => r.GetComponentsInChildren<Transform>(true)).Where(t => DshAvatarScene.Descriptor(t.gameObject) != null).ToArray();
            avatar = (candidates.FirstOrDefault(t => DshAvatarScene.HierarchyPath(t) == path) ?? candidates.FirstOrDefault(t => t.gameObject.activeInHierarchy))?.gameObject
                ?? throw new InvalidOperationException($"The avatar '{path}' is not in the scene in play mode.");
            result["avatar"] = DshAvatarScene.Describe(avatar.transform);
            var tried = SessionState.GetString(ActiveKey + "_tried", "");
            if (tried.Length > 0) result["triedRecipe"] = tried;
            Time.captureDeltaTime = Dt;

            var animator = avatar.GetComponent<Animator>();
            if (animator == null || !animator.isHuman) throw new InvalidOperationException("The simulation needs a humanoid avatar.");
            animator.enabled = false;  // the poses below drive the bones
            handler = new HumanPoseHandler(animator.avatar, avatar.transform);
            handler.GetHumanPose(ref basePose);
            basePosition = avatar.transform.position;
            baseRotation = avatar.transform.rotation;
            motions = (request.motions ?? "").Split(',').Select(m => m.Trim()).Where(m => m == "sway" || m == "walk" || m == "sit").Distinct().ToList();
            if (motions.Count == 0) throw new InvalidOperationException("motions must name sway, walk or sit.");

            legs = new List<Segment>();
            foreach (var (from, to) in new[] { (HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg), (HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg),
                                               (HumanBodyBones.LeftLowerLeg, HumanBodyBones.LeftFoot), (HumanBodyBones.RightLowerLeg, HumanBodyBones.RightFoot) })
            {
                var a = animator.GetBoneTransform(from);
                var b = animator.GetBoneTransform(to);
                if (a != null && b != null) legs.Add(new Segment { Name = from.ToString(), From = a, To = b, Radius = Thickness(avatar, a, b) });
            }
            result["legRadii"] = legs.ToDictionary(l => l.Name, l => (object)Math.Round(l.Radius, 3));

            var type = DshReflect.Find("VRCPhysBone", "VRC") ?? throw new InvalidOperationException("The VRChat SDK PhysBone component is unavailable.");
            var filter = request.filter ?? "";
            var legBones = legs.Select(l => l.From).ToArray();
            chains = new List<Chain>();
            foreach (var bone in avatar.GetComponentsInChildren(type, true))
            {
                var target = DshReflect.PathIn(bone.transform, avatar.transform);
                if (filter.Length > 0 && target.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                var root = type.GetField("rootTransform")?.GetValue(bone) as Transform ?? bone.transform;
                var ignored = (type.GetField("ignoreTransforms")?.GetValue(bone) as IEnumerable ?? Array.Empty<object>()).Cast<object>().OfType<Transform>().ToArray();
                var moved = root.GetComponentsInChildren<Transform>(true).Where(t => t != root && !ignored.Any(i => t.IsChildOf(i))).ToList();
                if (moved.Count == 0) continue;
                var tips = moved.Where(t => !moved.Any(m => m.parent == t)).ToList();
                // A chain that hangs from a leg moves with it; its contact with that leg is not a fault.
                var onLeg = legBones.Any(l => root.IsChildOf(l));
                chains.Add(new Chain
                {
                    Bone = bone, Target = target, Part = Part(target + "/" + root.name), Moved = onLeg ? new List<Transform>() : moved, Tips = tips,
                    Frame = root.parent != null ? root.parent : avatar.transform,
                    RestTips = new Vector3[tips.Count], LastTips = new Vector3[tips.Count],
                });
            }
            if (chains.Count == 0) throw new InvalidOperationException("No PhysBone matches. Check --filter.");
            frame = 0;
        }

        private static string Part(string path)
        {
            var p = path.ToLowerInvariant();
            if (p.Contains("skirt") || p.Contains("スカート")) return "skirt";
            if (p.Contains("tail") || p.Contains("しっぽ") || p.Contains("尻尾")) return "tail";
            if (p.Contains("ear") || p.Contains("耳")) return "ear";
            if (p.Contains("breast") || p.Contains("bust") || p.Contains("胸")) return "breast";
            if (p.Contains("hair") || p.Contains("髪")) return "hair";
            return "other";
        }

        /// <summary>The leg's thickness around a bone: a high percentile of the distance from the bone of the vertices on it.</summary>
        private static float Thickness(GameObject root, Transform from, Transform to)
        {
            var best = new List<float>();
            foreach (var skinned in root.GetComponentsInChildren<SkinnedMeshRenderer>(false))
            {
                var distances = new List<float>();
                var mesh = skinned.sharedMesh;
                var index = Array.IndexOf(skinned.bones, from);
                if (mesh == null || index < 0 || mesh.boneWeights.Length != mesh.vertexCount) continue;
                var baked = new Mesh();
                skinned.BakeMesh(baked, true);
                var vertices = baked.vertices;
                var weights = mesh.boneWeights;
                for (var i = 0; i < vertices.Length; i += 2)
                {
                    var w = weights[i];
                    var on = (w.boneIndex0 == index ? w.weight0 : 0) + (w.boneIndex1 == index ? w.weight1 : 0) +
                             (w.boneIndex2 == index ? w.weight2 : 0) + (w.boneIndex3 == index ? w.weight3 : 0);
                    if (on < 0.6f) continue;
                    var point = skinned.transform.TransformPoint(vertices[i]);
                    var (distance, t) = ToSegment(point, from.position, to.position);
                    if (t > 0.15f && t < 0.85f) distances.Add(distance);
                }
                UnityEngine.Object.DestroyImmediate(baked);
                if (distances.Count > best.Count) best = distances;
            }
            if (best.Count < 10) return 0.06f * Mathf.Abs(root.transform.lossyScale.y);
            best.Sort();
            return best[(int)(best.Count * 0.7f)];
        }

        private static (float distance, float t) ToSegment(Vector3 p, Vector3 a, Vector3 b)
        {
            var ab = b - a;
            var t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / Mathf.Max(1e-8f, ab.sqrMagnitude));
            return ((p - (a + ab * t)).magnitude, t);
        }

        /// <summary>The motion phase of a frame, its progress (0-1), and whether the avatar moves in it.</summary>
        private static (string phase, float progress) Phase(int f)
        {
            if (f < Rest) return ("rest", f / (float)Rest);
            f -= Rest;
            foreach (var motion in motions)
            {
                var length = motion == "sit" ? SitIn + SitHold : Motion;
                if (f < length) return (motion, f / (float)length);
                f -= length;
                // back to standing between motions
                if (motion == "sit") { if (f < SitIn) return ("stand-up", f / (float)SitIn); f -= SitIn; }
            }
            if (f < Settle) return ("settle", f / (float)Settle);
            return ("done", 1);
        }

        private static void Pose(string phase, float progress, int f)
        {
            var pose = basePose;
            var muscles = (float[])basePose.muscles.Clone();
            float Base(string name)
            {
                var index = Array.IndexOf(HumanTrait.MuscleName, name);
                return index >= 0 ? basePose.muscles[index] : 0;
            }
            void Set(string name, float value)
            {
                var index = Array.IndexOf(HumanTrait.MuscleName, name);
                if (index >= 0) muscles[index] = value;
            }
            // Arms down, so hair and sleeves hang as when standing.
            Set("Left Arm Down-Up", -0.6f);
            Set("Right Arm Down-Up", -0.6f);
            var position = basePosition;
            var rotation = baseRotation;
            var seconds = f * Dt;
            switch (phase)
            {
                case "sway":
                    position += baseRotation * new Vector3(Mathf.Sin(seconds * Mathf.PI * 2f / 0.9f) * 0.25f, 0, 0);
                    rotation = baseRotation * Quaternion.Euler(0, Mathf.Sin(seconds * Mathf.PI * 2f / 1.3f) * 35f, 0);
                    break;
                case "walk":
                    var swing = Mathf.Sin(seconds * Mathf.PI * 2f / 1.0f);
                    Set("Left Upper Leg Front-Back", Base("Left Upper Leg Front-Back") - 0.45f * swing);
                    Set("Right Upper Leg Front-Back", Base("Right Upper Leg Front-Back") + 0.45f * swing);
                    // the knee bends on the leg that swings back
                    Set("Left Lower Leg Stretch", Base("Left Lower Leg Stretch") - 0.7f * Mathf.Max(0, -swing));
                    Set("Right Lower Leg Stretch", Base("Right Lower Leg Stretch") - 0.7f * Mathf.Max(0, swing));
                    Set("Left Arm Front-Back", -0.3f * swing);
                    Set("Right Arm Front-Back", 0.3f * swing);
                    position += baseRotation * new Vector3(0, Mathf.Abs(swing) * 0.02f, progress * Motion * Dt * 1.2f);
                    break;
                case "sit":
                case "stand-up":
                    var amount = phase == "sit" ? Mathf.SmoothStep(0, 1, Mathf.Min(1, progress * (SitIn + SitHold) / SitIn)) : 1 - Mathf.SmoothStep(0, 1, progress);
                    // thighs forward (about 90 degrees), knees bent, as on a chair
                    Set("Left Upper Leg Front-Back", Mathf.Lerp(Base("Left Upper Leg Front-Back"), -1f, amount));
                    Set("Right Upper Leg Front-Back", Mathf.Lerp(Base("Right Upper Leg Front-Back"), -1f, amount));
                    Set("Left Lower Leg Stretch", Mathf.Lerp(Base("Left Lower Leg Stretch"), -0.9f, amount));
                    Set("Right Lower Leg Stretch", Mathf.Lerp(Base("Right Lower Leg Stretch"), -0.9f, amount));
                    position += baseRotation * new Vector3(0, -0.35f * amount * Mathf.Abs(avatar.transform.lossyScale.y), 0);
                    break;
            }
            pose.muscles = muscles;
            avatar.transform.SetPositionAndRotation(position, rotation);
            handler.SetHumanPose(ref pose);
        }

        private static void Step()
        {
            var (phase, progress) = Phase(frame);
            if (phase == "done")
            {
                Finish();
                return;
            }
            // Measure what the last frame's PhysBone update left, then pose this frame.
            var root = avatar.transform;
            foreach (var chain in chains)
            {
                for (var i = 0; i < chain.Tips.Count; i++)
                {
                    var tip = chain.Frame.InverseTransformPoint(chain.Tips[i].position);
                    if (phase == "rest") chain.RestTips[i] = tip;
                    else if (phase != "settle")
                    {
                        var swing = (tip - chain.RestTips[i]).magnitude;
                        if (!chain.Swing.TryGetValue(phase, out var max) || swing > max) chain.Swing[phase] = swing;
                    }
                    else if (chain.SettledAt < 0)
                    {
                        var moved = (tip - chain.LastTips[i]).magnitude;
                        if (i == 0) chain.StillFrames = moved < 0.0005f ? chain.StillFrames + 1 : 0;
                        else if (moved >= 0.0005f) chain.StillFrames = 0;
                    }
                    chain.LastTips[i] = tip;
                }
                if (phase == "settle" && chain.SettledAt < 0 && chain.StillFrames >= 10)
                    chain.SettledAt = frame - 10;
                if (phase == "rest") continue;
                var deepest = 0f;
                foreach (var bone in chain.Moved)
                    foreach (var leg in legs)
                    {
                        var (distance, _) = ToSegment(bone.position, leg.From.position, leg.To.position);
                        deepest = Mathf.Max(deepest, leg.Radius - distance);
                    }
                if (deepest <= 0.005f) continue;
                if (!chain.Depth.TryGetValue(phase, out var depth) || deepest > depth) chain.Depth[phase] = deepest;
                chain.Frames[phase] = (chain.Frames.TryGetValue(phase, out var n) ? n : 0) + 1;
            }
            var settleStart = Rest + motions.Sum(m => m == "sit" ? SitIn * 2 + SitHold : Motion);
            // Pictures at the height of each motion.
            if (phase == "rest" && frame == Rest - 1) Shots.Add(("rest", Snapshot(avatar)));
            if ((phase == "sway" || phase == "walk") && Mathf.Abs(progress - 0.6f) < 0.5f / Motion) Shots.Add((phase, Snapshot(avatar)));
            if (phase == "sit" && Mathf.Abs(progress - 0.9f) < 0.5f / (SitIn + SitHold)) Shots.Add(("sit", Snapshot(avatar)));
            if (frame == settleStart + 30) Shots.Add(("stopped 0.5 s", Snapshot(avatar)));
            Pose(phase, progress, frame);
            frame++;
        }

        /// <summary>A static copy of what the avatar shows now (skinned meshes baked), for rendering.</summary>
        private static GameObject Snapshot(GameObject source)
        {
            var copy = new GameObject(source.name + " (DSH Snapshot)");
            copy.transform.SetPositionAndRotation(source.transform.position, source.transform.rotation);
            foreach (var renderer in source.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled))
            {
                Mesh mesh;
                if (renderer is SkinnedMeshRenderer skinned)
                {
                    if (skinned.sharedMesh == null) continue;
                    mesh = new Mesh();
                    skinned.BakeMesh(mesh, true);
                }
                else if (renderer is MeshRenderer && renderer.GetComponent<MeshFilter>()?.sharedMesh is Mesh shared) mesh = shared;
                else continue;
                var part = new GameObject(renderer.name);
                part.transform.SetParent(copy.transform, false);
                part.transform.SetPositionAndRotation(renderer.transform.position, renderer.transform.rotation);
                if (!(renderer is SkinnedMeshRenderer)) part.transform.localScale = renderer.transform.lossyScale;
                part.AddComponent<MeshFilter>().sharedMesh = mesh;
                part.AddComponent<MeshRenderer>().sharedMaterials = renderer.sharedMaterials;
            }
            copy.SetActive(false);
            return copy;
        }

        private static void Finish()
        {
            var settleStart = Rest + motions.Sum(m => m == "sit" ? SitIn * 2 + SitHold : Motion);
            result["chains"] = chains.Select(c => (object)new Dictionary<string, object>
            {
                { "target", c.Target }, { "part", c.Part }, { "bones", c.Tips.Count + " tips" },
                { "maxSwing", c.Swing.ToDictionary(p => p.Key, p => (object)Math.Round(p.Value, 3)) },
                { "settleSeconds", c.SettledAt < 0 ? (object)"over 4" : Math.Round(Math.Max(0, c.SettledAt - settleStart) * Dt, 2) },
                { "legDepth", c.Depth.ToDictionary(p => p.Key, p => (object)Math.Round(p.Value, 3)) },
                { "legFrames", c.Frames.ToDictionary(p => p.Key, p => (object)p.Value) },
            }).ToArray();
            result["motions"] = motions.ToArray();
            result["units"] = "maxSwing and legDepth in metres (tip movement from rest, depth into the leg); settleSeconds after the avatar stops.";
            try
            {
                var views = DshCapture.ParseViews(request.views);
                var shots = Shots.ToList();
                result["image"] = DshCapture.RenderSheet(avatar, views, Mathf.Clamp(request.size, 64, 2048),
                    shots.Select(s => (s.label, (Func<GameObject, GameObject>)(_ => { s.snapshot.SetActive(true); return s.snapshot; }))).ToList());
                result["rows"] = shots.Select(s => s.label).ToArray();
                result["columns"] = views;
            }
            catch (Exception error)
            {
                result["imageError"] = error.GetBaseException().Message;
            }
            result["note"] = "Play mode with the VRChat SDK's PhysBones; poses are a rough stand-in for real movement, and colliders count only the leg capsules measured here.";
            result["ok"] = true;
            Done();
        }

        private static void Done()
        {
            EditorApplication.update -= Tick;
            SessionState.EraseBool(ActiveKey);
            SessionState.EraseString(ActiveKey + "_avatar");
            SessionState.EraseString(ActiveKey + "_tried");
            Time.captureDeltaTime = 0;
            DshAvatarScene.Finish("PhysBoneSim", result);
        }
    }
}
