# Roguelike（仮）

Python + [tcod](https://python-tcod.readthedocs.io/) で作る、風来のシレン系ローグライク。
将来的に **敵AIへ強化学習を導入**し、**Steam公開**を目指す。

## 必要環境

- Python 3.9+
- 依存ライブラリ：`pip3 install -r requirements.txt`（tcod, numpy）

## 実行

```bash
python3 main.py
```

## 操作

| キー | 動作 |
|------|------|
| 矢印キー | 移動（敵に向かって移動すると攻撃） |
| ESC | 終了 |

## モジュール構成

| ファイル | 役割 |
|----------|------|
| `main.py` | 起動（エントリーポイント） |
| `engine.py` | ゲーム状態の保持・ターン処理・描画の司令塔 |
| `entity.py` | プレイヤー/敵/アイテムの共通クラス（テンプレート複製対応） |
| `entity_factories.py` | 敵・プレイヤーの定義集（ステータス調整はここ） |
| `actions.py` | 行動（移動・攻撃・ぶつかり判定）をデータとして表現 |
| `input_handlers.py` | キー入力 → Action への変換 |
| `tile_types.py` | 床・壁などタイルの定義 |
| `game_map.py` | マップ配列とエンティティの保持・描画 |
| `procgen.py` | ランダムダンジョン生成・敵配置 |
| `components/ai.py` | 敵の頭脳（経路探索AI。★RLの差し替え地点） |
| `components/fighter.py` | 戦闘ステータス（HP・攻撃力・防御力） |

## ロードマップ

- [x] マップ生成 / 移動 / 衝突判定
- [x] 敵の配置 / ターン制AI（経路探索）
- [x] 戦闘（HP・ダメージ・撃破）
- [ ] メッセージログ（戦闘表示を画面内へ）
- [ ] 視界（FOV）
- [ ] アイテム（拾う・使う）
- [ ] 階段 / 複数フロア
- [ ] 強化学習による敵AI
- [ ] Steam配布（PyInstaller）

## 強化学習の設計メモ

- `components/ai.py` の `HostileEnemy.perform()` が敵の行動決定。**ここをRLの方策に差し替える**のが最終目標。
- `engine.handle_enemy_turns()` がRL環境の `step()` に相当。
- `engine.render()` を呼ばなければ **headless（画面なし）で高速に学習**できる。
