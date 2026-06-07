from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from entity import Entity


class EquipmentType(Enum):
    WEAPON = auto()
    ARMOR = auto()


class Equippable:
    """装備できるアイテム（武器・防具）。装備すると攻撃力/防御力を加算する。"""

    entity: "Entity"  # このコンポーネントを持つアイテム

    def __init__(
        self,
        equipment_type: EquipmentType,
        power_bonus: int = 0,
        defense_bonus: int = 0,
        stamina_cost: Optional[int] = None,
    ):
        self.equipment_type = equipment_type
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        # 武器の攻撃消費スタミナ（None なら既定値。防具は通常 None）
        self.stamina_cost = stamina_cost
