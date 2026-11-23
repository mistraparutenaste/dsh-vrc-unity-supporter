# BOOTH 出品の下書き

BOOTH の商品編集画面に貼り付けるための下書き。ZIP には入らない。
`[要確認]` は出品する人が決めるか、BOOTH の画面で確かめるところ。
商品説明は日本語のあとに English・中文（简体）・한국어 を続けている。日本語を変えたら、3 つの言語も合わせて直す。

## 基本情報

| 項目 | 値 |
|---|---|
| 商品名 | VRChat アバター改変を AI に任せるプラグイン「VRChat Avatar (Unity)」 |
| 価格 | 0 円 |
| カテゴリ | [要確認] 3D モデル → 3D ツール・システム（VRChat 向けツールがよく置かれる場所） |
| タグ | VRChat / Unity / アバター改変 / Modular Avatar / VRCFury / AvatarOptimizer / 生成AI / Claude Code / Codex / 無料 |
| ダウンロードファイル | `dist/booth/dsh-vrc-unity-supporter-<版>.zip`（`tools/build-booth.ps1` で作る） |
| サムネイル | [要確認] `docs/preview.svg` を PNG にしたもの、または実際の改変前後の画像（アバター作者の規約で掲載してよいものだけ） |
| 説明文の長さ | [要確認] 4 言語を続けて約 1 万字。BOOTH の商品説明の文字数の上限に収まるかを、貼り付けて確かめる。収まらなければ、各言語の「必要なもの」を短くする |
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
- lilToon の色・影・輪郭線・発光を、マテリアルの値で調整する（PSD 不要）
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

作者の環境（Unity 2022.3.22f1、VRCFury 1.1475.0、Modular Avatar 1.18.7、Avatar Optimizer 1.9.23）で、上の機能を Unity での適用と SDK の前処理まで確認しています（lilToon の調整は、改変前後の撮影での比較まで）。確認したアバターは限られていて、ほかのアバターや衣装ではうまくいかないことがあります。

まだ確認していないことは、`00_README_JA.txt` の「動作の確認状況」に書いています。特に **Codex 版は、まだ作者の環境で動作を確認していません**。

### AI について

このプラグインは AI エージェントで使うための道具で、開発にも AI の支援を受けています。アバターや衣装などの素材は含みません。

### サポート・免責

- 不具合の報告は GitHub の Issues か、BOOTH のメッセージにお願いします。返信や修正の時期は約束できません。 [要確認: 受け付ける窓口]
- MIT ライセンスです。無保証で、使用によって生じた損害について作者は責任を負いません。
- VRChat Inc.、Unity Technologies、各パッケージの作者とは関係ありません。

ソースコードと最新版: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter

---

## English

A plugin that lets an AI agent help you modify VRChat avatars.
It works with DeepSeek Harness, Claude Code and Codex.

Ask things like "Look into the avatars in this project" or "I want to switch the hoodie on and off from the menu". The AI reads your Unity project, shows what it will change and asks for your approval, applies the change with a Unity Editor script, and checks the result.

### ⚠ Before you start

- **The plugin is free, but the AI agent is not.** Claude Code and Codex need a paid plan; DeepSeek Harness needs API credits.
- It supports **Unity 2022.3.22f1** only. Unity 6 projects are not supported.
- Windows 10 / 11 only.
- Back up your project before making changes.
- The agent answers in Japanese by default. Write to it in your own language and it answers in that language.

### What it can do

- Diagnose a project (avatars, installed packages, missing references)
- Switch outfits already placed in the scene on and off from the menu (VRCFury)
- Make color variants from the layered PSD that comes with an outfit (PhotoCraft)
- Adjust lilToon colors, shadows, outlines and emission through material values (no PSD needed)
- Adjust body shape, and remove body parts hidden under clothes (Modular Avatar, Avatar Optimizer)
- Attach accessories and hair to bones, and remove them (Modular Avatar)
- Fit an outfit made for another avatar in Blender and dress your avatar in it (Blender)
- Estimate the performance rank, and give a pre-upload checklist

It does not upload. Upload with the VRChat SDK yourself.

### How it keeps your project safe

- Before any change, it shows what will change and which files will be created, and asks for your approval.
- Before any change, it makes a restore point with Git.
- It never edits scene or prefab files directly. Changes are made by Unity Editor scripts.
- It does not start a change while Unity is open on the project.

### Requirements

- An AI agent app (one of DeepSeek Harness Desktop / Claude Code / Codex)
- Git for Windows, Python 3.10 or later
- Unity Hub and Unity 2022.3.22f1
- A project managed with VCC or ALCOM that has VRChat SDK - Avatars
- Depending on the feature: VRCFury, Modular Avatar, Avatar Optimizer, PhotoCraft, Blender

