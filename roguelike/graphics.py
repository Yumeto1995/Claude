"""pygame による描画。タイル画像の読み込み・カメラ追従・下部UI（HP/ログ）を担う。

assets/<key>.png があればそれを使い、無ければ簡単な仮タイルを生成する。
日本語フォントは assets/fonts/game.ttf があれば優先、無ければ macOS のヒラギノを使う。
"""
from __future__ import annotations

import math
import os
import time
from typing import TYPE_CHECKING, Dict

import pygame

import camp
import colors
import item_category
import tile_types
from components.equippable import EquipmentType

if TYPE_CHECKING:
    from engine import Engine

TILE_SIZE = 32  # 1タイルのピクセルサイズ


class AttackAnim:
    """攻撃したエンティティが攻撃方向へスッと踏み込んで戻るモーション。"""

    DURATION = 0.18                 # 再生時間（秒）
    LUNGE = TILE_SIZE * 0.4         # 踏み込む最大ピクセル

    def __init__(self, entity, dx: int, dy: int):
        self.entity = entity
        self.dx = dx
        self.dy = dy
        self.start = time.time()

    def offset(self):
        """現在の描画オフセット (ox, oy)。終了していたら None。"""
        t = (time.time() - self.start) / self.DURATION
        if t >= 1.0:
            return None
        # sin で 0→最大→0 と踏み込んで戻る
        amount = math.sin(t * math.pi) * self.LUNGE
        return (self.dx * amount, self.dy * amount)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# スプライトのキー → 仮タイルの色（assets に PNG が無いとき使う）
