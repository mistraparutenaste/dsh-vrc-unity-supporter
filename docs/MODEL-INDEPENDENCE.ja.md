# モデルに依存しない設計への強化プラン

## 目的

DeepSeek V4.1 Flash 用に作ったプラグインを、Claude（Haiku / Sonnet / Opus）や Codex でも同じように動かす。
そのために、**モデルが約束を守らなくても壊れない作り**にする。

判断の基準は 1 つ。

> その約束は、モデルが読み飛ばしても守られるか。

守られないものは、次の順で強い仕組みに移す。

1. **CLI が拒否する**（コードで強制）
2. **ハーネスが止める**（Claude Code のフックやアプリの承認）
3. **CLI の出力が次の一手を指示する**（モデルは書かれたとおりに動くだけ）
4. **SKILL.md の文章**（最後の手段。判断が要るものだけ残す）

## 1. 洗い出し

対象: `claude/skills/vrc-avatar`、`codex/skills/vrc-avatar`、`skills/*`（13 個）、`cordis.patch.yml` のペルソナ、`tools/*`。

### 1.1 約束ごとの強制状況

| # | 約束 | 書いてある場所 | 今の強制 | 根拠 |
|---|---|---|---|---|
| 1 | Unity を閉じてから実行する | 入口、各スキル | **CLI で強制済み** | `unity-run.ps1` が実行前と、ロックを取った後にもう一度確認する |
| 2 | 別バージョンの Unity で開かない | unity-cli §1 | **CLI で強制済み** | `Find-DshUnityEditor` が見つからなければ止まる |
| 3 | apply の前にユーザーの明示的な確認を取る | 入口、全スキル | **未強制（鮮度だけ）** | `--approved-preview` は preview のハッシュ。モデルは preview の値をそのまま渡せるので、ユーザーに聞かずに preview → apply と続けて実行できる |
| 4 | Git のチェックポイントが必要 | first-run、各スキル | **CLI で強制済み** | `run_approved` が `git.head` と `sceneInCheckpoint` を確認する |
| 5 | 初回コミットは別に確認を取る | 入口、first-run | **文章だけ** | `checkpoint --confirm` はモデルが付けるフラグ |
| 6 | DSH 以外の変更が残っていれば止まる | first-run、outfit-fit | **CLI で強制済み** | `pending_user_changes` → `blockingChanges` |
| 7 | ヘルパーを置く前に `plannedPaths` を伝えて確認する | 入口、各スキル | **文章だけ。しかも例と矛盾** | accessory / material-adjust / shape-adjust / outfit-fit の最初のコマンド例に、最初から `--prepare` が付いている |
| 8 | シーン・Prefab・アセットの YAML を直接編集しない | 入口、ペルソナ、avatar-edit、edit-script | **文章だけ** | ファイル編集ツールで `.unity` や `.prefab` を書けてしまう |
| 9 | `.meta` なしで移動・削除しない | 入口、edit-script C3 | CLI の経路では守られる。**自由スクリプトとシェルでは文章だけ** | CLI は Unity 経由で削除する。`Remove-Item` や `git clean` は止められない |
| 10 | アップロード・公開・force-push をしない | 入口、ペルソナ、verify | アップロードは手段が無い。**force-push は文章だけ** | |
| 11 | 元のアセットを変えない | 各スキル | CLI の経路では作りで保証。**自由スクリプトでは文章だけ** | 成果物は DSH が管理するフォルダと複製だけに書く |
| 12 | 古い書き出しで適用しない | texture-variant | **CLI で強制済み** | preview が `stale` を拒否する |
| 13 | ほかから参照されていれば削除しない | texture-variant | **CLI で強制済み** | `otherReferences` を返して止まる |
| 14 | 手で直した FBX を上書きしない | blender-model | **CLI で強制済み** | build が `edited` で止まる |
| 15 | レシピの値の範囲 | accessory、texture、material、shape、blender | **CLI で強制済み** | レシピの検証で約 120 種類のエラーを返す |
| 16 | 自由スクリプトの C1（未記録の変更が無い）、C2（冪等）、C7（`changes` を出す） | edit-script | **文章だけ**（結果 JSON の有無だけは強制） | `unity-run.ps1` は Git を確かめない |
| 17 | 規約（改変・流用の可否）をユーザーに確認してもらう | accessory、outfit-fit、blender | **文章だけ**（人が判断するもので、強制はできない） | |
| 18 | 報告に「未検証」を必ず書く | verify §6 | **文章だけ** | |
| 19 | 撮影画像で位置・貫通を判断する | accessory、shape、texture、material | **モデルの画像読み取りに依存** | 数値で出ているのは三角形数と `headFit` だけ |
| 20 | `<pkg>` を求める | 全スキル（DSH・Claude Code・Codex で 3 通り） | **文章だけ** | 環境ごとの説明が 4 か所以上に散らばっている |
| 21 | 長い Unity 実行はバックグラウンドで回す | 入口、unity-cli §6 | **文章だけ**（環境ごとに書き方が違う） | |
| 22 | 次に何をするか | 全スキル | `next` があるのは 9 か所だけで、形もばらばら | `tools/*.py` |

