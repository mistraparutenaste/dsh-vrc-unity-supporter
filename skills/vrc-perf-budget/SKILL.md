---
name: vrc-perf-budget
description: VRChat の性能ランク（PC / Mobile）の上限表と数え方、パラメータ容量（256 bit）の測り方。三角形・PhysBone などを測り、Good を目標に判断する。
---

# 性能予算

VRChat の Performance Rank は**静的解析**で決まる。アニメーター・シェーダ・テクスチャ解像度は
考慮されないが、95% のケースで問題を検出できる目安になる。

**目標は Good。届かなければ Medium でも実用上は問題ない。**

## 1. 上限表（PC）

| 項目 | Excellent | Good | Medium | Poor |
|---|---|---|---|---|
| Triangles | 32,000 | 70,000 | 70,000 | 70,000 |
| Texture Memory | 40 MB | 75 MB | 110 MB | 150 MB |
| Skinned Meshes | 1 | 2 | 8 | 16 |
| Basic Meshes | 4 | 8 | 16 | 24 |
| Material Slots | 4 | 8 | 16 | 32 |
| PhysBones コンポーネント | 4 | 8 | 16 | 32 |
| PhysBones 対象 Transform | 16 | 64 | 128 | 256 |
| PhysBone Colliders | 4 | 8 | 16 | 32 |
| Contacts | 8 | 16 | 24 | 32 |
| Constraint 数 | 100 | 250 | 300 | 350 |
| Animators | 1 | 4 | 16 | 32 |
| Bones | 75 | 150 | 256 | 400 |
| Lights | 0 | 0 | 0 | 1 |
| Particle Systems | 0 | 4 | 8 | 16 |

完全な表は `assets/limits.json`（PC / Mobile / Face Tracking を含む）。

### Mobile

| 項目 | Excellent | Good | Medium | Poor |
|---|---|---|---|---|
| Triangles | 7,500 | 10,000 | 15,000 | 20,000 |
| Texture Memory | 10 MB | 18 MB | 25 MB | 40 MB |
| Material Slots | 1 | 1 | 2 | 4 |
| Contacts | 2 | 4 | 8 | 16 |
| PhysBones コンポーネント | 0 | 4 | 6 | 8 |

Mobile は **Medium を超えると表示されない**（Poor / Very Poor はブロック）。
コンポーネント上限を超えると、その種別は丸ごと削除される。

## 2. 数え方

Unityで元Prefabを数え、ビルド前の参考値として使う。MA、VRCFury、AAOなどのビルド処理後の値とランクはVRChat SDKで確認する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "<pkg>\tools\unity-run.ps1" -Project "C:\path\to\Project" `
  -Method "DSH.Editor.DshInspect.Perf"
```

今回の `result.json` に項目別のカウントが出る。ランクは手で表と見比べず、`rank` で出す（Unity 不要）:

```powershell
python -B "<pkg>\tools\unity_inspect.py" rank "<project>\.dsh\runs\<run-id>\result.json" --prefab "<avatar>.prefab" --json
```

`pc` / `mobile` ごとに、全体の `rank`、それを決めた項目（`limitedBy`）、1 つ上のランクに上げるための上限（`toReach.reduce`）、数えていない項目（`notMeasured`）が出る。Perf はプロジェクト内のアバター prefab をすべて数えるので、`--prefab` で対象を絞る（パスの一部で一致。`--json` を外すと 1 prefab 2 行の要約になる）。撮影や SDK 検証の三角形数だけを見るときは `{"triangles": 52000}` のような JSON を渡してもよい。

Read/Writeが無効な計測対象は `unreadableMeshes` に出る。テクスチャメモリは概算。未計測の項目がある場合は測った項目ごとの目安を伝える。

- **その項目が Excellent の上限以下なら Excellent を維持**
- 1 つでも超えたら、その項目の達成ランクに全体が引き下げられる（最弱の項目で決まる）
- 例: 三角形 25,000（Excellent）でも Skinned Mesh 2 個なら全体は Good

例として、三角形68,583はGood、Skinned Mesh 13はPoorの範囲。ビルド後はSDKで全項目を確認する。

## 3. よく効く改善（コストの低い順）

1. **Avatar Optimizer (AAO) の Trace and Optimize** — 未使用ボーン・ blendshape・
   メッシュの削除。ほぼ無設定で効く
2. **マテリアル統合** — 同じシェーダ・同じテクスチャなら 1 スロットに寄せる（TexTransTool）
3. **メッシュ統合** — 同一マテリアルのメッシュを結合
4. **PhysBone の統合** — 揺れ物ごとに分かれた PhysBone をまとめる（値やコライダーの調整は `vrc-physbone`）
5. **テクスチャ圧縮** — 1024 以下に落とす、使っていないチャンネルを削る
6. **ポリゴン削減** — 三角形数でランクが決まっているときだけ。Meshia でビルド時に減らす（`vrc-polygon`）

Quest（Android）版は、VRCQuestTools でモバイル用シェーダーと揺れ物の削減を同じシーンから作る（`vrc-quest`）。

## 4. 判断の指針

| 状況 | 判断 |
|---|---|
| 改変で +5,000 tri 程度 | 多くの場合許容。まず現状値を測る |
| Good 上限まで残り 10% 未満 | AAO の導入を提案する |
| Mobile 版も作る | 最初から 20,000 tri を上限に設計する。`vrc-quest` の `try` で Android 版のランクを測る |
| SPS を入れる | Contacts 8 個で Excellent 満杯。プラグ+ソケット 1 組で約 8 |

「測ってから言う」。改変前に現状値を出し、改変後に再度測って差分を報告する。

## 5. パラメータ容量（256 bit）

VRChat は同期するパラメータを合計 **256 bit** までしか許さない（Bool 1 bit、Int・Float 8 bit。ローカルだけのものは数えない）。
超えるとアップロードできない。トグルを足すたびに増えるので、改変の前に測る。

```powershell
python -B "<pkg>\tools\unity_params.py" measure --project '<project>' --scene 'Assets/Avatar.unity' --avatar 'Avatar' --prepare
```

既定では SDK ビルドしたコピーも数えるので、VRCFury や Modular Avatar がビルド時に足す分も入る（グラフィックス有りで起動する）。
`unity.built.usedBits` が合計、`byOwner` が出どころ別（avatar / VRCFury / Modular Avatar / other）、`parameters` が bit の大きい順の一覧。
`--no-build` ではシーン上の分だけを数える（速いが、ビルド時に足される分は入らない）。

測った値は `.dsh/params` に残り、衣装トグル・小物・表情の preview が `parameterBudget` に「今 + 追加 = 後」を出す。
後が 256 を超える apply は止まる。シーンが測ったあとに変わっていると `stale` になり、止めずに測り直しを促す。

減らし方（効く順）:

1. 自分だけが見ればよいトグル（デバッグ用、カメラ用）を同期しないようにする（MA Parameters の Local Only、VRCFury の Local Only）
2. 同時に 1 つしか使わない衣装を、Bool をいくつも使わず 1 つの Int で切り替える（Modular Avatar の Menu Item で値を割り当てる）
3. VRCFury の Parameter Compressor を入れる（複数の値を交代で同期して、使う bit を減らす。切り替えに少し遅れが出る）
4. 使っていないギミックを外す
