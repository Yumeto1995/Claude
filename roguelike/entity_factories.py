"""エンティティのテンプレート集。ここを増やせば敵やアイテムの種類が増える。

sprite は assets/<sprite>.png に対応する。画像が無ければ graphics.py が仮タイルを生成する。
"""
from __future__ import annotations

from components.ai import BossAI, HostileEnemy, RangedEnemy, RLEnemy, SupportEnemy
from components.consumable import (
    ConfusionConsumable,
    FoodConsumable,
    HealingConsumable,
    LightningConsumable,
    TentConsumable,
    UnlockZoneConsumable,
)
from components.equipment import Equipment
from components.equippable import Equippable, EquipmentType
from components.fighter import Fighter
from components.inventory import Inventory
from components.level import Level
from entity import Entity
from item_category import ItemCategory
from nutrition import Nutrition
from skills import Skills

player = Entity(
    sprite="player",
    name="プレイヤー",
    blocks_movement=True,
    fighter=Fighter(hp=40, defense=3, power=6, max_stamina=100, max_satiety=100),
    level=Level(level_up_base=50, level_up_factor=75),
    inventory=Inventory(capacity=36),
    equipment=Equipment(),
    skills=Skills(),
    nutrition=Nutrition(),
)

# ゴブリンは強化学習の方策（rl/policy.npz）で動く。
# 方策ファイルが無ければ従来のA*追跡と同じ動きになる。
goblin = Entity(
    sprite="goblin",
    name="ゴブリン",
    blocks_movement=True,
    ai_cls=RLEnemy,
    fighter=Fighter(hp=10, defense=0, power=4),
    level=Level(xp_given=45),
)

# スライムはルールベースのまま（RLゴブリンとの行動比較用）
slime = Entity(
    sprite="slime",
    name="スライム",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=15, defense=1, power=5),
    level=Level(xp_given=60),
)

# ボス：3×3マスを占有する大型の敵。ボスフロアの主。
boss = Entity(
    sprite="boss",
    name="ゴブリンロード",
    blocks_movement=True,
    ai_cls=BossAI,
    fighter=Fighter(hp=90, defense=3, power=9),
    level=Level(xp_given=300),
    size=3,
)

# --- 追加の敵（シレン系＝近接主体・遠距離少数・支援はさらに少数、の比率を参考に編成）---
# 近距離（HostileEnemy：近づいて殴る）
orc = Entity(
    sprite="orc", name="オーク", blocks_movement=True, ai_cls=HostileEnemy,
    fighter=Fighter(hp=20, defense=2, power=7), level=Level(xp_given=90),
)
bat = Entity(   # 弱いが数で押す群れ敵
    sprite="bat", name="コウモリ", blocks_movement=True, ai_cls=HostileEnemy,
    fighter=Fighter(hp=6, defense=0, power=3), level=Level(xp_given=30),
)
# 遠距離（RangedEnemy：射線が通れば離れて撃ち、近づかれたら退く）
goblin_archer = Entity(
    sprite="goblin_archer", name="ゴブリン弓兵", blocks_movement=True, ai_cls=RangedEnemy,
    fighter=Fighter(hp=10, defense=0, power=5), level=Level(xp_given=75),
)
goblin_mage = Entity(   # 魔法弾。低HP高火力
    sprite="goblin_mage", name="ゴブリン魔道士", blocks_movement=True, ai_cls=RangedEnemy,
    fighter=Fighter(hp=8, defense=0, power=5), level=Level(xp_given=90),
)
# 支援（SupportEnemy：味方を鼓舞して強化。前には出ない）
goblin_shaman = Entity(
    sprite="goblin_shaman", name="ゴブリンシャーマン", blocks_movement=True, ai_cls=SupportEnemy,
    fighter=Fighter(hp=12, defense=1, power=3), level=Level(xp_given=100),
)

# --- アイテム（blocks_movement=False：床に置かれ、踏むと拾える）---
healing_potion = Entity(
    sprite="potion",
    name="回復薬",
    blocks_movement=False,
    consumable=HealingConsumable(amount=15),
)

lightning_scroll = Entity(
    sprite="scroll",
    name="雷の巻物",
    blocks_movement=False,
    consumable=LightningConsumable(damage=20, maximum_range=6),
)

