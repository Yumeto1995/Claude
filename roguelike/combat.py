"""戦闘の共通処理（ダメージ・撃破・経験値）。

近接攻撃（actions.MeleeAction）からも、巻物などのアイテム効果
（components.consumable）からも使えるよう、ここに集約する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import colors
from components.level import HP_PER_LEVEL, POWER_PER_LEVEL

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
        target.ai = None                 # もう動かない
        target.blocks_movement = False   # 死体はすり抜けられる
        loot = getattr(target, "loot", None)
        if loot is not None:             # ボス等のレア報酬を中央の床に落とす
            half = getattr(target, "size", 1) // 2
            drop = loot.spawn(target.x + half, target.y + half)
            engine.game_map.entities.append(drop)
            engine.message_log.add_message(f"{loot.name} を落とした！", colors.LEVEL_UP)
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
