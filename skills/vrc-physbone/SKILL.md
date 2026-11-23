---
name: vrc-physbone
description: 髪・スカート・しっぽの揺れ方、掴める・ポーズできるかを PhysBone の値で変え、脚などにコライダーを足して貫通を防ぐ。揺れ物の調整を頼まれたら読む。
---

# 揺れ物の調整（PhysBone）

```
読む（PhysBone とコライダーを一覧）
 → 今の揺れを測る（simulate）
 → レシピを書いて、メモリ上で試して比べる（simulate --recipe --compare）
 → 適用（preview → 確認 → apply、SDK 検証）
 → 最後の見た目は Gesture Manager か VRChat で見てもらう
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

## 3. 動かして測る（simulate。シーンは保存しない）

```powershell
python -B $pb simulate --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar'
python -B $pb simulate ... --recipe SoftHair --compare          # レシピをメモリ上で試し、今と比べる
python -B $pb simulate ... --motions sit --filter Skirt          # 座ったときのスカートだけ
```

Unity を Play モードで動かし（VRCFury・MA の Play モード処理と、VRChat SDK の PhysBone がそのまま動く）、
アバターに Humanoid のポーズで動き（`sway` 左右に揺れて振り向く、`walk` 歩く、`sit` 座って立つ）をつけ、そのあと止める。
グラフィックス有りで起動し、1 回 1 分ほどかかる。

`unity.chains[]`（揺れ物ごと）:

| 項目 | 内容 |
|---|---|
| `maxSwing` | 動きごとの、先端の最大の振れ（メートル。揺れ物の根元の親ボーンから見た、静止時からの距離） |
| `settleSeconds` | 止まってから揺れが収まるまでの秒数（`over 4` は 4 秒たっても揺れている） |
| `legDepth` / `legFrames` | 揺れ物のボーンが太もも・すねに入り込んだ深さ（メートル）と、そのフレーム数。脚に付いた揺れ物（脚のベルトなど）は数えない |

`unity.legRadii` は、素体のメッシュから測った脚の太さ。`unity.image` は、静止・各動きの山場・止まって 0.5 秒後の画像（`rows` の順）。

読み方の目安:

- 「もっとふわっと」：`maxSwing` が増え、`settleSeconds` が少し延びる（0.3〜1 秒）ならねらいどおり。`over 4` は揺れすぎ（`pull` か `spring` を下げる）。
- 「硬く」：`maxSwing` と `settleSeconds` が減る。
- スカート・しっぽの貫通：`legDepth` の `sit` や `walk` が 0.01（1 cm）を超えるなら、太ももにコライダーを足す（§2 の `colliders`）。足したら `--compare` で `legDepth` が減ったかを確かめる。
- ポーズは目安の動きで、実際の歩き方やフルボディとは違う。数値は「前より良くなったか」の比較に使う。

## 4. 適用する

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'SoftHair')
python -B $pb preview @a --verify-sdk
python -B $pb apply @a --verify-sdk --approved-preview '<preview の値>'
```

- preview の `summary`（変える PhysBone の数、値の数、コライダーの数）と `plannedPaths` を伝え、明示的な確認を得てから apply する。
- `unity.applied` に変えた値（前 → 後）、`unity.countsBefore` / `counts` に性能ランクの項目の前後が出る。
- Git の扱いは衣装トグル・体型調整と同じ。
- 揺れ方は撮影では分からない。適用後、Gesture Manager（Play モード）で髪やスカートを揺らして確かめてもらう（`vrc-verify`）。

## 5. 元に戻す

```powershell
python -B $pb remove @a
python -B $pb remove @a --approved-preview '<値>'
```

apply が `.dsh/physbones/<名前>.json` に記録した分（変える前の値、足したコライダーとその登録）だけを戻す。
戻した値が prefab と同じなら、シーンのオーバーライドも外す。`python -B $pb recipes` でレシピと適用先のシーンを一覧にできる。
