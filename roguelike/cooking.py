"""料理（拠点の一施設）。食材2つを組み合わせて効果付き料理を作る。

組み合わせがレシピに一致すれば料理（発見）、しなければ失敗作。
作った料理は持ち物に入り、食べると満腹度回復＋一時バフが付く。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

# 料理に使える食材
INGREDIENTS = {"木の実", "薬草", "キノコ"}

# 食材ペア（名前のソート済タプル）→ 料理テンプレート
RECIPES = {
    tuple(sorted(["木の実", "薬草"])): ef.power_dish,
    tuple(sorted(["木の実", "キノコ"])): ef.guard_dish,
    tuple(sorted(["薬草", "キノコ"])): ef.vigor_dish,
}


def ingredient_names_in(items: List["Entity"]) -> List[str]:
    """持ち物にある食材の名前（重複なし）。"""
    names: List[str] = []
    for it in items:
        if it.name in INGREDIENTS and it.name not in names:
            names.append(it.name)
    return names


def has_ingredients(items: List["Entity"]) -> bool:
    return bool(ingredient_names_in(items))


def _count(items, name):
    return sum(1 for it in items if it.name == name)


def _remove_one(items, name):
    for it in items:
        if it.name == name:
            items.remove(it)
            return


def pick(engine: "Engine", name: str) -> None:
    """食材を1つ選ぶ。1つ目なら記録、2つ目なら調理する。"""
    if engine.cook_first is None:
        engine.cook_first = name
    else:
        _cook(engine, engine.cook_first, name)
        engine.cook_first = None
        engine.camp_screen = "cooking"
        engine.camp_cursor = 0


def _cook(engine: "Engine", name1: str, name2: str) -> None:
    inv = engine.player.inventory.items
    # 在庫チェック（同じ食材2つなら2個必要）
    if name1 == name2:
        if _count(inv, name1) < 2:
            engine.message_log.add_message(f"{name1} が2つ必要だ。", colors.NO_EFFECT)
            return
    elif _count(inv, name1) < 1 or _count(inv, name2) < 1:
        engine.message_log.add_message("食材が足りない。", colors.NO_EFFECT)
        return

    _remove_one(inv, name1)
    _remove_one(inv, name2)

    template = RECIPES.get(tuple(sorted([name1, name2])))
    if template is None:
        inv.append(ef.failed_dish.spawn(0, 0))
        engine.message_log.add_message("う〜ん、失敗作ができてしまった…", colors.NO_EFFECT)
        return

    dish = template.spawn(0, 0)
    inv.append(dish)
    if dish.name not in engine.discovered_dishes:
        engine.discovered_dishes.add(dish.name)
        engine.message_log.add_message(f"{dish.name} の作り方を覚えた！", colors.LEVEL_UP)
    else:
        engine.message_log.add_message(f"{dish.name} を作った。", colors.ITEM)
