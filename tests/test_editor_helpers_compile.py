"""Compile the bundled Editor helpers against a local Unity install's assemblies.

The workflow tests use a fake Unity, so they never compile templates/Editor/*.cs. This test does, with the
Roslyn compiler that Unity ships, against Unity's own engine and editor module assemblies. It needs the
Unity version the package targets (or UNITY_EDITOR_DATA pointing at an Editor/Data folder) and dotnet; it is
skipped where they are missing, as on CI. VRChat, VRCFury and Modular Avatar types are looked up by name at
run time, so the helpers compile without those packages.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
UNITY_VERSION = "2022.3.22f1"


def editor_data():
    configured = os.environ.get("UNITY_EDITOR_DATA")
    candidates = [Path(configured)] if configured else [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Unity" / "Hub" / "Editor" / UNITY_VERSION / "Editor" / "Data"]
    for data in candidates:
        if (data / "DotNetSdkRoslyn" / "csc.dll").is_file() and (data / "Managed" / "UnityEngine").is_dir():
            return data
    return None


def references(data):
    api = data / "UnityReferenceAssemblies" / "unity-4.8-api"
    yield from sorted(api.glob("*.dll"))
    yield api / "Facades" / "netstandard.dll"
    # The split engine and editor modules. UnityEditor.dll repeats the editor types, so it is left out.
    yield from sorted(p for p in (data / "Managed" / "UnityEngine").glob("*.dll") if p.name != "UnityEditor.dll")


@unittest.skipUnless(editor_data() and shutil.which("dotnet"),
                     f"needs Unity {UNITY_VERSION} (or UNITY_EDITOR_DATA) and dotnet")
class EditorHelperCompileTests(unittest.TestCase):
    def test_bundled_helpers_compile_against_unity(self):
        data = editor_data()
        with tempfile.TemporaryDirectory() as work:
            args = ["-target:library", "-nostdlib+", "-preferreduilang:en-US", "-langversion:9.0", "-warnaserror-", "-nowarn:1701,1702",
                    f"-out:{Path(work) / 'DshHelpers.dll'}",
                    *(f'-r:"{path}"' for path in references(data)),
                    *(f'"{path}"' for path in sorted((ROOT / "templates" / "Editor").glob("*.cs")))]
            response = Path(work) / "args.rsp"
            response.write_text("\n".join(args), encoding="utf-8")
            build = subprocess.run(["dotnet", str(data / "DotNetSdkRoslyn" / "csc.dll"), f"@{response}"],
                                   capture_output=True, encoding="utf-8", errors="replace", check=False)
            errors = [line for line in build.stdout.splitlines() if " error " in line]
            self.assertEqual(build.returncode, 0, "\n".join(errors) or build.stdout[-4000:])


if __name__ == "__main__":
    unittest.main()
