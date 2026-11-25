---
name: vrc-quest
description: VRCQuestTools で Quest（Android）版を同じシーンから作る。モバイル用シェーダーに変え、選んだ揺れ物を Android 版だけで外す。PC 版は変わらない。Quest 対応、Android 版、モバイルのランクを頼まれたら読む。
---

# Quest（Android）版

```
読む（マテリアルとシェーダー、PhysBone・コンタクト、Android の準備）
 → 試す（Android としてビルドしたコピーのランク。保存しない）
 → レシピを書く → もう一度試す
 → 適用（preview → 確認 → apply、SDK 検証）
 → ユーザーが Android に切り替えてアップロード
```

アバターを複製しない。アバターのルートに **VQT Avatar Converter Settings**、外す揺れ物のオブジェクトに
**VQT Platform Component Remover** を付ける。VRCQuestTools（NDMF）は Android のビルドのときだけ、
マテリアルを VRChat/Mobile のシェーダーに変え、テクスチャを小さくし、指定した PhysBone・コライダー・コンタクトを外す。
PC のビルドは変わらない。レシピは `Assets/DSH/Quest/<名前>/recipe.json` に置く。

**VRCQuestTools**（`com.github.kurotu.vrc-quest-tools`、2.x 以降）が要る。入っていないときは、VCC/ALCOM で
リポジトリ `https://kurotu.github.io/vpm-repos/vpm.json` を足して入れてもらう（DSH は入れない）。
アップロードには Unity Hub で **Android Build Support** のモジュールが要る（`read` の `androidModule`）。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$qt = '<pkg>\tools\unity_quest.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む・試す（ファイルは変えない）

```powershell
$s = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar')
python -B $qt read @s --prepare
python -B $qt try @s                       # 今のシーンを Android としてビルドしたら（VQT 未設定なら変換されない）
python -B $qt try @s --recipe Quest        # レシピを付けたら
```

- `read`：`unity.materials`（シェーダーと、すでにモバイル用か）、`unity.dynamics`（PhysBone・コライダー・コンタクトのある
  オブジェクトと、動くボーンの数）、`vrcQuestTools`、`androidModule`、`converterSettings`（VQT がすでに付いているか）。
- `try`：コピーに VQT Platform Target Settings（Android）を付けて SDK のビルドを通し、変換後を数える。Unity は PC のまま。
  VQT はテクスチャを GPU で作るので、Unity をグラフィックありで起動する（数分かかる）。
  `mobileRank`（Mobile のランクと `limitedBy`）、`unity.android.shaders`、`notMobile`（モバイル用にならなかったマテリアル）、
  `unity.android.dynamics`（残る揺れ物）。`textureMemoryMB` は圧縮前の見積もりで高めに出る。
- Mobile は **Medium 以内**を目指す。Poor 以下は、ほかの人には代わりのアバター（フォールバック）で見える（`vrc-perf-budget` §1 Mobile）。

## 2. レシピを書く

```json
{
  "name": "Quest",
  "shader": "toonStandard",
  "textureSize": 1024,
  "removeOnAndroid": ["Armature/Hips/Skirt_Root", "Armature/Hips/Spine/Chest/Breast_Root"]
}
```

| 項目 | 内容 |
|---|---|
| `shader` | `toonStandard`（VRChat Toon Standard。法線・リム・マットキャップを残す。既定）か `toonLit`（最も軽い） |
| `textureSize` | Android のテクスチャの最大の辺（256、512、1024、2048。既定 1024） |
| `brightness` | `toonLit` のときのメインテクスチャの明るさ（0〜1、既定 0.83） |
| `removeOnAndroid` | Android 版で PhysBone・コライダー・コンタクトを外すオブジェクトのパス（`read` の `dynamics` の `path`） |

外す揺れ物の選び方（ユーザーに案を出して決めてもらう）:

- Mobile の PhysBone の上限は、Medium で 6 コンポーネント、Poor で 8 コンポーネント。超えると、超えた種類が丸ごと外される。
- 残す優先：前髪・後ろ髪・しっぽなど見た目に効くもの。外す候補：胸・スカートの細かい揺れ、指のコンタクト、SPS。
- 三角形数が多すぎるとき（Mobile の Medium は 15,000）は、先に `vrc-polygon` で Android 用の削減を考える。
  ポリゴン削減は PC 版にもかかるので、PC 版を減らしたくないときはユーザーに伝えて決めてもらう。
- マテリアルスロット（Mobile の Medium は 2）が多いときは、Avatar Optimizer の統合（`vrc-perf-budget` §3）を案内する。

レシピを書いたら `try --recipe` で `mobileRank` を見せ、目標に届くまでレシピを直す。

## 3. 適用する・外す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Quest')
python -B $qt preview @a --verify-sdk
python -B $qt apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $qt remove @a                                  # 外す内容だけを返す
python -B $qt remove @a --approved-preview '<値>'
```

- preview の `summary` と `plannedPaths` を伝え、明示的な確認を得てから apply する。Git の扱いは衣装トグルと同じ。
- `unity.sdkVerification.android` に Android としてビルドした結果、`pcMobileMaterials` に PC のビルドでモバイル用シェーダーが
  増えていないこと、`rank."sdkVerification.android.counts"` に Android 版のランクが出る。
- DSH が付けていない VQT の部品がすでにあると止まる。そのときは Unity の中で設定してもらうか、外してから使う。
- remove は DSH が付けた VQT の部品だけを外す。レシピのファイルは残る。

## 4. アップロード（ユーザーが行う）

DSH はアップロードしない。次を案内する。

1. Unity を開き、VRChat SDK の Builder でプラットフォームを **Android** に切り替える（初回はテクスチャの再インポートに時間がかかる）。
2. 同じアバター（同じ Blueprint ID）のまま **Build and Upload** する。PC 版と Android 版は同じアバターの 2 つのプラットフォームになる。
3. 終わったら **Windows** に戻す。PC 版だけを直すときも同じシーンで作業できる。
4. 表示されるランクと警告（使えないコンポーネントなど）を確かめる。
