# dsh-vrc-unity-supporter

日本語 | [English](README.en.md) | [简体中文](README.zh-CN.md) | [한국어](README.ko.md)

このプラグインは、AI エージェントを使って VRChat のアバター改変を行うためのものです。

## 導入方法

### AI エージェントに任せる（おすすめ）

DSH、Claude Code、Codex のどれかのチャットに次の文章をそのまま貼り付けて送ってください。足りないものの確認、プラグインの導入、最初の確認までエージェントが順に案内します。

```text
VRChat のアバター改変に「dsh-vrc-unity-supporter」というプラグインを使いたいです。
Windows の PC で、導入から最初の確認までを次の順に手伝ってください。
1 つずつ進め、私の操作が必要なところでは待ってください。

1. 次が入っているかを、コマンドで調べてください。
   Git / Python 3.10 以上 / Unity Hub と Unity 2022.3.22f1 / VCC または ALCOM
   足りないものは公式のダウンロード先を示し、私が入れるのを待ってください。
   あなたがインストールすることはしないでください。
2. 今使っているアプリが DeepSeek Harness、Claude Code、Codex のどれかを確認し、プラグインを入れてください。
   - Claude Code の場合（デスクトップアプリを含む）:
     次の 2 つを PowerShell で実行してよいか私に聞いてから、実行してください。
       claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
       claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
     claude コマンドが見つからないときは、https://code.claude.com/docs/en/setup の
     Windows 向けの手順を示し、私が入れるのを待ってください。
   - Codex の場合:
     次を PowerShell で実行してよいか私に聞いてから、実行してください。
       codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
     そのあと、Codex のアプリの Plugins で「VRChat Avatar (Unity)」を入れる操作を私に案内してください。
     codex コマンドが見つからないときは、https://developers.openai.com/codex/ の手順を示し、
     私が入れるのを待ってください。
   - DeepSeek Harness の場合:
     Plugins → Add plugin に「dsh-vrc-unity-supporter」を入れる操作を私に案内してください。
3. 改変したい Unity プロジェクトのフォルダ（Assets と ProjectSettings があるフォルダ）を私に聞いてください。
4. 最後に、そのフォルダで新しいセッションを始め、次の一文を送るよう私に伝えてください。
   「このプロジェクトのアバター構成を調べて」

ここまでの間、Unity プロジェクトのファイルは変更しないでください。

GithubリポジトリURL：https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/tree/master
```

プラグインは入れたあとに始めた新しいセッションから使えます。

### DSH で導入する

1. DSH を開き、**Plugins** → **Add plugin** を選びます。
2. 入力欄に次のパッケージ名を貼り付け、インストールします。

   ```text
   dsh-vrc-unity-supporter
   ```

3. **新しいセッション** を作り、プリセットの一覧に **VRChat Avatar** が表示されることを確認します。

<details>
<summary>ZIP から導入する場合</summary>

1. この GitHub ページの **Code** → **Download ZIP** を選びます。
2. ダウンロードした ZIP を右クリックして **すべて展開** を選びます。
3. DSH を終了し、展開したフォルダにある **`install.cmd`** をダブルクリックします。
4. 「完了しました」と表示されたら、DSH を起動し直して **新しいセッション** で **VRChat Avatar** を選びます。

`install.cmd` は DSH に同梱されたコマンドを使い、npm から公開版を取得してインストールします。インストール時はインターネットに接続してください。 [インストーラーの詳細と削除方法](installer/README.md)

</details>

### Claude Code で導入する

Claude Code は**Claude デスクトップアプリの Code タブ** とターミナル版のどちらでも使えます。

**デスクトップアプリを使っている場合**

