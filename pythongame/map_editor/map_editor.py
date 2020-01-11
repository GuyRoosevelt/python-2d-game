import sys
from pathlib import Path
from typing import Tuple, Optional, List

import pygame
from pygame.rect import Rect

from generate_dungeon import generate_random_map_as_json_from_grid, Grid, generate_random_grid, determine_wall_type
from pythongame.core.common import Sprite, WallType, NpcType, ConsumableType, ItemType, PortalId, HeroId, PeriodicTimer, \
    Millis
from pythongame.core.entity_creation import create_portal, create_hero_world_entity, create_npc, create_wall, \
    create_consumable_on_ground, create_item_on_ground, create_decoration_entity, create_money_pile_on_ground, \
    create_player_state, create_chest
from pythongame.core.game_data import ENTITY_SPRITE_INITIALIZERS, UI_ICON_SPRITE_PATHS, PORTRAIT_ICON_SPRITE_PATHS
from pythongame.core.game_state import GameState
from pythongame.core.math import sum_of_vectors
from pythongame.core.view.game_world_view import GameWorldView
from pythongame.core.view.image_loading import load_images_by_sprite, load_images_by_ui_sprite, \
    load_images_by_portrait_sprite
from pythongame.map_editor.map_editor_ui_view import MapEditorView, PORTRAIT_ICON_SIZE, MAP_EDITOR_UI_ICON_SIZE, \
    EntityTab, GenerateRandomMap, SetCameraPosition, AddEntity, DeleteEntities, DeleteDecorations, MapEditorAction, \
    SaveMap, ToggleOutlines, AddSmartFloorTiles, DeleteSmartFloorTiles
from pythongame.map_editor.map_editor_world_entity import MapEditorWorldEntity
from pythongame.map_file import save_game_state_to_json_file, create_game_state_from_json_file, \
    create_game_state_from_map_data
from pythongame.register_game_data import register_all_game_data

MAP_DIR = "resources/maps/"

register_all_game_data()

GRID_CELL_SIZE = 25

ADVANCED_ENTITIES = [
    MapEditorWorldEntity.smart_floor_tile(Sprite.MAP_EDITOR_SMART_FLOOR_1, 25),
    MapEditorWorldEntity.smart_floor_tile(Sprite.MAP_EDITOR_SMART_FLOOR_2, 50),
    MapEditorWorldEntity.smart_floor_tile(Sprite.MAP_EDITOR_SMART_FLOOR_3, 75),
    MapEditorWorldEntity.smart_floor_tile(Sprite.MAP_EDITOR_SMART_FLOOR_4, 100)
]
WALL_ENTITIES = [MapEditorWorldEntity.wall(wall_type) for wall_type in WallType]
NPC_ENTITIES = [MapEditorWorldEntity.npc(npc_type) for npc_type in NpcType]
ITEM_ENTITIES = [MapEditorWorldEntity.item(item_type) for item_type in ItemType]
MISC_ENTITIES: List[MapEditorWorldEntity] = \
    [
        MapEditorWorldEntity.player(),
        MapEditorWorldEntity.chest(),
        MapEditorWorldEntity.money(1),
        MapEditorWorldEntity.decoration(Sprite.DECORATION_GROUND_STONE),
        MapEditorWorldEntity.decoration(Sprite.DECORATION_GROUND_STONE_GRAY),
        MapEditorWorldEntity.decoration(Sprite.DECORATION_PLANT),
    ] + \
    [MapEditorWorldEntity.consumable(consumable_type) for consumable_type in ConsumableType] + \
    [MapEditorWorldEntity.portal(portal_id) for portal_id in PortalId]

ENTITIES_BY_TYPE = {
    EntityTab.ADVANCED: ADVANCED_ENTITIES,
    EntityTab.ITEMS: ITEM_ENTITIES,
    EntityTab.NPCS: NPC_ENTITIES,
    EntityTab.WALLS: WALL_ENTITIES,
    EntityTab.MISC: MISC_ENTITIES
}

SCREEN_SIZE = (1200, 750)
CAMERA_SIZE = (1200, 550)

# The choice of hero shouldn't matter in the map editor, as we only store its position in the map file
HERO_ID = HeroId.MAGE


