from __future__ import annotations

from typing import TYPE_CHECKING

import colors
import combat
import item_category
from components.fighter import HUNGER_DAMAGE_MULT

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


class DescendAction(Action):
    """下り階段の上で実行すると次の階へ降りる（ターンは別扱い）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        if (entity.x, entity.y) == engine.game_map.downstairs_location:
            engine.generate_floor()
            engine.message_log.add_message(
                f"地下 {engine.current_floor} 階に降りた。", colors.DESCEND
            )
        else:
            engine.message_log.add_message("ここには階段がない。", colors.NO_EFFECT)


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


class CycleInventoryCategoryAction(Action):
    """持ち物メニューの分類タブを左右に切り替える（ターンは経過しない）。"""

    consumes_turn = False

    def __init__(self, delta: int):
        self.delta = delta

    def perform(self, engine: Engine, entity: Entity) -> None:
        n = len(item_category.ORDER)
        engine.inventory_category = (engine.inventory_category + self.delta) % n


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

        # 素材・大切なものなど、使用も装備もできないもの
        engine.message_log.add_message(f"{item.name} は今は使えない。", colors.NO_EFFECT)
        self.consumes_turn = False


class PickupAction(Action):
    """足元のアイテムを拾う（G キー）。要らなければ拾わずに通り過ぎられる。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        item = engine.item_under_player()
        if item is None:
            engine.message_log.add_message("足元には何もない。", colors.NO_EFFECT)
            self.consumes_turn = False
            return
        inv = entity.inventory
        if inv is None or len(inv.items) >= inv.capacity:
            engine.message_log.add_message(
                f"持ち物がいっぱいで {item.name} を拾えない。", colors.NO_EFFECT
            )
            self.consumes_turn = False
            return
        engine.game_map.entities.remove(item)
        inv.items.append(item)
        engine.message_log.add_message(f"{item.name} を拾った。", colors.ITEM)


class CampMoveCursorAction(Action):
    """拠点メニューのカーソルを上下に動かす。"""

    consumes_turn = False

    def __init__(self, delta: int):
        self.delta = delta

    def perform(self, engine: Engine, entity: Entity) -> None:
        import camp
        camp.move_cursor(engine, self.delta)


class CampSelectAction(Action):
    """拠点メニューで現在の項目を決定する。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        import camp
        camp.select(engine)


class CampBackAction(Action):
    """拠点メニューで一つ前に戻る。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        import camp
        camp.back(engine)


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
        if damage > 0 and target.fighter.is_hungry:
            damage = int(damage * HUNGER_DAMAGE_MULT)  # 空腹だと受けるダメージ増
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
