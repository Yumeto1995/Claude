"""歩けるテント内（拠点）のマップ定義。

ダンジオンとは別の小さな GameMap。プレイヤーが歩き回り、各区画の
『設備』タイルの上で Enter を押すと、その機能（収納・料理・畑など）が開く。
牧場・漁業区画は鍵アイテムで開放されるまで未開放。
"""
from __future__ import annotations

import tile_types
from game_map import GameMap

CAMP_W, CAMP_H = 24, 17
ENTRANCE = (12, 12)

# 設備タイル： (x, y) -> 種類
STATIONS = {
    # 住居区画（左上）
    (3, 3): "storage",
    (5, 3): "cooking",
    (7, 3): "alchemy",
    # 畑区画（右上）
    (16, 3): "farm0",
    (18, 3): "farm1",
    (16, 5): "farm2",
    (18, 5): "farm3",
    # 牧場区画（左下・未開放）
    (4, 12): "ranch",
    # 漁業区画（右下・未開放）
    (19, 12): "fishery",
    # 出入口（下中央）
    (12, 14): "exit",
}

# 区画名ラベル： (text, x, y)
ZONE_LABELS = [
    ("住居", 3, 1),
    ("畑", 16, 1),
    ("牧場", 3, 9),
    ("漁業", 18, 9),
]

# 設備ごとの表示名（案内・メッセージ用）
STATION_LABELS = {
    "storage": "収納",
    "cooking": "料理（かまど）",
    "alchemy": "アイテム錬金",
    "ranch": "牧場",
    "fishery": "漁業",
    "exit": "ダンジョンに戻る",
}


def build_camp_map() -> GameMap:
    gm = GameMap(CAMP_W, CAMP_H)
    # 外周は壁、内側は床（オープンな1部屋）
    gm.tiles[1 : CAMP_W - 1, 1 : CAMP_H - 1] = tile_types.floor
    gm.visible[:, :] = True   # 拠点は霧なし
    gm.explored[:, :] = True
    gm.safe[:, :] = True
    gm.downstairs_location = (-1, -1)
    return gm
