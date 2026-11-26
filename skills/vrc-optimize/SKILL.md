---
name: vrc-optimize
description: ビルド時の軽量化。AAO の Trace and Optimize（メッシュ統合、不要ボーン削除）と TexTransTool（テクスチャ縮小、マテリアル統合）をファイルを変えずに付ける。軽量化やテクスチャ削減を頼まれたら読む。
---

# 軽量化（ビルド時、非破壊）

```
読む（マテリアルとテクスチャ、メッシュ、ボーン、ランク、ツールの有無）
 → レシピを書いて確認
 → try（ビルドした前後の数を比べる、保存しない）／ capture（前後の画像）
 → 適用（preview → 確認 → apply --verify-sdk）
```

プロジェクトの FBX・マテリアル・テクスチャは変えない。シーンには部品だけを付け、アップロードのビルドで
軽くしたコピーが使われる。レシピは `Assets/DSH/Optimize/<名前>/recipe.json` に置く。

| 手段 | 使うツール | 下がる項目 |
|---|---|---|
| `traceAndOptimize` | **Avatar Optimizer**（AAO、`com.anatawa12.avatar-optimizer`）の Trace and Optimize をアバターのルートに付ける | Skinned Meshes、Bones、PhysBone、使われないオブジェクト・シェイプキー |
| `textures` | **TexTransTool**（TTT、`net.rs64.tex-trans-tool`）の AtlasTexture。マテリアルごとに指定の大きさへ縮める | Texture Memory |
| `atlas` | TTT の AtlasTexture。名前を挙げたマテリアルのテクスチャを 1 枚にまとめ、`merge` で 1 つのマテリアルにする | Material Slots、Texture Memory |

どちらも VCC/ALCOM で入れてもらう（DSH は入れない）。AAO は `https://vpm.anatawa12.com/vpm.json`、
TTT は `https://vpm.rs64.net/vpm.json` のリポジトリにある。使う手段のツールだけでよい。

