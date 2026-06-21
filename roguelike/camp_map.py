"""歩けるテント内（拠点）のマップ定義。

スターデュー風の自由配置農場。住居（収納・料理・錬金・体調）は左上に固定。
広い床に、プレイヤーが畑・牧柵・いけすを自由に建てる（engine.camp_objects）。
牧場・漁業は鍵で開放されるまで建てられない。
"""
from __future__ import annotations

import tile_types
from game_map import GameMap

CAMP_W, CAMP_H = 48, 30
ENTRANCE = (24, 27)

# 住居の固定設備： (x, y) -> 種類（畑/牧柵/いけすは固定ではなく自由配置）
STATIONS = {
    (3, 3): "storage",
    (5, 3): "cooking",
    (7, 3): "alchemy",
    (9, 3): "health",
    (24, 28): "exit",
}

# 区画名ラベル： (text, x, y)
ZONE_LABELS = [
    ("住居", 3, 1),
    ("農場（b で建設）", 16, 1),
]

# 設備ごとの表示名（案内・メッセージ用）
STATION_LABELS = {
    "storage": "収納",
    "cooking": "料理（かまど）",
    "alchemy": "アイテム錬金",
    "health": "体調を調べる",
    "exit": "ダンジョンに戻る",
}

# 自由配置で建てられる農場設備：
#   kind -> (表示名, 建設費=経験値, 空き状態スプライト, 必要開放区画, 消費アイテム名)
# 消費アイテム名が None なら経験値で建設、指定があればそのアイテムを1消費して設置する。
BUILDABLE = {
    "farm": ("畑", 20, "farm_empty", None, None),
    "pen":  ("牧柵", 40, "st_ranch", "ranch", None),
    "tank": ("いけす", 40, "st_fishery", "fishery", None),
    # スプリンクラーは購入/クラフトした「スプリンクラー」アイテムを設置（隣接畑を自動水やり）
    "sprinkler": ("スプリンクラー", 0, "sprinkler", None, "スプリンクラー"),
}

# 建設モードの道具（b で切替 / 1-6 で直接選択 / Enter で使用）。
# act=build(kind を建設) / remove(撤去) / water(畑に水やり) / feed(牧柵・いけすに餌やり)
TOOLS = [
    {"name": "クワ（畑を作る）", "act": "build", "kind": "farm", "sprite": "tool_hoe"},
    {"name": "トンカチ（牧柵）", "act": "build", "kind": "pen", "sprite": "tool_hammer"},
    {"name": "トンカチ（いけす）", "act": "build", "kind": "tank", "sprite": "tool_hammer"},
    {"name": "トンカチ（スプリンクラー）", "act": "build", "kind": "sprinkler", "sprite": "tool_hammer"},
    {"name": "ジョウロ（水やり）", "act": "water", "sprite": "tool_wateringcan"},
    {"name": "畜産フォーク（餌やり）", "act": "feed", "sprite": "tool_pitchfork"},
    {"name": "スコップ（撤去）", "act": "remove", "sprite": "tool_shovel"},
]
TEND_BOOST = 15   # 水やり/餌やり1回で進む歩数（同歩数のクールダウンも付く）


def build_camp_map() -> GameMap:
    gm = GameMap(CAMP_W, CAMP_H)
    # 外周は壁、内側は床（オープンな1部屋）
    gm.tiles[1 : CAMP_W - 1, 1 : CAMP_H - 1] = tile_types.floor
    gm.visible[:, :] = True   # 拠点は霧なし
    gm.explored[:, :] = True
    gm.safe[:, :] = True
    gm.downstairs_location = (-1, -1)
    return gm
