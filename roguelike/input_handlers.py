from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

import item_category
from actions import (
    Action,
    BumpAction,
    CampBackAction,
    CampBuildAction,
    CampInteractAction,
    CampLeaveAction,
    CampMoveCursorAction,
    CampSelectAction,
    BuildingLeaveAction,
    CloseDialogueAction,
    CycleInventoryCategoryAction,
    EscapeAction,
    MeleeAction,
    MoveInventoryCursorAction,
    MovementAction,
    PickupAction,
    RangedAttackAction,
    BeginThrowAction,
    ThrowItemAction,
    CancelThrowAction,
    ShopBuyAction,
    ShopCloseAction,
    ShopMoveCursorAction,
    ShopToggleModeAction,
    SkillNavAction,
    SkillUnlockAction,
    ToggleAttackModeAction,
    ToggleFireModeAction,
    ToggleInventoryAction,
    ToggleSkillTreeAction,
    UseItemAction,
    UseStairsAction,
    VillageInteractAction,
    WaitAction,
)

if TYPE_CHECKING:
    from engine import Engine

# キー → 方向 (dx, dy)。矢印・WASD・vi(hjkl/yubn)・テンキーに対応。
_DIRECTIONS = {
    # 上下左右
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_k: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_j: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_h: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0), pygame.K_l: (1, 0),
    # 斜め（vi: yubn）
    pygame.K_y: (-1, -1), pygame.K_u: (1, -1), pygame.K_b: (-1, 1), pygame.K_n: (1, 1),
    # テンキー
    pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1), pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0),
    pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1), pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1),
}

# 数字キー 1-7 → 道具インデックス（建設モードの道具を直接選択）
_NUM_KEYS = {
    pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3,
    pygame.K_5: 4, pygame.K_6: 5, pygame.K_7: 6,
}


def dispatch_event(event: pygame.event.Event, engine: "Engine") -> Optional[Action]:
    """単発キー（押すたび1回）のイベントを Action に変換する。

    移動モードの方向キーはここでは扱わず、長押し対応のため
    held_movement_action() でフレーム毎にポーリングする。
    """
    if event.type == pygame.QUIT:
        raise SystemExit()

    if event.type == pygame.KEYDOWN:
        key = event.key

        # スキルツリー画面（村・ダンジョンどちらからでも開ける全画面メニュー）
        if getattr(engine, "skill_open", False):
            return _skill_keys(key)

        # 村・建物内にいる間は専用の操作
        if getattr(engine, "in_village", False):
            if engine.inventory_open:
                return _inventory_keys(key, engine)   # 村でも持ち物を開ける（テント等）
            # 店（買い物）メニュー中
            if getattr(engine, "shop_kind", None) is not None:
                if key in (pygame.K_UP, pygame.K_w, pygame.K_k):
                    return ShopMoveCursorAction(-1)
                if key in (pygame.K_DOWN, pygame.K_s, pygame.K_j):
                    return ShopMoveCursorAction(1)
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return ShopBuyAction()
                if key == pygame.K_TAB:
                    return ShopToggleModeAction()   # 買う/売る 切替
                if key == pygame.K_ESCAPE:
                    return ShopCloseAction()
                return None
            if getattr(engine, "dialogue", None) is not None:
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                    return CloseDialogueAction()
                return None
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return VillageInteractAction()  # 洞窟→ダンジョン / ドア→建物 / 店主→店 / NPC→会話
            if key == pygame.K_i:
                return ToggleInventoryAction()   # 村でも持ち物を開ける（魔法のテント等）
            if key == pygame.K_t:
                return ToggleSkillTreeAction()   # スキルツリー
            if key == pygame.K_ESCAPE:
                if getattr(engine, "building_key", None) is not None:
                    return BuildingLeaveAction()  # 建物内→村へ
                return EscapeAction()  # 屋外→タイトルへ
            return None  # 方向キーはポーリングで移動

        # 拠点（テント内）にいる間は専用の操作
        if engine.in_camp:
            if engine.inventory_open:
                return _inventory_keys(key, engine)   # 拠点でも持ち物を開ける
            if engine.camp_menu is not None:
                return _camp_menu_keys(key, engine)   # 設備メニュー中
            # 建設モード中：Enter=道具を使う / b=切替 / 1-6=道具選択 / ESC=終了
            if getattr(engine, "camp_tool", None) is not None:
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return CampBuildAction("use")
                if key == pygame.K_b:
                    return CampBuildAction("cycle")
                if key == pygame.K_ESCAPE:
                    return CampBuildAction("exit")
                if key in _NUM_KEYS:
                    return CampBuildAction("select", _NUM_KEYS[key])
                return None  # 方向キーはポーリングで移動
            # テント内を歩いている：b=建設モード / Enter=設備 / ESC=ダンジョンへ
            if key == pygame.K_b:
                return CampBuildAction("cycle")
            if key == pygame.K_i:
                return ToggleInventoryAction()   # 拠点でも持ち物を開ける
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return CampInteractAction()
            if key == pygame.K_ESCAPE:
                return CampLeaveAction()
            return None  # 方向キーはポーリングで移動

        # 持ち物メニューを開いている間は専用の操作
        if engine.inventory_open:
            return _inventory_keys(key, engine)

        # 射撃モード中：方向キーで矢を発射、ESC/f で中止（他キーは無視）
        if getattr(engine, "fire_mode", False):
            if key in _DIRECTIONS:
                dx, dy = _DIRECTIONS[key]
                return RangedAttackAction(dx, dy)
            if key in (pygame.K_ESCAPE, pygame.K_f):
                return ToggleFireModeAction()
            return None

        # 投げモード中：方向キーで投げる、ESC で中止（他キーは無視）
        if getattr(engine, "throw_item", None) is not None:
            if key in _DIRECTIONS:
                dx, dy = _DIRECTIONS[key]
                return ThrowItemAction(dx, dy)
            if key == pygame.K_ESCAPE:
                return CancelThrowAction()
            return None

        # 攻撃モードの方向キーは1押し1攻撃（連打防止のため単発で扱う）
        if key in _DIRECTIONS and engine.attack_mode:
            dx, dy = _DIRECTIONS[key]
            return MeleeAction(dx, dy)

        # 階段の昇降（Enter＝足元の階段を使う / > 下り / < 上り。どれも足元の階段で作用）
        if event.unicode in (">", "<") or key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return UseStairsAction()
        if key == pygame.K_g:
            return PickupAction()               # 足元のアイテムを拾う
        if key == pygame.K_z:
            return WaitAction()                 # 足踏み
        if key == pygame.K_SPACE:
            return ToggleAttackModeAction()      # 攻撃/移動モード切替
        if key == pygame.K_f:
            return ToggleFireModeAction()        # 射撃モード（弓で矢を撃つ）
        if key == pygame.K_i:
            return ToggleInventoryAction()       # 持ち物を開く
        if key == pygame.K_t:
            return ToggleSkillTreeAction()       # スキルツリー
        if key == pygame.K_ESCAPE:
            return EscapeAction()

    return None


