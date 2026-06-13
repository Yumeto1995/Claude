from __future__ import annotations

import numpy as np

# タイル1種類の構造。walkable / transparent はロジック用、
# sprite は描画用のスプライト番号（graphics.py で画像に対応づける）。
tile_dt = np.dtype(
    [
        ("walkable", np.bool_),     # 歩けるか
        ("transparent", np.bool_),  # 視線を通すか（後の視界処理用）
        ("sprite", np.uint8),       # スプライト番号
    ]
)

# スプライト番号の割り当て
SPRITE_FLOOR = 0
SPRITE_WALL = 1
SPRITE_DOWNSTAIRS = 2
SPRITE_DOOR = 3   # 村・建物のドア（歩いて入れる）
SPRITE_TREE = 4   # 森の木（通れない）
SPRITE_UPSTAIRS = 5  # 上り階段（前の階／村へ）


def new_tile(
    *, walkable: int, transparent: int, sprite: int
) -> np.ndarray:
    """タイル種別を1つ作るヘルパー。"""
    return np.array((walkable, transparent, sprite), dtype=tile_dt)


floor = new_tile(walkable=True, transparent=True, sprite=SPRITE_FLOOR)
wall = new_tile(walkable=False, transparent=False, sprite=SPRITE_WALL)
down_stairs = new_tile(walkable=True, transparent=True, sprite=SPRITE_DOWNSTAIRS)
up_stairs = new_tile(walkable=True, transparent=True, sprite=SPRITE_UPSTAIRS)
door = new_tile(walkable=True, transparent=True, sprite=SPRITE_DOOR)
tree = new_tile(walkable=False, transparent=False, sprite=SPRITE_TREE)
