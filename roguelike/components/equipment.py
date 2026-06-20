from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import colors
from components.equippable import EquipmentType

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Equipment:
    """プレイヤーの装備枠（武器・防具）。装備中アイテムのボーナスを合算する。"""

    entity: "Entity"

    def __init__(
        self,
        weapon: Optional["Entity"] = None,
        armor: Optional["Entity"] = None,
        ranged: Optional["Entity"] = None,
    ):
        self.weapon = weapon  # 装備中の近接武器（Entity）or None
        self.armor = armor    # 装備中の防具（Entity）or None
        self.ranged = ranged  # 装備中の遠距離武器＝弓（Entity）or None

    @property
    def power_bonus(self) -> int:
        total = 0
        for item in (self.weapon, self.armor):
            if item is not None and item.equippable is not None:
                total += item.equippable.power_bonus
        return total

    @property
    def defense_bonus(self) -> int:
        total = 0
        for item in (self.weapon, self.armor):
            if item is not None and item.equippable is not None:
                total += item.equippable.defense_bonus
        return total

    def item_is_equipped(self, item: "Entity") -> bool:
        return item is self.weapon or item is self.armor or item is self.ranged

    def toggle_equip(self, item: "Entity", engine: "Engine") -> None:
        """アイテムを装備/解除する（同じ枠に別物があれば付け替え）。"""
        etype = item.equippable.equipment_type
        if etype == EquipmentType.WEAPON:
            slot = "weapon"
        elif etype == EquipmentType.RANGED:
            slot = "ranged"
        else:
            slot = "armor"
        if getattr(self, slot) is item:
            setattr(self, slot, None)
            engine.message_log.add_message(f"{item.name} を外した。", colors.ITEM)
        else:
            setattr(self, slot, item)
            engine.message_log.add_message(f"{item.name} を装備した。", colors.ITEM)
