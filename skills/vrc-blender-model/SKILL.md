---
name: vrc-blender-model
description: Blender をバックグラウンドで使い、小物（リボン・角・カチューシャ・チョーカー・ボタンなど。頭や髪に沿わせ、揺れ用のボーン付き）を作る、または別アバター用の衣装・髪をアバターの骨格に合わせて FBX に書き出す。FBX の中身を調べるときにも読む。
---

# Blender でモデルを作る・合わせる

```
調べる（FBX の中身、ボーン名）
 → レシピを書いて確認
 → build（Blender で FBX を書き出し、プレビュー画像と貫通の数を見る）
 → vrc-accessory で付けて、Unity で撮影・適用
```

元の FBX / .blend は変えない。結果は `Assets/DSH/Models/<名前>/<名前>.fbx`（DSH が管理するフォルダ）。
Blender が必要（blender.org の無料版）。見つからないときは `DSH_BLENDER` に `blender.exe` のパスを設定する。
Unity を閉じる必要はない（開いていれば、書き出した FBX を Unity が取り込む）。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$model = '<pkg>\tools\blender_model.py'
```

## 1. 調べる（ファイルは変えない）

```powershell
python -B $model inspect 'Assets/Booth/Outfit/Outfit.fbx' --project '<project>'
```

- `meshes[]`: 名前、頂点数、三角形数、シェイプキー数、使うアーマチュア。
- `armatures[]`: ボーン数と、Humanoid として読めたボーン（`hips`、`left upperarm` など）。
- `sizeUnity`: 全体の大きさ（幅・高さ・奥行き、メートル）。
- `--shapes <メッシュ名>`（`--filter <文字>` で絞る）を付けると、そのメッシュのシェイプキー名が `shapeKeyNames` に出る。
  体型キー（`avatarShapes`、`followShapes`）や縮めるキーの名前を確かめるときに使う。

アバターの FBX（体のメッシュ名とボーン名）も同じように調べる。FBX の場所は `vrc-asset-read` の `refs` や、
アバターの prefab が参照するモデルから探す。

## 2a. 小物を作る（kind: make）

```json
{
  "name": "Bow",
  "kind": "make",
  "avatar": "Assets/Amatousagi/Salt/FBX/Salt.fbx",
  "bone": "Head",
  "snap": true,
  "toward": [0, 0, 1],
  "parts": [
    {"name": "Knot", "shape": "sphere", "size": [0.022, 0.028, 0.016], "position": [0, 0.07, -0.12], "color": "#d84a6e"},
    {"name": "Wing", "shape": "tube", "section": "flat", "width": 0.032, "depth": 0.002, "closed": true, "mirror": true,
     "points": [[0.006, 0.07, -0.116], [0.035, 0.074, -0.111], [0.064, 0.072, -0.115], [0.064, 0.066, -0.125],
                [0.035, 0.068, -0.129], [0.006, 0.07, -0.124]], "color": "#d84a6e"},
    {"name": "Tail", "shape": "tube", "section": "flat", "width": 0.02, "depth": 0.002, "taper": 0.85, "mirror": true, "sway": 4,
     "points": [[0.004, 0.064, -0.126], [0.016, 0.035, -0.128], [0.024, 0, -0.129], [0.032, -0.03, -0.128]], "color": "#d84a6e"}
  ]
}
```

座標は付けるボーン（`bone`、既定 Head）の位置が原点で、x 右、y 上、z 前（Unity と同じ向き、メートル）。
付けるときは vrc-accessory の `mode: bone`、`origin: bone`、`position: [0, 0, 0]` にする（ここでの位置がそのまま使われる）。
`avatar` が無いときも同じ座標で作れるが、表面への沿わせ込みと、アバターと並べたプレビューは無い。

部品（`parts[]`、最大 64）の形:

| `shape` | 内容と項目 |
|---|---|
| `cube` `sphere` `cylinder` `cone` `torus` | `size`（幅 x・高さ y・奥行き z の外形）、`bevel`（cube と cylinder の角の丸め）、`thickness`（torus の輪の太さ、外径に対する割合）、`topRatio`（cone の上面の半径の割合） |
| `tube` | `points`（2〜64 点）をなめらかに通る帯・紐。`section: round`（紐、`radius`）か `flat`（リボン、`width` と厚み `depth`）。`taper`（終わりの太さの割合。0 で尖る＝角）、`closed`（輪にする＝チョーカー、リボンの羽）、`face`（平らな面を向ける向き。既定 `[0, 0, 1]` で前後を向く）、`tilt`（帯を軸まわりにひねる角度） |
| `lathe` | `profile`（`[半径, 高さ]` を下から 2〜64 点）を上下の軸まわりに回した形（ボタン、ビーズ、鈴、カップ）。`caps: false` で上下を閉じない |
| `extrude` | `outline`（`[x, y]` の点の並び、3〜256 点）か `star` / `heart` / `circle` / `diamond` を、`depth` の厚みの板にする（`size` の x・y が外形。star は `corners` と `inner`）。`bevel` で縁を丸める |

全部の形に使える項目:

| 項目 | 内容 |
|---|---|
| `position` / `rotation` | 位置と回転（度）。tube は `points` にもかかる |
| `color` | `#RRGGBB`。色ごとに 1 つのマテリアルになる（Unity では Standard。lilToon にするなら Unity で差し替える） |
| `mirror` | 左右反対側にも作る（`<名前>_R` が右 = +x、`<名前>_L` が左） |
| `subdivide` | 0〜3。なめらかにする（三角形は 4 倍ずつ増える） |
| `segments` | 丸みの分割数（既定 32、3〜128）。三角形が多いときに下げる |
| `smooth` | `false` で角ばった表示にする（既定は形に合わせ、縁は立てたまま丸く見せる） |
| `conform` | `snap`: 部品をまっすぐ動かして、アバターの外側の表面（髪の上など）に当てる。`surface`（tube だけ）: 通る点を表面に載せ、平らな面を表面に沿わせる（カチューシャ、チョーカー、頭に沿う紐）。`avatar` が必要 |
| `toward` | `snap` で動かす向き（例 `[0, 0, 1]` は前へ）。省略時は、付けるボーンのまわり（頭なら頭の中心）へ向かう |
| `sway` | tube だけ。揺れ用のボーン数（1〜8、`true` で 4）。根元は動かず、先へ行くほど揺れる。輪（`closed`）には付けられない |

