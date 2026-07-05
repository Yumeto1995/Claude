from __future__ import annotations

import random
from typing import TYPE_CHECKING

import colors
import combat
import enchant
import item_category
from components.fighter import HUNGER_DAMAGE_MULT

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

CRIT_MULT = 1.5  # 会心（クリティカル）のダメージ倍率


def _roll_crit(entity: "Entity", ranged: bool = False) -> bool:
    """会心（クリティカル）判定。装備の会心率＋符呪『会心』＋スキル『運』を合算して1回抽選。"""
    chance = 0.0
    eqp = getattr(entity, "equipment", None)
    if eqp is not None:
        weapon = eqp.ranged if ranged else eqp.weapon
        if weapon is not None and weapon.equippable is not None:
            chance += getattr(weapon.equippable, "crit_chance", 0.0)
    chance += enchant.weapon_crit_frac(entity, ranged=ranged)
    sk = getattr(entity, "skills", None)
    if sk is not None:
        chance += sk.crit_chance()
    return chance > 0.0 and random.random() < chance


class ReturnToTitle(Exception):
    """ゲーム中に ESC が押され、タイトル画面に戻ることを表す。"""


class Action:
    """すべての行動の基底クラス。perform() で実際の効果を起こす。"""

    consumes_turn = True  # この行動でターンが経過する（＝敵が動く）か
    is_attack = False     # 攻撃モーションか（攻撃ターンはスタミナ回復しない）

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise NotImplementedError()


class EscapeAction(Action):
    """タイトル画面に戻る（自動セーブ）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        raise ReturnToTitle()


class WaitAction(Action):
    """その場で1ターン待つ（足踏み）。何もしないがターンは経過する。"""

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.message_log.add_message("その場で待機した。", colors.NO_EFFECT)


class UseStairsAction(Action):
    """足元の階段を使う：上り階段→前の階（1階なら村）、下り階段→次の階。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.use_stairs()


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
        engine.inventory_cursor = 0


class CycleInventoryCategoryAction(Action):
    """持ち物メニューの分類タブを左右に切り替える（ターンは経過しない）。"""

    consumes_turn = False

    def __init__(self, delta: int):
        self.delta = delta

    def perform(self, engine: Engine, entity: Entity) -> None:
        n = len(item_category.ORDER)
        engine.inventory_category = (engine.inventory_category + self.delta) % n
        engine.inventory_cursor = 0  # 分類を変えたらカーソルは先頭へ


class MoveInventoryCursorAction(Action):
    """持ち物メニューのカーソルを上下に動かす（ターンは経過しない）。"""

    consumes_turn = False

    def __init__(self, delta: int):
        self.delta = delta

    def perform(self, engine: Engine, entity: Entity) -> None:
        category = item_category.ORDER[engine.inventory_category]
        items = item_category.items_in(entity.inventory.items, category)
        if not items:
            engine.inventory_cursor = 0
            return
        cursor = engine.inventory_cursor + self.delta
        engine.inventory_cursor = max(0, min(cursor, len(items) - 1))


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
        if inv is None or not inv.can_accept(item):
            # 大切なものは can_accept が常に True なので、ここには来ない＝拾い逃さない
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


class CampInteractAction(Action):
    """テント内で足元の設備を使う（Enter）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.camp_interact()


class CampBuildAction(Action):
    """建設モードの道具操作（cycle=切替 / select=直接選択 / use=使用 / exit=終了）。"""

    consumes_turn = False

    def __init__(self, op: str, index: int = None):
        self.op = op
        self.index = index

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.camp_tool_op(self.op, self.index)


class CampLeaveAction(Action):
    """テントからダンジョンに戻る（ESC）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.leave_camp()


class VillageInteractAction(Action):
    """村で足元/隣を調べる（入口→ダンジョン、NPC→会話）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.village_interact()


class BuildingLeaveAction(Action):
    """建物から村へ戻る（ESC）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.leave_building()


class ShopMoveCursorAction(Action):
    """店の選択カーソルを上下に動かす。"""

    consumes_turn = False

    def __init__(self, delta: int):
        self.delta = delta

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.shop_move_cursor(self.delta)


class ShopBuyAction(Action):
    """店でカーソル位置の品を買う（代金＝経験値）。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.shop_buy()


class ShopCloseAction(Action):
    """店を閉じる。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.shop_close()


class ShopToggleModeAction(Action):
    """店の『買う／売る』モードを切り替える。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.shop_toggle_mode()


class ToggleSkillTreeAction(Action):
    """スキルツリー画面を開閉する。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.toggle_skill_tree()


class SkillNavAction(Action):
    """スキルツリーのカーソル移動（系統←→・段↑↓）。"""

    consumes_turn = False

    def __init__(self, dbranch: int, dtier: int):
        self.dbranch = dbranch
        self.dtier = dtier

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.skill_nav(self.dbranch, self.dtier)


