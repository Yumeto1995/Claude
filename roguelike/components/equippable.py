from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from entity import Entity


class EquipmentType(Enum):
    WEAPON = auto()   # 近接武器（weapon 枠）
    ARMOR = auto()    # 防具（armor 枠）
    RANGED = auto()   # 遠距離武器（弓など。ranged 枠。近接 power には加算しない）


class Equippable:
    """装備できるアイテム（武器・防具）。装備すると攻撃力/防御力を加算する。"""

    entity: "Entity"  # このコンポーネントを持つアイテム

    def __init__(
        self,
        equipment_type: EquipmentType,
        power_bonus: int = 0,
        defense_bonus: int = 0,
        stamina_cost: Optional[int] = None,
        max_range: int = 0,
    ):
        self.equipment_type = equipment_type
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        # 武器の攻撃消費スタミナ（None なら既定値。防具は通常 None）。
        # 遠距離武器では「1射の消費スタミナ」を表す。
        self.stamina_cost = stamina_cost
        # 遠距離武器の射程（マス数）。近接・防具は 0。
        self.max_range = max_range
