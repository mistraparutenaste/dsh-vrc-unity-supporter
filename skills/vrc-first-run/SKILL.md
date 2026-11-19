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

対象は保存済みのシーンに配置されている衣装。`unity_inspect.py hierarchy "Assets/Avatar.unity" --project "<project>" --json` で候補を絞る。元Prefab展開の `[prefab]` などは診断上の表示なので、UnityのHierarchyの正確なパスで選択する。アバターや衣装が複数なら候補を示す。メニュー項目と初期状態を確認する。`--default-on` がない場合は最初はオフ。VRCFury未導入の場合はVCC / ALCOMで導入または更新する手順を案内する。

```powershell
$tool = '<pkg>\tools\unity_toggle.py'
$target = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar',
            '--outfit', 'Avatar/Hoodie', '--menu', '衣装/パーカー', '--default-on')
python -B $tool preview @target
```

1. `git.state` が `no-repository` または `no-commit` の場合、`python -B $tool checkpoint --project "<project>"` で内容を確認する。既存の作業もローカルの初回コミットに入ること、記録対象、`.gitignore` に足す除外を説明する。ユーザーが同意してから `checkpoint --confirm --project "<project>"` を実行する。Gitのユーザー名・メールアドレスが未設定なら設定を案内する。既存の未コミット作業があれば、ユーザーに変更を記録してもらってから再プレビューする。
2. `sceneInCheckpoint` が `false` なら、選んだシーンをGitに含めてから再プレビューする。最新のプレビューからシーン、アバターと衣装のHierarchyパス、メニュー名、初期状態、`plannedPaths` と生成される `.meta` を要約する。明示確認を得たら、そのプレビューに対応する次のコマンドを実行する。Unityで対象プロジェクトが開いている場合は、保存して閉じるよう案内する。

```powershell
python -B $tool apply @target --approved-preview '<preview の値>'
```

初回のUnityコンパイルに時間がかかる場合は、DSHのジョブ機能で実行する。結果とログは `.dsh/runs` に保存され、既存の `.gitignore` で除外されていない場合にはGitのローカル除外に `.dsh/` を追加する。

3. Unityが同名候補を返したら、候補のIDと同階層での順序を示す。ユーザーが選んだIDを `--avatar-id` または `--outfit-id` で指定し、対象が確定したプレビューを改めて確認してもらう。`changes` が今回の変更、`checkpoint` が適用前のコミット。エラーなら `unity.error` と `log` を調べ、保存済みかも含めて状態を伝える。追加のGit差分が発生した場合は、差分を確認してから続ける。
4. 成功時は変更ファイル、保存後に確認したトグル設定、復元地点を報告する。既存シーンは確認のうえ `git restore --source <checkpoint> -- <scene>` で復元できる。新規ヘルパーを戻す場合は、今回追加したファイルだけをUnity上で `.meta` と一緒に削除する。アップロード前にユーザー自身が **Build & Test** で衣装のオン・オフを確認する。

この導線は単一衣装のオン・オフ用。Prefab本体の改変、排他設定、衣装の装着などは `vrc-avatar-edit` と `vrc-edit-script` を使い、既存機能との相互作用を確認する。
