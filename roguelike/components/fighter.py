from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity


class Fighter:
    """HP・攻撃力・防御力を持つ、戦えるエンティティ用のコンポーネント。

    RL の観点では、ここの値（与ダメージ・残HP・撃破）が
    報酬や観測の材料になる。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。

    def __init__(self, hp: int, defense: int, power: int):
        self.max_hp = hp
        self._hp = hp          # 現在HP（setter経由で 0..max_hp に収める）
        self.defense = defense  # 防御力（受けるダメージを軽減）
        self.power = power      # 攻撃力

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        # 0 未満や最大値超えにならないように収める
        self._hp = max(0, min(value, self.max_hp))
