"""拠点（魔法のテント）での合成：料理・アイテム錬金・食料生産。

レシピはデータとして定義しておき、ここを増やせば作れるものが増える。
材料は持ち物の中の同名アイテムを消費し、成果物を1つ作る。
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, List, Tuple

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Station(Enum):
    COOKING = auto()   # 料理
    ALCHEMY = auto()   # アイテム錬金
    FOOD = auto()      # 食料生産


STATION_LABELS = {
    Station.COOKING: "料理",
    Station.ALCHEMY: "アイテム錬金",
    Station.FOOD: "食料生産",
}
STATIONS: List[Station] = [Station.COOKING, Station.ALCHEMY, Station.FOOD]


class Recipe:
    def __init__(
        self,
        station: Station,
        inputs: List[Tuple[str, int]],
        output: "Entity",
        output_name: str,
    ):
        self.station = station
        self.inputs = inputs          # [(材料名, 必要数), ...]
        self.output = output          # 成果物のテンプレート Entity
        self.output_name = output_name

    @property
    def input_text(self) -> str:
        return " + ".join(f"{n}×{c}" for n, c in self.inputs)


# 簡単な合成チェーン：スライムのかけら → 木の実 → 携帯食料 / 回復薬
RECIPES: List[Recipe] = [
    Recipe(Station.ALCHEMY, [("スライムのかけら", 3)], ef.healing_potion, "回復薬"),
    Recipe(Station.FOOD, [("スライムのかけら", 2)], ef.nuts, "木の実"),
    Recipe(Station.COOKING, [("木の実", 2)], ef.preserved_food, "携帯食料"),
]


def recipes_for(station: Station) -> List[Recipe]:
    return [r for r in RECIPES if r.station == station]


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
    # 材料を消費
    for name, count in recipe.inputs:
        removed = 0
        for it in list(inv.items):
            if it.name == name and removed < count:
                inv.items.remove(it)
                removed += 1
    # 成果物を追加
    inv.items.append(recipe.output.spawn(0, 0))
    engine.message_log.add_message(f"{recipe.output_name} を作った！", colors.ITEM)
