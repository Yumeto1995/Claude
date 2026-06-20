"""牧場（畜産）。牧柵に動物を入れ、歩くと産物が育ち、繰り返し収穫できる。

牧柵は自由配置の農場オブジェクト（kind="pen"）として扱う。
"""
from __future__ import annotations

import entity_factories as ef
import husbandry

WHERE = "牧柵"

# 動物名 → (産物テンプレート, 産出までの歩数)
ANIMALS = {
    "ニワトリ": (ef.egg, 60),
    "ウシ": (ef.milk, 100),
}


def animal_names_in(items):
    return husbandry.names_in(items, ANIMALS)


def place(engine, obj, animal_name):
    sk = getattr(engine.player, "skills", None)   # スキル『酪農』で産出が速く
    speed = sk.growth_factor("ranch") if sk is not None else 1.0
    husbandry.place_obj(engine, obj, animal_name, ANIMALS, WHERE, speed)


def collect(engine, obj):
    husbandry.collect_obj(engine, obj)


def label(obj):
    return husbandry.obj_label(obj, WHERE)
