# dsh-vrc-unity-supporter

このリポジトリは、VRChat アバターを改変するときに、AI エージェントが手順に沿って操作できるようにするプラグインです。**DeepSeek Harness（DSH）** と **Claude Code** の両方に対応しています（Claude Code は 0.5.0 から）。チャットでアバターの構成を調べたり、シーンに配置した衣装をメニューで切り替えられるようにしたりできます。変更は Unity 経由で適用し、結果と戻し方をチャットで確認できます。

## セットアップ

Windows で、まだ入っていないものを用意してください。

| 必要なもの | 準備すること |
| --- | --- |
| **DeepSeek Harness Desktop または Claude Code** | どちらか一つを使います。DSH は公式サイトの **Download Desktop → Windows (64-bit)** からインストールし、画面の案内に沿って初期設定を済ませます。Claude Code はデスクトップアプリかターミナル版を使います。どちらも、チャットを送れることを確認してください。 [DSH 公式サイト](https://www.deepseek.com/en/harness/) · [Claude Code の概要](https://code.claude.com/docs/en/overview) |
| **Git for Windows** | Git は改変前の状態を記録し、あとで元に戻すために使います。記録は PC の中で完結します。まず Windows 用のインストーラーで Git を入れます。 [Git のダウンロード](https://git-scm.com/install/win) |
| **Python 3.10 以上** | アバターの構成を調べるために使います。インストール後、DSH または Claude Code を開き直してください。 [Python の Windows 向けダウンロード](https://www.python.org/downloads/windows/) |
| **Unity Hub と Unity 2022.3.22f1** | Unity Hub で有効なライセンスを設定し、指定のバージョンでプロジェクトを開けることを確認します。 [VRChat 公式の Unity 導入案内](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) |
| **VCC または ALCOM とアバタープロジェクト** | 普段使っている管理アプリをどちらか一つ使用します。作業対象は **VRChat SDK - Avatars** が導入済みで、Unity で開けるプロジェクトです。 [VCC のセットアップ](https://vcc.docs.vrchat.com/guides/getting-started/) · [ALCOM のダウンロード](https://vrc-get.anatawa12.com/alcom/) |

下の例で **衣装トグル** を作る場合は、対象プロジェクトに **VRCFury** を導入し、アバターと衣装を同じシーンに配置して保存してください。実機での動作確認には VRChat クライアントを使います。 [VRCFury の導入手順](https://vrcfury.com/download/) · [VRChat のローカルテスト手順](https://creators.vrchat.com/avatars/#local-avatar-testing)

## 動作確認環境

| 項目 | DSH | Claude Code |
| --- | --- | --- |
| アプリ | DeepSeek Harness Desktop（Windows） | Claude desktop |
| モデル | DeepSeek V4.1 Flash（画面表示例 `DeepSeek-V41-Flash`） | Opus 5.5 |
| エフォート（推論の強さ） | `MAX` | 中～ |

上記以外の組み合わせでの動作は確認していません。

## プラグインのインストール

使うアプリに合わせて、どちらか一方の手順でインストールします。

### DSH で使う場合

1. DSH を開き、**Plugins** → **Add plugin** を選びます。
2. 入力欄に次のパッケージ名を貼り付け、インストールします。

   ```text
   dsh-vrc-unity-supporter
   ```

3. DSH で **新しいセッション** を作り、プリセットの一覧に **VRChat Avatar** が表示されることを確認します。

#### ZIP を使う場合

1. この GitHub ページの **Code** → **Download ZIP** を選びます。
2. ダウンロードした ZIP を右クリックして **すべて展開** を選びます。
3. DSH を終了し、展開したフォルダにある **`install.cmd`** をダブルクリックします。
4. 「完了しました」と表示されたら、DSH を起動し直して **新しいセッション** で **VRChat Avatar** を選びます。

`install.cmd` は DSH に同梱されたコマンドを使い、npm から公開版を取得してインストールします。インストール時はインターネットに接続してください。 [インストーラーの詳細と削除方法](installer/README.md)

プラグインのバージョンが **0.2.0** の場合は、Editor スクリプトの初期配置を手動で行います。 [0.2.0 のセットアップ手順](https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/blob/v0.2.0/README.md#プロジェクトへの初期配置)

### Claude Code で使う場合

同じスキルとツールを Claude Code のプラグインとしても使えます。Git、Python、Unity などの準備は上の表と同じです（DSH は不要）。Claude Code で次を順に実行します。

```text
/plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
/plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
```

ターミナルからは `claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter` のあと `claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter` でも入ります。Unity プロジェクトのフォルダで Claude Code を開き、下の「最初に試す」と同じ一文から始めてください。入口の `vrc-avatar` スキルが、読み取りから始めて適用前に確認を取る DSH 版と同じ手順に沿わせます。

## 最初に試す

1. DSH のワークスペース（Claude Code では作業フォルダ）で、改変したい Unity プロジェクトのフォルダを開きます。`Assets`、`Packages`、`ProjectSettings` が並んでいるフォルダです。
2. DSH では、新しいセッションのプリセットを **VRChat Avatar**、モデルを **DeepSeek V4.1 Flash**、エフォートを **MAX** に設定します。Claude Code では、プラグインを入れた状態で新しいセッションを始めるだけです。
3. チャットに次の一文を入力します。最初はプロジェクトのファイルを読み取るだけです。Unity の起動や Git での記録は、改変を適用するときに行います。

   ```text
   このプロジェクトのアバター構成を調べて
   ```

4. アバターと衣装が確認できたら、衣装名を自分のプロジェクトの名前に置き換えて依頼します。適用前に、シーンを保存して Unity を閉じてください。

   ```text
   Outfit_Hoodie を「衣装/パーカー」からオン・オフできるようにして。初期状態はオンで
   ```

エージェントが対象と変更予定を示します。衣装名が曖昧な場合は、保存済みのシーンから候補を取得し、チャットで選びます。初めて Git を使うプロジェクトでは、PC 上に復元地点を作る手順が案内されます。このプラグインで保存・検証したシーンは、手作業による変更が加わるまでは、コミットを挟まずに続けて改変できます。

適用後は、保存結果とSDKの前処理でメニュー・アニメーションを確認できたかがチャットに表示されます。VRChat内で試すには、Unityで **VRChat SDK → Show Control Panel → Builder → Offline Testing → Build & Test** を選びます。VRChatの **SDK Test Avatars** でテスト用アバターを選び、チャットに表示されたメニューから衣装をオン・オフしてください。 [VRChat のローカルテスト手順](https://creators.vrchat.com/avatars/#local-avatar-testing)

## 色・スキンの改変（0.6.0 から）

アバターや衣装に付属している、レイヤー分けされた PSD から色違いを作れます。衣装の色、肌の色、髪や瞳の色を変えたり、自分で用意したロゴや柄を入れたりできます。元の PSD・テクスチャ・マテリアルはそのまま残し、色違いは別のマテリアルとして追加されます。メニューから元の見た目と切り替えられます。

1. 無料の画像編集ソフト **PhotoCraft** をインストールします。PSD の編集はこのソフトのコマンドラインで行い、画面を開く必要はありません。 [PhotoCraft のダウンロード](https://getartcraft.com/apps/photocraft)
2. アバターの PSD がどこにあるか（BOOTH から展開したフォルダなど）を確認しておきます。
3. チャットで、たとえば次のように依頼します。

   ```text
   パーカーを紺色にした色違いを作って。PSD は Downloads\Salt_v1.0.1 にあります
   ```

エージェントは PSD のレイヤー構成を調べ、どのレイヤーをどう変えるか（レシピ）を示してから書き出します。続いて Unity でアバターを撮影し、改変前と改変後を並べた画像で確認します。適用前には、メニュー名と作られるファイルを示して確認を取ります。撮影と適用の前には、シーンを保存して Unity を閉じてください。撮影では GPU を使います。

付属 PSD から作ったテクスチャは、多くのアバターの利用規約で配布が禁止されています。プロジェクトの中でだけ使ってください。PhotoCraft の詳しい使い方は [docs/PHOTOCRAFT.md](docs/PHOTOCRAFT.md) にあります。

## 困ったとき

- **VRChat Avatar が表示されない**。Plugins でプラグインが入っていることを確認し、DSH で新しいセッションを作ります。
- **Claude Code でスキルが使われない**。`/plugin` で `dsh-vrc-unity-supporter` が有効になっているか確認し、`/reload-plugins` を実行するか新しいセッションを始めます。
- **プロジェクトが見つからない**。DSH または Claude Code で開いているフォルダに `Assets` と `ProjectSettings` があるか確認します。
- **色違いで「PhotoCraft CLI was not found」と出る**。PhotoCraft をインストールし、DSH または Claude Code を開き直します。別の場所に入れた場合は、環境変数 `PHOTOCRAFT_CLI` に `photocraft-cli.exe` のフルパスを設定します。
- **撮影（改変前後の画像）が失敗する**。撮影は GPU を使って Unity を起動します。Unity を閉じてから再度依頼し、それでも失敗する場合はチャットに表示されたログの場所を確認してください。
- **Git の名前やメールアドレスを求められた**。チャットで「このプロジェクトで Git の名前とメールアドレスを設定する方法を教えて」と聞いてください。
- **インストーラーが途中で止まる**。DSH をタスクトレイからも終了し、画面に表示されたエラーを確認してください。 [インストーラーのトラブル対処](installer/README.md#うまくいかないとき)

<details>
<summary>メンテナー向けのテストと公開手順</summary>

Windows で `python -B -m unittest discover -s tests -v` を実行すると、読み取り、衣装トグル、色違いの CLI の回帰テストを実行できます（Unity と PhotoCraft は偽物を使うので不要です）。Claude Code 版のマニフェストは `claude plugin validate . --strict` で確認できます。版を上げるときは `package.json` と `.claude-plugin/plugin.json` を揃えます（`verify-package.ps1` が照合します）。独自の Editor スクリプトを使う場合は `templates/Editor/` のヘルパーを `Assets/DSH/Editor/` に配置します。`templates/AGENTS.template.md` は任意のプロジェクトメモです。

```powershell
npm login
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1
```

`publish.ps1` は次を順に実行し、前提が欠けていれば**何も壊さずに止まります**。

1. `verify-package.ps1`（BOM / スキル名 / JSON / `dsh.bundle.patch` / プラグインのマニフェスト）
2. `npm pack --dry-run` で同梱内容を確認
3. npm / gh の認証確認（未ログインなら実行すべきコマンドを表示して終了）
4. `npm publish --access public`（同じ版が既にあれば skip。2 段階認証を使わない場合は `-Token` に npm のトークンを渡す）
5. `gh repo create ... --push`、`git tag`、タグ push

`-DryRun` を付けると 4 以降を実行せず、何をするかだけ表示します。

</details>

## ライセンス

MIT。サードパーティの扱いは [THIRD-PARTY.md](THIRD-PARTY.md) を参照してください。
本パッケージは VRChat Inc. / Unity Technologies / 各 VPM パッケージ作者とは無関係です。
