"""スキルツリー。

9系統（攻撃・防御・運・料理・農業・漁業・酪農・錬金・魔法）。各系統は3段
（心得→鍛錬→極意）で、下の段から順に解放する。レベルアップで手に入る
スキルポイントを使って解放する。

★レベルダウン時の仕様：
  各レベルに到達／そのレベルでポイントを使うたびに「そのレベル時点の構成」を
  スナップショットする。レベルが下がったら、下がった先のレベルのスナップショットに
  戻す（それより上のスナップショットは破棄）。お金（＝経験値）を使ってレベルが
  下がると、その分のスキルも巻き戻る。
"""
from __future__ import annotations

import random
from typing import Dict, List, Tuple

POINTS_PER_LEVEL = 1   # レベルアップ1回で得るスキルポイント
TIERS = 4              # 各系統の段数（心得→鍛錬→極意→奥義）
MEDICINE_XP_COST = 1000  # 医術「自己診断」の習得に必要な経験値（お金）

# 系統キー → (表示名, 各段の効果説明)
BRANCHES: List[Tuple[str, str]] = [
    ("attack", "攻撃"),
    ("defense", "防御"),
    ("luck", "運"),
    ("cooking", "料理"),
    ("farming", "農業"),
    ("fishery", "漁業"),
    ("ranch", "酪農"),
    ("alchemy", "錬金"),
    ("magic", "魔法"),
    ("medicine", "医術"),
]
BRANCH_KEYS = [b for b, _ in BRANCHES]
BRANCH_LABEL = dict(BRANCHES)

# 段ごとの効果説明（rank1,2,3）
# 効果説明（短め。系統名は列見出しにあるので数値中心）
TIER_DESC = {
    "attack": ["攻+1", "攻+2", "攻+3", "攻+4・吸血"],
    "defense": ["防+1", "防+2", "防+3", "防+4・軽減"],
    "luck": ["会心6%", "会心12%", "会心20%", "会心30%・回避"],
    "cooking": ["効果+15%", "効果+30%", "効果+50%", "効果+80%"],
    "farming": ["成長-15%", "成長-30%", "成長-45%", "成長-60%"],
    "fishery": ["釣果+", "釣果++", "入れ食い", "入れ食い++"],
    "ranch": ["産出-15%", "産出-30%", "産出-45%", "産出-60%"],
    "alchemy": ["おまけ20%", "おまけ40%", "おまけ60%", "おまけ80%"],
    "magic": ["威力+20%", "威力+40%", "威力+70%", "威力+100%"],
    "medicine": ["自己診断", "—", "—", "—"],
}
TIER_NAME = ["心得", "鍛錬", "極意", "奥義"]


def node_id(branch: str, tier: int) -> str:
    return f"{branch}{tier}"


def node_name(branch: str, tier: int) -> str:
    return f"{BRANCH_LABEL[branch]}の{TIER_NAME[tier]}"


def node_desc(branch: str, tier: int) -> str:
    return TIER_DESC[branch][tier]


# rank(1..4) → 倍率/値（index0 は未解放。4段目＝奥義）
_CRIT = [0.0, 0.06, 0.12, 0.20, 0.30]
_COOK = [1.0, 1.15, 1.30, 1.50, 1.80]
_MAGIC = [1.0, 1.20, 1.40, 1.70, 2.00]
_GROWTH = [1.0, 0.85, 0.70, 0.55, 0.40]   # 歩数の倍率（小さいほど速い）
_ALCHEMY = [0.0, 0.20, 0.40, 0.60, 0.80]  # おまけ生成の確率
# 奥義（4段目到達）で解放される新メカニクス
_DODGE = 0.20       # 運の奥義：被攻撃を確率で完全回避
_LIFESTEAL = 0.25   # 攻撃の奥義：与ダメージの割合を回復
_DMG_REDUCE = 0.25  # 防御の奥義：被ダメージの軽減割合


