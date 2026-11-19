---
name: vrc-first-run
description: DSHでの初回診断と、配置済み衣装にVRCFuryトグルを追加する手順。プロジェクトを調べたい、対象を選びたい、服をメニューで切り替えたいときに使う。
---

# 初回診断と衣装トグル

## プロジェクトを調べる

このスキルの `skills/vrc-first-run/` の親の親がプラグインルート。パスを取得できない場合は、`$env:DSH_PROFILE_DIR`、または `%USERPROFILE%\.dsh\profiles\<profile>` の `node_modules/dsh-vrc-unity-supporter` を確認する。`<pkg>`、`<project>` は実際のパスに置き換え、引用符で囲む。Python 3.10 以上を使う。`python` が使えなければ `py -3` も確認する。

```powershell
python -B "<pkg>\tools\unity_inspect.py" report --json
```

作業フォルダまたは親フォルダからプロジェクトを特定する。見つからなければ、開いたフォルダ直下にあるUnityプロジェクトを探す。候補が一つなら `report "<project>" --json` で診断し、複数ならパスを示して選んでもらう。候補が見つからなければプロジェクトのパスを聞く。

最初にプロジェクト名、アバターを含む可能性があるシーンとPrefab、次にできることを伝える。空の候補一覧からアバター不在を断定しない。モデルやPrefabの上書きがある場合は、UnityのHierarchyの表示を優先する。診断だけならUnity起動やファイル配置、Gitの準備は不要。

## 衣装トグルを適用する

対象は保存済みのシーンに配置された衣装。`unity_inspect.py hierarchy "Assets/Avatar.unity" --project "<project>" --json` をUnity起動前の候補探しに使う。名前だけで依頼されたときや同名候補があるときは、適用前にUnityから正確な候補を取得する。対象プロジェクトのシーンを保存してUnityを閉じてもらう。

```powershell
$tool = '<pkg>\tools\unity_toggle.py'
python -B $tool targets --project '<project>' --scene 'Assets/Avatar.unity' --query 'Hoodie'
```

`setup-required` が返ったら、`plannedPaths` とUnityが生成する `.meta` を伝え、初回のヘルパー設置を確認してから同じコマンドに `--prepare` を付ける。検索は対象シーンを保存せず、Gitの準備前にも使える。`unity.avatars` が複数なら選んでもらい、`--avatar` と `--avatar-id` を付けて衣装候補を取得する。`unity.outfits` の `path` と `siblingPath` で候補を示し、選択された実際のパスと `id` を適用に渡す。`outfitMatchCount` が返った候補数より多い場合は検索語を絞る。

メニュー項目と初期状態を確認する。`--default-on` がない場合は初期状態がオフ。VRCFury未導入の場合はVCC / ALCOMで導入または更新する手順を案内する。

```powershell
$target = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar',
            '--outfit', 'Avatar/Hoodie', '--menu', '衣装/パーカー', '--default-on', '--verify-sdk')
# targets で対象を選んだ場合は --avatar-id と --outfit-id も渡す。
python -B $tool preview @target
```

1. `git.state` が `no-repository` または `no-commit` の場合、`python -B $tool checkpoint --project "<project>"` で内容を確認する。既存の作業もローカルの初回コミットに入ること、記録対象、`.gitignore` に足す除外を説明する。ユーザーが同意してから `checkpoint --confirm --project "<project>"` を実行する。Gitのユーザー名・メールアドレスが未設定なら設定を案内する。`git.managedScenes` はDSHが保存・検証した変更で、コミットを挟まずに次の依頼へ進める。`git.blockingChanges` に項目があれば、該当ファイルをユーザーに伝え、作業を記録してもらってから再プレビューする。
2. `sceneInCheckpoint` が `false` なら、選んだシーンをGitに含めてから再プレビューする。最新のプレビューからシーン、アバターと衣装のHierarchyパス、メニュー名、初期状態、`plannedPaths` と生成される `.meta` を要約する。明示確認を得たら、そのプレビューに対応する次のコマンドを実行する。Unityで対象プロジェクトが開いている場合は、保存して閉じるよう案内する。

```powershell
python -B $tool apply @target --approved-preview '<preview の値>'
```

初回のUnityコンパイルに時間がかかる場合は、DSHのジョブ機能で実行する。結果とログは `.dsh/runs` に保存される。`--verify-sdk` はシーンを保存した後にアバターのコピーをSDKの前処理に通す。ローカルのGit除外には `.dsh/` と、SDK検証時に使うVRCFuryの一時ビルド出力が入る。

3. 適用時に同名候補が返ったら `targets` で対象を確認し、選び直したプレビューを提示する。`changes` は現在のGit差分、`checkpoint` は元のGitコミット。エラー時は `unity.error` と `log` を調べ、シーンが保存済みかも伝える。
4. 保存結果と `unity.sdkVerification` の結果をそれぞれ報告する。`passed` なら生成済みのメニュー名と衣装のオン・オフを切り替えるキーを確認できたことを伝える。`failed` または `inconclusive` なら理由を示す。SDK検証だけ再試行するときは、保存済みのトグルと同じ依頼を新たにプレビューして実行できる。VRChatクライアントでの動作は、ユーザーが **Build & Test** を実行し、報告されたメニューを開いて衣装の表示・非表示を確認する。
5. Gitで復元する場合、`git restore --source <checkpoint> -- <scene>` はそのシーン全体を元のコミットまで戻す。連続適用した複数の改変にも影響するので、対象と範囲を確認してから案内する。

この導線は単一衣装のオン・オフ用。Prefab本体の改変、排他設定、衣装の装着などは `vrc-avatar-edit` と `vrc-edit-script` を使い、既存機能との相互作用を確認する。
