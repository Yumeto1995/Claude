from __future__ import annotations

from typing import Iterable

import buildings
import camp_map
import colors
import entity_factories
import farming
import fishery
import item_category
import ranch
import shop
import spoilage
import village_map
from actions import EscapeAction
from fov import DEFAULT_RADIUS, compute_fov
from input_handlers import dispatch_event
from message_log import MessageLog
from procgen import generate_boss_floor, generate_dungeon, nonsafe_connected


class Engine:
    """ゲーム状態を保持し、入力→更新の流れを束ねる。描画は graphics.Renderer。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.game_over = False
        self.attack_mode = False     # True なら方向キーで攻撃、False なら移動
        self.fire_mode = False       # True なら次の方向キーで弓を撃つ（射撃モード）
        self.throw_item = None       # not None ならそのアイテムを次の方向キーで投げる
        self.inventory_open = False  # 持ち物メニューを開いているか
        self.inventory_category = 0  # 持ち物メニューで選択中の分類タブ
        self.inventory_cursor = 0    # 持ち物メニューで選択中の行（カーソル位置）
        # スキルツリー画面の状態
        self.skill_open = False
        self.skill_branch = 0        # 選択中の系統（列）
        self.skill_tier = 0          # 選択中の段（行）
        # 拠点（魔法のテント＝歩けるテント内マップ）の状態
        self.in_camp = False
        self.camp_menu = None        # None=拠点を歩いている / 文字列=設備メニュー表示中
        self.camp_cursor = 0
        self.cook_pot = []           # 料理の鍋に入れた食材名のリスト
        self.camp_objects = {}       # 自由配置の農場設備 (x,y)->{"kind","content"}
        self.camp_active_pos = None  # メニューで操作中の設備の位置
        self.camp_tool = None        # 建設モードの選択中の道具インデックス（None=非建設）
        self.discovered_dishes = set()  # 作ったことのある料理名
        self.storage = []            # 拠点の倉庫（持ち越し収納）
        self.shipping_bin = []       # 出荷箱：次にダンジョンへ潜るとき売却してXPに
        self.collected = set()       # 図鑑：育て/釣り/料理で手に入れた産物名
        self.collection_rewarded = False  # 図鑑コンプ報酬を渡したか
        self.upgrades = {"storage": 0, "cooking": 0}  # 設備アップグレード段階
        self.enchant_target = None   # 符呪の祭壇で選択中の装備
        self.unlocked_zones = set()  # 開放済み区画（"ranch"/"fishery"）
        self.dungeon_map = None      # 拠点滞在中、ダンジョンマップを退避
        self.dungeon_pos = (0, 0)
        # 攻撃・移動モーションの予約 [(entity, dx, dy), ...]。Renderer が再生する。
        self.pending_animations = []
        self.pending_moves = []
        # 視覚エフェクトの予約。("slash", x, y, dx, dy) / ("flash", entity) /
        # ("popup", x, y, text, color) のタプルを積む。
        self.pending_fx = []
        self.message_log = MessageLog()
        self.message_log.add_message("ダンジョンへようこそ。", colors.WELCOME)
        # プレイヤーはテンプレートから複製して用意（位置は生成時に決まる）
        self.player = entity_factories.player.spawn(0, 0)
        self._give_starting_equipment()
        self.current_floor = 0
        # 村（NPCのいる開始地点）の状態
        self.in_village = False
        self.dialogue = None
        # 建物（家・店）の状態。in_village=True のまま建物内に切り替わる。
        self.building_key = None     # None=屋外 / 建物キー=建物内
        self.building_exit = None    # 建物内のドア座標（ここで Enter→村へ）
        self.building_return = (0, 0)  # 村に戻るときの位置
        self.shop_kind = None        # 開いている店の種別（None=閉じている）
        self.shop_cursor = 0
        self.shop_mode = "buy"       # 店のモード（buy=買う / sell=売る）
        # 潜入中のダンジョン各階を保持（上下移動で同じ階に戻れる）。
        # 村に戻ると破棄され、次の潜入では新しいダンジョンになる。
        self.floors = {}
        # 敵AIのオンライン学習器（基本方策 policy.npz のコピー）。プレイヤーの
        # 実戦から随時学習し、Engine と一緒にセーブされる。ニューゲーム＝この
        # __init__ で基本方策へリセットされる。方策が無ければ None（RL無効・A*）。
        from rl.online import OnlineLearner
        self.enemy_learner = OnlineLearner.new_default()
        self.enter_village()  # ゲームは村から始まる

    BOSS_INTERVAL = 5  # この階数ごとにボスフロア（5,10,15…）

    def _build_floor(self, floor: int) -> "GameMap":
        """指定階のダンジョンを生成して返す。BOSS_INTERVAL の倍数はボスフロア。"""
        if floor % self.BOSS_INTERVAL == 0:
            return generate_boss_floor(self.width, self.height, self.player, floor)
        max_monsters = min(2 + (floor - 1) // 3, 5)  # 深いほど敵が増える（易しめ：上限5・増加緩やか）
        dungeon = None
        for _ in range(20):
            dungeon = generate_dungeon(
                max_rooms=30, room_min_size=6, room_max_size=10,
                map_width=self.width, map_height=self.height,
                max_monsters_per_room=max_monsters, max_items_per_room=1,
                player=self.player, floor=floor,
            )
            if nonsafe_connected(dungeon):
                break
        return dungeon

    def go_to_floor(self, floor: int, arrive: str) -> None:
        """floor 階へ移動する。arrive='up' なら上り階段、'down' なら下り階段に出る。

        生成済みの階は保持されたものを再利用（敵・探索状況も維持）。
        """
        old = self.game_map
        if old is not None and self.player in old.entities:
            old.entities.remove(self.player)
        if floor not in self.floors:
            self.floors[floor] = self._build_floor(floor)
        gm = self.floors[floor]
        if self.player not in gm.entities:
            gm.entities.append(self.player)
        self.game_map = gm
        self.current_floor = floor
        loc = gm.upstairs_location if arrive == "up" else gm.downstairs_location
        # 階段の上ではなく『隣』に出す（来た階段の画像が見えるように）
        self.player.x, self.player.y = self._adjacent_floor(gm, loc)
        self.update_fov()

    @staticmethod
    def _adjacent_floor(gm, loc) -> tuple:
        """loc の隣で、歩けて他に誰もいない床マスを返す（無ければ loc 自身）。"""
        lx, ly = loc
        for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1),
                       (1, 1), (-1, 1), (1, -1), (-1, -1)):
            nx, ny = lx + dx, ly + dy
            if (gm.in_bounds(nx, ny) and gm.tiles["walkable"][nx, ny]
                    and gm.tiles["sprite"][nx, ny] in (0,)  # 床のみ（階段は避ける）
                    and gm.get_blocking_entity_at(nx, ny) is None):
                return nx, ny
        return loc

    def handle_events(self, events: Iterable) -> None:
        for event in events:
            action = dispatch_event(event, self)
            if action is not None:
                self.perform_player_action(action)

    def perform_player_action(self, action) -> None:
        """プレイヤーの1アクションを実行し、ターン経過処理を行う。

        単発キー（handle_events）と長押し移動（メインループ）の両方から呼ばれる。
        """
        # 死亡後は終了(ESC)以外の操作を受け付けない
        if self.game_over and not isinstance(action, EscapeAction):
            return
        # 拠点（テント内）・村はターンが経過しない。移動と会話/設備操作だけ。
        if self.in_camp or getattr(self, "in_village", False):
            action.perform(self, self.player)
            return
        prev = (self.player.x, self.player.y)
        action.perform(self, self.player)
        # ターンを消費する行動の後だけ敵が動く（モード切替・壁ぶつかりは消費しない）
        if action.consumes_turn and not self.game_over:
            if (self.player.x, self.player.y) != prev:
                self._grow_camp()   # 1歩で畑・牧柵・いけすが育つ
            if not action.is_attack:
                self.player.fighter.regenerate_stamina()  # 攻撃以外で回復
                self.player.fighter.regenerate_hp()       # 歩行などでHPも自然回復（空腹時は不可）
            # 満腹度を消費。空腹になった瞬間は警告を出す。
            was_hungry = self.player.fighter.is_hungry
            self.player.fighter.drain_satiety()
            if not was_hungry and self.player.fighter.is_hungry:
                self.message_log.add_message(
                    "おなかが空いた！ 攻撃が重くなり、被ダメージも増える…", colors.PLAYER_DIE
                )
            self._tick_status_effects()
            self._tick_nutrition()     # 隠し栄養の減衰＋欠乏症状
            spoilage.tick(self.player)  # 持ち物の食料が古くなる（倉庫は除く）
            self.update_fov()          # プレイヤーが動いたので視界更新
            self.handle_enemy_turns()  # 敵は視界内のものだけ動く

    def _give_starting_equipment(self) -> None:
        """短剣と革の鎧を持たせて装備させる（開始時）。"""
        dagger = entity_factories.dagger.spawn(0, 0)
        armor = entity_factories.leather_armor.spawn(0, 0)
        bow = entity_factories.bow.spawn(0, 0)                  # 遠距離武器
        arrows = entity_factories.arrow.spawn(0, 0)             # 矢（スタック）
        arrows.count = 15
        proof = entity_factories.adventurers_proof.spawn(0, 0)  # 大切なもの
        tent = entity_factories.magic_tent.spawn(0, 0)          # 大切なもの（拠点へ）
        self.player.inventory.items.extend([dagger, armor, bow, arrows, proof, tent])
        self.player.equipment.weapon = dagger
        self.player.equipment.armor = armor
        self.player.equipment.ranged = bow
        # 合成・栽培を試せるよう、素材と種を少し持たせておく
        for _ in range(3):
            self.player.inventory.items.append(
                entity_factories.slime_shard.spawn(0, 0)
            )
        self.player.inventory.items.append(entity_factories.nut_seed.spawn(0, 0))
        self.player.inventory.items.append(entity_factories.herb_seed.spawn(0, 0))
        # 料理をすぐ試せるよう食材も少し
        self.player.inventory.items.append(entity_factories.meat.spawn(0, 0))
        self.player.inventory.items.append(entity_factories.herb.spawn(0, 0))
        self.player.inventory.items.append(entity_factories.preserved_food.spawn(0, 0))  # 炭水化物源＆保存食
        # 序盤の生存を助ける回復薬（難易度緩和）
        for _ in range(3):
            self.player.inventory.items.append(entity_factories.healing_potion.spawn(0, 0))
        # 拠点の倉庫に各種の種を入れておく＝最初から畑で農業を始められる
        for seed in (entity_factories.nut_seed, entity_factories.herb_seed,
                     entity_factories.mushroom_seed, entity_factories.potato_seed,
                     entity_factories.fruit_seed):
            for _ in range(3):
                self.storage.append(seed.spawn(0, 0))

    def enter_village(self) -> None:
        """村（開始地点）へ。NPCと話し、入口からダンジョンへ向かう。"""
        self.in_village = True
        self.in_camp = False
        self.dialogue = None
        self.building_key = None
        self.building_exit = None
        self.shop_kind = None
        self.game_map = village_map.build_village_map()
        self.player.x, self.player.y = village_map.SPAWN
        self.game_map.entities.append(self.player)

    def enter_dungeon(self) -> None:
        """村の入口からダンジョン1階へ（新しいダンジョンを生成）。"""
        self.in_village = False
        self.dialogue = None
        self.building_key = None
        self.shop_kind = None
        self.floors = {}        # 潜入のたびに新しいダンジョン
        self.current_floor = 0
        self.go_to_floor(1, "up")  # 1階の上り階段（セーフルーム）に出現
        self.message_log.add_message("ダンジョンに足を踏み入れた。", colors.WELCOME)

    def use_stairs(self) -> None:
        """足元の階段を使う。上り階段→前の階（1階なら村）、下り階段→次の階。"""
        pos = (self.player.x, self.player.y)
        if pos == self.game_map.downstairs_location:
            self.descend()
        elif pos == self.game_map.upstairs_location:
            if getattr(self.game_map, "boss_floor", False):
                self.message_log.add_message(
                    "ここからは戻れない。ボスを倒して先へ進もう。", colors.NO_EFFECT
                )
            else:
                self.ascend()
        else:
            self.message_log.add_message("ここには階段がない。", colors.NO_EFFECT)

    def descend(self) -> None:
        self.go_to_floor(self.current_floor + 1, "up")
        self.message_log.add_message(
            f"地下 {self.current_floor} 階に降りた。", colors.DESCEND
        )

    def ascend(self) -> None:
        if self.current_floor <= 1:
            self.return_to_village()
            return
        self.go_to_floor(self.current_floor - 1, "down")
        self.message_log.add_message(
            f"地下 {self.current_floor} 階に戻った。", colors.DESCEND
        )

    def return_to_village(self) -> None:
        """ダンジョンから村へ帰還する（潜入中のダンジョンは破棄）。"""
        if self.player in self.game_map.entities:
            self.game_map.entities.remove(self.player)
        self.floors = {}
        self.enter_village()
        self.player.x, self.player.y = village_map.DUNGEON_ENTRANCE  # 洞窟の前に出る
        self.message_log.add_message("地上の村に戻ってきた。", colors.WELCOME)

    def village_interact(self) -> None:
        """村/建物内で Enter。屋外：洞窟→ダンジョン / ドア→建物 / 隣接NPC→会話。
        建物内：出口ドア→村へ / 隣接店主→店 or 会話。"""
        pos = (self.player.x, self.player.y)
        if self.building_key is None:
            # 屋外（村）
            if pos == village_map.DUNGEON_ENTRANCE:
                self.enter_dungeon()
                return
            if pos in village_map.DOORS:
                self.enter_building(village_map.DOORS[pos])
                return
        else:
            # 建物内：出口ドアで村へ
            if pos == self.building_exit:
                self.leave_building()
                return
        # 隣接エンティティ：店主なら店、それ以外は会話
        for ent in self.game_map.entities:
            if ent is self.player:
                continue
            if max(abs(ent.x - self.player.x), abs(ent.y - self.player.y)) != 1:
                continue
            if getattr(ent, "shop", None):
                self.open_shop(ent.shop)
                return
            if getattr(ent, "dialogue", None):
                self.dialogue = {"name": ent.name, "lines": ent.dialogue}
                return

    # --- 建物（家・店）---
    def enter_building(self, key: str) -> None:
        """村のドアから建物内へ。村マップと位置を退避する。"""
        self.village_outdoor_map = self.game_map
        self.building_return = (self.player.x, self.player.y)
        gm, entrance, exit_pos = buildings.build_interior(key)
        self.game_map = gm
        self.building_key = key
        self.building_exit = exit_pos
        self.player.x, self.player.y = entrance
        gm.entities.append(self.player)
        self.message_log.add_message(
            f"{buildings.label(key)} に入った。", colors.WELCOME
        )

    def leave_building(self) -> None:
        """建物から村へ戻る。"""
        if self.player in self.game_map.entities:
            self.game_map.entities.remove(self.player)
        self.game_map = self.village_outdoor_map
        self.player.x, self.player.y = self.building_return
        self.building_key = None
        self.building_exit = None
        self.shop_kind = None

    # --- 店（買い物。代金＝経験値）---
    def open_shop(self, kind: str) -> None:
        self.shop_kind = kind
        self.shop_cursor = 0
        self.shop_mode = "buy"

    def shop_toggle_mode(self) -> None:
        self.shop_mode = "sell" if self.shop_mode == "buy" else "buy"
        self.shop_cursor = 0

    def shop_move_cursor(self, delta: int) -> None:
        n = len(shop.options(self, self.shop_kind))
        if n:
            self.shop_cursor = (self.shop_cursor + delta) % n

    def shop_buy(self) -> None:
        opts = shop.options(self, self.shop_kind)
        if not opts:
            return
        cur = opts[min(self.shop_cursor, len(opts) - 1)]
        if cur.get("enabled", True):
            if self.shop_mode == "sell":
                shop.sell(self, cur["index"])
            else:
                shop.buy(self, self.shop_kind, cur["index"])

    def shop_close(self) -> None:
        self.shop_kind = None

    # --- スキルツリー ---
    def toggle_skill_tree(self) -> None:
        self.skill_open = not self.skill_open

    def skill_nav(self, dbranch: int, dtier: int) -> None:
        import skills
        self.skill_branch = (self.skill_branch + dbranch) % len(skills.BRANCH_KEYS)
        self.skill_tier = max(0, min(skills.TIERS - 1, self.skill_tier + dtier))

    def skill_unlock(self) -> None:
        import skills
        sk = self.player.skills
        if sk is None:
            return
        branch = skills.BRANCH_KEYS[self.skill_branch]
        tier = self.skill_tier
        name = skills.node_name(branch, tier)
        if branch == "medicine":
            if tier != 0:
                self.message_log.add_message("医術はこれ以上修められない。", colors.NO_EFFECT)
            elif getattr(sk, "self_diagnosis", False):
                self.message_log.add_message("『自己診断』は習得済み。", colors.NO_EFFECT)
            elif self.player.level.wealth() < skills.MEDICINE_XP_COST:
                self.message_log.add_message(
                    f"経験値が足りない（自己診断には {skills.MEDICINE_XP_COST} 必要）。",
                    colors.NO_EFFECT)
            else:
                self.player.level.spend_xp(skills.MEDICINE_XP_COST, self.player.fighter)
                sk.self_diagnosis = True
                self.message_log.add_message(
                    "スキル『自己診断』を習得した！体調の異変が自分で分かるようになった。",
                    colors.LEVEL_UP)
            return
        if sk.unlock(branch, tier, self.player.level.current_level):
            self.message_log.add_message(
                f"スキル『{name}』を習得した！", colors.LEVEL_UP
            )
        elif sk.is_unlocked(branch, tier):
            self.message_log.add_message(f"『{name}』は習得済み。", colors.NO_EFFECT)
        elif sk.points < 1:
            self.message_log.add_message("スキルポイントが足りない。", colors.NO_EFFECT)
        else:
            self.message_log.add_message(
                f"先に『{skills.node_name(branch, tier - 1)}』が必要。", colors.NO_EFFECT
            )

    def enter_camp(self) -> None:
        """ダンジョンを退避して、歩けるテント内マップに切り替える。"""
        self.dungeon_map = self.game_map
        self.dungeon_pos = (self.player.x, self.player.y)
        self.camp_from_village = getattr(self, "in_village", False)  # 村から張ったか
        self.in_village = False   # 拠点描画に切り替える（村判定を一旦オフ）
        self.game_map = camp_map.build_camp_map()
        self.player.x, self.player.y = camp_map.ENTRANCE
        self.game_map.entities = [self.player]
        self.in_camp = True
        self.camp_menu = None
        self.camp_cursor = 0
        self.camp_tool = None
        self.cook_pot = []

    def leave_camp(self) -> None:
        """ダンジョンに戻る。出荷箱の中身はここで売却して経験値(お金)になる。"""
        self._ship_out()
        self.game_map = self.dungeon_map
        self.player.x, self.player.y = self.dungeon_pos
        self.in_camp = False
        self.camp_menu = None
        if getattr(self, "camp_from_village", False):
            self.in_village = True
            self.message_log.add_message("テントをたたんで村に戻った。", colors.WELCOME)
        else:
            self.message_log.add_message("テントをたたんでダンジョンに戻った。", colors.WELCOME)

    def _ship_out(self) -> None:
        """出荷箱の中身を売却して経験値(お金)にする（Stardew の出荷箱に相当）。"""
        import economy
        if not self.shipping_bin:
            return
        total = sum(economy.sell_value(it) for it in self.shipping_bin)
        n = len(self.shipping_bin)
        self.shipping_bin = []
        self.player.level.add_xp(total)
        self.message_log.add_message(
            f"出荷箱の {n} 品を売った。 +{total} の経験値（お金）を得た。", colors.LEVEL_UP)

    def record_collection(self, name: str) -> None:
        """図鑑に産物を記録。全種そろえたら一度だけ報酬。"""
        import economy
        if name not in economy.COLLECT_ALL or name in self.collected:
            return
        self.collected.add(name)
        if (not self.collection_rewarded
                and all(n in self.collected for n in economy.COLLECT_ALL)):
            self.collection_rewarded = True
            self.player.level.add_xp(economy.COLLECTION_REWARD)
            self.message_log.add_message(
                f"図鑑をコンプリート！ 報酬 +{economy.COLLECTION_REWARD} の経験値！",
                colors.LEVEL_UP)

    def apply_storage_upgrade(self) -> None:
        """収納アップグレード段階に応じて持ち物枠を更新する。"""
        import economy
        self.player.inventory.capacity = 36 + self.upgrades["storage"] * economy.STORAGE_PER_LEVEL

    def camp_interact(self) -> None:
        """足元の設備を使う（Enter）。住居設備か、配置した農場設備（畑/牧柵/いけす）。"""
        pos = (self.player.x, self.player.y)
        kind = camp_map.STATIONS.get(pos)
        if kind == "exit":
            self.leave_camp()
            return
        if kind == "skill":
            self.toggle_skill_tree()
            return
        if kind == "cooking":
            self.camp_menu, self.camp_cursor, self.cook_pot = "cook", 0, []
            return
        if kind == "altar":
            self.camp_menu, self.camp_cursor, self.enchant_target = "enchant", 0, None
            return
        if kind in ("alchemy", "storage", "health", "shipping", "upgrade", "collection"):
            self.camp_menu, self.camp_cursor = kind, 0
            return
        obj = self.camp_objects.get(pos)
        if obj is not None:
            self._interact_farm_object(pos, obj)

    def _interact_farm_object(self, pos, obj) -> None:
        """配置した畑/牧柵/いけすを操作（空→入れる / 育成中→状態 / 完了→収穫）。"""
        self.camp_active_pos = pos
        kind = obj["kind"]
        content = obj["content"]
        if kind == "farm":
            if content is None:
                if not farming.seed_names_in(self.player.inventory.items):
                    self.message_log.add_message("植える種を持っていない。", colors.NO_EFFECT)
                    return
                self.camp_menu, self.camp_cursor = "farm_plant", 0
            elif content["steps_left"] <= 0:
                farming.harvest_obj(self, obj)
            else:
                self.message_log.add_message(farming.plot_label(obj), colors.NO_EFFECT)
        elif kind == "pen":
            if content is None:
                if not ranch.animal_names_in(self.player.inventory.items):
                    self.message_log.add_message("入れる動物がいない。", colors.NO_EFFECT)
                    return
                self.camp_menu, self.camp_cursor = "pen_place", 0
            elif content["steps_left"] <= 0:
                ranch.collect(self, obj)
            else:
                self.message_log.add_message(ranch.label(obj), colors.NO_EFFECT)
        elif kind == "tank":
            if content is None:
                self.camp_menu, self.camp_cursor = "tank_place", 0
            elif content["steps_left"] <= 0:
                fishery.collect(self, obj)
            else:
                self.message_log.add_message(fishery.label(obj), colors.NO_EFFECT)
        elif kind == "sprinkler":
            self.message_log.add_message(
                "スプリンクラーが周囲の畑を自動で潤している。", colors.NO_EFFECT
            )

    def _grow_camp(self) -> None:
        """1歩あるくごとに農場設備を育てる。スプリンクラー隣接の畑は自動水やりで倍速。"""
        sprinkled = set()
        for (x, y), o in self.camp_objects.items():
            if o["kind"] == "sprinkler":
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        sprinkled.add((x + dx, y + dy))
        for pos, obj in self.camp_objects.items():
            c = obj.get("content")
            if c is None:
                continue
            if c["steps_left"] > 0:
                c["steps_left"] -= 1
                if obj["kind"] == "farm" and pos in sprinkled:
                    c["tended"] = True     # スプリンクラー管理＝手入れ済み（収穫品質UP）
                    if c["steps_left"] > 0:
                        c["steps_left"] -= 1   # 自動水やりで成長倍速
            if c.get("boost_cd", 0) > 0:
                c["boost_cd"] -= 1

    def camp_tool_op(self, op: str, index: int = None) -> None:
        """建設モードの操作。cycle=道具切替 / select=直接選択 / use=使用 / exit=終了。"""
        tools = camp_map.TOOLS
        if op == "cycle":
            if self.camp_tool is None:
                self.camp_tool = 0
            elif self.camp_tool + 1 < len(tools):
                self.camp_tool += 1
            else:
                self.camp_tool = None
            self._announce_tool()
        elif op == "select" and index is not None and 0 <= index < len(tools):
            self.camp_tool = index
            self._announce_tool()
        elif op == "exit":
            self.camp_tool = None
        elif op == "use" and self.camp_tool is not None:
            self._use_tool(tools[self.camp_tool])

    def _announce_tool(self) -> None:
        if self.camp_tool is None:
            self.message_log.add_message("建設モードを終了した。", colors.NO_EFFECT)
            return
        tool = camp_map.TOOLS[self.camp_tool]
        hint = ""
        if tool["act"] == "build":
            b = camp_map.BUILDABLE[tool["kind"]]
            hint = f"（要:{b[4]}）" if b[4] else f"（{b[1]}）"
        self.message_log.add_message(
            f"道具：{tool['name']}{hint}  Enter=使用 / b・1-7=切替 / ESC=終了",
            colors.WELCOME,
        )

    def _use_tool(self, tool) -> None:
        act = tool["act"]
        if act == "build":
            self.camp_build(tool["kind"])
        elif act == "remove":
            self.camp_remove()
        elif act == "water":
            self._tend(("farm",), "水やり", "湿っている", "成長")
        elif act == "feed":
            self._tend(("pen", "tank"), "餌やり", "足りている", "産出", consume="飼料")

    def _tend(self, kinds, verb, full_word, what, consume=None) -> None:
        """育成中の対象を一定歩数進める（同歩数のクールダウン付き）。
        consume を指定すると、その素材を持ち物から1つ消費する（餌やり＝飼料）。"""
        pos = (self.player.x, self.player.y)
        obj = self.camp_objects.get(pos)
        if obj is None or obj["kind"] not in kinds:
            self.message_log.add_message(f"ここに{verb}できる設備はない。", colors.NO_EFFECT)
            return
        c = obj["content"]
        if c is None or c["steps_left"] <= 0:
            self.message_log.add_message(f"今は{verb}の必要がない。", colors.NO_EFFECT)
            return
        if c.get("boost_cd", 0) > 0:
            self.message_log.add_message(f"まだ{full_word}。", colors.NO_EFFECT)
            return
        if consume is not None:
            inv = self.player.inventory.items
            item = next((it for it in inv if it.name == consume), None)
            if item is None:
                self.message_log.add_message(
                    f"{consume}がない（リンゴから錬金で作れる）。", colors.NO_EFFECT
                )
                return
            inv.remove(item)
        boost = camp_map.TEND_BOOST
        c["steps_left"] = max(0, c["steps_left"] - boost)
        c["boost_cd"] = boost
        c["tended"] = True   # 手入れ済み＝収穫/産出の品質UP
        suffix = f"（{consume}を1消費）" if consume is not None else ""
        self.message_log.add_message(f"{verb}した。{what}が進んだ{suffix}。", colors.ITEM)

    def camp_build(self, kind: str) -> None:
        """足元の空きマスに農場設備を建てる（経験値 or アイテムを消費）。"""
        pos = (self.player.x, self.player.y)
        if pos in camp_map.STATIONS or pos in self.camp_objects:
            self.message_log.add_message("ここには建てられない。", colors.NO_EFFECT)
            return
        label, cost, _spr, zone, item = camp_map.BUILDABLE[kind]
        if zone is not None and zone not in self.unlocked_zones:
            key = "牧場の鍵" if zone == "ranch" else "漁業の鍵"
            self.message_log.add_message(
                f"{label}はまだ建てられない。『{key}』で区画を開放しよう。", colors.NO_EFFECT
            )
            return
        if item is not None:                 # アイテムを消費して設置（例：スプリンクラー）
            inv = self.player.inventory.items
            held = next((it for it in inv if it.name == item), None)
            if held is None:
                self.message_log.add_message(
                    f"{label}を持っていない（道具屋で購入 / 錬金で作成）。", colors.NO_EFFECT
                )
                return
            inv.remove(held)
            self.camp_objects[pos] = {"kind": kind, "content": None}
            self.message_log.add_message(f"{label}を設置した。", colors.ITEM)
            return
        if cost > 0 and not self.player.level.spend_xp(cost, self.player.fighter):  # 経験値で建設（0なら無料）
            self.message_log.add_message("お金（経験値）が足りない。", colors.NO_EFFECT)
            return
        self.camp_objects[pos] = {"kind": kind, "content": None}
        suffix = f"（-{cost}）" if cost > 0 else ""
        self.message_log.add_message(f"{label}を建てた{suffix}。", colors.ITEM)

    def camp_remove(self) -> None:
        """足元の農場設備を撤去する。設置物本体（経験値/アイテム）と、牧柵・いけすの
        中の動物/魚はアイテムで戻る。畑の作物は失われる。"""
        pos = (self.player.x, self.player.y)
        obj = self.camp_objects.get(pos)
        if obj is None:
            self.message_log.add_message("ここに撤去できる設備はない。", colors.NO_EFFECT)
            return
        kind, content = obj["kind"], obj["content"]
        label, cost, _spr, _zone, item = camp_map.BUILDABLE[kind]
        del self.camp_objects[pos]
        inv = self.player.inventory
        livestock = {"ニワトリ": entity_factories.chicken, "ウシ": entity_factories.cow,
                     "魚": entity_factories.fish}
        recovered = []
        # 牧柵/いけすの中身（動物・魚）はアイテムで返す（畑の作物は失われる）
        if content is not None and kind in ("pen", "tank"):
            tmpl = livestock.get(content.get("src"))
            if tmpl is not None and not inv.is_full:
                inv.items.append(tmpl.spawn(0, 0))
                recovered.append(content["src"])
        # 設置物本体：アイテム建設は本体を、経験値建設は同額を戻す
        if item is not None:
            if not inv.is_full:
                inv.items.append(entity_factories.sprinkler.spawn(0, 0))
                recovered.append(label)
        elif cost > 0:                       # 経験値建設は同額を戻す（無料建設は戻しなし）
            self.player.level.add_xp(cost)
            recovered.append(f"経験値+{cost}")
        note = f"（{'・'.join(recovered)}を回収）" if recovered else ""
        self.message_log.add_message(f"{label}を撤去した{note}。", colors.ITEM)

    def _tick_status_effects(self) -> None:
        """料理バフなどの一時効果を1ターン分減らし、切れたら外す。"""
        for eff in list(self.player.status_effects):
            eff.turns -= 1
            if eff.turns <= 0:
                self.player.status_effects.remove(eff)
                self.message_log.add_message(
                    f"{eff.name} の効果が切れた。", colors.NO_EFFECT
                )

    def _tick_nutrition(self) -> None:
        """隠し栄養を1ターン減衰させ、欠乏の発症/回復を症状メッセージで知らせる。"""
        nut = getattr(self.player, "nutrition", None)
        if nut is None:
            return
        nut.decay()
        # 症状名・原因は伏せる。ただし医術「自己診断」を習得していれば具体的に知らせる
        changes = nut.update_symptoms()
        sk = self.player.skills
        if getattr(sk, "self_diagnosis", False):
            for _key, kind, symptom in changes:
                if kind == "onset":
                    self.message_log.add_message(
                        f"自己診断：『{symptom}』の症状が出ている。", colors.PLAYER_DIE)
                else:
                    self.message_log.add_message(
                        f"自己診断：『{symptom}』が治まった。", colors.HEAL)
        else:
            if any(kind == "onset" for _k, kind, _s in changes):
                self.message_log.add_message(
                    "なんだか体調が悪くなってきた…", colors.PLAYER_DIE)
            if any(kind == "recover" for _k, kind, _s in changes):
                self.message_log.add_message(
                    "体調が少し良くなってきた。", colors.HEAL)

    def item_under_player(self):
        """プレイヤーが乗っている床のアイテムを返す。なければ None。"""
        for ent in self.game_map.entities:
            if (
                item_category.is_item(ent)
                and ent.x == self.player.x
                and ent.y == self.player.y
            ):
                return ent
        return None

    def update_fov(self) -> None:
        """プレイヤー位置から視界を再計算し、探索済みに反映する。"""
        gm = self.game_map
        nut = getattr(self.player, "nutrition", None)
        pen = nut.fov_penalty if nut is not None else 0   # 夜盲症で視界が狭まる
        radius = max(2, DEFAULT_RADIUS - pen)
        gm.visible = compute_fov(
            gm.tiles["transparent"], gm.rooms, self.player.x, self.player.y, radius
        )
        gm.explored |= gm.visible

    def drain_animations(self):
        """予約された攻撃モーションを取り出して空にする（Renderer が呼ぶ）。"""
        anims = self.pending_animations
        self.pending_animations = []
        return anims

    def drain_moves(self):
        """予約された移動モーション（歩行）を取り出して空にする。"""
        moves = getattr(self, "pending_moves", [])
        self.pending_moves = []
        return moves

    def drain_fx(self):
        """予約された視覚エフェクト（斬撃・フラッシュ・ダメージ数字）を取り出す。"""
        fx = getattr(self, "pending_fx", [])
        self.pending_fx = []
        return fx

    def handle_enemy_turns(self) -> None:
        # AI を持つエンティティ（＝敵）だけが行動する。プレイヤーは ai=None。
        for entity in list(self.game_map.entities):
            if self.game_over:
                break  # プレイヤーが倒れたら残りの敵は動かさない
            if entity.ai is not None:
                entity.ai.perform(self)
