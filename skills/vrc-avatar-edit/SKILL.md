---
name: vrc-avatar-edit
description: 衣装・髪・メニュー・PhysBone・コンタクト / SPS の改変を設計するときに読む。MA / VRCFury / AAO の実行順序、併用の禁止、WriteDefaults の落とし穴を扱う。
---

# VRChat アバター改変

アバターの改変を「何を・どの順序で・どこに適用するか」まで決めるためのスキル。
実際の適用は、同梱のコマンドがあればそのスキル（§9）、無ければ `vrc-edit-script`、確認は `vrc-verify` が担う。

## 0. 前提と範囲

- 対象: 既存の VRChat Unity プロジェクト（Unity 2022.3.22f1、SDK 導入済み）
- 対象外: Unity/ALCOM の導入、プロジェクト作成・修復、ワールド、アップロード
- 変更は **同梱のコマンドか Editor スクリプト経由**でのみ行う（同梱のコマンドが先）。シーン/プレハブ YAML の直接編集は禁止

## 1. 最初に事実を確定させる

推測で設計しない。以下を実データで確認する。

| 確認すること | 見る場所 |
|---|---|
| アバターの prefab とシーン | プロジェクト直下の `AGENTS.md` → `unity_inspect.py hierarchy` |
| 導入済みパッケージと版 | `Packages/manifest.json`、`Packages/vpm-lock.json` |
| 改変対象（衣装/髪）の prefab | `unity_inspect.py refs --path <prefab>` |
| 現在の性能値 | `vrc-perf-budget` の手順で計測 |

`AGENTS.md` が無い場合は、判明した事実から `templates/AGENTS.template.md` を元に作ることを提案する
（プロジェクト直下に `AGENTS.md` としてコピーする。勝手に作らない）。

## 2. 実行順序（VRChat SDK preprocess callbackOrder）

```
1. NDMF 前半（-11000〜）  … Modular Avatar の衣装統合・メニュー生成
2. VRCFury 本体（-10000） … NDMF プラグインではなく SDK コールバックに直接登録
3. NDMF 後半（-1025〜）   … AAO などの最適化
```

帰結:

- **MA が先、VRCFury が後、AAO が最後**。この順序を前提に設計する
- VRCFury が生成したトグルも AAO の最適化対象になる
- MA 側から「VRCFury が生成するメニュー」を前提にした設定はできない

## 3. 衣装の装着

| 方法 | 使う場面 | 注意 |
|---|---|---|
| **Modular Avatar: Setup Outfit** | アバター付属のガイドが MA 指示の場合（大半） | 衣装 prefab をアバター直下に置いて実行 |
| **VRCFury: Armature Link** | 衣装が VRCFury 前提で作られている場合 | ボーン統合の挙動が MA と違う |

**同一衣装に両方を使わない。** 二重統合でボーンが壊れる（最頻出の事故）。

## 4. 髪の装着

髪アセットは MA 設定済みのことが多い。手順:

1. 髪 prefab をアバター直下に配置
2. MA の Bone Proxy / Merge Armature が設定済みか確認（`unity_inspect.py` で
   `ModularAvatarBoneProxy` / `ModularAvatarMergeArmature` の有無を見る）
3. 未設定なら、頭ボーンへの Bone Proxy を追加する
4. 髪の PhysBone が頭の PhysBone と競合していないか確認

## 5. メニューとトグル

### VRCFury Toggle（推奨・設定が少ない）

アバター直下に空オブジェクトを作り、`VRCFury | Toggle` を追加して設定する。

| 項目 | 意味 | 典型値 |
|---|---|---|
| Actions → Object toggle | 切り替える対象 | 衣装のルート |
| Menu Path | メニュー上の位置（`/` でサブメニュー） | `Outfit/Hoodie` |
| Exclusive Tags | 同じタグ同士を排他にする | `outfit` |
| Saved Between Worlds | 状態を保存する | ON |
| Default On | 初期状態で装備 | 好み |

複数衣装は同じ `Exclusive Tags` を付ける。上下セットなら `tops` / `bottoms`、
全身衣装は `tops,bottoms` のように複数タグ可。

