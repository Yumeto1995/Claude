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
import fishery
import nutrition
import ranch

if TYPE_CHECKING:
    from engine import Engine

_BACK: Dict[str, Any] = {"text": "とじる", "enabled": True, "kind": "back"}

TITLES = {
    "health": "体調を調べる（栄養状態）",
    "cook": "料理：鍋に食材を入れる",
    "cook_method": "料理：調理法を選ぶ",
    "alchemy": "アイテム錬金",
    "storage": "収納",
    "farm_plant": "畑：種を植える",
    "ranch": "牧場（畜産）",
    "ranch_place": "牧場：動物を入れる",
    "fishery": "漁業（漁・養殖）",
    "fishery_place": "漁業：養殖する魚を入れる",
}


def _slot_options(slots, labels, has_src, place_kind, collect_kind):
    """牧柵/いけすの各スロットを選択肢にする（空き→置く / 育成中→不可 / 完了→収穫）。"""
    opts = []
    for i, s in enumerate(slots):
        if s is None:
            opts.append({"text": labels(i), "enabled": has_src,
                         "kind": place_kind, "data": i})
        elif s["steps_left"] <= 0:
            opts.append({"text": labels(i), "enabled": True,
                         "kind": collect_kind, "data": i})
        else:
            opts.append({"text": labels(i), "enabled": False, "kind": "noop"})
    return opts


def title(engine: "Engine") -> str:
    return TITLES.get(engine.camp_menu, "")


def options(engine: "Engine") -> List[Dict[str, Any]]:
    menu = engine.camp_menu
    items = engine.player.inventory.items

    if menu == "health":
        nut = engine.player.nutrition
        opts = [
            {"text": f"{nutrition.NUTRIENTS[k]}：{nut.status_label(k)}",
             "enabled": False, "kind": "noop"}
            for k in nutrition.KEYS
        ]
        opts.append(_BACK)
        return opts

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

    if menu == "ranch":
        opts = _slot_options(
            engine.ranch_pens, lambda i: ranch.label(engine, i),
            bool(ranch.animal_names_in(items)), "ranch_place", "ranch_collect")
        opts.append(_BACK)
        return opts

    if menu == "ranch_place":
        opts = [{"text": f"{name} を入れる", "enabled": True, "kind": "ranch_do", "data": name}
                for name in ranch.animal_names_in(items)]
        opts.append(_BACK)
        return opts

    if menu == "fishery":
        bait = sum(1 for it in items if it.name == "エサ")
        opts = [{"text": f"釣る（エサ {bait}）", "enabled": bait > 0, "kind": "fish"}]
        opts += _slot_options(
            engine.fishery_tanks, lambda i: fishery.label(engine, i),
            bool(fishery.breed_names_in(items)), "fishery_place", "fishery_collect")
        opts.append(_BACK)
        return opts

    if menu == "fishery_place":
        opts = [{"text": f"{name} を養殖する", "enabled": True, "kind": "fishery_do", "data": name}
                for name in fishery.breed_names_in(items)]
        opts.append(_BACK)
        return opts

    return [_BACK]


def info(engine: "Engine") -> List[str]:
    menu = engine.camp_menu
    if menu == "health":
        nut = engine.player.nutrition
        if nut.deficient:
            syms = "・".join(nutrition.SYMPTOMS[k] for k in nutrition.KEYS if k in nut.deficient)
            return [f"気になる症状: {syms}", "不足している栄養を含む食事で改善する。"]
        if nut.is_good:
            return ["栄養バランス良好＝好調！（攻+1 防+1 スタミナ回復↑）"]
        return ["大きな偏りはなし。バランスよく食べよう。"]
    if menu == "cooking":
        return []
    if menu in ("cook", "cook_method"):
        return [f"鍋: {cooking.pot_summary(engine.cook_pot)}"]
    if menu == "storage":
        names = ", ".join(it.name for it in engine.storage) or "空"
        return [f"倉庫({len(engine.storage)}): {names}"]
    if menu == "farm_plant":
        return [f"畑{engine.camp_active_plot + 1} に植える"]
    if menu == "ranch":
        return ["動物を入れて歩くと、卵やミルクを繰り返し収穫できる。"]
    if menu == "fishery":
        return ["エサで釣り、釣った魚は養殖いけすで増やせる。フグは要調理。"]
    if menu in ("ranch_place", "fishery_place"):
        return [f"スロット{engine.camp_active_plot + 1} に入れる"]
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
    elif kind == "ranch_place":
        engine.camp_active_plot = cur["data"]
        engine.camp_menu, engine.camp_cursor = "ranch_place", 0
    elif kind == "ranch_collect":
        ranch.collect(engine, cur["data"])
    elif kind == "ranch_do":
        ranch.place(engine, engine.camp_active_plot, cur["data"])
        engine.camp_menu, engine.camp_cursor = "ranch", 0
    elif kind == "fish":
        fishery.fish(engine)
    elif kind == "fishery_place":
        engine.camp_active_plot = cur["data"]
        engine.camp_menu, engine.camp_cursor = "fishery_place", 0
    elif kind == "fishery_collect":
        fishery.collect(engine, cur["data"])
    elif kind == "fishery_do":
        fishery.place(engine, engine.camp_active_plot, cur["data"])
        engine.camp_menu, engine.camp_cursor = "fishery", 0


def back(engine: "Engine") -> None:
    menu = engine.camp_menu
    if menu == "cook_method":
        engine.camp_menu = "cook"
    elif menu == "cook":
        engine.cook_pot = []
        engine.camp_menu = None
    elif menu == "ranch_place":
        engine.camp_menu = "ranch"
    elif menu == "fishery_place":
        engine.camp_menu = "fishery"
    else:  # alchemy / storage / farm_plant / ranch / fishery
        engine.camp_menu = None
    engine.camp_cursor = 0
