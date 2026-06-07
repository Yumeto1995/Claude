"""pygame による描画。タイル画像の読み込みと、カメラ付きの画面描画を担う。

assets/<key>.png があればそれを使い、無ければ簡単な仮タイルを生成する。
絵が用意できたら assets/ に同名 PNG を置くだけで差し替わる。
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict

import pygame

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

# 地形（床・壁）として塗りつぶしで描くキー
TERRAIN_KEYS = {"floor", "wall"}


def _make_placeholder(key: str) -> pygame.Surface:
    """assets に画像が無いキー用の仮タイルを作る。"""
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    color = PLACEHOLDER_COLORS.get(key, (200, 0, 200))
    if key in TERRAIN_KEYS:
        # 地形：塗りつぶし＋薄い枠でタイル境界を見せる
        surf.fill(color)
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    else:
        # キャラ：透明背景に円
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
    """ウィンドウを持ち、カメラ追従でマップとエンティティを描く。"""

    def __init__(self, view_w: int, view_h: int):
        self.view_w = view_w  # 画面に映すタイル数（横）
        self.view_h = view_h  # 画面に映すタイル数（縦）
        self.ui_height = 40   # 下部のHP表示領域
        self.screen = pygame.display.set_mode(
            (view_w * TILE_SIZE, view_h * TILE_SIZE + self.ui_height)
        )
        pygame.display.set_caption("Roguelike")
        self.sprites = load_sprites()
        self.font = pygame.font.SysFont(None, 28)

    def render(self, engine: "Engine") -> None:
        screen = self.screen
        screen.fill((0, 0, 0))
        gm = engine.game_map

        # カメラ：プレイヤーを中心に、マップ端ではみ出さないようクランプ
        cam_x = max(0, min(engine.player.x - self.view_w // 2, gm.width - self.view_w))
        cam_y = max(0, min(engine.player.y - self.view_h // 2, gm.height - self.view_h))

        # 地形（床・壁）を描画
        for sy in range(self.view_h):
            for sx in range(self.view_w):
                wx, wy = cam_x + sx, cam_y + sy
                if not gm.in_bounds(wx, wy):
                    continue
                sprite_id = gm.tiles["sprite"][wx, wy]
                key = "wall" if sprite_id == tile_types.SPRITE_WALL else "floor"
                screen.blit(self.sprites[key], (sx * TILE_SIZE, sy * TILE_SIZE))

        # エンティティを描画（死体→生者の順で重なりを正す）
        for entity in sorted(gm.entities, key=lambda e: e.blocks_movement):
            ex, ey = entity.x - cam_x, entity.y - cam_y
            if 0 <= ex < self.view_w and 0 <= ey < self.view_h:
                sprite = self.sprites.get(entity.sprite, self.sprites["player"])
                screen.blit(sprite, (ex * TILE_SIZE, ey * TILE_SIZE))

        # 下部にHP表示（日本語フォント未導入のため当面ASCII）
        f = engine.player.fighter
        hp_surf = self.font.render(
            f"HP: {f.hp}/{f.max_hp}", True, (255, 255, 255)
        )
        screen.blit(hp_surf, (8, self.view_h * TILE_SIZE + 8))
        if engine.game_over:
            go_surf = self.font.render(
                "YOU DIED - press ESC", True, (255, 80, 80)
            )
            screen.blit(go_surf, (180, self.view_h * TILE_SIZE + 8))

        pygame.display.flip()
