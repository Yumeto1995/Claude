"""牧場の牧柵・漁業の養殖いけすで共通の『繰り返し産出』ロジック（1オブジェクト単位）。

自由配置の農場オブジェクト obj は {"kind": ..., "content": None or dict}。
content（産出中）= {"src": 動物/魚名, "product_name": 産物名, "product": 産物テンプレ,
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


def place_obj(engine, obj, name, table, where_label, speed: float = 1.0) -> None:
    """obj に動物/魚を入れて産出を開始する。"""
    inv = engine.player.inventory.items
    for it in inv:
        if it.name == name:
            inv.remove(it)
            break
    product, interval = table[name]
    interval = max(1, int(interval * speed))   # スキル『酪農/漁業』で産出が速く
    obj["content"] = {
        "src": name, "product_name": product.name, "product": product,
        "steps_left": interval, "interval": interval,
    }
    engine.message_log.add_message(f"{name} を{where_label}に入れた。", colors.ITEM)


def collect_obj(engine, obj) -> None:
    """産出が完了していれば収穫し、interval にリセット（繰り返し産出）。"""
    c = obj["content"]
    if c is None or c["steps_left"] > 0:
        return
    engine.player.inventory.items.append(c["product"].spawn(0, 0))
    engine.message_log.add_message(f"{c['product_name']} を手に入れた。", colors.ITEM)
    c["steps_left"] = c["interval"]


def obj_label(obj, where_label) -> str:
    c = obj["content"]
    if c is None:
        return f"{where_label}: 空き"
    if c["steps_left"] <= 0:
        return f"{where_label}: {c['product_name']} 収穫できる！"
    return f"{where_label}: {c['src']}（あと{c['steps_left']}歩）"
