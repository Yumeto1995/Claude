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
    CloseDialogueAction,
    CycleInventoryCategoryAction,
    DescendAction,
    EscapeAction,
    MeleeAction,
    MovementAction,
    PickupAction,
    ToggleAttackModeAction,
    ToggleInventoryAction,
    UseItemAction,
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


def dispatch_event(event: pygame.event.Event, engine: "Engine") -> Optional[Action]:
    """単発キー（押すたび1回）のイベントを Action に変換する。

    移動モードの方向キーはここでは扱わず、長押し対応のため
    held_movement_action() でフレーム毎にポーリングする。
    """
    if event.type == pygame.QUIT:
        raise SystemExit()

    if event.type == pygame.KEYDOWN:
        key = event.key

        # 村にいる間は専用の操作
        if getattr(engine, "in_village", False):
            if getattr(engine, "dialogue", None) is not None:
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                    return CloseDialogueAction()
                return None
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return VillageInteractAction()  # 入口→ダンジョン / NPC→会話
            if key == pygame.K_ESCAPE:
                return EscapeAction()  # タイトルへ
            return None  # 方向キーはポーリングで移動

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
    non_combat = engine.in_camp or getattr(engine, "in_village", False)
    if engine.in_camp:
        if engine.camp_menu is not None:
            return None  # 設備メニュー中は歩けない
    elif getattr(engine, "in_village", False):
        if getattr(engine, "dialogue", None) is not None:
            return None  # 会話中は歩けない
    elif engine.attack_mode or engine.inventory_open:
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
