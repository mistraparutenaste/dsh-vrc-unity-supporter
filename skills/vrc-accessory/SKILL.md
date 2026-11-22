---
name: vrc-accessory
description: 既存の prefab や FBX（帽子・リボン・髪・小物、アバター用の衣装、Blender で作った・合わせたモデル）をアバターに付ける手順。ボーンに付ける（MA Bone Proxy）か、アーマチュアを統合する（MA Setup Outfit）かを選び、メニューで出し入れでき、元の髪などを隠せる。小物・髪の追加、付け替え、取り外しを頼まれたときに読む。
---

# 小物・髪・衣装を付ける

```
探す（候補とアバターのボーンを一覧）
 → レシピを書いて確認
 → 撮影して位置を調整（必要なら何度でも）
 → 適用（preview → 確認 → apply、SDK 検証）
```

付ける prefab / FBX 自体と、アバターの元のオブジェクトは変えない。
アバター直下に `DSH Accessory <名前>` を作り、その下に置く。メニューのトグルもそこに付く。
レシピは `Assets/DSH/Accessories/<名前>/recipe.json` に置く（DSH が管理するフォルダ）。

`<pkg>` はパッケージのルート（Claude Code では `${CLAUDE_PLUGIN_ROOT}`）。

```powershell
$acc = '<pkg>\tools\unity_accessory.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。Modular Avatar が必要（トグルを使うなら VRCFury も）。

## 1. 探す（ファイルは変えない）

```powershell
python -B $acc candidates --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --filter 'Hat' --prepare
```

- `unity.assets[]`: `--filter` に合う prefab / モデル（最大 60 件）。`kind` が `armature` なら Hips を含む骨組み付き（衣装など）、`rigid` ならそれ以外（帽子、髪、小物）。
- `unity.bones`: アバターにある Humanoid ボーン名（`Head`、`Chest`、`LeftHand` など）。
- `unity.attached`: すでに付いている DSH の小物。

## 2. レシピを書く

```json
{
  "name": "WolfHair",
  "asset": "Assets/Booth/WolfHair/Salt_WolfHair.prefab",
  "mode": "bone",
  "bone": "Head",
  "origin": "auto",
  "position": [0, 0, 0],
  "rotation": [0, 0, 0],
  "scale": 1,
  "menu": "Accessory/WolfHair",
  "hide": ["Hair"],
  "materialsFrom": "",
  "defaultOn": true
}
```

| 項目 | 内容 |
|---|---|
| `asset` | 付ける `.prefab` / `.fbx`（`Assets/` からのパス）。アバター自体は付けられない |
| `mode` | `bone`: 1 つのボーンに付ける（MA Bone Proxy）。`armature`: 骨組みをアバターに統合する（MA Setup Outfit）。`auto`（既定）は `kind` で決める |
| `bone` | `bone` モードで付けるボーン（Humanoid 名）。既定 `Head` |
| `origin` | `avatar`: アセットの元の位置のまま（そのアバター用に作られた髪や小物）。`bone`: アセットの原点をボーンの位置に置く（汎用の帽子や Blender で作った形）。`auto`（既定）は、メッシュがボーンから 0.5m 以内にあれば `avatar` |
| `position` / `rotation` / `scale` | 位置の微調整。アバターの向きで x 右、y 上、z 前（メートル・度）。回転と拡大はボーンを中心にかかる |
| `menu` | メニューのパス（VRCFury が必要）。空ならトグルなしで常に表示 |
| `hide` | 小物を付けている間だけ隠す、アバターのオブジェクト（アバターからのパス）。髪の差し替えで元の髪を隠すときなど。`menu` があればトグルと一緒に切り替わる。`menu` が空なら常に着る扱いで、シーン上でオフにする（取り外すとオンに戻る） |
| `materialsFrom` | 同じ名前のメッシュのマテリアルを写す元の prefab / FBX（マテリアルやシェーダーが欠けていればエラーで止まる。パッケージを丸ごと入れ直してもらう）。Blender で合わせた FBX は Unity の標準マテリアルで取り込まれるので、元の衣装・髪の prefab を指定する（シーン上の上書きとして保存。FBX は変えない） |
| `defaultOn` | メニューの初期状態（既定 true）。トグルは保存される（ワールドを移っても残る） |

- アバター専用の髪・小物は、たいてい `mode: bone`、`origin: auto` のままでよい（元の位置に付く）。
- 衣装（Hips から骨組みがある）は `mode: armature`。ボーン名がアバターと合っている必要がある（合わない衣装は `vrc-blender-model` で合わせてから付ける）。
- 別アバター用の髪や帽子（骨組みが Head から始まるもの）を `vrc-blender-model` で合わせた FBX は、`mode: bone`、`bone: Head` で付ける（`origin: auto` で元の位置になる）。
- 元の髪を隠すオブジェクト名は、`unity_shape.py shapes --filter Hair` などで確かめる。
- 書いたら、付けるもの、付け方、メニュー名、隠すものをユーザーに伝えて確認を取る。

## 3. 撮影して位置を調整する（シーンは保存しない）

```powershell
python -B $acc capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe WolfHair --views front,left,face
```

上段が小物なし、下段がレシピどおりに付けた状態。既定では両方を **SDK でビルドしたコピー** で撮るので、
Bone Proxy と Merge Armature の結果が VRChat と同じように反映される（`unity.mode`、`unity.origin` に決まった付け方が出る）。
すでに適用済みの同じ名前の小物は、撮影のコピーではレシピの内容に置き換えて撮る。

- 浮き、めり込み、向きを見て、`position` / `rotation` / `scale` を少しずつ（1〜2cm、数度）直して撮り直す。
- 画像を読めない場合はパスを伝えてユーザーに見てもらう。

## 4. 適用する

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'WolfHair', '--verify-sdk')
python -B $acc preview @a
python -B $acc apply @a --approved-preview '<preview の値>'
```

- preview の `plannedPaths`（シーンと、`hide` を使うなら隠すためのクリップ）を伝え、明示的な確認を得てから apply する。
- 適用後に位置だけ直したいときは、レシピの `position` などを変えて preview / apply し直す（`unity.applied` に変わった点だけが出る）。付けるもの、付け方、メニューを変えるときは、いったん取り外してから付け直す。
- `unity.sdkVerification` に、ビルド後に付いたボーン（`attachedTo`）または統合された衣装のメッシュ数（`mergedRenderers`）、メニューの場所（`menuLocation`）が出る。
- Git の扱いは衣装トグル・色違いと同じ（チェックポイントが必要、DSH が保存したシーンはコミットなしで続けられる）。

## 5. 一覧と取り外し

```powershell
python -B $acc list --project '<project>'
python -B $acc remove --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe WolfHair
python -B $acc remove --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe WolfHair --approved-preview '<値>'
```

- `list` は Unity を使わない。レシピと、それを含む保存済みシーンが出る。
- `remove` は `--approved-preview` なしだと確認用の内容だけを返す。シーンから `DSH Accessory <名前>`（トグル込み）を消し、レシピのフォルダも消す（`--keep-files` で残す）。付けていた prefab / FBX 自体は残る。

## 注意

- 小物の三角形数とマテリアル数はそのまま増える。`unity.triangles` と `vrc-perf-budget` で性能ランクへの影響を確かめる。
- PhysBone を持つ髪は、そのまま動く。付けた後の揺れは Build & Test で確認する。
- 配布物の規約（改変や他アバターへの流用の可否）は、ユーザーに確認してもらう。
