from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from entity import Entity


class Inventory:
    """プレイヤーの持ち物。capacity 個まで持てる。"""

    entity: "Entity"  # 所有者

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.items: List["Entity"] = []
