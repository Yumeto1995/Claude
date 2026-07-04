from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# レベルアップ時のステータス上昇量（バランス調整はここ）
HP_PER_LEVEL = 20
POWER_PER_LEVEL = 2


class Level:
    """経験値とレベル。

    - プレイヤー：current_xp / current_level を蓄積してレベルアップする。
    - 敵：xp_given（倒されたとき相手に与える経験値）だけを使う。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。
    skills = None     # プレイヤーのスキルツリー（Entity 側で設定）。敵は None。

    def __init__(
        self,
        *,
        level_up_base: int = 50,
        level_up_factor: int = 100,
        xp_given: int = 0,
        current_level: int = 1,
        current_xp: int = 0,
    ):
        self.current_level = current_level
        self.current_xp = current_xp
        self.level_up_base = level_up_base      # 次レベルに必要なXPの基準
        self.level_up_factor = level_up_factor  # レベルごとの増加量
        self.xp_given = xp_given                # 倒されたとき相手に与えるXP

    @property
    def experience_to_next_level(self) -> int:
        """次のレベルに必要な経験値。"""
        return self.level_up_base + self.current_level * self.level_up_factor

    def add_xp(self, amount: int) -> int:
        """経験値を加算し、上がったレベル数を返す。"""
        self.current_xp += amount
        gained = 0
        while self.current_xp >= self.experience_to_next_level:
            self.current_xp -= self.experience_to_next_level
            self.current_level += 1
            gained += 1
            if self.skills is not None:  # レベルアップでスキルポイント付与＆記録
                self.skills.gain_level(self.current_level)
        return gained

    def _xp_to_reach(self, level: int) -> int:
        """level に上がるのに必要だった経験値（= level-1 の必要経験値）。"""
        return self.level_up_base + (level - 1) * self.level_up_factor

    def wealth(self) -> int:
        """お金として使える総経験値。

        このゲームではお金＝経験値。レベルに溜め込んだ分まで含め、
        Lv.1・XP0 まで使い切れる総量を返す（買い物で減るとレベルダウンする）。
        """
        w = self.current_xp
        for lv in range(2, self.current_level + 1):
            w += self._xp_to_reach(lv)
        return w

    def spend_xp(self, amount: int, fighter=None) -> bool:
        """経験値（お金）を amount 消費する。足りなければ False（買えない）。

        current_xp が尽きたらレベルダウンし、その分のステータス上昇を巻き戻す。
        Lv.1 を下回ることはない（wealth() で事前に判定）。
        """
        if amount <= 0:
            return True
        if self.wealth() < amount:
            return False
        from components.level import HP_PER_LEVEL, POWER_PER_LEVEL
        start_level = self.current_level
        self.current_xp -= amount
        while self.current_xp < 0 and self.current_level > 1:
            self.current_level -= 1
            self.current_xp += self._xp_to_reach(self.current_level + 1)
            if fighter is not None:                 # レベルダウン分のステータスを戻す
                fighter.max_hp = max(1, fighter.max_hp - HP_PER_LEVEL)
                fighter._hp = min(fighter._hp, fighter.max_hp)
                fighter.base_power = max(1, fighter.base_power - POWER_PER_LEVEL)
        if self.skills is not None and self.current_level < start_level:
            # 下がった先のレベル時点のスキル構成へ戻す
            self.skills.revert_to(self.current_level)
        return True
