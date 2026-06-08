"""食料生産＝栽培（拠点の一施設）。

拠点の畑に種を植え、ダンジョンの階を潜るうちに育ち、戻って収穫する。
畑の状態は engine.farm_plots（長さ NUM_PLOTS のリスト、各要素 None か dict）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

NUM_PLOTS = 4

# 種名 → (育つ食材テンプレート, 収穫までに歩く歩数)
SEEDS = {
    "木の実の種": (ef.nuts, 60),
    "薬草の種": (ef.herb, 60),
    "キノコの種": (ef.mushroom, 90),
}


def seed_names_in(items: List["Entity"]) -> List[str]:
    names: List[str] = []
    for it in items:
        if it.name in SEEDS and it.name not in names:
            names.append(it.name)
    return names


def has_seed(items) -> bool:
    return bool(seed_names_in(items))


def has_empty_plot(engine: "Engine") -> bool:
    return any(p is None for p in engine.farm_plots)


def has_ready(engine: "Engine") -> bool:
    return any(p is not None and p["steps_left"] <= 0 for p in engine.farm_plots)


def plant(engine: "Engine", seed_name: str, plot_index: int) -> None:
    """指定した区画に種を植える。"""
    if engine.farm_plots[plot_index] is not None:
        return
    inv = engine.player.inventory.items
    for it in inv:
        if it.name == seed_name:
            inv.remove(it)
            break
    output, steps = SEEDS[seed_name]
    engine.farm_plots[plot_index] = {
        "name": output.name, "template": output, "steps_left": steps,
    }
    engine.message_log.add_message(
        f"{seed_name} を畑{plot_index + 1}に植えた（{steps}歩で育つ）。", colors.ITEM
    )


def interact_plot(engine: "Engine", i: int) -> None:
    """畑の区画 i の上で Enter したとき：空→植える / 育成中→状態 / 完了→収穫。"""
    plot = engine.farm_plots[i]
    if plot is None:
        if not seed_names_in(engine.player.inventory.items):
            engine.message_log.add_message("植える種を持っていない。", colors.NO_EFFECT)
            return
        engine.camp_active_plot = i
        engine.camp_menu = "farm_plant"
        engine.camp_cursor = 0
    elif plot["steps_left"] <= 0:
        engine.player.inventory.items.append(plot["template"].spawn(0, 0))
        engine.message_log.add_message(f"{plot['name']} を収穫した。", colors.ITEM)
        engine.farm_plots[i] = None
    else:
        engine.message_log.add_message(
            f"{plot['name']}：あと{plot['steps_left']}歩で育つ。", colors.NO_EFFECT
        )


def grow_step(engine: "Engine") -> None:
    """プレイヤーが1歩あるくごとに作物を成長させる。"""
    for plot in engine.farm_plots:
        if plot is not None and plot["steps_left"] > 0:
            plot["steps_left"] -= 1


def plot_status_lines(engine: "Engine") -> List[str]:
    lines = []
    for i, plot in enumerate(engine.farm_plots):
        if plot is None:
            lines.append(f"畑{i + 1}: 空き")
        elif plot["steps_left"] <= 0:
            lines.append(f"畑{i + 1}: {plot['name']} 収穫できる！")
        else:
            lines.append(f"畑{i + 1}: {plot['name']}（あと{plot['steps_left']}歩）")
    return lines
