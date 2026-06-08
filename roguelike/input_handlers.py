from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

import item_category
from actions import (
    Action,
    BumpAction,
    CampBackAction,
    CampInteractAction,
    CampLeaveAction,
    CampMoveCursorAction,
    CampSelectAction,
    CycleInventoryCategoryAction,
    DescendAction,
    EscapeAction,
    MeleeAction,
    PickupAction,
    ToggleAttackModeAction,
    ToggleInventoryAction,
    UseItemAction,
    WaitAction,
)

if TYPE_CHECKING:
    from engine import Engine

# キー → 方向 (dx, dy)。矢印・WASD・vi(hjkl) に対応。
_DIRECTIONS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_k: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_j: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_h: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0), pygame.K_l: (1, 0),
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

        # 拠点（テント内）にいる間は専用の操作
        if engine.in_camp:
            if engine.camp_menu is not None:
                return _camp_menu_keys(key, engine)   # 設備メニュー中
            # テント内を歩いている：Enter=設備を使う、ESC=ダンジョンへ
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return CampInteractAction()
            if key == pygame.K_ESCAPE:
                return CampLeaveAction()
            return None  # 方向キーはポーリングで移動

        # 持ち物メニューを開いている間は専用の操作
        if engine.inventory_open:
            return _inventory_keys(key, engine)

        # 攻撃モードの方向キーは1押し1攻撃（連打防止のため単発で扱う）
        if key in _DIRECTIONS and engine.attack_mode:
            dx, dy = _DIRECTIONS[key]
            return MeleeAction(dx, dy)

        # 階段で次の階へ（Enter または > キー）
        if event.unicode == ">" or key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return DescendAction()
        if key == pygame.K_g:
            return PickupAction()               # 足元のアイテムを拾う
        if key == pygame.K_z:
            return WaitAction()                 # 足踏み
        if key == pygame.K_SPACE:
            return ToggleAttackModeAction()      # 攻撃/移動モード切替
        if key == pygame.K_i:
            return ToggleInventoryAction()       # 持ち物を開く
        if key == pygame.K_ESCAPE:
            return EscapeAction()

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
    """持ち物メニュー中のキー操作。←→で分類切替、a〜で使用/装備、ESC/i で閉じる。"""
    if key in (pygame.K_ESCAPE, pygame.K_i):
        return ToggleInventoryAction()  # 閉じる
    if key == pygame.K_LEFT:
        return CycleInventoryCategoryAction(-1)
    if key == pygame.K_RIGHT:
        return CycleInventoryCategoryAction(1)

    # 現在の分類タブの中だけを a〜 で選ぶ
    index = key - pygame.K_a  # a=0, b=1, ...
    category = item_category.ORDER[engine.inventory_category]
    items = item_category.items_in(engine.player.inventory.items, category)
    if 0 <= index < len(items):
        return UseItemAction(items[index])
    return None


def held_movement_action(engine: "Engine") -> Optional[Action]:
    """押しっぱなしの方向キーから移動 Action を返す（移動モード時のみ）。

    メインループがクールダウンを挟みつつ毎フレーム呼ぶことで連続移動になる。
    """
    if engine.game_over:
        return None
    if engine.in_camp:
        if engine.camp_menu is not None:
            return None  # 設備メニュー中は歩けない
    elif engine.attack_mode or engine.inventory_open:
        return None
    keys = pygame.key.get_pressed()
    for keycode, (dx, dy) in _DIRECTIONS.items():
        if keys[keycode]:
            return BumpAction(dx, dy)
    return None
