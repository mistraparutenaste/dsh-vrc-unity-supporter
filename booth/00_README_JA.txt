VRChat Avatar (Unity) - dsh-vrc-unity-supporter  版 {{VERSION}}
====================================================================

AI エージェント（DeepSeek Harness / Claude Code / Codex）に、VRChat アバターの
改変を手伝わせるためのプラグインです。Unity を開かずにプロジェクトを調べ、
変更は Unity の Editor スクリプトで適用し、結果を確認します。アップロードはしません。


■ はじめに必ず確認してください
--------------------------------------------------------------------

・このプラグインは 0 円ですが、使うには AI エージェントのアプリと、
  その利用料（有料プランや API の料金）が別に必要です。

・対応している Unity は 2022.3.22f1 です（VRChat SDK の作成側の対応版）。
  Unity 6 のプロジェクトには対応していません。

・改変の前に、プロジェクトのバックアップを取ってください。
  プラグインは適用の前に Git で復元地点を作り、内容を見せて承認を求めますが、
  すべての失敗を防げるわけではありません。


■ 必要なもの（Windows 10 / 11）
--------------------------------------------------------------------

  ・AI エージェントのアプリ（どれか 1 つ）
      DeepSeek Harness Desktop / Claude Code / Codex
  ・Git for Windows
  ・Python 3.10 以上
  ・Unity Hub と Unity 2022.3.22f1（ライセンスを有効にしたもの）
  ・VCC または ALCOM で管理している、VRChat SDK - Avatars 入りのプロジェクト

  機能によっては、VRCFury、Modular Avatar、Avatar Optimizer、
  PhotoCraft、Blender も必要です。


■ 展開する前に
--------------------------------------------------------------------

  ダウンロードした ZIP を右クリック → プロパティ → 下の「許可する」に
  チェック → OK を押してから展開してください。
  展開したフォルダは、消さない場所（例: ドキュメントの中）に置いてください。
  Claude Code と Codex は、このフォルダからプラグインを読み込みます。


■ 導入方法
--------------------------------------------------------------------

いちばん簡単なのは、AI エージェントに任せる方法です。
README.md の「AI エージェントに任せる（おすすめ）」の文章を、
使っているアプリのチャットに貼り付けて送ってください。

自分で入れる場合は、使っているアプリに合わせて次のどれかを行います。
以下の <フォルダ> は、この README があるフォルダのフルパスに置き換えます
（フォルダを Shift + 右クリック →「パスのコピー」で取得できます）。

[DeepSeek Harness]
  1. DeepSeek Harness を終了します（タスクトレイからも）。
  2. このフォルダの install.cmd をダブルクリックします。
  3. 「完了しました」と出たら起動し、新しいセッションで
     プリセット「VRChat Avatar」を選びます。
  ※ install.cmd はインターネット（npm）から公開版を取得します。
    この ZIP より新しい版が入ることがあります。

[Claude Code]
  PowerShell で次の 2 つを順に実行し、新しいセッションを始めます。

    claude plugin marketplace add "<フォルダ>"
    claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter

[Codex]
  PowerShell で次を実行し、Codex のアプリを開き直して、
  Plugins から「VRChat Avatar (Unity)」をインストールします。

    codex plugin marketplace add "<フォルダ>"

  ※ Codex 版は、モデル sol6.1・エフォート「中」で動作を確認しています。

自動で新しい版を受け取りたい場合は、<フォルダ> の代わりに
  mistraparutenaste/dsh-vrc-unity-supporter
を指定すると、GitHub から入れられます。


■ 新しい版に更新する
--------------------------------------------------------------------

  1. 新しい ZIP を展開し、中の dsh-vrc-unity-supporter フォルダで、
     前に置いたフォルダを丸ごと置き換えます（場所は変えないでください）。
  2. 使っているアプリに合わせて、PowerShell で次を実行します。

  [Claude Code]
    claude plugin marketplace update dsh-vrc-unity-supporter
    claude plugin update dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
  [Codex]
    codex plugin marketplace upgrade dsh-vrc-unity-supporter
  [DeepSeek Harness]
    Plugins で dsh-vrc-unity-supporter を更新します。

  3. 新しいセッション（Codex では新しいスレッド）を始めます。


