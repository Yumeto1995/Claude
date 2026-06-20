"""食材の鮮度・腐敗。

持ち物の食料は毎ターン古くなり、傷むと満腹/栄養の回復が下がり、腐敗すると
食中毒のリスクが出る（非常時は賭けで食べられる）。拠点テントの倉庫に預けた
食料は傷まない（tick の対象外＝唯一の保存手段）。

各食料 Entity は shelf_life（腐るまでのターン数）と freshness（残り）を持つ。
shelf_life=None のアイテム（武器・巻物・素材など）は腐らない。
"""
from __future__ import annotations

import random

from status import StatusEffect

# 段階しきい値（残り鮮度 / 最大 の割合）
FRESH = 0.85      # これ以上は「新鮮」
SPOILING = 0.35   # これ以下で「傷み」
ROTTEN = 0.0      # これ以下で「腐敗」


def is_perishable(item) -> bool:
    return getattr(item, "shelf_life", None) is not None


def fraction(item) -> float:
    """残り鮮度の割合 0..1（腐敗対象でなければ 1）。"""
    sl = getattr(item, "shelf_life", None)
    if not sl:
        return 1.0
    fr = getattr(item, "freshness", sl)
    if fr is None:
        return 1.0
    return max(0.0, min(1.0, fr / sl))


def stage(item):
    """表示用 (ラベル, 色)。新鮮/傷み/腐敗のみラベル、普通は空。"""
    if not is_perishable(item):
        return ("", None)
    f = fraction(item)
    if f <= ROTTEN:
        return ("腐敗", (214, 92, 80))
    if f <= SPOILING:
        return ("傷み", (220, 180, 80))
    if f >= FRESH:
        return ("新鮮", (130, 200, 120))
    return ("", None)


def tick(player) -> None:
    """持ち物の食料の鮮度を1ターン分減らす（倉庫の食料は対象外）。"""
    inv = getattr(player, "inventory", None)
    if inv is None:
        return
    for it in inv.items:
        if is_perishable(it) and it.freshness is not None:
            it.freshness = max(0, it.freshness - 1)


def freshness_factor(item) -> float:
    """満腹/栄養の回復倍率（傷み 0.6 / 腐敗 0.3）。"""
    if not is_perishable(item):
        return 1.0
    f = fraction(item)
    if f > SPOILING:
        return 1.0
    if f > ROTTEN:
        return 0.6
    return 0.3


def poison_on_eat(item):
    """食べたときの食中毒。発症すれば StatusEffect、しなければ None。"""
    if not is_perishable(item):
        return None
    f = fraction(item)
    if f > SPOILING:
        return None
    if f > ROTTEN:                      # 傷み：低確率・軽症
        if random.random() < 0.25:
            return StatusEffect("腹痛", turns=15, power_bonus=-1, defense_bonus=-1)
        return None
    if random.random() < 0.7:           # 腐敗：高確率・重症
        return StatusEffect("食中毒", turns=30, power_bonus=-3, defense_bonus=-3)
    return None