レシピ全体の項目:

| 項目 | 内容 |
|---|---|
| `avatar` | アバターの FBX。あると表面に沿わせられ、プレビューにアバターが写る（正面・横・斜め上） |
| `bone` | 付けるボーン（Humanoid 名。`Head`、`Neck`、`Chest`、`LeftHand` など）。vrc-accessory の `bone` と同じにする |
| `surfaces` | 沿わせる表面にするアバターのメッシュ名。省略時は、そのボーンのまわりの体・髪・耳（名前に cloth、costume、hood、shoe、sock などが入る服は除く）。結果の `avatar.surfaces` で確かめる |
| `avatarShapes` | アバターの体型キーの値（0〜100）。シーンで変えているなら合わせる |
| `snap` / `toward` | `true` で全体をひとつとして動かし、表面に当てる（リボンの結び目・羽・端がばらばらにならない） |
| `gap` | 表面から離す距離（既定 0.001m、0〜0.02） |
| `push` | 既定 true。表面のすぐ下（2cm 以内）に入った頂点を外へ押し出す |
| `join` | 全部を 1 つのメッシュにまとめる（既定 true） |

- build の結果:
  - `parts[]`: 部品ごとの `gapMm`（表面までの一番近い距離）、`insideVertices`（表面のすぐ下にある頂点数）、`snap`（動いた距離 `movedMm` と向き `offset`）、`sway`。
  - `push`: 押し出しの前後で表面の下にあった頂点数。`warnings` に残りが出たら `gap` を上げるか、部品の位置を直す。
  - `quality`: 三角形数、開いた縁（`openEdges`）、3 枚以上の面が重なる縁（`nonManifoldEdges`）、UV の有無、マテリアル数。`warnings` に三角形が多い（1 万超）・マテリアルが多い（4 超）などが出る。
  - `sway`: 揺れ用ボーンの根元の名前（`Tail_R_Sway` など）。vrc-accessory の `physBones` に書く。
