"""一時的な状態効果（料理を食べると付く強化バフ）。

プレイヤーの entity.status_effects に積まれ、毎ターン turns が減って 0 で消える。
Fighter.power/defense はこのボーナスを合算する。
"""
from __future__ import annotations


class StatusEffect:
    def __init__(
        self,
        name: str,
        turns: int,
        power_bonus: int = 0,
        defense_bonus: int = 0,
    ):
        self.name = name
        self.turns = turns
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
