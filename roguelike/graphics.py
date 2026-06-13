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

TILE_SIZE = 64  # 1タイルのピクセルサイズ（高精細化のため拡大）


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


# 歩行の滑り込みは MoveAnim ではなく Renderer の位置スムージング（render_pos）で
# 行う。離散スライドだと移動発火のタイミングずれで各マスに微小な静止が生じ
# カクついたため、毎フレーム目標へ寄せる方式に変更した。


class _TimedFx:
    """寿命付き視覚エフェクトの共通基底。progress() が 0→1、終了で None。"""

    DURATION = 0.2

    def __init__(self):
        self.start = time.time()

    def progress(self):
        t = (time.time() - self.start) / self.DURATION
        return None if t >= 1.0 else t


class SlashAnim(_TimedFx):
    """攻撃先タイルを白い斬撃線が走り抜けるエフェクト。"""

    DURATION = 0.16

    def __init__(self, x: int, y: int, dx: int, dy: int):
        super().__init__()
        self.x = x
        self.y = y
        norm = math.hypot(dx, dy) or 1.0
        self.ux, self.uy = dx / norm, dy / norm  # 攻撃方向の単位ベクトル


class FlashAnim(_TimedFx):
    """被弾したエンティティが一瞬白く光るエフェクト。"""

    DURATION = 0.15

    def __init__(self, entity):
        super().__init__()
        self.entity = entity


