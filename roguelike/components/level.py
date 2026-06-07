from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# レベルアップ時のステータス上昇量（バランス調整はここ）
HP_PER_LEVEL = 20
POWER_PER_LEVEL = 1


class Level:
    """経験値とレベル。

    - プレイヤー：current_xp / current_level を蓄積してレベルアップする。
    - 敵：xp_given（倒されたとき相手に与える経験値）だけを使う。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。

    def __init__(
        self,
        *,
        level_up_base: int = 50,
        level_up_factor: int = 100,
        xp_given: int = 0,
        current_level: int = 1,
        current_xp: int = 0,
    ):
        self.current_level = current_level
        self.current_xp = current_xp
        self.level_up_base = level_up_base      # 次レベルに必要なXPの基準
        self.level_up_factor = level_up_factor  # レベルごとの増加量
        self.xp_given = xp_given                # 倒されたとき相手に与えるXP

    @property
    def experience_to_next_level(self) -> int:
        """次のレベルに必要な経験値。"""
        return self.level_up_base + self.current_level * self.level_up_factor

    def add_xp(self, amount: int) -> int:
        """経験値を加算し、上がったレベル数を返す。"""
        self.current_xp += amount
        gained = 0
        while self.current_xp >= self.experience_to_next_level:
            self.current_xp -= self.experience_to_next_level
            self.current_level += 1
            gained += 1
        return gained
