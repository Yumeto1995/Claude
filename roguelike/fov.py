"""視界（FOV）計算。tcod を使わず、bresenham によるレイキャストで実装。

- 通路：プレイヤーから視線の通る範囲（壁で遮られる）
- 部屋：中に入ると部屋全体（＋囲む壁）が見える（風来のシレン風）
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from pathfinding import bresenham

DEFAULT_RADIUS = 5


def compute_fov(
    transparent: np.ndarray,
    rooms: List[Tuple[int, int, int, int]],
    px: int,
    py: int,
    radius: int = DEFAULT_RADIUS,
) -> np.ndarray:
    """プレイヤー位置から見えるタイルの bool 配列を返す。

    transparent: 視線を通すか（床=True, 壁=False）の (w, h) 配列。
    rooms: 各部屋の (x1, y1, x2, y2)。
    """
    w, h = transparent.shape
    visible = np.full((w, h), False, order="F")
    visible[px, py] = True

    # 1) レイキャスト：周囲 radius 内へ線を引き、壁で遮られるまで見える
    x0, x1 = max(0, px - radius), min(w - 1, px + radius)
    y0, y1 = max(0, py - radius), min(h - 1, py + radius)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if (tx - px) ** 2 + (ty - py) ** 2 > radius * radius:
                continue  # 円の外
            for x, y in bresenham((px, py), (tx, ty)):
                visible[x, y] = True
                if not transparent[x, y]:
                    break  # 壁にぶつかったらそこで遮られる（壁自体は見える）

    # 2) 部屋の中にいれば、その部屋全体（＋囲む壁）を見せる
    for (rx1, ry1, rx2, ry2) in rooms:
        if rx1 < px < rx2 and ry1 < py < ry2:  # 部屋の内側にいる
            visible[rx1 : rx2 + 1, ry1 : ry2 + 1] = True
            break

    return visible
