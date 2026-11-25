---
name: vrc-polygon
description: Meshia でビルド時にポリゴン数（三角形数）を減らす。アバター全体の目標か、メッシュごとの割合を決め、顔と小さなメッシュは残す。FBX は変えない。ポリゴン削減、三角形数を減らして性能ランクを上げたいと頼まれたら読む。
---

# ポリゴン削減

```
読む（メッシュごとの三角形数、顔のメッシュ、ランク）
 → レシピを書いて確認
 → 撮影（ビルド後の前後比較）
 → 適用（preview → 確認 → apply、SDK 検証で削減後の三角形数）
```

FBX とメッシュのアセットは変えない。各メッシュに Meshia Mesh Simplifier（NDMF）を付け、アップロードのビルドで
減らしたコピーが使われる。レシピは `Assets/DSH/Polygons/<名前>/recipe.json` に置く。
**Meshia**（Meshia Mesh Simplification、`com.ramtype0.meshia.mesh-simplification`）が要る。
入っていないときは、VCC/ALCOM でリポジトリ `https://ramtype0.github.io/VpmRepository/` を足して入れてもらう（DSH は入れない）。

まず `vrc-perf-budget` の考え方に沿う。三角形数で決まっているランクにだけ効く。Skinned Mesh やマテリアル数で
決まっているときは、Avatar Optimizer の統合が先（`vrc-perf-budget` §3）。服の下で見えない体は削減より
`vrc-shape-adjust` の削除が良い（見た目が変わらない）。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$pg = '<pkg>\tools\unity_polygon.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $pg read --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
```

- `unity.renderers`：メッシュのパス、三角形数（多い順）、`face`（Lip Sync のメッシュ）、`blendShapes`、すでにある Meshia の目標。
- `unity.meshia`：Meshia が入っているか。
- `rank.counts`：シーンのアバター（ビルド前）の PC / Mobile のランクと、それを決めている項目（`limitedBy`）。

## 2. レシピを書く

```json
{
  "name": "Light",
  "total": 69000,
  "keep": ["Body"],
  "renderers": [{"path": "Hair_Back", "ratio": 0.6}]
}
```

| 項目 | 内容 |
|---|---|
| `total` | アバター全体の三角形数の目標。名前を挙げたメッシュ、`keep`、顔、小さいメッシュを除いた残りを、同じ割合で減らす |
| `renderers[]` | メッシュごとの指定。`ratio`（0.05〜1、元の何割にするか）か `triangles`（三角形数）のどちらか |
| `keep` | 減らさないメッシュ |
| `keepFace` | 顔（Lip Sync のメッシュ）を減らさない（既定 true）。表情やリップシンクの崩れを避ける |
| `smallest` | `total` で、これより三角形の少ないメッシュは減らさない（既定 1000。目・歯・小物） |
| `preserveBorders` | 新しく付ける Meshia で、メッシュの縁（服の裾、髪の先）を保つ |

- 目安：PC の Good は 70,000、Excellent は 32,000。Mobile の Medium は 15,000（`vrc-perf-budget` §1）。
- 残りを 1 割未満に減らすことになるレシピは止まる。目標を上げるか、`keep` を見直す。
- 元の半分以下にすると、髪の房や指、服のしわが崩れやすい。顔に近い髪は割合を高めに（0.7 以上）する。

## 3. 撮影して確認する（シーンは保存しない）

```powershell
python -B $pg capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Light
```

上が元、下がレシピ。どちらも SDK のビルドを通すので、Meshia が実際に減らした形が出る。`trianglesAfterBuild` に
ビルド後の三角形数。崩れている部分があれば、その `renderers` の割合を上げるか `keep` に入れる。

## 4. 適用する・外す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Light')
python -B $pg preview @a --verify-sdk
python -B $pg apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $pg remove @a                                  # 戻す内容だけを返す
python -B $pg remove @a --approved-preview '<値>'
```

- preview の `summary` と `plannedPaths` を伝え、明示的な確認を得てから apply する。Git の扱いは衣装トグルと同じ。
- apply の `unity.targets` に、メッシュごとの前後の三角形数が出る。`unity.sdkVerification.renderers` にビルド後の三角形数、
  `rank."sdkVerification.countsAfterBuild"` にビルド後のランク。Avatar Optimizer がメッシュを統合したときは
  メッシュごとの数が取れず `inconclusive` になる（全体の数は `countsAfterBuild` で見る）。
- レシピを書き換えて apply すると、目標を付け直す。レシピから外したメッシュは元に戻る。
- remove は DSH が付けた Meshia を外し、変えた目標を元の値に戻す。レシピのファイルは残る。
- 最終のランクは、アップロード前に SDK の Builder で確かめてもらう。