class Skills:
    """プレイヤーの習得状況。Entity.skills として持たせ、Level と連携する。"""

    entity = None  # 所有者（Entity 側で設定）

    def __init__(self):
        self.unlocked = set()      # 解放済みノードID
        self.points = 0            # 未使用ポイント
        self.self_diagnosis = False  # 医術「自己診断」：経験値で習得・恒久（巻戻し対象外）
        # レベル → (frozenset(unlocked), points) のスナップショット
        self.snapshots: Dict[int, Tuple[frozenset, int]] = {1: (frozenset(), 0)}

    # ---- 進行（Level から呼ばれる）----
    def gain_level(self, new_level: int) -> None:
        """レベルアップ：ポイント付与し、その時点を記録。"""
        self.points += POINTS_PER_LEVEL
        self.snapshots[new_level] = (frozenset(self.unlocked), self.points)

    def revert_to(self, level: int) -> None:
        """レベルダウン：そのレベル時点の構成へ戻し、上位の記録を捨てる。"""
        snap = self.snapshots.get(level)
        if snap is None:
            # 念のため：記録が無ければ最も近い下位を採用
            lower = [lv for lv in self.snapshots if lv <= level]
            snap = self.snapshots[max(lower)] if lower else (frozenset(), 0)
        self.unlocked = set(snap[0])
        self.points = snap[1]
        for lv in [lv for lv in self.snapshots if lv > level]:
            del self.snapshots[lv]

    # ---- 解放 ----
    def is_unlocked(self, branch: str, tier: int) -> bool:
        if branch == "medicine":
            return tier == 0 and getattr(self, "self_diagnosis", False)
        return node_id(branch, tier) in self.unlocked

    def can_unlock(self, branch: str, tier: int) -> bool:
        if self.is_unlocked(branch, tier):
            return False
        if branch == "medicine":
            # 自己診断（心得のみ）。経験値（お金）1000 で習得。
            lvl = getattr(self.entity, "level", None)
            return tier == 0 and lvl is not None and lvl.wealth() >= MEDICINE_XP_COST
        if self.points < 1:
            return False
        if tier > 0 and not self.is_unlocked(branch, tier - 1):
            return False  # 下の段が未解放
        return True

    def unlock(self, branch: str, tier: int, current_level: int) -> bool:
        if branch == "medicine":
            return False  # 医術は経験値で習得（engine.skill_unlock が処理）
        if not self.can_unlock(branch, tier):
            return False
        self.unlocked.add(node_id(branch, tier))
        self.points -= 1
        # 現在レベルのスナップショットを更新（このレベルでの最新構成）
        self.snapshots[current_level] = (frozenset(self.unlocked), self.points)
        return True

    # ---- 効果（各システムが参照）----
    def rank(self, branch: str) -> int:
        return sum(1 for t in range(TIERS) if self.is_unlocked(branch, t))

    @property
    def power_bonus(self) -> int:
        return self.rank("attack")

    @property
    def defense_bonus(self) -> int:
        return self.rank("defense")

    def crit_chance(self) -> float:
        return _CRIT[self.rank("luck")]

    def cooking_mult(self) -> float:
        return _COOK[self.rank("cooking")]

    def magic_mult(self) -> float:
        return _MAGIC[self.rank("magic")]

    def growth_factor(self, branch: str) -> float:
        """農業/酪農/漁業養殖の成長歩数の倍率（小さいほど速い）。"""
        return _GROWTH[self.rank(branch)]

    def alchemy_bonus_chance(self) -> float:
        return _ALCHEMY[self.rank("alchemy")]

    # --- 奥義（各系統4段目）で解放される新メカニクス ---
    def dodge_chance(self) -> float:
        """運の奥義：被攻撃を確率で完全回避。"""
        return _DODGE if self.rank("luck") >= 4 else 0.0

    def lifesteal_frac(self) -> float:
        """攻撃の奥義：与ダメージのこの割合を回復。"""
        return _LIFESTEAL if self.rank("attack") >= 4 else 0.0

    def damage_reduction(self) -> float:
        """防御の奥義：被ダメージのこの割合を軽減。"""
        return _DMG_REDUCE if self.rank("defense") >= 4 else 0.0

    def roll(self, prob: float) -> bool:
        return prob > 0 and random.random() < prob


def of(entity) -> "Skills | None":
    """エンティティの Skills を返す（無ければ None）。"""
    return getattr(entity, "skills", None)
