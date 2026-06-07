from __future__ import annotations

import numpy as np

# console.rgb と同じ構造：文字・前景色・背景色
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # 文字（Unicodeコードポイント）
        ("fg", "3B"),      # 前景色 RGB
        ("bg", "3B"),      # 背景色 RGB
    ]
)

# タイル1種類の構造
tile_dt = np.dtype(
    [
        ("walkable", np.bool_),     # 歩けるか
        ("transparent", np.bool_),  # 視線を通すか（後の視界処理用）
        ("dark", graphic_dt),       # 見えているときの見た目
    ]
)


def new_tile(
    *,  # 以降はキーワード引数を強制（読みやすさのため）
    walkable: int,
    transparent: int,
    dark: tuple[int, tuple[int, int, int], tuple[int, int, int]],
) -> np.ndarray:
    """タイル種別を1つ作るヘルパー。"""
    return np.array((walkable, transparent, dark), dtype=tile_dt)


floor = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(" "), (255, 255, 255), (50, 50, 150)),
)

wall = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord(" "), (255, 255, 255), (0, 0, 100)),
)
