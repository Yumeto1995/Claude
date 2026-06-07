"""pygame による描画。タイル画像の読み込み・カメラ追従・下部UI（HP/ログ）を担う。

assets/<key>.png があればそれを使い、無ければ簡単な仮タイルを生成する。
日本語フォントは assets/fonts/game.ttf があれば優先、無ければ macOS のヒラギノを使う。
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict

import pygame

import colors
import tile_types

if TYPE_CHECKING:
    from engine import Engine

TILE_SIZE = 32  # 1タイルのピクセルサイズ
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# スプライトのキー → 仮タイルの色（assets に PNG が無いとき使う）
PLACEHOLDER_COLORS: Dict[str, tuple] = {
    "floor": (40, 40, 60),
    "wall": (90, 75, 55),
    "player": (255, 255, 255),
    "goblin": (80, 200, 80),
    "slime": (80, 200, 200),
    "corpse": (191, 0, 0),
}

TERRAIN_KEYS = {"floor", "wall"}

# 日本語フォントの探索候補（上から順に試す）
_FONT_CANDIDATES = [
    os.path.join(ASSETS_DIR, "fonts", "game.ttf"),  # 同梱フォント（配布用）
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def load_font(size: int) -> pygame.font.Font:
    """日本語が出せるフォントを読み込む。見つからなければ既定フォント。"""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont(None, size)  # 最終手段（日本語不可）


def _make_placeholder(key: str) -> pygame.Surface:
    """assets に画像が無いキー用の仮タイルを作る。"""
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    color = PLACEHOLDER_COLORS.get(key, (200, 0, 200))
    if key in TERRAIN_KEYS:
        surf.fill(color)
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    else:
        pygame.draw.circle(
            surf, color, (TILE_SIZE // 2, TILE_SIZE // 2), TILE_SIZE // 2 - 3
        )
    return surf


def load_sprites() -> Dict[str, pygame.Surface]:
    """全スプライトを読み込む。PNG が無ければ仮タイルで代用。"""
    sprites: Dict[str, pygame.Surface] = {}
    for key in PLACEHOLDER_COLORS:
        path = os.path.join(ASSETS_DIR, f"{key}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
            sprites[key] = img
        else:
            sprites[key] = _make_placeholder(key)
    return sprites


class Renderer:
    """ウィンドウを持ち、カメラ追従でマップ・エンティティ・下部UIを描く。"""

    PANEL_HEIGHT = 150   # 下部パネル（HP＋ログ）の高さ
    LOG_LINES = 4        # ログの表示行数
    LINE_HEIGHT = 26

    def __init__(self, view_w: int, view_h: int):
        self.view_w = view_w
        self.view_h = view_h
        self.play_h = view_h * TILE_SIZE  # マップ表示領域の高さ
        self.screen = pygame.display.set_mode(
            (view_w * TILE_SIZE, self.play_h + self.PANEL_HEIGHT)
        )
        pygame.display.set_caption("Roguelike")
        self.sprites = load_sprites()
        self.font = load_font(22)        # HP・ログ用
        self.big_font = load_font(48)    # ゲームオーバー用

    def render(self, engine: "Engine") -> None:
        screen = self.screen
        screen.fill((0, 0, 0))
        gm = engine.game_map

        # カメラ：プレイヤー中心。マップ端ではみ出さないようクランプ
        cam_x = max(0, min(engine.player.x - self.view_w // 2, gm.width - self.view_w))
        cam_y = max(0, min(engine.player.y - self.view_h // 2, gm.height - self.view_h))

        # 地形を描画
        for sy in range(self.view_h):
            for sx in range(self.view_w):
                wx, wy = cam_x + sx, cam_y + sy
                if not gm.in_bounds(wx, wy):
                    continue
                sprite_id = gm.tiles["sprite"][wx, wy]
                key = "wall" if sprite_id == tile_types.SPRITE_WALL else "floor"
                screen.blit(self.sprites[key], (sx * TILE_SIZE, sy * TILE_SIZE))

        # エンティティを描画（死体→生者の順）
        for entity in sorted(gm.entities, key=lambda e: e.blocks_movement):
            ex, ey = entity.x - cam_x, entity.y - cam_y
            if 0 <= ex < self.view_w and 0 <= ey < self.view_h:
                sprite = self.sprites.get(entity.sprite, self.sprites["player"])
                screen.blit(sprite, (ex * TILE_SIZE, ey * TILE_SIZE))

        self._render_panel(engine)

        if engine.game_over:
            self._render_game_over()

        pygame.display.flip()

    def _render_panel(self, engine: "Engine") -> None:
        """下部パネル：HP とメッセージログ。"""
        screen = self.screen
        width = self.view_w * TILE_SIZE
        # パネル背景
        pygame.draw.rect(
            screen, (20, 20, 28), (0, self.play_h, width, self.PANEL_HEIGHT)
        )
        pygame.draw.line(
            screen, (60, 60, 70), (0, self.play_h), (width, self.play_h), 1
        )

        # パネル上段：HP / スタミナ / モード を横並びで表示
        f = engine.player.fighter
        y = self.play_h + 6
        x = 8

        hp_surf = self.font.render(f"HP: {f.hp}/{f.max_hp}", True, colors.HP_TEXT)
        screen.blit(hp_surf, (x, y))
        x += hp_surf.get_width() + 20

        # スタミナ（攻撃に足りなければ赤系）
        st_color = colors.STAMINA if f.can_attack() else colors.STAMINA_LOW
        st_surf = self.font.render(f"ST: {f.stamina}/{f.max_stamina}", True, st_color)
        screen.blit(st_surf, (x, y))
        x += st_surf.get_width() + 20

        # 現在のモード
        if engine.attack_mode:
            mode_label, mode_color = "[攻撃モード]", (255, 120, 120)
        else:
            mode_label, mode_color = "[移動モード]", (150, 200, 150)
        screen.blit(self.font.render(mode_label, True, mode_color), (x, y))

        # メッセージログ（HPの下）
        engine.message_log.render(
            screen,
            self.font,
            x=8,
            y=self.play_h + 6 + self.LINE_HEIGHT,
            line_height=self.LINE_HEIGHT,
            max_lines=self.LOG_LINES,
        )

    def _render_game_over(self) -> None:
        screen = self.screen
        text = self.big_font.render("ゲームオーバー", True, colors.PLAYER_DIE)
        rect = text.get_rect(
            center=(self.view_w * TILE_SIZE // 2, self.play_h // 2)
        )
        # 背景を少し暗くして文字を目立たせる
        backdrop = pygame.Surface(text.get_size())
        backdrop.set_alpha(180)
        backdrop.fill((0, 0, 0))
        screen.blit(backdrop, rect.topleft)
        screen.blit(text, rect)
