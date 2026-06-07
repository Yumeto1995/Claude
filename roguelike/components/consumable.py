from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import colors
import combat

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Consumable:
    """使うと効果を発揮するアイテムの基底。"""

    entity: "Entity"  # このコンポーネントを持つアイテム

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        """効果を発動する。実際に使われたら True（呼び出し側が消費する）。"""
        raise NotImplementedError()


def _nearest_visible_enemy(
    engine: "Engine", consumer: "Entity", maximum_range: int
) -> Optional["Entity"]:
    """consumer から見て、視界内で最も近い生きた敵を返す。範囲外/不在なら None。"""
    nearest = None
    closest = maximum_range + 1
    for e in engine.game_map.entities:
        if e is consumer or e.fighter is None or e.ai is None:
            continue
        if not engine.game_map.visible[e.x, e.y]:
            continue
        d = abs(e.x - consumer.x) + abs(e.y - consumer.y)
        if d < closest:
            nearest = e
            closest = d
    return nearest


class HealingConsumable(Consumable):
    """HP を回復する消費アイテム。"""

    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        f = consumer.fighter
        if f is None:
            return False
        if f.hp >= f.max_hp:
            engine.message_log.add_message("HPは満タンだ。", colors.NO_EFFECT)
            return False  # 無駄遣いさせない（消費しない）
        recovered = min(self.amount, f.max_hp - f.hp)
        f.hp += recovered
        engine.message_log.add_message(
            f"{self.entity.name} を使った。HPが {recovered} 回復した。", colors.HEAL
        )
        return True


class LightningConsumable(Consumable):
    """視界内で最も近い敵に雷ダメージを与える巻物。"""

    def __init__(self, damage: int, maximum_range: int):
        self.damage = damage
        self.maximum_range = maximum_range

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        target = _nearest_visible_enemy(engine, consumer, self.maximum_range)
        if target is None:
            engine.message_log.add_message("近くに敵がいない。", colors.NO_EFFECT)
            return False
        engine.message_log.add_message(
            f"雷が {target.name} を撃った！ {self.damage} ダメージ。", colors.SCROLL
        )
        combat.inflict_damage(engine, target, self.damage, attacker=consumer)
        return True


class ConfusionConsumable(Consumable):
    """視界内で最も近い敵を一定ターン混乱させる巻物。"""

    def __init__(self, turns: int):
        self.turns = turns

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        from components.ai import ConfusedEnemy  # 循環インポート回避のため遅延import

        target = _nearest_visible_enemy(engine, consumer, maximum_range=8)
        if target is None:
            engine.message_log.add_message("近くに敵がいない。", colors.NO_EFFECT)
            return False
        engine.message_log.add_message(
            f"{target.name} は混乱して よろめき始めた！", colors.SCROLL
        )
        target.ai = ConfusedEnemy(target, previous_ai=target.ai, turns=self.turns)
        return True
