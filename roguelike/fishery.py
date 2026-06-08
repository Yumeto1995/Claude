"""漁業。釣り（エサを消費して魚を釣る）と、養殖いけす（魚を繰り返し産出）。"""
from __future__ import annotations

import random

import colors
import entity_factories as ef
import husbandry

TANKS = 3
WHERE = "いけす"

# 養殖：魚を入れると魚が繰り返し増える
BREED = {
    "魚": (ef.fish, 80),
}

# 釣りの結果（テンプレート, 名前, 重み）。None はハズレ。
FISH_POOL = [
    (ef.fish, "魚", 48),
    (ef.big_fish, "大魚", 12),
    (ef.puffer, "フグ", 18),
    (None, "ゴミ", 22),
]


def has_bait(items):
    return any(it.name == "エサ" for it in items)


def fish(engine):
    inv = engine.player.inventory.items
    bait = next((it for it in inv if it.name == "エサ"), None)
    if bait is None:
        engine.message_log.add_message("エサがない。錬金で作れる。", colors.NO_EFFECT)
        return
    inv.remove(bait)
    pool = random.choices(FISH_POOL, weights=[w for *_, w in FISH_POOL])[0]
    template, name, _ = pool
    if template is None:
        engine.message_log.add_message("ゴミが釣れた…", colors.NO_EFFECT)
        return
    inv.append(template.spawn(0, 0))
    engine.message_log.add_message(f"{name} を釣り上げた！", colors.LEVEL_UP)


# --- 養殖いけす ---

def breed_names_in(items):
    return husbandry.names_in(items, BREED)


def place(engine, tank_index, fish_name):
    husbandry.place(engine, engine.fishery_tanks, tank_index, fish_name, BREED, WHERE)


def collect(engine, tank_index):
    husbandry.collect(engine, engine.fishery_tanks, tank_index)


def step_grow(engine):
    husbandry.step_grow(getattr(engine, "fishery_tanks", []))


def label(engine, i):
    return husbandry.slot_label(engine.fishery_tanks, i, WHERE)
