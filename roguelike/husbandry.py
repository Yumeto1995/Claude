"""牧場の牧柵・漁業の養殖いけすで共通の『繰り返し産出スロット』ロジック。

スロット = None（空き）か dict:
  {"src": 動物/魚名, "product_name": 産物名, "product": 産物テンプレ,
   "steps_left": 残り歩数, "interval": 産出間隔}
歩くごとに steps_left が減り、0で収穫可。収穫すると steps_left を interval に戻す（繰り返し）。
"""
from __future__ import annotations

from typing import List

import colors


def names_in(items, table) -> List[str]:
    """持ち物にある、table に載っている素材（動物/魚）の名前。"""
    seen: List[str] = []
    for it in items:
        if it.name in table and it.name not in seen:
            seen.append(it.name)
    return seen


def place(engine, slots, idx, name, table, where_label) -> None:
    inv = engine.player.inventory.items
    for it in inv:
        if it.name == name:
            inv.remove(it)
            break
    product, interval = table[name]
    slots[idx] = {
        "src": name, "product_name": product.name, "product": product,
        "steps_left": interval, "interval": interval,
    }
    engine.message_log.add_message(f"{name} を{where_label}{idx + 1}に入れた。", colors.ITEM)


def collect(engine, slots, idx) -> None:
    s = slots[idx]
    if s is None or s["steps_left"] > 0:
        return
    engine.player.inventory.items.append(s["product"].spawn(0, 0))
    engine.message_log.add_message(f"{s['product_name']} を手に入れた。", colors.ITEM)
    s["steps_left"] = s["interval"]  # 繰り返し産出


def step_grow(slots) -> None:
    for s in slots:
        if s is not None and s["steps_left"] > 0:
            s["steps_left"] -= 1


def slot_label(slots, i, where_label) -> str:
    s = slots[i]
    if s is None:
        return f"{where_label}{i + 1}: 空き"
    if s["steps_left"] <= 0:
        return f"{where_label}{i + 1}: {s['product_name']} 収穫できる！"
    return f"{where_label}{i + 1}: {s['src']}（あと{s['steps_left']}歩）"
