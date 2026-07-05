"""符呪（エンチャント）：拠点の祭壇で、お札を使って武器・防具を強化する。

Minecraft のエンチャント方式を参考にした設計：
  * 1つの装備に **複数の異なる符呪** を付けられる（例：鋭利III・火炎I・撃退I）。
  * 各符呪には **レベル（I〜）** があり、同じお札を重ねると上がる（最大Lvあり）。
  * 効果は受動（鋭利=攻撃力/防護=防御力/軽量=消費スタミナ）と、戦闘中の特殊効果
    （火炎=追加ダメージ / 撃退=ノックバック / 略奪=撃破経験値増 / 棘=反射）に分かれる。
お札は符呪ごとに分かれ、武器用/防具用の別がある。装備名に〈鋭利III・火炎I〉のように表示。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

import colors
from components.equippable import EquipmentType

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

ROMAN = ["", "I", "II", "III", "IV", "V"]

# 符呪ID → 定義。cat=weapon/armor、max=最大Lv、power/defense/stamina=Lvあたりの受動ボーナス、
# それ以外の効果（fire/knock/loot/thorns）は戦闘フックで参照する。
ENCHANTS: Dict[str, dict] = {
    "sharp":   {"name": "鋭利", "cat": "weapon", "max": 5, "power": 1, "desc": "攻撃力+1/Lv"},
    "fire":    {"name": "火炎", "cat": "weapon", "max": 3, "desc": "命中時に追加ダメージ +3/Lv"},
    "knock":   {"name": "撃退", "cat": "weapon", "max": 2, "desc": "敵をノックバックする"},
    "loot":    {"name": "略奪", "cat": "weapon", "max": 3, "desc": "撃破の経験値 +20%/Lv"},
    "crit":    {"name": "会心", "cat": "weapon", "max": 3, "desc": "会心率 +8%/Lv"},
    "protect": {"name": "防護", "cat": "armor",  "max": 4, "defense": 1, "desc": "防御力+1/Lv"},
    "thorns":  {"name": "棘",   "cat": "armor",  "max": 3, "desc": "被弾時に反射 15%/Lv"},
    "light":   {"name": "軽量", "cat": "weapon", "max": 3, "stamina": -3, "desc": "攻撃の消費スタミナ -3/Lv"},
}

# お札名 → 符呪ID
OFUDA: Dict[str, str] = {
    "鋭利の札": "sharp", "火炎の札": "fire", "撃退の札": "knock", "略奪の札": "loot",
    "防護の札": "protect", "棘の札": "thorns", "軽量の札": "light", "会心の札": "crit",
}


def _cat(item) -> str:
    eq = getattr(item, "equippable", None)
    if eq is None:
        return ""
    return "armor" if eq.equipment_type == EquipmentType.ARMOR else "weapon"


def enchants_of(item) -> Dict[str, int]:
    return getattr(item, "enchants", {})


def level_of(item, eid: str) -> int:
    return enchants_of(item).get(eid, 0) if item is not None else 0


def enchantable_items(items) -> List["Entity"]:
    return [it for it in items if getattr(it, "equippable", None) is not None]


def ofuda_names_in(items) -> List[str]:
    seen: List[str] = []
    for it in items:
        if it.name in OFUDA and it.name not in seen:
            seen.append(it.name)
    return seen


def ofuda_id(name: str) -> str:
    return OFUDA.get(name, "")


def ofuda_desc(name: str) -> str:
    e = ENCHANTS.get(OFUDA.get(name, ""))
    return e["desc"] if e else ""


def compatible_ofuda(items, target) -> List[str]:
    cat = _cat(target)
    return [n for n in ofuda_names_in(items) if ENCHANTS[OFUDA[n]]["cat"] == cat]


def can_apply(target, name: str) -> Tuple[bool, str]:
    """(可否, 理由)。"""
    eid = OFUDA.get(name)
    if eid is None or getattr(target, "equippable", None) is None:
        return (False, "符呪できない")
    e = ENCHANTS[eid]
    if e["cat"] != _cat(target):
        return (False, "防具専用" if e["cat"] == "armor" else "武器専用")
    if level_of(target, eid) >= e["max"]:
        return (False, "最大Lv")
    return (True, "")


def base_name(item) -> str:
    if not hasattr(item, "base_name"):
        item.base_name = item.name
    return item.base_name


def summary(item) -> str:
    ench = enchants_of(item)
    return "・".join(f"{ENCHANTS[i]['name']}{ROMAN[lv]}" for i, lv in ench.items() if lv)


def _rename(item) -> None:
    s = summary(item)
    item.name = f"{base_name(item)}〈{s}〉" if s else base_name(item)


def _recompute(item) -> None:
    """符呪Lvから装備の受動ボーナス（攻/防/消費スタミナ）を再計算する。"""
    eq = item.equippable
    if not hasattr(item, "_base_power"):
        item._base_power = eq.power_bonus
        item._base_defense = eq.defense_bonus
        item._base_stamina = eq.stamina_cost
    ench = enchants_of(item)
    eq.power_bonus = item._base_power + sum(ENCHANTS[i].get("power", 0) * lv for i, lv in ench.items())
    eq.defense_bonus = item._base_defense + sum(ENCHANTS[i].get("defense", 0) * lv for i, lv in ench.items())
    if item._base_stamina is not None:
        eq.stamina_cost = max(2, item._base_stamina
                              + sum(ENCHANTS[i].get("stamina", 0) * lv for i, lv in ench.items()))


def apply(engine: "Engine", target: "Entity", name: str) -> None:
    ok, reason = can_apply(target, name)
    if not ok:
        engine.message_log.add_message(f"符呪できない（{reason}）。", colors.NO_EFFECT)
        return
    inv = engine.player.inventory.items
    ofuda = next((it for it in inv if it.name == name), None)
    if ofuda is None:
        return
    inv.remove(ofuda)
    eid = OFUDA[name]
    if not hasattr(target, "enchants"):
        target.enchants = {}
    target.enchants[eid] = target.enchants.get(eid, 0) + 1
    _recompute(target)
    _rename(target)
    e = ENCHANTS[eid]
    engine.message_log.add_message(
        f"{base_name(target)} に『{e['name']} {ROMAN[target.enchants[eid]]}』を符呪した！",
        colors.LEVEL_UP)


def preset(item: "Entity", ench: Dict[str, int]) -> "Entity":
    """テンプレートにあらかじめ符呪を付ける（エンチャント済みのレア装備を作る用）。

    entity_factories でレア装備を定義した直後に呼ぶ。spawn は deepcopy するので、
    テンプレートに付けた符呪はそのまま各インスタンスに複製される。"""
    item.enchants = dict(ench)
    _recompute(item)
    _rename(item)
    return item


def stat_text(item) -> str:
    """メニュー表示用：符呪一覧＋現在の攻/防。"""
    eq = getattr(item, "equippable", None)
    if eq is None:
        return ""
    bits = []
    s = summary(item)
    if s:
        bits.append(s)
    if eq.power_bonus:
        bits.append(f"攻+{eq.power_bonus}")
    if eq.defense_bonus:
        bits.append(f"防+{eq.defense_bonus}")
    return "  ".join(bits) if bits else "符呪なし"


# ---------- 戦闘フック（プレイヤーの装備を参照）----------
def _weapon(entity):
    eqp = getattr(entity, "equipment", None)
    return eqp.weapon if eqp is not None else None


def _armor(entity):
    eqp = getattr(entity, "equipment", None)
    return eqp.armor if eqp is not None else None


def _ranged(entity):
    eqp = getattr(entity, "equipment", None)
    return eqp.ranged if eqp is not None else None


def weapon_fire_bonus(entity) -> int:
    """火炎：命中時の追加ダメージ。"""
    return 3 * level_of(_weapon(entity), "fire")


def weapon_crit_frac(entity, ranged: bool = False) -> float:
    """会心：符呪『会心』による会心率の上乗せ（近接は装備中の武器、射撃は弓/クロスボウ）。"""
    return 0.08 * level_of(_ranged(entity) if ranged else _weapon(entity), "crit")


def looting_mult(entity) -> float:
    """略奪：撃破経験値の倍率。"""
    return 1.0 + 0.20 * level_of(_weapon(entity), "loot")


def armor_thorns_frac(entity) -> float:
    """棘：被弾ダメージを反射する割合。"""
    return 0.15 * level_of(_armor(entity), "thorns")


def apply_knockback(engine: "Engine", attacker, target, dx: int, dy: int) -> None:
    """撃退：target を攻撃方向へ1マス押す（1×1・空きマスのみ）。"""
    if level_of(_weapon(attacker), "knock") <= 0:
        return
    if target.fighter is None or target.fighter.hp <= 0 or getattr(target, "size", 1) != 1:
        return
    gm = engine.game_map
    nx, ny = target.x + dx, target.y + dy
    if (gm.in_bounds(nx, ny) and gm.tiles["walkable"][nx, ny]
            and gm.get_blocking_entity_at(nx, ny) is None):
        target.x, target.y = nx, ny
        engine.pending_moves.append((target, dx, dy))