confusion_scroll = Entity(
    sprite="scroll_confuse",
    name="混乱の巻物",
    blocks_movement=False,
    consumable=ConfusionConsumable(turns=8),
)

# --- 武器・防具（装備品）---
# 武器：素手の消費は30。軽い武器ほど安く、重い武器ほど高い。
dagger = Entity(
    sprite="dagger",
    name="短剣",
    blocks_movement=False,
    # 軽い：攻撃力控えめだがスタミナ消費が少なく手数で攻める
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=3, stamina_cost=14, crit_chance=0.10),
)

sword = Entity(
    sprite="sword",
    name="剣",
    blocks_movement=False,
    # 重い：高火力だがスタミナ消費が大きく、連続では振れない
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=6, stamina_cost=36, crit_chance=0.05),
)

# ボス撃破報酬：レアな大剣（剣より高火力）。ボスは倒すと床に落とす。
goblin_greatsword = Entity(
    sprite="sword",
    name="ゴブリンロードの大剣",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=9, stamina_cost=30, crit_chance=0.08),
)
boss.loot = goblin_greatsword

# 追加の近接武器（短剣＜槍＜刀＜剣＜戦斧 の攻撃力／消費スタミナの階段）
spear = Entity(
    sprite="spear",
    name="槍",
    blocks_movement=False,
    # 中量：短剣と剣の中間。バランス型
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=5, stamina_cost=22, crit_chance=0.05),
)

katana = Entity(
    sprite="katana",
    name="刀",
    blocks_movement=False,
    # 侍向け：高火力なのに軽快（1点あたりの消費が軽い）
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=7, stamina_cost=26, crit_chance=0.15),
)

battle_axe = Entity(
    sprite="axe",
    name="戦斧",
    blocks_movement=False,
    # 最重量：大火力だが1振りが非常に重く連撃できない
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=8, stamina_cost=44, crit_chance=0.0),
)

# --- 遠距離武器・弾 ---
# 弓：ranged 枠に装備（近接武器と両立）。矢を1本消費して直線上の最初の敵を射る。
bow = Entity(
    sprite="bow",
    name="弓",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.RANGED, power_bonus=4, stamina_cost=20, max_range=6, crit_chance=0.05),
)

# クロスボウ：弓より高威力だが重く（消費大）、射程はやや短い。矢を共用する。
crossbow = Entity(
    sprite="crossbow",
    name="クロスボウ",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.RANGED, power_bonus=7, stamina_cost=34, max_range=5, crit_chance=0.12),
)

# 矢：スタックする弾。count 本まとめて1スロット。撃つたびに1減り、0で尽きる。
arrow = Entity(
    sprite="arrow",
    name="矢",
    blocks_movement=False,
    item_category=ItemCategory.AMMO,
)

# 防具：stamina_cost は攻撃時の追加消費（重い防具ほど攻撃が重くなる）。
leather_armor = Entity(
    sprite="leather_armor",
    name="革の鎧",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=1, stamina_cost=2),
)

chain_mail = Entity(
    sprite="chain_mail",
    name="鎖帷子",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=4, stamina_cost=6),
)

# 木の盾：盾は専用枠。鎧（革/鎖/板金）と同時に装備して防御を上乗せできる
wooden_shield = Entity(
    sprite="shield",
    name="木の盾",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.SHIELD, defense_bonus=2, stamina_cost=3),
)

# 板金鎧：最高防御だが非常に重く、攻撃のたびに大きくスタミナを食う
plate_armor = Entity(
    sprite="plate_armor",
    name="板金鎧",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=7, stamina_cost=12),
)

