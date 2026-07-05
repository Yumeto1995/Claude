"""隠し栄養システム：食事で現実同等の栄養素を蓄積し、偏ると欠乏症状（デバフ）、
バランス良好なら好調（バフ）。値は隠しパラメータ（拠点で大まかに確認できる）。

栄養素データ（食材→栄養）は料理システム(cooking)とも共有する単一情報源。
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

# 栄養素キー → 表示名（順序＝表示順）
NUTRIENTS: Dict[str, str] = {
    "protein": "たんぱく質",
    "fat": "脂質",
    "carb": "炭水化物",
    "vitA": "ビタミンA",
    "vitB": "ビタミンB群",
    "vitC": "ビタミンC",
    "iron": "鉄分",
    "calcium": "カルシウム",
}
KEYS: List[str] = list(NUTRIENTS.keys())

# 食材ごとの栄養素（未記載は0）。tox は毒性（料理の食中毒判定用）。
FOOD_NUTRITION: Dict[str, Dict[str, int]] = {
    "リンゴ":   {"carb": 16, "fat": 18, "protein": 4, "vitB": 6, "calcium": 4},
    "薬草":     {"vitC": 20, "vitA": 16, "calcium": 8, "iron": 4},
    "キノコ":   {"vitB": 14, "protein": 6, "iron": 4, "tox": 5},
    "肉":       {"protein": 28, "fat": 12, "iron": 14, "vitB": 10, "tox": 4},
    "毒キノコ": {"vitB": 8, "protein": 4, "tox": 22},
    "卵":       {"protein": 14, "fat": 10, "vitA": 10, "vitB": 8, "calcium": 6},
    "ミルク":   {"protein": 8, "fat": 8, "calcium": 18, "vitA": 8, "vitB": 6},
    "魚":       {"protein": 22, "fat": 8, "calcium": 10, "vitB": 6, "vitA": 4, "iron": 4},
    "大魚":     {"protein": 34, "fat": 14, "iron": 8, "vitB": 8, "calcium": 8},
    "フグ":     {"protein": 24, "calcium": 6, "tox": 18},
    "携帯食料": {"carb": 22, "protein": 8, "fat": 10, "vitB": 2},
    # 追加食材（栄養ニッチ）
    "イモ":     {"carb": 24, "vitC": 8, "fat": 2},          # 炭水化物の塊
    "果実":     {"vitC": 22, "carb": 14, "vitA": 6},        # 2つめのビタミンC源
    "貝":       {"calcium": 16, "iron": 12, "protein": 14, "tox": 3},  # カルシウム＋鉄
    "チーズ":   {"calcium": 22, "fat": 16, "protein": 12},  # 日持ちするカルシウム源
    "蜂蜜":     {"carb": 28},                                # 超日持ちの炭水化物
}

# 蓄積ストアの範囲としきい値
MAX = 100.0
START = 70.0
LOW = 20.0       # これ未満で欠乏症状を発症
RECOVER = 32.0   # ここまで戻ると症状解消（ヒステリシス）
GOOD = 50.0      # 全栄養がこれ以上で「好調」バフ
EAT_SCALE = 0.5  # 食事1回で profile×この倍率を蓄積（満腹度とは別系統）

# 1ターンあたりの減衰（マクロは速く、微量栄養は遅い）。
# テスターの自動プレイで調整：偏食を続けたときの欠乏発症が、炭水化物（主燃料）で
# 概ね floor2（約190ターン）、脂質/たんぱく質で floor3、微量栄養は floor4〜6 と
# なるよう設定。満腹度が尽きる前に欠乏で floor1 から詰む…を避けつつ、偏った食事は
# 中盤以降じわじわ響く。バランス良く食べれば「好調」バフを維持できる。
DECAY: Dict[str, float] = {
    "carb": 0.21, "fat": 0.16, "protein": 0.13,
    "vitA": 0.09, "vitB": 0.11, "vitC": 0.11, "iron": 0.08, "calcium": 0.08,
}

# 欠乏症状名（栄養キー → 症状）
SYMPTOMS: Dict[str, str] = {
    "protein": "筋力低下",
    "fat": "エネルギー不足",
    "carb": "燃料切れ",
    "vitA": "夜盲症",
    "vitB": "脚気",
    "vitC": "壊血病",
    "iron": "貧血",
    "calcium": "骨の弱り",
}


def profile_for(name: str) -> Dict[str, int]:
    """食べ物の名前 → 栄養プロファイル（無ければ空）。料理は dish 側が栄養を持つ。"""
    return FOOD_NUTRITION.get(name, {})


class Nutrition:
    """プレイヤーの隠し栄養状態。各栄養素の蓄積量を持ち、食事で増え時間で減る。"""

    entity = None  # 所有者（Entity 側で設定）

    def __init__(self):
        self.stores: Dict[str, float] = {k: START for k in KEYS}
        self.deficient: Set[str] = set()  # 発症中の欠乏（ヒステリシス管理）

    def eat(self, profile: Dict[str, int], scale: float = EAT_SCALE) -> None:
        """食べ物の栄養を蓄積（上限 MAX）。"""
        for k in KEYS:
            amt = profile.get(k, 0)
            if amt:
                self.stores[k] = min(MAX, self.stores[k] + amt * scale)

    def decay(self) -> None:
        """1ターン分、各栄養を減衰。"""
        for k in KEYS:
            self.stores[k] = max(0.0, self.stores[k] - DECAY[k])

    def update_symptoms(self) -> List[Tuple[str, str, str]]:
        """欠乏の発症/回復を判定。(キー, 'onset'|'recover', 症状名) の変化リストを返す。"""
        changes: List[Tuple[str, str, str]] = []
        for k in KEYS:
            lvl = self.stores[k]
            if k not in self.deficient and lvl < LOW:
                self.deficient.add(k)
                changes.append((k, "onset", SYMPTOMS[k]))
            elif k in self.deficient and lvl >= RECOVER:
                self.deficient.discard(k)
                changes.append((k, "recover", SYMPTOMS[k]))
        return changes

    @property
    def is_good(self) -> bool:
        """全栄養が GOOD 以上＝好調。"""
        return all(self.stores[k] >= GOOD for k in KEYS)

    # --- 効果（fighter / engine が参照する補正値） ---
    @property
    def power_mod(self) -> int:
        m = -2 if "protein" in self.deficient else 0
        return m + (1 if self.is_good else 0)

    @property
    def defense_mod(self) -> int:
        m = 0
        if "vitC" in self.deficient:
            m -= 2
        if "calcium" in self.deficient:
            m -= 1
        return m + (1 if self.is_good else 0)

    @property
    def stamina_regen_mult(self) -> float:
        # 現実の欠乏症状に対応：脂質＝エネルギー不足、炭水化物＝主燃料切れ、
        # 脚気(vitB)＝神経・筋の疲労、貧血(iron)＝酸素運搬低下による易疲労。
        m = 1.0
        if "fat" in self.deficient:
            m *= 0.6
        if "carb" in self.deficient:
            m *= 0.8   # 炭水化物＝主要エネルギー源。切れると疲れやすい
        if "vitB" in self.deficient:
            m *= 0.6
        if "iron" in self.deficient:
            m *= 0.7   # 貧血＝酸素が回らず持久力低下
        return m * (1.15 if self.is_good else 1.0)

    def hp_regen_interval(self, base: int) -> int:
        """歩行によるHP自然回復の間隔（ターン）。返り値が大きいほど回復が遅い。

        現実の創傷治癒に必要な栄養が欠けると治りが遅れる：たんぱく質＝組織修復の材料、
        ビタミンC＝コラーゲン生成（壊血病では傷が治らない）。好調なら少し速い。"""
        mult = 1.0
        if "protein" in self.deficient:
            mult *= 2.0    # たんぱく質不足＝組織修復の材料切れ
        if "vitC" in self.deficient:
            mult *= 1.5    # 壊血病＝コラーゲン生成障害で創傷治癒が滞る
        interval = base * mult
        if self.is_good:
            interval *= 0.7
        return max(1, int(round(interval)))

    @property
    def satiety_drain_add(self) -> int:
        """炭水化物欠乏で満腹の減りが速くなる追加消費。"""
        return 1 if "carb" in self.deficient else 0

    @property
    def fov_penalty(self) -> int:
        """ビタミンA欠乏（夜盲症）で視界が狭まるマス数。"""
        return 2 if "vitA" in self.deficient else 0

    def status_label(self, k: str) -> str:
        """拠点表示用：栄養ごとの大まかな状態。"""
        lvl = self.stores[k]
        if lvl < LOW:
            return "欠乏"
        if lvl < GOOD:
            return "不足"
        if lvl < 80:
            return "良好"
        return "充実"
