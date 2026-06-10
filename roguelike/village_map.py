"""ゲーム開始の村マップ。歩いてNPCに話しかけ、北の入口からダンジョンへ。

camp_map と同じく、ダンジョンとは別の小さな GameMap。NPC はダイアログを持つ
ブロッキングなエンティティとして配置する。
"""
from __future__ import annotations

import tile_types
from entity import Entity
from game_map import GameMap

VW, VH = 24, 17
SPAWN = (12, 11)            # プレイヤーの初期位置
DUNGEON_ENTRANCE = (12, 2)  # 北の洞窟（ダンジョン入口）

LABELS = [
    ("▲ ダンジョン入口", 8, 1),
    ("村", 2, 14),
]

# NPC：(x, y, 名前, セリフ行...)
NPC_DEFS = [
    (10, 5, "村長", [
        "ようこそ、辺境の村へ。",
        "北の洞窟から魔物があふれ出ておる。",
        "君のような冒険者だけが頼りなのじゃ。",
    ]),
    (4, 8, "道具屋のおやじ", [
        "いらっしゃい！…と言いたいが、まだ開店準備中でな。",
        "そのうち武器や薬を並べるさ。楽しみにな。",
    ]),
    (19, 8, "教官", [
        "戦いの心得を教えよう。",
        "セーフルームに魔物は入れん。『魔法のテント』を張れば",
        "料理・畑・牧場・漁業ができるぞ。空腹には気をつけてな。",
    ]),
    (15, 12, "村の子供", [
        "おにいちゃん、ダンジョンって こわい？",
        "モンスターがいっぱいいるんだって！",
    ]),
]


def build_village_map() -> GameMap:
    gm = GameMap(VW, VH)
    gm.tiles[1 : VW - 1, 1 : VH - 1] = tile_types.floor  # 広場（オープン）
    gm.tiles[DUNGEON_ENTRANCE] = tile_types.down_stairs   # 入口は階段スプライト
    gm.visible[:, :] = True
    gm.explored[:, :] = True
    gm.safe[:, :] = False
    gm.downstairs_location = (-1, -1)

    for x, y, name, lines in NPC_DEFS:
        gm.entities.append(
            Entity(x=x, y=y, sprite="npc", name=name, blocks_movement=True, dialogue=lines)
        )
    return gm
