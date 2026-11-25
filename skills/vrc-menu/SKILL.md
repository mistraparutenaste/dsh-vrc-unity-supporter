---
name: vrc-menu
description: Expressions メニューをビルド後の形で一覧にし、項目の移動・名前の変更・アイコン・並べ替えをする。VRCFury や Modular Avatar が足した項目も動かせる。メニューの整理・並べ替え・アイコンを頼まれたら読む。
---

# メニューの整理

```
読む（ビルド後のメニュー。VRCFury・MA が足す項目と「Next」ページを含む）
 → レシピを書いて確認
 → 適用（preview → 確認 → apply、SDK 検証）
 → 再生テストとメニューの確認
```

作者のメニューのアセットは変えない。アバターの下に `DSH Menu <名前>` を 1 つ作り、VRCFury の
「Move or Rename Menu Item」「Set Menu Item Icon」「Reorder Menu Item」だけを付ける。VRCFury はビルドの最後に
できあがったメニューへこれをかけるので、作者のメニュー、VRCFury のトグル、MA のメニュー、DSH のトグルの
どれでも動かせる。レシピは `Assets/DSH/Menus/<名前>/recipe.json` に置く。VRCFury が必要。

`<pkg>` はパッケージのルート（このスキルの 2 階層上。Claude Code では `${CLAUDE_PLUGIN_ROOT}` でもよい）。

```powershell
$mn = '<pkg>\tools\unity_menu.py'
```

Unity を使う手順は、シーンを保存して Unity を閉じてから行う。初回は `setup-required` が返るので、
`plannedPaths` を伝えて確認を取ってから `--prepare` を付ける。

## 1. 読む（ファイルは変えない）

```powershell
python -B $mn read --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
python -B $mn read ... --no-build      # 作者のメニューのアセットだけ（速いが、ツールが足す項目は出ない）
```

- `items`：上から順に、`path`（レシピで使う形。ページは含まない）、`type`（SubMenu、Toggle、Button、RadialPuppet など）、
  `index`（そのフォルダの中の位置。0 が最初）、`parameter`、`icon`、`page`（「Next」をたどる必要があるとき、その道筋）。
- `holders`：すでにある `DSH Menu ...` と、その中身。
- 1 ページは 8 項目まで。あふれた分は VRCFury が「Next」に送る。整理の提案では、`page` のある項目を前に出すか、
  サブメニューにまとめて、よく使う項目が 1 ページ目に来るようにする。

ラベルに `/` を含む項目は、パスの中で `\/` と書く。

## 2. レシピを書く

```json
{
  "name": "Tidy",
  "moves": [
    {"from": "Color/Hair Pink", "to": "Hair/Pink Hair"},
    {"from": "Accessory", "to": "Costume/Accessory"}
  ],
  "icons": [{"path": "Hair/Pink Hair", "icon": "Assets/MyIcons/pink.png"}],
  "order": [{"path": "Facial Set", "position": 0}]
}
```

| 項目 | 内容 |
|---|---|
| `moves[]` | `from` の項目を `to` に動かす。同じフォルダの中で名前だけ変えれば改名、フォルダごと動かすこともできる。`to` のフォルダが無ければ作られる |
| `icons[]` | `path` の項目のアイコン。Assets の中の画像（png など）。動かす項目は、動かした後のパスで書く |
| `order[]` | `path` の項目のフォルダの中の位置。0 が最初、1 が 2 番目、999 が最後、-1 が最後から 2 番目 |

- 変更は合わせて 50 個まで。かかる順番は moves → icons → order。
- ユーザーにはメニューの前後を短い木の形で見せ、明示的な確認を得る。
- 別のレシピや VRCFury の部品が同じ項目を動かしていると、後からかかったものが勝つ。`holders` と `read` の結果を見て重ならないようにする。

## 3. 適用する・外す

```powershell
$a = @('--project', '<project>', '--scene', 'Assets/Avatar.unity', '--avatar', 'Avatar', '--recipe', 'Tidy')
python -B $mn preview @a --verify-sdk
python -B $mn apply @a --verify-sdk --approved-preview '<preview の値>'
python -B $mn remove @a                                  # 外す内容だけを返す
python -B $mn remove @a --approved-preview '<値>'
python -B $mn recipes --project '<project>'              # レシピと適用先のシーン
```

- preview の `summary` と `plannedPaths` を伝え、確認を得てから apply する。Git の扱いは衣装トグルと同じ。
- `unity.sdkVerification.checks` に、ビルド後のメニューで、動かした項目が `to` にあるか（`found`）、元の場所から消えたか、
  アイコンが付いたか、位置（`index` と `expected`）が出る。`failed` のときは `read` でビルド後の形を見直す。
- レシピを書き換えて apply すると、`DSH Menu <名前>` の中身を入れ替える。同じレシピをもう一度 apply しても何も変わらない。
- remove は `DSH Menu <名前>` だけを消す。メニューは元の形に戻り、レシピのファイルは残る。
- 適用したら `vrc-verify` §3 の再生テストで、動かしたトグルがビルド後も動くかを確かめる。
- パラメータは増えない（パラメータ容量は変わらない）。
