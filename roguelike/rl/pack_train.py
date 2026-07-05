"""群れ戦術のQ学習トレーナー（複数敵アリーナ）。

使い方（roguelike ディレクトリで）:
    python3 -m rl.pack_train                    # 既定で学習して保存
    python3 -m rl.pack_train --episodes 5000    # 短く試す
    python3 -m rl.pack_train --eval-only        # 保存済み方策を評価だけ

全ゴブリンが同じQ表を共有し、各自 ε-greedy で動いて各自の報酬でQを更新する
（独立Q学習＝IQL＋パラメータ共有）。撃破報酬は群れ全員に入る＝連携すると得。

評価は「群れQ学習」と「群れベースライン（全員ひたすら最短で近づいて殴る）」を
同じ条件で回し、**プレイヤー撃破率（勝率）**・平均報酬・平均生存数などを比べる。
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from rl.obs import ACTIONS
from rl.pack_env import PackArenaEnv
from rl.qlearning import QLearningAgent, load_qtable

EPSILON_FINAL = 0.05
PACK_POLICY_PATH = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "pack_policy.npz")


def baseline_action(env: PackArenaEnv, agent) -> int:
    """ベースライン：プレイヤーへ一直線に近づき、隣接したら攻撃（全員同じ）。"""
    p = env.engine.player
    dx, dy = p.x - agent.x, p.y - agent.y
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    return ACTIONS.index((sx, sy)) if (sx, sy) != (0, 0) else 8


def run_episode(env: PackArenaEnv, act_fn) -> dict:
    """1エピソード。act_fn(state, agent) → 行動番号。greedy 評価にも学習にも使う。"""
    states = env.reset()
    done_all = False
    total = 0.0
    while not done_all:
        actions = [act_fn(states[i], env.agents[i]) for i in range(len(env.agents))]
        states, rewards, dones, info = env.step(actions)
        total += sum(rewards)
        done_all = info["done_all"]
    survivors = sum(1 for g in env.agents if g.fighter.hp > 0)
    return {
        "reward": total,
        "win": info["player_dead"],          # プレイヤーを倒せたか
        "survivors": survivors,
        "steps": info["steps"],
    }


def evaluate(env: PackArenaEnv, act_fn, episodes: int, label: str) -> dict:
    stats = [run_episode(env, act_fn) for _ in range(episodes)]
    avg = {k: float(np.mean([s[k] for s in stats]))
           for k in ("reward", "win", "survivors", "steps")}
    print(
        f"  {label:<14} 勝率 {avg['win']*100:5.1f}%"
        f" / 群れ報酬 {avg['reward']:7.2f} / 平均生存 {avg['survivors']:.2f}体"
        f" / ターン {avg['steps']:5.1f}"
    )
    return avg


def train(episodes: int, n_agents: int, seed: int = 0,
          vary_agents: bool = False) -> QLearningAgent:
    env = PackArenaEnv(n_agents=n_agents, vary_agents=vary_agents, seed=seed)
    agent = QLearningAgent(seed=seed)   # 全ゴブリンで共有する1つのQ表
    decay_until = int(episodes * 0.8)
    report_every = max(1, episodes // 10)
    window = []
    t0 = time.time()

    for ep in range(1, episodes + 1):
        agent.epsilon = max(
            EPSILON_FINAL, 1.0 - (1.0 - EPSILON_FINAL) * ep / max(1, decay_until))
        states = env.reset()
        n = len(env.agents)
        prev_alive = [True] * n
        done_all = False
        total = 0.0
        while not done_all:
            actions = [agent.act(states[i]) for i in range(n)]
            next_states, rewards, dones, info = env.step(actions)
            # このステップの開始時に生きていたゴブリンだけQ更新（共有表を全員で更新）
            for i in range(n):
                if prev_alive[i]:
                    agent.update(states[i], actions[i], rewards[i],
                                 next_states[i], dones[i])
            prev_alive = [g.fighter.hp > 0 for g in env.agents]
            states = next_states
            total += sum(rewards)
            done_all = info["done_all"]
        window.append(total)

        if ep % report_every == 0:
            print(f"ep {ep:>6}/{episodes}  直近{len(window)}本の平均群れ報酬 "
                  f"{np.mean(window):7.2f}  (ε={agent.epsilon:.2f})")
            window = []
    print(f"学習時間: {time.time() - t0:.1f} 秒")
    return agent


def main() -> None:
    parser = argparse.ArgumentParser(description="群れ戦術のQ学習")
    parser.add_argument("--episodes", type=int, default=30000)
    parser.add_argument("--n-agents", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-episodes", type=int, default=500)
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--vary-agents", action="store_true",
                        help="毎エピソード1..n_agents体を抽選（ソロも学習に混ぜる）")
    parser.add_argument("--out", default=PACK_POLICY_PATH)
    args = parser.parse_args()

    if args.eval_only:
        q = load_qtable(args.out)
        if q is None:
            print(f"方策ファイルがありません: {args.out}")
            return
    else:
        agent = train(args.episodes, args.n_agents, seed=args.seed,
                      vary_agents=args.vary_agents)
        agent.save(args.out)
        print(f"方策を保存: {args.out}")
        q = agent.q

    print(f"--- 評価（greedy・{args.eval_episodes}エピソード・{args.n_agents}体）---")
    env = PackArenaEnv(n_agents=args.n_agents, seed=args.seed + 1)
    evaluate(env, lambda s, g: int(np.argmax(q[s])), args.eval_episodes, "群れQ学習")
    env2 = PackArenaEnv(n_agents=args.n_agents, seed=args.seed + 1)
    evaluate(env2, lambda s, g: baseline_action(env2, g),
             args.eval_episodes, "群れベースライン")


if __name__ == "__main__":
    main()
