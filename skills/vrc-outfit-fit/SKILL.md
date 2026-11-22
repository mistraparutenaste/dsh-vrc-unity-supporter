---
name: vrc-outfit-fit
description: 非対応衣装（別アバター用の服・髪）をアバターに着せる一連の手順。素材と元のアバターを調べ、Blender で骨格と体の表面に合わせ、体型シェイプキーを衣装にも作り、MA Setup Outfit で付け、体型に追従させて服の下の体を消し、撮影と SDK 検証まで進める。「この服を着せたい」「非対応衣装の着せ替え」「別アバター用の髪を使いたい」と頼まれたときに最初に読む。
---

# 非対応衣装を着せる（一連の流れ）

```
0. 規約と素材の確認
1. 調べる（衣装・元のアバター・着せるアバター・今の体型）
2. 合わせる（vrc-blender-model の fit。プレビューと数値を見る）
3. 付ける（vrc-accessory の armature。撮影して直す → 適用）
4. 体型に追従させ、服の下の体を消す（vrc-shape-adjust。撮影 → 適用）
5. 確認（vrc-verify）
```

各段の詳しい項目は、それぞれのスキルを読む。ここでは、つなぎ方と判断の基準を扱う。
元の FBX・prefab・アバターは変えない。作るのは `Assets/DSH/Models/<名前>`、`Assets/DSH/Accessories/<名前>`、
`Assets/DSH/Shapes/<名前>` のレシピと FBX、シーンの変更だけ。各段の適用前に、ユーザーの明示的な確認を取る。

```powershell
$model = '<pkg>\tools\blender_model.py'
$acc   = '<pkg>\tools\unity_accessory.py'
$shape = '<pkg>\tools\unity_shape.py'
```

## 0. 規約と素材の確認

- 衣装とアバターの規約で、他アバターへの改変・流用が許されているかをユーザーに確認してもらう。
- 揃えるもの（すべて `Assets/` の下にインポート済みであること）:

| 素材 | 用途 | 無いとき |
|---|---|---|
| 衣装の FBX | 合わせる元（`outfit`） | 必須 |
| 衣装の prefab | マテリアルと PhysBone を写す元（`materialsFrom`） | FBX のマテリアル（Unity の標準）で付く |
| **元のアバター**の FBX（衣装が作られた素体） | 体の表面の差を写す（`source`） | 骨格合わせと押し出しだけになる（体型差が大きいと浮きやめり込みが残る） |
| 着せるアバターの FBX | 合わせる先（`avatar`） | 必須（prefab が参照するモデル） |

衣装の配布物に素体が同梱されていることがある（`inspect` で体のメッシュがある FBX）。元のアバターを持っていない場合は、
その旨をユーザーに伝え、`source` なしで進める。

## 1. 調べる（ファイルは変えない）

```powershell
python -B $model inspect 'Assets/Booth/Coat/FBX/Coat.fbx' --project '<project>'
python -B $model inspect 'Assets/Booth/Selestia/SELESTIA.fbx' --project '<project>'
python -B $model inspect 'Assets/Amatousagi/Salt/FBX/Salt.fbx' --project '<project>'
python -B $shape shapes --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --filter 'Body' --prepare
```

- 衣装: メッシュ名（付属の素体があれば `exclude` に入れる）、`humanoid`（腕・脚・背骨が読めているか）。
- アバター: 体のメッシュ（`Body_base` など、全身に広がるもの）と、体型のシェイプキー（`Breasts_big`、`Waist_slim` など）。
- 今の体型: `shapes` で 0 以外の値が付いた体型キー。これを `avatarShapes` に入れると、その体型に合わせて作る。

## 2. 合わせる

`Assets/DSH/Models/Coat_Fit/recipe.json`:

```json
{
  "name": "Coat_Fit",
  "kind": "fit",
  "outfit": "Assets/Booth/Coat/FBX/Coat.fbx",
  "avatar": "Assets/Amatousagi/Salt/FBX/Salt.fbx",
  "source": "Assets/Booth/Selestia/SELESTIA.fbx",
  "avatarShapes": {"Breasts_big": 40},
  "followShapes": ["Breasts_small", "Waist_slim"],
  "exclude": []
}
```