### Installation

See `00_README_EN.txt` in the ZIP. You can also open your AI agent in the extracted folder and ask it to read that file and install the plugin for you.

### Tested so far

In the author's environment (Unity 2022.3.22f1, VRCFury 1.1475.0, Modular Avatar 1.18.7, Avatar Optimizer 1.9.23), the features above were checked up to applying them in Unity and the SDK build preprocessing (lilToon adjustments only up to comparing before/after captures). Only a few avatars were tested; other avatars and outfits may not work.

What has not been tested is listed under "Tested so far" in `00_README_EN.txt`. In particular, **the Codex version has not been tested in the author's environment yet**.

### About AI

This plugin is a tool for AI agents, and it was developed with help from AI. It contains no avatars, outfits or other assets.

### Support and disclaimer

- Report problems through GitHub Issues or BOOTH messages. Replies and fixes are not guaranteed.
- MIT License. It comes with no warranty, and the author is not responsible for any damage caused by using it.
- Not affiliated with VRChat Inc., Unity Technologies, or the authors of any package.

Source code and latest version: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter

---

## 中文（简体）

这是一个让 AI 代理帮助你改造 VRChat 模型的插件。
可在 DeepSeek Harness、Claude Code 和 Codex 中使用。

只要提出「调查一下这个项目里的模型结构」「我想在菜单里切换连帽衫的开关」这样的请求，AI 就会读取 Unity 项目，说明要修改的内容并征得你的同意，再用 Unity 的 Editor 脚本应用修改，最后检查结果。

### ⚠ 使用前须知

- **本插件免费，但 AI 代理需要另外付费。** Claude Code 和 Codex 需要付费订阅，DeepSeek Harness 需要 API 费用。
- 仅支持 **Unity 2022.3.22f1**，不支持 Unity 6 项目。
- 仅支持 Windows 10 / 11。
- 修改之前，请先备份项目。
- AI 代理默认用日语回答。用中文提问，它就会用中文回答。

### 功能

- 诊断项目（模型、已安装的包、丢失的引用）
- 在菜单中开关已放置在场景里的服装（VRCFury）
- 用服装附带的分层 PSD 制作换色版本（PhotoCraft）
- 通过材质数值调整 lilToon 的颜色、阴影、描边和自发光（不需要 PSD）
- 调整体型，删除被衣服遮住的身体部分（Modular Avatar、Avatar Optimizer）
- 把饰品、头发挂到骨骼上，或取下（Modular Avatar）
- 在 Blender 中把为其他模型制作的服装调整后穿上（Blender）
- 估算性能等级，提供上传前检查清单

本插件不会上传。请自行用 VRChat SDK 上传。

### 安全机制

- 修改之前，会说明修改内容和将要创建的文件，并征求你的同意。
- 修改之前，会用 Git 创建还原点。
- 不会直接改写场景或预制体文件。修改通过 Unity 的 Editor 脚本进行。
- 项目在 Unity 中打开时，不会开始修改。

### 所需环境

- AI 代理应用（DeepSeek Harness Desktop / Claude Code / Codex 中的任意一个）
- Git for Windows、Python 3.10 或更高版本
- Unity Hub 和 Unity 2022.3.22f1
- 用 VCC 或 ALCOM 管理、已安装 VRChat SDK - Avatars 的项目
- 视功能而定：VRCFury、Modular Avatar、Avatar Optimizer、PhotoCraft、Blender

### 安装方法

请参阅 ZIP 中的 `00_README_ZH.txt`。也可以在解压后的文件夹中打开 AI 代理，让它阅读这个文件并代为安装。

### 测试情况

在作者的环境（Unity 2022.3.22f1、VRCFury 1.1475.0、Modular Avatar 1.18.7、Avatar Optimizer 1.9.23）中，上述功能已测试到在 Unity 中应用以及 SDK 的预处理（lilToon 调整仅测试到修改前后的截图对比）。测试过的模型有限，其他模型或服装可能无法正常使用。

尚未测试的内容写在 `00_README_ZH.txt` 的「测试情况」中。特别是，**Codex 版尚未在作者的环境中测试**。

### 关于 AI

本插件是供 AI 代理使用的工具，开发过程中也借助了 AI。不包含任何模型、服装等素材。

### 支持与免责声明

- 请通过 GitHub Issues 或 BOOTH 消息反馈问题。不保证回复或修复的时间。
- 采用 MIT 许可证。不提供任何担保，作者对使用本插件造成的任何损失不承担责任。
- 与 VRChat Inc.、Unity Technologies 以及各个包的作者无关。

