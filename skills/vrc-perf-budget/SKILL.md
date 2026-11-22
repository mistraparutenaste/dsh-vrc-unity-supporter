---
name: vrc-perf-budget
description: VRChat の性能ランク（PC / Mobile）の上限表と数え方。三角形・マテリアル・PhysBone・コンタクトなどを測り、Good を目標に判断する。
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
python -B "<pkg>\tools\unity_inspect.py" rank "<project>\.dsh\runs\<run-id>\result.json" --json
```

`pc` / `mobile` ごとに、全体の `rank`、それを決めた項目（`limitedBy`）、1 つ上のランクに上げるための上限（`toReach.reduce`）、数えていない項目（`notMeasured`）が出る。撮影や SDK 検証の三角形数だけを見るときは `{"triangles": 52000}` のような JSON を渡してもよい。

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
4. **PhysBone の統合** — 揺れ物ごとに分かれた PhysBone をまとめる
5. **テクスチャ圧縮** — 1024 以下に落とす、使っていないチャンネルを削る

## 4. 判断の指針

| 状況 | 判断 |
|---|---|
| 改変で +5,000 tri 程度 | 多くの場合許容。まず現状値を測る |
| Good 上限まで残り 10% 未満 | AAO の導入を提案する |
| Mobile 版も作る | 最初から 20,000 tri を上限に設計する |
| SPS を入れる | Contacts 8 個で Excellent 満杯。プラグ+ソケット 1 組で約 8 |

「測ってから言う」。改変前に現状値を出し、改変後に再度測って差分を報告する。
