---
name: vrc-blender-model
description: Blender をバックグラウンドで動かして 3D モデルを作る・合わせる手順。簡単な形（リボン、輪、角、帽子のような形）をレシピから作る、別アバター用（非対応）の衣装をアバターの骨格に合わせて貫通を押し出す。結果は FBX として Assets/DSH/Models に書き、vrc-accessory で付ける。小物の作成、非対応衣装の着せ替え、FBX の中身の確認を頼まれたときに読む。
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

`<pkg>` はパッケージのルート（Claude Code では `${CLAUDE_PLUGIN_ROOT}`）。

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

アバターの FBX（体のメッシュ名とボーン名）も同じように調べる。FBX の場所は `vrc-asset-read` の `refs` や、
アバターの prefab が参照するモデルから探す。

## 2a. 簡単な形を作る（kind: make）

```json
{
  "name": "Ribbon",
  "kind": "make",
  "parts": [
    {"shape": "sphere", "size": [0.03, 0.03, 0.03], "position": [0, 0, 0], "color": "#e05a7a"},
    {"shape": "cone", "size": [0.06, 0.05, 0.02], "position": [-0.035, 0, 0], "rotation": [0, 0, 90], "color": "#e05a7a"},
    {"shape": "cone", "size": [0.06, 0.05, 0.02], "position": [0.035, 0, 0], "rotation": [0, 0, -90], "color": "#e05a7a"}
  ]
}
```

| 項目 | 内容 |
|---|---|
| `shape` | `cube`、`sphere`、`cylinder`、`cone`、`torus` |
| `size` | 外形の大きさ（幅 x、高さ y、奥行き z、メートル） |
| `position` / `rotation` | 原点からの位置と回転（x 右、y 上、z 前。Unity と同じ向き） |
| `color` | `#RRGGBB`。Unity では Standard のマテリアルになる（lilToon にしたければ Unity で差し替える） |
| `segments` / `bevel` / `smooth` | 分割数（既定 32）、角の丸め（cube と cylinder、メートル）、スムーズ表示 |
| `thickness` | torus の輪の太さ（外径に対する割合、既定 0.2）。`topRatio` は cone の上面の半径の割合 |
| `join` | 全部を 1 つのメッシュにまとめる（既定 true） |

原点が付けるボーンの位置になる。付けるときは vrc-accessory の `mode: bone`、`origin: bone` を使い、
`position` で頭の上などへずらす。

## 2b. 非対応の衣装を合わせる（kind: fit）

```json
{
  "name": "Hoodie_Fit",
  "kind": "fit",
  "outfit": "Assets/Booth/Hoodie/FBX/Hoodie_ForOtherAvatar.fbx",
  "avatar": "Assets/Amatousagi/Salt/FBX/Salt.fbx",
  "body": "Body",
  "weights": "keep",
  "push": 0.002,
  "boneMap": {"J_Bip_C_UpperChest": "Chest"},
  "exclude": [],
  "scale": 1,
  "offset": [0, 0, 0]
}
```

処理の順番:
1. 衣装のボーンをアバターのボーンに対応づける（`boneMap` → 同じ名前 → Humanoid の綴りの違い。`Upperarm.L` と `Left_UpperArm` など）。
2. 対応したボーンの付け根と向きをアバターに合わせ、衣装を変形する（シェイプキーも一緒に変形する）。長さの違いに合わせて拡大縮小もする（`scaleBones`、既定 true、0.5〜2 倍）。
3. その姿勢を新しい基本姿勢にし、対応したボーンの名前をアバターに合わせる（`weights: keep`）。
4. 体（`body`、省略時は一番大きいメッシュ）の内側に入った頂点を、表面から `push`（既定 0.002m）外へ押し出す。

| 項目 | 内容 |
|---|---|
| `weights` | `keep`: 衣装のウェイトと揺れもの用のボーンを残す。`transfer`: 体からウェイトを写し、アバターの骨組みに付け替える（衣装のリグが壊れている・無いとき。スカートの揺れものボーンは無くなる） |
| `push` | 押し出す距離（0〜0.02m、0 で押し出さない） |
| `exclude` | 書き出さない衣装のメッシュ名（付属の素体など）。`inspect` に出る名前で書く |
| `scale` / `offset` | 一番上の対応ボーンにかける拡大（0.5〜2）とずらし（x 右、y 上、z 前、メートル）。髪や帽子のように Head だけで対応するものは、頭の大きさの違いを骨格から読めないので、これで合わせる |

- build の結果の `verticesInsideBody` に、メッシュごとの「体の内側にある頂点数」が、骨格を合わせた直後（`afterFit`）と押し出し後（`afterPush`）で出る。`afterPush` が大きく残るなら、`push` を少し上げるか、Unity の `vrc-shape-adjust` の `remove` で体側を消す。
- 髪は内側の層が頭に近いので、`body` には頭のメッシュ（顔の付いたメッシュ）を指定する。
- `unmatchedOutfitBones` は対応しなかったボーン（揺れもの用などは対応しなくてよい）。腕や脚の主なボーンが入っていたら `boneMap` で補う。
- 付けるときは vrc-accessory の `mode: armature` を使う（Head から始まる髪・帽子は `mode: bone`、`bone: Head`）。
  書き出した FBX のマテリアルは Unity の標準になるので、vrc-accessory の `materialsFrom` に元の衣装・髪の prefab を指定する。

## 3. build する

```powershell
python -B $model build --project '<project>' --model Hoodie_Fit
python -B $model list --project '<project>'
```

- 結果の `preview`（正面と横の画像、衣装はオレンジ、体はグレー。make では指定した色）で、大きくずれていないかを先に見る。最終的な見た目は vrc-accessory の撮影で確かめる。
- 書き出し先の FBX を手で変えていたら build は止まる（上書きしない）。`list` の `fbx` が `current` / `stale`（レシピか元ファイルが変わった）/ `edited` / `missing` を示す。
- 作り直したら、Unity で付けた小物はそのまま新しい FBX を使う（レシピは同じ）。撮影で確かめる。

## 注意

- 自動で合わせられるのは「骨格の位置と向き」と「体からの押し出し」まで。デザインの違い（丈、袖の太さ、体型差が大きい部分）は Blender での手作業が要ることを、ユーザーに伝える。
- 衣装・アバターの規約で、他アバターへの改変・流用が許されているかをユーザーに確認してもらう。
- 書き出した FBX は Unity で `Generic` のモデルとして取り込まれる。Humanoid への変更は不要（MA が統合する）。