- 髪や耳は薄い面なので、表面の「下」は表面のすぐ近く（2cm）しか判定しない。めり込みは撮影（vrc-accessory の capture）で確かめる。
- プレビューで、浮き・めり込み・羽の向きを見て、`position` や `points` を 2〜5mm ずつ直す。羽が細い線に見えるときは、輪の点を前後（z）に並べて平らにする（上の例）。
- 帯の向きが思った向きでないときは `face` か `tilt` を変える。
- UV は自動で展開する（tube は長さ方向にそろう）。テクスチャを描くなら Unity で lilToon などに差し替える。

## 2b. 非対応の衣装を合わせる（kind: fit）

```json
{
  "name": "Hoodie_Fit",
  "kind": "fit",
  "outfit": "Assets/Booth/Hoodie/FBX/Hoodie_ForOtherAvatar.fbx",
  "avatar": "Assets/Amatousagi/Salt/FBX/Salt.fbx",
  "source": "Assets/Booth/OtherAvatar/FBX/OtherAvatar.fbx",
  "body": "",
  "avatarShapes": {"Breasts_big": 40},
  "followShapes": ["Waist_slim"],
  "weights": "keep",
  "push": 0.002,
  "boneMap": {"J_Bip_C_UpperChest": "Chest"},
  "exclude": [],
  "scale": "auto",
  "offset": [0, 0, 0]
}
```

処理の順番:
1. 衣装のボーンをアバターのボーンに対応づける（`boneMap` → 同じ名前 → Humanoid の綴りの違い。`Upperarm.L` と `Left_UpperArm` など）。
2. 対応したボーンの付け根と向きをアバターに合わせ、衣装を変形する（シェイプキーも一緒に変形する）。大きさも合わせる（`scaleBones`、既定 true）:
   衣装全体に、アバターと衣装の「腰〜頭の高さ」と「肩幅」の比の平均をかける（結果の `bodyScale`）。
   腰・背骨・胸・首・肩はこの大きさのまま。腕・脚だけは自分の長さの比に合わせる（全体の 0.8〜1.25 倍の範囲。結果の `boneScales`）。
   対応しないボーン（スカート、袖、リボン）は親の大きさを受け継ぐ。
3. `source`（衣装が作られた元のアバター）があれば、その体も同じように骨格を合わせ、元の体の表面からアバターの体の表面までの差（胸、腰、腕の太さなど）を衣装に写す。
4. その姿勢を新しい基本姿勢にし、対応したボーンの名前をアバターに合わせる（`weights: keep`）。
5. 体（`body`）の内側に入った頂点を、表面から `push`（既定 0.002m）外へ押し出す。
6. `followShapes` の体型キーを、同じ名前で衣装のメッシュにも作る（体の動きを近くの衣装の頂点に写す）。

