"""敵AIのQ学習トレーナー。

使い方（roguelike ディレクトリで）:
    python3 -m rl.train                     # 既定 30000 エピソード学習して保存
    python3 -m rl.train --episodes 5000     # 短く試す
    python3 -m rl.train --eval-only         # 保存済み方策を評価だけする

学習後に rl/policy.npz が保存され、次回のゲーム起動からゴブリンが
学習済み方策で動く（無ければ従来のA*追跡のまま）。

比較のため、評価時はベースライン（本編の HostileEnemy 相当：
ひたすら近づいて隣接したら殴る）も同じ条件で走らせる。
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from rl.env import ArenaEnv
from rl.obs import ACTIONS
from rl.qlearning import POLICY_PATH, QLearningAgent, load_qtable

EPSILON_FINAL = 0.05  # 減衰後の探索率


def baseline_action(env: ArenaEnv) -> int:
    """ベースライン方策：プレイヤーへ一直線に近づき、隣接したら攻撃。"""
    a, p = env.agent, env.engine.player
    dx, dy = p.x - a.x, p.y - a.y
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    return ACTIONS.index((sx, sy)) if (sx, sy) != (0, 0) else 8


def run_episode(env: ArenaEnv, policy_fn) -> dict:
    """1エピソード走らせて成績を返す。policy_fn(state) → 行動番号。"""
    state = env.reset()
    total = dealt = taken = 0.0
    done = False
    while not done:
        state, reward, done, info = env.step(policy_fn(state))
        total += reward
        dealt += info["dealt"]
        taken += info["taken"]
    return {
        "reward": total, "dealt": dealt, "taken": taken,
        "steps": info["steps"],
        "win": env.engine.player.fighter.hp <= 0,
        "survived": env.agent.fighter.hp > 0,
    }


def evaluate(env: ArenaEnv, policy_fn, episodes: int, label: str) -> dict:
    """greedy 方策で評価し、平均成績を表示して返す。"""
    stats = [run_episode(env, policy_fn) for _ in range(episodes)]
    avg = {k: float(np.mean([s[k] for s in stats]))
           for k in ("reward", "dealt", "taken", "steps", "survived")}
    print(
        f"  {label:<12} 報酬 {avg['reward']:6.2f} / 与ダメ {avg['dealt']:5.2f}"
        f" / 被ダメ {avg['taken']:5.2f} / 生存ターン {avg['steps']:5.1f}"
        f" / 生存率 {avg['survived']*100:5.1f}%"
    )
    return avg


def train(episodes: int, seed: int = 0) -> QLearningAgent:
    env = ArenaEnv(seed=seed)
    agent = QLearningAgent(seed=seed)
    decay_until = int(episodes * 0.8)  # 最初の8割で ε を 1.0 → 0.05 に減衰
    report_every = max(1, episodes // 10)
    window = []
    t0 = time.time()

    for ep in range(1, episodes + 1):
        agent.epsilon = max(
            EPSILON_FINAL, 1.0 - (1.0 - EPSILON_FINAL) * ep / max(1, decay_until)
        )
        state = env.reset()
        total = 0.0
        done = False
        while not done:
            action = agent.act(state)
            next_state, reward, done, _ = env.step(action)
            agent.update(state, action, reward, next_state, done)
            state = next_state
            total += reward
        window.append(total)

        if ep % report_every == 0:
            print(
                f"ep {ep:>6}/{episodes}  直近{len(window)}本の平均報酬 "
                f"{np.mean(window):6.2f}  (ε={agent.epsilon:.2f})"
            )
            window = []
    print(f"学習時間: {time.time() - t0:.1f} 秒")
    return agent


def main() -> None:
    parser = argparse.ArgumentParser(description="敵AIのQ学習")
    parser.add_argument("--episodes", type=int, default=30000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-episodes", type=int, default=500)
    parser.add_argument("--eval-only", action="store_true",
                        help="学習せず保存済み方策を評価だけする")
    parser.add_argument("--out", default=POLICY_PATH)
    args = parser.parse_args()

    if args.eval_only:
        q = load_qtable(args.out)
        if q is None:
            print(f"方策ファイルがありません: {args.out}")
            return
    else:
        agent = train(args.episodes, seed=args.seed)
        agent.save(args.out)
        print(f"方策を保存: {args.out}")
        q = agent.q

    print(f"--- 評価（greedy・{args.eval_episodes}エピソード）---")
    eval_env = ArenaEnv(seed=args.seed + 1)
    evaluate(eval_env, lambda s: int(np.argmax(q[s])), args.eval_episodes, "Q学習")
    eval_env2 = ArenaEnv(seed=args.seed + 1)
    evaluate(eval_env2, lambda s: baseline_action(eval_env2),
             args.eval_episodes, "ベースライン")


if __name__ == "__main__":
    main()
