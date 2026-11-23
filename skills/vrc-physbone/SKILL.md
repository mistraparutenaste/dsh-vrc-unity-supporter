---
name: vrc-physbone
description: 髪・スカート・しっぽの揺れ方、掴める・ポーズできるかを PhysBone の値で変え、脚などにコライダーを足して貫通を防ぐ。揺れ物の調整を頼まれたら読む。
---

# 揺れ物の調整（PhysBone）

```
読む（PhysBone とコライダーを一覧）
 → レシピを書いて確認
 → 適用（preview → 確認 → apply、SDK 検証）
 → Gesture Manager で揺れ方を見てもらう
```

元の prefab は変えない。値はシーンのオーバーライドとして保存し、コライダーは Humanoid のボーンの下に
`DSH Collider <レシピ名> <名前>` として足す。レシピは `Assets/DSH/PhysBones/<名前>/recipe.json` に置く（DSH が管理するフォルダ）。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$pb = '<pkg>\tools\unity_physbone.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $pb list --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
```

`physBones[]` に、PhysBone の付いたオブジェクト（`target`）、同じオブジェクトに複数あるときの番号（`index`）、
揺らすボーンの根元（`root`）、部位の推測（`part`: hair / skirt / tail / ear / breast / other）、
揺らすボーンの数（`transforms`）、今の値（`values`）、使っているコライダーが出る。`--filter Hair` で絞れる。
`counts` は PhysBone の数、揺れるボーンの合計、コライダーの数（性能ランクの項目。`vrc-perf-budget`）。

## 2. レシピを書く

```json
{
  "name": "SoftHair",
  "bones": [
    {"target": "AvatarDynamics/PB/Hair/Hair_back", "preset": "soft"},
    {"target": "AvatarDynamics/PB/Kemono_Tail", "values": {"allowGrabbing": false, "gravity": 0.1}}
  ],
  "colliders": [
    {"name": "LegL", "bone": "LeftUpperLeg", "radius": 0.07,
     "targets": [{"target": "AvatarDynamics/PB/Skirt"}]}
  ]
}
```

`bones`（既存の PhysBone の値を変える）:

| 項目 | 内容 |
|---|---|
| `target` | list の `target`（PhysBone の付いたオブジェクト）か `root`（揺らす根元）。同じオブジェクトに複数あるときは `index` |
| `preset` | `soft`（ふわっと）、`normal`、`stiff`（硬め）、`heavy`（重く垂れる）、`skirt`。`values` が優先される |
| `values` | `pull`、`spring`、`stiffness`、`gravity`、`gravityFalloff`、`immobile`、`grabMovement`、`maxSquish`（0〜1）、`maxStretch`（0〜5）、`maxAngleX` / `maxAngleZ`（0〜180）、`radius`、`limitType`（None / Angle / Hinge / Polar）、`immobileType`（AllMotion / World）、`integrationType`（Simplified / Advanced）、`allowCollision` / `allowGrabbing` / `allowPosing` / `snapToHand`（true / false） |

`colliders`（コライダーを足す）:

| 項目 | 内容 |
|---|---|
| `name` | レシピ内で一意の名前 |
| `bone` | 付ける Humanoid のボーン（`LeftUpperLeg`、`Hips`、`Head` など） |
| `shape` | `capsule`（既定。`bone` から次のボーンまで。`to` で終点を変えられる）か `sphere` |
| `radius` / `height` | 太さと長さ（メートル）。`height` を省くとボーンの長さから決める |
| `offset` | アバターの向き（x 右、y 上、z 前）でずらす量 |
| `targets` | このコライダーを使う PhysBone（`bones` と同じ書き方）。必ず 1 つ以上 |

- PhysBone 1.0（list の `version` が `Version_1_0`）では `stiffness` が効かない。
- 「掴めないように」は `allowGrabbing: false`、「ポーズを付けられないように」は `allowPosing: false`。
- スカートが脚を貫通するときは、左右の `UpperLeg` にカプセルを足して、スカートの PhysBone を `targets` にする。
- 書いたら、変える値（今 → 後）と足すコライダーをユーザーに伝えて確認を取る。

## 3. 適用する

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'SoftHair')
python -B $pb preview @a --verify-sdk
python -B $pb apply @a --verify-sdk --approved-preview '<preview の値>'
```

- preview の `summary`（変える PhysBone の数、値の数、コライダーの数）と `plannedPaths` を伝え、明示的な確認を得てから apply する。
- `unity.applied` に変えた値（前 → 後）、`unity.countsBefore` / `counts` に性能ランクの項目の前後が出る。
- Git の扱いは衣装トグル・体型調整と同じ。
- 揺れ方は撮影では分からない。適用後、Gesture Manager（Play モード）で髪やスカートを揺らして確かめてもらう（`vrc-verify`）。

## 4. 元に戻す

```powershell
python -B $pb remove @a
python -B $pb remove @a --approved-preview '<値>'
```

apply が `.dsh/physbones/<名前>.json` に記録した分（変える前の値、足したコライダーとその登録）だけを戻す。
戻した値が prefab と同じなら、シーンのオーバーライドも外す。`python -B $pb recipes` でレシピと適用先のシーンを一覧にできる。
