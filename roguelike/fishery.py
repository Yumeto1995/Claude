"""漁業。釣り（エサを消費して魚を釣る）と、養殖いけす（魚を繰り返し産出）。

いけすは自由配置の農場オブジェクト（kind="tank"）として扱う。空のいけすでは
釣り（エサで魚を得る）か、魚を入れて養殖を始められる。
"""
from __future__ import annotations

import random

import colors
import entity_factories as ef
import husbandry

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
    # スキル『漁業』：ハズレ(ゴミ)の重みを減らし、良い魚が出やすくなる
    sk = getattr(engine.player, "skills", None)
    rank = sk.rank("fishery") if sk is not None else 0
    weights = []
    for tmpl, _name, w in FISH_POOL:
        weights.append(max(1, w - rank * 6) if tmpl is None else w + rank * 3)
    template, name, _ = random.choices(FISH_POOL, weights=weights)[0]
    if template is None:
        engine.message_log.add_message("ゴミが釣れた…", colors.NO_EFFECT)
        return
    import economy
    caught = template.spawn(0, 0)
    caught.quality = economy.roll_quality(rank)
    inv.append(caught)
    engine.record_collection(name)
    engine.message_log.add_message(
        f"{name}{economy.quality_suffix(caught)} を釣り上げた！", colors.LEVEL_UP)


# --- 養殖いけす ---

def breed_names_in(items):
    return husbandry.names_in(items, BREED)


def place(engine, obj, fish_name):
    sk = getattr(engine.player, "skills", None)   # スキル『漁業』で養殖が速く
    speed = sk.growth_factor("fishery") if sk is not None else 1.0
    husbandry.place_obj(engine, obj, fish_name, BREED, WHERE, speed)


def collect(engine, obj):
    husbandry.collect_obj(engine, obj)


def label(obj):
    return husbandry.obj_label(obj, WHERE)
