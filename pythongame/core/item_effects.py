from typing import Dict, Union

from pythongame.core.common import *
from pythongame.core.game_state import GameState, Event


class AbstractItemEffect:
    def apply_start_effect(self, game_state: GameState):
        pass

    def apply_middle_effect(self, game_state: GameState, time_passed: Millis):
        pass

    def apply_end_effect(self, game_state: GameState):
        pass

    def get_item_type(self):
        pass

    def item_handle_event(self, event: Event, game_state: GameState):
        pass


def _modify_hero_stat(game_state: GameState, hero_stat: HeroStat, stat_delta: Union[int, float], ):
    player_state = game_state.player_state
    if hero_stat == HeroStat.MAX_HEALTH:
        if stat_delta >= 0:
            player_state.health_resource.increase_max(stat_delta)
        elif stat_delta < 0:
            player_state.health_resource.decrease_max(-stat_delta)
    elif hero_stat == HeroStat.HEALTH_REGEN:
        player_state.health_resource.regen_bonus += stat_delta
    elif hero_stat == HeroStat.MAX_MANA:
        if stat_delta >= 0:
            player_state.mana_resource.increase_max(stat_delta)
        elif stat_delta < 0:
            player_state.mana_resource.decrease_max(-stat_delta)
    elif hero_stat == HeroStat.MANA_REGEN:
        player_state.mana_resource.regen_bonus += stat_delta
    elif hero_stat == HeroStat.ARMOR:
        player_state.armor_bonus += stat_delta
    elif hero_stat == HeroStat.MOVEMENT_SPEED:
        game_state.player_entity.add_to_speed_multiplier(stat_delta)
    elif hero_stat == HeroStat.DAMAGE:
        player_state.damage_modifier_bonus += stat_delta
    elif hero_stat == HeroStat.LIFE_STEAL:
        player_state.life_steal_ratio += stat_delta
    else:
        raise Exception("Unhandled stat: " + str(hero_stat))


class StatModifyingItemEffect(AbstractItemEffect):
    def __init__(self, item_type: ItemType, stat_modifiers: Dict[HeroStat, Union[int, float]]):
        self.item_type = item_type
        self.stat_modifiers = stat_modifiers

    def apply_start_effect(self, game_state: GameState):
        for stat, delta in self.stat_modifiers.items():
            _modify_hero_stat(game_state, stat, delta)

    def apply_end_effect(self, game_state: GameState):
        for stat, delta in self.stat_modifiers.items():
            _modify_hero_stat(game_state, stat, -delta)

    def get_item_type(self):
        return self.item_type


_item_effects: Dict[ItemType, AbstractItemEffect] = {}


def register_item_effect(item_type: ItemType, effect: AbstractItemEffect):
    _item_effects[item_type] = effect


# Note this is handled differently compared to buffs
# There is only one effect instance per item type - having duplicate items with active effects may not be well supported
def get_item_effect(item_type: ItemType) -> AbstractItemEffect:
    return _item_effects[item_type]
