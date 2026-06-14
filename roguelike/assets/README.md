# 画像素材（assets）

## フォント（fonts/）

UIには **PixelMplus**（8bit風の日本語TrueTypeフォント）を同梱している。

| ファイル | 用途 |
|----------|------|
| `fonts/PixelMplus12-Regular.ttf` | 本文（24pxで使用＝12の倍数でドットが揃う） |
| `fonts/PixelMplus12-Bold.ttf` | 見出し・ラベル・タイトル |
| `fonts/PixelMplus10-*.ttf` | 予備（小さめ表示用） |
| `fonts/PixelMplus-LICENSE.md` / `fonts/MPLUS-FONT-LICENSE.txt` | ライセンス（M+ FONT LICENSE：改変・再配布自由） |

サイズは **12px系は12の倍数、10px系は10の倍数**で使うとドットが揃う（`graphics.py` の `load_font`）。
`fonts/game.ttf` を置くと本文フォントを差し替えられる。

**ドットの大きさ**：3つの生成器（`gen_sprites.py` / `gen_tiles.py` / `gen_items.py`）は仕上げに
`pixelate()` で **`PIX_BLOCK`×`PIX_BLOCK` のブロックに量子化**し、2000年代初頭（GBA期）風の
太いドットにする。既定 `PIX_BLOCK=2`（64グリッド→32相当＝ドット2倍）。`4` でさらに大きく、
`1` で従来の細かいドット。64 を割り切る値（2 や 4）にするとタイルの継ぎ目が保たれる。

ここに **`<キー>.png`** を置くと、ゲームが起動時に自動で読み込みます。
無いものは仮タイル（単色）で代用されるので、用意できたものから順に追加できます。
（背景＝床/壁、アイテム、キャラ、設備すべてこの仕組みで反映されます）

- 表示タイルサイズは **64×64**（`graphics.py` の `TILE_SIZE`）。
- **キャラ画像**は 64×64 を推奨（`gen_sprites.py` が64pxで生成）。
- **地形・アイテム・設備**は 32×32 のままでよい（64へ整数2倍でくっきり拡大される）。
- キャラ・アイテム・設備は**背景透過**推奨。床/壁は不透過でOK。

### 向き＋歩行＋攻撃（方向別スプライト）

キャラは**向き別**に表示する。命名は `<キー>_<向き>[ _walk1 | _walk2 | _attack ].png`：
- 向き：`down`（正面）/ `up`（後ろ姿）/ `left`（横顔）。**`right` は `left` を水平反転**して自動生成。
- `_walk1`/`_walk2`：移動中に交互表示（脚＋腕を振る全身歩行）。
- `_attack`：攻撃中、向いた方向へ武器を突き出すポーズ。
- 解決順：`<キー>_<向き>_<状態>` →（無ければ）`<キー>_<状態>` → `<キー>_<向き>` → `<キー>`。

向きはプレイヤー/敵の「最後に動いた／攻撃した方向」から自動で決まる。
`gen_sprites.py` が player/npc/goblin を全方向×ポーズで生成（slime/corpse は無方向）。
`assets` 内の PNG は**ファイル名がそのままキー**として全部読み込まれる。

## 必要なファイル一覧

> Claude Chat で生成する場合のプロンプト集：[PROMPTS.md](PROMPTS.md)

## キャラ画像の再生成（gen_sprites.py）

`player` `npc` `goblin` `slime` `corpse` の5枚は **`gen_sprites.py`**（pygame だけで動く）で
プログラム生成している。色や形を変えたいときはスクリプトを編集して再実行する：

```bash
cd assets && python3 gen_sprites.py   # 5枚を assets 直下に再生成
```

**64×64**で各色を 5 階調＋鏡面ハイライトにして光源=左上で陰影を付ける方式（球は `ball()`、
手足は円筒シェードの `_limb()`）。歩行2フレーム（`*_walk1`/`*_walk2`）も同時に出力する。
手描きPNGに差し替えたい場合はそのまま上書きすればよい（再実行しなければ消えない）。

## アイテム・設備の再生成（gen_items.py）

薬・巻物・武具・素材・テント、拠点の設備（かまど/収納/錬金/牧場/漁業/出口）、畑タイル
（空き/育成/収穫）の計22枚は **`gen_items.py`** で生成する。描画プリミティブは
`gen_sprites.py` から再利用し、キャラと同じ **64×64・光源=左上・陰影＋黒縁** の画風で揃える：

```bash
cd assets && python3 gen_items.py   # 22枚を assets 直下に再生成
```

