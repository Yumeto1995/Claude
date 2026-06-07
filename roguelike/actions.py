from __future__ import annotations

from typing import TYPE_CHECKING

import colors

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Action:
    """すべての行動の基底クラス。perform() で実際の効果を起こす。"""

    consumes_turn = True  # この行動でターンが経過する（＝敵が動く）か
    is_attack = False     # 攻撃モーションか（攻撃ターンはスタミナ回復しない）

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise NotImplementedError()


class EscapeAction(Action):
    """ゲームを終了する。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise SystemExit()


class WaitAction(Action):
    """その場で1ターン待つ（足踏み）。何もしないがターンは経過する。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.message_log.add_message("その場で待機した。", colors.NO_EFFECT)


class ToggleAttackModeAction(Action):
    """移動モード ⇄ 攻撃モードを切り替える（ターンは経過しない）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.attack_mode = not engine.attack_mode
        mode = "攻撃モード" if engine.attack_mode else "移動モード"
        engine.message_log.add_message(f"{mode} に切り替えた。", colors.WELCOME)


class ActionWithDirection(Action):
    """方向 (dx, dy) を持つ行動の共通基底。"""

    def __init__(self, dx: int, dy: int):
        self.dx = dx
        self.dy = dy

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise NotImplementedError()


class MovementAction(ActionWithDirection):
    """エンティティを (dx, dy) だけ動かす（移動できる場合のみ）。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        dest_x = entity.x + self.dx
        dest_y = entity.y + self.dy

        if not engine.game_map.in_bounds(dest_x, dest_y):
            return  # マップ外
        if not engine.game_map.tiles["walkable"][dest_x, dest_y]:
            return  # 壁
        if engine.game_map.get_blocking_entity_at(dest_x, dest_y):
            return  # 他のエンティティがいる

        entity.move(self.dx, self.dy)


class MeleeAction(ActionWithDirection):
    """隣接するエンティティへの近接攻撃。"""

    is_attack = True

    def perform(self, engine: Engine, entity: Entity) -> None:
        # スタミナが足りなければ攻撃モーションを取れない（ターンも消費しない）
        if entity.fighter is not None and not entity.fighter.can_attack():
            engine.message_log.add_message("スタミナが足りない！", colors.NO_EFFECT)
            self.consumes_turn = False
            return
        # 攻撃モーション成立：スタミナを消費（空振りでも消費する）
        if entity.fighter is not None:
            entity.fighter.spend_attack_stamina()

        dest_x = entity.x + self.dx
        dest_y = entity.y + self.dy
        target = engine.game_map.get_blocking_entity_at(dest_x, dest_y)
        # 攻撃先に戦える相手がいなければ空振り（攻撃モードでの素振りなど）
        if target is None or target.fighter is None or entity.fighter is None:
            engine.message_log.add_message("空振りした。", colors.NO_EFFECT)
            return

        damage = entity.fighter.power - target.fighter.defense
        attack_color = colors.PLAYER_ATK if entity is engine.player else colors.ENEMY_ATK
        desc = f"{entity.name} が {target.name} を攻撃"
        if damage > 0:
            engine.message_log.add_message(f"{desc} → {damage} ダメージ", attack_color)
            target.fighter.hp -= damage
        else:
            engine.message_log.add_message(f"{desc} → 効果がない", colors.NO_EFFECT)

        # HP が尽きたら撃破
        if target.fighter.hp <= 0:
            self._die(engine, target)

    @staticmethod
    def _die(engine: Engine, target: Entity) -> None:
        if target is engine.player:
            engine.message_log.add_message("あなたは倒れた！  ESC で終了", colors.PLAYER_DIE)
            engine.game_over = True
        else:
            engine.message_log.add_message(f"{target.name} を倒した！", colors.ENEMY_DIE)
            target.ai = None                 # もう動かない
            target.blocks_movement = False   # 死体はすり抜けられる
            target.name = f"{target.name}の死体"
        # 共通：見た目を死体スプライトに
        target.sprite = "corpse"


class BumpAction(ActionWithDirection):
    """移動先に敵がいれば攻撃、いなければ移動、と自動で振り分ける。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        dest_x = entity.x + self.dx
        dest_y = entity.y + self.dy

        if engine.game_map.get_blocking_entity_at(dest_x, dest_y):
            sub: ActionWithDirection = MeleeAction(self.dx, self.dy)
        else:
            sub = MovementAction(self.dx, self.dy)
        sub.perform(engine, entity)
        # 実際に行った行動（攻撃 or 移動）の結果を引き継ぐ
        self.consumes_turn = sub.consumes_turn
        self.is_attack = sub.is_attack
