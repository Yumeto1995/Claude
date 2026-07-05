"""拠点の設備メニュー制御（設備の上で Enter したとき開く）。

engine.camp_menu（文字列）で開いているメニューを表す：
  cook/cook_method（料理）/ alchemy（錬金）/ storage（収納）/ health（体調）/
  farm_plant（畑に植える）/ pen_place（牧柵に入れる）/ tank_place（いけす）
None のときはメニューを閉じてテント内を歩いている状態。
自由配置の畑・牧柵・いけすは engine.camp_objects[engine.camp_active_pos] を操作する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import colors
import cooking
import crafting
import economy
import enchant
import farming
import fishery
import nutrition
import ranch

if TYPE_CHECKING:
    from engine import Engine

_BACK: Dict[str, Any] = {"text": "とじる", "enabled": True, "kind": "back"}

TITLES = {
    "health": "体調を調べる（栄養状態）",
    "cook": "料理：鍋に食材を入れる",
    "cook_method": "料理：調理法を選ぶ",
    "alchemy": "アイテム錬金",
    "storage": "収納",
    "farm_plant": "畑：種を植える",
    "pen_place": "牧柵：動物を入れる",
    "tank_place": "いけす：釣り／養殖",
    "shipping": "出荷箱：産物を売る",
    "upgrade": "設備のアップグレード",
    "collection": "図鑑（コレクション）",
    "enchant": "符呪：強化する装備を選ぶ",
    "enchant_ofuda": "符呪：使うお札を選ぶ",
}


def _active(engine: "Engine"):
    """メニューで操作中の農場設備オブジェクト（無ければ None）。"""
    return engine.camp_objects.get(engine.camp_active_pos)


def title(engine: "Engine") -> str:
    return TITLES.get(engine.camp_menu, "")


def options(engine: "Engine") -> List[Dict[str, Any]]:
    menu = engine.camp_menu
    items = engine.player.inventory.items

    if menu == "health":
        nut = engine.player.nutrition
        opts = [
            {"text": f"{nutrition.NUTRIENTS[k]}：{nut.status_label(k)}",
             "enabled": False, "kind": "noop"}
            for k in nutrition.KEYS
        ]
        opts.append(_BACK)
        return opts

    if menu == "alchemy":
        opts = [
            {"text": f"{r.output_name}  ←  {r.input_text}",
             "enabled": crafting.can_craft(items, r), "kind": "alchemy", "data": r}
            for r in crafting.ALCHEMY_RECIPES
        ]
        opts.append(_BACK)
        return opts

    if menu == "cook":
        opts = []
        for name in cooking.ingredient_names_in(items):
            rest = cooking.available(items, engine.cook_pot, name)
            opts.append({"text": f"{name} を入れる（残り{rest}）",
                         "enabled": rest > 0, "kind": "pot_add", "data": name})
        opts.append({"text": f"調理する（鍋に{len(engine.cook_pot)}品）",
                     "enabled": len(engine.cook_pot) > 0, "kind": "goto", "data": "cook_method"})
        opts.append({"text": "鍋を空にする",
                     "enabled": len(engine.cook_pot) > 0, "kind": "pot_clear"})
        opts.append(_BACK)
        return opts

    if menu == "cook_method":
        opts = [{"text": m, "enabled": True, "kind": "cook_do", "data": m}
                for m in cooking.METHOD_NAMES]
        opts.append(_BACK)
        return opts

    if menu == "storage":
        equip = engine.player.equipment
        opts = []
        for it in list(items):
            opts.append({"text": f"預ける: {it.name}",
                         "enabled": not equip.item_is_equipped(it),
                         "kind": "deposit", "data": it})
        space = not engine.player.inventory.is_full
        for it in list(engine.storage):
            opts.append({"text": f"取り出す: {it.name}", "enabled": space,
                         "kind": "withdraw", "data": it})
        opts.append(_BACK)
        return opts

    if menu == "farm_plant":
        opts = [{"text": f"{name} を植える", "enabled": True, "kind": "plant", "data": name}
                for name in farming.seed_names_in(items)]
        opts.append(_BACK)
        return opts

    if menu == "pen_place":
        opts = [{"text": f"{name} を入れる", "enabled": True, "kind": "pen_do", "data": name}
                for name in ranch.animal_names_in(items)]
        opts.append(_BACK)
        return opts

    if menu == "tank_place":
        bait = sum(1 for it in items if it.name == "エサ")
        opts = [{"text": f"釣る（エサ {bait}）", "enabled": bait > 0, "kind": "fish"}]
        opts += [{"text": f"{name} を養殖する", "enabled": True, "kind": "tank_do", "data": name}
                 for name in fishery.breed_names_in(items)]
        opts.append(_BACK)
        return opts

    if menu == "shipping":
        equip = engine.player.equipment
        opts = []
        for it in list(items):
            if economy.is_sellable(it) and not equip.item_is_equipped(it):
                opts.append({"text": f"出荷: {it.name}{economy.quality_suffix(it)}（{economy.sell_value(it)}）",
                             "enabled": True, "kind": "ship", "data": it})
        space = not engine.player.inventory.is_full
        for it in list(engine.shipping_bin):
            opts.append({"text": f"戻す: {it.name}{economy.quality_suffix(it)}",
                         "enabled": space, "kind": "unship", "data": it})
        opts.append(_BACK)
        return opts

    if menu == "upgrade":
        wealth = engine.player.level.wealth()
        opts = []
        for fac, (flabel, descs, costs) in economy.UPGRADES.items():
            lv = engine.upgrades.get(fac, 0)
            if lv >= economy.MAX_UPGRADE:
                opts.append({"text": f"{flabel}：最大（{descs[-1]}）", "enabled": False, "kind": "noop"})
            else:
                cost = costs[lv]
                opts.append({"text": f"{flabel}：{descs[lv]}（{cost}）",
                             "enabled": wealth >= cost, "kind": "upgrade_do", "data": fac})
        opts.append(_BACK)
        return opts

    if menu == "collection":
        opts = []
        for cat, names in economy.COLLECTIBLES.items():
            got = sum(1 for n in names if n in engine.collected)
            opts.append({"text": f"― {cat}（{got}/{len(names)}）―", "enabled": False, "kind": "noop"})
            for n in names:
                mark = "✓" if n in engine.collected else "・"
                opts.append({"text": f"  {mark} {n}", "enabled": False, "kind": "noop"})
        opts.append(_BACK)
        return opts

    if menu == "enchant":
        opts = [{"text": f"{it.name}（{enchant.stat_text(it)}）を符呪",
                 "enabled": True, "kind": "enchant_pick", "data": it}
                for it in enchant.enchantable_items(items)]
        opts.append(_BACK)
        return opts

    if menu == "enchant_ofuda":
        target = engine.enchant_target
        opts = []
        if target is not None:
            for name in enchant.compatible_ofuda(items, target):
                ok, reason = enchant.can_apply(target, name)
                cnt = sum(1 for it in items if it.name == name)
                curlv = enchant.level_of(target, enchant.ofuda_id(name))
                extra = f"（{reason}）" if (not ok and reason) else (f"（現Lv{curlv}）" if curlv else "")
                opts.append({"text": f"『{name}』{enchant.ofuda_desc(name)}{extra} ×{cnt}",
                             "enabled": ok, "kind": "enchant_do", "data": name})
        opts.append(_BACK)
        return opts

    return [_BACK]


def info(engine: "Engine") -> List[str]:
    menu = engine.camp_menu
    if menu == "health":
        nut = engine.player.nutrition
        if nut.deficient:
            sk = engine.player.skills
            if getattr(sk, "self_diagnosis", False):
                syms = "・".join(nutrition.SYMPTOMS[k] for k in nutrition.KEYS if k in nut.deficient)
                return [f"自己診断: {syms}", "不足している栄養を含む食事で改善する。"]
            return ["どうも体調が優れない…", "最近の食事に偏りがないか見直してみよう。"]
        if nut.is_good:
            return ["栄養バランス良好＝好調！（攻+1 防+1 スタミナ回復↑）"]
        return ["大きな偏りはなし。バランスよく食べよう。"]
    if menu in ("cook", "cook_method"):
        return [f"鍋: {cooking.pot_summary(engine.cook_pot)}"]
    if menu == "storage":
        names = ", ".join(it.name for it in engine.storage) or "空"
        return [f"倉庫({len(engine.storage)}): {names}"]
    if menu == "farm_plant":
        return ["畑に植える種を選ぶ。階を潜るうちに育つ。"]
    if menu == "pen_place":
        return ["牧柵に動物を入れる。歩くと卵やミルクを繰り返し収穫できる。"]
    if menu == "tank_place":
        return ["いけすで釣る、または魚を入れて養殖する。フグは要調理。"]
    if menu == "shipping":
        total = sum(economy.sell_value(it) for it in engine.shipping_bin)
        return [f"出荷箱: {len(engine.shipping_bin)}品 / 売値 {total}（テントを出ると売れる）"]
    if menu == "upgrade":
        return [f"所持金（経験値）: {engine.player.level.wealth()}　※農産物を出荷して稼ごう"]
    if menu == "collection":
        got = sum(1 for n in economy.COLLECT_ALL if n in engine.collected)
        return [f"収集 {got}/{len(economy.COLLECT_ALL)}（全種そろえると報酬）"]
    if menu == "enchant":
        return ["武器・防具にお札を符呪して恒久強化する。お札は道具屋で買える。"]
    if menu == "enchant_ofuda":
        t = engine.enchant_target
        if t is not None:
            return [f"{enchant.base_name(t)}：{enchant.stat_text(t)}"]
        return ["先に装備を選んでください。"]
    return []


def move_cursor(engine: "Engine", delta: int) -> None:
    n = len(options(engine))
    engine.camp_cursor = (engine.camp_cursor + delta) % n


def select(engine: "Engine") -> None:
    opts = options(engine)
    if not opts:
        return
    cur = opts[min(engine.camp_cursor, len(opts) - 1)]
    if not cur.get("enabled", True):
        return
    kind = cur["kind"]
    inv = engine.player.inventory

    if kind == "back":
        back(engine)
    elif kind == "goto":
        engine.camp_menu = cur["data"]
        engine.camp_cursor = 0
    elif kind == "alchemy":
        crafting.try_craft(engine, cur["data"])
    elif kind == "pot_add":
        engine.cook_pot.append(cur["data"])
    elif kind == "pot_clear":
        engine.cook_pot = []
    elif kind == "cook_do":
        cooking.cook(engine, engine.cook_pot, cur["data"])
        engine.cook_pot = []
        engine.camp_menu = "cook"
        engine.camp_cursor = 0
    elif kind == "deposit":
        item = cur["data"]
        if item in inv.items:
            inv.items.remove(item)
            engine.storage.append(item)
    elif kind == "withdraw":
        item = cur["data"]
        if inv.can_accept(item) and item in engine.storage:
            engine.storage.remove(item)
            inv.items.append(item)
    elif kind == "plant":
        obj = _active(engine)
        if obj is not None:
            farming.plant_obj(engine, obj, cur["data"])
        engine.camp_menu = None
    elif kind == "pen_do":
        obj = _active(engine)
        if obj is not None:
            ranch.place(engine, obj, cur["data"])
        engine.camp_menu = None
    elif kind == "fish":
        fishery.fish(engine)
        engine.camp_menu = None
    elif kind == "tank_do":
        obj = _active(engine)
        if obj is not None:
            fishery.place(engine, obj, cur["data"])
        engine.camp_menu = None
    elif kind == "ship":
        item = cur["data"]
        if item in inv.items:
            inv.items.remove(item)
            engine.shipping_bin.append(item)
    elif kind == "unship":
        item = cur["data"]
        if item in engine.shipping_bin and inv.can_accept(item):
            engine.shipping_bin.remove(item)
            inv.items.append(item)
    elif kind == "upgrade_do":
        fac = cur["data"]
        flabel, descs, costs = economy.UPGRADES[fac]
        lv = engine.upgrades.get(fac, 0)
        if lv < economy.MAX_UPGRADE and engine.player.level.spend_xp(costs[lv], engine.player.fighter):
            engine.upgrades[fac] = lv + 1
            if fac == "storage":
                engine.apply_storage_upgrade()
            engine.message_log.add_message(f"{flabel}を強化した（{descs[lv]}）。", colors.LEVEL_UP)
    elif kind == "enchant_pick":
        engine.enchant_target = cur["data"]
        engine.camp_menu, engine.camp_cursor = "enchant_ofuda", 0
    elif kind == "enchant_do":
        if engine.enchant_target is not None:
            enchant.apply(engine, engine.enchant_target, cur["data"])
        engine.camp_cursor = 0


def back(engine: "Engine") -> None:
    if engine.camp_menu == "cook_method":
        engine.camp_menu = "cook"
    elif engine.camp_menu == "cook":
        engine.cook_pot = []
        engine.camp_menu = None
    elif engine.camp_menu == "enchant_ofuda":
        engine.camp_menu = "enchant"
    else:  # alchemy / storage / health / farm_plant / pen_place / tank_place / …
        engine.camp_menu = None
    engine.camp_cursor = 0