■ 最初に試すこと
--------------------------------------------------------------------

  1. 改変したい Unity プロジェクトのフォルダ（Assets と ProjectSettings が
     あるフォルダ）を、アプリの作業フォルダとして開きます。
  2. チャットに「このプロジェクトのアバター構成を調べて」と送ります。
     この段階では、プロジェクトのファイルを読むだけです。
  3. 改変を頼むときは、Unity でシーンを保存して Unity を閉じてください。

  詳しい使い方は README.md を見てください。


■ 動作の確認状況（版 {{VERSION}} の時点）
--------------------------------------------------------------------

作者の環境（Windows 11、Unity 2022.3.22f1、VRCFury 1.1475.0、
Modular Avatar 1.18.7、Avatar Optimizer 1.9.23）で確認したこと:

  ・プロジェクトの診断（複数のアバターのプロジェクト）
  ・配置済みの衣装のトグル、トグルの取り外し
  ・小物・髪をボーンに付ける、外す
  ・別アバター用の衣装を Blender で合わせて着せる（肩・袖・靴の位置）
  ・衣装に付属の PSD から色違いを作る、一覧・削除
  ・lilToon・Poiyomi の値を変えた複製（色調補正・リムライト・輪郭線）の
    撮影比較とメニューへの適用（lilToon 2.4.1、Poiyomi Toon 10.0.30）
  ・別アバター用の髪を合わせて付ける、汎用の帽子を頭に合わせて付ける
  ・着せた衣装を、腕を下ろす・座る・腕を上げる姿勢で撮影しての貫通の確認
  ・体型の調整、服の下に隠れる体の削除、その取り消し
  ・性能ランクの試算
  ・Codex 版（モデル sol6.1、エフォート「中」）での動作
  いずれも、Unity での適用と SDK の前処理（ビルド）までを確認しています。

まだ確認していないこと:

  ・VRChat の中での見た目と動き（アップロードして確かめるのは利用者です）
  ・排他トグル（片方をオンにすると片方がオフ）の、Gesture Manager や
    VRChat の中での動き
  ・肌・髪・瞳の PSD からの色違い
  ・別アバター用の衣装に Blendshape Sync を付けて、服の下の体を消す手順
  ・軽量化（Avatar Optimizer の Trace and Optimize、TexTransTool の
    テクスチャ縮小・マテリアル統合）と、Inspector の値の読み取り
    （どちらも版 0.22.0 で追加）
  ・lilToon・Poiyomi の調整の、VRChat の中での見た目
  ・Poiyomi のアップロード時の自動ロック（ロックの処理そのものは確認済み）

確認したアバターは限られています。ほかのアバターや衣装では、
うまくいかないことがあります。


■ 困ったとき・問い合わせ
--------------------------------------------------------------------

  README.md の「困ったとき」を見てください。
  不具合の報告は、次のどちらかにお願いします。
    ・GitHub の Issues
      https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/issues
    ・BOOTH のメッセージ
  返信や修正の時期は約束できません。


■ ライセンス・免責
--------------------------------------------------------------------

  ・MIT ライセンスです（LICENSE）。改変・再配布できます。
  ・無保証です。使用によって生じた損害について、作者は責任を負いません。
  ・このプラグインは、VRChat Inc.、Unity Technologies、各パッケージの
    作者とは関係がありません。VRChat と Unity は各社の商標です。
  ・アバター・衣装・髪などの素材は含みません。素材の利用規約は、
    それぞれの作者の規約に従ってください。付属の PSD から作った
    テクスチャなど、素材から作ったものを配布しないでください。
  ・このプラグインは、AI の支援を受けて開発しています。
