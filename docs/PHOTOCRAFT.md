# PhotoCraft 連携メモ

`tools/unity_texture.py` が使う PhotoCraft CLI の操作をまとめる。PhotoCraft は早期アルファ版なので、
版が上がってコマンドが変わったら、このメモと `commands_for()`（`tools/unity_texture.py`）を一緒に直す。

確認した版: `photocraft-cli 0.23.1 (45066c482, 2026-11-12)`、Windows 11、`C:\Program Files\ArtCraft\PhotoCraft\`。

## 使っているコマンド

| 目的 | CLI / エンジンコマンド | パラメータ |
|---|---|---|
| レイヤー木を読む | `photocraft-cli info <file>` | JSON。`layers[]` に `id`、`name`、`kind`、`visible`、`blend`、`clipped`、`opacity`、`bounds`、`children` |
| 操作して書き出す | `photocraft-cli run <file> --cmd <id> --params <json> ... --out <png>` | `--out` が元ファイルと同じだと拒否される（`--in-place` を付けない限り）。PNG へは統合して書き出す |
| 表示・非表示 | `layer.setProps` | `{"layer": id, "visible": bool}` |
| 対象レイヤーを選ぶ | `layer.select` | `{"layer": id}` |
| 色相・彩度 | `layer.newAdjustmentLayer.hueSaturation` | `hue` -180..180、`saturation`/`lightness` -100..100、`colorize`（hue 0..360、saturation 0..100）、`clipToPrevious: true` で選択レイヤーにクリップ |
| 画像を置く | `file.placeEmbedded` | `{"path", "scale": %, "center": [x, y], "smartObject": false}`。選択レイヤーの直上に入る。座標は左上原点のピクセル |
| クリップする | `layer.createClippingMask` | `{}`（直前に置いたレイヤーを下のレイヤーにクリップ） |

一覧は `photocraft-cli commands --json`（1000 件超）で取れる。`--filter <text>` で絞れる。

## 実機で確かめたこと

- Salt（4096×4096、48 レイヤー）の衣装 PSD で、`info` は約 1 秒、上の操作 4 つと PNG 書き出しは約 2 秒。
- `layer.select` + `hueSaturation(clipToPrevious)` は、そのレイヤーにだけ効く。
- `file.placeEmbedded` + `layer.createClippingMask` で、ロゴが衣装の形で切り抜かれる。
- PSD に `UV` レイヤーが表示状態で入っていることがある（Salt）。書き出し前に隠す（レシピの `hideUv`、既定で有効）。
- Salt の髪（400MB、43 レイヤー）と顔（142 レイヤー）の PSD も、`info` は約 3 秒、書き出しは約 5 秒。
  大容量 PSD 用の `--approve-high-memory` は不要だった。
- 顔の PSD をそのまま書き出した PNG は、同梱のテクスチャと同じ色になった（色の再現に問題なし）。
- 色プリセット（`Hair_Color`、`Eye_Color` グループ）の表示切り替えで、髪と瞳の色違いが作者の陰影のまま作れた。
- 肌は相対的な色相・彩度のずらしだと、体（`Skin_Tone` の彩度レイヤーあり）と顔で結果が揃わなかった。
  `colorize` で同じ色を指定すると揃った。
- レイヤー ID は保存し直すと振り直されるので、レシピには ID ではなくパスを書き、書き出しのたびに `info` から引き直す。

## Unity 側で確かめたこと（Unity 2022.3.22f1、lilToon、VRCFury 1.1474.0、MA 1.18.7）

- 撮影はグラフィックス有りのバッチモード（`unity-run.ps1 -AllowGraphics`）で動く。
- lilToon は Unity を開くたびに `Packages/jp.lilxyzw.liltoon/Editor/CurrentRP.txt` へ描画 API（`Null` / `Direct3D11`）を書く。
  DSH はこの差分を作業の妨げとして扱わない。
- SDK 検証用のコピーを前処理すると、NDMF が `Packages/nadena.dev.ndmf/__Generated/` に書き出す。
  VRCFury の `Builds` と同じく、ローカルの Git 除外に入れる。
- VRCFury の公開 API にマテリアル差し替えは無いので、`m_Materials.Array.data[i]` を切り替えるアニメーションを作り、
  `FuryToggle.GetActions().AddAnimationClip()` に渡す。

## Claude Code で MCP として使う（任意）

対話しながら PSD を触りたいときは、PhotoCraft の MCP サーバーも登録できる。DSH 版と共通の手順は CLI だけで完結する。

```bash
claude mcp add photocraft -- "C:\Program Files\ArtCraft\PhotoCraft\photocraft-cli.exe" mcp --automation-read-root "<PSD のフォルダ>" --automation-write-root "<project>\Assets\DSH\Variants"
```

書き込み先はバリエーションのフォルダに限る。元の PSD のフォルダには書き込み権限を渡さない。
