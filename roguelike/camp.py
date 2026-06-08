"""拠点の設備メニュー制御（テント内で設備の上で Enter したとき開く）。

engine.camp_menu（文字列）で開いているメニューを表す：
  cook → cook_method（料理）/ alchemy（錬金）/ storage（収納）/ farm_plant（畑に植える）
None のときはメニューを閉じてテント内を歩いている状態。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import colors
import cooking
import crafting
import farming

if TYPE_CHECKING:
    from engine import Engine

_BACK: Dict[str, Any] = {"text": "とじる", "enabled": True, "kind": "back"}

TITLES = {
    "cook": "料理：鍋に食材を入れる",
    "cook_method": "料理：調理法を選ぶ",
    "alchemy": "アイテム錬金",
    "storage": "収納",
    "farm_plant": "畑：種を植える",
}


def title(engine: "Engine") -> str:
    return TITLES.get(engine.camp_menu, "")


def options(engine: "Engine") -> List[Dict[str, Any]]:
    menu = engine.camp_menu
    items = engine.player.inventory.items

    if menu == "alchemy":
        opts = [
            {"text": f"{r.output_name}  ←  {r.input_text}",
             "enabled": crafting.can_craft(items, r), "kind": "alchemy", "data": r}
            for r in crafting.ALCHEMY_RECIPES
        ]
        opts.append(_BACK)
        return opts

    if menu == "cook":
        opts = []
        for name in cooking.ingredient_names_in(items):
            rest = cooking.available(items, engine.cook_pot, name)
            opts.append({"text": f"{name} を入れる（残り{rest}）",
                         "enabled": rest > 0, "kind": "pot_add", "data": name})
        opts.append({"text": f"調理する（鍋に{len(engine.cook_pot)}品）",
                     "enabled": len(engine.cook_pot) > 0, "kind": "goto", "data": "cook_method"})
        opts.append({"text": "鍋を空にする",
                     "enabled": len(engine.cook_pot) > 0, "kind": "pot_clear"})
        opts.append(_BACK)
        return opts

    if menu == "cook_method":
        opts = [{"text": m, "enabled": True, "kind": "cook_do", "data": m}
                for m in cooking.METHOD_NAMES]
        opts.append(_BACK)
        return opts

    if menu == "storage":
        equip = engine.player.equipment
        opts = []
        for it in list(items):
            opts.append({"text": f"預ける: {it.name}",
                         "enabled": not equip.item_is_equipped(it),
                         "kind": "deposit", "data": it})
        space = len(items) < engine.player.inventory.capacity
        for it in list(engine.storage):
            opts.append({"text": f"取り出す: {it.name}", "enabled": space,
                         "kind": "withdraw", "data": it})
        opts.append(_BACK)
        return opts

    if menu == "farm_plant":
        opts = [{"text": f"{name} を植える", "enabled": True, "kind": "plant", "data": name}
                for name in farming.seed_names_in(items)]
        opts.append(_BACK)
        return opts

    return [_BACK]


def info(engine: "Engine") -> List[str]:
    menu = engine.camp_menu
    if menu == "cooking":
        return []
    if menu in ("cook", "cook_method"):
        return [f"鍋: {cooking.pot_summary(engine.cook_pot)}"]
    if menu == "storage":
        names = ", ".join(it.name for it in engine.storage) or "空"
        return [f"倉庫({len(engine.storage)}): {names}"]
    if menu == "farm_plant":
        return [f"畑{engine.camp_active_plot + 1} に植える"]
    return []


def move_cursor(engine: "Engine", delta: int) -> None:
    n = len(options(engine))
    engine.camp_cursor = (engine.camp_cursor + delta) % n


def select(engine: "Engine") -> None:
    opts = options(engine)
    if not opts:
        return
    cur = opts[min(engine.camp_cursor, len(opts) - 1)]
    if not cur.get("enabled", True):
        return
    kind = cur["kind"]
    inv = engine.player.inventory

    if kind == "back":
        back(engine)
    elif kind == "goto":
        engine.camp_menu = cur["data"]
        engine.camp_cursor = 0
    elif kind == "alchemy":
        crafting.try_craft(engine, cur["data"])
    elif kind == "pot_add":
        engine.cook_pot.append(cur["data"])
    elif kind == "pot_clear":
        engine.cook_pot = []
    elif kind == "cook_do":
        cooking.cook(engine, engine.cook_pot, cur["data"])
        engine.cook_pot = []
        engine.camp_menu = "cook"
        engine.camp_cursor = 0
    elif kind == "deposit":
        item = cur["data"]
        if item in inv.items:
            inv.items.remove(item)
            engine.storage.append(item)
    elif kind == "withdraw":
        item = cur["data"]
        if len(inv.items) < inv.capacity and item in engine.storage:
            engine.storage.remove(item)
            inv.items.append(item)
    elif kind == "plant":
        farming.plant(engine, cur["data"], engine.camp_active_plot)
        engine.camp_menu = None


def back(engine: "Engine") -> None:
    menu = engine.camp_menu
    if menu == "cook_method":
        engine.camp_menu = "cook"
    elif menu == "cook":
        engine.cook_pot = []
        engine.camp_menu = None
    else:  # alchemy / storage / farm_plant
        engine.camp_menu = None
    engine.camp_cursor = 0
