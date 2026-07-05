"""プレイヤーの実戦から敵AIが随時学習するオンライン学習器（off-policy Q学習）。

同梱の基本方策 policy.npz（読み取り専用）の複製から始め、ゲーム内の戦闘で
観測した遷移 (s, a, r, s') で Q 表を更新する。Engine が1つだけ保持し、Engine
まるごと pickle されるのでセーブに含まれる。**ニューゲームでは new_default() で
基本方策のコピーへ戻る**＝“新しいデータ（新しいプレイ）”はデフォルトにリセットされる。
観測設計（POLICY_VERSION）が変わった古いセーブも、読み込み時にリセットする。

学習対象は RLEnemy が方策で判断する「隣接間合いの駆け引き（攻撃／後退／待機）」だけ。
接近は A* 任せ（方策外）なので学習しない。敵は基本グリーディに動く（探索なし）ので
挙動はブレず、実戦の遷移から少しずつ“今のプレイヤー”に適応する。
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from rl.obs import N_ACTIONS, N_STATES
from rl.qlearning import POLICY_VERSION, load_qtable

# 報酬係数（rl/env.py の ArenaEnv.R_* と揃える）。攻めて削るほど得。
R_DEALT = 3.0      # 与ダメージ1点あたり
R_TAKEN = -0.4     # 被ダメージ1点あたり
R_KILL = 40.0      # プレイヤー撃破
R_DEATH = -6.0     # 自分が倒される
R_STEP = -0.3      # 1ターン経過
R_APPROACH = 1.2   # プレイヤーへ1マス近づくごと（離れると同額減点）


class OnlineLearner:
    """基本方策のコピーを保持し、実戦の遷移で少しずつ更新する共有Q表。"""

    def __init__(self, q: np.ndarray, alpha: float = 0.05, gamma: float = 0.95):
        self.q = q               # 可変（基本方策のコピー）。全ゴブリンで共有。
        self.alpha = alpha       # 学習率は小さめ＝適応は緩やか＝挙動が暴れない
        self.gamma = gamma
        self.version = POLICY_VERSION  # 観測設計の版（古いセーブ検出＝リセット判断に使う）

    @classmethod
    def new_default(cls) -> Optional["OnlineLearner"]:
        """基本方策 policy.npz のコピーから作る。方策が無ければ None（＝RL無効）。"""
        base = load_qtable()
        if base is None:
            return None
        return cls(base.copy())

    def best_action(self, state: int) -> int:
        return int(np.argmax(self.q[state]))

    def learn(self, s: int, a: int, r: float, s2: int, done: bool) -> None:
        target = r if done else r + self.gamma * float(self.q[s2].max())
        self.q[s, a] += self.alpha * (target - self.q[s, a])