class MapEditor:
    def __init__(self, map_file_name: Optional[str]):
        self.map_file_path = MAP_DIR + (map_file_name or "map1.json")

        possible_grid_cell_sizes = [GRID_CELL_SIZE, GRID_CELL_SIZE * 2]
        grid_cell_size_index = 0

        self.grid_cell_size = possible_grid_cell_sizes[grid_cell_size_index]
        self.grid: Grid = None
        self.game_state = None

        if Path(self.map_file_path).exists():
            game_state = create_game_state_from_json_file(CAMERA_SIZE, self.map_file_path, HERO_ID)
        else:
            player_entity = create_hero_world_entity(HERO_ID, (0, 0))
            player_state = create_player_state(HERO_ID)
            game_state = GameState(player_entity, [], [], [], [], [], CAMERA_SIZE, Rect(-250, -250, 500, 500),
                                   player_state, [], [], [])
        self._set_game_state(game_state)
        self.setup_grid_from_game_state()

        pygame.init()

        pygame_screen = pygame.display.set_mode(SCREEN_SIZE)
        images_by_sprite = load_images_by_sprite(ENTITY_SPRITE_INITIALIZERS)
        images_by_ui_sprite = load_images_by_ui_sprite(UI_ICON_SPRITE_PATHS, MAP_EDITOR_UI_ICON_SIZE)
        images_by_portrait_sprite = load_images_by_portrait_sprite(PORTRAIT_ICON_SPRITE_PATHS, PORTRAIT_ICON_SIZE)
        world_view = GameWorldView(pygame_screen, CAMERA_SIZE, SCREEN_SIZE, images_by_sprite)

        self.render_outlines = False

        ui_view = MapEditorView(
            pygame_screen, self.game_state.camera_world_area, SCREEN_SIZE, images_by_sprite, images_by_ui_sprite,
            images_by_portrait_sprite, self.game_state.entire_world_area,
            self.game_state.player_entity.get_center_position(),
            ENTITIES_BY_TYPE, self.grid_cell_size, self.map_file_path)

        camera_move_distance = 75  # must be a multiple of the grid size

        held_down_arrow_keys = set([])
        clock = pygame.time.Clock()
        camera_pan_timer = PeriodicTimer(Millis(50))

        while True:

            # HANDLE USER INPUT

            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEMOTION:
                    action = ui_view.handle_mouse_movement(event.pos)
                    if action:
                        self._handle_action(action, self.grid_cell_size)

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:
                        self.save()
                    elif event.key in [pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP]:
                        held_down_arrow_keys.add(event.key)
                    elif event.key == pygame.K_PLUS:
                        grid_cell_size_index = (grid_cell_size_index + 1) % len(possible_grid_cell_sizes)
                        grid_cell_size = possible_grid_cell_sizes[grid_cell_size_index]
                        ui_view.grid_cell_size = grid_cell_size
                    else:
                        ui_view.handle_key_down(event.key)

                if event.type == pygame.KEYUP:
                    if event.key in held_down_arrow_keys:
                        held_down_arrow_keys.remove(event.key)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    action = ui_view.handle_mouse_click()
                    if action:
                        self._handle_action(action, self.grid_cell_size)

                elif event.type == pygame.MOUSEBUTTONUP:
                    action = ui_view.handle_mouse_release()
                    if action:
                        self._handle_action(action, self.grid_cell_size)

            # HANDLE TIME

            clock.tick()
            time_passed = clock.get_time()

            if camera_pan_timer.update_and_check_if_ready(time_passed):
                if pygame.K_RIGHT in held_down_arrow_keys:
                    self.game_state.translate_camera_position((camera_move_distance, 0))
                if pygame.K_LEFT in held_down_arrow_keys:
                    self.game_state.translate_camera_position((-camera_move_distance, 0))
                if pygame.K_DOWN in held_down_arrow_keys:
                    self.game_state.translate_camera_position((0, camera_move_distance))
                if pygame.K_UP in held_down_arrow_keys:
                    self.game_state.translate_camera_position((0, -camera_move_distance))

            ui_view.camera_world_area = self.game_state.camera_world_area
            ui_view.world_area = self.game_state.entire_world_area

            # RENDER

            world_view.render_world(
                all_entities_to_render=self.game_state.get_all_entities_to_render(),
                decorations_to_render=self.game_state.get_decorations_to_render(),
                player_entity=self.game_state.player_entity,
                is_player_invisible=self.game_state.player_state.is_invisible,
                player_active_buffs=self.game_state.player_state.active_buffs,
                camera_world_area=self.game_state.camera_world_area,
                non_player_characters=self.game_state.non_player_characters,
                visual_effects=self.game_state.visual_effects,
                render_hit_and_collision_boxes=self.render_outlines,
                player_health=self.game_state.player_state.health_resource.value,
                player_max_health=self.game_state.player_state.health_resource.max_value,
                entire_world_area=self.game_state.entire_world_area,
                entity_action_text=None)

            wall_positions = [w.world_entity.get_position() for w in self.game_state.walls_state.walls]
            npc_positions = [npc.world_entity.get_position() for npc in self.game_state.non_player_characters]

            ui_view.render(
                num_enemies=len(self.game_state.non_player_characters),
                num_walls=len(self.game_state.walls_state.walls),
                num_decorations=len(self.game_state.decorations_state.decoration_entities),
                npc_positions=npc_positions,
                wall_positions=wall_positions,
                player_position=self.game_state.player_entity.get_center_position(),
                grid=self.grid)

            pygame.display.flip()

    def save(self):
        save_game_state_to_json_file(self.game_state, self.map_file_path)
        print("Saved state to " + self.map_file_path)

    def _handle_action(self, action: MapEditorAction, grid_cell_size: int):
        if isinstance(action, GenerateRandomMap):
            self._generate_random_map()
        elif isinstance(action, SaveMap):
            self.save()
        elif isinstance(action, SetCameraPosition):
            self.game_state.set_camera_position_to_ratio_of_world(action.position_ratio)
            self.game_state.snap_camera_to_grid(grid_cell_size)
        elif isinstance(action, AddEntity):
            entity_being_placed = action.entity
            if entity_being_placed.is_player:
                self.game_state.player_entity.set_position(action.world_position)
            elif entity_being_placed.npc_type:
                _add_npc(entity_being_placed.npc_type, self.game_state, action.world_position)
            elif entity_being_placed.wall_type:
                _set_wall(self.game_state, action.world_position, entity_being_placed.wall_type)
            elif entity_being_placed.consumable_type:
                _add_consumable(entity_being_placed.consumable_type, self.game_state,
                                action.world_position)
            elif entity_being_placed.item_type:
                _add_item(entity_being_placed.item_type, self.game_state, action.world_position)
            elif entity_being_placed.decoration_sprite:
                _add_decoration(entity_being_placed.decoration_sprite, self.game_state,
                                action.world_position)
            elif entity_being_placed.money_amount:
                _add_money(entity_being_placed.money_amount, self.game_state, action.world_position)
            elif entity_being_placed.portal_id:
                _add_portal(entity_being_placed.portal_id, self.game_state, action.world_position)
            elif entity_being_placed.is_chest:
                _add_chest(self.game_state, action.world_position)
            else:
                raise Exception("Unknown entity: " + str(entity_being_placed))
        elif isinstance(action, DeleteEntities):
            _delete_map_entities_from_position(self.game_state, action.world_position)
        elif isinstance(action, DeleteDecorations):
            _delete_map_decorations_from_position(self.game_state, action.world_position)
        elif isinstance(action, ToggleOutlines):
            self.render_outlines = action.outlines
        elif isinstance(action, AddSmartFloorTiles):
            self._add_smart_floor_tiles(action.tiles)
        elif isinstance(action, DeleteSmartFloorTiles):
            self._remove_smart_floor_tiles(action.tiles)
        else:
            raise Exception("Unhandled event: " + str(action))

    def _set_game_state(self, game_state: GameState):
        self.game_state = game_state
        self.game_state.center_camera_on_player()
        self.game_state.snap_camera_to_grid(self.grid_cell_size)

    def setup_grid_from_game_state(self):
        print("Creating smart floor tiles ...")
        floor_cells = []
        world_area = self.game_state.entire_world_area
        for decoration in self.game_state.decorations_state.decoration_entities:
            for x in range(int(decoration.x), int(decoration.x) + GRID_CELL_SIZE * 2, GRID_CELL_SIZE):
                for y in range(int(decoration.y), int(decoration.y) + GRID_CELL_SIZE * 2, GRID_CELL_SIZE):
                    if len(self.game_state.walls_state.get_walls_at_position((x, y))) == 0:
                        floor_cells.append(((x - world_area.x) // GRID_CELL_SIZE, (y - world_area.y) // GRID_CELL_SIZE))
        print("Created %i smart floor tiles." % len(floor_cells))
        grid_size = (world_area.w // GRID_CELL_SIZE, world_area.h // GRID_CELL_SIZE)
        self.grid = Grid.create_from_rects(grid_size, [])
        self.grid.add_floor_cells(floor_cells)
        self.grid.print()

    def _generate_random_map(self):
        print("Generating random mapp ...")
        self.grid, rooms = generate_random_grid()
        map_json = generate_random_map_as_json_from_grid(self.grid, rooms)
        game_state = create_game_state_from_map_data(CAMERA_SIZE, map_json, HERO_ID)
        print("Random map generated.")
        self._set_game_state(game_state)

    def _add_smart_floor_tiles(self, tiles: List[Tuple[int, int, int, int]]):
        floor_cells = [((r[0] - self.game_state.entire_world_area.x) // GRID_CELL_SIZE,
                        (r[1] - self.game_state.entire_world_area.y) // GRID_CELL_SIZE)
                       for r in tiles]
        self.grid.add_floor_cells(floor_cells)
        xmin = min([cell[0] for cell in floor_cells]) - 1
        xmax = max([cell[0] for cell in floor_cells]) + 2
        ymin = min([cell[1] for cell in floor_cells]) - 1
        ymax = max([cell[1] for cell in floor_cells]) + 2

        for y in range(ymin, ymax):
            for x in range(xmin, xmax):
                pos = sum_of_vectors(self.game_state.entire_world_area.topleft,
                                     (x * GRID_CELL_SIZE, y * GRID_CELL_SIZE))
                is_even_cell = x % 2 == 0 and y % 2 == 0  # ground sprite covers 4 cells, so we only need them on even cells
                if is_even_cell and any(
                        [self.grid.is_floor(c) for c in [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]]):
                    _add_decoration(Sprite.DECORATION_GROUND_STONE, self.game_state, pos)
                if self.grid.is_wall((x, y)):
                    wall_type = determine_wall_type(self.grid, (x, y))
                    _set_wall(self.game_state, pos, wall_type)
                if self.grid.is_floor((x, y)):
                    # print("deleting wall from cell (%i,%i)" % (pos))
                    self._delete_wall(pos)

    def _remove_smart_floor_tiles(self, tiles: List[Tuple[int, int, int, int]]):
        floor_cells = [((r[0] - self.game_state.entire_world_area.x) // GRID_CELL_SIZE,
                        (r[1] - self.game_state.entire_world_area.y) // GRID_CELL_SIZE)
                       for r in tiles]
        self.grid.remove_floor_cells(floor_cells)
        xmin = min([cell[0] for cell in floor_cells])
        xmax = max([cell[0] for cell in floor_cells])
        ymin = min([cell[1] for cell in floor_cells])
        ymax = max([cell[1] for cell in floor_cells])

        for y in range(ymin - 1, ymax + 2):
            for x in range(xmin - 1, xmax + 2):
                pos = sum_of_vectors(self.game_state.entire_world_area.topleft,
                                     (x * GRID_CELL_SIZE, y * GRID_CELL_SIZE))
                is_even_cell = x % 2 == 0 and y % 2 == 0  # ground sprite covers 4 cells, so we only need them on even cells
                if is_even_cell:
                    if any([self.grid.is_floor(c) for c in [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]]):
                        _add_decoration(Sprite.DECORATION_GROUND_STONE, self.game_state, pos)
                    else:
                        _delete_map_decorations_from_position(self.game_state, pos)
                if self.grid.is_wall((x, y)):
                    wall_type = determine_wall_type(self.grid, (x, y))
                    _set_wall(self.game_state, pos, wall_type)
                else:
                    self._delete_wall(pos)

    def _delete_wall(self, world_position: Tuple[int, int]):
        self.game_state.walls_state.remove_all_from_position(world_position)


def main(map_file_name: Optional[str]):
    MapEditor(map_file_name)


# TODO Convert these functions to methods

def _add_money(amount: int, game_state, snapped_mouse_world_position):
    already_has_money = any([x for x in game_state.money_piles_on_ground
                             if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_money:
        money_pile_on_ground = create_money_pile_on_ground(amount, snapped_mouse_world_position)
        game_state.money_piles_on_ground.append(money_pile_on_ground)


def _add_portal(portal_id: PortalId, game_state, snapped_mouse_world_position):
    already_has_portal = any([x for x in game_state.portals
                              if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_portal:
        portal = create_portal(portal_id, snapped_mouse_world_position)
        game_state.portals.append(portal)


def _add_chest(game_state: GameState, snapped_mouse_world_position):
    already_has_chest = any([x for x in game_state.chests
                             if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_chest:
        chest = create_chest(snapped_mouse_world_position)
        game_state.chests.append(chest)


def _add_item(item_type: ItemType, game_state, snapped_mouse_world_position):
    already_has_item = any([x for x in game_state.items_on_ground
                            if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_item:
        item_on_ground = create_item_on_ground(item_type, snapped_mouse_world_position)
        game_state.items_on_ground.append(item_on_ground)


def _add_consumable(consumable_type: ConsumableType, game_state, snapped_mouse_world_position):
    already_has_consumable = any([x for x in game_state.consumables_on_ground
                                  if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_consumable:
        consumable_on_ground = create_consumable_on_ground(consumable_type, snapped_mouse_world_position)
        game_state.consumables_on_ground.append(consumable_on_ground)


def _add_npc(npc_type, game_state: GameState, snapped_mouse_world_position):
    already_has_npc = any([x for x in game_state.non_player_characters
                           if x.world_entity.get_position() == snapped_mouse_world_position])
    if not already_has_npc:
        npc = create_npc(npc_type, snapped_mouse_world_position)
        game_state.add_non_player_character(npc)


def _add_decoration(decoration_sprite: Sprite, game_state: GameState, snapped_mouse_world_position):
    if len(game_state.decorations_state.get_decorations_at_position(snapped_mouse_world_position)) == 0:
        decoration_entity = create_decoration_entity(snapped_mouse_world_position, decoration_sprite)
        game_state.decorations_state.add_decoration(decoration_entity)


def _set_wall(game_state: GameState, world_pos: Tuple[int, int], wall_type: WallType):
    existing_walls = game_state.walls_state.get_walls_at_position(world_pos)
    if len(existing_walls) > 0:
        if existing_walls[0].wall_type == wall_type:
            return
        for w in existing_walls:
            game_state.walls_state.remove_wall(w)
    wall = create_wall(wall_type, world_pos)
    game_state.walls_state.add_wall(wall)


def _delete_map_entities_from_position(game_state: GameState, snapped_mouse_world_position: Tuple[int, int]):
    game_state.walls_state.remove_all_from_position(snapped_mouse_world_position)
    for enemy in [e for e in game_state.non_player_characters if
                  e.world_entity.get_position() == snapped_mouse_world_position]:
        game_state.non_player_characters.remove(enemy)
    for consumable in [p for p in game_state.consumables_on_ground
                       if p.world_entity.get_position() == snapped_mouse_world_position]:
        game_state.consumables_on_ground.remove(consumable)
    for item in [i for i in game_state.items_on_ground
                 if i.world_entity.get_position() == snapped_mouse_world_position]:
        game_state.items_on_ground.remove(item)
    for money_pile in [m for m in game_state.money_piles_on_ground
                       if m.world_entity.get_position() == snapped_mouse_world_position]:
        game_state.money_piles_on_ground.remove(money_pile)
    for portal in [p for p in game_state.portals
                   if p.world_entity.get_position() == snapped_mouse_world_position]:
        game_state.portals.remove(portal)


def _delete_map_decorations_from_position(game_state: GameState, world_pos: Tuple[int, int]):
    for d in game_state.decorations_state.get_decorations_at_position(world_pos):
        game_state.decorations_state.remove_decoration(d)
