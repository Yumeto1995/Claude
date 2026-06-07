from __future__ import annotations

from typing import TYPE_CHECKING

import colors
import combat

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


class ToggleInventoryAction(Action):
    """持ち物メニューを開閉する（ターンは経過しない）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.inventory_open = not engine.inventory_open


class UseItemAction(Action):
    """持ち物のアイテムを使う。"""

    def __init__(self, item: Entity):
        self.item = item

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.inventory_open = False  # 選んだらメニューを閉じる
        item = self.item

        # 装備品なら装備/解除（持ち物には残る）
        if item.equippable is not None and entity.equipment is not None:
            entity.equipment.toggle_equip(item, engine)
            return

        # 消費アイテムなら使用（成功時のみ消費）
        if item.consumable is not None and entity.inventory is not None:
            used = item.consumable.activate(engine, entity)
            if used:
                entity.inventory.items.remove(item)
            else:
                self.consumes_turn = False  # 使えなかった（満タン等）→ターン非消費
            return

        self.consumes_turn = False


def _auto_pickup(engine: Engine, actor: Entity) -> None:
    """actor が乗っている床のアイテムを1つ拾う（持ち物がいっぱいなら拾わない）。"""
    inv = actor.inventory
    for item in list(engine.game_map.entities):
        if item.consumable is None:
            continue  # アイテムでない
        if item.x == actor.x and item.y == actor.y:
            if len(inv.items) >= inv.capacity:
                engine.message_log.add_message(
                    f"持ち物がいっぱいで {item.name} を拾えない。", colors.NO_EFFECT
                )
                return
            engine.game_map.entities.remove(item)
            inv.items.append(item)
            engine.message_log.add_message(f"{item.name} を拾った。", colors.ITEM)
            return


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

        # 進めない場合はターンを消費しない（長押しで壁に詰まっても時間が進まない）
        if not engine.game_map.in_bounds(dest_x, dest_y):
            self.consumes_turn = False
            return  # マップ外
        if not engine.game_map.tiles["walkable"][dest_x, dest_y]:
            self.consumes_turn = False
            return  # 壁
        if engine.game_map.get_blocking_entity_at(dest_x, dest_y):
            self.consumes_turn = False
            return  # 他のエンティティがいる

        entity.move(self.dx, self.dy)
        # 持ち物を持つ者（＝プレイヤー）が乗った床のアイテムを自動取得
        if entity.inventory is not None:
            _auto_pickup(engine, entity)


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
        # 攻撃方向への踏み込みアニメを予約（命中・空振り問わず）
        engine.pending_animations.append((entity, self.dx, self.dy))

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
            combat.inflict_damage(engine, target, damage, attacker=entity)
        else:
            engine.message_log.add_message(f"{desc} → 効果がない", colors.NO_EFFECT)


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
