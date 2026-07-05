"""表形式Q学習のエージェントと、方策ファイル（policy.npz）の保存/読み込み。

Q(s, a) を numpy の2次元配列で持ち、
    Q[s,a] ← Q[s,a] + α (r + γ max_a' Q[s',a'] − Q[s,a])
で更新するだけの最小構成。依存は numpy のみ。
"""
from __future__ import annotations

import os
import random
from typing import Optional

import numpy as np

from rl.obs import N_ACTIONS, N_STATES

# 方策ファイルの置き場所（ゲーム本体の RLEnemy もここを読む）
POLICY_PATH = os.path.join(os.path.dirname(__file__), "policy.npz")
POLICY_VERSION = 2  # 観測の設計を変えたら上げる（古い方策の誤読み込み防止）
#   v2: 最寄り味方の方向を状態に追加（群れ連携）。N_STATES 1458→13122。


class QLearningAgent:
    def __init__(
        self,
        alpha: float = 0.1,    # 学習率
        gamma: float = 0.95,   # 割引率
        epsilon: float = 1.0,  # ε-greedy の探索率（学習中に減衰させる）
        seed: Optional[int] = None,
    ):
        self.q = np.zeros((N_STATES, N_ACTIONS), dtype=np.float32)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = random.Random(seed)

    def act(self, state: int, greedy: bool = False) -> int:
        """ε-greedy で行動を選ぶ。greedy=True なら常に最善手（評価・本番用）。"""
        if not greedy and self.rng.random() < self.epsilon:
            return self.rng.randrange(N_ACTIONS)
        return int(np.argmax(self.q[state]))

    def update(self, s: int, a: int, r: float, s2: int, done: bool) -> None:
        target = r if done else r + self.gamma * float(self.q[s2].max())
        self.q[s, a] += self.alpha * (target - self.q[s, a])

    def save(self, path: str = POLICY_PATH) -> None:
        np.savez(path, q=self.q, version=POLICY_VERSION,
                 n_states=N_STATES, n_actions=N_ACTIONS)


def load_qtable(path: str = POLICY_PATH) -> Optional[np.ndarray]:
    """学習済みQテーブルを読み込む。無い・形が合わない場合は None。"""
    if not os.path.exists(path):
        return None
    try:
        data = np.load(path)
        if int(data["version"]) != POLICY_VERSION:
            return None  # 観測設計が古い方策は使わない
        q = data["q"]
        if q.shape != (N_STATES, N_ACTIONS):
            return None
        return q
    except Exception:
        return None