class PopupAnim(_TimedFx):
    """ダメージ数字がふわっと浮かんで消えるエフェクト。"""

    DURATION = 0.6
    RISE = 18  # 浮き上がる高さ(px)

    def __init__(self, x: int, y: int, text: str, color: tuple):
        super().__init__()
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.surf = None  # 初回描画時にレンダリングしてキャッシュ


ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# スプライトのキー → 仮タイルの色（assets に PNG が無いとき使う）
PLACEHOLDER_COLORS: Dict[str, tuple] = {
    "floor": (40, 40, 60),
    "safe_floor": (40, 70, 70),
    "wall": (90, 75, 55),
    "player": (255, 255, 255),
    "npc": (240, 220, 150),
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

# 日本語フォントの探索候補（上から順に試す）。
# 同梱の PixelMplus（ドット絵調・M+ライセンス）を最優先。
# PixelMplus10 は10の倍数、PixelMplus12 は12の倍数のサイズで使うとドットが揃う。
# 漢字の可読性が高い 12px 設計を本文に使う（24px = きっちり2倍表示）。
_FONT_CANDIDATES = [
    os.path.join(ASSETS_DIR, "fonts", "game.ttf"),  # 任意の差し替え用（最優先）
    os.path.join(ASSETS_DIR, "fonts", "PixelMplus12-Regular.ttf"),
    os.path.join(ASSETS_DIR, "fonts", "PixelMplus10-Regular.ttf"),
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """日本語が出せるフォントを読み込む。見つからなければ既定フォント。

    bold=True は太字のピクセルフォントを探す（サイズに応じて
    12px系/10px系のうちドットが揃う方を選ぶ）。
    """
    candidates = list(_FONT_CANDIDATES)
    if bold:
        name = "PixelMplus12-Bold.ttf" if size % 12 == 0 else "PixelMplus10-Bold.ttf"
        candidates.insert(0, os.path.join(ASSETS_DIR, "fonts", name))
    for path in candidates:
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


# キャラの追加ポーズ。あれば自動で読み込み、描画側が状況に応じて差し替える。
#   _attack = 攻撃モーション中 / _walk1,_walk2 = 移動中に交互表示（歩行）
SPRITE_VARIANTS = ("_attack", "_walk1", "_walk2")


def load_sprites() -> Dict[str, pygame.Surface]:
    """全スプライトを読み込む。PNG が無ければ仮タイルで代用。

    `<キー>.png` に加え、あれば `<キー>_attack/_walk1/_walk2.png` も読む。
    32px 原寸の地形・アイテムは TILE_SIZE への整数倍拡大でくっきり表示される。
    """
    sprites: Dict[str, pygame.Surface] = {}
    for key in PLACEHOLDER_COLORS:
        path = os.path.join(ASSETS_DIR, f"{key}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            sprites[key] = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
        else:
            sprites[key] = _make_placeholder(key)
        for suf in SPRITE_VARIANTS:
            vpath = os.path.join(ASSETS_DIR, f"{key}{suf}.png")
            if os.path.exists(vpath):
                img = pygame.image.load(vpath).convert_alpha()
                sprites[f"{key}{suf}"] = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
    return sprites


class Renderer:
    """ウィンドウを持ち、カメラ追従でマップ・エンティティ・下部UIを描く。"""

    PANEL_HEIGHT = 192   # 下部パネル（HP/Lv＋ログ）の高さ
    LOG_LINES = 4        # ログの表示行数
    LINE_HEIGHT = 28

    def __init__(self, view_w: int, view_h: int):
        self.view_w = view_w
        self.view_h = view_h
        self.play_h = view_h * TILE_SIZE  # マップ表示領域の高さ
        size = (view_w * TILE_SIZE, self.play_h + self.PANEL_HEIGHT)
        # SCALED：論理サイズを保ちつつウィンドウ/全画面に自動スケール（F11でトグル）
        try:
            self.screen = pygame.display.set_mode(size, pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode(size)
        pygame.display.set_caption("Roguelike")
        self.sprites = load_sprites()
        # 探索済み（今は見えない）タイル用の暗いバージョン
        self.dark_sprites = {
            key: self._darken(surf) for key, surf in self.sprites.items()
        }
        self.font = load_font(24)              # 本文（PixelMplus12 ×2倍）
        self.font_bold = load_font(24, bold=True)   # 見出し・ラベル
        self.big_font = load_font(48, bold=True)    # タイトル・ゲームオーバー
        self.anims = []                  # 再生中の攻撃モーション（踏み込み）
        self.fx = []                     # 再生中のエフェクト（斬撃・フラッシュ・数字）
        self.flash = {}                  # id(entity) → 被弾フラッシュの強度(0〜1)
        self.attacking = set()           # 攻撃モーション再生中のエンティティ id
        self.attack_off = {}             # id(entity) → 攻撃踏み込みのオフセット(px)
        # 位置スムージング：各エンティティの「描画ピクセル位置」を毎フレーム
        # 目標タイルへ滑らかに寄せる。これでカメラもキャラもカクつかず流れる。
        self.render_pos = {}             # id(entity) → [px, py]（ワールド座標・左上）
        self.last_tile = {}              # id(entity) → (tx, ty) 直近のタイル（歩数判定）
        self.step_t0 = {}                # id(entity) → そのマスに踏み出した時刻
        self.walking = set()             # 目標へ移動中のエンティティ id（脚アニメ用）
        self.walk_step = {}              # id(entity) → 歩数（walk1/walk2 の交互判定）
        self.now = 0.0                   # 現在時刻（_update_animations で更新）
        self._last_frame_t = None        # 前フレームの時刻（dt 計算用）

    CONTROLS = [
        "移動：矢印 / WASD / vi / テンキー（斜め・2方向同時可）",
        "Z：足踏み　Space：移動/攻撃モード切替",
        "G：拾う　i：持ち物（←→分類 ↑↓選択 Enter使用）",
        "Enter / >：下り階段で次の階へ",
        "セーフルームで『魔法のテント』→拠点（料理・畑・牧場）",
        "F5：セーブ　F9：ロード　F11：全画面",
        "ESC：タイトルへ戻る（自動セーブ）",
    ]

    # ===== UI 共通部品（ウィンドウ枠・文字影・ゲージ） =====

    FRAME_LIGHT = (211, 198, 156)  # 窓枠の明色（真鍮風）
    FRAME_DARK = (110, 96, 66)     # 窓枠の暗色
    WINDOW_BG = (15, 17, 28)       # ウィンドウの地色
    TEXT_MAIN = (228, 228, 235)    # 本文
    TEXT_DIM = (148, 150, 168)     # 補足・ヒント
    TEXT_GOLD = (252, 226, 120)    # 強調・選択中

    def _draw_window(self, x: int, y: int, w: int, h: int, alpha: int = 240) -> None:
        """市販RPG風の装飾枠ウィンドウ（黒縁→明枠→暗ライン＋四隅飾り）。"""
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((*self.WINDOW_BG, alpha))
        # 地のグラデーション（上1/3 をわずかに明るく）
        pygame.draw.rect(box, (24, 27, 42, alpha), (3, 3, w - 6, max(8, h // 3)))
        # 三重の枠
        pygame.draw.rect(box, (0, 0, 0, 255), (0, 0, w, h), 1)
        pygame.draw.rect(box, (*self.FRAME_LIGHT, 255), (1, 1, w - 2, h - 2), 2)
        pygame.draw.rect(box, (*self.FRAME_DARK, 255), (3, 3, w - 6, h - 6), 1)
        # 四隅の飾り鋲
        for cx in (3, w - 7):
            for cy in (3, h - 7):
                pygame.draw.rect(box, (*self.FRAME_LIGHT, 255), (cx, cy, 4, 4))
                pygame.draw.rect(box, (0, 0, 0, 255), (cx, cy, 4, 4), 1)
        self.screen.blit(box, (x, y))

    def _text(self, text: str, x: int, y: int, color=None, bold: bool = False,
              shadow: bool = True) -> int:
        """影付きでテキストを描き、描いた幅を返す（ドット絵らしい固い影）。"""
        font = self.font_bold if bold else self.font
        if color is None:
            color = self.TEXT_MAIN
        if shadow:
            self.screen.blit(font.render(text, True, (6, 6, 10)), (x + 2, y + 2))
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))
        return surf.get_width()

    def _draw_gauge(self, x: int, y: int, w: int, h: int, ratio: float,
                    color: tuple) -> None:
        """枠付きゲージ。上下に明暗を入れて立体感を出す。"""
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(self.screen, (0, 0, 0), (x, y, w, h))
        pygame.draw.rect(self.screen, (46, 48, 60), (x + 1, y + 1, w - 2, h - 2))
        fill = int((w - 4) * ratio)
        if fill > 0:
            light = tuple(min(255, c + 70) for c in color)
            dark = tuple(max(0, c - 70) for c in color)
            pygame.draw.rect(self.screen, color, (x + 2, y + 2, fill, h - 4))
            pygame.draw.rect(self.screen, light, (x + 2, y + 2, fill, 2))
            pygame.draw.rect(self.screen, dark, (x + 2, y + h - 4, fill, 2))

    def _draw_chip(self, text: str, x: int, y: int, color, right_align: bool = False) -> int:
        """小さな縁取りチップ（モード表示・階数表示など）。幅を返す。"""
        surf = self.font.render(text, True, color)
        w, h = surf.get_width() + 14, surf.get_height() + 6
        if right_align:
            x -= w
        chip = pygame.Surface((w, h), pygame.SRCALPHA)
        chip.fill((10, 11, 18, 215))
        pygame.draw.rect(chip, (0, 0, 0, 255), (0, 0, w, h), 1)
        dim = tuple(max(0, c - 110) for c in color)
        pygame.draw.rect(chip, (*dim, 255), (1, 1, w - 2, h - 2), 1)
        self.screen.blit(chip, (x, y))
        self.screen.blit(surf, (x + 7, y + 3))
        return w

    def render_title(self, options, cursor: int) -> None:
        """タイトル画面（ロゴ＋メニューウィンドウ＋操作説明）。"""
        screen = self.screen
        w = self.view_w * TILE_SIZE
        h = self.play_h + self.PANEL_HEIGHT

        # 夜空風の縦グラデーション背景
        band = 4
        for i in range(h // band + 1):
            t = i / (h // band)
            color = (int(7 + 9 * t), int(8 + 12 * t), int(14 + 22 * t))
            pygame.draw.rect(screen, color, (0, i * band, w, band))

        # タイトルロゴ（固い影＋金色＋飾り罫）
        title = "ローグライク"
        tw = self.big_font.size(title)[0]
        tx, ty = (w - tw) // 2, 56
        screen.blit(self.big_font.render(title, True, (6, 6, 10)), (tx + 4, ty + 4))
        screen.blit(self.big_font.render(title, True, self.TEXT_GOLD), (tx, ty))
        line_y = ty + 60
        pygame.draw.line(screen, self.FRAME_LIGHT,
                         (w // 2 - 190, line_y), (w // 2 + 190, line_y), 2)
        for dx in (-190, 190):  # 罫の両端の飾り
            pygame.draw.rect(screen, self.FRAME_LIGHT, (w // 2 + dx - 3, line_y - 3, 6, 6))
        sub = "- ダンジョンと拠点づくり -"
        self._text(sub, (w - self.font.size(sub)[0]) // 2, line_y + 12,
                   color=self.TEXT_DIM, shadow=False)

        # メニューウィンドウ
        mw = 340
        mh = 26 + len(options) * 40 + 12
        mx, my = (w - mw) // 2, 176
        self._draw_window(mx, my, mw, mh)
        for i, opt in enumerate(options):
            oy = my + 20 + i * 40
            if i == cursor:
                pygame.draw.rect(screen, (46, 52, 86), (mx + 8, oy - 5, mw - 16, 34))
                pygame.draw.rect(screen, (104, 112, 168), (mx + 8, oy - 5, mw - 16, 34), 1)
                pygame.draw.rect(screen, self.TEXT_GOLD, (mx + 8, oy - 5, 3, 34))
                self._text("▶", mx + 22, oy, color=self.TEXT_GOLD, bold=True)
            color = self.TEXT_GOLD if i == cursor else self.TEXT_MAIN
            self._text(opt, mx + 56, oy, color=color, bold=(i == cursor))

        # 操作説明ウィンドウ
        cw = 680
        ch = 40 + len(self.CONTROLS) * 28 + 10
        cx, cy = (w - cw) // 2, my + mh + 16
        self._draw_window(cx, cy, cw, ch, alpha=215)
        self._text("操作説明", cx + 16, cy + 8, color=self.FRAME_LIGHT, bold=True)
        pygame.draw.line(screen, self.FRAME_DARK,
                         (cx + 12, cy + 36), (cx + cw - 12, cy + 36), 1)
        for i, line in enumerate(self.CONTROLS):
            self._text(line, cx + 16, cy + 44 + i * 28, color=self.TEXT_DIM, shadow=False)

        pygame.display.flip()

    def _camera_px(self, engine: "Engine") -> tuple:
        """プレイヤーのスムージング済み位置にピクセル単位で追従するカメラ。

        返り値はビュー左上のワールドピクセル座標 (cam_x, cam_y)。
        タイル整数ではなくピクセルで動かすので、世界がカクつかず滑らかにスクロールする。
        攻撃の踏み込みはカメラに含めない（画面が揺れないように）。マップ端でクランプ。
        """
        p = engine.player
        px, py = self.render_pos.get(id(p), (p.x * TILE_SIZE, p.y * TILE_SIZE))
        gm = engine.game_map
        vw, vh = self.view_w * TILE_SIZE, self.view_h * TILE_SIZE
        cam_x = px + TILE_SIZE / 2 - vw / 2
        cam_y = py + TILE_SIZE / 2 - vh / 2
        cam_x = max(0.0, min(cam_x, gm.width * TILE_SIZE - vw))
        cam_y = max(0.0, min(cam_y, gm.height * TILE_SIZE - vh))
        return cam_x, cam_y

    def _draw_terrain(self, gm, cam_x: float, cam_y: float, surf_of) -> None:
        """ピクセルカメラに合わせて地形タイルを敷き詰める。

        surf_of(tx, ty) が描くべき Surface（None ならスキップ）を返す。
        端の欠けを防ぐためビューより1タイル広く回す。
        """
        screen = self.screen
        tx0, ty0 = int(cam_x // TILE_SIZE), int(cam_y // TILE_SIZE)
        for ty in range(ty0, ty0 + self.view_h + 2):
            for tx in range(tx0, tx0 + self.view_w + 2):
                if not gm.in_bounds(tx, ty):
                    continue
                surf = surf_of(tx, ty)
                if surf is not None:
                    screen.blit(surf, (tx * TILE_SIZE - cam_x, ty * TILE_SIZE - cam_y))

    def render(self, engine: "Engine") -> None:
        screen = self.screen
        screen.fill((0, 0, 0))

        # 村は専用描画
        if getattr(engine, "in_village", False):
            self._render_village_map(engine)
            self._render_panel(engine)
            if getattr(engine, "dialogue", None) is not None:
                self._render_dialogue(engine)
            pygame.display.flip()
            return

        # 拠点（テント内）は専用描画
        if engine.in_camp:
            self._render_camp_map(engine)
            self._render_panel(engine)
            if engine.camp_menu is not None:
                self._render_camp_menu(engine)
            pygame.display.flip()
            return

        gm = engine.game_map

        # 位置スムージングを更新し、ピクセル単位カメラでプレイヤーに滑らかに追従
        self._update_animations(engine)
        cam_x, cam_y = self._camera_px(engine)

        # 地形を描画（見えている=明るく / 探索済み=暗く / 未探索=黒）
        def terrain(tx, ty):
            sid = gm.tiles["sprite"][tx, ty]
            if sid == tile_types.SPRITE_WALL:
                key = "wall"
            elif sid == tile_types.SPRITE_DOWNSTAIRS:
                key = "stairs_down"
            elif gm.safe[tx, ty]:
                key = "safe_floor"
            else:
                key = "floor"
            if gm.visible[tx, ty]:
                return self.sprites[key]
            if gm.explored[tx, ty]:
                return self.dark_sprites[key]
            return None  # 未探索は描かない
        self._draw_terrain(gm, cam_x, cam_y, terrain)

        # エンティティを描画（死体→生者の順）。見えているタイルのものだけ。
        vw, vh = self.view_w * TILE_SIZE, self.view_h * TILE_SIZE
        for entity in sorted(gm.entities, key=lambda e: e.blocks_movement):
            if not gm.visible[entity.x, entity.y]:
                continue
            sx, sy = self._entity_screen(entity, cam_x, cam_y)
            if -TILE_SIZE < sx < vw and -TILE_SIZE < sy < vh:
                # 攻撃ポーズ・歩行コマ・通常を状況で切り替える
                sprite = self.sprites.get(
                    self._sprite_key_for(entity), self.sprites["player"]
                )
                flash = self.flash.get(id(entity), 0.0)
                if flash > 0.0:
                    sprite = self._whiten(sprite, flash)  # 被弾フラッシュ
                if entity.blocks_movement:  # 生きたキャラには足元影
                    self._draw_shadow(sx, sy)
                screen.blit(sprite, (sx, sy))

        # 斬撃・ダメージ数字はエンティティの上に重ねる
        self._draw_fx(engine, cam_x, cam_y)

        # セーフルームにいるときは画面右上に表示
        if engine.game_map.safe[engine.player.x, engine.player.y]:
            self._draw_chip("セーフルーム", self.view_w * TILE_SIZE - 8, 8,
                            colors.HEAL, right_align=True)

        self._render_panel(engine)

        if engine.inventory_open:
            self._render_inventory(engine)

        if engine.game_over:
            self._render_game_over()

        pygame.display.flip()

    def _render_village_map(self, engine: "Engine") -> None:
        """村マップ（地形・NPC・入口・看板・プレイヤー・案内）。"""
        import village_map

        screen = self.screen
        gm = engine.game_map
        self._update_animations(engine)
        cam_x, cam_y = self._camera_px(engine)

        def terrain(tx, ty):
            sid = gm.tiles["sprite"][tx, ty]
            if sid == tile_types.SPRITE_WALL:
                return self.sprites["wall"]
            if sid == tile_types.SPRITE_DOWNSTAIRS:
                return self.sprites["stairs_down"]
            return self.sprites["floor"]
        self._draw_terrain(gm, cam_x, cam_y, terrain)

        # 看板（区画名）
        for text, lx, ly in village_map.LABELS:
            self._text(text, lx * TILE_SIZE - cam_x, ly * TILE_SIZE - cam_y,
                       color=(214, 206, 156), bold=True)

        # エンティティ（NPC→プレイヤーの順）。スムージング位置で描く。
        vw, vh = self.view_w * TILE_SIZE, self.view_h * TILE_SIZE
        for ent in sorted(gm.entities, key=lambda e: e is engine.player):
            sx, sy = self._entity_screen(ent, cam_x, cam_y)
            if -TILE_SIZE < sx < vw and -TILE_SIZE < sy < vh:
                spr = self.sprites.get(self._sprite_key_for(ent), self.sprites["player"])
                self._draw_shadow(sx, sy)
                screen.blit(spr, (sx, sy))

        # 足元/隣の案内
        px, py = engine.player.x, engine.player.y
        hint = None
        if (px, py) == village_map.DUNGEON_ENTRANCE:
            hint = "Enter で ダンジョンへ"
        else:
            for ent in gm.entities:
                if getattr(ent, "dialogue", None) and max(abs(ent.x - px), abs(ent.y - py)) == 1:
                    hint = f"Enter で {ent.name} と話す"
                    break
        if hint:
            self._draw_chip(hint, 8, self.play_h - 36, colors.DESCEND)

    def _render_dialogue(self, engine: "Engine") -> None:
        """会話ウィンドウ（名前プレートが枠に重なる市販RPG風）。"""
        d = engine.dialogue
        w = self.view_w * TILE_SIZE
        bx, bw = 20, w - 40
        bh = 30 + len(d["lines"]) * 28 + 42
        by = self.play_h - bh - 14

        self._draw_window(bx, by, bw, bh)
        # 名前プレート（本体の枠に少し重ねる）
        plate_w = self.font_bold.size(d["name"])[0] + 30
        self._draw_window(bx + 14, by - 19, plate_w, 36, alpha=255)
        self._text(d["name"], bx + 29, by - 13, color=self.TEXT_GOLD, bold=True)

        for i, line in enumerate(d["lines"]):
            self._text(line, bx + 22, by + 26 + i * 28)
        tip = "Enter で閉じる"
        self._text(tip, bx + bw - self.font.size(tip)[0] - 16, by + bh - 30,
                   color=self.TEXT_DIM, shadow=False)

    def _render_camp_map(self, engine: "Engine") -> None:
        """歩けるテント内マップ（地形・設備・区画名・プレイヤー・案内）。"""
        import camp_map

        screen = self.screen
        gm = engine.game_map
        self._update_animations(engine)
        cam_x, cam_y = self._camera_px(engine)

        def terrain(tx, ty):
            key = "wall" if gm.tiles["sprite"][tx, ty] == tile_types.SPRITE_WALL else "floor"
            return self.sprites[key]
        self._draw_terrain(gm, cam_x, cam_y, terrain)

        # 設備
        for (wx, wy), kind in camp_map.STATIONS.items():
            spr = self._station_sprite(kind, engine)
            screen.blit(self.sprites[spr], (wx * TILE_SIZE - cam_x, wy * TILE_SIZE - cam_y))

        # 区画名ラベル
        for text, lx, ly in camp_map.ZONE_LABELS:
            self._text(text, lx * TILE_SIZE - cam_x, ly * TILE_SIZE - cam_y,
                       color=(206, 204, 146), bold=True)

        # プレイヤー（スムージング位置で描く）
        ppx, ppy = self._entity_screen(engine.player, cam_x, cam_y)
        self._draw_shadow(ppx, ppy)
        screen.blit(
            self.sprites.get(self._sprite_key_for(engine.player), self.sprites["player"]),
            (ppx, ppy),
        )

        # 足元の設備案内（設備メニューを開いている間は出さない）
        here = camp_map.STATIONS.get((engine.player.x, engine.player.y))
        if here is not None and engine.camp_menu is None:
            label = camp_map.STATION_LABELS.get(here, here)
            self._draw_chip("Enter で " + label, 8, self.play_h - 36, colors.DESCEND)

    @staticmethod
    def _station_sprite(kind: str, engine: "Engine") -> str:
        if kind.startswith("farm"):
            plot = engine.farm_plots[int(kind[4:])]
            if plot is None:
                return "farm_empty"
            return "farm_ready" if plot["steps_left"] <= 0 else "farm_grow"
        return "st_" + kind

    def _render_camp_menu(self, engine: "Engine") -> None:
        """設備メニュー：全画面を暗くして大きな装飾ウィンドウに表示する。"""
        screen = self.screen
        w = self.view_w * TILE_SIZE
        h = self.play_h + self.PANEL_HEIGHT

        overlay = pygame.Surface((w, h))
        overlay.set_alpha(170)
        overlay.fill((4, 5, 9))
        screen.blit(overlay, (0, 0))

        wx, wy = 44, 26
        ww, wh = w - 88, h - 52
        self._draw_window(wx, wy, ww, wh)

        x, y = wx + 22, wy + 14
        self._text(camp.title(engine), x, y, color=self.TEXT_GOLD, bold=True)
        pygame.draw.line(screen, self.FRAME_DARK,
                         (wx + 14, y + 34), (wx + ww - 14, y + 34), 1)

        cy = y + 46
        # 補足情報（畑の状態・発見済み料理など）
        for line in camp.info(engine):
            self._text(line, x, cy, color=self.TEXT_DIM, shadow=False)
            cy += self.LINE_HEIGHT

        cy += 8
        # 選択肢（選択中はハイライトバー）
        for i, opt in enumerate(camp.options(engine)):
            self._camp_line(
                wx, ww, x, cy + i * self.LINE_HEIGHT,
                opt["text"], i == engine.camp_cursor, opt.get("enabled", True),
            )

        self._text("↑↓：選択　Enter：決定　ESC：戻る",
                   x, wy + wh - 36, color=self.TEXT_DIM, shadow=False)

    def _camp_line(self, wx: int, ww: int, x: int, y: int,
                   text: str, selected: bool, enabled: bool) -> None:
        if selected:
            pygame.draw.rect(self.screen, (46, 52, 86), (wx + 10, y - 3, ww - 20, self.LINE_HEIGHT))
            pygame.draw.rect(self.screen, (104, 112, 168), (wx + 10, y - 3, ww - 20, self.LINE_HEIGHT), 1)
            pygame.draw.rect(self.screen, self.TEXT_GOLD, (wx + 10, y - 3, 3, self.LINE_HEIGHT))
            self._text("▶", x, y, color=self.TEXT_GOLD, bold=True)
        if not enabled:
            color = (110, 110, 118)       # 材料不足などで作れない
        elif selected:
            color = self.TEXT_GOLD
        else:
            color = self.TEXT_MAIN
        self._text(text, x + 30, y, color=color, shadow=selected)

    ROW_H = 36  # 持ち物1行の高さ（32pxアイコン＋余白）

    def _render_inventory(self, engine: "Engine") -> None:
        """持ち物メニュー：装飾枠＋分類タブ＋アイコン付き一覧。"""
        screen = self.screen
        all_items = engine.player.inventory.items
        current = item_category.ORDER[engine.inventory_category]
        items = item_category.items_in(all_items, current)

        x, y = 24, 20
        width = 706
        header_h = 86
        height = header_h + max(1, len(items)) * self.ROW_H + 44
        self._draw_window(x, y, width, height)

        # タイトル行：見出し＋所持数
        self._text("持ち物", x + 18, y + 10, color=self.TEXT_GOLD, bold=True)
        self._text(f"{len(all_items)} / {engine.player.inventory.capacity}",
                   x + 122, y + 10, color=self.TEXT_DIM)

        # 分類タブ（選択中は明るい箱＋金文字）
        tab_x = x + 12
        tab_y = y + 48
        for cat in item_category.ORDER:
            count = len(item_category.items_in(all_items, cat))
            label = f"{item_category.LABELS[cat]} {count}"
            tw = self.font.size(label)[0] + 18
            active = cat is current
            if active:
                pygame.draw.rect(screen, (52, 58, 92), (tab_x, tab_y - 5, tw, 34))
                pygame.draw.rect(screen, self.FRAME_LIGHT, (tab_x, tab_y - 5, tw, 34), 1)
            else:
                pygame.draw.rect(screen, (24, 26, 40), (tab_x, tab_y - 5, tw, 34))
                pygame.draw.rect(screen, (58, 60, 78), (tab_x, tab_y - 5, tw, 34), 1)
            self._text(label, tab_x + 9, tab_y,
                       color=self.TEXT_GOLD if active else self.TEXT_DIM, shadow=active)
            tab_x += tw + 6

        # アイテム一覧（アイコン＋名前＋性能＋装備中バッジ）
        list_y = y + header_h
        if not items:
            self._text("（なし）", x + 26, list_y + 6, color=self.TEXT_DIM)
        else:
            equipment = engine.player.equipment
            cursor = min(engine.inventory_cursor, len(items) - 1)
            for i, item in enumerate(items):
                row_y = list_y + i * self.ROW_H
                if i == cursor:
                    pygame.draw.rect(screen, (46, 52, 86),
                                     (x + 8, row_y, width - 16, self.ROW_H))
                    pygame.draw.rect(screen, (104, 112, 168),
                                     (x + 8, row_y, width - 16, self.ROW_H), 1)
                    pygame.draw.rect(screen, self.TEXT_GOLD, (x + 8, row_y, 3, self.ROW_H))
                icon = self.sprites.get(item.sprite)
                if icon is not None:
                    screen.blit(icon, (x + 20, row_y + (self.ROW_H - TILE_SIZE) // 2))
                name_color = self.TEXT_GOLD if i == cursor else self.TEXT_MAIN
                self._text(item.name, x + 62, row_y + 7, color=name_color)
                # 右端：装備中バッジ → 性能（控えめ色）の順に右詰め
                right = x + width - 16
                if equipment.item_is_equipped(item):
                    right -= self._draw_chip("装備中", right, row_y + 4,
                                             self.TEXT_GOLD, right_align=True) + 10
                stat = self._equippable_stat_text(item).strip()
                if stat:
                    sw = self.font.size(stat)[0]
                    self._text(stat, right - sw, row_y + 7,
                               color=self.TEXT_DIM, shadow=False)

        # フッター：操作ヒント
        fy = y + height - 32
        pygame.draw.line(screen, self.FRAME_DARK, (x + 10, fy - 4), (x + width - 10, fy - 4), 1)
        self._text("←→：分類　↑↓：選択　Enter：使用/装備　i：閉じる",
                   x + 18, fy, color=self.TEXT_DIM, shadow=False)

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

    # 1歩(1マス)の中の脚サイクル：踏み出し→足をそろえる(passing)。
    # これを毎マス交互の足で繰り返すと「右足・左足」の歩行に見える。
    STEP_DT = 0.13   # 1歩の見かけ時間(秒)。踏み出し時刻からの経過で位相を取る
    PASS_AT = 0.6    # 位相がこの割合を超えたら passing（足をそろえる）に切替

    def _sprite_key_for(self, entity) -> str:
        """状況に応じたスプライトキーを返す（攻撃ポーズ＞歩行コマ＞通常）。"""
        key = entity.sprite
        eid = id(entity)
        if eid in self.attacking and f"{key}_attack" in self.sprites:
            return f"{key}_attack"
        if eid in self.walking:
            # 踏み出してからの経過で位相を取り、前半=踏み出し / 後半=足そろえ
            phase = (self.now - self.step_t0.get(eid, self.now)) / self.STEP_DT
            if phase < self.PASS_AT:
                stride = "_walk1" if self.walk_step.get(eid, 0) % 2 == 0 else "_walk2"
                if f"{key}{stride}" in self.sprites:
                    return f"{key}{stride}"
        return key

    def _draw_shadow(self, px: float, py: float) -> None:
        """キャラの足元に落ちる楕円影（接地感を出す）。"""
        sh = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 78),
                            (5, TILE_SIZE - 9, TILE_SIZE - 10, 7))
        self.screen.blit(sh, (px, py))

    @staticmethod
    def _whiten(surf: pygame.Surface, intensity: float) -> pygame.Surface:
        """スプライトを白寄りに光らせたコピーを返す（被弾フラッシュ用）。"""
        bright = surf.copy()
        v = int(200 * intensity)
        bright.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        return bright

    @staticmethod
    def _darken(surf: pygame.Surface) -> pygame.Surface:
        """スプライトを暗くしたコピーを返す（探索済みタイルの記憶表示用）。"""
        dark = surf.copy()
        dark.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
        return dark

    # 位置スムージングの係数。
    SMOOTH_TAU = 0.045   # 目標へ寄る時定数(秒)。小さいほど機敏、大きいほどぬるっと
    SNAP_DIST = TILE_SIZE * 1.6  # これ以上離れていたら瞬間移動とみなしスナップ

    def _update_animations(self, engine: "Engine") -> None:
        """毎フレーム呼ぶ。描画位置を目標へ滑らかに寄せ、攻撃/エフェクトも更新する。

        従来の「1マス＝1スライド」方式は移動発火のタイミングずれで各マスに
        微小な静止フレームが生じカクついた。ここでは離散スライドをやめ、
        render_pos を毎フレーム指数関数的に目標へ近づける（=途切れない動き）。
        """
        now = time.time()
        self.now = now
        dt = 0.0 if self._last_frame_t is None else now - self._last_frame_t
        self._last_frame_t = now
        dt = min(0.1, max(0.0, dt))
        alpha = 1.0 - math.exp(-dt / self.SMOOTH_TAU) if dt > 0 else 0.0

        # 攻撃モーション・エフェクトの取り込み（移動予約は位置追従で扱うので捨てる）
        for entity, dx, dy in engine.drain_animations():
            self.anims.append(AttackAnim(entity, dx, dy))
        engine.drain_moves()
        for fx in engine.drain_fx():
            kind = fx[0]
            if kind == "slash":
                self.fx.append(SlashAnim(*fx[1:]))
            elif kind == "flash":
                self.fx.append(FlashAnim(fx[1]))
            elif kind == "popup":
                self.fx.append(PopupAnim(*fx[1:]))

        # --- 位置スムージング：各エンティティの描画位置を目標タイルへ寄せる ---
        ents = list(engine.game_map.entities)
        if engine.player not in ents:
            ents.append(engine.player)
        self.walking = set()
        live = set()
        for ent in ents:
            eid = id(ent)
            live.add(eid)
            tx, ty = ent.x * TILE_SIZE, ent.y * TILE_SIZE
            cur = self.render_pos.get(eid)
            if (cur is None or abs(cur[0] - tx) > self.SNAP_DIST
                    or abs(cur[1] - ty) > self.SNAP_DIST):
                self.render_pos[eid] = [float(tx), float(ty)]   # 初期/瞬間移動はスナップ
            else:
                cur[0] += (tx - cur[0]) * alpha
                cur[1] += (ty - cur[1]) * alpha
                if abs(cur[0] - tx) > 1.0 or abs(cur[1] - ty) > 1.0:
                    self.walking.add(eid)
                else:                                           # 十分近ければ吸着
                    cur[0], cur[1] = float(tx), float(ty)
            # タイルが変わった瞬間に歩数++＆踏み出し時刻を記録（左右の足を交互に）
            if self.last_tile.get(eid) != (ent.x, ent.y):
                if eid in self.last_tile:
                    self.walk_step[eid] = self.walk_step.get(eid, 0) + 1
                    self.step_t0[eid] = now
                self.last_tile[eid] = (ent.x, ent.y)

        # 退場したエンティティ（フロア移動で入れ替わる敵など）の記録を掃除
        for d in (self.render_pos, self.last_tile, self.step_t0, self.walk_step):
            for k in [k for k in d if k not in live]:
                del d[k]

        # --- 攻撃モーション（踏み込み）のオフセットを集計 ---
        self.attack_off = {}
        self.attacking = set()
        active = []
        for anim in self.anims:
            off = anim.offset()
            if off is None:
                continue  # 再生終了
            active.append(anim)
            self.attacking.add(id(anim.entity))
            ox, oy = self.attack_off.get(id(anim.entity), (0.0, 0.0))
            self.attack_off[id(anim.entity)] = (ox + off[0], oy + off[1])
        self.anims = active

        # エフェクトの寿命管理と被弾フラッシュ強度の集計
        self.flash = {}
        active_fx = []
        for fx in self.fx:
            t = fx.progress()
            if t is None:
                continue  # 再生終了
            active_fx.append(fx)
            if isinstance(fx, FlashAnim):
                self.flash[id(fx.entity)] = 1.0 - t  # 当たった瞬間が最も白い
        self.fx = active_fx

    def _entity_screen(self, entity, cam_x: float, cam_y: float) -> tuple:
        """エンティティの画面描画位置（スムージング済み位置＋攻撃踏み込み−カメラ）。"""
        px, py = self.render_pos.get(
            id(entity), (entity.x * TILE_SIZE, entity.y * TILE_SIZE)
        )
        ax, ay = self.attack_off.get(id(entity), (0.0, 0.0))
        return px + ax - cam_x, py + ay - cam_y

    def _draw_fx(self, engine: "Engine", cam_x: float, cam_y: float) -> None:
        """斬撃・ダメージ数字をエンティティの上に重ねて描く（cam はピクセル座標）。"""
        gm = engine.game_map
        for fx in self.fx:
            if isinstance(fx, FlashAnim):
                continue  # フラッシュはエンティティ描画時に反映済み
            t = fx.progress()
            if t is None:
                continue
            if not gm.in_bounds(fx.x, fx.y) or not gm.visible[fx.x, fx.y]:
                continue  # 視界外の戦闘（同士討ち等）は描かない
            sx = fx.x * TILE_SIZE - cam_x
            sy = fx.y * TILE_SIZE - cam_y
            if isinstance(fx, SlashAnim):
                self._draw_slash(fx, t, sx, sy)
            elif isinstance(fx, PopupAnim):
                self._draw_popup(fx, t, sx, sy)

    def _draw_slash(self, fx: SlashAnim, t: float, sx: int, sy: int) -> None:
        """攻撃方向と垂直な白い線が、タイルを手前から奥へ走り抜ける。"""
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        # 線の中心：攻撃方向に沿って手前→奥へ移動
        shift = (t - 0.5) * TILE_SIZE * 0.7
        mx = TILE_SIZE / 2 + fx.ux * shift
        my = TILE_SIZE / 2 + fx.uy * shift
        # 線の向き：攻撃方向に垂直。進むにつれ少し短くなる
        px, py = -fx.uy, fx.ux
        half = TILE_SIZE * 0.42 * (1.0 - 0.3 * t)
        alpha = int(230 * (1.0 - t))
        pygame.draw.line(
            surf, (255, 255, 255, alpha),
            (mx - px * half, my - py * half), (mx + px * half, my + py * half), 3,
        )
        self.screen.blit(surf, (sx, sy))

    def _draw_popup(self, fx: PopupAnim, t: float, sx: int, sy: int) -> None:
        """ダメージ数字：太字＋影で浮き上がり、後半でフェードアウト。"""
        if fx.surf is None:
            base = self.font_bold.render(fx.text, True, fx.color)
            shade = self.font_bold.render(fx.text, True, (6, 6, 10))
            surf = pygame.Surface(
                (base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA
            )
            surf.blit(shade, (2, 2))
            surf.blit(base, (0, 0))
            fx.surf = surf
        label = fx.surf
        if t > 0.5:
            label.set_alpha(int(255 * (1.0 - t) * 2))
        x = sx + (TILE_SIZE - label.get_width()) // 2
        y = sy - 8 - int(fx.RISE * t)
        self.screen.blit(label, (x, y))

    @staticmethod
    def _ratio_color(ratio: float) -> tuple:
        """残量ゲージの色（高=緑 / 中=黄 / 低=赤）。"""
        if ratio > 0.5:
            return (88, 190, 96)
        if ratio > 0.25:
            return (230, 196, 60)
        return (224, 80, 70)

    def _stat_gauge(self, x: int, y: int, label: str, value_text: str,
                    ratio: float, color: tuple) -> int:
        """ラベル＋ゲージ＋数値のひとかたまりを描き、使った幅を返す。"""
        lw = self._text(label, x, y, color=self.FRAME_LIGHT, bold=True)
        gx = x + lw + 8
        self._draw_gauge(gx, y + 5, 96, 16, ratio, color)
        vw = self._text(value_text, gx + 102, y)
        return (gx + 102 + vw) - x

    def _render_panel(self, engine: "Engine") -> None:
        """下部パネル：ステータスゲージ＋ログ（装飾枠ウィンドウ）。"""
        screen = self.screen
        width = self.view_w * TILE_SIZE
        self._draw_window(0, self.play_h, width, self.PANEL_HEIGHT, alpha=255)

        f = engine.player.fighter
        y = self.play_h + 10
        x = 14

        # --- 1段目：HP・ST ゲージ／（ダンジョン中）モード・階数チップ
        hp_ratio = f.hp / max(1, f.max_hp)
        x += self._stat_gauge(x, y, "HP", f"{f.hp}/{f.max_hp}",
                              hp_ratio, self._ratio_color(hp_ratio)) + 22
        if f.uses_stamina:
            st_ratio = f.stamina / max(1, f.max_stamina)
            st_color = (86, 160, 222) if f.can_attack() else (224, 80, 70)
            x += self._stat_gauge(x, y, "ST", f"{f.stamina}(-{f.attack_stamina_cost})",
                                  st_ratio, st_color) + 22

        in_dungeon = not engine.in_camp and not getattr(engine, "in_village", False)
        if in_dungeon:
            rx = width - 14
            rx -= self._draw_chip(f"地下 {engine.current_floor} 階", rx, y - 2,
                                  colors.DESCEND, right_align=True) + 8
            if engine.attack_mode:
                self._draw_chip("攻撃モード", rx, y - 2, (255, 130, 130), right_align=True)
            else:
                self._draw_chip("移動モード", rx, y - 2, (150, 210, 150), right_align=True)

        # --- 2段目：満腹ゲージ・Lv/XP・実効ステータス・料理バフ
        y2 = y + self.LINE_HEIGHT
        x = 14
        if f.max_satiety > 0:
            sat_ratio = f.satiety / f.max_satiety
            if f.is_hungry:
                x += self._stat_gauge(x, y2, "空腹!", "", sat_ratio, (224, 70, 60)) + 16
            else:
                x += self._stat_gauge(x, y2, "満腹", f"{f.satiety}",
                                      sat_ratio, (226, 150, 62)) + 16
        lv = engine.player.level
        x += self._text(f"Lv.{lv.current_level}", x, y2, color=colors.XP, bold=True) + 12
        x += self._text(f"XP {lv.current_xp}/{lv.experience_to_next_level}",
                        x, y2, color=self.TEXT_DIM) + 16
        x += self._text(f"攻 {f.power}  防 {f.defense}", x, y2) + 16
        for eff in engine.player.status_effects:
            x += self._text(f"{eff.name}({eff.turns})", x, y2, color=colors.LEVEL_UP) + 12

        # --- 区切り線＋メッセージログ
        ly = self.play_h + 10 + self.LINE_HEIGHT * 2
        pygame.draw.line(screen, self.FRAME_DARK, (12, ly - 3), (width - 12, ly - 3), 1)
        engine.message_log.render(
            screen,
            self.font,
            x=14,
            y=ly + 2,
            line_height=self.LINE_HEIGHT,
            max_lines=self.LOG_LINES,
        )

        # --- 足元・階段の案内チップ（プレイ画面の右下に浮かせる）
        if in_dungeon:
            hint_text = None
            hint_color = colors.DESCEND
            if (engine.player.x, engine.player.y) == engine.game_map.downstairs_location:
                hint_text = "▼ Enter で次の階へ"
            else:
                foot = engine.item_under_player()
                if foot is not None:
                    hint_text = f"足元: {foot.name}（G で拾う）"
                    hint_color = colors.ITEM
            if hint_text:
                self._draw_chip(hint_text, width - 10, self.play_h - 36,
                                hint_color, right_align=True)

    def _render_game_over(self) -> None:
        screen = self.screen
        w = self.view_w * TILE_SIZE
        # 画面全体を暗く沈める
        overlay = pygame.Surface((w, self.play_h))
        overlay.set_alpha(150)
        overlay.fill((6, 2, 2))
        screen.blit(overlay, (0, 0))

        text = "ゲームオーバー"
        tw = self.big_font.size(text)[0]
        bw, bh = tw + 96, 116
        bx, by = (w - bw) // 2, self.play_h // 2 - bh // 2
        self._draw_window(bx, by, bw, bh, alpha=250)
        tx = bx + (bw - tw) // 2
        screen.blit(self.big_font.render(text, True, (6, 6, 10)), (tx + 4, by + 24 + 4))
        screen.blit(self.big_font.render(text, True, colors.PLAYER_DIE), (tx, by + 24))
        tip = "ESC でタイトルへ"
        self._text(tip, bx + (bw - self.font.size(tip)[0]) // 2, by + bh - 32,
                   color=self.TEXT_DIM, shadow=False)