### Modular Avatar Menu Item

MA で組む場合。Expression Menu の階層を MA が生成するので、
手動でアニメーターを触らない。既存メニューとの衝突に注意。

## 6. PhysBone / コンタクト / SPS

- **PhysBone**: 揺れ物には必ず付く。`integratedLimits` は無効化しない
  （VRChat 側で強制されるため、無効化しても効果がなく混乱の元）
- **コンタクト**: SPS はプラグ = sender 2 / receiver 5、ソケット = sender 1 の
  コストを持つ。レガシー互換（DPS/TPS/SPS1/2）はソケットあたりライト 2 個などの
  追加コストがあるため、不要なら OFF
- コンタクト数は性能ランクの評価対象（`vrc-perf-budget` 参照）

## 7. WriteDefaults とアニメーター

- 既存の FX レイヤーを触る場合、`Write Defaults` の混在は遷移崩れの原因。
  レイヤー単位で揃っているか確認し、**勝手に統一しない**（他レイヤーが依存している）
- 新しいレイヤーを足すより、MA/VRCFury に生成させる方が安全
- 手でアニメーターを編集する必要が出たら、その旨をユーザーに伝えて承認を取る

## 8. よくある破綻と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| ボーンが二重になる | MA と VRCFury の併用 | 片方を外す |
| メニューが消える | 排他タグの付け忘れ / Menu Path の重複 | タグと Path を確認 |
| 服が貫通する | 体型を変えたのに衣装が追従していない / 服の下の体が残っている / 別アバター用の衣装 | `vrc-shape-adjust`（追従・削除）、非対応衣装なら `vrc-outfit-fit` |
| スカートや紐が体を突き抜ける | 揺れものの PhysBone コライダーが無い | `vrc-physbone` で脚などにコライダーを足す |
| 髪が動かない | Bone Proxy 未設定 / PhysBone の root が違う | 階層を確認 |
| アップロード時に警告 | WriteDefaults 混在 / 参照切れ | `vrc-verify` へ |
| 開いた瞬間 `error CS0246`（`VTPTests.cs` など SDK 内） | SDK が要求する `com.unity.*` が `manifest.json` に無い | `Packages/com.vrchat.base/package.json` の `dependencies` を確認し、不足分を `manifest.json` に追加 |
| `Packages/vpm-manifest.json` がある | 旧 vrc-get レイアウト | 動作はするが Unity 依存は自動で入らない。上の対処が必要 |

`vrc-get` で入れた直後にコンパイルが落ちる場合、**アセットではなく依存宣言の問題**であることが多い。
`Assets/` を疑う前に `Packages/` を見る。

## 9. 委任の切り方

- 読み取りだけで済む → `vrc-asset-read` の `unity_inspect.py`
- 配置済み衣装のオン・オフ → `vrc-first-run`
- 色違い・肌色・ロゴ（付属 PSD から） → `vrc-texture-variant`
- lilToon・Poiyomi の色・影・輪郭線・発光の調整（マテリアルの値） → `vrc-material-adjust`
- 体型・貫通・隠れる部分の削除（シェイプキー、MA、AAO） → `vrc-shape-adjust`
- 小物・髪・衣装の取り付け、付け替え、取り外し → `vrc-accessory`
- 別アバター用の衣装・髪を着せる → `vrc-outfit-fit`
- 既存の PhysBone の値、ボーンに付けるコライダー → `vrc-physbone`
- ビューポイント、ボーン単位の大きさ → `vrc-proportion`
- 表情（ジェスチャー、メニューで選ぶ表情、ほほ染めなどのトグル） → `vrc-expression`（既存の FX は変えずにレイヤーを足す）
- 手に持って置ける小物、ワールドに固定する小物 → `vrc-accessory` の `hold` / `world`
- 上のどれにも当たらない構造の変更（新しい PhysBone、コンタクト / SPS、MA のメニュー、アニメーター） → `vrc-edit-script` でスクリプト化して適用
- 数値の判断 → `vrc-perf-budget`
- 適用後 → `vrc-verify`

判断に迷ったら、まず読み取りで事実を揃える。推測でスクリプトを書かない。
