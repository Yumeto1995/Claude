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
    target.fighter.hp -= amount
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
        target.name = f"{target.name}の死体"
    target.sprite = "corpse"


def grant_xp(engine: "Engine", attacker: "Entity", amount: int) -> None:
    if amount <= 0 or attacker.level is None or attacker.fighter is None:
        return
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
