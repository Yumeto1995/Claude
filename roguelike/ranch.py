"""牧場（畜産）。牧柵に動物を入れ、歩くと産物が育ち、繰り返し収穫できる。"""
from __future__ import annotations

import entity_factories as ef
import husbandry

PENS = 3
WHERE = "牧柵"

# 動物名 → (産物テンプレート, 産出までの歩数)
ANIMALS = {
    "ニワトリ": (ef.egg, 60),
    "ウシ": (ef.milk, 100),
}


def animal_names_in(items):
    return husbandry.names_in(items, ANIMALS)


def place(engine, pen_index, animal_name):
    husbandry.place(engine, engine.ranch_pens, pen_index, animal_name, ANIMALS, WHERE)


def collect(engine, pen_index):
    husbandry.collect(engine, engine.ranch_pens, pen_index)


def step_grow(engine):
    husbandry.step_grow(getattr(engine, "ranch_pens", []))


def label(engine, i):
    return husbandry.slot_label(engine.ranch_pens, i, WHERE)
