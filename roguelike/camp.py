"""拠点（魔法のテント）のメニュー制御。

engine.camp_screen（文字列）で画面を切り替える：
  main → cooking / alchemy / farm（→ farm_plant）/ cook
options() が現在画面の選択肢、info() が補足表示、select()/back() が操作。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import colors
import cooking
import crafting
import farming

if TYPE_CHECKING:
    from engine import Engine

_BACK: Dict[str, Any] = {"text": "もどる", "enabled": True, "kind": "back"}

TITLES = {
    "main": "魔法のテント",
    "cooking": "料理",
    "cook": "料理：食材を組み合わせる",
    "alchemy": "アイテム錬金",
    "farm": "食料生産（畑）",
    "farm_plant": "種を植える",
}


def title(engine: "Engine") -> str:
    return TITLES.get(engine.camp_screen, "魔法のテント")


def options(engine: "Engine") -> List[Dict[str, Any]]:
    s = engine.camp_screen
    items = engine.player.inventory.items

    if s == "main":
        return [
            {"text": "料理", "enabled": True, "kind": "goto", "data": "cooking"},
            {"text": "アイテム錬金", "enabled": True, "kind": "goto", "data": "alchemy"},
            {"text": "食料生産（畑）", "enabled": True, "kind": "goto", "data": "farm"},
            {"text": "ダンジョンに戻る", "enabled": True, "kind": "exit"},
        ]

    if s == "alchemy":
        opts = [
            {
                "text": f"{r.output_name}  ←  {r.input_text}",
                "enabled": crafting.can_craft(items, r),
                "kind": "alchemy",
                "data": r,
            }
            for r in crafting.ALCHEMY_RECIPES
        ]
        opts.append(_BACK)
        return opts

    if s == "farm":
        return [
            {
                "text": "種を植える",
                "enabled": farming.has_seed(items) and farming.has_empty_plot(engine),
                "kind": "goto",
                "data": "farm_plant",
            },
            {"text": "収穫する", "enabled": farming.has_ready(engine), "kind": "harvest"},
            _BACK,
        ]

    if s == "farm_plant":
        opts = [
            {"text": f"{name} を植える", "enabled": True, "kind": "plant", "data": name}
            for name in farming.seed_names_in(items)
        ]
        opts.append(_BACK)
        return opts

    if s == "cooking":
        return [
            {
                "text": "食材を組み合わせて作る",
                "enabled": cooking.has_ingredients(items),
                "kind": "goto",
                "data": "cook",
            },
            _BACK,
        ]

    if s == "cook":
        opts = [
            {"text": f"{name}（{cooking._count(items, name)}個）", "enabled": True,
             "kind": "pick", "data": name}
            for name in cooking.ingredient_names_in(items)
        ]
        opts.append(_BACK)
        return opts

    return [_BACK]


def info(engine: "Engine") -> List[str]:
    s = engine.camp_screen
    if s in ("farm", "farm_plant"):
        return farming.plot_status_lines(engine)
    if s == "cooking":
        if engine.discovered_dishes:
            return ["発見済み: " + " / ".join(sorted(engine.discovered_dishes))]
        return ["（まだ料理を発見していない。食材2つを試そう）"]
    if s == "cook":
        if engine.cook_first:
            return [f"1つ目: {engine.cook_first}  → 2つ目の食材を選ぶ"]
        return ["1つ目の食材を選ぶ"]
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

    if kind == "back":
        back(engine)
    elif kind == "exit":
        engine.in_camp = False
        engine.message_log.add_message("テントをたたんでダンジョンに戻った。", colors.WELCOME)
    elif kind == "goto":
        engine.camp_screen = cur["data"]
        engine.camp_cursor = 0
        engine.cook_first = None
    elif kind == "alchemy":
        crafting.try_craft(engine, cur["data"])  # 画面はそのまま
    elif kind == "harvest":
        farming.harvest(engine)
    elif kind == "plant":
        farming.plant(engine, cur["data"])
        engine.camp_screen = "farm"
        engine.camp_cursor = 0
    elif kind == "pick":
        cooking.pick(engine, cur["data"])


def back(engine: "Engine") -> None:
    s = engine.camp_screen
    if s == "farm_plant":
        engine.camp_screen = "farm"
    elif s == "cook":
        if engine.cook_first is not None:
            engine.cook_first = None  # 1つ目の選択をキャンセル
        else:
            engine.camp_screen = "cooking"
    elif s in ("cooking", "alchemy", "farm"):
        engine.camp_screen = "main"
    else:  # main
        engine.in_camp = False
    engine.camp_cursor = 0
