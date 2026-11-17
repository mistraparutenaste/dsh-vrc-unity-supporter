---
name: vrc-edit-script
description: アバター改変を Unity Editor スクリプトとして書き、バッチモードで適用する手順。冪等な書き方、結果 JSON、失敗時の巻き戻し、YAML と .meta を壊さないための制約を扱う。シーンやプレハブの構造を変えるときに使う。
---

# Editor スクリプトで改変を適用する

このプリセットの適用経路は 1 本だけ:

```
設計 → C# を書く → バッチモードで実行 → 結果 JSON を読む → git 差分を確認
```

シーン/プレハブの YAML を直接書き換えてはいけない。GUID と参照が壊れて復旧できなくなる。

## 0. パッケージの場所

このスキルの 2 階層上がパッケージルート。ツールはそこからの相対で呼ぶ。

```
<pkg>/skills/vrc-edit-script/SKILL.md   ← ここ
<pkg>/tools/unity-run.ps1
<pkg>/templates/Editor/DshApply.cs
```

`<pkg>` は通常 `%USERPROFILE%\.dsh\profiles\<profile>\node_modules\dsh-vrc-unity-supporter`。
分からなければ `doctor.ps1` が表示する。

## 1. 守る制約

| # | 制約 |
|---|---|
| C1 | 実行前に `git status` がクリーンであること。汚れていれば commit を促して止まる |
| C2 | 何度実行しても同じ結果になる（冪等）ように書く。`Find` して無ければ作る、有れば更新 |
| C3 | ファイルの移動・削除は `AssetDatabase.MoveAsset` / `AssetDatabase.DeleteAsset` を使う。`File.Delete` で `.meta` を孤立させない |
| C4 | プレハブの編集は `PrefabUtility.LoadPrefabContents` / `SaveAsPrefabAsset` を通す |
| C5 | シーンの編集は `EditorSceneManager.OpenScene` → 変更 → `SaveScene` |
| C6 | 例外は握りつぶさず、結果 JSON に `ok: false` と例外を書いて `EditorApplication.Exit(1)` |
| C7 | 変更内容を `changes` 配列に列挙する（人間がレビューできる粒度） |

## 2. タスクスクリプトの雛形

`Assets/DSH/Editor/Tasks/<TaskName>.cs` に置く。名前空間は `DSH.Tasks`。

**必ず `Editor` フォルダの配下に置く。** `DshApply` は Editor アセンブリに含まれるので、
`Assets/DSH/Tasks/` のような通常フォルダに置くと
`error CS0234: The type or namespace name 'DshApply' does not exist` でコンパイルが落ちる。

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DSH.Tasks
{
    public static class AddOutfitToggle
    {
        // バッチモード入口: -executeMethod DSH.Tasks.AddOutfitToggle.Execute
        public static void Execute()
        {
            var result = new Dictionary<string, object>
            {
                { "task", "AddOutfitToggle" },
                { "changes", new List<string>() },
            };
            try
            {
                const string scenePath = "Assets/Avatar.unity";
                var scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);

                // --- ここに冪等な変更を書く ---
                var root = GameObject.Find("Avatar");
                if (root == null) throw new Exception("Avatar ルートが見つからない");

                var toggle = root.transform.Find("Outfit_Hoodie");
                if (toggle == null)
                {
                    var go = new GameObject("Outfit_Hoodie");
                    go.transform.SetParent(root.transform, false);
                    ((List<string>)result["changes"]).Add("created Outfit_Hoodie");
                }

                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                result["ok"] = true;
            }
            catch (Exception e)
            {
                result["ok"] = false;
                result["error"] = e.ToString();
            }

            DshApply.WriteResult("AddOutfitToggle", result);
            EditorApplication.Exit((bool)result["ok"] ? 0 : 1);
        }
    }
}
```

`DshApply.WriteResult` は `templates/Editor/DshApply.cs` が提供する
（`Assets/DSH/Editor/DshApply.cs` に配置済みの前提）。

## 3. 実行する

```powershell
<pkg>/tools/unity-run.ps1 -Project "C:\path\to\Project" -Method "DSH.Tasks.AddOutfitToggle.Execute"
```

ランナーがやること:

- `ProjectSettings/ProjectVersion.txt` から Unity のバージョンを読み、対応する
  `Unity.exe` を探す
- `Library/` のロックを検出して、Unity 起動中なら**実行せずに止まる**
- `-batchmode -nographics -quit -logFile <log>` で起動
- 終了コードとログからエラーを抽出して要約する

## 4. 結果を読む

- 終了コード 0 + `Assets/DSH/Results/<TaskName>.json` の `ok: true`
- 失敗時は `error` と Unity ログの `error CS` / `Exception` 行を見る
- コンパイルエラーは「タスクスクリプトの誤り」なので、直して再実行する
  （プロジェクトのアセットを壊したわけではない）

## 5. 失敗したときの戻し方

1. `git status` で何が変わったか確認
2. 意図しない変更があれば `git restore -- <path>`（**新しいファイルは `git clean` ではなく手で消す**。
   `.meta` の孤立を避けるため、`Assets/` 内は `AssetDatabase.DeleteAsset` を優先）
3. スクリプトを直して再実行

## 6. 終わったら

- `git diff --stat` を要約してユーザーに見せる
- 変更が期待通りか `vrc-verify` の手順で確認
- タスクスクリプトは残す（再現手段として価値がある）。消す場合は理由を伝える
