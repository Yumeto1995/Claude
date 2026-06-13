"""ゲーム開始の村マップ：森の外れの寂れた村。

草地に木造の建物（道具屋・武器防具屋・食料品店・民家）が建ち、まわりを森が囲む。
建物の**ドア**の上で Enter を押すと、別マップ（建物内）に入れる（buildings.py）。
北の**洞窟**（ダンジョン入口）から地下へ。
"""
from __future__ import annotations

import tile_types
from entity import Entity
from game_map import GameMap

VW, VH = 30, 20
SPAWN = (15, 11)            # プレイヤーの初期位置（広場の中央）
DUNGEON_ENTRANCE = (15, 3)  # 北の洞窟（ダンジョン入口）

# ドアタイル (x, y) → 入れる建物のキー（buildings.BUILDINGS と対応）
DOORS = {
    (6, 9): "item",
    (14, 9): "weapon",
    (22, 9): "food",
    (12, 16): "house",
}

# 看板・地名（text, x, y）
LABELS = [
    ("▲ 洞窟（ダンジョン）", 11, 2),
    ("道具屋", 4, 5),
    ("武器・防具屋", 11, 5),
    ("食料品店", 20, 5),
    ("民家", 10, 12),
    ("～ 森の外れの寂れた村 ～", 2, 18),
]

# 村人（x, y, 名前, セリフ…）。寂れた雰囲気のフレーバー。
NPC_DEFS = [
    (16, 10, "村長", [
        "ようこそ、こんな辺鄙な村へ。",
        "若い者は皆出ていき、残ったのは年寄りばかりでな。",
        "北の洞窟の魔物を鎮めてくれれば、村もまた賑わうだろう。",
    ]),
    (9, 13, "村の子供", [
        "おにいちゃん、つよい？",
        "お店の人たちね、ぼうけんしゃにはやさしいんだって。",
    ]),
    (24, 13, "年老いた旅人", [
        "わしも昔は冒険者じゃった。",
        "金が要るなら経験を売るがいい…ただし、力は少し鈍るがの。",
    ]),
]


def _stamp_building(gm: GameMap, x1: int, y1: int, x2: int, y2: int, door: tuple) -> None:
    """(x1,y1)-(x2,y2) を木の壁で塗り、door の位置だけドアにする。"""
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            gm.tiles[x, y] = tile_types.wall  # 描画側で wood_wall に割り当て
    gm.tiles[door] = tile_types.door


def build_village_map() -> GameMap:
    gm = GameMap(VW, VH)
    # 一面を草地に
    gm.tiles[:, :] = tile_types.floor
    # まわりを森（木）で囲う。上側は2列にして深い森に。
    gm.tiles[0, :] = tile_types.tree
    gm.tiles[VW - 1, :] = tile_types.tree
    gm.tiles[:, 0] = tile_types.tree
    gm.tiles[:, VH - 1] = tile_types.tree
    gm.tiles[:, 1] = tile_types.tree
    # 散在する木（寂れた森の外れ感）
    for x, y in [(3, 3), (27, 3), (2, 9), (27, 10), (5, 16), (26, 16), (19, 14)]:
        gm.tiles[x, y] = tile_types.tree

    # 建物（道具屋・武器防具屋・食料品店・民家）
    _stamp_building(gm, 4, 6, 8, 9, (6, 9))
    _stamp_building(gm, 12, 6, 16, 9, (14, 9))
    _stamp_building(gm, 20, 6, 24, 9, (22, 9))
    _stamp_building(gm, 10, 13, 14, 16, (12, 16))

    # 洞窟（ダンジョン入口）。周囲の木を少し開けて洞口に
    gm.tiles[DUNGEON_ENTRANCE] = tile_types.down_stairs

    gm.visible[:, :] = True
    gm.explored[:, :] = True
    gm.safe[:, :] = False
    gm.downstairs_location = (-1, -1)

    for x, y, name, lines in NPC_DEFS:
        gm.entities.append(
            Entity(x=x, y=y, sprite="npc", name=name, blocks_movement=True, dialogue=lines)
        )
    return gm
