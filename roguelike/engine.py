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
import village_map
from actions import EscapeAction
from fov import compute_fov
from input_handlers import dispatch_event
from message_log import MessageLog
from procgen import generate_dungeon, nonsafe_connected


class Engine:
    """ゲーム状態を保持し、入力→更新の流れを束ねる。描画は graphics.Renderer。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.game_over = False
        self.attack_mode = False     # True なら方向キーで攻撃、False なら移動
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
        self.camp_active_plot = 0    # 畑/牧柵/いけすメニューで操作中のスロット番号
        self.farm_plots = [None] * 4   # 畑（None=空き / dict=栽培中）
        self.ranch_pens = [None] * 3   # 牧場の牧柵
        self.fishery_tanks = [None] * 3  # 漁業の養殖いけす
        self.discovered_dishes = set()  # 作ったことのある料理名
        self.storage = []            # 拠点の倉庫（持ち越し収納）
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
        # 潜入中のダンジョン各階を保持（上下移動で同じ階に戻れる）。
        # 村に戻ると破棄され、次の潜入では新しいダンジョンになる。
        self.floors = {}
        self.enter_village()  # ゲームは村から始まる

    def _build_floor(self, floor: int) -> "GameMap":
        """指定階のダンジョンを生成して返す（連結を検証）。"""
        max_monsters = min(2 + (floor - 1) // 2, 6)  # 深いほど敵が増える
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
                farming.grow_step(self)   # 1歩で作物が育つ
                ranch.step_grow(self)     # 牧場の産物も育つ
                fishery.step_grow(self)   # 養殖も育つ
            if not action.is_attack:
                self.player.fighter.regenerate_stamina()  # 攻撃以外で回復
            # 満腹度を消費。空腹になった瞬間は警告を出す。
            was_hungry = self.player.fighter.is_hungry
            self.player.fighter.drain_satiety()
            if not was_hungry and self.player.fighter.is_hungry:
                self.message_log.add_message(
                    "おなかが空いた！ 攻撃が重くなり、被ダメージも増える…", colors.PLAYER_DIE
                )
            self._tick_status_effects()
            self.update_fov()          # プレイヤーが動いたので視界更新
            self.handle_enemy_turns()  # 敵は視界内のものだけ動く

    def _give_starting_equipment(self) -> None:
        """短剣と革の鎧を持たせて装備させる（開始時）。"""
        dagger = entity_factories.dagger.spawn(0, 0)
        armor = entity_factories.leather_armor.spawn(0, 0)
        proof = entity_factories.adventurers_proof.spawn(0, 0)  # 大切なもの
        tent = entity_factories.magic_tent.spawn(0, 0)          # 大切なもの（拠点へ）
        self.player.inventory.items.extend([dagger, armor, proof, tent])
        self.player.equipment.weapon = dagger
        self.player.equipment.armor = armor
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
        if pos == self.game_map.upstairs_location:
            self.ascend()
        elif pos == self.game_map.downstairs_location:
            self.descend()
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
        self.game_map = camp_map.build_camp_map()
        self.player.x, self.player.y = camp_map.ENTRANCE
        self.game_map.entities = [self.player]
        self.in_camp = True
        self.camp_menu = None
        self.camp_cursor = 0
        self.cook_pot = []

    def leave_camp(self) -> None:
        """ダンジョンに戻る。"""
        self.game_map = self.dungeon_map
        self.player.x, self.player.y = self.dungeon_pos
        self.in_camp = False
        self.camp_menu = None
        self.message_log.add_message("テントをたたんでダンジョンに戻った。", colors.WELCOME)

    def camp_interact(self) -> None:
        """足元の設備を使う（拠点を歩いているときに Enter）。"""
        kind = camp_map.STATIONS.get((self.player.x, self.player.y))
        if kind is None:
            return
        if kind == "exit":
            self.leave_camp()
        elif kind == "cooking":
            self.camp_menu, self.camp_cursor, self.cook_pot = "cook", 0, []
        elif kind == "alchemy":
            self.camp_menu, self.camp_cursor = "alchemy", 0
        elif kind == "storage":
            self.camp_menu, self.camp_cursor = "storage", 0
        elif kind.startswith("farm"):
            farming.interact_plot(self, int(kind[4:]))
        elif kind in ("ranch", "fishery"):
            if kind in self.unlocked_zones:
                self.camp_menu, self.camp_cursor = kind, 0
            else:
                label = camp_map.STATION_LABELS[kind]
                key = "牧場の鍵" if kind == "ranch" else "漁業の鍵"
                self.message_log.add_message(
                    f"{label}はまだ使えない。『{key}』を見つけて開放しよう。", colors.NO_EFFECT
                )

    def _tick_status_effects(self) -> None:
        """料理バフなどの一時効果を1ターン分減らし、切れたら外す。"""
        for eff in list(self.player.status_effects):
            eff.turns -= 1
            if eff.turns <= 0:
                self.player.status_effects.remove(eff)
                self.message_log.add_message(
                    f"{eff.name} の効果が切れた。", colors.NO_EFFECT
                )

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
        gm.visible = compute_fov(
            gm.tiles["transparent"], gm.rooms, self.player.x, self.player.y
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
