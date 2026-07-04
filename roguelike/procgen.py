from __future__ import annotations

import random
from typing import Iterator, List, Tuple

import numpy as np

import entity_factories
from entity import Entity
from game_map import GameMap
from pathfinding import bresenham
import tile_types


class RectangularRoom:
    """矩形の部屋。左上座標と幅・高さで定義する。"""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """部屋の内側（外周の壁を除いた床部分）のスライス。"""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: "RectangularRoom") -> bool:
        """他の部屋と重なるなら True。"""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """2点間を L字型の通路でつなぐ座標を順に返す。"""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5:
        # 先に横、次に縦
        corner_x, corner_y = x2, y1
    else:
        # 先に縦、次に横
        corner_x, corner_y = x1, y2

    # bresenham で直線上の格子点を得る
    for x, y in bresenham((x1, y1), (corner_x, corner_y)):
        yield x, y
    for x, y in bresenham((corner_x, corner_y), (x2, y2)):
        yield x, y


def _scale_monster(monster: Entity, floor: int) -> None:
    """階層が深いほど敵を強くする（攻撃力・HP・防御・経験値）。"""
    f = floor - 1
    if f <= 0:
        return
    fi = monster.fighter
    if fi is not None:
        fi.base_power += (f + 1) // 3   # 深いほど与ダメが伸びる（易しめ：伸びを緩やかに）
        fi.base_defense += f // 4
        fi.max_hp += f * 2              # HPは控えめに伸ばす（殴り応えを残す）
        fi._hp = fi.max_hp
    if monster.level is not None:
        monster.level.xp_given += f * 5


def place_entities(
    room: RectangularRoom, dungeon: GameMap, maximum_monsters: int, floor: int
) -> None:
    """1つの部屋にランダムな数の敵を配置する（floor で強さをスケール）。"""
    number_of_monsters = random.randint(0, maximum_monsters)

    for _ in range(number_of_monsters):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        # 既に誰かいるマスは避ける
        if any(e.x == x and e.y == y for e in dungeon.entities):
            continue

        template = entity_factories.goblin if random.random() < 0.8 else entity_factories.slime
        monster = template.spawn(x, y)
        _scale_monster(monster, floor)
        dungeon.entities.append(monster)


def place_items(
    room: RectangularRoom, dungeon: GameMap, maximum_items: int
) -> None:
    """1つの部屋にランダムな数のアイテムを配置する。"""
    number_of_items = random.randint(0, maximum_items)

    for _ in range(number_of_items):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if any(e.x == x and e.y == y for e in dungeon.entities):
            continue

        # 種類を重み付き抽選（消費アイテム多め、装備は控えめ）
        templates = [
            entity_factories.healing_potion,
            entity_factories.lightning_scroll,
            entity_factories.confusion_scroll,
            entity_factories.dagger,
            entity_factories.sword,
            entity_factories.leather_armor,
            entity_factories.chain_mail,
            entity_factories.slime_shard,
            # 食材：全栄養素を探索で入手できるよう種類を確保
            # （木の実=炭水化物/脂質, 卵=カルシウム/ビタミンA, 肉=たんぱく質/鉄 …）
            entity_factories.herb,
            entity_factories.mushroom,
            entity_factories.meat,
            entity_factories.nuts,
            entity_factories.egg,
            entity_factories.potato,
            entity_factories.fruit,
            entity_factories.shellfish,
            entity_factories.honey,
            entity_factories.poison_mushroom,
            entity_factories.nut_seed,
            entity_factories.herb_seed,
            entity_factories.mushroom_seed,
            entity_factories.ranch_key,
            entity_factories.fishery_key,
            entity_factories.chicken,
            entity_factories.cow,
            entity_factories.bait,
        ]
        weights = [34, 10, 8, 8, 4, 6, 4, 10, 6, 6, 6, 6, 4, 5, 5, 4, 3, 4, 4, 4, 4, 2, 2, 3, 3, 4]
        template = random.choices(templates, weights=weights)[0]
        dungeon.entities.append(template.spawn(x, y))


