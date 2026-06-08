"""料理：栄養素ベースの自由調理。

任意の食材を「鍋」に入れ、調理法を選んで作る。完成品の効果は
  栄養素の合計 × 調理法の保持率 × 入れすぎ補正
から動的に決まる。毒性が高いと食中毒（逆効果）になる。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

import colors
from status import StatusEffect

if TYPE_CHECKING:
    from engine import Engine

# 栄養素の種類（毒性 tox は別扱い）
NUTRIENTS = ["protein", "mineral", "vitamin", "carb", "fat"]

# 食材ごとの栄養素（未記載は0）。tox は毒性。
NUTRITION: Dict[str, Dict[str, int]] = {
    "木の実": {"carb": 16, "fat": 18, "protein": 4},
    "薬草":   {"vitamin": 24, "mineral": 6},
    "キノコ": {"mineral": 18, "protein": 8, "tox": 5},
    "肉":     {"protein": 28, "fat": 12, "tox": 4},
    "毒キノコ": {"mineral": 12, "protein": 6, "tox": 22},
    # 畜産・漁業の産物
    "卵":     {"protein": 14, "fat": 10},
    "ミルク": {"protein": 8, "fat": 8, "mineral": 12},
    "魚":     {"protein": 22, "fat": 8, "vitamin": 4},
    "大魚":   {"protein": 34, "fat": 14},
    "フグ":   {"protein": 24, "tox": 18},
}

# 調理法 → 栄養素ごとの保持率＋毒性倍率。
METHODS: Dict[str, Dict[str, float]] = {
    "生":   {"protein": 1.0, "mineral": 1.0, "vitamin": 1.0, "carb": 1.0, "fat": 1.0, "tox": 1.0},
    "焼く": {"protein": 1.2, "mineral": 1.0, "vitamin": 0.5, "carb": 1.0, "fat": 1.1, "tox": 0.5},
    "煮る": {"protein": 0.95, "mineral": 0.85, "vitamin": 0.7, "carb": 1.15, "fat": 0.9, "tox": 0.25},
    "蒸す": {"protein": 1.0, "mineral": 0.95, "vitamin": 0.95, "carb": 1.0, "fat": 1.0, "tox": 0.55},
}
METHOD_NAMES = list(METHODS.keys())

TOX_MILD = 6     # これ以上で腹痛
TOX_SEVERE = 12  # これ以上で食中毒


# ---- 鍋（選択中の食材）操作 ----

def ingredient_names_in(items) -> List[str]:
    """持ち物にある食材の名前（重複なし）。"""
    names: List[str] = []
    for it in items:
        if it.name in NUTRITION and it.name not in names:
            names.append(it.name)
    return names


def has_ingredients(items) -> bool:
    return bool(ingredient_names_in(items))


def available(items, pot: List[str], name: str) -> int:
    """まだ鍋に入れられる残り数（持ち物の数 − 鍋に入れた数）。"""
    in_inv = sum(1 for it in items if it.name == name)
    in_pot = pot.count(name)
    return in_inv - in_pot


def pot_summary(pot: List[str]) -> str:
    if not pot:
        return "空"
    counts: Dict[str, int] = {}
    for n in pot:
        counts[n] = counts.get(n, 0) + 1
    return ", ".join(f"{n}×{c}" for n, c in counts.items())


# ---- 調理 ----

def compute_dish(pot: List[str], method: str) -> Dict:
    """鍋の中身と調理法から、完成料理の効果を計算する。"""
    mult = METHODS[method]
    n = len(pot)
    # 入れすぎ補正：4品以上から効果が薄まる
    dilution = 1.0 if n <= 3 else max(0.5, 1.0 - 0.12 * (n - 3))

    total = {k: 0.0 for k in NUTRIENTS}
    tox = 0.0
    for name in pot:
        prof = NUTRITION.get(name, {})
        for k in NUTRIENTS:
            total[k] += prof.get(k, 0)
        tox += prof.get("tox", 0)
    for k in NUTRIENTS:
        total[k] = total[k] * mult[k] * dilution
    tox *= mult["tox"]

    satiety = int(total["carb"] * 1.4 + total["fat"] * 1.1)
    heal = int(total["vitamin"] * 0.5)
    effects: List[StatusEffect] = []
    pmag = min(int(total["protein"] // 8), 6)
    if pmag > 0:
        effects.append(StatusEffect(f"ちから+{pmag}", turns=15 + pmag * 3, power_bonus=pmag))
    dmag = min(int(total["mineral"] // 8), 6)
    if dmag > 0:
        effects.append(StatusEffect(f"まもり+{dmag}", turns=15 + dmag * 3, defense_bonus=dmag))

    if tox >= TOX_SEVERE:
        return {
            "name": "あたりそうな料理", "satiety": -20, "heal": 0, "toxic": True,
            "effects": [StatusEffect("食中毒", turns=30, power_bonus=-3, defense_bonus=-3)],
        }
    if tox >= TOX_MILD:
        return {
            "name": "あやしい料理", "satiety": max(0, satiety // 2), "heal": 0, "toxic": True,
            "effects": [StatusEffect("腹痛", turns=18, power_bonus=-1, defense_bonus=-1)],
        }

    return {
        "name": _name_for(satiety, heal, pmag, dmag),
        "satiety": satiety, "heal": heal, "effects": effects, "toxic": False,
    }


def _name_for(satiety, heal, pmag, dmag) -> str:
    scores = [
        ("ちからの料理", pmag * 4),
        ("まもりの料理", dmag * 4),
        ("回復の料理", heal),
        ("スタミナ料理", satiety // 6),
    ]
    strong = sum(1 for _, v in scores if v >= 8)
    if strong >= 2:
        return "ごちそう"
    best = max(scores, key=lambda t: t[1])
    return best[0] if best[1] >= 2 else "微妙な料理"


def cook(engine: "Engine", pot: List[str], method: str) -> None:
    inv = engine.player.inventory.items
    # 鍋の食材を消費
    for name in pot:
        for it in inv:
            if it.name == name:
                inv.remove(it)
                break

    res = compute_dish(pot, method)

    from components.consumable import FoodDishConsumable
    from entity import Entity

    dish = Entity(
        sprite="dish", name=res["name"], blocks_movement=False,
        consumable=FoodDishConsumable(
            satiety=res["satiety"], heal=res["heal"], effects=res["effects"]
        ),
    )
    inv.append(dish)
    engine.discovered_dishes.add(res["name"])

    eff_txt = "・".join(e.name for e in res["effects"]) if res["effects"] else "効果なし"
    color = colors.NO_EFFECT if res["toxic"] else colors.LEVEL_UP
    engine.message_log.add_message(
        f"{method}て「{res['name']}」ができた（{eff_txt}）。", color
    )
