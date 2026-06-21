"""店（買い物）。代金は『お金＝経験値』で支払う。

買うと所持金（=総経験値）が減り、足りない分はレベルダウンして捻出する
（components/level.py の spend_xp）。所持金より高い品は買えない。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import colors
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
    ],
    "weapon": [
        (ef.dagger, 40),
        (ef.sword, 150),
        (ef.leather_armor, 50),
        (ef.chain_mail, 180),
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
    ],
}

TITLES = {"item": "道具屋", "weapon": "武器・防具屋", "food": "食料品店"}


def title(kind: str) -> str:
    return f"{TITLES.get(kind, '店')}（お金＝経験値）"


def info(engine: "Engine", kind: str) -> List[str]:
    return [f"所持金（経験値）：{engine.player.level.wealth()}",
            "↑↓ 選ぶ　Enter 購入　ESC やめる"]


def _stat_text(template) -> str:
    eq = template.equippable
    if eq is None:
        return ""
    parts = []
    if eq.power_bonus:
        parts.append(f"攻+{eq.power_bonus}")
    if eq.defense_bonus:
        parts.append(f"防+{eq.defense_bonus}")
    return "  " + " ".join(parts) if parts else ""


def options(engine: "Engine", kind: str) -> List[Dict[str, Any]]:
    """店の品をメニュー項目に。買えない（高い・満杯）なら enabled=False。"""
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
