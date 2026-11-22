---
name: vrc-verify
description: 改変を適用した直後に読む。コンパイル確認、SDK 前処理の結果の読み方、人が行う動作確認とアップロード前チェックリストを扱う。
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

## 3. 動作の確認（人間が行う）

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

## 4. 性能の再測定（AI が実行する）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "<pkg>\tools\unity-run.ps1" -Project "C:\path\to\Project" `
  -Method "DSH.Editor.DshInspect.Perf"
```

改変前後で比較し、ランクが落ちた項目を名指しで報告する。
判断基準は `vrc-perf-budget`。

## 5. アップロード前チェックリスト（人間が実行する）

AI はこのリストを出して、**ユーザーの確認を待つ**。代行しない。

- [ ] `git status` が意図した変更だけ（未コミットのゴミが無い）
- [ ] Unity コンソールに赤いエラーが無い
- [ ] SDK のビルドパネルで **Build & Test** が通る
- [ ] VRCFury Test Copy でトグル・メニュー・PhysBone が動く
- [ ] 性能ランクが想定どおり（Good 以上を目標）
- [ ] アバター名・サムネイル・説明が意図どおり
- [ ] コンテンツギャラリー（公開範囲・年齢制限）の設定を確認した
- [ ] 別アバターを誤って上書きしない（Blueprint ID を確認）

## 6. 報告の型

```
変更: <何をしたか>
検証: コンパイル OK / 階層 OK / 性能 <前> → <後>
未検証: Play モードの動作（人間の確認が必要）
次: アップロードは上のチェックリストを満たしてから
```

「未検証」を必ず書く。インストールや適用が通ったことは、動くことの証明ではない。
