---
name: unity-cli
description: Unity をバッチモードで動かす手順。エディタの解決、コマンド形、ログの読み方、Library ロックとライセンスの失敗、長時間処理をジョブで回す方法を扱う。スクリプトを適用・検証するときに下支えとして読む。
---

# Unity バッチモード

`tools/unity-run.ps1` がこのスキルの内容を実装している。通常はランナーを呼ぶだけでよく、
このスキルは**失敗したときの読み方**のためにある。

## 1. エディタの解決

Unity Hub は `C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe` に置く。

1. `<project>/ProjectSettings/ProjectVersion.txt` の `m_EditorVersion` を読む
2. 上記パスを探す。無ければ Hub の別ドライブ（`%ProgramFiles%` 以外）も探す
3. 見つからなければ**止まる**。勝手に別バージョンで開かない（プロジェクトが壊れる）

## 2. コマンド形

```powershell
& "<Unity.exe>" -batchmode -nographics -quit `
  -projectPath "<project>" `
  -executeMethod "<Namespace.Class.Method>" `
  -logFile "<project>\.dsh\runs\<run-id>\<name>.log"
```

| 引数 | 意味 |
|---|---|
| `-batchmode` | GUI 無し。スクリプトから実行する場合に必須 |
| `-nographics` | GPU 初期化をしない。重いアセットの描画確認には使えない |
| `-quit` | メソッド終了後に終了する（`EditorApplication.Exit` を書くなら不要な場合あり） |
| `-executeMethod` | 静的メソッドを 1 つ実行する |
| `-logFile` | ログの出力先。`-` で標準出力 |

## 3. 終了コードとログ

| 終了コード | 意味 | 見る場所 |
|---|---|---|
| 0 | 成功 | 同じ実行ディレクトリの `result.json` |
| 1 | 失敗（例外・コンパイルエラー・ライセンス） | ログの末尾 |
| 124 | タイムアウト | ログの末尾 |
| その他 | Unity 自体の異常終了 | ログ全体 |

ログで探す文字列:

- `error CS` — コンパイルエラー（スクリプトの誤り）
- `Exception` / `NullReferenceException` — 実行時例外
- `No valid Unity Editor license found` — ライセンス未認証
- `Aborting batchmode due to failure` — 上記いずれかで中断

**最初の `error CS` だけ直して再実行**する。1 個直すと連鎖が消えることが多い。

## 4. Library ロック

Unity がプロジェクトを開いている間は、別プロセスから同じプロジェクトを開けない。

検出:

```
<project>/Temp/UnityLockfile          ← ロックが残っている可能性
<project>/Library/EditorInstance.json  ← pid が入る
```

ランナーは検出したら**実行せずに終了**する。ユーザーに「Unity を閉じてください」と伝える。
無理に消してはいけない（データ破損の原因）。

## 5. ライセンス

バッチモードもライセンスを必要とする。未認証なら上のエラーで落ちる。
この場合 AI は何もできないので、**Unity Hub でサインインしてライセンスを有効化**するよう伝える。

## 6. 長時間処理の扱い

アセットのインポートは数分かかることがある。同期で待たない。

```powershell
# 悪い例: タイムアウトする
& unity-run.ps1 -Project ... -Method ...

# 良い例: ジョブで回してログを追う
```

DSh のジョブ機能（`tool-jobs`）でバックグラウンド実行し、ログを tail する。
初回起動は Library 生成で特に遅い。2 回目以降は速い。

## 7. 初回だけ必要な準備

初回の衣装トグルは `vrc-first-run` の適用コマンドがヘルパーを配置する。独自タスクでは `templates/Editor/` の必要なファイルを `Assets/DSH/Editor/` に配置する。
旧テンプレートだけを使っているプロジェクトは、新しい `DshApply.cs` を取り込む。独自の結果を返さない既存メソッドでは `-AllowMissingResult` を指定できる。

`DshInspect.Dump` は任意のリクエストを受け取る。省略時は全アバター prefab を 1 prefab あたり 4000 ノードまで出す。

```powershell
'{"prefab":"Assets/Avatar.fbx","maxNodes":2000,"filter":"Armature"}' | Set-Content req.json -Encoding utf8
& "<pkg>\tools\unity-run.ps1" -Project "C:\path\to\Project" `
  -Method "DSH.Editor.DshInspect.Dump" -ExpectedTask Dump -RequestFile req.json
```

`prefab` は GameObject として読める任意のアセット（FBX も可）、`maxNodes` は 0 で無制限、`filter` はフルパスへの部分一致。
ノードは `result.json` と同じフォルダの `dump.ndjson` に 1 行ずつ書かれる。読み方は `vrc-asset-read` §5。
