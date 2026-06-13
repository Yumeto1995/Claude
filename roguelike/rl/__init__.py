"""強化学習（敵AI）パッケージ。

- obs.py       : 観測のエンコードと行動の定義（学習と本番で共有）
- env.py       : 1対1の戦闘アリーナ環境（gym風 reset/step、描画なし）
- qlearning.py : 表形式Q学習のエージェントと方策ファイルの保存/読み込み
- train.py     : 学習スクリプト（python3 -m rl.train）

学習済み方策は rl/policy.npz に保存され、components/ai.py の RLEnemy が
起動時に読み込む（無ければ従来のA*追跡にフォールバック）。
"""
