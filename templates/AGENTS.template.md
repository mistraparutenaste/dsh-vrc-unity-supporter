# アバタープロジェクト メモ（エージェント向け）

このファイルはプリセットがセッション開始時に読む。分かっている事実だけ書く。
推測・願望・未確認のことを書かない。

## アバター

| 項目 | 値 |
|---|---|
| アバター名 | （記入） |
| prefab / シーン | `Assets/…/（記入）.prefab` |
| 身長・スケール | （記入） |

## 環境

| 項目 | 値 |
|---|---|
| Unity | 2022.3.22f1 |
| VRChat SDK | （`Packages/manifest.json` の実値） |
| パッケージ管理 | ALCOM / VCC（どちらで管理しているか） |
| vrc-get CLI | あり / なし |

## 導入済みパッケージ

| パッケージ | 版 | 用途 |
|---|---|---|
| Modular Avatar | （記入） | 衣装統合・メニュー |
| VRCFury | （記入） | トグル・SPS |
| Avatar Optimizer | （記入） | 最適化 |
| lilToon | （記入） | シェーダ |

## 性能予算（実測値）

`DSH.Editor.DshInspect.Perf` を実行して埋める。

| 項目 | 現在 | 目標 |
|---|---|---|
| Triangles | （記入） | 70,000 以下（Good） |
| Material Slots | （記入） | 8 以下 |
| Skinned Meshes | （記入） | 2 以下 |
| Contacts | （記入） | 16 以下 |
| PhysBone コンポーネント | （記入） | 8 以下 |

## 禁止事項（このプロジェクト固有）

- （例）`Assets/Amatousagi/` 配下は作者配布物なので編集しない
- （例）シェーダは lilToon のみ。Poiyomi は導入しない

## 既知の問題

- （記入。無ければ「なし」）