### 1.2 設計の矛盾とずれ

- **A. 改変の入口が自由 C# を勧めている。**
  ペルソナ（`cordis.patch.yml`）と入口（`claude/` と `codex/` の `vrc-avatar`）に「変更はすべて Unity Editor スクリプトを書き、バッチモード実行して適用する（`vrc-edit-script`）」とある。
  実際の主な経路はレシピと CLI。弱いモデルほど、この一文を読んで C# を書き始める。
  いちばんモデル依存の大きい経路へ誘導してしまっている。
- **B. `--prepare` の例が確認の約束と食い違う**（表の #7）。
- **C. 約束が 3 か所に重複している**（ペルソナ、Claude Code の入口、Codex の入口）。同期を取る仕組みが無く、ずれていく。
- **D. 承認トークンが同意の証明になっていない**（表の #3）。CLI だけでは解決できない。モデルは出力をすべて読めるので、CLI がどんな値を出してもモデルはそのまま渡せる。本当の同意はハーネスでしか強制できない。

### 1.3 よくできている点（崩さない）

- preview → apply のトークンで、確認した内容と実行する内容が同じであることを保証している。
- Unity のロック、版、Git のチェックポイント、DSH 以外の変更の検出は、コードで強制済み。
- 成果物は DSH が管理するフォルダと複製だけに書き、元のアセットに触らない。
- レシピの検証エラーが、直し方まで書いている。
- 偽物の Unity・Blender・PhotoCraft を使ったテストがある。

## 2. プラン

各段は独立してリリースできる。上ほど効果に対して手間が小さい。

### P0. 矛盾を直す（小）

- A: ペルソナと入口の「変更はすべて Editor スクリプト」を、次の順に書き換える。
  1. 同梱のコマンド（トグル、色違い、マテリアル、体型、小物、Blender）を使う。
  2. 足りないときだけ `vrc-edit-script` を使う。
  3. YAML の直接編集はしない。
- B: スキルの最初のコマンド例から `--prepare` を外し、「`setup-required` が返ったら `--prepare`」の 1 か所に寄せる。
- 完了の条件: `grep -n "prepare" skills/*/SKILL.md` で、最初のコマンド例に `--prepare` が残っていない。

### P1. 約束を 1 か所にまとめる

- 共通の約束を `docs/rules.ja.md`（仮）にまとめる。
- ペルソナと 2 つの入口に、その写しを同じ文で載せる。
- `verify-package.ps1` で、3 つの写しが元と一致するかを照合する。
- 完了の条件: どれか 1 か所だけ変えると `verify-package.ps1` が落ちる。

### P2. 同意と危険な操作をハーネスで止める（Claude Code）

プラグインのフック（`hooks/hooks.json`）を追加する。

