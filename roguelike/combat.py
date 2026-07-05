"""戦闘の共通処理（ダメージ・撃破・経験値）。

近接攻撃（actions.MeleeAction）からも、巻物などのアイテム効果
（components.consumable）からも使えるよう、ここに集約する。
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

import colors
from components.level import HP_PER_LEVEL, POWER_PER_LEVEL

SEED_DROP_CHANCE = 0.08  # 敵撃破時に種をこぼす確率（栽培のタネを探索でも入手できる）


def _free_item_tile(engine: "Engine", x: int, y: int) -> tuple:
    """(x, y) から最も近い『アイテムの無い歩けるマス』を返す。

    ドロップ先に既にアイテムがあると重なって拾いにくいので、近い順に空きを探す。
    見つからなければ元の (x, y) を返す（最悪でも消えはしない）。"""
    import item_category
    gm = engine.game_map

    def occupied(tx: int, ty: int) -> bool:
        return any(item_category.is_item(e) and e.x == tx and e.y == ty
                   for e in gm.entities)

    def usable(tx: int, ty: int) -> bool:
        return gm.in_bounds(tx, ty) and gm.tiles["walkable"][tx, ty]

    if usable(x, y) and not occupied(x, y):
        return (x, y)
    # チェビシェフ距離の近いリングから順に探す＝最寄りの空きマス
    for r in range(1, 9):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                tx, ty = x + dx, y + dy
                if usable(tx, ty) and not occupied(tx, ty):
                    return (tx, ty)
    return (x, y)

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


def inflict_damage(
    engine: "Engine",
    target: "Entity",
    amount: int,
    attacker: Optional["Entity"] = None,
) -> None:
    """target に amount のダメージを与える。死亡時は撃破処理＋（attacker がいれば）経験値。"""
    if target.fighter is None:
        return
    ts = getattr(target, "skills", None)   # スキルを持つのはプレイヤーのみ
    # 運の奥義：確率で攻撃を完全回避
    if ts is not None and ts.dodge_chance() and ts.roll(ts.dodge_chance()):
        engine.message_log.add_message(f"{target.name} は攻撃をかわした！", colors.NO_EFFECT)
        engine.pending_fx.append(("popup", target.x, target.y, "MISS", (170, 210, 255)))
        return
    # 防御の奥義：被ダメージを軽減
    if ts is not None and ts.damage_reduction():
        amount = max(1, int(amount * (1.0 - ts.damage_reduction())))
    target.fighter.hp -= amount
    # 攻撃の奥義：与ダメージの一部を吸収して回復
    if attacker is not None and attacker.fighter is not None and amount > 0:
        a_sk = getattr(attacker, "skills", None)
        if a_sk is not None and a_sk.lifesteal_frac():
            heal = max(1, int(amount * a_sk.lifesteal_frac()))
            attacker.fighter.hp = min(attacker.fighter.max_hp, attacker.fighter.hp + heal)
    # 棘の符呪：被弾時、近接攻撃者へダメージを反射（防具に棘があると）
    if attacker is not None and attacker.fighter is not None and attacker.fighter.hp > 0 and amount > 0:
        import enchant
        frac = enchant.armor_thorns_frac(target)
        if frac > 0:
            inflict_damage(engine, attacker, max(1, int(amount * frac)), attacker=target)
    if target.fighter.hp <= 0:
        _die(engine, target)
        if (
            attacker is not None
            and attacker.level is not None
            and target.level is not None
        ):
            grant_xp(engine, attacker, target.level.xp_given)


def _die(engine: "Engine", target: "Entity") -> None:
    if target is engine.player:
        engine.message_log.add_message("あなたは倒れた！  ESC で終了", colors.PLAYER_DIE)
        engine.game_over = True
    else:
        engine.message_log.add_message(f"{target.name} を倒した！", colors.ENEMY_DIE)
        # 学習する敵（RLEnemy）は、死ぬ前に最後の判断を死亡報酬で確定させる
        on_death = getattr(target.ai, "on_death", None)
        if on_death is not None:
            on_death(engine)
        target.ai = None                 # もう動かない
        target.blocks_movement = False   # 死体はすり抜けられる
        loot = getattr(target, "loot", None)
        if loot is not None:             # ボス等のレア報酬を最寄りの空きマスに落とす
            half = getattr(target, "size", 1) // 2
            lx, ly = _free_item_tile(engine, target.x + half, target.y + half)
            engine.game_map.entities.append(loot.spawn(lx, ly))
            engine.message_log.add_message(f"{loot.name} を落とした！", colors.LEVEL_UP)
        # 稀に種をこぼす（栽培のタネを探索でも入手できる）。既存アイテムに重ねない
        if random.random() < SEED_DROP_CHANCE:
            import entity_factories  # 遅延import（循環回避）
            seed = random.choice([entity_factories.nut_seed, entity_factories.herb_seed,
                                  entity_factories.mushroom_seed])
            sx, sy = _free_item_tile(engine, target.x, target.y)
            engine.game_map.entities.append(seed.spawn(sx, sy))
            engine.message_log.add_message(f"{seed.name} がこぼれ落ちた。", colors.ITEM)
        target.size = 1                  # 死体は通常サイズに
        target.name = f"{target.name}の死体"
    target.sprite = "corpse"


def grant_xp(engine: "Engine", attacker: "Entity", amount: int) -> None:
    if amount <= 0 or attacker.level is None or attacker.fighter is None:
        return
    import enchant
    amount = int(amount * enchant.looting_mult(attacker))   # 略奪の符呪：撃破XP増
    is_player = attacker is engine.player
    if is_player:
        engine.message_log.add_message(f"{amount} の経験値を得た。", colors.XP)

    gained = attacker.level.add_xp(amount)
    for _ in range(gained):
        f = attacker.fighter
        f.max_hp += HP_PER_LEVEL
        f.hp += HP_PER_LEVEL          # 上昇分だけ回復
        f.base_power += POWER_PER_LEVEL
        if is_player:
            engine.message_log.add_message(
                f"レベルアップ！ Lv.{attacker.level.current_level} になった。",
                colors.LEVEL_UP,
            )
        elif engine.game_map.visible[attacker.x, attacker.y]:
            engine.message_log.add_message(
                f"{attacker.name} がレベルアップした！", colors.LEVEL_UP
            )
