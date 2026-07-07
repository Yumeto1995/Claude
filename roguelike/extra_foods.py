"""追加食材のデータテーブル（単一情報源）。現実の食材を幅広く増やし、栄養の偏りを無くす。

各エントリ:
  nut   … 栄養プロファイル（nutrition.py の8栄養＋tox）。未記載は0。
  sat   … 満腹回復量（FoodConsumable.amount）。
  shelf … 日持ち（歩数）。傷みやすい生鮮は短く、乾物・保存食は長い。
  sprite… アイコンキー（assets/items/<sprite>.png）。
  plant … 栽培種別。"fruit"=果物(株が残り再収穫) / "veg"=野菜(収穫で種) /
          "grain"=穀物(野菜と同じ扱い) / None=栽培不可(ドロップ/畜産/漁業/加工で入手)。
  steps … 栽培の収穫までの歩数（plant がある時）。

entity_factories / nutrition / farming / procgen がこのテーブルを取り込む。
栄養値は既存食材（肉=protein28 等）と同じスケール。
"""

FOODS = {
    # ---- 果物（vitC・vitA・炭水化物。株が残り再収穫）----
    "バナナ":   {"nut": {"carb": 22, "vitB": 6, "calcium": 2},              "sat": 20, "shelf": 90,  "sprite": "food_fruit",  "plant": "fruit", "steps": 55},
    "オレンジ": {"nut": {"vitC": 22, "carb": 12, "calcium": 4},             "sat": 16, "shelf": 110, "sprite": "food_berry",  "plant": "fruit", "steps": 55},
    "ブドウ":   {"nut": {"carb": 18, "vitC": 8, "iron": 3},                 "sat": 14, "shelf": 80,  "sprite": "food_berry",  "plant": "fruit", "steps": 50},
    "イチゴ":   {"nut": {"vitC": 24, "carb": 8},                            "sat": 12, "shelf": 60,  "sprite": "food_berry",  "plant": "fruit", "steps": 45},
    "モモ":     {"nut": {"vitA": 10, "carb": 14, "vitC": 8},                "sat": 16, "shelf": 70,  "sprite": "food_fruit",  "plant": "fruit", "steps": 55},
    "カキ":     {"nut": {"vitA": 14, "vitC": 12, "carb": 12},               "sat": 18, "shelf": 100, "sprite": "food_fruit",  "plant": "fruit", "steps": 60},
    "スイカ":   {"nut": {"carb": 14, "vitA": 6, "vitC": 8},                 "sat": 22, "shelf": 70,  "sprite": "food_fruit",  "plant": "fruit", "steps": 60},

    # ---- 野菜（vitA・vitC・鉄・カルシウム。収穫で種が採れる）----
    "ニンジン":     {"nut": {"vitA": 24, "carb": 10, "fat": 1},             "sat": 16, "shelf": 260, "sprite": "food_carrot", "plant": "veg", "steps": 55},
    "カボチャ":     {"nut": {"vitA": 22, "carb": 18, "vitC": 6},            "sat": 26, "shelf": 320, "sprite": "food_carrot", "plant": "veg", "steps": 65},
    "ダイコン":     {"nut": {"vitC": 12, "calcium": 4, "carb": 6},          "sat": 18, "shelf": 220, "sprite": "food_carrot", "plant": "veg", "steps": 55},
    "タマネギ":     {"nut": {"carb": 10, "vitC": 6, "iron": 3},             "sat": 14, "shelf": 300, "sprite": "food_carrot", "plant": "veg", "steps": 50},
    "キャベツ":     {"nut": {"vitC": 18, "calcium": 8, "vitA": 4},          "sat": 16, "shelf": 180, "sprite": "food_leafy",  "plant": "veg", "steps": 55},
    "ホウレンソウ": {"nut": {"iron": 16, "vitA": 14, "calcium": 10, "vitC": 8}, "sat": 12, "shelf": 120, "sprite": "food_leafy", "plant": "veg", "steps": 50},
    "ブロッコリー": {"nut": {"vitC": 20, "calcium": 8, "iron": 6, "vitA": 6}, "sat": 16, "shelf": 130, "sprite": "food_leafy", "plant": "veg", "steps": 55},
    "トマト":       {"nut": {"vitC": 14, "vitA": 8, "carb": 4},             "sat": 14, "shelf": 110, "sprite": "food_tomato", "plant": "veg", "steps": 55},
    "ナス":         {"nut": {"carb": 8, "vitB": 4, "vitC": 4},              "sat": 14, "shelf": 150, "sprite": "food_tomato", "plant": "veg", "steps": 55},
    "ピーマン":     {"nut": {"vitC": 22, "vitA": 6},                        "sat": 12, "shelf": 140, "sprite": "food_tomato", "plant": "veg", "steps": 50},

    # ---- 穀物（炭水化物の主力。乾物で日持ち。畑で育つ）----
    "米":   {"nut": {"carb": 28, "protein": 6},                            "sat": 30, "shelf": 500, "sprite": "food_grain", "plant": "grain", "steps": 70},
    "麦":   {"nut": {"carb": 24, "protein": 8, "iron": 4, "vitB": 4},      "sat": 28, "shelf": 500, "sprite": "food_grain", "plant": "grain", "steps": 70},
    "トウモロコシ": {"nut": {"carb": 22, "protein": 6, "fat": 4, "vitA": 4}, "sat": 26, "shelf": 300, "sprite": "food_grain", "plant": "grain", "steps": 65},

    # ---- 豆類（たんぱく質・鉄・脂質。畑で育つ）----
    "大豆": {"nut": {"protein": 20, "fat": 10, "calcium": 8, "iron": 6},   "sat": 20, "shelf": 500, "sprite": "food_nuts", "plant": "veg", "steps": 60},
    "豆":   {"nut": {"protein": 16, "iron": 8, "carb": 10, "calcium": 6},  "sat": 18, "shelf": 450, "sprite": "food_nuts", "plant": "veg", "steps": 55},

    # ---- 木の実・加工（栽培不可。採取/加工で入手）----
    "ナッツ":   {"nut": {"fat": 22, "protein": 10, "iron": 4, "vitB": 4},  "sat": 18, "shelf": 600, "sprite": "food_nuts",  "plant": None},
    "クルミ":   {"nut": {"fat": 24, "protein": 8, "calcium": 6},           "sat": 18, "shelf": 600, "sprite": "food_nuts",  "plant": None},
    "パン":     {"nut": {"carb": 24, "protein": 6, "fat": 4},              "sat": 34, "shelf": 250, "sprite": "food_bread", "plant": None},
    "モチ":     {"nut": {"carb": 30, "protein": 4},                        "sat": 36, "shelf": 300, "sprite": "food_bread", "plant": None},
    "バター":   {"nut": {"fat": 24, "vitA": 12, "calcium": 4},             "sat": 20, "shelf": 260, "sprite": "food_cheese", "plant": None},
    "ヨーグルト": {"nut": {"calcium": 16, "protein": 10, "vitB": 6, "fat": 4}, "sat": 16, "shelf": 160, "sprite": "food_milk", "plant": None},

    # ---- 肉（たんぱく質・鉄・vitB・vitA。ドロップ/畜産）----
    "鶏肉":   {"nut": {"protein": 26, "fat": 8, "vitB": 8},                "sat": 22, "shelf": 130, "sprite": "food_meat", "plant": None},
    "猪肉":   {"nut": {"protein": 30, "fat": 16, "iron": 12, "vitB": 10},  "sat": 26, "shelf": 120, "sprite": "food_meat", "plant": None},
    "レバー": {"nut": {"vitA": 24, "iron": 20, "vitB": 14, "protein": 18}, "sat": 18, "shelf": 90,  "sprite": "food_meat", "plant": None},

    # ---- 魚介（たんぱく質・カルシウム・鉄・vitA。漁業）----
    "エビ":   {"nut": {"protein": 18, "calcium": 12, "vitB": 4},           "sat": 16, "shelf": 110, "sprite": "food_shellfish", "plant": None},
    "カニ":   {"nut": {"protein": 16, "calcium": 14, "iron": 6, "vitB": 4}, "sat": 18, "shelf": 100, "sprite": "food_shellfish", "plant": None},
    "イカ":   {"nut": {"protein": 20, "vitB": 6, "iron": 4},               "sat": 16, "shelf": 110, "sprite": "food_fish", "plant": None},
    "タコ":   {"nut": {"protein": 22, "iron": 8, "calcium": 6},            "sat": 18, "shelf": 110, "sprite": "food_fish", "plant": None},
    "海藻":   {"nut": {"calcium": 18, "iron": 12, "vitA": 10, "vitB": 6},  "sat": 12, "shelf": 400, "sprite": "food_leafy", "plant": None},
}
