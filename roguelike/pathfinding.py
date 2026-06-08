"""経路探索とライン描画のユーティリティ（純Python実装）。

以前は tcod.path / tcod.los を使っていたが、pygame と tcod が別々の SDL2 を
読み込んで衝突するのを避けるため、tcod 依存を外して自前実装にした。
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Tuple

import numpy as np

Point = Tuple[int, int]


def bresenham(start: Point, end: Point) -> List[Point]:
    """2点間の直線上の格子点を返す（始点・終点を含む）。"""
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    points: List[Point] = []
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points


def find_path(cost: np.ndarray, start: Point, goal: Point) -> List[Point]:
    """4方向の A* 経路探索。

    cost[x, y] が 0 のマスは通行不可。値が大きいほど通りにくい。
    戻り値は start を除いた経路 [(x, y), ...]。到達不可なら空リスト。
    """
    width, height = cost.shape
    gx, gy = goal

    def heuristic(x: int, y: int) -> int:
        return max(abs(x - gx), abs(y - gy))  # 8方向なのでチェビシェフ距離

    open_heap: List[Tuple[int, int, Point]] = [(heuristic(*start), 0, start)]
    came_from: Dict[Point, Point] = {}
    g_score: Dict[Point, int] = {start: 0}
    visited = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current == goal:
            # 経路を復元（start を除いて返す）
            path: List[Point] = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        if current in visited:
            continue
        visited.add(current)

        cx, cy = current
        for dx, dy in (
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            tile_cost = int(cost[nx, ny])
            if tile_cost == 0:
                continue  # 壁
            # 斜めは縦・横の両隣が壁でないこと（壁の角抜け防止）
            if dx != 0 and dy != 0 and (cost[cx + dx, cy] == 0 or cost[cx, cy + dy] == 0):
                continue
            tentative = g + tile_cost
            if tentative < g_score.get((nx, ny), 1 << 30):
                g_score[(nx, ny)] = tentative
                came_from[(nx, ny)] = current
                heapq.heappush(
                    open_heap, (tentative + heuristic(nx, ny), tentative, (nx, ny))
                )
    return []  # 到達不可