PLACEHOLDER_COLORS: Dict[str, tuple] = {
    "floor": (40, 40, 60),
    "safe_floor": (40, 70, 70),
    "wall": (90, 75, 55),
    "player": (255, 255, 255),
    "goblin": (80, 200, 80),
    "slime": (80, 200, 200),
    "corpse": (191, 0, 0),
    "potion": (230, 90, 200),
    "scroll": (230, 220, 140),
    "scroll_confuse": (170, 120, 255),
    "dagger": (200, 200, 210),
    "sword": (230, 230, 245),
    "leather_armor": (160, 110, 60),
    "chain_mail": (150, 160, 180),
    "material": (120, 180, 120),
    "key_item": (240, 210, 90),
    "stairs_down": (120, 220, 255),
    "tent": (90, 170, 90),
    "food": (220, 180, 120),
    "seed": (170, 140, 80),
    "dish": (255, 170, 90),
    # 拠点の設備
    "st_cooking": (235, 130, 70),
    "st_storage": (170, 140, 100),
    "st_alchemy": (150, 110, 210),
    "st_ranch": (200, 160, 110),
    "st_fishery": (90, 150, 210),
    "st_exit": (120, 220, 255),
    "farm_empty": (110, 80, 55),
    "farm_grow": (120, 170, 90),
    "farm_ready": (230, 220, 90),
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

    PANEL_HEIGHT = 178   # 下部パネル（HP/Lv＋ログ）の高さ
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
        # 探索済み（今は見えない）タイル用の暗いバージョン
        self.dark_sprites = {
            key: self._darken(surf) for key, surf in self.sprites.items()
        }
        self.font = load_font(22)        # HP・ログ用
        self.big_font = load_font(48)    # ゲームオーバー用
        self.attack_anims = []           # 再生中の攻撃モーション

    def render(self, engine: "Engine") -> None:
        screen = self.screen
        screen.fill((0, 0, 0))

        # 拠点（テント内）は専用描画
        if engine.in_camp:
            self._render_camp_map(engine)
            self._render_panel(engine)
            if engine.camp_menu is not None:
                self._render_camp_menu(engine)
            pygame.display.flip()
            return

        gm = engine.game_map

        # カメラ：プレイヤー中心。マップ端ではみ出さないようクランプ
        cam_x = max(0, min(engine.player.x - self.view_w // 2, gm.width - self.view_w))
        cam_y = max(0, min(engine.player.y - self.view_h // 2, gm.height - self.view_h))

        # 地形を描画（見えている=明るく / 探索済み=暗く / 未探索=黒）
        for sy in range(self.view_h):
            for sx in range(self.view_w):
                wx, wy = cam_x + sx, cam_y + sy
                if not gm.in_bounds(wx, wy):
                    continue
                sprite_id = gm.tiles["sprite"][wx, wy]
                if sprite_id == tile_types.SPRITE_WALL:
                    key = "wall"
                elif sprite_id == tile_types.SPRITE_DOWNSTAIRS:
                    key = "stairs_down"
                elif gm.safe[wx, wy]:
                    key = "safe_floor"
                else:
                    key = "floor"
                pos = (sx * TILE_SIZE, sy * TILE_SIZE)
                if gm.visible[wx, wy]:
                    screen.blit(self.sprites[key], pos)
                elif gm.explored[wx, wy]:
                    screen.blit(self.dark_sprites[key], pos)
                # 未探索は描かない（黒のまま）

        # 攻撃モーションのオフセットを更新（id(entity) → (ox, oy)）
        offsets = self._update_animations(engine)

        # エンティティを描画（死体→生者の順）。見えているタイルのものだけ。
        for entity in sorted(gm.entities, key=lambda e: e.blocks_movement):
            if not gm.visible[entity.x, entity.y]:
                continue
            ex, ey = entity.x - cam_x, entity.y - cam_y
            if 0 <= ex < self.view_w and 0 <= ey < self.view_h:
                sprite = self.sprites.get(entity.sprite, self.sprites["player"])
                ox, oy = offsets.get(id(entity), (0, 0))
                screen.blit(sprite, (ex * TILE_SIZE + ox, ey * TILE_SIZE + oy))

        self._render_panel(engine)

        if engine.inventory_open:
            self._render_inventory(engine)

        if engine.game_over:
            self._render_game_over()

        pygame.display.flip()

    def _render_camp_map(self, engine: "Engine") -> None:
        """歩けるテント内マップ（地形・設備・区画名・プレイヤー・案内）。"""
        import camp_map

        screen = self.screen
        gm = engine.game_map
        cam_x = max(0, min(engine.player.x - self.view_w // 2, gm.width - self.view_w))
        cam_y = max(0, min(engine.player.y - self.view_h // 2, gm.height - self.view_h))

        for sy in range(self.view_h):
            for sx in range(self.view_w):
                wx, wy = cam_x + sx, cam_y + sy
                if not gm.in_bounds(wx, wy):
                    continue
                key = "wall" if gm.tiles["sprite"][wx, wy] == tile_types.SPRITE_WALL else "floor"
                screen.blit(self.sprites[key], (sx * TILE_SIZE, sy * TILE_SIZE))

        # 設備
        for (wx, wy), kind in camp_map.STATIONS.items():
            spr = self._station_sprite(kind, engine)
            screen.blit(self.sprites[spr], ((wx - cam_x) * TILE_SIZE, (wy - cam_y) * TILE_SIZE))

        # 区画名ラベル
        for text, lx, ly in camp_map.ZONE_LABELS:
            screen.blit(
                self.font.render(text, True, (200, 200, 140)),
                ((lx - cam_x) * TILE_SIZE, (ly - cam_y) * TILE_SIZE),
            )

        # プレイヤー
        screen.blit(
            self.sprites["player"],
            ((engine.player.x - cam_x) * TILE_SIZE, (engine.player.y - cam_y) * TILE_SIZE),
        )

        # 足元の設備案内
        here = camp_map.STATIONS.get((engine.player.x, engine.player.y))
        if here is not None:
            label = camp_map.STATION_LABELS.get(here, here)
            txt = "Enter で " + label
            surf = self.font.render(txt, True, colors.DESCEND)
            screen.blit(surf, (8, self.play_h - 28))

    @staticmethod
    def _station_sprite(kind: str, engine: "Engine") -> str:
        if kind.startswith("farm"):
            plot = engine.farm_plots[int(kind[4:])]
            if plot is None:
                return "farm_empty"
            return "farm_ready" if plot["steps_left"] <= 0 else "farm_grow"
        return "st_" + kind

    def _render_camp_menu(self, engine: "Engine") -> None:
        """設備メニューのオーバーレイ。camp モジュールの状態に従って描く。"""
        screen = self.screen
        w = self.view_w * TILE_SIZE
        h = self.play_h + self.PANEL_HEIGHT

        overlay = pygame.Surface((w, h))
        overlay.set_alpha(232)
        overlay.fill((12, 14, 20))
        screen.blit(overlay, (0, 0))

        x, y = 60, 40
        screen.blit(self.big_font.render(camp.title(engine), True, (255, 230, 120)), (x, y))

        cy = y + 64
        # 補足情報（畑の状態・発見済み料理など）
        for line in camp.info(engine):
            screen.blit(self.font.render(line, True, (175, 180, 190)), (x, cy))
            cy += self.LINE_HEIGHT

        cy += 8
        # 選択肢
        for i, opt in enumerate(camp.options(engine)):
            self._camp_line(
                x, cy + i * self.LINE_HEIGHT,
                opt["text"], i == engine.camp_cursor, opt.get("enabled", True),
            )

        screen.blit(
            self.font.render("↑↓：選択   Enter：決定   ESC：戻る", True, (150, 150, 160)),
            (x, h - 40),
        )

    def _camp_line(self, x: int, y: int, text: str, selected: bool, enabled: bool) -> None:
        cursor = "▶ " if selected else "    "
        if not enabled:
            color = (115, 115, 120)       # 材料不足などで作れない
        elif selected:
            color = (255, 230, 120)
        else:
            color = (220, 220, 230)
        self.screen.blit(self.font.render(cursor + text, True, color), (x, y))

    def _render_inventory(self, engine: "Engine") -> None:
        """持ち物メニューのオーバーレイ（分類タブ付き）。"""
        screen = self.screen
        all_items = engine.player.inventory.items
        current = item_category.ORDER[engine.inventory_category]
        items = item_category.items_in(all_items, current)

        x, y = 24, 24
        width = 540
        height = 92 + max(1, len(items)) * self.LINE_HEIGHT

        box = pygame.Surface((width, height))
        box.set_alpha(235)
        box.fill((15, 15, 25))
        screen.blit(box, (x, y))
        pygame.draw.rect(screen, (120, 120, 150), (x, y, width, height), 2)

        # 分類タブ（現在の分類を強調、各分類の所持数を併記）
        tab_x = x + 14
        for cat in item_category.ORDER:
            count = len(item_category.items_in(all_items, cat))
            label = f"{item_category.LABELS[cat]}({count})"
            color = (255, 230, 120) if cat is current else (130, 130, 145)
            surf = self.font.render(label, True, color)
            screen.blit(surf, (tab_x, y + 10))
            tab_x += surf.get_width() + 14

        # 操作ヒント
        hint = self.font.render(
            "←→：分類切替   a〜：使用/装備   i：閉じる", True, (150, 150, 160)
        )
        screen.blit(hint, (x + 14, y + 10 + self.LINE_HEIGHT))

        # 現在の分類のアイテム一覧
        list_y = y + 14 + self.LINE_HEIGHT * 2
        if not items:
            screen.blit(
                self.font.render("（なし）", True, (160, 160, 160)), (x + 18, list_y)
            )
            return
        equipment = engine.player.equipment
        for i, item in enumerate(items):
            letter = chr(ord("a") + i)
            stat = self._equippable_stat_text(item)
            mark = "  [装備中]" if equipment.item_is_equipped(item) else ""
            line = self.font.render(
                f"{letter}) {item.name}{stat}{mark}", True, (230, 230, 230)
            )
            screen.blit(line, (x + 18, list_y + i * self.LINE_HEIGHT))

    @staticmethod
    def _equippable_stat_text(item) -> str:
        """装備品の性能表示用テキスト（攻+/防+/ST消費）。装備品でなければ空。"""
        eq = item.equippable
        if eq is None:
            return ""
        parts = []
        if eq.power_bonus:
            parts.append(f"攻+{eq.power_bonus}")
        if eq.defense_bonus:
            parts.append(f"防+{eq.defense_bonus}")
        if eq.stamina_cost is not None:
            # 武器=その攻撃の消費、防具=攻撃時の追加消費（+表記）
            if eq.equipment_type == EquipmentType.ARMOR:
                parts.append(f"ST+{eq.stamina_cost}")
            else:
                parts.append(f"ST{eq.stamina_cost}")
        return "  (" + " ".join(parts) + ")" if parts else ""

    @staticmethod
    def _darken(surf: pygame.Surface) -> pygame.Surface:
        """スプライトを暗くしたコピーを返す（探索済みタイルの記憶表示用）。"""
        dark = surf.copy()
        dark.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
        return dark

    def _update_animations(self, engine: "Engine") -> Dict[int, tuple]:
        """engine の予約を取り込み、再生中モーションのオフセットを集計して返す。"""
        for entity, dx, dy in engine.drain_animations():
            self.attack_anims.append(AttackAnim(entity, dx, dy))

        offsets: Dict[int, tuple] = {}
        active = []
        for anim in self.attack_anims:
            off = anim.offset()
            if off is None:
                continue  # 再生終了
            active.append(anim)
            ox, oy = offsets.get(id(anim.entity), (0.0, 0.0))
            offsets[id(anim.entity)] = (ox + off[0], oy + off[1])
        self.attack_anims = active
        return offsets

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

        # スタミナ（攻撃に足りなければ赤系）。括弧内は1回の攻撃で消費する量。
        st_color = colors.STAMINA if f.can_attack() else colors.STAMINA_LOW
        st_surf = self.font.render(
            f"ST: {f.stamina}/{f.max_stamina}(-{f.attack_stamina_cost})", True, st_color
        )
        screen.blit(st_surf, (x, y))
        x += st_surf.get_width() + 20

        # 現在のモード
        if engine.attack_mode:
            mode_label, mode_color = "[攻撃モード]", (255, 120, 120)
        else:
            mode_label, mode_color = "[移動モード]", (150, 200, 150)
        screen.blit(self.font.render(mode_label, True, mode_color), (x, y))

        # 階層表示・文脈ヒント（ダンジョン中のみ。拠点では設備案内を別途出す）
        if not engine.in_camp:
            floor_surf = self.font.render(
                f"地下 {engine.current_floor} 階", True, colors.DESCEND
            )
            screen.blit(floor_surf, (width - floor_surf.get_width() - 10, y))

            hint_text = None
            hint_color = colors.DESCEND
            if (engine.player.x, engine.player.y) == engine.game_map.downstairs_location:
                hint_text = "▼ Enter で次の階へ"
            else:
                foot = engine.item_under_player()
                if foot is not None:
                    hint_text = f"足元: {foot.name}（G で拾う）"
                    hint_color = colors.ITEM
                elif engine.game_map.safe[engine.player.x, engine.player.y]:
                    hint_text = "セーフルーム（テントが使える・敵が入れない）"
                    hint_color = colors.HEAL
            if hint_text:
                hint = self.font.render(hint_text, True, hint_color)
                screen.blit(hint, (width - hint.get_width() - 10, y + self.LINE_HEIGHT))

        # 2段目：レベル・経験値・実効ステータス（装備込み）
        lv = engine.player.level
        lv_surf = self.font.render(
            f"Lv.{lv.current_level}  XP:{lv.current_xp}/{lv.experience_to_next_level}"
            f"   攻撃{f.power} 防御{f.defense}",
            True,
            colors.XP,
        )
        screen.blit(lv_surf, (8, y + self.LINE_HEIGHT))

        # 満腹度（空腹なら赤で警告）＋ 一時バフ（料理効果）
        row1_y = y + self.LINE_HEIGHT
        sx = 8 + lv_surf.get_width() + 24
        if f.max_satiety > 0:
            if f.is_hungry:
                sat_text, sat_color = "空腹！", (255, 80, 80)
            else:
                sat_text = f"満腹:{f.satiety}/{f.max_satiety}"
                sat_color = colors.STAMINA if f.satiety > 20 else colors.STAMINA_LOW
            sat_surf = self.font.render(sat_text, True, sat_color)
            screen.blit(sat_surf, (sx, row1_y))
            sx += sat_surf.get_width() + 20
        for eff in engine.player.status_effects:
            eff_surf = self.font.render(f"{eff.name}({eff.turns})", True, colors.LEVEL_UP)
            screen.blit(eff_surf, (sx, row1_y))
            sx += eff_surf.get_width() + 14

        # メッセージログ（3段目以降）
        engine.message_log.render(
            screen,
            self.font,
            x=8,
            y=self.play_h + 6 + self.LINE_HEIGHT * 2,
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
