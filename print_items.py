#!/usr/bin/env python3
from typing import List, Tuple, Optional

from pythongame.core.common import ItemType
from pythongame.core.item_data import randomized_item_id, create_item_description, get_items_with_category, \
    get_optional_item_level, ItemData, build_item_name
from pythongame.core.item_inventory import ItemEquipmentCategory
from pythongame.register_game_data import register_all_game_data


def print_items():
    for category in [c for c in ItemEquipmentCategory] + [None]:
        if category:
            print(category.name + ":")
        else:
            print("PASSIVE:")
        print("- - - - -")
        entries: List[Tuple[ItemType, ItemData, Optional[int]]] = [
            (i_type, i_data, get_optional_item_level(i_type)) for (i_type, i_data) in get_items_with_category(category)]
        entries.sort(key=lambda entry: entry[2] if entry[2] else 9999)
        for item_type, item_data, item_level in entries:
            level_text = "level {:<10}".format(item_level) if item_level else " " * 16
            item_id = randomized_item_id(item_type)
            item_name = build_item_name(item_id)
            print("{:<25}".format(item_name) + level_text + str(create_item_description(item_id)))
        print("")


register_all_game_data()
print_items()
