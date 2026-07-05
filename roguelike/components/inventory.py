from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from entity import Entity


class Inventory:
    """プレイヤーの持ち物。capacity 個まで持てる。

    「大切なもの」(ItemCategory.KEY) は別枠扱い＝容量を消費せず、持ち物が
    いっぱいでも必ず持てる（拾い逃しを防ぐ）。items には一緒に入れておくが、
    容量カウントからは除外する。
    """

    entity: "Entity"  # 所有者

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.items: List["Entity"] = []

    @staticmethod
    def _is_key(item) -> bool:
        import item_category
        return item_category.category_of(item) == item_category.ItemCategory.KEY

    @property
    def used(self) -> int:
        """容量を消費している個数（大切なものを除く）。"""
        return sum(1 for it in self.items if not self._is_key(it))

    @property
    def is_full(self) -> bool:
        return self.used >= self.capacity

    def can_accept(self, item) -> bool:
        """このアイテムを持てるか。大切なものは枠を消費せず常に持てる。"""
        return self._is_key(item) or not self.is_full
