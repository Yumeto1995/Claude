from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import colors
import combat
import nutrition

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


class FoodConsumable(Consumable):
    """食べると満腹度を回復する食料。"""

    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        f = consumer.fighter
        if f is None or f.max_satiety <= 0:
            return False
        if f.satiety >= f.max_satiety:
            engine.message_log.add_message("満腹で食べられない。", colors.NO_EFFECT)
            return False
        restored = f.restore_satiety(self.amount)
        nut = getattr(consumer, "nutrition", None)
        if nut is not None:                      # 隠し栄養：この食材の栄養を蓄積
            nut.eat(nutrition.profile_for(self.entity.name))
        engine.message_log.add_message(
            f"{self.entity.name} を食べた。満腹度が {restored} 回復した。", colors.HEAL
        )
        return True


class FoodDishConsumable(Consumable):
    """料理：食べると満腹度変化＋HP回復＋一時効果（複数可。食中毒など負の効果も）。"""

    def __init__(self, satiety: int = 0, heal: int = 0, effects=None, nutrients=None):
        self.satiety = satiety      # 満腹度の変化（食中毒では負）
        self.heal = heal
        self.effects = effects or []  # status.StatusEffect のリスト
        self.nutrients = nutrients or {}  # 隠し栄養への寄与（食材合計）

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        import copy

        f = consumer.fighter
        if f is None:
            return False
        if f.max_satiety > 0 and self.satiety:
            f.satiety = max(0, min(f.max_satiety, f.satiety + self.satiety))
        if self.heal:
            f.hp += self.heal
        for eff in self.effects:
            consumer.status_effects.append(copy.deepcopy(eff))
        nut = getattr(consumer, "nutrition", None)
        if nut is not None and self.nutrients:   # 隠し栄養：料理の栄養を蓄積
            nut.eat(self.nutrients)

        names = "・".join(e.name for e in self.effects)
        msg = f"{self.entity.name} を食べた。"
        if names:
            msg += f" {names}！"
        engine.message_log.add_message(msg, colors.HEAL)
        return True


class TentConsumable(Consumable):
    """魔法のテント：使うと歩けるテント内（拠点）へ移動する。消費されない。"""

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        if engine.in_camp:
            return False
        if not engine.game_map.safe[consumer.x, consumer.y]:
            engine.message_log.add_message(
                "ここではテントを張れない。セーフルームでだけ使える。", colors.NO_EFFECT
            )
            return False
        engine.message_log.add_message("魔法のテントを張った。", colors.WELCOME)
        engine.enter_camp()
        return False  # アイテムは消費しない


class UnlockZoneConsumable(Consumable):
    """区画開放の鍵：使うと拠点の対応区画（牧場/漁業）を開放する。消費されない。"""

    def __init__(self, zone: str, zone_label: str):
        self.zone = zone
        self.zone_label = zone_label

    def activate(self, engine: "Engine", consumer: "Entity") -> bool:
        if self.zone in engine.unlocked_zones:
            engine.message_log.add_message(
                f"{self.zone_label}はすでに開放済み。", colors.NO_EFFECT
            )
            return False
        engine.unlocked_zones.add(self.zone)
        engine.message_log.add_message(
            f"{self.zone_label}区画が開放された！（テント内で利用可）", colors.LEVEL_UP
        )
        return False  # 鍵は残る（大切なもの）


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
        sk = getattr(consumer, "skills", None)        # スキル『魔法』で威力上昇
        damage = int(self.damage * sk.magic_mult()) if sk is not None else self.damage
        engine.message_log.add_message(
            f"雷が {target.name} を撃った！ {damage} ダメージ。", colors.SCROLL
        )
        combat.inflict_damage(engine, target, damage, attacker=consumer)
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
        sk = getattr(consumer, "skills", None)        # スキル『魔法』で効果ターン延長
        turns = int(self.turns * sk.magic_mult()) if sk is not None else self.turns
        engine.message_log.add_message(
            f"{target.name} は混乱して よろめき始めた！", colors.SCROLL
        )
        target.ai = ConfusedEnemy(target, previous_ai=target.ai, turns=turns)
        return True
