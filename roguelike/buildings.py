"""建物内（別マップ）の定義。村のドアから入る家・店の内部。

各建物は小さな木の部屋。店主（NPC）がいて、隣で Enter すると
店（shop.py）が開く。民家は店ではなく会話だけ。下のドアで村へ戻る。
"""
from __future__ import annotations

import tile_types
from entity import Entity
from game_map import GameMap

IW, IH = 13, 9
ENTRANCE = (6, 7)   # 入ったときのプレイヤー位置
EXIT = (6, 8)       # 村へ戻るドア（下の壁）
KEEPER = (6, 2)     # 店主/住人の立ち位置

# 建物キー → 看板名・店主名・店種（None なら会話のみ）・セリフ
BUILDINGS = {
    "item": {
        "sign": "道具屋", "keeper": "道具屋のおやじ", "shop": "item",
        "lines": ["いらっしゃい！冒険の必需品、揃ってるよ。",
                  "代金は経験でいい。命あっての物種さ。"],
    },
    "weapon": {
        "sign": "武器・防具屋", "keeper": "鍛冶屋", "shop": "weapon",
        "lines": ["うちの武具は確かだぜ。",
                  "重い装備は構えに体力を食う。装備して確かめな。"],
    },
    "food": {
        "sign": "食料品店", "keeper": "食料品店の女将", "shop": "food",
        "lines": ["お腹が空いては戦はできないよ。",
                  "保存食はダンジョンの友さ。"],
    },
    "house": {
        "sign": "民家", "keeper": "村のおばあさん", "shop": None,
        "lines": ["あらあら、お客さんなんて久しぶり。",
                  "ゆっくりしておいき。…何もないけれどね。"],
    },
}


def label(key: str) -> str:
    return BUILDINGS[key]["sign"]


def build_interior(key: str):
    """建物内マップと (entrance, exit) を返す。店主エンティティも配置する。"""
    info = BUILDINGS[key]
    gm = GameMap(IW, IH)
    gm.tiles[1:IW - 1, 1:IH - 1] = tile_types.floor   # 床（描画で wood_floor）
    gm.tiles[EXIT] = tile_types.door                  # 下の壁にドア
    gm.visible[:, :] = True
    gm.explored[:, :] = True
    gm.safe[:, :] = True
    gm.downstairs_location = (-1, -1)

    keeper = Entity(
        x=KEEPER[0], y=KEEPER[1], sprite="npc", name=info["keeper"],
        blocks_movement=True, dialogue=info["lines"],
    )
    keeper.shop = info["shop"]   # 店なら種別、民家なら None
    gm.entities.append(keeper)
    return gm, ENTRANCE, EXIT