| 対象 | 条件 | 動き |
|---|---|---|
| Bash / PowerShell | `--approved-preview`、`checkpoint --confirm`、`--prepare` を含む | `ask`（ユーザーに承認ダイアログを出す） |
| Edit / Write | パスが `.unity`、`.prefab`、`.asset`、`.meta`、`.controller`、`.anim`、`.mat` | `deny`（理由と、代わりに使うスキルを返す） |
| Bash / PowerShell | `git push --force`、`git push -f`、`git clean`、`git reset --hard` | `deny` |
| Bash / PowerShell | `Remove-Item` / `rm` で `Assets/` 配下が対象 | `ask` |

- フックの判定は `tools/` に Python で書き、単体テストを付ける。
- 自動承認のモードでも `ask` が効くかは、実際に確かめる。
- Codex はアプリの承認ポリシーやルールで同じことができるか、**調べてから決める**。DSH は `dsh-tool-pwsh` の承認設定を調べる。
  できない環境では P3 の `status: needs-confirmation` と文章の約束が最後の守りになることを、README に書く。
- 完了の条件: Claude Code で Haiku に「パーカーのトグルを付けて」と頼むと、apply の直前に必ず承認ダイアログが出る。

### P3. 結果 JSON の形をそろえる

全コマンドの出力に、次の共通部分を持たせる。共通の処理は `unity_toggle.py` に置く（ほかのツールはすでに `toggle` を import している）。

```json
{
  "status": "ok | setup-required | needs-confirmation | blocked | error",
  "code": "unity-open | no-checkpoint | blocking-changes | stale-render | ...",
  "next": {
    "say": "ユーザーに伝える要点",
    "ask": "確認すること（無ければ省く）",
    "run": ["次に実行するコマンド（引数の配列）"]
  },
  "unverified": ["VRChat クライアントでの動作", "..."]
}
```

- `WorkflowError` に `code` と `next` を持たせ、今ある約 120 か所の文言はそのまま残す。
- preview は必ず `status: needs-confirmation` と `next.ask` を返す。`next.ask` には、確認する項目（シーン、パス、メニュー名、初期状態、`plannedPaths`）を CLI が組み立てて入れる。
  モデルが要約し損ねても、聞くべき内容が抜けない。
- apply と verify は `unverified` を返す（表の #18）。
- 完了の条件: テストで、全サブコマンドの出力が共通の形に合うことを確かめる。

### P4. レシピの下書きと項目の説明を CLI へ移す

- `unity_accessory.py draft`、`unity_shape.py draft`、`unity_texture.py draft`（マテリアルの値）を追加する。
  読み取りの結果から記入済みの `recipe.json` を書き出し、モデルは名前・メニュー名・値を少し直すだけにする。
- 各ツールに `schema` サブコマンドを足し、項目、型、範囲、既定値、使う場面を JSON で返す。
  今 SKILL.md にある項目表の元にする。
- 完了の条件: SKILL.md の項目表を消しても、`schema` で同じことが分かる。

### P5. SKILL.md を短くする

- 各スキルに残すのは、流れの図、判断のポイント、してはいけないこと、の 3 つだけ。項目表とエラーの対処は P3・P4 の出力に任せる。
- 目安は各スキル 60 行以内（今は 59〜186 行、合計 1,666 行）。
- `<pkg>` を求める説明は入口の 1 か所にまとめる（表の #20）。
- 完了の条件: 合計 900 行以下。テストと評価（P8）が通る。

### P6. 長い実行と環境差を CLI で吸収する

- Unity を使うコマンドに `--detach` を足し、すぐに `runId` を返す。`status --run <id>` で進み具合と結果を返す。
  そうすれば、DSH のジョブ機能、Claude Code のバックグラウンド実行、Codex のタイムアウトの違いを、モデルが覚えなくてよくなる（表の #21）。
- 同じプロジェクトで二重に起動したときは、今の `unity.lock` で止めたうえで `code: run-active` と、その `runId` を返す。