## ダンジョン地形の再生成（gen_tiles.py）

ダンジョンの床/壁は**階層テーマ別**（浅層=草原 `meadow` / 中層=洞窟 `cave` / 深層=石 `stone`）で、
**`gen_tiles.py`** が下地テクスチャを生成する：

```bash
cd assets && python3 gen_tiles.py   # meadow_/cave_/stone_ の floor/wall/safe_floor を再生成
```

壁は隣接状況を見て**床に面した側だけ縁取り**し（壁同士の辺は描かない＝塊が連結して見える）、
床は壁際に影を落とす。この向き別の縁取り・影は `graphics.py` が下地に重ねて描く（オートタイル）ので、
追加の向き別PNGは不要。色を変えるときは `gen_tiles.py` の `PALETTES`／各 `make_*` を編集する。
テーマの境目は `graphics.py` の `Renderer.MEADOW_MAX_FLOOR`（既定3階まで草原）と
`CAVE_MAX_FLOOR`（既定6階まで洞窟・以降は石）。

### 背景（地形）
| ファイル | 用途 |
|----------|------|
| `meadow_floor.png` / `meadow_wall.png` / `meadow_safe_floor.png` | 草原テーマ（浅層）：床=踏み固めた土 / 壁=丈の高い茂み＋岩 |
| `cave_floor.png` / `cave_wall.png` / `cave_safe_floor.png` | 洞窟テーマ（中層）の下地 |
| `stone_floor.png` / `stone_wall.png` / `stone_safe_floor.png` | 石テーマ（深層）の下地 |
| `stairs_down.png` / `stairs_up.png` | 下り階段（▼寒色）・上り階段（▲暖色）。村の洞窟入口は下り |
| `grass.png` ＋ `grass_flower/clover/stone/dirt.png` | 村の草地（5バリアントをタイル毎に敷き分け） |
| `tree.png` / `door.png` | 村：森の木・ドア（`gen_tiles.py` が生成） |
| `wood_wall.png` / `wood_floor.png` | 村の建物・建物内の壁/床（同上） |
| `floor.png` / `safe_floor.png` / `wall.png` | 拠点（テント内）で使う汎用の床/壁 |

### キャラクター
| ファイル | 用途 |
|----------|------|
| `player.png` | プレイヤー |
| `npc.png` | 村人（NPC） |
| `goblin.png` | ゴブリン |
| `slime.png` | スライム |
| `corpse.png` | 倒した敵（死体） |

### アイテム（消費）
| ファイル | 用途 |
|----------|------|
| `potion.png` | 回復薬 |
| `scroll.png` | 雷の巻物 |
| `scroll_confuse.png` | 混乱の巻物 |
| `food.png` | 食材・食料（木の実/薬草/キノコ/肉） |
| `dish.png` | 料理（できあがり） |

### アイテム（武器・防具）
| ファイル | 用途 |
|----------|------|
| `dagger.png` | 短剣 |
| `sword.png` | 剣 |
| `leather_armor.png` | 革の鎧 |
| `chain_mail.png` | 鎖帷子 |

### アイテム（素材・種・大切なもの）
| ファイル | 用途 |
|----------|------|
| `material.png` | 素材（スライムのかけら/毒キノコ） |
| `seed.png` | 種 |
| `key_item.png` | 大切なもの（冒険者の証・各種の鍵） |
| `tent.png` | 魔法のテント |

### 拠点（テント内）の設備
| ファイル | 用途 |
|----------|------|
| `st_cooking.png` | かまど（料理） |
| `st_storage.png` | 収納 |
| `st_alchemy.png` | 錬金台 |
| `st_ranch.png` | 牧場 |
| `st_fishery.png` | 漁業 |
| `st_exit.png` | 出口 |
| `farm_empty.png` | 畑（空き） |
| `farm_grow.png` | 畑（育成中） |
| `farm_ready.png` | 畑（収穫可） |

> 注：`food`/`dish`/`material`/`key_item`/`seed` は複数アイテムで共有。
> 個別の絵にしたい場合は `entity_factories.py` の `sprite=` と `graphics.py` の
> `PLACEHOLDER_COLORS` にキーを追加する。

### 攻撃ポーズ（任意・あれば自動使用）

`<キー>_attack.png`（例：`player_attack.png`、`goblin_attack.png`）を置くと、
そのキャラの**攻撃モーション中だけ**自動でこの画像に差し替わる。
無ければ通常画像のまま踏み込みアニメだけが再生される（必須ではない）。
