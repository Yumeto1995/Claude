from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class Action:
    """すべての行動の基底クラス。perform() で実際の効果を起こす。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise NotImplementedError()


class EscapeAction(Action):
    """ゲームを終了する。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise SystemExit()


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

    def perform(self, engine: Engine, entity: Entity) -> None:
        dest_x = entity.x + self.dx
        dest_y = entity.y + self.dy
        target = engine.game_map.get_blocking_entity_at(dest_x, dest_y)
        # 戦えない相手（死体など）には何もしない
        if target is None or target.fighter is None or entity.fighter is None:
            return

        damage = entity.fighter.power - target.fighter.defense
        desc = f"{entity.name} が {target.name} を攻撃"
        if damage > 0:
            print(f"{desc} → {damage} ダメージ")
            target.fighter.hp -= damage
        else:
            print(f"{desc} → 効果がない")

        # HP が尽きたら撃破
        if target.fighter.hp <= 0:
            self._die(engine, target)

    @staticmethod
    def _die(engine: Engine, target: Entity) -> None:
        if target is engine.player:
            print("*** あなたは倒れた！  ESC で終了 ***")
            engine.game_over = True
        else:
            print(f"{target.name} を倒した！")
            target.ai = None                 # もう動かない
            target.blocks_movement = False   # 死体はすり抜けられる
            target.name = f"{target.name}の死体"
        # 共通：見た目を死体（赤い %）に
        target.char = "%"
        target.color = (191, 0, 0)


class BumpAction(ActionWithDirection):
    """移動先に敵がいれば攻撃、いなければ移動、と自動で振り分ける。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        dest_x = entity.x + self.dx
        dest_y = entity.y + self.dy

        if engine.game_map.get_blocking_entity_at(dest_x, dest_y):
            MeleeAction(self.dx, self.dy).perform(engine, entity)
        else:
            MovementAction(self.dx, self.dy).perform(engine, entity)
