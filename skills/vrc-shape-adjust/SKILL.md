---
name: vrc-shape-adjust
description: FBX を変えずに、シェイプキーで体型・顔を変え、衣装を体型に追従させ（MA Blendshape Sync）、服の下の体をビルド時に消す（AAO）。体型調整・貫通・はみ出しを頼まれたら読む。
---

# 形の調整（シェイプキー・衣装の追従・隠れる部分の削除）

```
読む（シェイプキーと既存の連動を一覧）
 → レシピを書いて確認
 → 撮影して前後比較（SDK ビルド後の見た目と三角形数）
 → 適用（preview → 確認 → apply、SDK 検証）
```

元の FBX は変えない。変更はシーンに保存されるシェイプキーの値と、追加するコンポーネントだけ。
レシピは `Assets/DSH/Shapes/<名前>/recipe.json` に置く（DSH が管理するフォルダ）。

`<pkg>` はパッケージのルート（Claude Code では `${CLAUDE_PLUGIN_ROOT}`）。

```powershell
$shape = '<pkg>\tools\unity_shape.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $shape shapes --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --filter 'Body' --prepare
```

`renderers[]` に、メッシュのパス、三角形数、シェイプキー（値が 0 のものは名前だけ、それ以外は `{name, weight}`）、
既存の `blendshapeSync`（`ソース:シェイプキー`）と `removeMeshByBlendShape` が出る。
顔のメッシュはシェイプキーが数百あるので、`--filter` で体や衣装に絞る（上限 400 件。`truncated` を確認）。

よくある名前:

| 種類 | 例 | 使い方 |
|---|---|---|
| 体型 | `Breasts_big`、`Chest_flat`、`Waist_slim`、`Hip_narrow` | 値を変える（`weights`） |
| 縮める | `Chest_1_OFF`、`UpperArm_OFF`、`Knee_OFF_L` | 服の下を消す（`remove`） |
| 衣装側の対応キー | `Hoodie_Breasts_big`、`Socks_Hip_narrow` | 体に追従させる（`sync`） |

## 2. レシピを書く

```json
{
  "name": "Fit_Hoodie",
  "weights": [
    {"renderer": "Body_base", "shape": "Chest_flat", "weight": 0},
    {"renderer": "Body_base", "shape": "Breasts_big", "weight": 60}
  ],
  "sync": [
    {"renderer": "Costume_Hoodie", "source": "Body_base", "shapes": ["Breasts_big", "Chest_flat"]}
  ],
  "remove": [
    {"renderer": "Body_base", "shapes": ["Chest_1_OFF", "Spine_1_OFF", "UpperArm_OFF"], "tolerance": 0.001}
  ]
}
```

| 項目 | 内容 |
|---|---|
| `weights` | シェイプキーの値（0〜100）をシーンに保存する |
| `sync` | `renderer`（衣装）のシェイプキーを `source`（体）に追従させる（MA Blendshape Sync）。衣装側の名前は、同名か `_<名前>` で終わる 1 つを自動で選ぶ。違う名前なら `"体の名前=衣装の名前"` と書く |
| `remove` | そのシェイプキーで動く頂点を、ビルド時に削除する（AAO Remove Mesh By BlendShape）。`tolerance` は既定 0.001 |

- 体型を変えるときは、衣装の対応キーが体に追従しているかを `shapes` で確かめる。アバターによっては作者が最初から連動を入れている（すでにある連動は追加しない）。
- `remove` には、その衣装を着ているときに完全に隠れる部位だけを入れる。袖が短い服で `LowerArm_OFF` を入れると腕が消える。
- 書いたら、変える値、追従させるキー、消す部位をユーザーに伝えて確認を取る。

## 3. 撮影して確認する（シーンは保存しない）

```powershell
python -B $shape capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Fit_Hoodie --views front,left,face
```

上段が元、下段がレシピを当てた状態。既定では両方を **SDK でビルドしたコピー** で撮るので、
衣装の追従と隠れる部分の削除が VRChat と同じように反映される。`unity.triangles` に各段の三角形数が出る。
グラフィックス有りで Unity を起動する（GPU が要る）。`--no-build` でビルドせずに撮れる（速いが、削除は反映されない）。

- 首元、袖口、裾など、服と体の境目を見て、貫通や穴（消しすぎ）がないかを確かめる。
- 画像を読めない場合はパスを伝えてユーザーに見てもらう。

## 4. 適用する

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Fit_Hoodie', '--verify-sdk')
python -B $shape preview @a
python -B $shape apply @a --approved-preview '<preview の値>'
```

- preview の `summary`（値の数、追従するキーの数、消すキーの数）と `plannedPaths` を伝え、明示的な確認を得てから apply する。
- Git の扱いは衣装トグル・色違いと同じ（チェックポイントが必要、DSH が保存したシーンはコミットなしで続けられる）。
- apply は、保存後にシーンを読み直してもう一度レシピを当て、何も変わらないことを確かめる（`unity.applied` が今回の変更）。
- `unity.sdkVerification` に、シーン上とビルド後の三角形数が出る。性能ランクへの影響は `vrc-perf-budget` で判断する。
- 元に戻すときは `remove` を使う。apply が `.dsh/shapes/<名前>.json` に記録した分（変える前の値、DSH が足した追従・削除のキーとコンポーネント）だけを戻し、作者が最初から入れていた連動は残す。レシピのファイルは残る。

```powershell
python -B $shape remove --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Fit_Hoodie
python -B $shape remove --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Fit_Hoodie --approved-preview '<値>'
```

  `--approved-preview` なしでは `summary`（戻す値・追従・削除の数）だけを返すので、伝えて確認を取ってから実行する。記録が無い（この版より前に適用した、別のコピーで適用した）ときは止まるので、Git でシーンを復元する（`vrc-first-run` の復元の注意を参照）。

## 注意

- AAO のメッシュ処理はグラフィックス有りでないと動かないため、`--verify-sdk` と撮影ではグラフィックス有りで Unity を起動する。
- 衣装に対応キーが無い体型変更は、衣装が体に追従しない。その場合はボーンの大きさ（MA Scale Adjuster）か、Blender で体型キーを衣装にも作る（`vrc-blender-model` の `followShapes`）。
