from typing import Dict, Union, List

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


def _get_description_of_stat_modifier(hero_stat: HeroStat, delta: Union[int, float]) -> str:
    if hero_stat == HeroStat.MAX_HEALTH:
        return "+" + str(delta) + " max health"
    elif hero_stat == HeroStat.HEALTH_REGEN:
        return "+" + str(delta) + " health regen"
    elif hero_stat == HeroStat.MAX_MANA:
        return "+" + str(delta) + " max mana"
    elif hero_stat == HeroStat.MANA_REGEN:
        return "+" + str(delta) + " mana regen"
    elif hero_stat == HeroStat.ARMOR:
        return str(delta) + " armor"
    elif hero_stat == HeroStat.MOVEMENT_SPEED:
        if delta >= 0:
            return "Increases movement speed by " + str(int(delta * 100)) + "%"
        else:
            return "Reduces movement speed by " + str(int(delta * 100)) + "%"
    elif hero_stat == HeroStat.DAMAGE:
        return "+" + str(int(round(delta * 100))) + "% damage"
    elif hero_stat == HeroStat.LIFE_STEAL:
        return "+" + str(int(delta * 100)) + "% life steal"
    else:
        raise Exception("Unhandled stat: " + str(hero_stat))


class StatModifyingItemEffect(AbstractItemEffect):
    def __init__(self, item_type: ItemType, stat_modifiers: Dict[HeroStat, Union[int, float]]):
        self.item_type = item_type
        self.stat_modifiers = stat_modifiers

    def apply_start_effect(self, game_state: GameState):
        for stat, delta in self.stat_modifiers.items():
            game_state.modify_hero_stat(stat, delta)

    def apply_end_effect(self, game_state: GameState):
        for stat, delta in self.stat_modifiers.items():
            game_state.modify_hero_stat(stat, -delta)

    def get_item_type(self):
        return self.item_type

    def get_description(self) -> List[str]:
        return [_get_description_of_stat_modifier(stat, delta) for (stat, delta) in self.stat_modifiers.items()]


class EmptyItemEffect(AbstractItemEffect):
    def __init__(self, item_type: ItemType):
        self.item_type = item_type

    def get_item_type(self):
        return self.item_type


_item_effects: Dict[ItemType, AbstractItemEffect] = {}


def register_item_effect(item_type: ItemType, effect: AbstractItemEffect):
    _item_effects[item_type] = effect


# Note this is handled differently compared to buffs
# There is only one effect instance per item type - having duplicate items with active effects may not be well supported
def get_item_effect(item_type: ItemType) -> AbstractItemEffect:
    return _item_effects[item_type]
