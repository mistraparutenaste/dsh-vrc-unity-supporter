---
name: vrc-asset-read
description: Unity プロジェクトを開かずに読む手順。.meta の GUID 索引、シーン/プレハブの階層、参照切れ、VRChat/MA/VRCFury/AAO コンポーネントの検出を unity_inspect.py で行う。アバターの構造把握や「なぜか動かない」の切り分けに使う。
---

# プロジェクトを開かずに読む

`unity_inspect.py` は Unity を起動せず、`Assets/` と `Packages/` の YAML と `.meta` を読む。
速く、Library ロックを取らず、Unity が起動中でも使える。

## 0. ツールの場所

このスキルの 2 階層上がパッケージルート。

```powershell
python <pkg>/tools/unity_inspect.py --help
```

## 1. まず全体像: `report`

```powershell
python <pkg>/tools/unity_inspect.py report "C:\path\to\Project"
```

出力（`--json` で機械可読）:

| 項目 | 意味 |
|---|---|
| `unity.version` | `ProjectVersion.txt` の版 |
| `vpm.packages` | 導入済み VPM パッケージ（3 形式をまとめて検出、下記） |
| `vpm.lock` | `vpm-lock.json` / `vpm-manifest.json` のどちらがあるか |
| `avatars` | `Assets/` 内で `VRCAvatarDescriptor`（SDK 3.x は VRCSDK3A.dll 内）を使う prefab / シーンの**候補**。prefab バリアントは親だけが出るので、正確な一覧は `DshInspect.Perf` / `Dump` で取る |
| `scripts.missing` | 解決できない `m_Script` GUID（**パッケージ不足の証拠**） |
| `meta.missing` | `.meta` が無いアセット（Unity が GUID を振り直す危険） |
| `git` | `.git` の有無 |

VPM の検出は 3 形式すべてを見る（クライアントによって書き方が違う）:

1. `Packages/manifest.json` の `dependencies` — VCC / ALCOM 2.x
2. `Packages/vpm-manifest.json` の `dependencies` — 旧 vrc-get
3. `Packages/<id>/package.json` — 埋め込みパッケージ（どちらのクライアントでも）

`scripts.missing` が空でないときは、依存パッケージが入っていない。
インストールを勝手に始めず、まず「何が足りないか」を報告する。

## 2. 階層を見る: `hierarchy`

```powershell
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.prefab"
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.prefab" --depth 0   # 参照解決なし
```

各ノードについて `m_Name`、`fileID`、コンポーネント（スクリプト名に解決できたもの）、
有効/無効を出す。プレハブのインスタンスは元 prefab を解決して展開する（既定 `--depth 2`）。

**FBX モデルのインスタンスは展開できない。** アバターの prefab が `Salt.fbx` のような
モデル prefab のインスタンスになっている場合、ボーンとメッシュは FBX の中にあり YAML には
現れない。その場合は `unity-cli` の `DshInspect.Dump`（バッチモード）を使う。

## 3. 参照をたどる: `refs`

```powershell
python <pkg>/tools/unity_inspect.py refs --guid 1a2b3c... --project "C:\path\to\Project"
```

「このアセットはどこから参照されているか」を返す。削除や移動の前に必ず使う。

## 4. 索引を作る: `index`

```powershell
python <pkg>/tools/unity_inspect.py index "C:\path\to\Project"
```

`<project>/.dsh/guid-index.json` に GUID → パス の対応を書く。`hierarchy` と `refs` は
索引があれば高速化される。`Packages/` も含めるので、VRChat SDK のスクリプト名も解決できる。

## 5. この方法で分からないこと

| 分からない | 代わりに |
|---|---|
| FBX モデル内のボーン・メッシュ | `DshInspect.Dump`（バッチモード） |
| プレハブ override の最終的な値 | Unity で開く（`DshInspect.cs` のバッチダンプ） |
| 実際の三角形数・マテリアル数 | `vrc-perf-budget`（バッチダンプで計測） |
| アニメーターの実効状態・遷移 | `vrc-verify`（Gesture Manager など） |
| シェーダのコンパイルエラー | Unity のコンソール（バッチログ） |

読み取りで足りないと分かったら、無理に推測せずバッチダンプに切り替える。

## 6. 報告の作法

- 数値は必ず出典（どのファイル・どのコマンド）を添える
- 「参照切れ」を見つけたら、原因（パッケージ未導入 / アセット移動）を切り分けて書く
- 壊れた箇所を勝手に直さない。まず一覧を出して承認を取る
