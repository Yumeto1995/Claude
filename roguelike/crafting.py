"""アイテム錬金（拠点の一施設）。素材から消費アイテムを作る単純な合成。

料理は cooking.py、食料生産（栽培）は farming.py に分離した。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Recipe:
    def __init__(self, inputs: List[Tuple[str, int]], output: "Entity", output_name: str):
        self.inputs = inputs          # [(材料名, 必要数), ...]
        self.output = output          # 成果物テンプレート
        self.output_name = output_name

    @property
    def input_text(self) -> str:
        return " + ".join(f"{n}×{c}" for n, c in self.inputs)


ALCHEMY_RECIPES: List[Recipe] = [
    Recipe([("スライムのかけら", 3)], ef.healing_potion, "回復薬"),
    Recipe([("スライムのかけら", 5)], ef.lightning_scroll, "雷の巻物"),
    Recipe([("スライムのかけら", 1)], ef.bait, "エサ（釣り用）"),
]


def can_craft(items: List["Entity"], recipe: Recipe) -> bool:
    for name, count in recipe.inputs:
        if sum(1 for it in items if it.name == name) < count:
            return False
    return True


def try_craft(engine: "Engine", recipe: Recipe) -> None:
    inv = engine.player.inventory
    if not can_craft(inv.items, recipe):
        engine.message_log.add_message(
            f"材料が足りない（{recipe.input_text}）。", colors.NO_EFFECT
        )
        return
    for name, count in recipe.inputs:
        removed = 0
        for it in list(inv.items):
            if it.name == name and removed < count:
                inv.items.remove(it)
                removed += 1
    inv.items.append(recipe.output.spawn(0, 0))
    engine.message_log.add_message(f"{recipe.output_name} を作った！", colors.ITEM)
    # スキル『錬金』：一定確率でおまけがもう1つ
    sk = getattr(engine.player, "skills", None)
    if sk is not None and sk.roll(sk.alchemy_bonus_chance()) and len(inv.items) < inv.capacity:
        inv.items.append(recipe.output.spawn(0, 0))
        engine.message_log.add_message(f"錬金の妙！ {recipe.output_name} がもう1つできた。", colors.LEVEL_UP)