# --- 素材アイテム（効果なし。将来の合成用などに持っておく）---
slime_shard = Entity(
    sprite="material",
    name="スライムのかけら",
    blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# ゴブリンの爪：ゴブリン撃破時のドロップ素材
goblin_claw = Entity(
    sprite="material",
    name="ゴブリンの爪",
    blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# 敵の撃破ドロップ（combat._die が target.loot を床に落とす。ボスと同じ仕組み）
goblin.loot = goblin_claw
slime.loot = slime_shard

# --- 食料・食材（消費アイテム。満腹度を回復し、料理の材料にもなる）---
nuts = Entity(
    sprite="food_fruit", name="リンゴ", blocks_movement=False,
    consumable=FoodConsumable(amount=25), shelf_life=400,  # 乾物で日持ち
)
preserved_food = Entity(
    sprite="food_ration", name="携帯食料", blocks_movement=False,
    consumable=FoodConsumable(amount=50), shelf_life=600,  # 保存食。最長だが不滅ではない
)
herb = Entity(
    sprite="food_herb", name="薬草", blocks_movement=False,
    consumable=FoodConsumable(amount=15), shelf_life=200,
)
mushroom = Entity(
    sprite="food_mushroom", name="キノコ", blocks_movement=False,
    consumable=FoodConsumable(amount=15), shelf_life=180,
)
meat = Entity(
    sprite="food_meat", name="肉", blocks_movement=False,
    consumable=FoodConsumable(amount=20), shelf_life=120,  # 生肉。傷みやすい
)

# 追加食材（栄養ニッチを埋める。日持ちは食材ごとに差をつける）
potato = Entity(
    sprite="food_potato", name="イモ", blocks_movement=False,
    consumable=FoodConsumable(amount=30), shelf_life=350,  # 炭水化物源・日持ち長め
)
fruit = Entity(
    sprite="food_fruit", name="果実", blocks_movement=False,
    consumable=FoodConsumable(amount=18), shelf_life=90,   # ビタミンC源・傷みやすい
)
shellfish = Entity(
    sprite="food_shellfish", name="貝", blocks_movement=False,
    consumable=FoodConsumable(amount=16), shelf_life=100,  # カルシウム＋鉄
)
cheese = Entity(
    sprite="food_cheese", name="チーズ", blocks_movement=False,
    consumable=FoodConsumable(amount=24), shelf_life=300,  # 日持ちするカルシウム源
)
honey = Entity(
    sprite="food_honey", name="蜂蜜", blocks_movement=False,
    consumable=FoodConsumable(amount=22), shelf_life=800,  # 超日持ちの炭水化物
)
# 毒キノコ：生食はできない素材。料理して毒を抜けば食材になる（生焼けだと食中毒）
poison_mushroom = Entity(
    sprite="material", name="毒キノコ", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# --- 種（素材。拠点の畑に植えると、階を潜るうちに食材が育つ）---
nut_seed = Entity(
    sprite="seed", name="リンゴの種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
herb_seed = Entity(
    sprite="seed", name="薬草の種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
mushroom_seed = Entity(
    sprite="seed", name="キノコの種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
potato_seed = Entity(       # 野菜：イモ（収穫で種が採れる）
    sprite="seed", name="イモの種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
fruit_seed = Entity(        # 果物：果実（収穫しても株が残り再収穫できる）
    sprite="seed", name="果実の種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# --- 畜産・漁業の産物（食材。満腹度回復＋料理素材）---
egg = Entity(sprite="food_egg", name="卵", blocks_movement=False,
             consumable=FoodConsumable(amount=15), shelf_life=140)
milk = Entity(sprite="food_milk", name="ミルク", blocks_movement=False,
              consumable=FoodConsumable(amount=20), shelf_life=120)
fish = Entity(sprite="food_fish", name="魚", blocks_movement=False,
              consumable=FoodConsumable(amount=20), shelf_life=110)
big_fish = Entity(sprite="food_bigfish", name="大魚", blocks_movement=False,
                  consumable=FoodConsumable(amount=35), shelf_life=110)
# フグ：生食危険な素材（料理して毒を抜く前提）
puffer = Entity(sprite="material", name="フグ", blocks_movement=False,
                item_category=ItemCategory.MATERIAL)

# --- 牧場の動物・漁業のエサ（素材）---
chicken = Entity(sprite="material", name="ニワトリ", blocks_movement=False,
                 item_category=ItemCategory.MATERIAL)
cow = Entity(sprite="material", name="ウシ", blocks_movement=False,
             item_category=ItemCategory.MATERIAL)
bait = Entity(sprite="material", name="エサ", blocks_movement=False,
              item_category=ItemCategory.MATERIAL)
# 飼料：畜産フォークでの餌やりに消費する（リンゴから錬金で作る）
feed = Entity(sprite="feed", name="飼料", blocks_movement=False,
              item_category=ItemCategory.MATERIAL)
# スプリンクラー：購入/クラフトで入手し、建設モードのトンカチで設置（撤去で回収）
sprinkler = Entity(sprite="sprinkler", name="スプリンクラー", blocks_movement=False,
                   item_category=ItemCategory.MATERIAL)

# --- 符呪のお札（拠点の祭壇で装備にエンチャントを付ける消耗品。武器用/防具用）---
# Minecraft のエンチャント風：札ごとに符呪が対応し、重ねるとレベルが上がる。
ofuda_sharp   = Entity(sprite="scroll", name="鋭利の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_fire    = Entity(sprite="scroll", name="火炎の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_knock   = Entity(sprite="scroll", name="撃退の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_loot    = Entity(sprite="scroll", name="略奪の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_protect = Entity(sprite="scroll", name="防護の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_thorns  = Entity(sprite="scroll", name="棘の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_light   = Entity(sprite="scroll", name="軽量の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)
ofuda_crit    = Entity(sprite="scroll", name="会心の札", blocks_movement=False, item_category=ItemCategory.MATERIAL)

# --- エンチャント済みのレア装備（あらかじめ符呪付き。ダンジョンのレアドロップ）---
# enchant.preset でテンプレートに符呪を焼き込む。spawn は deepcopy するので各個体に複製される。
import enchant as _enchant  # noqa: E402  レア装備の事前符呪に使う

# 妖刀：刀ベースに火炎II・会心I。高会心の攻撃特化レア。
cursed_katana = Entity(
    sprite="katana", name="妖刀", blocks_movement=False,
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=8, stamina_cost=26, crit_chance=0.15),
)
_enchant.preset(cursed_katana, {"fire": 2, "crit": 1})

# 守護の板金鎧：板金鎧ベースに防護I・棘I。防御特化レア。
guardian_plate = Entity(
    sprite="plate_armor", name="守護の板金鎧", blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=7, stamina_cost=12),
)
_enchant.preset(guardian_plate, {"protect": 1, "thorns": 1})

# 料理は固定テンプレートではなく cooking.cook() が動的に生成する。

# --- 大切なもの（捨てられない重要アイテム）---
adventurers_proof = Entity(
    sprite="key_item",
    name="冒険者の証",
    blocks_movement=False,
    item_category=ItemCategory.KEY,
)

# 魔法のテント：大切なものだが「使う」と拠点へ移動できる（消費されない）
magic_tent = Entity(
    sprite="tent",
    name="魔法のテント",
    blocks_movement=False,
    consumable=TentConsumable(),
    item_category=ItemCategory.KEY,
)

# 区画開放の鍵（大切なもの。使うと拠点の区画が開放される）
ranch_key = Entity(
    sprite="key_item", name="牧場の鍵", blocks_movement=False,
    consumable=UnlockZoneConsumable("ranch", "牧場"),
    item_category=ItemCategory.KEY,
)
fishery_key = Entity(
    sprite="key_item", name="漁業の鍵", blocks_movement=False,
    consumable=UnlockZoneConsumable("fishery", "漁業"),
    item_category=ItemCategory.KEY,
)


# --- 追加食材（extra_foods.py のテーブルから動的生成。栄養/満腹/日持ち/種を一括登録）---
import extra_foods as _xf

EXTRA_FOODS = {}   # 食材名 → 食材 Entity
EXTRA_SEEDS = {}   # 食材名 → 種 Entity（栽培可能な食材のみ）
for _name, _d in _xf.FOODS.items():
    EXTRA_FOODS[_name] = Entity(
        sprite=_d["sprite"], name=_name, blocks_movement=False,
        consumable=FoodConsumable(amount=_d["sat"]), shelf_life=_d["shelf"],
    )
    if _d.get("plant"):
        EXTRA_SEEDS[_name] = Entity(
            sprite="seed", name=_name + "の種", blocks_movement=False,
            item_category=ItemCategory.MATERIAL,
        )