源代码和最新版本：https://github.com/mistraparutenaste/dsh-vrc-unity-supporter

---

## 한국어

AI 에이전트가 VRChat 아바타 개변을 돕도록 하는 플러그인입니다.
DeepSeek Harness, Claude Code, Codex에서 사용할 수 있습니다.

「이 프로젝트의 아바타 구성을 조사해 줘」「후드티를 메뉴에서 켜고 끌 수 있게 해 줘」처럼 요청하면, AI가 Unity 프로젝트를 읽고, 변경할 내용을 보여 주며 승인을 받은 뒤, Unity Editor 스크립트로 적용하고 결과를 확인합니다.

### ⚠ 시작하기 전에

- **플러그인은 무료이지만, AI 에이전트 이용료는 별도로 듭니다.** Claude Code와 Codex는 유료 플랜이, DeepSeek Harness는 API 이용료가 필요합니다.
- **Unity 2022.3.22f1**만 지원합니다. Unity 6 프로젝트는 지원하지 않습니다.
- Windows 10 / 11 전용입니다.
- 개변하기 전에 프로젝트를 백업해 주세요.
- AI 에이전트는 기본적으로 일본어로 답합니다. 한국어로 요청하면 한국어로 답합니다.

### 할 수 있는 것

- 프로젝트 진단(아바타, 설치된 패키지, 끊어진 참조)
- 씬에 배치된 의상을 메뉴에서 켜고 끄기(VRCFury)
- 의상에 포함된 레이어 PSD로 색상 바리에이션 만들기(PhotoCraft)
- 머티리얼 값으로 lilToon의 색, 그림자, 윤곽선, 발광 조정하기(PSD 불필요)
- 체형 조정, 옷 아래에 가려지는 몸 삭제(Modular Avatar, Avatar Optimizer)
- 소품과 머리카락을 본에 붙이기, 떼기(Modular Avatar)
- 다른 아바타용 의상을 Blender로 맞춰서 입히기(Blender)
- 퍼포먼스 랭크 추정, 업로드 전 체크리스트

업로드는 하지 않습니다. VRChat SDK로 직접 업로드해 주세요.

### 안전 장치

- 변경하기 전에 변경 내용과 만들어질 파일을 보여 주고 승인을 받습니다.
- 변경하기 전에 Git으로 복원 지점을 만듭니다.
- 씬이나 프리팹 파일을 직접 수정하지 않습니다. 변경은 Unity Editor 스크립트로 합니다.
- 프로젝트가 Unity에서 열려 있으면 변경을 시작하지 않습니다.

### 필요한 것

- AI 에이전트 앱(DeepSeek Harness Desktop / Claude Code / Codex 중 하나)
- Git for Windows, Python 3.10 이상
- Unity Hub와 Unity 2022.3.22f1
- VCC 또는 ALCOM으로 관리하는, VRChat SDK - Avatars가 들어 있는 프로젝트
- 기능에 따라: VRCFury, Modular Avatar, Avatar Optimizer, PhotoCraft, Blender

### 설치 방법

ZIP 안의 `00_README_KO.txt`를 참고해 주세요. 압축을 푼 폴더에서 AI 에이전트를 열고, 이 파일을 읽고 설치해 달라고 맡길 수도 있습니다.

### 동작 확인 상황

작자의 환경(Unity 2022.3.22f1, VRCFury 1.1475.0, Modular Avatar 1.18.7, Avatar Optimizer 1.9.23)에서 위 기능을 Unity에서의 적용과 SDK 전처리까지 확인했습니다(lilToon 조정은 개변 전후 촬영 비교까지). 확인한 아바타는 한정되어 있어, 다른 아바타나 의상에서는 잘 되지 않을 수 있습니다.

아직 확인하지 않은 것은 `00_README_KO.txt`의 「동작 확인 상황」에 적혀 있습니다. 특히 **Codex 버전은 아직 작자의 환경에서 동작을 확인하지 않았습니다**.

### AI에 대해

이 플러그인은 AI 에이전트로 사용하기 위한 도구이며, 개발에도 AI의 도움을 받았습니다. 아바타나 의상 등의 소재는 포함되어 있지 않습니다.

### 지원 및 면책

- 문제 보고는 GitHub Issues 또는 BOOTH 메시지로 부탁드립니다. 답변이나 수정 시기는 약속할 수 없습니다.
- MIT 라이선스입니다. 보증하지 않으며, 사용으로 인해 생긴 손해에 대해 작자는 책임지지 않습니다.
- VRChat Inc., Unity Technologies, 각 패키지의 작자와는 관계가 없습니다.

소스 코드와 최신 버전: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter
