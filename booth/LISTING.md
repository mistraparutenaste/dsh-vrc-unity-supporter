# BOOTH 出品の下書き

BOOTH の商品編集画面に貼り付けるための下書き。ZIP には入らない。
`[要確認]` は出品する人が決めるか、BOOTH の画面で確かめるところ。

## 基本情報

| 項目 | 値 |
|---|---|
| 商品名 | VRChat アバター改変を AI に任せるプラグイン「VRChat Avatar (Unity)」 |
| 価格 | 0 円 |
| カテゴリ | [要確認] 3D モデル → 3D ツール・システム（VRChat 向けツールがよく置かれる場所） |
| タグ | VRChat / Unity / アバター改変 / Modular Avatar / VRCFury / AvatarOptimizer / 生成AI / Claude Code / Codex / 無料 |
| ダウンロードファイル | `dist/booth/dsh-vrc-unity-supporter-<版>.zip`（`tools/build-booth.ps1` で作る） |
| サムネイル | [要確認] `docs/preview.svg` を PNG にしたもの、または実際の改変前後の画像（アバター作者の規約で掲載してよいものだけ） |
| AI に関する表示 | [要確認] BOOTH の出品画面とガイドラインで、生成 AI の利用の申告が要るかを確かめる。要らなくても、下の説明文の「AI について」は残す |

## 商品説明（ここから下を貼り付ける）

AI エージェントに、VRChat アバターの改変を手伝わせるためのプラグインです。
DeepSeek Harness・Claude Code・Codex で使えます。

「このプロジェクトのアバター構成を調べて」「パーカーをメニューで切り替えたい」のように頼むと、AI が Unity のプロジェクトを調べ、変更の内容を示して確認を取り、Unity の Editor スクリプトで適用し、結果を確かめます。

### ⚠ はじめに

- **このプラグインは 0 円ですが、AI エージェントの利用料は別にかかります。** Claude Code・Codex は有料プラン、DeepSeek Harness は API の利用料が必要です。
- 対応する Unity は **2022.3.22f1** です。Unity 6 のプロジェクトには対応していません。
- Windows 10 / 11 専用です。
- 改変の前に、プロジェクトのバックアップを取ってください。

### できること

- プロジェクトの診断（アバター、導入済みパッケージ、参照切れ）
- 配置済みの衣装をメニューでオン・オフ（VRCFury）
- 衣装に付属の PSD から色違いを作る（PhotoCraft）
- 体型の調整、服の下に隠れる体の削除（Modular Avatar・Avatar Optimizer）
- 小物・髪をボーンに付ける、外す（Modular Avatar）
- 別アバター用の衣装を Blender で合わせて着せる（Blender）
- 性能ランクの試算、アップロード前のチェックリスト

アップロードはしません。VRChat SDK でのアップロードは、ご自身で行ってください。

### 安全のしくみ

- 変更の前に、内容と作られるファイルを示して、承認を求めます。
- 変更の前に、Git で復元地点を作ります。
- シーンやプレハブのファイルを直接書き換えません。変更は Unity の Editor スクリプトで行います。
- Unity が起動中のときは、変更を始めません。

### 必要なもの

- AI エージェントのアプリ（DeepSeek Harness Desktop / Claude Code / Codex のどれか）
- Git for Windows、Python 3.10 以上
- Unity Hub と Unity 2022.3.22f1
- VCC または ALCOM で管理している、VRChat SDK - Avatars 入りのプロジェクト
- 機能によって: VRCFury、Modular Avatar、Avatar Optimizer、PhotoCraft、Blender

### 導入方法

ZIP の中の `00_README_JA.txt` を見てください。AI エージェントのチャットに文章を貼り付けて、導入を任せることもできます。

### 動作の確認状況

作者の環境（Unity 2022.3.22f1、VRCFury 1.1475.0、Modular Avatar 1.18.7、Avatar Optimizer 1.9.23）で、上の機能を Unity での適用と SDK の前処理まで確認しています。確認したアバターは限られていて、ほかのアバターや衣装ではうまくいかないことがあります。

まだ確認していないことは、`00_README_JA.txt` の「動作の確認状況」に書いています。特に **Codex 版は、まだ作者の環境で動作を確認していません**。

### AI について

このプラグインは AI エージェントで使うための道具で、開発にも AI の支援を受けています。アバターや衣装などの素材は含みません。

### サポート・免責

- 不具合の報告は GitHub の Issues か、BOOTH のメッセージにお願いします。返信や修正の時期は約束できません。 [要確認: 受け付ける窓口]
- MIT ライセンスです。無保証で、使用によって生じた損害について作者は責任を負いません。
- VRChat Inc.、Unity Technologies、各パッケージの作者とは関係ありません。

ソースコードと最新版: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter
