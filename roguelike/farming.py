"""食料生産＝栽培（拠点の畑）。

拠点の畑に種を植え、ダンジョンの階を潜るうちに育ち、戻って収穫する。
畑は自由配置の農場オブジェクト（kind="farm"）。content=None なら空き、
dict（{"name","template","steps_left"}）なら栽培中。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

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


def plant_obj(engine: "Engine", obj, seed_name: str) -> None:
    """畑オブジェクトに種を植える。"""
    inv = engine.player.inventory.items
    for it in inv:
        if it.name == seed_name:
            inv.remove(it)
            break
    output, steps = SEEDS[seed_name]
    sk = getattr(engine.player, "skills", None)   # スキル『農業』で成長が速く
    if sk is not None:
        steps = max(1, int(steps * sk.growth_factor("farming")))
    obj["content"] = {"name": output.name, "template": output, "steps_left": steps}
    engine.message_log.add_message(
        f"{seed_name} を植えた（{steps}歩で育つ）。", colors.ITEM
    )


def harvest_obj(engine: "Engine", obj) -> None:
    """育った作物を収穫し、畑を空にする。"""
    c = obj["content"]
    if c is None or c["steps_left"] > 0:
        return
    engine.player.inventory.items.append(c["template"].spawn(0, 0))
    engine.message_log.add_message(f"{c['name']} を収穫した。", colors.ITEM)
    obj["content"] = None


def plot_label(obj) -> str:
    c = obj["content"]
    if c is None:
        return "畑: 空き"
    if c["steps_left"] <= 0:
        return f"畑: {c['name']} 収穫できる！"
    return f"畑: {c['name']}（あと{c['steps_left']}歩）"