1. PowerShell を開き、次の 2 つを順に実行します。

   ```powershell
   claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   ```powershell
   claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
   ```

   「claude が見つからない」と表示されたら、[Claude Code のセットアップ](https://code.claude.com/docs/en/setup) の Windows 向けの手順で `claude` コマンドを入れてから、もう一度実行します。
2. デスクトップアプリの **Code** タブで、Unity プロジェクトのフォルダを選んで新しいセッションを始めます。
3. プロンプト欄の横の **+** → **Plugins** → **Manage plugins** に `dsh-vrc-unity-supporter` が表示され、有効になっていることを確認します。

**ターミナル版を使っている場合**

Unity プロジェクトのフォルダで Claude Code を開き、次を順に実行します。

```text
/plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
/plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
```

入れたあとに `/reload-plugins` を実行するか、新しいセッションを始めます。

### Codex で導入する

1. PowerShell を開き、次を実行してマーケットプレイスを追加します。

   ```powershell
   codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   「codex が見つからない」と表示されたら、[Codex のドキュメント](https://developers.openai.com/codex/) の手順で `codex` コマンドを入れてから、もう一度実行します。
2. Codex のアプリを開き直し、**Plugins** でマーケットプレイス `dsh-vrc-unity-supporter` を選んで **VRChat Avatar (Unity)** をインストールします。
3. Unity プロジェクトのフォルダで新しいスレッドを始めます。

Codex では、スキルのコマンドがサンドボックスの中で動きます。Unity や Blender の実行で、サンドボックスの外で実行してよいかを聞かれることがあります。何を実行するかを確かめてから承認してください。

### 必要なもの

AI エージェントに任せる場合は、エージェントが確認します。手動で準備する場合は、Windows で次をそろえてください。

| 必要なもの | 準備すること |
| --- | --- |
| **DeepSeek Harness Desktop、Claude Code、Codex のどれか** | DSH は公式サイトの **Download Desktop → Windows (64-bit)** からインストールし、画面の案内に沿って初期設定を済ませます。Claude Code はデスクトップアプリかターミナル版を使います。Codex はアプリと `codex` コマンドを使います。[DSH 公式サイト](https://www.deepseek.com/en/harness/) · [Claude Code の概要](https://code.claude.com/docs/en/overview) · [Codex のドキュメント](https://developers.openai.com/codex/) |
| **Git for Windows** | 改変前の状態を記録し、あとで元に戻すために使います。記録は PC の中で完結します。 [Git のダウンロード](https://git-scm.com/install/win) |
| **Python 3.10 以上** | アバターの構成を調べるために使います。インストール後、使っているアプリ（DSH、Claude Code、Codex）を開き直してください。 [Python の Windows 向けダウンロード](https://www.python.org/downloads/windows/) |
| **Unity Hub と Unity 2022.3.22f1** | Unity Hub で有効なライセンスを設定し、指定のバージョンでプロジェクトを開けることを確認します。 [VRChat 公式の Unity 導入案内](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) |
| **VCC または ALCOM とアバタープロジェクト** | 普段使っている管理アプリをどちらか一つ使います。作業対象は **VRChat SDK - Avatars** が導入済みで、Unity で開けるプロジェクトです。 [VCC のセットアップ](https://vcc.docs.vrchat.com/guides/getting-started/) · [ALCOM のダウンロード](https://vrc-get.anatawa12.com/alcom/) |

機能によっては、ほかにも必要なものがあります（VRCFury、Modular Avatar、Avatar Optimizer、PhotoCraft、Blender）。[できること](#できること) の表を見てください。

## 試すこと

1. 改変したい Unity プロジェクトのフォルダを開きます。`Assets`、`Packages`、`ProjectSettings` が並んでいるフォルダです。DSH ではワークスペースとして、Claude Code と Codex では作業フォルダとして開きます。
2. DSH では、新しいセッションのプリセットを **VRChat Avatar**、モデルを **DeepSeek V4.1 Flash**、エフォートを **MAX** にします。Claude Code では新しいセッション、Codex では新しいスレッドを始めるだけです。
3. チャットに次の一文を送ります。この段階では、プロジェクトのファイルを読むだけです。

   ```text
   このプロジェクトのアバター構成を調べて
   ```

4. アバターと衣装が確認できたら、衣装名を自分のプロジェクトのものに置き換えて頼みます。適用の前に、シーンを保存して Unity を閉じてください。

   ```text
   Outfit_Hoodie を「衣装/パーカー」からオン・オフできるようにして。初期状態はオンで
   ```

5. エージェントが対象と変更予定を示すので、確認してから適用を頼みます。衣装名が曖昧なときは、保存済みのシーンから候補を出して聞いてきます。
6. 適用すると、保存の結果と、SDK の前処理でメニューとアニメーションを確認できたかが表示されます。VRChat の中で試すときは、Unity で **VRChat SDK → Show Control Panel → Builder → Offline Testing → Build & Test** を選びます。VRChat の **SDK Test Avatars** でテスト用アバターを選び、メニューから衣装をオン・オフしてください。 [VRChat のローカルテスト手順](https://creators.vrchat.com/avatars/#local-avatar-testing)

## できること

| できること | 頼み方の例 | 追加で必要なもの |
| --- | --- | --- |
| アバターの構成を調べる | 「このプロジェクトのアバター構成を調べて」 | なし |
| 衣装をメニューで切り替える | 「Outfit_Hoodie を『衣装/パーカー』からオン・オフできるようにして」 | VRCFury |
| 色違いを作る | 「パーカーを紺色にした色違いを作って」 | PhotoCraft、アバター付属の PSD |
| lilToon の色・影・輪郭線を調整する | 「髪の影を薄くして、輪郭線を細くして」 | VRCFury、lilToon か Poiyomi のマテリアル |
| 体型の調整と貫通の修正 | 「服の下の体を消して、胸を少し大きくして」 | Modular Avatar、Avatar Optimizer |
| 小物・髪・衣装を付ける | 「このウルフヘアを付けて」 | Modular Avatar |
| Blender で作る・非対応衣装を着せる | 「Selestia 用のこのコートを Salt に着せて」 | Blender、Modular Avatar |
| 性能ランクを調べる | 「性能ランクを調べて」 | なし |

VRCFury、Modular Avatar、Avatar Optimizer は、VCC または ALCOM で対象のプロジェクトに入れます。 [VRCFury の導入手順](https://vrcfury.com/download/)

### 衣装をメニューで切り替える

シーンに配置した衣装を、VRChat のメニューからオン・オフできるようにします。アバターと衣装を同じシーンに配置して保存しておいてください。

```text
Outfit_Hoodie を「衣装/パーカー」からオン・オフできるようにして。初期状態はオンで
```

- **1 着だけ着る**：「パーカーとコートを、どちらか 1 着だけ着るように切り替えられるようにして」と頼むと、同じグループのトグルになります。片方をオンにすると、もう片方がオフになります。
- **一覧と取り外し**：作ったトグルは「衣装トグルを一覧にして」で確認できます。「パーカーのトグルを外して」と頼むと、そのトグルだけを外します（衣装そのものは残ります）。

### 色違いを作る

アバターや衣装に付属している、レイヤー分けされた PSD から色違いを作ります。衣装・肌・髪・瞳の色を変えたり、自分で用意したロゴや柄を入れたりできます。元の PSD・テクスチャ・マテリアルはそのまま残り、色違いは別のマテリアルとして追加されます。メニューから元の見た目と切り替えられます。

```text
パーカーを紺色にした色違いを作って。PSD は Downloads\Salt_v1.0.1 にあります
```

エージェントは PSD のレイヤー構成を調べ、どのレイヤーをどう変えるかを示してから書き出します。続いて Unity でアバターを撮影し、改変前と改変後を並べた画像で確認します。作った色違いは「色違いを一覧にして」で確認でき、「Hoodie_Blue の色違いを削除して」で外せます。

- 無料の画像編集ソフト **PhotoCraft** を入れておきます。PSD の編集はコマンドラインで行うので、画面を開く必要はありません。 [PhotoCraft のダウンロード](https://getartcraft.com/apps/photocraft) · [詳しい使い方](docs/PHOTOCRAFT.md)
- 付属 PSD から作ったテクスチャは、多くのアバターの利用規約で配布が禁止されています。プロジェクトの中でだけ使ってください。

### lilToon の色・影・輪郭線を調整する

PSD が無い衣装や髪でも、lilToon のマテリアルの値で見た目を調整できます。Poiyomi Toon（9・10、ロックしていないもの）のマテリアルにも使えます。変えられるのは、主色と色調補正（色相・彩度・明るさ）、影の色と強さ、輪郭線の色と太さ、発光、リムライト、マットキャップ、明るさの上限と下限です。元のマテリアルはそのまま残り、値を変えた複製が追加されます。メニューから元の見た目と切り替えられます。

```text
髪の影を薄くして、輪郭線を細くして。ずっとこの見た目にしたい
```

エージェントは、今表示されている髪や衣装のマテリアルと今の値を調べ、変える値（前 → 後）を示します。続いて改変前後を並べた画像で確認し、確認を取ってから適用します。「ずっとこの見た目に」と頼むと、初期状態をオンにします（メニューでオフにすると元に戻ります）。外し方は色違いと同じです。

- 黒・白・灰色の髪や服は、色そのものが無いため、色相や彩度を変えてもほとんど変わりません。明るさやリムライト・輪郭線で調整するか、PSD から色違いを作ってください。
- 描画モード、透過、ステンシルのような値は変えません。lilToon と Poiyomi 以外のシェーダー（UnityChan Toon Shader など）には、まだ対応していません。

### 体型の調整と貫通の修正

FBX を変えずに、アバターの形を調整します。

- **体型・顔**：アバターに付属のシェイプキー（胸の大きさ、ウエストなど）の値を変えます。
- **衣装の追従**：体型を変えたときに、衣装の対応するシェイプキーが体に合わせて動くようにします（Modular Avatar の Blendshape Sync）。
- **隠れる部分の削除**：服の下に隠れる体のメッシュを、ビルド時に削除します（Avatar Optimizer の Remove Mesh By BlendShape）。貫通が起きにくくなり、ポリゴン数も減ります。

```text
パーカーを着ているときに服の下の体を消して、胸を少し大きくして
```

エージェントがシェイプキーを調べて、変える値と消す部位を示します。そのうえで、VRChat と同じようにビルドした改変前後の画像と三角形数を見せ、確認を取ってから適用します。「Fit_Hoodie の体型調整を元に戻して」で戻せます。戻すのはこのプラグインが変えた値と足した設定だけで、アバターに最初から入っていた連動は残ります。

### 小物・髪・衣装を付ける

既存の帽子・髪・小物・衣装（prefab や FBX）を、アバターに付けます。

- **ボーンに付ける**：帽子やリボン、アバター用の髪を、頭などのボーンに付けます（Modular Avatar の Bone Proxy）。
- **骨組みを統合する**：衣装のように骨組みを持つものは、アバターの骨組みに統合します（Modular Avatar の Setup Outfit）。
- **メニューで出し入れ**：付けた小物をメニューでオン・オフでき、付けている間だけ元の髪などを隠せます。

```text
このウルフヘアを付けて、元の髪はメニューで切り替えられるようにして
```

エージェントが候補とボーンを調べて付け方を示し、VRChat と同じようにビルドした改変前後の画像で位置を確かめてから、確認を取って適用します。「付けた小物を一覧にして」「WolfHair を外して」とも頼めます。

### Blender で作る・非対応衣装を着せる

**Blender** を入れておくと、次のこともできます。Blender はバックグラウンドで動くので、画面は開きません。

- **簡単な形を作る**：球・立方体・円柱・円錐・輪を組み合わせて、リボンや角のような小物を作ります。
- **非対応の衣装を着せる**：別のアバター用に作られた髪や衣装を、このアバターの骨格に合わせて変形し、体にめり込んだ部分を外へ押し出します。衣装が作られた元のアバターの FBX があれば、胸・腰・腕の太さなどの体型差も衣装に写します。アバターの体型キー（`Breasts_big` など）を衣装にも作るので、体型を変えても衣装が追従します。付けたあとは、服の下に隠れる体の削除と、ビルドした前後の撮影まで続けて行います。

```text
Selestia 用のこのコートを Salt に着せて。元の素体は Assets/Booth/SELESTIA.fbx にある
```

自動で合わせられるのは、骨格の位置・向き・長さ、元のアバターとの体型差、体からの押し出し、体型キーの追従までです。丈や体型の差が大きい部分は、Blender での手作業が必要になることがあります。他アバター用の衣装を使ってよいかは、それぞれの利用規約を確認してください。

Blender は [blender.org](https://www.blender.org/download/) から無料で入れられます（`winget install BlenderFoundation.Blender` でも可）。

### 性能ランクを調べる

「性能ランクを調べて」と頼むと、PC と Mobile の性能ランクと、ランクを決めている項目（たとえばスキンメッシュの数）、1 つ上のランクにするための目安を示します。ビルド前の元の prefab で数えた目安なので、最終的なランクは VRChat SDK のビルド画面で確認してください。

## 安全のしくみと元に戻す方法

- **最初は読むだけ**：構成を調べる段階では、プロジェクトのファイルを読むだけです。Unity の起動や Git での記録は、改変を適用するときに行います。
- **適用の前に確認**：エージェントは、対象、変更予定、作られるファイルを示してから適用します。確認したあとにシーンやレシピが変わったときは、もう一度確認を取ります。
- **Git の復元地点**：初めて Git を使うプロジェクトでは、PC 上に復元地点を作る手順が案内されます。すでに Git で管理しているプロジェクトに記録していない変更があるときは、先に記録するよう求められます。
- **Unity は閉じておく**：適用と撮影では、Unity を別に起動して作業します。対象のプロジェクトを開いている Unity は、シーンを保存して閉じてください。
- **失敗したら元の状態に戻す**：Unity での保存後の確認に失敗したときは、シーンを実行前の状態に戻します。
- **続けて改変できる**：このプラグインで保存・確認したシーンは、手作業の変更が加わるまでは、Git に記録し直さずに続けて改変できます。

このプラグインで加えた変更は、次のように頼むと戻せます。外す前には、何を戻すかの確認があります。

| 戻したいもの | 頼み方の例 |
| --- | --- |
| 衣装トグル | 「パーカーのトグルを外して」 |
| 色違い・lilToon の調整 | 「Hoodie_Blue の色違いを削除して」 |
| 体型の調整 | 「Fit_Hoodie の体型調整を元に戻して」 |
| 小物・髪 | 「WolfHair を外して」 |

それ以外の変更は、Git の復元地点からシーンを戻します。戻し方はチャットで聞いてください。

## 動作確認環境

| 項目 | DSH | Claude Code |
| --- | --- | --- |
| アプリ | DeepSeek Harness Desktop（Windows） | Claude デスクトップアプリ |
| モデル | DeepSeek V4.1 Flash（画面表示例 `DeepSeek-V41-Flash`） | Opus 5.5 |
| エフォート（推論の強さ） | `MAX` | 中以上 |

上記以外の組み合わせでの動作は確認していません。Codex 版はまだ動作を確認していません。

## 困ったとき

- **VRChat Avatar が表示されない**。Plugins でプラグインが入っていることを確認し、DSH で新しいセッションを作ります。
- **Claude Code でスキルが使われない**。デスクトップアプリでは **+** → **Plugins** → **Manage plugins**、ターミナル版では `/plugin` で、`dsh-vrc-unity-supporter` が有効になっているか確認します。そのうえで新しいセッションを始めます（ターミナル版は `/reload-plugins` でも可）。
- **「claude が見つからない」と表示される**。[Claude Code のセットアップ](https://code.claude.com/docs/en/setup) の Windows 向けの手順で `claude` コマンドを入れ、PowerShell を開き直します。
- **Codex でスキルが使われない**。Codex のアプリの **Plugins** で **VRChat Avatar (Unity)** がインストールされているか確認し、新しいスレッドを始めます。最新版にするには `codex plugin marketplace upgrade dsh-vrc-unity-supporter` を実行します。
- **Codex で Unity の実行が途中で止まる**。初回のコンパイルには数分かかります。Unity がまだ動いていることがあるので、チャットで「Unity がまだ動いているか確認して」と頼んでから、もう一度頼んでください。
- **プロジェクトが見つからない**。使っているアプリで開いているフォルダに `Assets` と `ProjectSettings` があるか確認します。
- **「Blender was not found」と表示される**。Blender をインストールし、使っているアプリを開き直します。別の場所に入れた場合は、環境変数 `DSH_BLENDER` に `blender.exe` のフルパスを設定します。
- **色違いで「PhotoCraft CLI was not found」と表示される**。PhotoCraft をインストールし、使っているアプリを開き直します。別の場所に入れた場合は、環境変数 `PHOTOCRAFT_CLI` に `photocraft-cli.exe` のフルパスを設定します。
- **撮影（改変前後の画像）が失敗する**。撮影では GPU を使って Unity を起動します。Unity を閉じてから再度頼み、それでも失敗する場合は、チャットに表示されたログの場所を確認してください。
- **体型の調整を戻せない**。0.10.0 より前に適用した体型の調整には、戻すための記録がありません。Git の復元地点からシーンを戻してください。
- **Git の名前やメールアドレスを求められた**。チャットで「このプロジェクトで Git の名前とメールアドレスを設定する方法を教えて」と聞いてください。
- **インストーラーが途中で止まる**。DSH をタスクトレイからも終了し、画面に表示されたエラーを確認してください。 [インストーラーのトラブル対処](installer/README.md#うまくいかないとき)
- **プラグインが 0.2.0 のまま**。最新版に更新してください。0.2.0 では Editor スクリプトの初期配置を手動で行う必要があります。 [0.2.0 のセットアップ手順](https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/blob/v0.2.0/README.md#プロジェクトへの初期配置)

<details>
<summary>メンテナー向けのテストと公開手順</summary>

Windows で `python -B -m unittest discover -s tests -v` を実行すると、読み取り、衣装トグル、色違い、体型、小物、Blender の CLI の回帰テストを実行できます（Unity・Blender・PhotoCraft は偽物を使うので不要です）。Unity 2022.3.22f1 が入っている PC では、`templates/Editor/` のヘルパーを Unity の DLL に対してコンパイルするテストも動きます（無い PC では skip）。GitHub では push と PR のたびに `.github/workflows/ci.yml` が Windows と Python 3.10 / 3.13 で同じテストと `verify-package.ps1` を回します。Claude Code 版のマニフェストは `claude plugin validate . --strict` で確認できます。版を上げるときは `package.json`、`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json` を揃えます（`verify-package.ps1` が照合します）。Codex 版はマニフェストが `.codex-plugin/plugin.json`、マーケットプレイスが `.agents/plugins/marketplace.json`、入口スキルが `codex/skills/vrc-avatar/` です。共有スキルは `skills/` にあり、Claude Code 用の入口スキル（`claude/skills/vrc-avatar/`）と Codex 用の入口スキルは、どちらも全スキルへの案内を載せます。BOOTH で配る ZIP は、コミットしてから `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-booth.ps1` で `dist/booth/` に作ります（ZIP の中の説明は `booth/00_README_JA.txt`、商品ページの下書きは `booth/LISTING.md`）。独自の Editor スクリプトを使う場合は `templates/Editor/` のヘルパーを `Assets/DSH/Editor/` に配置します。`templates/AGENTS.template.md` は任意のプロジェクトメモです。

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
