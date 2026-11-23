---
name: vrc-expression
description: ハンドジェスチャーの表情、メニューで選ぶ表情の固定、ほほ染め・涙などのシェイプキーのトグルを作る。表情の差し替え・固定・追加を頼まれたら読む。
---

# 表情の改変

```
読む（顔のシェイプキーと、作者のジェスチャー表情）
 → レシピを書いて確認
 → 撮影（表情ごとの顔）
 → 適用（preview → 確認 → apply、SDK 検証）
 → Gesture Manager で確かめてもらう
```

アバターのアニメーターは変えない。DSH はレシピのフォルダの `Generated/` に FX のコントローラー・アニメーション・メニューを作り、
アバターの下の `DSH Expression <名前>` に Modular Avatar の Merge Animator・Parameters・Menu Installer を付ける。
作者の表情レイヤーは残り、DSH のレイヤーがその後ろに入るので、**レシピに書いたシェイプキーだけ** DSH が上書きする。
レシピは `Assets/DSH/Expressions/<名前>/recipe.json` に置く。Modular Avatar が必要。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$ex = '<pkg>\tools\unity_expression.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $ex list --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
python -B $ex list ... --filter mouth      # シェイプキーを名前で絞る
```

- `renderer`：顔のメッシュ（Avatar Descriptor の Lip Sync のメッシュ）。違うときはレシピの `renderer` で指定する。
- `shapes`：顔のシェイプキー（上限 400。`truncated` を確認）。
- `authorGestures`：作者のジェスチャー表情。レイヤー、状態、どの手のどのジェスチャーで入るか、そのとき動くシェイプキー（0 以外）。
  `FacialSet` のような切り替えで、同じジェスチャーに複数の表情がある（`Fist_1`、`Fist_2`）アバターもある。

## 2. レシピを書く

```json
{
  "name": "Face",
  "menu": "Expressions",
  "gestures": [
    {"hand": "right", "gesture": "Fist", "shapes": {"eye_smile_1": 100, "mouth_smile_1": 60, "eye_blink_2": 0, "eyebrow_down": 0}}
  ],
  "locks": [
    {"name": "Jito", "shapes": {"eye_jito_1": 100, "mouth_mu_R": 40}}
  ],
  "toggles": [
    {"name": "Blush", "shapes": {"Option_shy_1": 100}, "saved": true}
  ]
}
```

| 項目 | 内容 |
|---|---|
| `gestures[]` | `hand`（left / right / either）、`gesture`（Fist、Open、Point、Peace、RockNRoll、Gun、ThumbsUp）、`shapes`（シェイプキー名と 0〜100）。両手で DSH の表情があるときは右手が勝つ |
| `locks[]` | メニューで選ぶ表情。オンの間はジェスチャーより優先される。`name` はメニューの表示名 |
| `toggles[]` | 単独でオン・オフするシェイプキー（ほほ染め、涙、汗）。`saved`（既定 true）でワールド移動後も保つ |
| `menu` | `locks` と `toggles` を入れるサブメニューのパス。`locks` と `toggles` は合わせて 8 個まで |
| `override` | `listed`（既定）：レシピに書いたシェイプキーだけを上書き。`all`：作者のジェスチャー表情が動かすシェイプキーもすべて DSH が持つ（作者のジェスチャー表情は実質使われなくなる） |
| `renderer` | 顔のメッシュのパス（省略時は Lip Sync のメッシュ） |

上書きの考え方（ユーザーに説明する）:

- DSH が持つシェイプキー（`gestures` と `locks` に出てくるもの）は、どの状態でも DSH が値を決める。表情を出していないときは、シーンに保存されている値（普段の顔）に戻す。
- 作者の同じジェスチャーが別のシェイプキーも動かしていると、両方が混ざる。混ぜたくないシェイプキーは、そのジェスチャーで `0` を書く（例の `eye_blink_2: 0`、`eyebrow_down: 0`。作者の Fist が動かしていたもの）。
  そのシェイプキーは DSH が持つことになるので、作者のほかのジェスチャーでも動かなくなる。`authorGestures` を見せて、影響を伝えてから決める。
- `toggles` のシェイプキーは `gestures`・`locks` と重ねられない。
- 目を閉じる表情では、VRChat のまばたきが重なることがある。気になるときは作者のまばたきの設定を案内する（このコマンドでは変えない）。
- 追加される同期パラメータは、`locks` があれば 8 bit、`toggles` 1 個につき 1 bit。preview の `parameterBudget` で残りを確かめる（`vrc-perf-budget` §5）。

## 3. 撮影して確認する（シーンは保存しない）

```powershell
python -B $ex capture --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --recipe Face
```

上から、今の顔、各ジェスチャー、各メニュー表情、各トグルのオフ・オン の順に顔を撮る（`rows` に並び順）。
作者の表情との混ざり方は撮影には出ないので、適用後に Gesture Manager で確かめてもらう。

## 4. 適用する・外す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Face')
python -B $ex preview @a --verify-sdk
python -B $ex apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $ex remove @a                                  # 外す内容だけを返す
python -B $ex remove @a --approved-preview '<値>'
```

- preview の `summary`、`parameterBudget`、`plannedPaths` を伝え、明示的な確認を得てから apply する。Git の扱いは衣装トグルと同じ。
- `unity.sdkVerification` に、ビルド後の FX にある DSH のレイヤー、アニメーションの届く先、`layerOrder`（DSH のレイヤーが作者のジェスチャーレイヤーより後ろにあるか）、メニューの位置が出る。
- レシピを書き換えて apply すると、`Generated/` を作り直す。
- remove は `DSH Expression <名前>` と `Generated/` を消す。レシピのファイルは残る。`python -B $ex recipes` でレシピと適用先のシーンを一覧にできる。