| 項目 | 内容 |
|---|---|
| `weights` | `keep`: 衣装のウェイトと揺れもの用のボーンを残す。`transfer`: 体からウェイトを写し、アバターの骨組みに付け替える（衣装のリグが壊れている・無いとき。スカートの揺れものボーンは無くなる） |
| `source` / `sourceBody` | 衣装が作られた元のアバターの FBX と、その体のメッシュ名（省略時は自動）。あると体型差まで合う。無ければ骨格合わせと押し出しだけ |
| `body` | アバターの体のメッシュ名。省略時は、衣装が使うボーンを一番広く覆うメッシュ（全身の服なら体、髪なら頭） |
| `avatarShapes` | アバターの体型キーの値（0〜100、Unity の表示と同じ）。シーンで体型を変えているなら、その値に合わせて作る。`sourceShapes` は元のアバター側 |
| `followShapes` | 衣装にも作る体型キー（`Breasts_big`、`Waist_slim` など）。Unity で `vrc-shape-adjust` の `sync` を付けると体型に追従する。縮めるキー（`*_OFF`）や顔のキーは入れない。`avatarShapes` と同じキーは入れない（二重に動く） |
| `push` | 押し出す距離（0〜0.02m、0 で押し出さない） |
| `exclude` | 書き出さない衣装のメッシュ名（付属の素体など）。`inspect` に出る名前で書く |
| `scale` / `offset` | 一番上の対応ボーンにかける拡大とずらし（x 右、y 上、z 前、メートル）。`scale` は `"auto"`（既定）か 0.5〜2。髪や帽子のように Head だけで対応するものは、頭の大きさを骨格から読めないので、`"auto"` なら頭の中心を基準に、頭に埋まる頂点の 8 割が外に出る大きさを探す（結果の `headScale`。`insideAt1` は 1 倍で頭に埋まる頂点数）。全身の衣装では `bodyScale` が使われ、`"auto"` は何もしない。数値を書くとその倍率に固定する |

- build の結果の `verticesInsideBody` に、メッシュごとの「体の内側にある頂点数」が、骨格を合わせた直後（`afterFit`）と押し出し後（`afterPush`）で出る。`afterPush` が大きく残るなら、`push` を少し上げるか、Unity の `vrc-shape-adjust` の `remove` で体側を消す。
- 髪は `body` を省略すると頭のメッシュが選ばれる（`build` の結果の `body` で確かめる）。
- `unmatchedHumanoidBones` は対応しなかった主なボーン（腕・脚・背骨など）。入っていたら `boneMap` で補う（つま先は無くてもよい）。揺れもの用などの数は `unmatchedOtherBones`。
- `bodyScale` の `height`（腰〜頭）と `width`（肩幅）の比が大きく違う（0.2 以上）ときは、プロポーションの違うアバター。撮影で丈と幅を確かめる。
- 撮影で衣装が風船のように膨らむ・縮むときは、`boneScales` で大きく外れたボーンを探し、`boneMap` の対応を確かめる。
- `surfaceFit` は `source` を使ったときの結果。`matchedPoints` が半分未満なら、元のアバターか `sourceBody` が違う。`meanMoveMm` は体型差で動かした平均の距離。
- `followedShapes` は、メッシュごとに作った体型キー（ほとんど動かないメッシュには作らない）。
- 付けるときは vrc-accessory の `mode: armature` を使う（Head から始まる髪・帽子は `mode: bone`、`bone: Head`）。
  書き出した FBX のマテリアルは Unity の標準になるので、vrc-accessory の `materialsFrom` に元の衣装・髪の prefab を指定する。

## 3. build する

```powershell
python -B $model build --project '<project>' --model Hoodie_Fit
python -B $model list --project '<project>'
```

- 結果の `preview`（正面と横の画像、衣装はオレンジ、体はグレー。make では指定した色で、`avatar` があればアバターと並べ、斜め上からの画像も付く）で、大きくずれていないかを先に見る。最終的な見た目は vrc-accessory の撮影で確かめる。
- 書き出し先の FBX を手で変えていたら build は止まる（上書きしない）。`list` の `fbx` が `current` / `stale`（レシピか元ファイルが変わった）/ `edited` / `missing` を示す。
- 作り直したら、Unity で付けた小物はそのまま新しい FBX を使う（レシピは同じ）。撮影で確かめる。

## 注意

- 着せる一連の流れ（付ける、追従、隠れる体の削除まで）は `vrc-outfit-fit` を読む。
- 自動で合わせられるのは「骨格の位置と向き」「元のアバターとの体型差（`source` があるとき）」「体からの押し出し」「体型キーの追従」まで。デザインの違い（丈、袖の太さ、体型差が大きい部分）は Blender での手作業が要ることを、ユーザーに伝える。
- 衣装・アバターの規約で、他アバターへの改変・流用が許されているかをユーザーに確認してもらう。
- 書き出した FBX は Unity で `Generic` のモデルとして取り込まれる。Humanoid への変更は不要（MA が統合する）。