def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    max_monsters_per_room: int,
    max_items_per_room: int,
    player: Entity,
    floor: int = 1,
) -> GameMap:
    """ランダムなダンジョンを生成して GameMap を返す。"""
    dungeon = GameMap(map_width, map_height)
    dungeon.entities.append(player)  # プレイヤーもマップの住人として登録

    rooms: List[RectangularRoom] = []
    center_of_last_room = (0, 0)

    for _ in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        new_room = RectangularRoom(x, y, room_width, room_height)

        # 既存の部屋と重なるなら捨てて次へ
        if any(new_room.intersects(other) for other in rooms):
            continue

        # 部屋の内側を床に掘る
        dungeon.tiles[new_room.inner] = tile_types.floor

        if len(rooms) == 0:
            # 最初の部屋＝セーフルーム。プレイヤーを配置し、敵は置かない。
            # 最初の部屋は接続上「行き止まり（葉）」なので、敵を締め出しても
            # 階層は分断されない。上り階段は通路掘りで消えないよう最後に置く。
            player.x, player.y = new_room.center
            dungeon.safe[new_room.inner] = True
            first_room_center = new_room.center
        else:
            # 直前の部屋と通路でつなぐ
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                dungeon.tiles[x, y] = tile_types.floor
            # 2部屋目以降に敵とアイテムを配置
            place_entities(new_room, dungeon, max_monsters_per_room, floor)
            place_items(new_room, dungeon, max_items_per_room)

        center_of_last_room = new_room.center
        rooms.append(new_room)
        # FOV 用に部屋の範囲を記録
        dungeon.rooms.append((new_room.x1, new_room.y1, new_room.x2, new_room.y2))

    # 上り階段（前の階／村へ）を最初の部屋の中央に置く。
    # 通路掘りで床に上書きされないよう、全ての掘削が終わったここで置く。
    dungeon.tiles[first_room_center] = tile_types.up_stairs
    dungeon.upstairs_location = first_room_center

    # 下り階段を最後の部屋の中央に置く（上り階段と重ならないよう保証）
    if center_of_last_room == first_room_center and len(rooms) >= 2:
        center_of_last_room = rooms[1].center
    dungeon.tiles[center_of_last_room] = tile_types.down_stairs
    dungeon.downstairs_location = center_of_last_room

    return dungeon


def _carve_wide_h(dungeon: GameMap, x1: int, x2: int, y: int, half: int = 1) -> None:
    """y を中心に高さ (2*half+1) の横通路を掘る（大型ボスが通れる幅）。"""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for dy in range(-half, half + 1):
            if dungeon.in_bounds(x, y + dy):
                dungeon.tiles[x, y + dy] = tile_types.floor


def generate_boss_floor(
    map_width: int, map_height: int, player: Entity, floor: int
) -> GameMap:
    """ボスフロア：入口室→幅広通路→ボスアリーナ→幅広通路→出口室（下り階段）。

    セーフルーム無し・上り階段無し（戻れない）。主は 3×3 マスの大型ボス。
    通路はボスが通れる幅（3マス）で掘る。
    """
    dungeon = GameMap(map_width, map_height)
    dungeon.entities.append(player)
    dungeon.boss_floor = True
    cy = map_height // 2

    ent = RectangularRoom(3, cy - 4, 8, 8)
    arena = RectangularRoom(map_width // 2 - 8, cy - 8, 16, 16)
    exit_room = RectangularRoom(map_width - 12, cy - 4, 8, 8)
    for r in (ent, arena, exit_room):
        dungeon.tiles[r.inner] = tile_types.floor
        dungeon.rooms.append((r.x1, r.y1, r.x2, r.y2))

    # 幅広（3マス）通路で横につなぐ＝ボスも通れる
    _carve_wide_h(dungeon, ent.center[0], arena.center[0], cy, half=1)
    _carve_wide_h(dungeon, arena.center[0], exit_room.center[0], cy, half=1)

    # 入場位置（入口室）。上り階段は置かない＝戻れない（boss_floor フラグで使用不可）。
    player.x, player.y = ent.center
    dungeon.upstairs_location = ent.center
    # 下り階段（出口室）で先へ進む
    dungeon.tiles[exit_room.center] = tile_types.down_stairs
    dungeon.downstairs_location = exit_room.center

    # ボス（3×3）をアリーナ中央に（中心がアリーナ中央になるよう左上を置く）
    bcx, bcy = arena.center
    boss = entity_factories.boss.spawn(bcx - 1, bcy - 1)
    _scale_monster(boss, floor)
    dungeon.entities.append(boss)
    return dungeon


def nonsafe_connected(dungeon: GameMap) -> bool:
    """セーフルームを除いた床（＝モンスターが動ける範囲）が一つに繋がっているか。

    セーフ化でフロアが分断されていないことの検証に使う。
    """
    from collections import deque

    walkable = dungeon.tiles["walkable"] & (~dungeon.safe)
    total = int(walkable.sum())
    if total == 0:
        return True

    w, h = dungeon.width, dungeon.height
    sx, sy = (int(v) for v in np.argwhere(walkable)[0])
    seen = {(sx, sy)}
    dq = deque([(sx, sy)])
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and walkable[nx, ny] and (nx, ny) not in seen:
                seen.add((nx, ny))
                dq.append((nx, ny))
    return len(seen) == total
