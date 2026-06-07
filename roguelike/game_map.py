from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import numpy as np
import tcod

import tile_types

if TYPE_CHECKING:
    from entity import Entity


class GameMap:
    """ダンジョン1フロア分のタイル配列と、そこにいる全エンティティを保持する。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.entities: List["Entity"] = []

        # 最初は全面を壁にしておき、生成側で部屋・通路を床に掘る
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")

    def in_bounds(self, x: int, y: int) -> bool:
        """(x, y) がマップ内なら True。"""
        return 0 <= x < self.width and 0 <= y < self.height

    def get_blocking_entity_at(self, x: int, y: int) -> Optional["Entity"]:
        """(x, y) にいる『すり抜け不可』なエンティティを返す。なければ None。"""
        for entity in self.entities:
            if entity.blocks_movement and entity.x == x and entity.y == y:
                return entity
        return None

    def render(self, console: tcod.Console) -> None:
        # まずタイル（床・壁）を一括描画
        console.rgb[0 : self.width, 0 : self.height] = self.tiles["dark"]
        # その上にエンティティを描画。死体・アイテム（すり抜け可）を先に、
        # 生きている者（すり抜け不可）を後に描いて重なり順を正す。
        for entity in sorted(self.entities, key=lambda e: e.blocks_movement):
            console.print(entity.x, entity.y, entity.char, fg=entity.color)
