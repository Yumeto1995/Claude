"""アイテムの分類（持ち物画面のタブ分け）。

武器・防具・消費アイテムはコンポーネントから自動判定し、
素材・大切なものは Entity.item_category で明示指定する。
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, List

from components.equippable import EquipmentType

if TYPE_CHECKING:
    from entity import Entity


class ItemCategory(Enum):
    CONSUMABLE = auto()  # 消費アイテム
    MATERIAL = auto()    # 素材アイテム
    WEAPON = auto()      # 武器
    ARMOR = auto()       # 防具
    KEY = auto()         # 大切なもの


LABELS = {
    ItemCategory.CONSUMABLE: "消費",
    ItemCategory.MATERIAL: "素材",
    ItemCategory.WEAPON: "武器",
    ItemCategory.ARMOR: "防具",
    ItemCategory.KEY: "大切なもの",
}

# タブの並び順
ORDER: List[ItemCategory] = [
    ItemCategory.CONSUMABLE,
    ItemCategory.MATERIAL,
    ItemCategory.WEAPON,
    ItemCategory.ARMOR,
    ItemCategory.KEY,
]


def category_of(item: "Entity") -> ItemCategory:
    """アイテムの分類を返す。明示指定があれば優先、なければコンポーネントから判定。"""
    explicit = getattr(item, "item_category", None)
    if explicit is not None:
        return explicit
    if item.equippable is not None:
        if item.equippable.equipment_type == EquipmentType.WEAPON:
            return ItemCategory.WEAPON
        return ItemCategory.ARMOR
    if item.consumable is not None:
        return ItemCategory.CONSUMABLE
    return ItemCategory.MATERIAL


def items_in(items: List["Entity"], category: ItemCategory) -> List["Entity"]:
    """items のうち、指定分類のものだけを返す。"""
    return [it for it in items if category_of(it) == category]


def is_item(entity: "Entity") -> bool:
    """拾えるアイテムか（消費・装備・素材/大切なもの のいずれか）。死体や生物は False。"""
    return (
        entity.consumable is not None
        or entity.equippable is not None
        or entity.item_category is not None
    )
