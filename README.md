# dsh-vrc-unity-supporter

DeepSeek Harness のエージェントプリセット。**VRChat アバターの改変を AI に任せる**ためのものです。

土台を作る道具ではありません。Unity と VCC/ALCOM が入っていて、VRChat プロジェクトが
開ける状態の人を対象にしています。

## これがやること

```
読む（Unity不要） → 設計 → C# を書く → バッチ適用 → 検証 → git 差分
```

1. **読む** — シーン・プレハブ・`.meta` を解析し、階層・コンポーネント・参照切れを Unity を開かずに報告する
2. **設計** — 衣装・髪・トグル・メニュー・SPS・最適化の進め方を、実行順序（MA → VRCFury → AAO）を踏まえて組み立てる
3. **適用** — 改変を Editor スクリプトとして書き、バッチモードで Unity に適用する
4. **検証** — コンパイル・パフォーマンス試算・非アップロード検証を行い、結果を報告する

シーン/プレハブの YAML を直接書き換えることはありません。変更は必ず Unity 経由で、
`git diff` で全部レビューできます。

## 前提

| 必要 | 確認 |
|---|---|
| Unity 2022.3.22f1（VRChat 対応版） | `tools/doctor.ps1` |
| 有効な Unity ライセンス | 同上（無効だとバッチモードが動きません） |
| VCC または ALCOM | どちらか一方で可 |
| VRChat プロジェクト（SDK 導入済み） | 同上 |
| `vrc-get` CLI（**任意**） | あるとパッケージ操作を自動化。無ければ GUI 手順を提示します |

## インストール

### 1. npm（推奨）

```
plugin_manager install_bundle target: "dsh-vrc-unity-supporter"
```

または **Plugins** 画面でパッケージ名を入力。更新は Update ボタンから。

### 2. GitHub

```
plugin_manager install_bundle target: "https://github.com/<owner>/dsh-vrc-unity-supporter"
```

### 3. clone

```powershell
git clone https://github.com/<owner>/dsh-vrc-unity-supporter
```

**Plugins** > **Add plugin** でそのディレクトリを指定。

インストール後、**新しいセッション**を作り、プリセットで `VRChat Avatar` を選んでください。
既存のセッションには反映されません。

## プロジェクトへの初期配置

プリセットはプロジェクトの中に 3 つ置くものがあります。初回だけコピーしてください。

```
templates/Editor/*.cs        -> <Project>/Assets/DSH/Editor/
templates/gitignore.template -> <Project>/.gitignore
templates/AGENTS.template.md -> <Project>/AGENTS.md
```

`Assets/DSH/Editor/` が無いとバッチモードから `-executeMethod` を呼べません。
`AGENTS.md` はセッション開始時に読まれ、アバター名・導入済みパッケージ・性能予算を
エージェントに伝えます（分かる範囲で埋めてください）。

## 最初に試す

```
このプロジェクトのアバター構成を調べて
```

```
Outfit_Hoodie をメニューから切り替えられるようにして。排他は outfit タグで
```

```
いまの三角形数とマテリアル数から、PC のパフォーマンスランクを試算して
```

## やらないこと

- Unity / ALCOM / VCC のインストール、ライセンス設定
- プロジェクトの新規作成・修復
- ワールド制作（World SDK / UdonSharp / ライティング）
- **アップロード**（チェックリストを出します。実行は人間が行ってください）
- アセットのリッピングや VRChat ToS に反する操作

## 仕組み（なぜ YAML を触らないのか）

シーンやプレハブの YAML を直接編集すると、GUID と参照が壊れて復旧が難しくなります。
このプリセットは代わりに **Editor スクリプトを生成して Unity に適用させます**。

- 改変がコードとして残る（手作業の順序に依存しない）
- 失敗したら script ごと revert できる
- `git diff` で何が変わったか全部見える

そのため **git 管理されていることを前提**にしています。管理されていない場合は、
最初に `git init` を提案します（勝手には行いません）。

## 公開（メンテナ向け）

```powershell
npm login
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1
```

`publish.ps1` は次を順に実行し、前提が欠けていれば**何も壊さずに止まります**。

1. `verify-package.ps1`（BOM / スキル名 / JSON / `dsh.bundle.patch`）
2. `npm pack --dry-run` で同梱内容を確認
3. npm / gh の認証確認（未ログインなら実行すべきコマンドを表示して終了）
4. `npm publish --access public`（同じ版が既にあれば skip）
5. `gh repo create ... --push`、`git tag`、タグ push

`-DryRun` を付けると 4 以降を実行せず、何をするかだけ表示します。

## ライセンス

MIT。サードパーティの扱いは [THIRD-PARTY.md](THIRD-PARTY.md) を参照してください。
本パッケージは VRChat Inc. / Unity Technologies / 各 VPM パッケージ作者とは無関係です。
