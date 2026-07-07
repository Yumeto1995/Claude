"""食料生産＝栽培（拠点の畑）。

拠点の畑に種を植え、ダンジョンの階を潜るうちに育ち、戻って収穫する。
畑は自由配置の農場オブジェクト（kind="farm"）。content=None なら空き、
dict（{"name","template","steps_left","kind","seed","regrow"}）なら栽培中。

野菜（veg）：収穫すると種が必ず1つ、稀に2〜3つ採れ、畑は空く（要・植え替え）。
果物（fruit）：収穫しても株が残り、成長が1段階戻るだけ＝植え替えずに再収穫できる。
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, List

import colors
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

# 種名 → 栽培情報。crop=育つ食材 / steps=収穫までの歩数 / kind="veg"|"fruit" /
# seed=収穫時に返る種テンプレート（野菜のみ。果物は株が残るので省略）。
SEEDS = {
    "リンゴの種": {"crop": ef.nuts,     "steps": 50, "kind": "fruit"},
    "果実の種":   {"crop": ef.fruit,    "steps": 55, "kind": "fruit"},
    "薬草の種":   {"crop": ef.herb,     "steps": 50, "kind": "veg", "seed": ef.herb_seed},
    "キノコの種": {"crop": ef.mushroom, "steps": 70, "kind": "veg", "seed": ef.mushroom_seed},
    "イモの種":   {"crop": ef.potato,   "steps": 60, "kind": "veg", "seed": ef.potato_seed},
}

# 追加食材（extra_foods.py）の栽培も取り込む。果物=株が残り再収穫／野菜・穀物=収穫で種。
import extra_foods as _xf
for _name, _d in _xf.FOODS.items():
    if not _d.get("plant"):
        continue
    _kind = "fruit" if _d["plant"] == "fruit" else "veg"
    _entry = {"crop": ef.EXTRA_FOODS[_name], "steps": _d["steps"], "kind": _kind}
    if _kind == "veg":
        _entry["seed"] = ef.EXTRA_SEEDS[_name]
    SEEDS[_name + "の種"] = _entry


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
    info = SEEDS[seed_name]
    output, steps = info["crop"], info["steps"]
    sk = getattr(engine.player, "skills", None)   # スキル『農業』で成長が速く
    if sk is not None:
        steps = max(1, int(steps * sk.growth_factor("farming")))
    obj["content"] = {
        "name": output.name, "template": output, "steps_left": steps,
        "kind": info["kind"], "seed": info.get("seed"),
        "regrow": max(1, steps // 2),   # 果物が再び実るまでの歩数（成長1段階分）
    }
    engine.message_log.add_message(
        f"{seed_name} を植えた（{steps}歩で育つ）。", colors.ITEM
    )


def harvest_obj(engine: "Engine", obj) -> None:
    """育った作物を収穫する。野菜は種が採れて畑は空き、果物は株が残り再収穫できる。"""
    import economy
    c = obj["content"]
    if c is None or c["steps_left"] > 0:
        return
    inv = engine.player.inventory.items
    item = c["template"].spawn(0, 0)
    sk = getattr(engine.player, "skills", None)
    rank = sk.rank("farming") if sk is not None else 0
    item.quality = economy.roll_quality(rank, tended=c.get("tended", False))
    inv.append(item)
    engine.record_collection(item.name)
    engine.message_log.add_message(
        f"{c['name']}{economy.quality_suffix(item)} を収穫した。", colors.ITEM)

    if c.get("kind") == "fruit":
        # 果物：株はそのまま。成長が1段階戻り、regrow 歩でまた実る（植え替え不要）
        c["steps_left"] = c["regrow"]
        engine.message_log.add_message(
            f"{c['name']}の株は残った（あと{c['regrow']}歩でまた実る）。", colors.ITEM)
        return

    # 野菜：種が必ず1つ、稀に2〜3つ採れる（農業スキルで少し増えやすい）
    seed = c.get("seed")
    if seed is not None:
        n = 1
        bonus = 0.05 * rank
        if random.random() < 0.25 + bonus:
            n += 1
        if random.random() < 0.08 + bonus:
            n += 1
        for _ in range(n):
            inv.append(seed.spawn(0, 0))
        engine.message_log.add_message(
            f"{seed.name} を {n} つ採れた。", colors.ITEM)
    obj["content"] = None


def plot_label(obj) -> str:
    c = obj["content"]
    if c is None:
        return "畑: 空き"
    if c["steps_left"] <= 0:
        return f"畑: {c['name']} 収穫できる！"
    return f"畑: {c['name']}（あと{c['steps_left']}歩）"
