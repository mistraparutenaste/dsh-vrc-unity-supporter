---
name: vrc-verify
description: 改変を適用した直後に読む。コンパイル確認、SDK 前処理の結果、AI が回す再生テスト（ジェスチャー・メニュー）、人が行う確認とアップロード前チェックを扱う。
---

# 検証（アップロードしない）

アップロードは AI が行わない。このスキルは「人間がアップロードする前に、
どこまで機械的に確認できるか」を定義する。

## 1. まずコンパイルを通す（AI が実行する）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "<pkg>\tools\unity-run.ps1" -Project "C:\path\to\Project" `
  -Method "DSH.Editor.DshInspect.CompileCheck"
```

- 終了コード 0 かつログに `error CS` が無ければ合格
- 失敗したら `vrc-edit-script` に戻る。**アセットは壊れていない**ので慌てない

## 2. 構造の確認（AI が実行する）

```powershell
python <pkg>/tools/unity_inspect.py hierarchy "Assets\Avatar.prefab"
```

意図したオブジェクト・コンポーネントが増えているか、参照切れが無いかを確認する。
シーンや大きな prefab では `--filter <対象名>` で変更箇所に絞る（既定は 300 ノード・約 48KB まで。`truncated` を確認する）。

## 3. 再生テスト（AI が実行する。Gesture Manager の代わり）

SDK でビルドしたコピーの FX を、ジェスチャー・メニュー・パラメータで動かし、状態ごとに何が変わったかを返す。
VRCFury と Modular Avatar が統合したあとの FX そのものを動かすので、レシピの撮影より VRChat に近い。シーンは変えない。

```powershell
$pb = '<pkg>\tools\unity_playback.py'
python -B $pb test --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --auto --prepare
```

`--auto` は、このアバターにかかっている DSH の表情・小物（メニュー、置く）・衣装トグルから、状態と期待値を作る。
DSH 以外のギミックや、組み合わせを試すときは、テストを JSON で書いて `--spec` で渡す（置き場所は `.dsh/playback/` など、Assets の外）。

```json
{"states": [
  {"label": "右手グー", "gesture": {"right": "Fist"}, "expect": [{"path": "@face", "shape": "eye_smile_1", "min": 90}]},
  {"label": "帽子を外す", "menu": ["!Props/Cap"], "expect": [{"path": "**/Cap", "active": false}]},
  {"label": "置く", "menu": ["Props/Cap", "Props/Put down"], "expect": [{"path": "**/Cap", "freezeToWorld": true}]},
  {"label": "髪型 2", "parameters": {"Hair": 2}}
]}
```

| 項目 | 内容 |
|---|---|
| `gesture` | `left` / `right` に Neutral、Fist、Open、Point、Peace、RockNRoll、Gun、ThumbsUp |
| `menu` | ビルド後のメニューのパス。そのトグルの値を入れる。先頭の `!` はオフにする（初期状態がオンのトグル） |
| `parameters` | パラメータ名と値（FX にあるもの。`unity.states[].parameters.notInFx` に、FX に無い名前が出る） |
| `expect` | `path` はビルド後のアバターからのパス、`@face`（Lip Sync のメッシュ）、`**/名前`（ビルドでボーンの下に移る小物）。`shape` と `min` / `max`、`active`、`freezeToWorld` のどれか |

結果の読み方:

- `unity.states[]`：`changedShapes`（何もしていない状態からの変化。`メッシュ:シェイプキー: 前 -> 後`）、`turnedOn` / `turnedOff`、`frozenInWorld`、`layerStates`（どのレイヤーがどのステートにいるか）、`checks`（期待値の合否）。
- `mixing[]` に、作者の表情が混ざった状態とシェイプキーが出る（直し方は `vrc-auto-adjust`）。
- `summary.failedStates` が 0 でなければ、`changedShapes` と `layerStates` から原因を探し、レシピを直して apply し、もう一度テストする。
  例：作者の表情が混ざる → `changedShapes` に、レシピに無いシェイプキーが出る。DSH のレイヤーに入っていない → `layerStates` で分かる。
- `unity.image`：何もしていない状態を先頭に、状態ごとの画像（`rows` の順）。画像を読めるなら見て判断し、読めないときはパスを伝える。
- 揺れ物（PhysBone）は、再生テストでは動かさない。`unity_physbone.py simulate`（`vrc-physbone` §3）で、Play モードで動かして振れ・収まるまでの時間・脚への食い込みを測る。
- IK、ネットワーク同期、一人称の見え方は動かせない。次の §4 で人に見てもらう。

## 4. 動作の確認（人間が行う）

衣装トグルの適用で `--verify-sdk` を使った場合は、まず `unity.sdkVerification` を読む。SDKの前処理で生成されたメニュー項目・初期値・対象衣装のオンとオフのキーを確認する。シーンへの保存結果、SDKの前処理結果、VRChatクライアントでの動作確認を報告し、クライアントで試すメニュー名と操作を具体的に伝える。

| 方法 | 何が分かる | 手順 |
|---|---|---|
| **VRCFury: Build an Editor Test Copy** | **最終形に最も近い**。SDK 前処理を実ビルドと同じ順で通す | アバターを選択 → `Tools > VRCFury > Build an Editor Test Copy` |
| **NDMF: Manual bake avatar** | MA / AAO だけの結果 | アバター右クリック → `NDMF > Manual bake avatar` |
| **Gesture Manager** | ジェスチャー・メニュー・PhysBone・コンタクト | `Tools > Gesture Manager Emulator` → prefab をシーンへ → Play |
| **Av3Emulator** | 上記の代替 | 導入していれば Play で確認 |

AI が代行できない理由: いずれもエディタの GUI か Play モードを必要とし、
結果は「見た目・触感」で判断するものだから。**AI は手順と確認項目を出す。**

VRCFury の前提設定（OFF だと Play でトグルが動かない）:

- `Tools > VRCFury > Settings > Enable VRCFury in play mode`
- `Tools > VRCFury > Settings > Enable VRCFury for uploads`（セッション中のみ保持）

## 5. 性能の再測定（AI が実行する）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "<pkg>\tools\unity-run.ps1" -Project "C:\path\to\Project" `
  -Method "DSH.Editor.DshInspect.Perf"
