using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace DSH.Editor
{
    /// <summary>
    /// Read-only: the synced expression parameter memory (256 bits in VRChat) of the avatar in the scene and of an
    /// SDK-built copy, which includes what VRCFury and Modular Avatar add at build time.
    /// </summary>
    public static class DshParameters
    {
        [Serializable]
        private sealed class Request
        {
            public string scene = "";
            public string avatar = "";
            public string avatarId = "";
            public string expectedSceneDigest = "";
            public bool build = true;
        }

        public const int Limit = 256;

        public static void Measure()
        {
            var result = new Dictionary<string, object> { { "ok", false } };
            try
            {
                var request = DshAvatarScene.ReadRequest<Request>();
                var scene = DshAvatarScene.OpenScene(request.scene, request.expectedSceneDigest);
                var avatar = DshAvatarScene.ResolveAvatar(scene, request.avatar, request.avatarId, result);
                result["avatar"] = DshAvatarScene.Describe(avatar.transform);
                var own = Read(avatar);
                result["scene"] = Summary(own, null);
                if (request.build)
                {
                    GameObject copy = null;
                    try
                    {
                        copy = DshVrc.PreprocessCopy(avatar);
                        result["built"] = Summary(Read(copy), new HashSet<string>(own.Select(p => p.name)));
                    }
                    finally
                    {
                        if (copy != null) UnityEngine.Object.DestroyImmediate(copy);
                    }
                }
                result["limit"] = Limit;
                result["ok"] = true;
            }
            catch (Exception error)
            {
                result["error"] = error.GetBaseException().Message;
            }
            DshAvatarScene.Finish("Parameters", result);
        }

        private struct Parameter
        {
            public string name;
            public string type;
            public bool synced;
            public bool saved;
            public int Cost => !synced ? 0 : type == "Bool" ? 1 : 8;
        }

        private static List<Parameter> Read(GameObject avatar)
        {
            var descriptor = DshAvatarScene.Descriptor(avatar)
                ?? throw new InvalidOperationException("The avatar has no VRC Avatar Descriptor.");
            var asset = DshVrc.PublicMember(descriptor, "expressionParameters");
            var found = new List<Parameter>();
            if (asset == null) return found;
            foreach (var item in DshVrc.PublicItems(asset, "parameters"))
            {
                var name = DshVrc.PublicMember(item, "name") as string;
                if (string.IsNullOrEmpty(name)) continue;
                var synced = DshVrc.PublicMember(item, "networkSynced");
                found.Add(new Parameter
                {
                    name = name,
                    type = DshVrc.PublicMember(item, "valueType")?.ToString() ?? "",
                    synced = !(synced is bool b) || b,
                    saved = DshVrc.PublicMember(item, "saved") is bool s && s,
                });
            }
            return found;
        }

        /// <summary>Totals, a breakdown by who added the parameter, and the largest synced ones.</summary>
        private static Dictionary<string, object> Summary(List<Parameter> parameters, HashSet<string> fromAvatar)
        {
            string Owner(Parameter p) => fromAvatar == null || fromAvatar.Contains(p.name) ? "avatar"
                : p.name.StartsWith("VF", StringComparison.Ordinal) ? "VRCFury" : "Modular Avatar / other";
            var used = parameters.Sum(p => p.Cost);
            return new Dictionary<string, object>
            {
                { "usedBits", used }, { "freeBits", Limit - used }, { "overLimit", used > Limit },
                { "synced", parameters.Count(p => p.synced) }, { "localOnly", parameters.Count(p => !p.synced) },
                { "byOwner", parameters.GroupBy(Owner).ToDictionary(g => g.Key, g => (object)g.Sum(p => p.Cost)) },
                { "parameters", parameters.Where(p => p.synced).OrderByDescending(p => p.Cost).Take(80)
                    .Select(p => (object)new Dictionary<string, object>
                    {
                        { "name", p.name }, { "type", p.type }, { "bits", p.Cost }, { "saved", p.saved },
                    }).ToArray() },
            };
        }
    }
}
