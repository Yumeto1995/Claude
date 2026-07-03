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


class ArrowAnim(_TimedFx):
    """放たれた矢が始点から着弾/停止点まで直線に飛ぶエフェクト。"""

    DURATION = 0.18

    def __init__(self, x0: int, y0: int, dx: int, dy: int, path):
        super().__init__()
        self.x0 = x0
        self.y0 = y0
        self.dx = dx
        self.dy = dy
        ex, ey = path[-1] if path else (x0, y0)  # 最遠到達タイル
        self.ex, self.ey = ex, ey
        self.x, self.y = ex, ey  # 視界判定用（終点）


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
    "boss": (170, 60, 70),
    "corpse": (191, 0, 0),
    "potion": (230, 90, 200),
    "scroll": (230, 220, 140),
    "scroll_confuse": (170, 120, 255),
    "dagger": (200, 200, 210),
    "sword": (230, 230, 245),
    "bow": (170, 130, 70),
    "arrow": (210, 200, 180),
    "leather_armor": (160, 110, 60),
    "chain_mail": (150, 160, 180),
    "material": (120, 180, 120),
    "key_item": (240, 210, 90),
    "stairs_down": (120, 220, 255),
    "stairs_up": (240, 210, 120),
    "tent": (90, 170, 90),
    "food": (220, 180, 120),
    # 食材の個別アイコン（実画像が来るまでの仮色）
    "food_nuts": (170, 90, 50), "food_herb": (90, 180, 90),
    "food_mushroom": (180, 130, 90), "food_meat": (200, 90, 80),
    "food_egg": (245, 235, 200), "food_milk": (236, 240, 245),
    "food_fish": (130, 170, 200), "food_bigfish": (90, 140, 190),
    "food_ration": (180, 160, 120), "food_potato": (182, 140, 90),
    "food_fruit": (220, 80, 90), "food_shellfish": (210, 190, 160),
    "food_cheese": (240, 200, 90), "food_honey": (230, 170, 60),
    # 農具アイコン（建設モードのチップ用）
    "tool_hoe": (150, 120, 80), "tool_hammer": (140, 110, 90),
    "tool_wateringcan": (110, 170, 200), "tool_pitchfork": (160, 140, 100),
    "tool_shovel": (150, 150, 160),
    "feed": (200, 180, 90), "sprinkler": (120, 180, 210),
    "seed": (170, 140, 80),
    "dish": (255, 170, 90),
    # 拠点の設備
    "st_cooking": (235, 130, 70),
    "st_storage": (170, 140, 100),
    "st_alchemy": (150, 110, 210),
    "st_ranch": (200, 160, 110),
    "st_fishery": (90, 150, 210),
    "st_exit": (120, 220, 255),
    "st_health": (225, 120, 120),
    "st_skill": (198, 130, 250),
    "farm_empty": (110, 80, 55),
    "farm_grow": (120, 170, 90),
    "farm_ready": (230, 220, 90),
    # ダンジョンのテーマ別 下地（gen_tiles.py が生成）。
    # 壁の向き別の縁取り・床の影は描画側でこの上に重ねる（オートタイル）。
    "cave_floor": (96, 80, 62), "cave_wall": (58, 49, 42), "cave_safe_floor": (74, 100, 90),
    "stone_floor": (78, 80, 98), "stone_wall": (52, 54, 70), "stone_safe_floor": (72, 102, 96),
    "meadow_floor": (156, 126, 86), "meadow_wall": (52, 92, 46), "meadow_safe_floor": (150, 150, 104),
    # セーフルーム＝ログハウス内装（床=板/敷物・壁=丸太/窓）。テーマに依らず使う。
    "log_floor": (176, 120, 68), "log_rug": (170, 80, 70),
    "log_wall": (150, 100, 55), "log_window": (150, 110, 72),
    # 村・建物（gen_tiles.py が生成）
    "grass": (74, 112, 58), "tree": (44, 84, 44), "door": (150, 110, 66),
    "wood_wall": (104, 72, 44), "wood_floor": (150, 112, 70),
}

TERRAIN_KEYS = {
    "floor", "wall",
    "cave_floor", "cave_wall", "cave_safe_floor",
    "stone_floor", "stone_wall", "stone_safe_floor",
    "meadow_floor", "meadow_wall", "meadow_safe_floor",
    "log_floor", "log_rug", "log_wall", "log_window",
    "grass", "tree", "door", "wood_wall", "wood_floor",
}

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


def load_sprites() -> Dict[str, pygame.Surface]:
    """assets 配下(サブフォルダ含む)の PNG を再帰読み込み（パスを除くファイル名＝キー）。

    characters/ monsters/ backgrounds/ items/ structures/ 等に整理済みでも、キーは
    サブフォルダを除いたファイル名（例 characters/player/player_left.png → "player_left"）。
    方向別・歩行・攻撃のコマ（例 player_down_walk1.png / player_right_walk1.png）も
    そのままファイル名＝キーで全部読む。**左右反転による自動生成は行わない**——右向きは
    専用の `*_right*` 画像を用意して読み込む（鏡像だと剣が逆の手になるため）。
    PLACEHOLDER_COLORS にあって PNG が無いキーは仮タイルで代用。
    32px 原寸の地形・アイテムは TILE_SIZE への整数倍拡大でくっきり表示される。
    """
    sprites: Dict[str, pygame.Surface] = {}
    if os.path.isdir(ASSETS_DIR):
        # サブフォルダを再帰探索。キーはパスを除いたファイル名（全体で一意の前提）。
        for root, _dirs, files in os.walk(ASSETS_DIR):
            for fn in files:
                if not fn.endswith(".png"):
                    continue
                try:
                    img = pygame.image.load(os.path.join(root, fn)).convert_alpha()
                except pygame.error:
                    continue
                sprites[fn[:-4]] = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
    # PNG が無い必須キーは仮タイルで代用
    for key in PLACEHOLDER_COLORS:
        if key not in sprites:
            sprites[key] = _make_placeholder(key)
    return sprites


