"""店（買い物）。代金は『お金＝経験値』で支払う。

買うと所持金（=総経験値）が減り、足りない分はレベルダウンして捻出する
（components/level.py の spend_xp）。所持金より高い品は買えない。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import colors
import economy
import entity_factories as ef

if TYPE_CHECKING:
    from engine import Engine

# 店種 → [(テンプレート, 価格(=経験値)), ...]
WARES = {
    "item": [
        (ef.healing_potion, 30),
        (ef.lightning_scroll, 70),
        (ef.confusion_scroll, 55),
        (ef.sprinkler, 80),       # 畑を自動水やりする設置物（建設モードで設置）
        # 符呪のお札（祭壇で装備にエンチャント）。武器用／防具用に分かれる
        (ef.ofuda_sharp, 60),     # 武器：鋭利（攻撃力+1/Lv）
        (ef.ofuda_fire, 90),      # 武器：火炎（追加ダメージ）
        (ef.ofuda_knock, 70),     # 武器：撃退（ノックバック）
        (ef.ofuda_loot, 90),      # 武器：略奪（撃破XP増）
        (ef.ofuda_light, 70),     # 武器：軽量（消費スタミナ減）
        (ef.ofuda_crit, 90),      # 武器：会心（会心率+8%/Lv）
        (ef.ofuda_protect, 60),   # 防具：防護（防御力+1/Lv）
        (ef.ofuda_thorns, 90),    # 防具：棘（反射）
    ],
    "weapon": [
        (ef.dagger, 40),
        (ef.spear, 90),
        (ef.katana, 200),
        (ef.sword, 150),
        (ef.battle_axe, 170),
        (ef.crossbow, 160),
        (ef.leather_armor, 50),
        (ef.wooden_shield, 70),
        (ef.chain_mail, 180),
        (ef.plate_armor, 260),
    ],
    "food": [
        # 全栄養素を補給できる品揃え（栄養は非表示＝食べて覚える）
        (ef.nuts, 12),          # 炭水化物・脂質
        (ef.preserved_food, 35),  # 炭水化物・たんぱく質（日持ち）
        (ef.herb, 10),          # ビタミンC・A
        (ef.meat, 22),          # たんぱく質・鉄分
        (ef.milk, 16),          # カルシウム・ビタミンA
        (ef.egg, 14),           # バランス（カルシウム等）
        (ef.potato, 10),        # 炭水化物・日持ち
        (ef.cheese, 20),        # カルシウム・日持ち
        (ef.honey, 18),         # 炭水化物・超日持ち
        # 種（拠点の畑に植えて育てる）。育てて出荷すれば利益になる（種<作物の売値）
        (ef.nut_seed, 4),
        (ef.herb_seed, 3),
        (ef.mushroom_seed, 5),
    ],
}

TITLES = {"item": "道具屋", "weapon": "武器・防具屋", "food": "食料品店"}


def title(kind: str) -> str:
    return f"{TITLES.get(kind, '店')}（お金＝経験値）"


def info(engine: "Engine", kind: str) -> List[str]:
    sell = getattr(engine, "shop_mode", "buy") == "sell"
    mode = "【売る】" if sell else "【買う】"
    return [f"{mode}　所持金（経験値）：{engine.player.level.wealth()}",
            f"↑↓ 選ぶ　Enter {'売却' if sell else '購入'}　Tab 買う↔売る　ESC やめる"]


def _stat_text(template) -> str:
    from components.equippable import EquipmentType
    eq = template.equippable
    if eq is None:
        return ""
    parts = []
    if eq.power_bonus:
        parts.append(f"攻+{eq.power_bonus}")
    if eq.defense_bonus:
        parts.append(f"防+{eq.defense_bonus}")
    if eq.max_range:
        parts.append(f"射程{eq.max_range}")   # 遠距離武器の射程
    if getattr(eq, "crit_chance", 0):
        parts.append(f"会心{int(round(eq.crit_chance * 100))}%")
    if eq.stamina_cost:
        # 武器/弓＝1撃(1射)の消費スタミナ、防具＝装備中に攻撃が重くなる分(加算)
        if eq.equipment_type == EquipmentType.ARMOR:
            parts.append(f"重さ+{eq.stamina_cost}")
        else:
            parts.append(f"消費{eq.stamina_cost}")
    return "  " + " ".join(parts) if parts else ""


def options(engine: "Engine", kind: str) -> List[Dict[str, Any]]:
    """店の品をメニュー項目に。買う／売るモードで内容が変わる。"""
    if getattr(engine, "shop_mode", "buy") == "sell":
        return _sell_options(engine)
    wealth = engine.player.level.wealth()
    inv = engine.player.inventory
    full = len(inv.items) >= inv.capacity
    opts = []
    for i, (tmpl, price) in enumerate(WARES.get(kind, [])):
        opts.append({
            "text": f"{tmpl.name}{_stat_text(tmpl)}　{price}",
            "enabled": (price <= wealth) and not full,
            "index": i,
        })
    return opts


def buy(engine: "Engine", kind: str, index: int) -> None:
    wares = WARES.get(kind, [])
    if not (0 <= index < len(wares)):
        return
    tmpl, price = wares[index]
    player = engine.player
    inv = player.inventory
    if len(inv.items) >= inv.capacity:
        engine.message_log.add_message("持ち物がいっぱいで買えない。", colors.NO_EFFECT)
        return
    lv = player.level
    before = lv.current_level
    if not lv.spend_xp(price, player.fighter):
        engine.message_log.add_message("お金（経験値）が足りない。", colors.NO_EFFECT)
        return
    inv.items.append(tmpl.spawn(0, 0))
    engine.message_log.add_message(f"{tmpl.name} を購入した（-{price}）。", colors.ITEM)
    if lv.current_level < before:
        engine.message_log.add_message(
            f"経験を使い、Lv.{lv.current_level} に下がった。", colors.NO_EFFECT
        )


def _sellable(engine: "Engine") -> List["Entity"]:
    """売却できる持ち物（装備中・大切なものは除く）。"""
    equip = engine.player.equipment
    return [it for it in engine.player.inventory.items
            if economy.is_sellable(it) and not equip.item_is_equipped(it)]


def _sell_options(engine: "Engine") -> List[Dict[str, Any]]:
    opts = []
    for i, it in enumerate(_sellable(engine)):
        opts.append({"text": f"{it.name}{economy.quality_suffix(it)}　{economy.sell_value(it)}",
                     "enabled": True, "index": i})
    if not opts:
        opts.append({"text": "（売れる物がない）", "enabled": False, "index": -1})
    return opts


def sell(engine: "Engine", index: int) -> None:
    """売却モードで index の持ち物を売る（代金＝経験値を得る）。"""
    items = _sellable(engine)
    if not (0 <= index < len(items)):
        return
    it = items[index]
    price = economy.sell_value(it)
    engine.player.inventory.items.remove(it)
    engine.player.level.add_xp(price)
    engine.message_log.add_message(f"{it.name} を売った（+{price}）。", colors.ITEM)
    n = len(_sellable(engine))
    if n and engine.shop_cursor >= n:
        engine.shop_cursor = n - 1