まず `vrc-perf-budget` の考え方に沿い、ランクを決めている項目（`limitedBy`）に効く手段を選ぶ。三角形数なら `vrc-polygon`、
Quest 版は `vrc-quest`（Android ではテクスチャを VQT が縮める）。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$op = '<pkg>\tools\unity_optimize.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $op read --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
```

- `unity.materials[]`：マテリアル名、アセットのパス、シェーダー（`family` が lilToon / Poiyomi / other）、使っているメッシュ、
  `largest`（一番大きいテクスチャの辺）、`textures[]`（大きさ、形式、`mb`）、`sharesTexturesWith`（同じテクスチャを使う別のマテリアル）。
- `unity.renderers[]`：メッシュごとのマテリアル数、ボーン数、シェイプキー数。
- `unity.counts` と `rank.counts`：ビルド前の数とランク。`textureMemoryMB` は取り込み後の大きさ（形式・ミップマップ込み）で数える。
- `unity.aao`：AAO があるか、Trace and Optimize がもう付いているか、`options[]`（Inspector の表示名 `label`、保存名 `path`、既定値 `value`）。
- `unity.ttt`：TTT があるか、すでにある TTT の部品、`supported`。`false` のときは `problems` に、この版の AtlasTexture の
  何が見つからなかったかが出る。その版では `textures` と `atlas` を使えないので、Unity で手で設定してもらうよう伝える。

## 2. レシピを書く

```json
{
  "name": "Light",
  "traceAndOptimize": true,
  "textures": {"size": 1024, "materials": ["*"], "exclude": ["Face"]},
  "atlas": [{"materials": ["Hoodie", "Pants", "Shoes"], "size": 2048, "merge": true}]
}
```

| 項目 | 内容 |
|---|---|
| `traceAndOptimize` | AAO の Trace and Optimize を付ける。既定の設定でメッシュの自動統合、使われないボーン・オブジェクト・シェイプキーの削除などを行う |
| `aaoOptions` | Trace and Optimize の設定を変える。`read` の `aao.options[].path` をキーに true / false（例 `{"<path>": false}`。名前は AAO の版で違うので、必ず read の値を使う）。ふつうは書かない |
| `textures.size` | テクスチャの長い辺の上限（256、512、1024、2048、4096） |
| `textures.materials` | 縮めるマテリアル（名前かアセットのパス）。`["*"]` で全部 |
| `textures.exclude` | 縮めないマテリアル（顔、目など） |
| `atlas[].materials` | 1 枚にまとめるマテリアル（2 つ以上）。`textures` と同じマテリアルを名前で重ねない |
| `atlas[].size` | まとめたテクスチャの辺（既定 2048） |
| `atlas[].merge` | まとめたマテリアルを 1 つにする（既定 true）。`false` はテクスチャだけまとめ、マテリアルの数は変えない |

- `textures` は、同じテクスチャを使うマテリアルを 1 つのアトラスにまとめる（同じ絵を二重に作らない）。
  テクスチャがすでに `size` 以下のマテリアルは触らない（`skipped`）。
- 目安：PC の Texture Memory は Good 75 MB、Excellent 40 MB。Material Slots は Good 8（`vrc-perf-budget` §1）。
- 顔・目は 1024 未満にするとぼやけて見えやすい。最初は `exclude` に入れる。
- `merge` は **同じシェーダー**（lilToon どうしなど）のマテリアルだけにする。設定の違うマテリアルをまとめると、
  まとめた先の設定（最初のマテリアル）に揃う。透過、輪郭線、エミッションの有無が違うものは別のグループにする。
- アニメーションやトグルでマテリアルを差し替えるメッシュ（色替え、DSH の色違いなど）は、`atlas` に入れない。
- AAO が統合できないメッシュ（シェイプキーをアニメーションで動かす顔など）は自動で残る。全部が 1 つになるとは限らない。

## 3. 試す（シーンは保存しない）

```powershell
python -B $op try --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Light
python -B $op capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Light
```

- `try`：レシピ無しとレシピ有りのコピーを SDK でビルドし、`unity.compare.changes` に前後の数
  （三角形、Skinned Meshes、Material Slots、Texture Memory、テクスチャの枚数、ボーン、PhysBone）、
  `rank."compare.before"` と `rank."compare.after"` にランク、`unity.groups` に作るアトラスの組を返す。
  `--recipe` を付けなければ、今のシーンのままのビルド後の数だけ（`built`）。
- `capture`：上が元、下がレシピ。どちらもビルドを通すので、縮めたテクスチャ・まとめたマテリアルの見た目が出る。
  ぼやけ・色の違い・透け方の違いがあれば、そのマテリアルを `exclude` に入れるか、`size` を上げるか、グループを分ける。
- AAO と TTT はグラフィックスが要るので、どちらも Unity をグラフィックス有りで起動する（数分かかる）。

「もっと軽く」は、目標（たとえば Texture Memory 75 MB 以下）を決めて `try` を繰り返し、届いた案を見せてから適用する（`vrc-auto-adjust`）。

## 4. 適用する・外す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Light')
python -B $op preview @a --verify-sdk
python -B $op apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $op remove @a                                  # 戻す内容だけを返す
python -B $op remove @a --approved-preview '<値>'
```

- preview の `summary` と `plannedPaths` を伝え、明示的な確認を得てから apply する。Git の扱いは衣装トグルと同じ。
- apply はアバターのルートに Trace and Optimize を、アバターの直下に `DSH Optimize <名前>` を作り、その子にアトラスごとの AtlasTexture を付ける。
- `--verify-sdk` は、DSH の部品を外したビルドとシーンのままのビルドを比べる。`unity.sdkVerification.changes` に前後、
  `rank."sdkVerification.countsAfterBuild"` にビルド後のランク。TTT が縮めも統合もしなかったときは失敗にする。
  Trace and Optimize だけで数が変わらないときは `inconclusive`（もう軽い、または AAO が動いていない）。
- すでにユーザーが付けた Trace and Optimize があるときは、それを使い、DSH は付けない（`aaoOptions` は書けない）。
- レシピを書き換えて apply すると、アトラスを作り直す。remove は DSH が付けた Trace and Optimize と `DSH Optimize <名前>` を外す。レシピのファイルは残る。
- 最終のランクは、アップロード前に SDK の Builder で確かめてもらう。