```powershell
python -B $model build --project '<project>' --model Coat_Fit
```

見るところ:

| 結果 | 基準 | 直し方 |
|---|---|---|
| `preview`（正面・横、衣装はオレンジ） | 肩・袖・裾・靴が体の位置にある | 大きくずれるなら `boneMap` |
| `unmatchedHumanoidBones` | 空（つま先程度なら可） | `boneMap` で補う |
| `surfaceFit.matchedPoints` | 半分以上 | 少ないなら `source` が違う素体、または `sourceBody` を指定 |
| `verticesInsideBody.afterPush` | 各メッシュ数十以下 | `push` を少し上げる、または 4 で体側を消す |
| `followedShapes` | 体型を変えたいキーが衣装のメッシュに付いた | キーの名前を `inspect` の体のキー名に合わせる |

- `avatarShapes` は「今の体型」を基本形として作る。後で値を変えたいキーは `followShapes` に入れる（同じキーを両方に入れない。二重に動く）。
- 縮めるキー（`*_OFF`）や顔のキーは `followShapes` に入れない（衣装まで縮む）。
- 髪・帽子（骨組みが Head から始まる）も同じ手順でよい。`source` があれば頭の形の差も写る。無ければ `scale` / `offset` で合わせる。

## 3. 付ける

`Assets/DSH/Accessories/Coat/recipe.json`:

```json
{
  "name": "Coat",
  "asset": "Assets/DSH/Models/Coat_Fit/Coat_Fit.fbx",
  "mode": "armature",
  "menu": "Outfit/Coat",
  "hide": ["Costume_Hoodie", "Costume_Shorts"],
  "materialsFrom": "Assets/Booth/Coat/Coat.prefab"
}
```

- `hide` には、新しい衣装と重なるアバターの元の服を入れる（名前は `shapes --filter Costume` などで確かめる）。
- `vrc-accessory` の 3〜4 のとおり `capture` で前後を見て、`preview` → 確認 → `apply --verify-sdk`。
- 撮影で大きくずれていたら、2 のレシピを直して build し直す（付けた小物は新しい FBX をそのまま使う）。

## 4. 体型に追従させ、服の下の体を消す

3 を適用した後で、衣装のメッシュのパスを調べる（`DSH Accessory Coat/...` の下にある）:

```powershell
python -B $shape shapes --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --filter 'DSH Accessory Coat'
```

`Assets/DSH/Shapes/Coat/recipe.json`:

```json
{
  "name": "Coat",
  "sync": [
    {"renderer": "DSH Accessory Coat/Coat_Fit/Outer", "source": "Body_base", "shapes": ["Breasts_small", "Waist_slim"]}
  ],
  "remove": [
    {"renderer": "Body_base", "shapes": ["Chest_1_OFF", "Spine_1_OFF", "UpperArm_OFF"]}
  ]
}
```

- `sync` には 2 の `followedShapes` に出たメッシュとキーを入れる（衣装側は同じ名前で作られている）。
- `remove` には、この衣装で完全に隠れる部位の縮めるキーだけを入れる。メニューで衣装を外せるなら、
  外したときに体に穴が開くので、ユーザーに伝えて判断してもらう（常に着るなら問題ない）。
- `vrc-shape-adjust` の 3〜4 のとおり撮影 → `preview` → 確認 → `apply --verify-sdk`。

## 5. 確認

`vrc-verify` を読む。首元・袖口・裾・股・脇の貫通、揺れもの（スカート、紐）の動き、三角形数（`vrc-perf-budget`）を見る。
動かしたときの貫通は Gesture Manager か Build & Test で確かめてもらう。

## 伝えること

- 自動で合わせられるのは、骨格（位置・向き・長さ）、体の表面の差（`source` があるとき）、押し出し、体型キーの追従まで。
  デザインの違い（丈、袖の太さ、大きく違う体型の部分）や、動いたときの貫通は手直しが要ることがある。
- やり直しは、各レシピを直して同じ段からやり直す。シーンの変更は Git で戻せる。