class SkillUnlockAction(Action):
    """選択中のスキルノードを習得する。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.skill_unlock()


class CloseDialogueAction(Action):
    """会話ウィンドウを閉じる。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.dialogue = None


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
        # 斜め移動は縦・横の両隣が床でないと不可（壁の角を斜めにすり抜けない）
        if self.dx != 0 and self.dy != 0:
            walk = engine.game_map.tiles["walkable"]
            if not (walk[entity.x + self.dx, entity.y] and walk[entity.x, entity.y + self.dy]):
                self.consumes_turn = False
                return
        if engine.game_map.get_blocking_entity_at(dest_x, dest_y):
            self.consumes_turn = False
            return  # 他のエンティティがいる
        # モンスターはセーフルームに入れない（プレイヤーは入れる）
        if entity is not engine.player and engine.game_map.safe[dest_x, dest_y]:
            self.consumes_turn = False
            return

        entity.move(self.dx, self.dy)
        engine.pending_moves.append((entity, self.dx, self.dy))  # 歩行アニメを予約


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
        # 攻撃方向への踏み込みアニメ＋攻撃先タイルの斬撃エフェクト（命中・空振り問わず）
        engine.pending_animations.append((entity, self.dx, self.dy))
        engine.pending_fx.append(("slash", dest_x, dest_y, self.dx, self.dy))

        target = engine.game_map.get_blocking_entity_at(dest_x, dest_y)
        # 攻撃先に戦える相手がいなければ空振り（攻撃モードでの素振りなど）
        if target is None or target.fighter is None or entity.fighter is None:
            engine.message_log.add_message("空振りした。", colors.NO_EFFECT)
            return

        damage = entity.fighter.power - target.fighter.defense
        damage += enchant.weapon_fire_bonus(entity)   # 火炎の符呪：追加ダメージ
        if target.fighter.is_hungry:
            damage = int(damage * HUNGER_DAMAGE_MULT)  # 空腹だと受けるダメージ増
        damage = max(1, damage)  # 命中すれば最低1ダメージ（防御で完全無効化しない）
        # 会心の一撃（1.5倍）：武器の会心率＋符呪『会心』＋スキル『運』の合算で判定
        crit = _roll_crit(entity, ranged=False)
        if crit:
            damage = int(damage * CRIT_MULT)
        attack_color = colors.PLAYER_ATK if entity is engine.player else colors.ENEMY_ATK
        prefix = "会心の一撃！ " if crit else ""
        engine.message_log.add_message(
            f"{prefix}{entity.name} が {target.name} を攻撃 → {damage} ダメージ", attack_color
        )
        # 被弾フラッシュ＋ダメージ数字（プレイヤーが受けたダメージは赤系で表示）
        engine.pending_fx.append(("flash", target))
        popup_color = (255, 90, 90) if target is engine.player else (255, 240, 140)
        engine.pending_fx.append(("popup", dest_x, dest_y, f"-{damage}", popup_color))
        combat.inflict_damage(engine, target, damage, attacker=entity)
        enchant.apply_knockback(engine, entity, target, self.dx, self.dy)  # 撃退の符呪


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


def _find_ammo(entity: Entity):
    """持ち物の中から、残りのある矢（AMMO）スタックを返す。無ければ None。"""
    inv = getattr(entity, "inventory", None)
    if inv is None:
        return None
    for it in inv.items:
        if item_category.category_of(it) == item_category.ItemCategory.AMMO and it.count > 0:
            return it
    return None


