# 画像素材（assets）

ここに **`<キー>.png`** を置くと、ゲームが起動時に自動で読み込みます。
無いものは仮タイル（単色）で代用されるので、用意できたものから順に追加できます。
（背景＝床/壁、アイテム、キャラ、設備すべてこの仕組みで反映されます）

- 形式：**PNG**、サイズ **32×32**（読み込み時に32×32へ自動拡縮）
- キャラ・アイテム・設備は**背景透過**推奨。床/壁は不透過でOK
- タイルサイズを変えたいときは `graphics.py` の `TILE_SIZE`

## 必要なファイル一覧（全30種）

### 背景（地形）
| ファイル | 用途 |
|----------|------|
| `floor.png` | 床 |
| `safe_floor.png` | セーフルームの床 |
| `wall.png` | 壁 |
| `stairs_down.png` | 下り階段 |

### キャラクター
| ファイル | 用途 |
|----------|------|
| `player.png` | プレイヤー |
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