class Renderer:
    """ウィンドウを持ち、カメラ追従でマップ・エンティティ・下部UIを描く。"""

    PANEL_HEIGHT = 184   # 下部パネル（HP/Lv＋ログ）。14*64+184=1080（フルHD）
    LOG_LINES = 4        # ログの表示行数
    LINE_HEIGHT = 28

    def __init__(self, view_w: int, view_h: int, panel_height: int = None):
        self.view_w = view_w
        self.view_h = view_h
        if panel_height is not None:
            self.PANEL_HEIGHT = panel_height  # 解像度ごとに下部パネル高を上書き
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
        self.facing = {}                 # id(entity) → 向き "down"/"up"/"left"/"right"
        self.now = 0.0                   # 現在時刻（_update_animations で更新）
        self._last_frame_t = None        # 前フレームの時刻（dt 計算用）
        # オートタイルの合成結果キャッシュ（向き別の壁・床影は隣接状況で決まる）
        self._wall_cache = {}            # (theme, mask, dark) → Surface
        self._floor_cache = {}           # (key, smask, dark) → Surface
        self._floor_keys_cache = {}      # theme → 床バリアントキーのタプル

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

    def render_settings(self, options, cursor: int, note: str = "") -> None:
        """画面設定（解像度選択）。options は表示用文字列のリスト。"""
        screen = self.screen
        w = self.view_w * TILE_SIZE
        h = self.play_h + self.PANEL_HEIGHT

        # 夜空風グラデ背景（タイトルと統一）
        band = 4
        for i in range(h // band + 1):
            t = i / (h // band)
            color = (int(7 + 9 * t), int(8 + 12 * t), int(14 + 22 * t))
            pygame.draw.rect(screen, color, (0, i * band, w, band))

        title = "画面設定（解像度）"
        tw = self.big_font.size(title)[0]
        tx, ty = (w - tw) // 2, 56
        screen.blit(self.big_font.render(title, True, (6, 6, 10)), (tx + 4, ty + 4))
        screen.blit(self.big_font.render(title, True, self.TEXT_GOLD), (tx, ty))

        mw = 460
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

        if note:
            self._text(note, (w - self.font.size(note)[0]) // 2, my + mh + 16,
                       color=self.TEXT_DIM, shadow=False)
        tip = "↑↓：選択　Enter：適用　ESC：戻る　F11：全画面"
        self._text(tip, (w - self.font.size(tip)[0]) // 2, my + mh + 44,
                   color=self.TEXT_DIM, shadow=False)
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
        return self._clamp_cam(cam_x, gm.width * TILE_SIZE, vw), \
            self._clamp_cam(cam_y, gm.height * TILE_SIZE, vh)

    @staticmethod
    def _clamp_cam(cam: float, world: float, view: float) -> float:
        """カメラ位置を世界内にクランプ。世界がビューより小さい軸は中央寄せ。

        村の建物内（13×9）など、ビュー(30×14)より小さいマップで両脇が
        黒帯にならないよう、収まりきる軸はマップを画面中央に置く。
        """
        if world <= view:
            return (world - view) / 2.0   # 負値＝マップを中央へ寄せる
        return max(0.0, min(cam, world - view))

    # ダンジョンの階層テーマ（浅層＝草原 / 中層＝洞窟 / 深層＝石）。
    MEADOW_MAX_FLOOR = 3   # ここまで草原（床=土・壁=茂み）
    CAVE_MAX_FLOOR = 6     # ここまで洞窟、以降は石

    @staticmethod
    def _dungeon_theme(floor: int) -> str:
        if floor <= Renderer.MEADOW_MAX_FLOOR:
            return "meadow"
        if floor <= Renderer.CAVE_MAX_FLOOR:
            return "cave"
        return "stone"

    @staticmethod
    def _is_wall(gm, x: int, y: int) -> bool:
        """(x,y) が壁か。マップ外も壁扱い（外周がスカスカに見えないように）。"""
        if not gm.in_bounds(x, y):
            return True
        return gm.tiles["sprite"][x, y] == tile_types.SPRITE_WALL

    # マスク用ビット（8近傍）
    _N, _S, _E, _W = 1, 2, 4, 8
    _NE, _NW, _SE, _SW = 16, 32, 64, 128

    def _wall_mask(self, gm, x: int, y: int) -> int:
        """隣接8マスのうち『壁である』方向のビットマスク。"""
        m = 0
        if self._is_wall(gm, x, y - 1): m |= self._N
        if self._is_wall(gm, x, y + 1): m |= self._S
        if self._is_wall(gm, x + 1, y): m |= self._E
        if self._is_wall(gm, x - 1, y): m |= self._W
        if self._is_wall(gm, x + 1, y - 1): m |= self._NE
        if self._is_wall(gm, x - 1, y - 1): m |= self._NW
        if self._is_wall(gm, x + 1, y + 1): m |= self._SE
        if self._is_wall(gm, x - 1, y + 1): m |= self._SW
        return m

    def _wall_surface(self, theme: str, mask: int, dark: bool) -> pygame.Surface:
        """壁の下地に『床へ面した側だけ』縁取り（光源=左上の立体感）を重ねた1枚。

        壁同士が隣り合う辺には縁取りを描かないので、壁の塊が連結して見える。
        結果は (theme, mask, dark) でキャッシュする。
        """
        key = (theme, mask, dark)
        cached = self._wall_cache.get(key)
        if cached is not None:
            return cached
        surf = self.sprites[f"{theme}_wall"].copy()
        T = TILE_SIZE
        N = not (mask & self._N); S = not (mask & self._S)
        E = not (mask & self._E); W = not (mask & self._W)

        def band(rect, color, alpha):
            ov = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
            ov.fill((*color, alpha))
            surf.blit(ov, (rect[0], rect[1]))

        LIGHT = (255, 246, 224)
        DARK = (0, 0, 0)
        # 床に面した辺＝立体の縁。上/左は明るく、下/右は影。
        if N:  # 上が床：頂部に光
            band((0, 0, T, 4), LIGHT, 70); band((0, 0, T, 1), LIGHT, 150)
        if W:  # 左が床：左面に光
            band((0, 0, 4, T), LIGHT, 60); band((0, 0, 1, T), LIGHT, 130)
        if E:  # 右が床：右面に影
            band((T - 4, 0, 4, T), DARK, 70); band((T - 1, 0, 1, T), DARK, 120)
        if S:  # 下が床：前面の段差＋接地の濃い影
            band((0, T - 6, T, 6), DARK, 80); band((0, T - 2, T, 2), DARK, 150)
        # 入り隅（斜めだけ床）：その角に小さな影を入れて窪みを表現
        for dia, (cx, cy), need in (
            (self._NE, (T - 6, 0), self._N | self._E),
            (self._NW, (0, 0), self._N | self._W),
            (self._SE, (T - 6, T - 6), self._S | self._E),
            (self._SW, (0, T - 6), self._S | self._W),
        ):
            if not (mask & dia) and (mask & need) == need:
                band((cx, cy, 6, 6), DARK, 80)

        if dark:
            surf = self._darken(surf)
        self._wall_cache[key] = surf
        return surf

    def _floor_surface(self, key: str, smask: int, dark: bool) -> pygame.Surface:
        """床の下地に、北/西に壁があれば『壁が落とす影』を重ねた1枚。

        壁際が暗くなることで壁と床の境界・つながりが分かりやすくなる。
        smask: bit0=北が壁, bit1=西が壁。
        """
        ckey = (key, smask, dark)
        cached = self._floor_cache.get(ckey)
        if cached is not None:
            return cached
        surf = self.sprites[key].copy()
        T = TILE_SIZE
        if smask & 1:  # 北に壁 → 上端に下向きの影グラデーション
            for i in range(7):
                a = int(95 * (1 - i / 7))
                ov = pygame.Surface((T, 1), pygame.SRCALPHA); ov.fill((0, 0, 0, a))
                surf.blit(ov, (0, i))
        if smask & 2:  # 西に壁 → 左端に右向きの影グラデーション
            for i in range(7):
                a = int(85 * (1 - i / 7))
                ov = pygame.Surface((1, T), pygame.SRCALPHA); ov.fill((0, 0, 0, a))
                surf.blit(ov, (i, 0))
        if dark:
            surf = self._darken(surf)
        self._floor_cache[ckey] = surf
        return surf

    def _draw_dungeon_terrain(self, engine, gm, cam_x: float, cam_y: float) -> None:
        """テーマ別＋オートタイルでダンジョン地形を描く。

        壁は床に面した側だけ縁取りして連結表示、床は壁際に影を落として
        境界を明確化する。見えている=明るく / 探索済み=暗く / 未探索=描かない。
        """
        screen = self.screen
        theme = self._dungeon_theme(engine.current_floor)
        tx0, ty0 = int(cam_x // TILE_SIZE), int(cam_y // TILE_SIZE)
        for ty in range(ty0, ty0 + self.view_h + 2):
            for tx in range(tx0, tx0 + self.view_w + 2):
                if not gm.in_bounds(tx, ty):
                    continue
                vis = gm.visible[tx, ty]
                if not vis and not gm.explored[tx, ty]:
                    continue  # 未探索は黒のまま
                dark = not vis
                sid = gm.tiles["sprite"][tx, ty]
                pos = (tx * TILE_SIZE - cam_x, ty * TILE_SIZE - cam_y)
                if sid == tile_types.SPRITE_WALL:
                    if self._is_safe_wall(gm, tx, ty):   # セーフルームを囲む壁＝丸太（時々窓）
                        key = self._det_pick(tx, ty, self.SAFE_WALL_VARIANTS)
                        surf = self.dark_sprites[key] if dark else self.sprites[key]
                    else:
                        surf = self._wall_surface(theme, self._wall_mask(gm, tx, ty), dark)
                elif sid in (tile_types.SPRITE_DOWNSTAIRS, tile_types.SPRITE_UPSTAIRS):
                    # 階段は透過オブジェクト。下に床を敷いてから階段を重ねる
                    # （敷かないと透過部分が黒く抜ける）。
                    screen.blit(self._floor_under(gm, tx, ty, theme, dark), pos)
                    skey = "stairs_down" if sid == tile_types.SPRITE_DOWNSTAIRS else "stairs_up"
                    surf = self.dark_sprites[skey] if dark else self.sprites[skey]
                elif gm.safe[tx, ty]:                    # セーフルームの床＝板（時々敷物）
                    key = self._det_pick(tx, ty, self.SAFE_FLOOR_VARIANTS)
                    surf = self.dark_sprites[key] if dark else self.sprites[key]
                else:
                    surf = self._floor_under(gm, tx, ty, theme, dark)
                screen.blit(surf, pos)

    # セーフルーム＝ログハウス内装のタイル（テーマ非依存）。基本を多く、窓/敷物はまばら。
    SAFE_FLOOR_VARIANTS = ("log_floor", "log_floor", "log_floor", "log_floor", "log_rug")
    SAFE_WALL_VARIANTS = ("log_wall", "log_wall", "log_wall", "log_window")

    @staticmethod
    def _det_pick(tx: int, ty: int, variants):
        """タイル座標から決定的に1枚選ぶ（毎フレーム同じ柄でちらつかない）。"""
        h = ((tx * 73856093) ^ (ty * 19349663)) & 0x7FFFFFFF
        return variants[h % len(variants)]

    def _floor_under(self, gm, tx: int, ty: int, theme: str, dark: bool) -> pygame.Surface:
        """そのタイルの床Surface（セーフ=板/敷物、通常=テーマ床＋壁影）。
        階段など透過オブジェクトの下地にも使う。"""
        if gm.safe[tx, ty]:
            key = self._det_pick(tx, ty, self.SAFE_FLOOR_VARIANTS)
            return self.dark_sprites[key] if dark else self.sprites[key]
        smask = (1 if self._is_wall(gm, tx, ty - 1) else 0) \
            | (2 if self._is_wall(gm, tx - 1, ty) else 0)
        key = self._det_pick(tx, ty, self._floor_keys(theme))
        return self._floor_surface(key, smask, dark)

    def _floor_keys(self, theme: str):
        """テーマ床のバリアントキー一覧（`{theme}_floor`, `_floor2..5` の在るものだけ）。

        村の草（GRASS_VARIANTS）と同様、複数タイルを座標で決定的に敷き分けて
        単一タイル反復の格子模様を抑える。バリアントが無ければ従来どおり1枚。"""
        keys = self._floor_keys_cache.get(theme)
        if keys is None:
            cands = [f"{theme}_floor"] + [f"{theme}_floor{n}" for n in range(2, 6)]
            keys = tuple(k for k in cands if k in self.sprites) or (f"{theme}_floor",)
            self._floor_keys_cache[theme] = keys
        return keys

    def _is_safe_wall(self, gm, tx: int, ty: int) -> bool:
        """セーフルームの床に隣接する壁か（8近傍）。＝ログハウスの内壁にする。"""
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = tx + dx, ty + dy
                if (gm.in_bounds(nx, ny) and gm.safe[nx, ny]
                        and gm.tiles["sprite"][nx, ny] != tile_types.SPRITE_WALL):
                    return True
        return False

    # 屋外の草地バリアント。基本を多めに、装飾はまばらに混ぜる重み付きリスト。
    GRASS_VARIANTS = (
        "grass", "grass", "grass", "grass", "grass",
        "grass_clover", "grass_clover", "grass_flower", "grass_stone", "grass_dirt",
    )

    def _grass_for(self, tx: int, ty: int) -> pygame.Surface:
        """タイル座標から決定的に草バリアントを選ぶ（毎フレーム同じ柄）。"""
        h = ((tx * 73856093) ^ (ty * 19349663)) & 0x7FFFFFFF
        key = self.GRASS_VARIANTS[h % len(self.GRASS_VARIANTS)]
        return self.sprites.get(key, self.sprites["grass"])

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

        # 村・建物は専用描画
        if getattr(engine, "in_village", False):
            self._render_village_map(engine)
            self._render_panel(engine)
            if getattr(engine, "dialogue", None) is not None:
                self._render_dialogue(engine)
            if getattr(engine, "shop_kind", None) is not None:
                self._render_shop_menu(engine)
            if getattr(engine, "skill_open", False):
                self._render_skill_tree(engine)
            pygame.display.flip()
            return

        # 拠点（テント内）は専用描画
        if engine.in_camp:
            self._render_camp_map(engine)
            self._render_panel(engine)
            if engine.camp_menu is not None:
                self._render_camp_menu(engine)
            if getattr(engine, "skill_open", False):
                self._render_skill_tree(engine)
            pygame.display.flip()
            return

        gm = engine.game_map

        # 位置スムージングを更新し、ピクセル単位カメラでプレイヤーに滑らかに追従
        self._update_animations(engine)
        cam_x, cam_y = self._camera_px(engine)

        # 地形を描画（テーマ別＋オートタイルで壁を連結・床に影）
        self._draw_dungeon_terrain(engine, gm, cam_x, cam_y)

        # エンティティを描画（死体→生者の順）。見えているタイルのものだけ。
        vw, vh = self.view_w * TILE_SIZE, self.view_h * TILE_SIZE
        for entity in sorted(gm.entities, key=lambda e: e.blocks_movement):
            es = getattr(entity, "size", 1)
            # 可視判定：大型はフットプリントのどこかが見えていれば描く
            if es > 1:
                vis = any(gm.in_bounds(entity.x + ox, entity.y + oy)
                          and gm.visible[entity.x + ox, entity.y + oy]
                          for ox in range(es) for oy in range(es))
            else:
                vis = gm.visible[entity.x, entity.y]
            if not vis:
                continue
            sx, sy = self._entity_screen(entity, cam_x, cam_y)
            if -TILE_SIZE * es < sx < vw and -TILE_SIZE * es < sy < vh:
                # 攻撃ポーズ・歩行コマ・通常を状況で切り替える
                sprite = self.sprites.get(
                    self._sprite_key_for(entity), self.sprites["player"]
                )
                if es > 1:                              # 大型ボスは size×size に拡大
                    sprite = pygame.transform.scale(sprite, (TILE_SIZE * es, TILE_SIZE * es))
                flash = self.flash.get(id(entity), 0.0)
                if flash > 0.0:
                    sprite = self._whiten(sprite, flash)  # 被弾フラッシュ
                if entity.blocks_movement:  # 生きたキャラには足元影
                    self._draw_shadow(sx, sy)
                # 手続き的モーション（呼吸・歩行の跳ね）を上下オフセットで加える
                screen.blit(sprite, (sx, sy + self._sprite_motion(entity)))

        # 斬撃・ダメージ数字はエンティティの上に重ねる
        self._draw_fx(engine, cam_x, cam_y)

        # セーフルームにいるときは画面右上に表示
        if engine.game_map.safe[engine.player.x, engine.player.y]:
            self._draw_chip("セーフルーム", self.view_w * TILE_SIZE - 8, 8,
                            colors.HEAL, right_align=True)

        # ボスフロアでは画面上部に主のHPバー
        self._render_boss_hud(engine)

        self._render_panel(engine)

        if engine.inventory_open:
            self._render_inventory(engine)

        if getattr(engine, "skill_open", False):
            self._render_skill_tree(engine)

        if engine.game_over:
            self._render_game_over()

        pygame.display.flip()

    def _render_village_map(self, engine: "Engine") -> None:
        """村・建物内マップ（地形・NPC/店主・ドア・看板・プレイヤー・案内）。"""
        import village_map

        screen = self.screen
        gm = engine.game_map
        indoors = getattr(engine, "building_key", None) is not None
        self._update_animations(engine)
        cam_x, cam_y = self._camera_px(engine)

        floor_key = "wood_floor" if indoors else "grass"

        def terrain(tx, ty):
            sid = gm.tiles["sprite"][tx, ty]
            if sid == tile_types.SPRITE_WALL:
                return self.sprites["wood_wall"]
            if sid == tile_types.SPRITE_TREE:
                return self.sprites["tree"]
            if sid == tile_types.SPRITE_DOOR:
                return self.sprites["door"]
            if sid == tile_types.SPRITE_DOWNSTAIRS:
                return self.sprites["stairs_down"]
            if floor_key == "grass":
                return self._grass_for(tx, ty)   # 屋外はタイル毎に草を敷き分ける
            return self.sprites[floor_key]
        self._draw_terrain(gm, cam_x, cam_y, terrain)

        # 看板（屋外のみ。建物内は店名を案内チップで出す）
        if not indoors:
            for text, lx, ly in village_map.LABELS:
                self._text(text, lx * TILE_SIZE - cam_x, ly * TILE_SIZE - cam_y,
                           color=(238, 226, 170), bold=True)

        # エンティティ（NPC/店主→プレイヤーの順）。スムージング位置で描く。
        vw, vh = self.view_w * TILE_SIZE, self.view_h * TILE_SIZE
        for ent in sorted(gm.entities, key=lambda e: e is engine.player):
            sx, sy = self._entity_screen(ent, cam_x, cam_y)
            if -TILE_SIZE < sx < vw and -TILE_SIZE < sy < vh:
                spr = self.sprites.get(self._sprite_key_for(ent), self.sprites["player"])
                self._draw_shadow(sx, sy)
                screen.blit(spr, (sx, sy))

        # 建物内の見出し
        if indoors:
            import buildings
            self._draw_chip(buildings.label(engine.building_key), 8, 8, colors.WELCOME)

        # 足元/隣の案内チップ
        px, py = engine.player.x, engine.player.y
        hint = None
        if not indoors and (px, py) == village_map.DUNGEON_ENTRANCE:
            hint = "Enter で 洞窟（ダンジョン）へ"
        elif not indoors and (px, py) in village_map.DOORS:
            import buildings
            hint = f"Enter で {buildings.label(village_map.DOORS[(px, py)])} に入る"
        elif indoors and (px, py) == engine.building_exit:
            hint = "Enter で 村へ戻る"
        else:
            for ent in gm.entities:
                if ent is engine.player:
                    continue
                if max(abs(ent.x - px), abs(ent.y - py)) != 1:
                    continue
                if getattr(ent, "shop", None):
                    hint = f"Enter で {ent.name} と取引"
                    break
                if getattr(ent, "dialogue", None):
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

    def _render_shop_menu(self, engine: "Engine") -> None:
        """店（買い物）のウィンドウ。品名・価格・所持金を表示し、買えない品は淡色。"""
        import shop
        kind = engine.shop_kind
        opts = shop.options(engine, kind)
        info = shop.info(engine, kind)

        w = self.view_w * TILE_SIZE
        ww = 560
        wh = 70 + len(info) * self.LINE_HEIGHT + max(1, len(opts)) * self.LINE_HEIGHT + 16
        wx, wy = (w - ww) // 2, 28
        self._draw_window(wx, wy, ww, wh)

        x, y = wx + 22, wy + 14
        self._text(shop.title(kind), x, y, color=self.TEXT_GOLD, bold=True)
        pygame.draw.line(self.screen, self.FRAME_DARK,
                         (wx + 14, y + 32), (wx + ww - 14, y + 32), 1)
        cy = y + 40
        for line in info:
            self._text(line, x, cy, color=self.TEXT_DIM, shadow=False)
            cy += self.LINE_HEIGHT
        cy += 6
        cursor = min(engine.shop_cursor, max(0, len(opts) - 1))
        if not opts:
            self._text("（品物がない）", x, cy, color=self.TEXT_DIM)
        for i, opt in enumerate(opts):
            row = cy + i * self.LINE_HEIGHT
            if i == cursor:
                pygame.draw.rect(self.screen, (46, 52, 86), (wx + 12, row - 3, ww - 24, self.LINE_HEIGHT))
                pygame.draw.rect(self.screen, (104, 112, 168), (wx + 12, row - 3, ww - 24, self.LINE_HEIGHT), 1)
                pygame.draw.rect(self.screen, self.TEXT_GOLD, (wx + 12, row - 3, 3, self.LINE_HEIGHT))
                self._text("▶", x, row, color=self.TEXT_GOLD, bold=True)
            if not opt.get("enabled", True):
                color = (118, 118, 124)   # 高い/満杯で買えない
            elif i == cursor:
                color = self.TEXT_GOLD
            else:
                color = self.TEXT_MAIN
            self._text(opt["text"], x + 30, row, color=color, shadow=(i == cursor))

    def _render_skill_tree(self, engine: "Engine") -> None:
        """スキルツリー：9系統×3段の格子。習得済/習得可/前提未達を色分け表示。"""
        import skills as sk_mod
        sk = engine.player.skills
        screen = self.screen
        w = self.view_w * TILE_SIZE
        h = self.play_h + self.PANEL_HEIGHT

        overlay = pygame.Surface((w, h)); overlay.set_alpha(180); overlay.fill((4, 5, 9))
        screen.blit(overlay, (0, 0))

        wx, wy, ww, wh = 24, 24, w - 48, h - 48
        self._draw_window(wx, wy, ww, wh)
        self._text("スキルツリー", wx + 20, wy + 12, color=self.TEXT_GOLD, bold=True)
        self._text(f"スキルポイント：{sk.points}", wx + 220, wy + 12,
                   color=self.TEXT_GOLD, bold=True)
        self._text(f"Lv.{engine.player.level.current_level}（お金＝経験値を使うと下がる）",
                   wx + 420, wy + 12, color=self.TEXT_DIM, shadow=False)
        pygame.draw.line(screen, self.FRAME_DARK,
                         (wx + 14, wy + 44), (wx + ww - 14, wy + 44), 1)

        branches = sk_mod.BRANCH_KEYS
        n = len(branches)
        col_w = (ww - 40) // n
        grid_x = wx + 20
        grid_y = wy + 60
        cell_h = 78
        node_w, node_h = col_w - 10, 64

        for bi, branch in enumerate(branches):
            cx = grid_x + bi * col_w
            # 系統名（縦の見出し）
            label = sk_mod.BRANCH_LABEL[branch]
            sel_branch = bi == engine.skill_branch
            self._text(label, cx + (node_w - self.font.size(label)[0]) // 2, grid_y - 28,
                       color=self.TEXT_GOLD if sel_branch else self.FRAME_LIGHT, bold=True)
            for tier in range(sk_mod.TIERS):
                ny = grid_y + tier * cell_h
                unlocked = sk.is_unlocked(branch, tier)
                can = sk.can_unlock(branch, tier)
                selected = sel_branch and tier == engine.skill_tier
                # 枠の色：習得済=緑 / 習得可=金 / それ以外=灰
                if unlocked:
                    bg, border = (34, 64, 40), (96, 190, 110)
                elif can:
                    bg, border = (54, 50, 30), self.TEXT_GOLD
                else:
                    bg, border = (28, 30, 40), (70, 72, 88)
                pygame.draw.rect(screen, bg, (cx, ny, node_w, node_h))
                pygame.draw.rect(screen, border, (cx, ny, node_w, node_h),
                                 3 if selected else 1)
                if selected:  # 選択枠を強調
                    pygame.draw.rect(screen, self.TEXT_GOLD, (cx, ny, node_w, node_h), 3)
                # 列見出しに系統名があるので、ノードは段名（心得/鍛錬/極意）＋効果
                nm = sk_mod.TIER_NAME[tier]
                ds = sk_mod.node_desc(branch, tier)
                mark = "✓" if unlocked else ("●" if can else "・")
                tcol = (220, 240, 220) if unlocked else (self.TEXT_MAIN if can else (120, 122, 134))
                self._text(f"{mark}{nm}", cx + 6, ny + 5, color=tcol, shadow=False)
                self._text(ds, cx + 6, ny + 33,
                           color=(196, 198, 210) if (can or unlocked) else (110, 112, 124),
                           shadow=False)

        # 下部の操作ヒント
        self._text("←→ 系統　↑↓ 段　Enter 習得　t/ESC 閉じる",
                   wx + 20, wy + wh - 34, color=self.TEXT_DIM, shadow=False)

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

        # 住居の固定設備
        for (wx, wy), kind in camp_map.STATIONS.items():
            screen.blit(self.sprites["st_" + kind],
                        (wx * TILE_SIZE - cam_x, wy * TILE_SIZE - cam_y))
        # 自由配置した畑・牧柵・いけす
        for (ox, oy), obj in engine.camp_objects.items():
            sx, sy = ox * TILE_SIZE - cam_x, oy * TILE_SIZE - cam_y
            screen.blit(self.sprites[self._camp_object_sprite(obj)], (sx, sy))
            c = obj["content"]
            if c is not None and c["steps_left"] <= 0:   # 収穫可能マーカー
                pygame.draw.circle(screen, (255, 230, 90),
                                   (int(sx + TILE_SIZE - 10), int(sy + 10)), 5)

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

        # 足元の案内（建設モード / 住居設備 / 配置物）。設備メニュー中は出さない。
        pos = (engine.player.x, engine.player.y)
        ti = getattr(engine, "camp_tool", None)
        if ti is not None:
            tool = camp_map.TOOLS[ti]
            px = engine.player.x * TILE_SIZE - cam_x
            py = engine.player.y * TILE_SIZE - cam_y
            ok = self._tool_target_ok(engine, pos, tool)
            pygame.draw.rect(screen, (120, 230, 140) if ok else (230, 120, 110),
                             (px, py, TILE_SIZE, TILE_SIZE), 2)
            cx = 8
            icon = self.sprites.get(tool.get("sprite"))
            if icon is not None:                      # 道具アイコンをチップ左に
                screen.blit(pygame.transform.smoothscale(icon, (28, 28)),
                            (10, self.play_h - 40))
                cx = 44
            cost = ""
            if tool["act"] == "build":
                b = camp_map.BUILDABLE[tool["kind"]]
                cost = f"(要:{b[4]})" if b[4] else f"({b[1]})"
            self._draw_chip(f"{tool['name']}{cost}  Enter使用 / b・1-7切替 / ESC終了",
                            cx, self.play_h - 36, (255, 205, 90))
        elif engine.camp_menu is None:
            here = camp_map.STATIONS.get(pos)
            if here is not None:
                self._draw_chip("Enter で " + camp_map.STATION_LABELS.get(here, here),
                                8, self.play_h - 36, colors.DESCEND)
            elif pos in engine.camp_objects:
                lbl = camp_map.BUILDABLE[engine.camp_objects[pos]["kind"]][0]
                self._draw_chip("Enter で " + lbl, 8, self.play_h - 36, colors.DESCEND)
            else:
                self._draw_chip("b で建設モード", 8, self.play_h - 36, (150, 210, 150))

    @staticmethod
    def _camp_object_sprite(obj) -> str:
        """配置した農場設備のスプライト（畑は栽培状態でempty/grow/readyに変化）。"""
        kind, c = obj["kind"], obj["content"]
        if kind == "farm":
            if c is None:
                return "farm_empty"
            return "farm_ready" if c["steps_left"] <= 0 else "farm_grow"
        if kind == "pen":
            return "st_ranch"
        if kind == "tank":
            return "st_fishery"
        return "sprinkler"

    @staticmethod
    def _tool_target_ok(engine, pos, tool) -> bool:
        """道具が足元タイルで使えるか（建設モードの緑/赤ハイライト用）。"""
        import camp_map
        act = tool["act"]
        obj = engine.camp_objects.get(pos)
        if act == "build":
            return pos not in camp_map.STATIONS and obj is None
        if act == "remove":
            return obj is not None
        if act in ("water", "feed"):
            want = ("farm",) if act == "water" else ("pen", "tank")
            c = obj["content"] if obj is not None else None
            return (obj is not None and obj["kind"] in want
                    and c is not None and c["steps_left"] > 0 and c.get("boost_cd", 0) <= 0)
        return False

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
        import spoilage
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
                disp_name = item.name if getattr(item, "count", 1) <= 1 else f"{item.name} ×{item.count}"
                self._text(disp_name, x + 62, row_y + 7, color=name_color)
                slabel, scolor = spoilage.stage(item)   # 鮮度タグ（新鮮/傷み/腐敗）
                if slabel:
                    nw = self.font.size(disp_name)[0]
                    self._text(slabel, x + 62 + nw + 12, row_y + 7, color=scolor, shadow=False)
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
        self._text("←→：分類　↑↓：選択　Enter：使用/装備　t：投げる　i：閉じる",
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
        if getattr(eq, "max_range", 0):
            parts.append(f"射程{eq.max_range}")
        return "  (" + " ".join(parts) + ")" if parts else ""

    # 1歩(1マス)の中の脚サイクル：踏み出し→足をそろえる(passing)。
    # これを毎マス交互の足で繰り返すと「右足・左足」の歩行に見える。
    STEP_DT = 0.13   # 1歩の見かけ時間(秒)。踏み出し時刻からの経過で位相を取る
    PASS_AT = 0.6    # 位相がこの割合を超えたら passing（足をそろえる）に切替
    # 手続き的モーション（画像に依存しない“生き感”）。歩行=跳ね／静止=呼吸。
    # ベース画像1枚でも動くので、仮画像でも本番画像でもそのまま効く。
    IDLE_BOB = 2.2   # 静止時に上下する最大px（呼吸）
    IDLE_FREQ = 3.1  # 呼吸の速さ(rad/s)
    WALK_HOP = 5.0   # 歩行1歩で跳ねる最大px

    @staticmethod
    def _dir_from(dx: int, dy: int) -> str:
        """移動/攻撃の (dx,dy) から向きを決める（横優先＝斜めは左右を向く）。"""
        if dx == 0 and dy == 0:
            return "down"
        if abs(dx) >= abs(dy):
            return "left" if dx < 0 else "right"
        return "up" if dy < 0 else "down"

    def _resolve(self, base: str, d: str, suffix: str) -> "Optional[str]":
        """`base_d_suffix` → `base_suffix` → `base_d` → `base` の順で在るキーを返す。"""
        for cand in (f"{base}_{d}{suffix}", f"{base}{suffix}", f"{base}_{d}", base):
            if cand in self.sprites:
                return cand
        return None

    def _sprite_key_for(self, entity) -> str:
        """状況＋向きに応じたスプライトキー（攻撃ポーズ＞歩行コマ＞通常、方向別）。"""
        key = entity.sprite
        eid = id(entity)
        d = self.facing.get(eid, "down")
        if eid in self.attacking:
            r = self._resolve(key, d, "_attack")
            if r:
                return r
        if eid in self.walking:
            # 踏み出してからの経過で位相を取り、前半=踏み出し / 後半=足そろえ
            phase = (self.now - self.step_t0.get(eid, self.now)) / self.STEP_DT
            if phase < self.PASS_AT:
                stride = "_walk1" if self.walk_step.get(eid, 0) % 2 == 0 else "_walk2"
                r = self._resolve(key, d, stride)
                if r:
                    return r
        # idle：向きだけ反映
        return self._resolve(key, d, "") or key

    def _sprite_motion(self, entity) -> float:
        """スプライトに与える上下オフセット(px)。画像に依存せず“生き感”を出す。

        歩行＝1歩ごとにひょこっと跳ね／静止＝ゆっくり呼吸で上下／攻撃＝0（踏み込みは
        attack_off 側で表現）。生きたキャラ（blocks_movement）だけが動き、死体・アイテム
        は静止。影は足元（sy）に固定なので、跳ねると接地して見える。"""
        if not entity.blocks_movement:
            return 0.0
        eid = id(entity)
        if eid in self.attacking:
            return 0.0
        if eid in self.walking:
            t = (self.now - self.step_t0.get(eid, self.now)) / self.STEP_DT
            return -self.WALK_HOP * abs(math.sin(min(t, 1.0) * math.pi))
        # 静止：個体ごとに位相をずらし、一斉に動かないようにする
        phase = (eid % 1000) / 1000.0 * math.tau
        return -self.IDLE_BOB * (0.5 + 0.5 * math.sin(self.now * self.IDLE_FREQ + phase))

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
            self.facing[id(entity)] = self._dir_from(dx, dy)  # 攻撃した向きを向く
        engine.drain_moves()
        for fx in engine.drain_fx():
            kind = fx[0]
            if kind == "slash":
                self.fx.append(SlashAnim(*fx[1:]))
            elif kind == "flash":
                self.fx.append(FlashAnim(fx[1]))
            elif kind == "popup":
                self.fx.append(PopupAnim(*fx[1:]))
            elif kind == "arrow":
                self.fx.append(ArrowAnim(*fx[1:]))

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
                    px, py = self.last_tile[eid]
                    self.facing[eid] = self._dir_from(ent.x - px, ent.y - py)  # 進む向き
                self.last_tile[eid] = (ent.x, ent.y)

        # 退場したエンティティ（フロア移動で入れ替わる敵など）の記録を掃除
        for d in (self.render_pos, self.last_tile, self.step_t0, self.walk_step, self.facing):
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
            if isinstance(fx, ArrowAnim):
                self._draw_arrow(fx, t, gm, cam_x, cam_y)
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

    def _draw_arrow(self, fx, t: float, gm, cam_x: float, cam_y: float) -> None:
        """矢が始点→着弾点を直線に飛ぶ。現在位置のタイルが見えている時だけ描く。"""
        cx = fx.x0 + (fx.ex - fx.x0) * t   # タイル座標で線形補間
        cy = fx.y0 + (fx.ey - fx.y0) * t
        ti, tj = int(round(cx)), int(round(cy))
        if not gm.in_bounds(ti, tj) or not gm.visible[ti, tj]:
            return
        sx = cx * TILE_SIZE - cam_x + TILE_SIZE / 2
        sy = cy * TILE_SIZE - cam_y + TILE_SIZE / 2
        norm = math.hypot(fx.dx, fx.dy) or 1.0
        ux, uy = fx.dx / norm, fx.dy / norm
        half = TILE_SIZE * 0.30
        tail = (sx - ux * half, sy - uy * half)
        head = (sx + ux * half, sy + uy * half)
        pygame.draw.line(self.screen, (240, 228, 180), tail, head, 3)
        pygame.draw.circle(self.screen, (255, 250, 210), (int(head[0]), int(head[1])), 3)

    @staticmethod
    def _boss_entity(gm):
        """ボスフロアの主（生存中の大型エンティティ）を返す。いなければ None。"""
        if not getattr(gm, "boss_floor", False):
            return None
        for e in gm.entities:
            if getattr(e, "size", 1) > 1:
                f = getattr(e, "fighter", None)
                if f is not None and f.hp > 0:
                    return e
        return None

    def _render_boss_hud(self, engine: "Engine") -> None:
        """ボスフロアで主を視認中、画面上部に名前＋HPバーを表示する。"""
        gm = engine.game_map
        boss = self._boss_entity(gm)
        if boss is None:
            return
        # 一度視認したら、そのフロアにいる間は出し続ける（視界外でも消えない）
        es = getattr(boss, "size", 1)
        if not getattr(boss, "_hud_seen", False):
            visible_now = any(gm.in_bounds(boss.x + ox, boss.y + oy)
                              and gm.visible[boss.x + ox, boss.y + oy]
                              for ox in range(es) for oy in range(es))
            if not visible_now:
                return
            boss._hud_seen = True

        f = boss.fighter
        width = self.view_w * TILE_SIZE
        ww = min(width - 80, 560)
        x0 = (width - ww) // 2
        y0, wh = 14, 56
        self._draw_window(x0, y0, ww, wh, alpha=235)
        # 名前（左・金色）／HP数値（右）
        self._text(boss.name, x0 + 16, y0 + 8, color=(244, 208, 120), bold=True)
        vt = f"{max(0, f.hp)}/{f.max_hp}"
        vw = self.font.size(vt)[0]
        self._text(vt, x0 + ww - 16 - vw, y0 + 8)
        # HP ゲージ（幅広・残量で色変化）
        ratio = f.hp / max(1, f.max_hp)
        self._draw_gauge(x0 + 16, y0 + 32, ww - 32, 16, ratio, self._ratio_color(ratio))

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
            if getattr(engine, "fire_mode", False):
                self._draw_chip("射撃方向？", rx, y - 2, (255, 205, 90), right_align=True)
            elif getattr(engine, "throw_item", None) is not None:
                self._draw_chip("投げる方向？", rx, y - 2, (255, 205, 90), right_align=True)
            elif engine.attack_mode:
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
        # 所持金＝経験値（使うとレベルが下がる）。金色で強調。
        x += self._text(f"所持金 {lv.wealth()}", x, y2, color=self.TEXT_GOLD, bold=True) + 14
        x += self._text(f"次Lv {lv.experience_to_next_level - lv.current_xp}",
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
            pos = (engine.player.x, engine.player.y)
            if pos == engine.game_map.downstairs_location:
                hint_text = "▼ Enter で次の階へ"
            elif pos == engine.game_map.upstairs_location:
                hint_text = ("▲ Enter で村へ戻る" if engine.current_floor <= 1
                             else "▲ Enter で上の階へ")
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