class ToggleFireModeAction(Action):
    """射撃モードの切替。オン時は次の方向キーで矢を1本撃つ。弓と矢が無ければ入れない。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        if getattr(engine, "fire_mode", False):
            engine.fire_mode = False
            return
        eq = getattr(entity, "equipment", None)
        if eq is None or eq.ranged is None:
            engine.message_log.add_message("弓を装備していない。", colors.NO_EFFECT)
            return
        if _find_ammo(entity) is None:
            engine.message_log.add_message("矢を持っていない。", colors.NO_EFFECT)
            return
        engine.fire_mode = True
        engine.message_log.add_message("射撃方向を選択（ESC で中止）。", colors.WELCOME)


class RangedAttackAction(ActionWithDirection):
    """装備中の弓で矢を1本撃つ。(dx, dy) 方向の直線上で最初に当たった敵に命中。"""

    is_attack = True

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.fire_mode = False
        eq = getattr(entity, "equipment", None)
        bow = eq.ranged if eq is not None else None
        ammo = _find_ammo(entity)
        f = entity.fighter
        fire_cost = bow.equippable.stamina_cost if (bow and bow.equippable) else 0

        # 前提チェック（どれか欠けたらターン消費せず中止）
        if bow is None or bow.equippable is None:
            engine.message_log.add_message("弓を装備していない。", colors.NO_EFFECT)
            self.consumes_turn = False
            return
        if ammo is None:
            engine.message_log.add_message("矢を持っていない。", colors.NO_EFFECT)
            self.consumes_turn = False
            return
        if self.dx == 0 and self.dy == 0:
            self.consumes_turn = False
            return
        if f is not None and f.uses_stamina and f.stamina < fire_cost:
            engine.message_log.add_message("スタミナが足りない！", colors.NO_EFFECT)
            self.consumes_turn = False
            return

        # コスト：スタミナと矢を1本消費
        if f is not None and f.uses_stamina:
            f.stamina = max(0, f.stamina - fire_cost)
        ammo.count -= 1
        if ammo.count <= 0 and entity.inventory is not None:
            entity.inventory.items.remove(ammo)

        # 直線を走査：壁/マップ端で停止、最初の戦える相手に命中
        gm = engine.game_map
        max_range = bow.equippable.max_range or 1
        x, y = entity.x, entity.y
        path = []
        target = None
        for _ in range(max_range):
            x += self.dx
            y += self.dy
            if not gm.in_bounds(x, y) or not gm.tiles["walkable"][x, y]:
                break
            path.append((x, y))
            blocker = gm.get_blocking_entity_at(x, y)
            if blocker is not None and blocker.fighter is not None:
                target = blocker
                break

        # 矢の軌道エフェクト（Renderer が再生）
        engine.pending_fx.append(("arrow", entity.x, entity.y, self.dx, self.dy, list(path)))

        if target is None:
            engine.message_log.add_message(f"{entity.name} の矢は外れた。", colors.NO_EFFECT)
            return

        # ダメージ（近接と同じ作法。弓の power_bonus を素の攻撃力に加える）
        base = (f.base_power if f is not None else 0) + bow.equippable.power_bonus
        damage = base - target.fighter.defense
        if target.fighter.is_hungry:
            damage = int(damage * HUNGER_DAMAGE_MULT)
        damage = max(1, damage)
        # 会心（射撃）：弓/クロスボウの会心率＋符呪『会心』＋スキル『運』
        crit = _roll_crit(entity, ranged=True)
        if crit:
            damage = int(damage * CRIT_MULT)
        attack_color = colors.PLAYER_ATK if entity is engine.player else colors.ENEMY_ATK
        prefix = "会心の一撃！ " if crit else ""
        engine.message_log.add_message(
            f"{prefix}{entity.name} の矢が {target.name} に命中 → {damage} ダメージ", attack_color
        )
        engine.pending_fx.append(("flash", target))
        engine.pending_fx.append(("popup", target.x, target.y, f"-{damage}", (255, 240, 140)))
        combat.inflict_damage(engine, target, damage, attacker=entity)


# --- アイテム投擲 ---------------------------------------------------------
THROW_RANGE = 6          # 投げが届く最大マス数
THROW_BASE_POWER = 3     # 投擲の基礎威力（武器なら power_bonus を加算）


class BeginThrowAction(Action):
    """持ち物で選んだアイテムを投げる体勢に入る（次の方向キーで投げる）。"""

    consumes_turn = False

    def __init__(self, item: Entity):
        self.item = item

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.inventory_open = False
        engine.throw_item = self.item
        engine.message_log.add_message(
            f"{self.item.name} を投げる方向を選択（ESC で中止）。", colors.WELCOME
        )


class CancelThrowAction(Action):
    """投げる体勢を中止する。"""

    consumes_turn = False

    def perform(self, engine: Engine, entity: Entity) -> None:
        engine.throw_item = None


class ThrowItemAction(ActionWithDirection):
    """選んだアイテムを (dx, dy) 方向へ投げる。直線上で最初に当たった敵に命中。"""

    is_attack = True

    def perform(self, engine: Engine, entity: Entity) -> None:
        item = getattr(engine, "throw_item", None)
        engine.throw_item = None
        if item is None or (self.dx == 0 and self.dy == 0):
            self.consumes_turn = False
            return

        # 直線を走査：壁/マップ端で停止、最初の戦える相手に命中
        gm = engine.game_map
        x, y = entity.x, entity.y
        path = []
        target = None
        for _ in range(THROW_RANGE):
            x += self.dx
            y += self.dy
            if not gm.in_bounds(x, y) or not gm.tiles["walkable"][x, y]:
                break
            path.append((x, y))
            blocker = gm.get_blocking_entity_at(x, y)
            if blocker is not None and blocker.fighter is not None:
                target = blocker
                break

        engine.pending_fx.append(("arrow", entity.x, entity.y, self.dx, self.dy, list(path)))

        # 投げたぶんを1個消費（スタックは1減、最後の1個は持ち物から除去）
        if getattr(item, "count", 1) > 1:
            item.count -= 1
        elif entity.inventory is not None and item in entity.inventory.items:
            entity.inventory.items.remove(item)

        if target is None:
            engine.message_log.add_message(f"{item.name} を投げたが外れた。", colors.NO_EFFECT)
            return

        eqp = getattr(item, "equippable", None)
        base = THROW_BASE_POWER + (eqp.power_bonus if eqp is not None else 0)
        damage = max(1, base - target.fighter.defense)
        if target.fighter.is_hungry:
            damage = max(1, int(damage * HUNGER_DAMAGE_MULT))
        attack_color = colors.PLAYER_ATK if entity is engine.player else colors.ENEMY_ATK
        engine.message_log.add_message(
            f"{item.name} を投げて {target.name} に {damage} ダメージ！", attack_color
        )
        engine.pending_fx.append(("flash", target))
        engine.pending_fx.append(("popup", target.x, target.y, f"-{damage}", (255, 240, 140)))
        combat.inflict_damage(engine, target, damage, attacker=entity)