```

`result.json` を `unity_inspect.py rank` に渡してランクを出し（`vrc-perf-budget` §2）、改変前後で比較してランクが落ちた項目（`limitedBy`）を名指しで報告する。
判断基準は `vrc-perf-budget`。

## 6. アップロード前チェックリスト（人間が実行する）

AI はこのリストを出して、**ユーザーの確認を待つ**。代行しない。

- [ ] `git status` が意図した変更だけ（未コミットのゴミが無い）
- [ ] Unity コンソールに赤いエラーが無い
- [ ] SDK のビルドパネルで **Build & Test** が通る
- [ ] VRCFury Test Copy でトグル・メニュー・PhysBone が動く（`vrc-physbone` で値を変えた揺れ物は、揺らして確かめる）
- [ ] パラメータ容量が 256 bit 以内（`vrc-perf-budget` §5）
- [ ] 性能ランクが想定どおり（Good 以上を目標）
- [ ] アバター名・サムネイル・説明が意図どおり
- [ ] コンテンツギャラリー（公開範囲・年齢制限）の設定を確認した
- [ ] 別アバターを誤って上書きしない（Blueprint ID を確認）

## 7. 報告の型

```
変更: <何をしたか>
検証: コンパイル OK / 階層 OK / 性能 <前> → <後>
未検証: Play モードの動作（人間の確認が必要）
次: アップロードは上のチェックリストを満たしてから
```

「未検証」を必ず書く。インストールや適用が通ったことは、動くことの証明ではない。