def _skill_keys(key: int) -> Optional[Action]:
    """スキルツリー画面のキー操作。←→で系統、↑↓で段、Enterで習得、t/ESCで閉じる。"""
    if key in (pygame.K_LEFT, pygame.K_a, pygame.K_h):
        return SkillNavAction(-1, 0)
    if key in (pygame.K_RIGHT, pygame.K_d, pygame.K_l):
        return SkillNavAction(1, 0)
    if key in (pygame.K_UP, pygame.K_w, pygame.K_k):
        return SkillNavAction(0, -1)
    if key in (pygame.K_DOWN, pygame.K_s, pygame.K_j):
        return SkillNavAction(0, 1)
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return SkillUnlockAction()
    if key in (pygame.K_t, pygame.K_ESCAPE):
        return ToggleSkillTreeAction()
    return None


def _camp_menu_keys(key: int, engine: "Engine") -> Optional[Action]:
    """設備メニュー中のキー操作。↑↓で選択、Enterで決定、ESCで閉じる。"""
    if key in (pygame.K_UP, pygame.K_w, pygame.K_k):
        return CampMoveCursorAction(-1)
    if key in (pygame.K_DOWN, pygame.K_s, pygame.K_j):
        return CampMoveCursorAction(1)
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return CampSelectAction()
    if key == pygame.K_ESCAPE:
        return CampBackAction()
    return None


def _inventory_keys(key: int, engine: "Engine") -> Optional[Action]:
    """持ち物メニュー中のキー操作。←→で分類切替、↑↓でカーソル、Enterで使用/装備。"""
    if key in (pygame.K_ESCAPE, pygame.K_i):
        return ToggleInventoryAction()  # 閉じる
    if key in (pygame.K_LEFT, pygame.K_a, pygame.K_h):
        return CycleInventoryCategoryAction(-1)
    if key in (pygame.K_RIGHT, pygame.K_d, pygame.K_l):
        return CycleInventoryCategoryAction(1)
    if key in (pygame.K_UP, pygame.K_w, pygame.K_k):
        return MoveInventoryCursorAction(-1)
    if key in (pygame.K_DOWN, pygame.K_s, pygame.K_j):
        return MoveInventoryCursorAction(1)

    # t で投げる、Enter で使用/装備（どちらもカーソル位置のアイテム）
    if key in (pygame.K_t, pygame.K_RETURN, pygame.K_KP_ENTER):
        category = item_category.ORDER[engine.inventory_category]
        items = item_category.items_in(engine.player.inventory.items, category)
        if items:
            index = min(engine.inventory_cursor, len(items) - 1)
            if key == pygame.K_t:
                return BeginThrowAction(items[index])
            return UseItemAction(items[index])
    return None


def held_movement_action(engine: "Engine") -> Optional[Action]:
    """押しっぱなしの方向キーから移動 Action を返す（移動モード時のみ）。

    メインループがクールダウンを挟みつつ毎フレーム呼ぶことで連続移動になる。
    """
    if engine.game_over or getattr(engine, "skill_open", False):
        return None
    non_combat = engine.in_camp or getattr(engine, "in_village", False)
    if engine.in_camp:
        if engine.camp_menu is not None or engine.inventory_open:
            return None  # 設備メニュー中・持ち物を開いている間は歩けない
    elif getattr(engine, "in_village", False):
        if (getattr(engine, "dialogue", None) is not None
                or getattr(engine, "shop_kind", None) is not None
                or engine.inventory_open):
            return None  # 会話中・買い物中・持ち物中は歩けない
    elif (engine.attack_mode or engine.inventory_open
          or getattr(engine, "fire_mode", False)
          or getattr(engine, "throw_item", None) is not None):
        return None
    # 押されている方向キーを合成（↑＋→ などで斜め移動）
    keys = pygame.key.get_pressed()
    dx = dy = 0
    for keycode, (kx, ky) in _DIRECTIONS.items():
        if keys[keycode]:
            dx += kx
            dy += ky
    dx = max(-1, min(1, dx))
    dy = max(-1, min(1, dy))
    if dx == 0 and dy == 0:
        return None
    # 非戦闘マップ（村・拠点）では攻撃しない＝単純移動
    return MovementAction(dx, dy) if non_combat else BumpAction(dx, dy)
