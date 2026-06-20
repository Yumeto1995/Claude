"""料理：栄養素ベースの自由調理。

任意の食材を「鍋」に入れ、調理法を選んで作る。完成品の効果は
  栄養素の合計 × 調理法の保持率 × 入れすぎ補正
から動的に決まる。毒性が高いと食中毒（逆効果）になる。
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Dict, List

import colors
from nutrition import FOOD_NUTRITION as NUTRITION, KEYS as NUTRIENTS
from status import StatusEffect

if TYPE_CHECKING:
    from engine import Engine

# 栄養素データ（NUTRIENTS / NUTRITION）は nutrition.py を単一情報源として共有する。

# 調理法 → 栄養素ごとの保持率＋毒性倍率。
# 調理法 → 栄養素ごとの保持率＋毒性倍率。ビタミンは加熱に弱い（特にC）。
METHODS: Dict[str, Dict[str, float]] = {
    "生":   {"protein": 1.0, "fat": 1.0, "carb": 1.0, "vitA": 1.0, "vitB": 1.0,
             "vitC": 1.0, "iron": 1.0, "calcium": 1.0, "tox": 1.0},
    "焼く": {"protein": 1.2, "fat": 1.1, "carb": 1.0, "vitA": 0.7, "vitB": 0.6,
             "vitC": 0.4, "iron": 1.0, "calcium": 1.0, "tox": 0.5},
    "煮る": {"protein": 0.95, "fat": 0.9, "carb": 1.15, "vitA": 0.8, "vitB": 0.6,
             "vitC": 0.5, "iron": 0.9, "calcium": 0.9, "tox": 0.25},
    "蒸す": {"protein": 1.0, "fat": 1.0, "carb": 1.0, "vitA": 0.95, "vitB": 0.85,
             "vitC": 0.85, "iron": 0.95, "calcium": 0.95, "tox": 0.55},
    "揚げる": {"protein": 1.1, "fat": 1.4, "carb": 1.1, "vitA": 0.6, "vitB": 0.5,
              "vitC": 0.3, "iron": 1.0, "calcium": 1.0, "tox": 0.5},
    "干す": {"protein": 1.0, "fat": 0.85, "carb": 1.0, "vitA": 0.7, "vitB": 0.4,
             "vitC": 0.2, "iron": 1.1, "calcium": 1.1, "tox": 0.6},
    "漬ける": {"protein": 0.95, "fat": 0.95, "carb": 1.0, "vitA": 0.85, "vitB": 0.7,
              "vitC": 0.9, "iron": 1.0, "calcium": 1.0, "tox": 0.3},
    "発酵": {"protein": 1.15, "fat": 0.9, "carb": 0.8, "vitA": 0.85, "vitB": 1.4,
             "vitC": 0.6, "iron": 1.15, "calcium": 1.1, "tox": 0.2},
}
METHOD_NAMES = list(METHODS.keys())

# 調理法ごとの完成品の日持ち（保存系=干す/漬ける/発酵 は長い）。
METHOD_SHELF: Dict[str, int] = {
    "生": 150, "焼く": 150, "煮る": 150, "蒸す": 150, "揚げる": 150,
    "干す": 500, "漬ける": 400, "発酵": 450,
}
# 満腹補正（干物は水分が抜けて軽い）。
METHOD_SATIETY: Dict[str, float] = {"干す": 0.6}

# 名物料理：特定の食材の組合せ（＋指定があれば調理法）で専用料理になる。
# ingredients は「鍋の中身がちょうどこれと一致」したとき成立（毒料理では不成立）。
# 効果は栄養ベースの満腹/回復にボーナスを上乗せする。
RECIPES: List[Dict] = [
    {"ingredients": {"卵": 1, "ミルク": 1}, "method": None, "name": "ふわとろオムレツ",
     "bonus_satiety": 12, "bonus_heal": 6,
     "effects": [StatusEffect("ちから+2", turns=30, power_bonus=2)]},
    {"ingredients": {"肉": 1}, "method": "干す", "name": "干し肉",
     "bonus_satiety": 6, "shelf_life": 700,
     "effects": [StatusEffect("ちから+1", turns=24, power_bonus=1)]},
    {"ingredients": {"果実": 2}, "method": None, "name": "フルーツサラダ",
     "bonus_heal": 14, "effects": []},
    {"ingredients": {"チーズ": 1, "木の実": 1}, "method": None, "name": "チーズ焼き",
     "bonus_satiety": 14,
     "effects": [StatusEffect("まもり+2", turns=30, defense_bonus=2)]},
    {"ingredients": {"蜂蜜": 1, "果実": 1}, "method": None, "name": "蜂蜜がけフルーツ",
     "bonus_satiety": 10, "bonus_heal": 8, "shelf_life": 300, "effects": []},
]


def _match_recipe(pot: List[str], method: str):
    """鍋の中身（＋調理法）が名物料理に一致すれば、その定義を返す。無ければ None。"""
    counts = dict(Counter(pot))
    for r in RECIPES:
        if counts != r["ingredients"]:
            continue
        if r["method"] is not None and r["method"] != method:
            continue
        return r
    return None

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

def compute_dish(pot: List[str], method: str, boost: float = 1.0) -> Dict:
    """鍋の中身と調理法から、完成料理の効果を計算する。

    boost はスキル『料理』による栄養（効果）の倍率（毒性は強めない）。
    """
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
        total[k] = total[k] * mult[k] * dilution * boost
    tox *= mult["tox"]

    satiety = int((total["carb"] * 1.4 + total["fat"] * 1.1) * METHOD_SATIETY.get(method, 1.0))
    heal = int((total["vitA"] + total["vitB"] + total["vitC"]) * 0.5)
    nutrients = {k: int(round(total[k])) for k in NUTRIENTS}  # 料理が持つ栄養（食事で蓄積）
    shelf = METHOD_SHELF.get(method, 150)  # 保存系の調理法は日持ちする
    effects: List[StatusEffect] = []
    pmag = min(int(total["protein"] // 8), 6)
    if pmag > 0:
        effects.append(StatusEffect(f"ちから+{pmag}", turns=15 + pmag * 3, power_bonus=pmag))
    dmag = min(int((total["iron"] + total["calcium"]) // 8), 6)
    if dmag > 0:
        effects.append(StatusEffect(f"まもり+{dmag}", turns=15 + dmag * 3, defense_bonus=dmag))

    if tox >= TOX_SEVERE:
        return {
            "name": "あたりそうな料理", "satiety": -20, "heal": 0, "toxic": True,
            "effects": [StatusEffect("食中毒", turns=30, power_bonus=-3, defense_bonus=-3)],
            "nutrients": nutrients, "shelf_life": shelf,
        }
    if tox >= TOX_MILD:
        return {
            "name": "あやしい料理", "satiety": max(0, satiety // 2), "heal": 0, "toxic": True,
            "effects": [StatusEffect("腹痛", turns=18, power_bonus=-1, defense_bonus=-1)],
            "nutrients": nutrients, "shelf_life": shelf,
        }

    recipe = _match_recipe(pot, method)   # 名物料理（毒でない時のみ成立）
    if recipe is not None:
        for e in recipe["effects"]:
            effects.append(e)
        return {
            "name": recipe["name"],
            "satiety": satiety + recipe.get("bonus_satiety", 0),
            "heal": heal + recipe.get("bonus_heal", 0),
            "effects": effects, "toxic": False,
            "nutrients": nutrients,
            "shelf_life": recipe.get("shelf_life", shelf),
        }

    return {
        "name": _name_for(satiety, heal, pmag, dmag),
        "satiety": satiety, "heal": heal, "effects": effects, "toxic": False,
        "nutrients": nutrients, "shelf_life": shelf,
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

    sk = getattr(engine.player, "skills", None)
    boost = sk.cooking_mult() if sk is not None else 1.0
    res = compute_dish(pot, method, boost)

    from components.consumable import FoodDishConsumable
    from entity import Entity

    dish = Entity(
        sprite="dish", name=res["name"], blocks_movement=False,
        consumable=FoodDishConsumable(
            satiety=res["satiety"], heal=res["heal"], effects=res["effects"],
            nutrients=res.get("nutrients"),
        ),
        shelf_life=res.get("shelf_life", 150),  # 干す/漬ける/発酵 は日持ちする
    )
    inv.append(dish)
    engine.discovered_dishes.add(res["name"])

    eff_txt = "・".join(e.name for e in res["effects"]) if res["effects"] else "効果なし"
    color = colors.NO_EFFECT if res["toxic"] else colors.LEVEL_UP
    engine.message_log.add_message(
        f"{method}て「{res['name']}」ができた（{eff_txt}）。", color
    )
