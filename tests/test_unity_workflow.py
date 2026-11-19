import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
PREFAB_GUID = "1" * 32
SDK_GUID = "2" * 32
GIT_IDENTITIES = dict(os.environ, GIT_AUTHOR_NAME="Tester", GIT_AUTHOR_EMAIL="tester@example.test",
                      GIT_COMMITTER_NAME="Tester", GIT_COMMITTER_EMAIL="tester@example.test")


class UnityWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="dsh test ")
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2022.3.22f1\n")
        (self.project / "Assets").mkdir()

    def write(self, path, text):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def cli(self, tool, *args, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, "-B", str(TOOLS / tool), *args],
            cwd=cwd or self.project, env=env, capture_output=True, encoding="utf-8", check=False,
        )

    def json_output(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.project, env=GIT_IDENTITIES,
                                       encoding="utf-8").strip()

    def editor_fixture(self, main):
        editor = self.project / "Library" / "Unity.exe"
        source = self.write("Library/fake.cs", "using System; using System.IO;\n"
                            "public class Fixture { public static void Main(string[] args) {\n" + main + "\n} }")
        environment = dict(os.environ, UNITY_EDITOR_PATH=str(editor))
        build = subprocess.run([
            "powershell.exe", "-NoProfile", "-Command",
            "Add-Type -Path $env:DSH_TEST_SOURCE -OutputAssembly $env:UNITY_EDITOR_PATH "
            "-OutputType ConsoleApplication",
        ], env=dict(environment, DSH_TEST_SOURCE=str(source)), capture_output=True, text=True)
        self.assertEqual(build.returncode, 0, build.stderr)
        return environment

    def avatar_scene(self):
        self.write("Packages/com.vrchat.avatars/VRCSDK3A.dll", "stub")
        self.write("Packages/com.vrchat.avatars/VRCSDK3A.dll.meta", f"guid: {SDK_GUID}\n")
        self.write("Assets/Avatar.prefab", f"--- !u!114 &50\nMonoBehaviour:\n"
                   f"  m_Script: {{fileID: 42, guid: {SDK_GUID}, type: 3}}\n"
                   "--- !u!1 &51\nGameObject:\n  m_Name: Avatar\n"
                   "--- !u!4 &52\nTransform:\n  m_GameObject: {fileID: 51}\n")
        self.write("Assets/Avatar.prefab.meta", f"guid: {PREFAB_GUID}\n")
        self.write("Assets/試着.unity", "".join(
            f"--- !u!1001 &{i}\nPrefabInstance:\n  m_Modification:\n"
            f"  m_SourcePrefab: {{fileID: 100100000, guid: {PREFAB_GUID}, type: 3}}\n"
            for i in (100, 101)
        ))
        self.write("Assets/試着.unity.meta", f"guid: {'3' * 32}\n")

    def test_first_diagnosis_from_a_project_subfolder_returns_one_json_document(self):
        for _ in range(2):
            result = self.json_output(self.cli("unity_inspect.py", "report", "--json",
                                               cwd=self.project / "Assets"))
            self.assertEqual(Path(result["project"]), self.project)
        self.assertFalse((self.project / ".dsh").exists())

    def test_report_finds_scenes_that_inherit_a_descriptor_from_a_prefab(self):
        self.avatar_scene()
        report = self.json_output(self.cli("unity_inspect.py", "report", ".", "--json"))
        self.assertEqual(report["avatars"], ["Assets/Avatar.prefab", "Assets/試着.unity"])

    def test_repeated_prefab_expands_in_each_instance(self):
        self.avatar_scene()
        self.json_output(self.cli("unity_inspect.py", "index", ".", "--json"))
        hierarchy = self.json_output(self.cli("unity_inspect.py", "hierarchy", "Assets/試着.unity", "--json"))
        self.assertEqual([node["name"] for node in hierarchy["nodes"]],
                         ["[prefab] Avatar", "Avatar", "[prefab] Avatar", "Avatar"])

    def test_guid_resolution_refreshes_after_add_and_move(self):
        self.json_output(self.cli("unity_inspect.py", "index", ".", "--json"))
        self.avatar_scene()
        for expected in ("Assets/Avatar.prefab", "Assets/Renamed.prefab"):
            refs = self.json_output(self.cli("unity_inspect.py", "refs", "--guid", PREFAB_GUID, "--json"))
            self.assertEqual(refs["target"], expected)
            if expected == "Assets/Avatar.prefab":
                for extension in (".prefab", ".prefab.meta"):
                    (self.project / f"Assets/Avatar{extension}").rename(self.project / f"Assets/Renamed{extension}")

    def test_preview_does_not_copy_helpers_or_initialize_git(self):
        self.avatar_scene()
        self.write(".gitignore", "# Existing ignore\n")
        self.write("AGENTS.md", "Existing project instructions\n")
        preview = self.json_output(self.cli("unity_toggle.py", "preview", "--scene", "Assets/試着.unity",
                                           "--avatar", "Avatar", "--outfit", "Avatar/服", "--menu", "衣装/服"))
        self.assertEqual(preview["git"]["state"], "no-repository")
        self.assertIn("Assets/試着.unity", preview["plannedPaths"])
        self.assertFalse((self.project / ".git").exists())
        self.assertFalse((self.project / ".dsh").exists())
        self.assertEqual((self.project / ".gitignore").read_text(), "# Existing ignore\n")
        self.assertEqual((self.project / "AGENTS.md").read_text(), "Existing project instructions\n")

    def test_checkpoint_preserves_existing_project_instructions_and_ignores_transient_data(self):
        self.write(".gitignore", "# Rules\n/custom/\n")
        self.write("AGENTS.md", "Existing project instructions\n")
        self.write("Assets/test.txt", "work")
        self.write("Library/Cache.file", "cache")
        self.write(".dsh/logs/old.log", "log")
        self.json_output(self.cli("unity_toggle.py", "checkpoint"))
        self.assertFalse((self.project / ".git").exists())
        result = self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        self.assertEqual(result["git"]["state"], "ready")
        self.assertEqual(self.git("remote"), "")
        self.assertEqual(self.git("ls-files", "Library", ".dsh"), "")
        self.assertEqual(self.git("show", "HEAD:AGENTS.md"), "Existing project instructions")
        self.assertTrue((self.project / ".gitignore").read_text().startswith("# Rules\n/custom/\n"))

    @unittest.skipUnless(os.name == "nt", "Doctor uses Windows PowerShell")
    def test_doctor_distinguishes_other_packages_from_the_avatar_sdk(self):
        self.write("Packages/manifest.json", '{"dependencies":{"com.example.tool":"1.0.0"}}')
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 str(TOOLS / "doctor.ps1"), "-Project", str(self.project)],
                                capture_output=True, encoding="utf-8", errors="replace")
        self.assertRegex(result.stdout, r"VRChat Avatar SDK\s+FAIL")
        self.assertRegex(result.stdout, r"unity licence\s+WARN")

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_runner_rejects_exit_zero_without_a_current_result(self):
        # A real child process that exits successfully without invoking the requested method.
        legacy = self.write("Assets/DSH/Results/Old.json", '{"ok": true, "task": "Old"}')
        environment = self.editor_fixture("")
        run = subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(TOOLS / "unity-run.ps1"), "-Project", str(self.project), "-Method", "DSH.Tasks.Example.Execute",
        ], env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(legacy.is_file())

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_runner_refuses_an_open_project_before_installing_helpers(self):
        environment = self.editor_fixture("System.Threading.Thread.Sleep(30000);")
        editor = subprocess.Popen([environment["UNITY_EDITOR_PATH"]], creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(editor.wait, 5)
        self.addCleanup(editor.terminate)
        self.write("Library/EditorInstance.json", json.dumps({"process_id": editor.pid}))
        self.write("Temp/UnityLockfile", "active")
        request = self.write("request.json", '{"helpers":[{"file":"DshApply.cs","before":null}]}')
        run = subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(TOOLS / "unity-run.ps1"), "-Project", str(self.project), "-Method", "DSH.Tasks.Example.Execute",
            "-InstallOutfitHelpers", "-RequestFile", str(request),
        ], env=environment, capture_output=True, encoding="utf-8", errors="replace", timeout=10)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Close the editor", run.stderr)
        self.assertFalse((self.project / "Assets/DSH").exists())

    @unittest.skipUnless(os.name == "nt", "Unity runner uses Windows PowerShell")
    def test_apply_declines_stale_previews_and_can_repeat_a_verified_request(self):
        scene = self.write("Assets/試着.unity", "original\n")
        self.json_output(self.cli("unity_toggle.py", "checkpoint", "--confirm", env=GIT_IDENTITIES))
        target = ("--scene", "Assets/試着.unity", "--avatar", "Avatar", "--outfit", "Avatar/Hoodie",
                  "--menu", "衣装/パーカー")
        environment = self.editor_fixture(r'''
            string request = File.ReadAllText(Environment.GetEnvironmentVariable("DSH_UNITY_REQUEST_PATH"));
            if (!request.Contains("衣装/パーカー")) Environment.Exit(4);
            File.AppendAllText("Assets/試着.unity", "saved\n");
            File.WriteAllText(Environment.GetEnvironmentVariable("DSH_UNITY_RESULT_PATH"),
                "{\"ok\":true,\"task\":\"OutfitToggle\",\"verified\":true,\"saved\":true}");
        ''')
        before = self.json_output(self.cli("unity_toggle.py", "preview", *target))
        scene.write_text("user edited since preview\n", encoding="utf-8")
        stale = self.cli("unity_toggle.py", "apply", *target, "--approved-preview", before["preview"], env=environment)
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("preview changed", json.loads(stale.stdout)["error"])
        self.assertFalse((self.project / "Assets/DSH").exists())
        self.git("restore", "--", "Assets/試着.unity")

        applied = self.json_output(self.cli("unity_toggle.py", "apply", *target,
                                           "--approved-preview", before["preview"], env=environment))
        self.assertTrue(applied["unity"]["verified"])
        self.assertTrue((self.project / "Assets/DSH/Editor/DshApply.cs").is_file())
        self.assertEqual(scene.read_text(), "original\nsaved\n")
        again = self.json_output(self.cli("unity_toggle.py", "preview", *target))
        repeated = self.json_output(self.cli("unity_toggle.py", "apply", *target,
                                            "--approved-preview", again["preview"], env=environment))
        self.assertTrue(repeated["alreadyApplied"])
        self.assertEqual(scene.read_text(), "original\nsaved\n")
        self.git("restore", "--source", applied["checkpoint"], "--", "Assets/試着.unity")
        self.assertEqual(scene.read_text(), "original\n")


if __name__ == "__main__":
    unittest.main()