### P7. 自由スクリプトの経路を狭める

- `unity-run.ps1` に `-RequireCleanGit` を足す。`DSH.Tasks.*` を実行するときは既定で有効にし、未記録の変更があれば止める（表の #16 の C1）。
- 結果 JSON に `changes` 配列が無ければ失敗にする（C7）。
- 冪等かどうかは、同じタスクを 2 回目に実行して、`changes` が空になるかで確かめる `-CheckIdempotent` を足す（C2）。
- 入口のスキル表で `vrc-edit-script` を「同梱のコマンドで足りないときだけ。強いモデルを推奨」と明記する。
- よく頼まれる自由スクリプトの作業は、記録を見てレシピの機能として足していく。

### P8. 撮影の判断を数値で補う

- 小物の撮影で、ボーンからの距離、頭や体の表面にめり込んだ頂点の数、浮いている距離を `unity.fit` に出す（表の #19）。
- 体型の撮影で、衣装の内側に出た体の頂点の数を出す（Blender の `verticesInsideBody` と同じ考え方）。
- スキルには「数値が基準の中なら画像は確認用。画像を読めなければ数値で判断し、画像のパスをユーザーに渡す」と書く。

### P9. モデルを替えて同じ場面を試す

- `tests/scenarios/` に、頼み方と期待するコマンドの順番を書いた場面を置く。
  - 初回診断
  - トグル
  - 色違い
  - マテリアル
  - 体型
  - 小物
  - 非対応衣装
  - 取り外し
  - 範囲外の依頼（アップロード）
- 偽物の Unity で、`claude -p --model <haiku|sonnet|opus>`（と DSH、Codex）を回し、次の点を記録する。
  - 承認の前に apply したか（P2 の後は、フックの記録で確かめる）
  - 決められたコマンドを使ったか、自由に C# を書いたか
  - YAML を直接編集しようとしたか
  - 報告に `unverified` を入れたか
- 結果を README の「動作確認環境」に反映し、通ったモデルを載せる。
- 完了の条件: Haiku 5.5 で全場面が通る。通らない場面は、どの約束が CLI・ハーネスに残っていないかの手がかりにする。

## 3. 進め方

| 順 | 段 | 大きさ | 主に変えるファイル |
|---|---|---|---|
| 1 | P0 矛盾を直す | 小 | `cordis.patch.yml`、`claude/` と `codex/` の `vrc-avatar`、4 つのスキル |
| 2 | P9 の場面を先に作る（基準を測る） | 中 | `tests/scenarios/` |
| 3 | P2 フック | 中 | `hooks/hooks.json`、`tools/dsh_guard.py`、テスト |
| 4 | P3 結果 JSON | 中〜大 | `tools/unity_*.py`、`tools/blender_model.py`、テスト |
| 5 | P1 約束を 1 か所に | 小 | `docs/rules.ja.md`、`verify-package.ps1` |
| 6 | P4 下書きと schema | 中 | `tools/unity_accessory.py`、`unity_shape.py`、`unity_texture.py` |
| 7 | P5 SKILL.md を短く | 中 | `skills/*` |
| 8 | P7 自由スクリプト | 小〜中 | `tools/unity-run.ps1`、`skills/vrc-edit-script` |
| 9 | P6 長い実行 | 中 | `tools/unity_toggle.py`（共通の実行部分） |
| 10 | P8 撮影の数値 | 大 | `templates/Editor/DshCapture.cs`、`DshAccessory.cs`、`DshShape.cs` |

P9 の場面は 2 番目に作る。改善の前後を同じ物差しで測るため。

## 4. やらないこと

- 確認そのものを無くすこと。確認の内容は CLI が組み立てるが、確認するのは人。
- CLI だけで同意を証明しようとすること。モデルは出力をすべて読めるので、ハーネス（P2）が要る。
- 自由スクリプトの経路を無くすこと。足りない機能の逃げ道として残し、狭める。
