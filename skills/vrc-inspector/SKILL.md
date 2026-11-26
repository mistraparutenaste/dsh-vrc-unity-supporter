---
name: vrc-inspector
description: Unity の Inspector に出ている値を、表示名・保存名・Prefab からの変更つきで読む（unity_inspector.py）。設定値やコンポーネントの場所を聞かれたら、推測せずにこれで読む。
---

# Inspector の値を読む

`unity_inspector.py` は Unity をバッチで開き、コンポーネントの SerializedObject を読む。Inspector が表示するのと
同じ保存済みの値（Prefab の値に、シーンでの上書きを重ねたもの）が、Inspector と同じ表示名で出る。
**ファイルは変えない。** シーンは保存して Unity を閉じてから使う。

YAML を読む `vrc-asset-read` との違い:

| | `vrc-asset-read`（YAML） | `vrc-inspector`（Unity） |
|---|---|---|
| Unity | 起動しない（速い、開いたままでもよい） | バッチで起動する（プロジェクトにより数十秒〜数分） |
| Prefab のアバター | シーンの上書き分しか見えない | Prefab の値と上書きを重ねた、Inspector と同じ値 |
| 表示 | `m_` の保存名、GUID | Inspector の表示名、enum の表示名、アセットのパス |

階層やどのアセットを参照しているかは `vrc-asset-read`、**項目の値**はこちらで読む。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$ins = '<pkg>\tools\unity_inspector.py'
```

初回は `setup-required` が返る。`plannedPaths`（`Assets/DSH/Editor/` の補助スクリプト）を伝えて確認を取ってから `--prepare` を付ける。

## 1. どこにあるかを探す: `find`

```powershell
python -B $ins find --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --type ModularAvatarMenuInstaller
```

`--type` は型名の一部でよい（大文字小文字は区別しない）。`found[]` にオブジェクトのパス（アバターからの相対）、
有効かどうか、合ったコンポーネント。`missingScripts` があれば、スクリプトが読めないコンポーネントがある
（パッケージの入れ忘れ。`vrc-verify` で切り分ける）。

よく探す型: `VRCAvatarDescriptor`、`VRCPhysBone`、`VRCPhysBoneCollider`、`VRCContact`、`ModularAvatar`（MA の全部）、
`ModularAvatarMenuItem`、`ModularAvatarMergeArmature`、`VRCFury`、`AvatarOptimizer`（AAO）、`TexTransTool`（TTT）、`Meshia`。

## 2. 値を読む: `read`

```powershell
python -B $ins read --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --path 'Hair/Hair_Back' --component PhysBone
```

| 引数 | 内容 |
|---|---|
| `--path` | アバターからの相対パス。省くとアバターのルート |
| `--component` | 型名にこれを含むコンポーネントだけ |
| `--field` | 表示名か保存名にこれを含む項目だけ（`--field Pull`） |
| `--hidden` | Inspector が隠している項目も出す（ふつうは不要） |
| `--max-properties` / `--max-depth` / `--array-items` | 出す量の上限（既定 400 / 6 / 20）。`truncated` が true なら絞り込む |

出力:

- `object`：名前、有効か、タグ、レイヤー。Prefab の一部なら `prefab`（元の Prefab）と `addedInScene`（シーンで足したものか）。
- `children`：子オブジェクトの名前。
- `components[]`：上から順（Inspector の並び）。`type`（表示名）、`fullType`、`title`（Inspector の見出し）、`enabled`、
  `script`（スクリプトのパス）、`addedInScene`、`overrides`（Prefab から変えた項目の数）、`missing`（スクリプトが読めない）。
  Transform は `inspector` に Position / Rotation（Inspector と同じオイラー角）/ Scale。
- `properties[]`：

| キー | 内容 |
|---|---|
| `label` | Inspector の表示名（例 `Pull`、`Allow Grabbing`、`Element 0`） |
| `path` | 保存名（例 `pull`、`m_Materials.Array.data[0]`）。スクリプトで変えるときはこちらを使う |
| `depth` | 入れ子の深さ（0 が一番上）。折りたたみの中の項目は深い |
| `type` | 種類（`Float`、`Enum`、`ObjectReference` など。入れ子はクラス名） |
| `value` | 値。enum は表示名、色は `#RRGGBBAA (r, g, b, a)`、参照は `名前 (型) Assets/...`、アバター内なら `avatar:パス`、ほかのシーンのオブジェクトは `scene:パス`、空は `None`、参照切れは `Missing` |
| `size` | 配列・リストの要素数 |
| `override` | Prefab の値からシーンで変えた項目 |
| `tooltip` | Inspector でマウスを乗せると出る説明 |

## 3. 答え方

- ユーザーには **Inspector の表示名**（`label`）で答え、どのオブジェクトのどのコンポーネントかを添える。
  例：「`Hair/Hair_Back` の VRC Phys Bone の Pull は 0.2、Spring は 0.4 です（Prefab から変えています）」。
- `override` が付いた値は、元の Prefab とは違う。アバターの更新で消えやすいので、そう伝える（`vrc-avatar-update`）。
- 表示名が同じ項目がいくつもあるときは、`depth` と `path` で親を確かめる（例：PhysBone の `Limits` 内の `Max Angle`）。
- カーブ（`AnimationCurve`）は「キーがいくつあるか」しか出ない。形はスクリーンショットで確かめてもらう。

### コンポーネントごとの見どころ

- **VRC Avatar Descriptor**：`View Position`、`Lip Sync` と `Face Mesh`、`Eye Look`、`Playable Layers`（FX など）、
  `Expressions` の `Menu` と `Parameters`。値はここで読み、変更はそれぞれのスキルで行う。
- **VRC Phys Bone**：数値の項目は `vrc-physbone` のレシピ名と同じ（`pull`、`spring`、`stiffness`、`gravity`、`radius` など）。
  `… Curve` はカーブ。`Colliders` は参照の配列。
- **Modular Avatar**：Inspector は MA 独自の画面だが、保存された項目はそのまま読める。参照先は `avatar:パス` で出る
  （Merge Armature の `Merge Target`、Menu Installer の `Install To` など）。MA の Inspector は言語を変えられるため、
  ユーザーの画面と表示名が違うことがある。そのときは `path` で突き合わせる。
- **VRCFury**：設定は 1 つの `content`（`ManagedReference`）にまとまり、`value` が機能の型名（例 `Toggle`、`ArmatureLink`）。
  その下の深い項目が中身。`--max-depth 10` まで上げると、トグルの状態やアクションまで読める。
- **Renderer**：`Materials` の要素がマテリアルのアセットのパス。シェーダーの値は `vrc-material-adjust` で読む。

## 4. してはいけないこと

- 読んだ値をもとに、シーンや Prefab の YAML を直接書き換えない。変えるときは、その変更を扱うスキルのコマンドを使い、
  無ければ `vrc-edit-script` で Editor スクリプトを書く（`path` の保存名を `SerializedObject.FindProperty` に使える）。
- ユーザーのスクリーンショットと値が食い違うときは、保存していない変更がある可能性が高い。
  Unity でシーンを保存してから読み直す。
