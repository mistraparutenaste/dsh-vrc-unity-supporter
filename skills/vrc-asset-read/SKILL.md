---
name: vrc-asset-read
description: Unity プロジェクトを開かずに読む手順。.meta の GUID 索引、シーン/プレハブの階層、参照切れ、VRChat/MA/VRCFury/AAO コンポーネントの検出を unity_inspect.py で行う。アバターの構造把握や「なぜか動かない」の切り分けに使う。
---

# プロジェクトを開かずに読む

`unity_inspect.py` は Unity を起動せず、`Assets/` と `Packages/` の YAML と `.meta` を読む。
速く、Library ロックを取らず、Unity が起動中でも使える。

## 0. ツールの場所

このスキルの 2 階層上がパッケージルート（`<pkg>`）。Claude Code では `${CLAUDE_PLUGIN_ROOT}`。

```powershell
python <pkg>/tools/unity_inspect.py --help
```

## 1. まず全体像: `report`

```powershell
python <pkg>/tools/unity_inspect.py report --json
# 別のフォルダを指定する場合
python <pkg>/tools/unity_inspect.py report "C:\path\to\Project" --json
```

出力（`--json` で機械可読）:

| 項目 | 意味 |
|---|---|
| `unity.version` | `ProjectVersion.txt` の版 |
| `vpm.packages` | 導入済み VPM パッケージ（3 形式をまとめて検出、下記） |
| `vpm.lock` | `vpm-lock.json` / `vpm-manifest.json` のどちらがあるか |
| `avatars` | `Assets/` 内で VRChat SDK のスクリプトを使うPrefab・シーンの候補。Prefab参照から継承した候補を含み、Unityで個別のDescriptorを確認する |
| `scripts.missing` | `Assets/` と `Packages/` の索引で解決できない `m_Script` GUID |
| `meta.missing` | `.meta` が無いアセット（Unity が GUID を振り直す危険） |
| `git` | `.git` の有無 |

VPM の検出は 3 形式すべてを見る（クライアントによって書き方が違う）:

1. `Packages/manifest.json` の `dependencies` — VCC / ALCOM 2.x
2. `Packages/vpm-manifest.json` の `dependencies` — 旧 vrc-get
3. `Packages/<id>/package.json` — 埋め込みパッケージ（どちらのクライアントでも）

`scripts.missing` が空でないときは、参照元と依存パッケージを調べ、Unityの表示で確認する。

## 2. 階層を見る: `hierarchy`

```powershell
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.prefab"
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.prefab" --depth 0   # 参照解決なし
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.unity" --filter Hoodie --json   # パスで絞る
```

各ノードについて `m_Name`、`fileID`、コンポーネント（スクリプト名に解決できたもの）、
有効/無効を出す。プレハブのインスタンスは元 prefab を解決して展開する（既定 `--depth 2`）。

出力は既定で先頭 300 ノードまで、かつ約 48KB まで（`--max-nodes`、0 で件数も容量も無制限）。`--json` は1行のJSONで、
`nodeCount`（総数）と `truncated` を持つ。`truncated` が true なら全件を出し直さず、
`--filter <名前の一部>`（フルパスへの大文字小文字無視の部分一致。一致したノードの子孫も含む）や
`--max-depth <N>`（ツリーの深さ上限、0 がルート）で絞る。シーンにはアバター階層が丸ごと入るため、
シーンの全件表示は避ける。

**FBX モデルのインスタンスは展開できない。** アバターの prefab が `Salt.fbx` のような
モデル prefab のインスタンスになっている場合、ボーンとメッシュは FBX の中にあり YAML には
現れない。その場合は `unity-cli` の `DshInspect.Dump`（バッチモード）を使う。

## 3. 参照をたどる: `refs`

```powershell
python <pkg>/tools/unity_inspect.py refs --guid 1a2b3c... --project "C:\path\to\Project"
```

「このアセットはどこから参照されているか」を返す。削除や移動の前に必ず使う。
`referencedBy` は既定で最大 200 件。総数は `referencedByCount` に入る（超えたら `truncated: true`）。
移動や削除の前に全件が必要なら `--max-refs 0` を付ける（テキスト出力でも同じ）。

## 4. 索引を作る: `index`

```powershell
python <pkg>/tools/unity_inspect.py index "C:\path\to\Project"
```

GUIDとパスの対応をOSの一時フォルダへ書き出す。出力先は `--out` でも指定できる。
`report`、`hierarchy`、`refs` はその時点の `Assets/` と `Packages/` を読み、初回から単一のJSONを返す。

## 5. この方法で分からないこと

| 分からない | 代わりに |
|---|---|
| FBX モデル内のボーン・メッシュ | `DshInspect.Dump`（バッチモード） |
| プレハブ override の最終的な値 | Unity で開く（`DshInspect.cs` のバッチダンプ） |
| 実際の三角形数・マテリアル数 | `vrc-perf-budget`（バッチダンプで計測） |
| アニメーターの実効状態・遷移 | `vrc-verify`（Gesture Manager など） |
| シェーダのコンパイルエラー | Unity のコンソール（バッチログ） |

読み取りで足りないと分かったら、無理に推測せずバッチダンプに切り替える。

`DshInspect.Dump` の `result.json` は要約だけを持つ。ノード本体は `dumpFile`（`dump.ndjson`、
1行1ノードで `depth`/`path`/`name`/`active`/`components`）にある。`assets[]` の
`startLine`/`lineCount` を使い、read の offset/limit で必要な範囲だけ読むか、grep でパスを探す。
ファイル全体を一度に読まない。prefab が 50 件を超えると `assets[]` は先頭 50 件だけになる（`assetsTruncated`）。全件の行範囲は `assetIndexFile`（`dump-index.ndjson`、1 行 1 prefab）を必要な範囲だけ読む。対象 prefab・上限・絞り込みはリクエストで渡す（`unity-cli` §7）。

## 6. 報告の作法

- 数値は必ず出典（どのファイル・どのコマンド）を添える
- 「参照切れ」を見つけたら、原因（パッケージ未導入 / アセット移動）を切り分けて書く
- 壊れた箇所を勝手に直さない。まず一覧を出して承認を取る
