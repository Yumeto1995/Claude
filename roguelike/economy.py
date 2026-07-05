"""拠点の経済まわり（Stardew 風の作り込みの共通基盤）。

- 品質（星）：産物に付く 普通/銀/金。満腹・栄養・売値が上がる。
- 出荷（売却）：産物や余り物の売値を算出する。
- 図鑑：収集対象（作物・畜産・魚・料理）の一覧。
- 設備アップグレード：段階ごとの効果値。
これらは camp.py / farming / husbandry / fishery / cooking / consumable などから参照される。
"""
from __future__ import annotations

import random

import item_category

# ---- 品質（星）----
QUALITY_NAME = ["", "銀", "金"]        # 0=普通 / 1=銀 / 2=金
QUALITY_MULT = [1.0, 1.25, 1.5]       # 満腹・栄養・売値にかかる倍率


def quality_of(item) -> int:
    return getattr(item, "quality", 0)


def quality_suffix(item) -> str:
    q = quality_of(item)
    return f"（{QUALITY_NAME[q]}）" if q else ""


def roll_quality(rank: int, tended: bool = False) -> int:
    """スキルランク（0..4）＋手入れ（水やり/スプリンクラー/餌）で品質を抽選。"""
    score = rank + (2 if tended else 0) + random.randint(0, 2)
    if score >= 6:
        return 2
    if score >= 4:
        return 1
    return 0


# ---- 売値（出荷）----
# 名前ごとの基準額。未記載は分類で決定。品質倍率と count を掛けて算出する。
# 売値は必ず店の買値より安く設定する（村で買って出荷＝転売で儲からないように）。
# 育てて/釣って手に入れる産物は、種やエサの費用より高く＝生産すれば利益が出るように。
BASE_VALUE = {
    # 作物（店で買える食材は買値より安く）
    "木の実": 7, "薬草": 6, "キノコ": 10,
    # 畜産
    "卵": 8, "ミルク": 9,
    # 魚・海産（店で買えないので少し高め）
    "魚": 12, "大魚": 24, "フグ": 14, "貝": 11,
    # その他食材
    "肉": 12, "イモ": 6, "果実": 10, "チーズ": 11, "蜂蜜": 10, "携帯食料": 18,
    # 種（転売不可＝安い。育てて売る前提）
    "木の実の種": 3, "薬草の種": 3, "キノコの種": 4,
    # 素材
    "スライムのかけら": 5, "ゴブリンの爪": 7, "毒キノコ": 4, "エサ": 3, "飼料": 4,
    "ニワトリ": 30, "ウシ": 55,
}
CATEGORY_VALUE = {
    item_category.ItemCategory.CONSUMABLE: 20,   # 料理など（材料費以下に）
    item_category.ItemCategory.MATERIAL: 8,
    item_category.ItemCategory.WEAPON: 30,
    item_category.ItemCategory.ARMOR: 30,
    item_category.ItemCategory.AMMO: 2,
}


def is_sellable(item) -> bool:
    """出荷できるか（大切なものは売れない）。"""
    return item_category.category_of(item) != item_category.ItemCategory.KEY


def sell_value(item) -> int:
    """出荷したときの売値（品質・数量込み）。"""
    base = BASE_VALUE.get(item.name)
    if base is None:
        base = CATEGORY_VALUE.get(item_category.category_of(item), 10)
    v = int(base * QUALITY_MULT[quality_of(item)])
    return max(1, v) * max(1, getattr(item, "count", 1))


# ---- 図鑑（コレクション）----
# 収集カテゴリ → 対象名の一覧（自分で育てて/釣って/作って手に入れると記録）
COLLECTIBLES = {
    "作物": ["木の実", "薬草", "キノコ", "イモ", "果実"],
    "畜産": ["卵", "ミルク"],
    "魚介": ["魚", "大魚", "フグ", "貝"],
}
COLLECT_ALL = [n for names in COLLECTIBLES.values() for n in names]
# 全種収集の達成報酬（経験値）。一度だけ付与。
COLLECTION_REWARD = 500


# ---- 設備アップグレード ----
# facility -> (表示名, [各段の説明], 各段のXPコスト)
UPGRADES = {
    "storage": ("収納の拡張", ["持ち物+6", "持ち物+12", "持ち物+18"], [200, 400, 700]),
    "cooking": ("かまどの改良", ["料理+10%", "料理+20%", "料理+30%"], [200, 400, 700]),
}
MAX_UPGRADE = 3
STORAGE_PER_LEVEL = 6       # 収納拡張1段あたりの持ち物枠増
COOKING_PER_LEVEL = 0.10    # かまど改良1段あたりの料理効果倍率
