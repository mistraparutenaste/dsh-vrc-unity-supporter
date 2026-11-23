---
name: vrc-avatar-update
description: アバターの新しい版（作者の更新）に、このプラグインで入れた改変を引き継ぐ。改変の一覧、新しい版での参照チェック、まとめてのかけ直しと、手作業の変更の一覧を扱う。
---

# 元アバターの更新に改変を引き継ぐ

```
一覧（DSH の改変 ＋ 手作業の変更）
 → 新しい版をシーンに置いてもらう
 → 計画（新しい版で、各レシピが使うものがあるか）
 → 足りないものを直す（レシピの書き換え・複製、または外す）
 → まとめて適用（計画を 1 回確認）
 → 手作業の変更はチェックリストで案内
```

引き継げるのは、このプラグインのコマンドで入れた改変（衣装トグル、色違い・マテリアル調整、体型、小物、揺れ物、
目線と大きさ、表情）だけ。手で入れた変更（Inspector で直した値、足したコンポーネント）は一覧にするだけで、自動ではコピーしない。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$mg = '<pkg>\tools\unity_migrate.py'
```

## 0. 更新のされ方を確かめる

| 更新のされ方 | 見分け方 | やること |
|---|---|---|
| 同じ場所に上書き（`.unitypackage` を上から入れた） | アバターの prefab のパスが変わらない。シーンのアバターはそのまま新しい版になる | `--to-avatar` を同じアバターにして plan → apply。各改変がまだ当たるかの確認と、外れたもののかけ直しになる |
| 別のフォルダに新しく入った（`Salt_v2` など） | 新しい prefab が別のパスにある | 新しい版をシーンに置いてもらう（ユーザーが Unity で置く。置けないときは `vrc-edit-script` で置く）。古いアバターは残したまま plan → apply |

上書きする前に、Git で今の状態を記録しておくよう案内する（`unity_toggle.py checkpoint`、または普段のコミット）。
作者の更新内容（メッシュ名やシェイプキー名の変更）は、配布ページの更新履歴も見てもらう。

## 1. 一覧

```powershell
python -B $mg inventory --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --overrides --prepare
```

- `changes`：このアバターに今かかっている DSH の改変（`kind`: shape / accessory / physbone / proportion / toggle / variant / expression、`name`）。
  `.dsh` に残る適用の記録から作るので、このコピーのプロジェクトで適用したものだけが出る。
  `unverified` は、記録の仕組みができる前に適用したもので、レシピからかけ直すことはできる。
- `manual`（`--overrides` のとき）：prefab に対して手で変えた値（`values`）、足したオブジェクト・コンポーネント、消したコンポーネント。
  DSH が変えたもの（記録にある値、`DSH ` で始まるオブジェクト）は除いてある。これは引き継がれないので、ユーザーに一覧として見せる。

## 2. 計画

```powershell
python -B $mg plan --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --to-scene 'Assets/AvatarV2.unity' --to-avatar 'Avatar_v2'
```

新しい版を Unity で読み、改変ごとに `status` を返す。

- `ready`：レシピが使うメッシュ・シェイプキー・ボーン・オブジェクト・マテリアルが、新しい版にそろっている。
- `needs-attention`：`problems[]` に、無いもの（`missing`、`name`）と近い候補（`suggest`）が出る。
  - 名前が変わっただけなら、レシピを複製して新しい名前で書く（例：`Fit_Hoodie` → `Fit_Hoodie_v2`）。古いアバターに同じレシピがかかっているときは、元のレシピを書き換えない。
  - 色違い（variant）は、新しい版がほかのテクスチャやマテリアルを使っていると引き継げない。新しい版の PSD から作り直す（`vrc-texture-variant`）か、マテリアルの調整を作り直す（`vrc-material-adjust`）。
  - 直したら plan をもう一度実行する。直さない改変は、apply では飛ばされる（`skipped`）。

`plan` の値が、適用の確認に使う値になる。改変の一覧と、飛ばすものをユーザーに伝え、明示的な確認を得る。

## 3. まとめて適用

```powershell
python -B $mg apply --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --to-scene 'Assets/AvatarV2.unity' --to-avatar 'Avatar_v2' --approved-plan '<plan の値>'
```

- `ready` の改変を、体型 → 小物 → 揺れ物 → 目線と大きさ → 衣装トグル → 色違い → 表情 の順に、各コマンドの preview と apply でかけ直す。
  Git の確認、パラメータの残り、保存後の確認は、それぞれのコマンドと同じ。
- 途中で失敗すると止まる。それまでの改変は残る（`done`）。原因を直して plan からやり直す。
- 最後に、`--verify-sdk` を付けて 1 つの改変を apply し直すか、`vrc-verify` の手順でビルドを確かめる。表情や揺れ物は Gesture Manager で見てもらう。

## 4. 手作業の変更を案内する

`inventory --overrides` の `manual` を、新しい版でやり直すチェックリストとして見せる（オブジェクトのパス、項目、値）。
数が多いときや、同梱のコマンドで表せるもの（シェイプキーの値 → `vrc-shape-adjust`、PhysBone の値 → `vrc-physbone`）は、
その先にレシピにしておくと、次の更新から引き継げるようになる、と伝える。
