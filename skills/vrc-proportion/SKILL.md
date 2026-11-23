---
name: vrc-proportion
description: ビューポイント（一人称の目線）の位置と、頭・手などボーン単位の大きさを変える。目線のずれ、頭を大きく・手を小さくしたいと頼まれたら読む。
---

# ビューポイントと部分的な大きさ

```
読む（今のビューポイント、目の位置、大きさを変えたボーン）
 → レシピを書いて確認
 → 撮影して前後比較（目線の位置に赤い印）
 → 適用（preview → 確認 → apply、SDK 検証）
```

FBX は変えない。ビューポイントは Avatar Descriptor の値、大きさはボーンのスケール（シーンのオーバーライド）か
Modular Avatar Scale Adjuster で変える。レシピは `Assets/DSH/Proportions/<名前>/recipe.json` に置く。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$pr = '<pkg>\tools\unity_proportion.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $pr read --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
```

`viewPosition`（今の値）、`eyes`（両目のボーンの中間）、`suggested`（自動で置く位置）、`viewToEyes`（今の値と目の距離、メートル）、
`scaleAdjusters`（Scale Adjuster の付いたボーン）が出る。座標はアバターの向き（x 右、y 上、z 前、メートル）。

## 2. レシピを書く

```json
{
  "name": "BigHead",
  "view": "auto",
  "scales": [
    {"bone": "Head", "scale": 1.1},
    {"bone": "LeftHand", "scale": 0.9, "children": false}
  ]
}
```

| 項目 | 内容 |
|---|---|
| `view` | `"auto"`（両目の間、少し前。`forward` で前に出す量、既定 0.035 m）、`[x, y, z]`（値で指定）、`{"offset": [x, y, z]}`（DSH が変える前の位置からずらす） |
| `scales[].bone` | Humanoid のボーン名（`Head`、`LeftHand`、`Chest` など） |
| `scales[].scale` | 倍率（0.1〜5）か `[x, y, z]`。何度 apply しても元の大きさに対する倍率 |
| `scales[].children` | `true`（既定）: ボーンごと大きくする。頭なら髪・耳・帽子も一緒に大きくなる。`false`: Scale Adjuster で、そのボーンに付いた体だけを変え、子（指や髪）は変えない |

- 頭を大きくするときは `children: true`。`false` にすると顔だけが大きくなり、髪がずれる。
- 大きさを変えると目の位置も動く。`view: "auto"` は大きさを変えたあとの目の位置から決める。
- 手を小さくするとき、指も一緒に小さくするなら `children: true`、手のひらだけなら `false`。

## 3. 撮影して確認する（シーンは保存しない）

```powershell
python -B $pr capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe BigHead --views front,left,face
```

上段が元、下段がレシピを当てた状態（既定で SDK ビルドしたコピー）。目線の位置に赤い球が描かれる。
`viewPositions` に両段の値が出る。顔の正面（face）で、赤い球が両目の間、顔の表面のすぐ前にあるかを見る。
顔の中に隠れて見えないときは `forward` を増やす。

## 4. 適用する・戻す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'BigHead')
python -B $pr preview @a --verify-sdk
python -B $pr apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $pr remove @a                                   # 戻す内容だけを返す
python -B $pr remove @a --approved-preview '<値>'
```

- preview の `summary` と `plannedPaths` を伝え、明示的な確認を得てから apply する。Git の扱いは体型調整と同じ。
- remove は `.dsh/proportions/<名前>.json` に記録した分（前のビューポイント、前のボーンのスケール、DSH が足した Scale Adjuster）だけを戻す。
- 一人称での見え方（目線の高さ、手の大きさ）は、Gesture Manager か VRChat で確かめてもらう。
