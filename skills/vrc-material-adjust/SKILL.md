---
name: vrc-material-adjust
description: lilToon・Poiyomi のマテリアルの値（主色・色調補正・影・輪郭線・発光・リム）を変えた複製を作り、メニューで切り替える。PSD のない衣装・髪の色や質感の調整を頼まれたら読む。
---

# lilToon・Poiyomi の調整（マテリアルの値 → バリエーション）

```
読む（マテリアルと、lilToon / Poiyomi の今の値）
 → レシピを書いてユーザーに確認
 → 撮影して前後比較（capture）
 → 適用（preview → 確認 → apply）: 複製マテリアル + メニューで切り替え
```

テクスチャは描き変えない。マテリアルを複製して値だけを変える。PSD も PhotoCraft も要らない。
仕組みは色違い（`vrc-texture-variant`）と同じで、同じ CLI・同じフォルダ `Assets/DSH/Variants/<名前>/` を使う。
1 つのレシピで、PSD からのテクスチャ（`textures`）とマテリアルの値（`materials`）を一緒に変えてもよい。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$tex = '<pkg>\tools\unity_texture.py'
```

## 0. 前提

- 対象のマテリアルが **lilToon**（`lilToon`、`Hidden/lilToon...`、`_lil/lilToonMulti`）か **Poiyomi Toon 9 / 10**（`.poiyomi/...`）であること。
  UnityChan Toon Shader などは対象外。Poiyomi の**ロック済み**（`Hidden/Locked/...`、`locked: true`）は値が焼き込まれているので、
  Unity で Poiyomi の Lock を外してもらってから行う。
  アップロード時は Poiyomi が、元のマテリアルも、メニューで差し替える複製（FX のアニメーションにあるもの）も自動でロックし、
  変えた値は焼き込まれる。`--verify-sdk` の確認ではロックしない（VRCFury が本当のアップロード以外では止める）ので、
  マテリアルは変わらない。
- 切り替えには **VRCFury** を使う。Unity を使う手順は、シーンを保存して Unity を閉じてから行う。
- 初回は `setup-required` が返るので、`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $tex materials --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --filter 'Hair' --properties --prepare
```

- `slots`: Renderer、スロット、マテリアル、シェーダー、`active`（今シーンで表示されているか）。
  `--filter` は Renderer のパスかマテリアル名で絞る。1 マテリアルで約 3 KB 出るので、`--properties` は絞って使う。
- **見えている Renderer のマテリアルを選ぶ**。付け替えた髪や衣装があると、元の `Hair` などは `active: false` で隠れている。
  名前で決めず、まず `--properties` なしで全体の `slots` を見て、`active: true` のものから選ぶ。
- `materialValues[]`（`--properties` のとき、最大 12 マテリアル）: 今の値。`family` は `lilToon` / `Poiyomi`。
  `multi` は lilToon Multi、`outline` は輪郭線が出ているか（lilToon は輪郭線付きのシェーダー、Poiyomi は `_EnableOutlines`）。
- `ranges`: 数値の値の範囲（シェーダーの宣言どおり）。
- 同じマテリアルを複数の Renderer が使っていると、そのすべてが変わる。`slots` で確かめて伝える。

## 2. レシピを書く

`Assets/DSH/Variants/<名前>/recipe.json`（名前は英数字・`_`・`-`）:

```json
{
  "name": "Hair_Ash",
  "menu": "Color/Hair Ash",
  "exclusiveTag": "DSH Hair Color",
  "defaultOn": true,
  "materials": [
    {
      "material": "Assets/Avatar/Materials/Hair.mat",
      "set": {
        "_MainTexHSVG": {"hue": -0.05, "saturation": 0.6, "value": 0.95},
        "_ShadowColor": "#7C7F99",
        "_UseRim": true, "_RimColor": "#D8E4FFFF", "_RimBorder": 0.6
      }
    }
  ]
}
```

| 値の形 | 対象 | 書き方 |
|---|---|---|
| 色 | `_Color`、`_ShadowColor`、`_Shadow2ndColor`、`_Shadow3rdColor`、`_ShadowBorderColor`、`_OutlineColor`、`_EmissionColor`、`_RimColor`、`_MatCapColor`、`_BacklightColor`、`_ReflectionColor` | `"#RRGGBB"`（アルファは今のまま）、`"#RRGGBBAA"`、`[r, g, b]`（0〜1。発光などの HDR は 100 まで。読み取りでは HDR の色だけがこの形で出る） |
| 色調補正 | `_MainTexHSVG`（メイン）、`_OutlineTexHSVG`（輪郭線） | `{"hue": -0.5〜0.5, "saturation": 0〜2, "value": 0〜2, "gamma": 0.01〜2}`。書かない項目は今のまま。変えないときの値は hue 0、ほかは 1 |
| 機能のオン・オフ | `_UseShadow`、`_UseRim`、`_UseEmission`、`_UseMatCap`、`_UseReflection`、`_UseBacklight` | `true` / `false` |
| 数値 | 影 `_ShadowStrength`・`_ShadowBorder`・`_ShadowBlur`（2nd・3rd も）・`_ShadowMainStrength`・`_ShadowEnvStrength`、輪郭線 `_OutlineWidth`、リム `_RimBorder`・`_RimBlur`・`_RimFresnelPower`、発光 `_EmissionBlend`・`_EmissionMainStrength`、明るさ `_LightMinLimit`・`_LightMaxLimit`・`_AsUnlit`・`_MonochromeLighting` など | `ranges` の範囲の数 |

上は lilToon。**Poiyomi** で変えられる値（読み取りの `materialValues[].properties` に出る名前と同じ）:

| 値の形 | Poiyomi の値 |
|---|---|
| 色 | `_Color`、`_LightingShadowColor`（影の色味）、`_ShadowColor`、`_LineColor`（輪郭線）、`_EmissionColor`、`_RimLightColor`、`_MatcapColor` |
| 色の調整 | `_MainHueShift`（0〜1、色相を回す量）、`_Saturation`（-1〜10、0 で変えない）、`_MainBrightness`（-1〜2、0 で変えない）、`_MainGamma`（0.01〜5、1 で変えない）。書くと、必要な `_MainColorAdjustToggle`・`_MainHueShiftToggle` も自動でオンになる |
| 機能のオン・オフ | `_EnableOutlines`、`_EnableEmission`、`_EnableRimLighting`、`_MatcapEnable`（シェーダーのキーワードも合わせて切り替える） |
| 数値 | 影 `_ShadowStrength`・`_ShadowBorder`・`_ShadowBlur`、明るさ `_LightingMinLightBrightness`・`_LightingCap`、輪郭線 `_LineWidth`・`_OutlineTintMix`、発光 `_EmissionStrength`、リム `_RimWidth`・`_RimStrength`、マットキャップ `_MatcapIntensity` |

- 上の表にない値（描画モード、透過、ステンシル、テクスチャの差し替え）は変えられない。必要なら Unity で手で変えてもらう。
- `materials` のパスは `Assets/` 内の元のマテリアル。最大 16 個、1 つにつき最大 48 値。
- **ずっとこの見た目にしたい**（「髪をもう少し青く」）ときは `defaultOn: true`。メニューでオフにすると元に戻せる。
  **選べるようにしたい**ときは `defaultOn: false` で、同じ部位の候補を同じ `exclusiveTag` にする。
- 書いたら、変えるマテリアル、値（前 → 後）、メニュー名、初期状態を要約してユーザーに確認を取る。

### 色相の決め方

色相は 1 周を 1 とする（lilToon の `hue` は -0.5〜0.5 のずらし、Poiyomi の `_MainHueShift` は 0〜1 の回転。どちらも 1 = 360°）。
目安: 赤 0、オレンジ 0.08、黄 0.17、緑 0.33、水色 0.5、青 0.6〜0.67、紫 0.75、ピンク 0.9。
**ずらす量 = 目標の色相 − 今の色相**。lilToon では -0.5〜0.5 に収まるように 1 を足し引きする
（例: 青 0.6 → ピンク 0.9 は +0.3。-0.12 にすると水色寄りの緑になる）。
今の色はテクスチャで決まるので、撮影の上段で今の色を確かめてから値を決め、下段で狙いどおりか確かめる。

### よくある頼み方と値

| 頼み方 | 変える値 |
|---|---|
| 色を少し変える・くすませる・明るく | `_MainTexHSVG`（hue で色相、saturation で鮮やかさ、value で明るさ）。全体の色味を足すなら `_Color` |
| 黒・白・灰色の髪や服の色を変える | 色相・彩度・`_Color` ではほぼ変わらない（色が無いため）。明るさは `value` と `gamma`（1 未満で暗い部分が明るくなる）、色味はリム・輪郭線で足す。はっきり色を変えるなら PSD（`vrc-texture-variant`） |
| 影を薄く・柔らかく・色を変える | `_ShadowStrength` を下げる、`_ShadowBlur` を上げる、`_ShadowColor` |
| 輪郭線を細く・色を変える | `_OutlineWidth`、`_OutlineColor`（`outline: false` のシェーダーでは効かない） |
| 光らせる | `_UseEmission: true` と `_EmissionColor`。発光マスクのテクスチャが無いと全体が光る |
| 縁を光らせる | `_UseRim: true`、`_RimColor`、`_RimBorder` |
| 暗いワールドで暗くなりすぎる | `_LightMinLimit` を少し上げる（0.05 → 0.1〜0.2）。Poiyomi は `_LightingMinLightBrightness` |
| Poiyomi の髪の色を変える | `_MainHueShift`（色相）と `_Saturation`。輪郭線が出ていないなら `_EnableOutlines: true` と `_LineColor` |

## 3. 撮影して確認する（Unity を使う、シーンは保存しない）

```powershell
python -B $tex capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --variant Hair_Ash
```

上段が元、下段が変更後の 1 枚の画像（`unity.image`）。色のずれ、影や線の浮き、光りすぎを見て報告する。
`unity.warning` が出たら、変えたマテリアルは隠れた Renderer にしか無い（`visibleSwappedSlots: 0`）。
見えている Renderer のマテリアルに直す（メニューで出す衣装の調整なら、そのままでよいと伝える）。
撮影は Unity の既定のライトなので、VRChat のワールドでの明るさとは違う。直すときはレシピを変えて撮り直す。
`render` はテクスチャを変えるレシピのときだけ要る（値だけのレシピでは「nothing to render」と返る）。

## 4. 適用・一覧・削除

`vrc-texture-variant` の §5・§6 と同じ。`preview` の `request.edits` が変える値の一覧。

```powershell
$v = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--variant', 'Hair_Ash', '--verify-sdk')
python -B $tex preview @v
python -B $tex apply @v --approved-preview '<preview の値>'
```

- apply は元のマテリアルを複製し、値を変え、`DSH Color Variant <名前>` に VRCFury のトグルを作る。
  結果の `unity.materials[].changed` に変えた値の名前、`visibleNow` に今のシーンで表示されているかが出る。
- 同じマテリアルを変える別のバリエーションは、同時にオンにすると片方しか効かない（`overlappingVariants`）。
  同じ `exclusiveTag` にするか、1 つのレシピにまとめる。
- `list` の `render` は、値だけのレシピなら `not-needed`。

## してはいけないこと

- 元のマテリアルの上書き（変えるのは複製だけ）。
- 表にない値を、Editor スクリプトで直接書き換えること（描画モードやステンシルを崩す）。
