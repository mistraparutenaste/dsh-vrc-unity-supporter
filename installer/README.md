# かんたんインストール（Windows）

`install.cmd` をダブルクリックするだけで、DeepSeek Harness にプリセットを入れられます。

## 必要なもの

- Windows 10 / 11
- DeepSeek Harness（Desktop 版）がインストール済み
- インターネット接続（npm からパッケージを取得します）

管理者権限は不要です。レジストリ、PATH、システム設定は変更しません。

## 使い方

1. `installer` フォルダごとダウンロード（またはリポジトリを clone）
2. **DeepSeek Harness を終了**する（起動中だとプロファイルを書き換えられません）
3. `install.cmd` をダブルクリック
4. 黒いウィンドウに「完了しました」と出たら、DeepSeek Harness を起動
5. **新しいセッション**を作り、プリセットで **`VRChat Avatar`** を選ぶ

> 「Windows によって PC が保護されました」と出た場合は、`install.cmd` を右クリック →
> プロパティ → 下部の「ブロックの解除」にチェック → OK、で実行できます。

## 何をしているか

```
1. レジストリから DeepSeek Harness のインストール先を探す
2. 実行中でないことを確認する
3. dsh plugin --profile desktop add dsh-vrc-unity-supporter を実行する
4. 次の 3 点を検証する
   - プロファイルの package.json に依存として入ったか
   - node_modules に実体があり、バージョンが読めるか
   - dsh.profile.bundles に入って有効化されたか
5. 結果を表示して終わる
```

`package.json` は実行前に `package.json.bak-<日時>` としてバックアップし、
途中で失敗したら元に戻します。

## オプション

| 引数 | 意味 |
|---|---|
| `-Profile <name>` | 入れるプロファイル（既定 `desktop`） |
| `-Version <x.y.z>` | バージョンを固定する（既定は最新） |
| `-Force` | DeepSeek Harness が起動中でも続行（非推奨） |
| `-InstallDir <path>` | インストール先を自動検出せず指定する |

例:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Version 0.1.1
```

## うまくいかないとき

| 症状 | 確認すること |
|---|---|
| 「DeepSeek Harness が見つかりません」 | デスクトップ版が入っているか。独自の場所なら `-InstallDir` で指定 |
| 「起動中です」 | タスクトレイも含めてアプリを終了する |
| 「インストールに失敗しました」 | ネットワーク、プロキシ、npm レジストリへの到達 |
| 完了したのにプリセットが出ない | **新しいセッション**を作ったか。既存セッションには反映されません |

ログは `%TEMP%\dsh-vrc-unity-install-*.log` に残ります。

## 削除

`uninstall.cmd` をダブルクリック（同じくアプリを終了してから）。
依存とバンドル選択の両方から削除されたことを確認して終わります。

## 手動でやる場合

インストーラを使わずに、同じことを手で実行することもできます。

```powershell
# DeepSeek Harness を終了してから
& "<install>\resources\runtime\cli\bin\dsh.cmd" plugin --profile desktop add dsh-vrc-unity-supporter
```

または DSH の **Plugins** 画面でパッケージ名 `dsh-vrc-unity-supporter` を入力します。
