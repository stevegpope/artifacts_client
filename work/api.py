import json
import math
import time
import requests
import logging
from typing import Optional, Dict, List, Tuple
import re
from artifactsmmo_wrapper import wrapper, logger, ArtifactsAPI
from artifactsmmo_wrapper.subclasses import Item, Monster, Resource

class CharacterAPI:
    def __init__(self, my_logger: logging.Logger, token: str, character_name: str):
        """
        Initializes the CharacterAPI with the provided logger, token, and character name.

        Args:
            logger (logging.Logger): The logger instance.
            token (str): The bearer token for authorization.
            character_name (str): The name of the character.
        """
        self.logger = my_logger
        wrapper.token = token
        self.current_character = character_name

        self.api: ArtifactsAPI = wrapper.character(character_name)
        logger.setLevel("DEBUG")

    def get_item(self, item_code) -> Item: 
        item = self.api.items.get(item_code)
        item_level = 1
        try:
            if item.level > 0:
                item_level = item.level
        except:
            if item.craft is not None:
                item_level = item.craft.get('level',1)
            elif item.code == 'old_boots': # not set
                item_level = 20
            elif item.code == 'wooden_club': # not set
                item_level = 25
        item.level = item_level
        return item
    
    def all_items(self) -> List[Item]:
        return self.parse_json_fields(self.api.items.get(code=None))

    def parse_json_fields(self, items: List[Item]):
        for item in items:
            # Parse `craft` if it's a JSON string
            if item.craft and isinstance(item.craft, str):
                try:
                    item.craft = json.loads(item.craft)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse 'craft' for item {item.name}: {item.craft}")
                    item.craft = None  # Set to None if parsing fails

            # Parse `effects` if it's a JSON string
            if item.effects and isinstance(item.effects, str):
                try:
                    item.effects = json.loads(item.effects)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse 'effects' for item {item.name}: {item.effects}")
                    item.effects = None  # Set to None if parsing fails

        return items

    def all_monsters(self) -> List[Monster]:
        return self.api.monsters.all_monsters
    
    def all_resources(self) -> List[Resource]:
        return self.api.resources.all_resources
    
    def deposit_all_inventory_to_bank(self):
        """
        Iterates through the character's inventory and deposits all items into the bank.
        """
        inventory = self.api.get_character().inventory

        if not inventory:
            self.logger.info(f"{self.current_character}: Inventory is empty. Nothing to deposit.")
            return

        for item in inventory:
            code = item.code
            quantity = item.quantity

            # Skip empty slots or items with zero quantity
            if not code or quantity <= 0:
                continue

            try:
                self.api.actions.bank_deposit_item(code, quantity)
            except:
                x,y = self.find_closest_content('bank','bank')
                self.move_character(x,y)
                self.api.actions.bank_deposit_item(code, quantity)

            if self.api.char.gold > 0:
                self.logger.info(f"deposit {self.api.char.gold} gold")
                self.api.actions.bank_deposit_gold(self.api.char.gold)

        self.logger.info(f"{self.current_character}: All items deposited into the bank.")

    def gear_up(self, monster: Monster):
        x,y = self.find_closest_content('bank','bank')
        self.move_character(x,y)
        self.rest()
        self.deposit_all_inventory_to_bank()

        defense_elements = {
            "air": monster.res_air,
            "earth": monster.res_earth,
            "fire": monster.res_fire,
            "water": monster.res_water
        }

        attack_elements = {
            "air": monster.attack_air,
            "earth": monster.attack_earth,
            "fire": monster.attack_fire,
            "water": monster.attack_water
        }

        print(f"{monster.code} attack elements: {attack_elements}")
        print(f"{monster.code} resist elements: {defense_elements}")

        contents = self.get_bank_contents()
        self.logger.info(f"gear_up for {monster}, got bank contents")

        slots = {
            'weapon': ['weapon_slot'],
            'rune': ['rune_slot'],
            'shield': ['shield_slot'],
            'helmet': ['helmet_slot'],
            'body_armor': ['body_armor_slot'],
            'leg_armor': ['leg_armor_slot'],
            'boots': ['boots_slot'],
            'ring': ['ring1_slot','ring2_slot'],
            'amulet': ['amulet_slot'],
            'bag': ['bag_slot'],
            'artifact': ['artifact1_slot','artifact2_slot','artifact3_slot']
        }

        weapon_chosen = False
        weapon_attack_elements = []
        for slot in slots.keys():
            self.gear_up_slot(slot, slots[slot], contents, attack_elements, defense_elements, [], weapon_attack_elements)
            if not weapon_chosen:
                # weapon first, choose the rest based on the attack
                weapon_chosen = True
                weapon_code = self.api.char.weapon_slot
                weapon = self.get_item(weapon_code)
                for effect in weapon.effects:
                    if effect.code.startswith('attack_'):
                        attack_element = effect.code.replace("attack_","")
                        weapon_attack_elements.append(attack_element)

        self.logger.info(f"gear_up with main weapon {weapon_code} attack elements {weapon_attack_elements}")
        self.deposit_all_inventory_to_bank()
        self.get_consumables(contents, attack_elements, defense_elements, weapon_attack_elements)

    def get_consumables(self, contents, attack_elements, defense_elements, weapon_attack_elements: List):
        self.logger.info("get_consumables")
        character_data = self.get_character()
        best_items = {}
        slots = ['utility1_slot','utility2_slot']
        for slot in slots:
            try:
                original_item = getattr(character_data, slot)
                best_items[slot] = original_item
            except AttributeError:
                print(f"get_consumables slot '{slot}' not found.")
                best_items['slot'] = None
                exit(1)

        for item_dict in contents:
            item_code = item_dict['code']
            item = self.get_item(item_code)
            if item.type != 'utility':
                continue

            if item.level != None and item.level > character_data.level:
                self.logger.info(f"get_consumables item {item.code} is too high level {item.level} for me at {self.api.char.level}")
                continue
            
            for best_key in best_items.keys():
                best_item_code = best_items[best_key]
                best_item = None
                if best_item_code:
                    best_item = self.get_item(best_item_code)
                if self.item_better(best_item, item, attack_elements, defense_elements, weapon_attack_elements):
                    if best_key == 'utility1_slot':
                        if best_items['utility2_slot'] != item.code:
                            best_items[best_key] = item.code
                    else:
                        if best_items['utility1_slot'] != item.code:
                            best_items[best_key] = item.code

        for slot in best_items.keys():
            best_item_code = best_items[slot]
            current = self.get_slot(slot)
            if current != best_item_code:
                equipped = False
                self.logger.info(f"get_consumables switch from {current} to {best_item_code} in slot {slot}")
                if current:
                    if slot == 'utility1_slot':
                        self.api.actions.unequip_item('utility1', self.api.char.utility1_slot_quantity)
                    else:
                        self.api.actions.unequip_item('utility2', self.api.char.utility2_slot_quantity)
                quantity = self.withdraw_all(best_item_code, contents)
                if quantity > 0:
                    slot_name = slot.replace('_slot','')
                    if self.api.actions.equip_item(best_item_code, slot_name, quantity):
                        equipped = True
                if not equipped:
                    self.logger.info(f"\n\nERROR\n\nget_consumables could not equip {best_item_code}, probably not really in the bank")
                    exit(1)
            else:
                self.logger.info(f"top up on {current} in {slot}")
                if slot == 'utility1_slot':
                    current_quantity = self.api.char.utility1_slot_quantity
                else:
                    current_quantity = self.api.char.utility2_slot_quantity
                taken = self.withdraw_all(current, contents)
                ideal_amount = 100 - current_quantity
                quantity = min(ideal_amount, taken)
                if quantity == 0:
                    self.logger.info(f"no more {current} to add")
                    continue
                slot_name = slot.replace('_slot','')
                self.api.actions.equip_item(current, slot_name, quantity)

        self.deposit_all_inventory_to_bank()
        for item_dict in contents:
            item = self.get_item(item_dict['code'])
            if item.type == 'consumable' and item.subtype == 'food':
                self.logger.info(f"load up on {item.code}")
                self.withdraw_all(item.code, contents)

    def gear_up_slot(self, slot_type, slots, contents, attack_elements, defense_elements, banned_items: List, weapon_attack_elements: List):
        best_items = self.find_best_item(slot_type, slots, contents, attack_elements, defense_elements, banned_items, weapon_attack_elements)
        for slot in best_items.keys():
            best_item_code = best_items[slot]
            current = self.get_slot(slot)
            if current != best_item_code:
                equipped = False
                if self.withdraw_from_bank(best_item_code, 1):
                    slot_name = slot.replace('_slot','')
                    self.unequip(slot_name)
                    if self.equip(best_item_code, slot_name):
                        equipped = True
                if not equipped:
                    self.logger.info(f"\n\nERROR\n\n\ngear_up_slot could not equip {best_item_code}, probably not really in the bank")
                    banned_items.append(best_item_code)
                    self.gear_up_slot(slot_type, slots, contents, attack_elements, defense_elements, banned_items, weapon_attack_elements)

    def find_best_item(self, slot_name, slots, contents, attack_elements, defense_elements, banned_items: List, weapon_attack_elements: List):
        character_data = self.get_character()

        # Keep a map of slots to the best item for the slot, start with the original ones
        best_items = {}
        for slot in slots:
            try:
                original_item = getattr(character_data, slot)
                best_items[slot] = original_item
            except AttributeError:
                print(f"find_best_item slot '{slot}' not found.")
                best_items['slot'] = None
                return

        # Iterate everything looking for best items
        for item_dict in contents:
            item_code = item_dict['code']
            if item_code in banned_items:
                self.logger.info(f"find_best_item {item_code} banned")
                continue

            item = self.get_item(item_code)

            if item.type != slot_name:
                continue

            if item.level > character_data.level:
                self.logger.info(f"item {item.code} is too high level {item.level} for me at {self.api.char.level}")
                continue
            
            for best_key in best_items.keys():
                best_item_code = best_items[best_key]
                best_item = None
                if best_item_code:
                    best_item = self.get_item(best_item_code)
                if self.item_better(best_item, item, attack_elements, defense_elements, weapon_attack_elements):
                    best_items[best_key] = item.code
        
        return best_items

    def item_better(self, best_item, item, attack_elements, defense_elements, weapon_attack_elements: List):
        if item.level > self.api.char.level:
            return False
        
        best_total = 0
        best_item_code = "None"
        if best_item:
            best_total = self.calculate_item_value(best_item, attack_elements, defense_elements, weapon_attack_elements)
            best_item_code = best_item.code

        new_total = self.calculate_item_value(item, attack_elements, defense_elements, weapon_attack_elements)
        better = new_total > best_total and new_total > 0
        if better:
            self.logger.info(f"item_better best {best_item_code} = {best_total}, new best {item.code} = {new_total}")
        return better
    def calculate_item_value(self, item, attack_elements: Dict, defense_elements: Dict, weapon_attack_elements: List):
        # Samples
        # ogre attack elements: {'air': 0, 'earth': 80, 'fire': 0, 'water': 0}
        # ogre resist elements: {'air': 0, 'earth': 30, 'fire': -20, 'water': 0}
        value = 0
        estimated_rounds = 7
        for effect in item.effects:
            # Hp once per battle
            if effect.code == "hp":
                add = effect.attributes['value']
                value += add

            # Damage per round per damage type
            if effect.code == "dmg":
                add = effect.attributes['value'] * estimated_rounds * len(weapon_attack_elements)
                value += add

            # Restore per round
            if effect.code == "restore":
                add = effect.attributes['value'] * estimated_rounds
                value += add

            # Prospecting for drops, but not high value. This will choose it over nothing
            if effect.code == "prospecting":
                add = effect.attributes['value'] / 10
                value += add
            # Wisdom for xp, also not high value
            if effect.code == "wisdom":
                add = effect.attributes['value'] / 10
                value += add

            # Heal per round
            if effect.code == "heal":
                add = effect.attributes['value'] * estimated_rounds
                value += add

            # Resistance per round
            elif effect.code.startswith("res_"):
                for element in attack_elements.keys():
                    attack_element_value = attack_elements[element]
                    if attack_element_value > 0:
                        if effect.code == f"res_{element}":
                            add = effect.attributes['value'] * estimated_rounds
                            value += add

            # Attack per round weighted to the resistances
            elif effect.code.startswith("attack") or effect.code.startswith("dmg") or effect.code.startswith("boost_dmg_"):
                for element in defense_elements.keys():
                    if effect.code == f"attack_{element}" or effect.code == f"dmg_{element}" or effect.code == f"boost_dmg_{element}":
                        if len(weapon_attack_elements) > 0 and not element in weapon_attack_elements:
                            continue
                        defense_element_value = defense_elements[element]
                        add = max(effect.attributes['value'] - defense_element_value, 0) * estimated_rounds
                        value += add
        return value

    def fight_xp(self):
        level = self.api.char.level
        target_monster_level = level - 10
        self.logger.info(f'Fight loop level {level}, target {target_monster_level}')

        # Special case, always be on the lookout for bandit lizards
        x,y = self.find_closest_content('monster', 'bandit_lizard')
        if x and y:
            closest_monster = self.api.monsters.get('bandit_lizard')
        else:
            monsters = self.api.monsters.get(min_level=target_monster_level,max_level=level-7)
            if not monsters:
                self.logger.info('No monsters found within the level range')
                return None
            
            # Find the monster closest to target_monster_level
            closest_monster = min(monsters, key=lambda x: abs(x.level - target_monster_level))
            self.logger.info(f'Closest monster found: {closest_monster}')
        
        self.gear_up(closest_monster)

        x,y = self.find_closest_content('monster', closest_monster.code)
        self.move_character(x, y)

        self.fight(10)
        return

    def find_closest_content(self, content_type: str, content_code: str):
        maps_data = self.api.maps.get(content_code=content_code, content_type=content_type)
        self.logger.info(f"closest {content_code} in {maps_data}")

        char_x = self.api.char.pos.x
        char_y = self.api.char.pos.y
        
        closest_distance = float('inf')
        x = None
        y = None
        
        # Iterate through all map tiles
        for tile in maps_data:
            if tile.content_code != content_code:
                continue

            # Calculate the Manhattan distance between the character and the tile
            distance = abs(tile.x - char_x) + abs(tile.y - char_y)
            
            # Update the closest tile if this tile is closer
            if distance < closest_distance:
                closest_distance = distance
                x = tile.x
                y = tile.y
        
        self.logger.info(f"closest {content_type} {content_code} at {x},{y}")
        return x,y

    def get_bank_contents(self) -> List[Dict]:
        all_data = []
        page=1
        response = self.api.account.get_bank_items(page = page)
        all_data.extend(response.get("data",[]))
        total_pages = response.get("pages",1)
        while page < total_pages:
            page += 1
            self.logger.info(f"{self.current_character}: Fetch page {page} of {total_pages}")
            response = self.api.account.get_bank_items(page = page)
            all_data.extend(response.get("data",[]))
        return all_data
    
    def withdraw_all(self, code: str, contents = None) -> int:
        if not contents:
            contents = self.get_bank_contents()
        space = self.api.char.get_inventory_space() - 25
        for item in contents:
            if item["code"] == code:
                quantity = min(item['quantity'],100)
                take = min(space,quantity)
                if take > 0:
                    if self.withdraw_from_bank(code,take):
                        self.logger.info(f"{self.current_character}: withdrew {quantity} {code}, {item['quantity']-quantity} remains")
                        return take
        return 0

    def withdraw_from_bank(self, code: str, quantity: int) -> Optional[Dict]:
        try:
            response = self.api.actions.bank_withdraw_item(code, quantity)
            data = response["data"]
            bank = data.get('bank',[])
            for item in bank:
                if item['code'] == code:
                    quantity_remaining = item.get('quantity',None)
                    self.logger.info(f"{self.api.char.name} withdrew {quantity} {code}, {quantity_remaining} remains")
                    break

            return True
        except Exception as e:
            self.logger.info(f"withdraw_from_bank error {e}")
            pass
        return None
    
    def deposit_to_bank(self, code: str, quantity: int) -> Optional[Dict]:
        if (quantity <= 0):
            return
        
        self.logger.info(f"{self.current_character}: Depositing {quantity} of {code} into the bank.")
        self.api.actions.bank_deposit_item(code, quantity)

    def recycle(self, code: str, quantity: int) -> Optional[Dict]:
        if (quantity <= 0):
            return
        
        self.logger.info(f"{self.current_character}: Recycle {quantity} {code}")
        response = self.api.actions.recycle_item(code, quantity)
        if response:
            return response
        else:
            self.logger.error(f"{self.current_character}: Failed to recycle")
            return None

    def choose_task(self, fight_task: bool = False) -> Optional[Dict]:
        """
        Returns the current task from the character data if one exists.
        Otherwise, requests a new task from the API.

        Returns:
            Optional[Dict]: The current or newly assigned task data, or None if no task is available.
        """

        # Check if the character already has a task
        current_task = self.api.char.task
        current_task_type = self.api.char.task_type
        task_total = self.api.char.task_total
        task_progress = self.api.char.task_progress

        if current_task and current_task_type:
            self.logger.info(f"{self.current_character}: Current task: {current_task} (Type: {current_task_type})")
            self.logger.info(f"{self.current_character}:   - Progress: {task_progress}/{task_total}")
            return {
                "code": current_task,
                "type": current_task_type,
                "total": task_total,
                "progress": task_progress,
            }

        # If no current task, request a new one
        self.logger.info(f"{self.current_character}: No current task. Requesting a new task...")
        x, y = self.find_taskmaster(fight_task)
        self.move_character(x, y)
        response = self.api.actions.taskmaster_accept_task()
        if not response:
            self.logger.error(f"{self.current_character}: Failed to request a new task.")
            return None

        # Extract the task data from the response
        task_data = response.get("data", {}).get("task", {})
        if not task_data:
            self.logger.error(f"{self.current_character}: No task data found in the response.")
            return None

        # Log the assigned task details
        self.logger.info(f"{self.current_character}: Assigned task: {task_data['code']} (Type: {task_data['type']})")
        self.logger.info(f"{self.current_character}:   - Total: {task_data['total']}")
        self.logger.info(f"{self.current_character}:   - Rewards: {task_data['rewards']}")

        return task_data

    def find_taskmaster(self, fight_task: bool = False):
        if fight_task:
            self.logger.info(f"{self.current_character}: fight taskmaster at (1,2)")
            return 1,2
        else:
            self.logger.info(f"{self.current_character}: items taskmaster at (4,13)")
            return 4, 13

    def complete_task(self):
        self.logger.info(f"{self.current_character}: Complete task")
        self.api.actions.taskmaster_complete_task()

    def trade_task_items(self, code: str, quantity: int):
        self.logger.info(f"{self.current_character}: Trade in {quantity} {code}")
        response = self.api.actions.taskmaster_trade_task(code, quantity)

    def equip_utility(self, code: str):
        existing_quantity = 0
        slot = 'utility1'
        if self.api.char.utility1_slot == code or self.api.char.utility1_slot == '':
            slot = 'utility1'
            existing_quantity = self.api.char.utility1_slot_quantity
            self.logger.info(f"equip_utility already have {existing_quantity} {code} in {slot}")
        elif self.api.char.utility2_slot == code or self.api.char.utility2_slot == '':
            slot = 'utility2'
            existing_quantity = self.api.char.utility2_slot_quantity
            self.logger.info(f"equip_utility already have {existing_quantity} {code} in {slot}")
        else:
            self.logger.info("equip_utility No slots available")
            return

        for item in self.api.char.inventory:
            if item.code == code:
                quantity = item.quantity
                max_equip = 100 - existing_quantity
                equip_quantity = min(quantity, max_equip)

                if equip_quantity == 0:
                    return

                self.logger.info(f"{self.current_character}: Equip {equip_quantity} {code} into {slot}")
                try:
                    self.api.actions.equip_item(code, slot, equip_quantity)
                except:
                    pass

    def equip(self, code: str, slot: str):
        """
        Equips an item with the specified code into the specified slot.

        Args:
            code (str): The code of the item to equip (e.g., "wooden_staff").
            slot (str): The slot to equip the item into (e.g., "weapon").
        """
        try:
            response = self.api.actions.equip_item(code, slot)
            if response is not None:
                return True
        except:
            return False
        return False

    def craft(self, item_code: str, amount: int = 1):
        """
        Crafts an item with the specified code and waits for the cooldown period.

        Args:
            item_code (str): The code of the item to craft (e.g., "wooden_staff").
            amount (int): The number of items to craft. Defaults to 1.
        """
        self.logger.info(f"{self.current_character}: Crafting {item_code} {amount} time(s)")

        response = self.api.actions.craft_item(item_code, amount)
        if not response:
            self.logger.error(f"{self.current_character}: Failed to craft item.")
            return -1

        # Log the crafting results
        details = response.get("data", {}).get("details", {})
        xp_gained = details.get("xp", 0)
        items_crafted = details.get("items", [])

        character_json = response.get("data", {}).get("character", {})

        self.logger.info(f"{self.current_character}: Crafted {item_code} for {xp_gained}xp")
        self.logger.info(f'weaponcraft level {character_json.get("weaponcrafting_level", 0)} {character_json.get("weaponcrafting_xp", 0)}/{character_json.get("weaponcrafting_max_xp", 0)}')
        self.logger.info(f'gearcraft level {character_json.get("gearcrafting_level", 0)} {character_json.get("gearcrafting_xp", 0)}/{character_json.get("gearcrafting_max_xp", 0)}')
        self.logger.info(f'jewelrycraft level {character_json.get("jewelrycrafting_level", 0)} {character_json.get("jewelrycrafting_xp", 0)}/{character_json.get("jewelrycrafting_max_xp", 0)}')
        self.logger.info(f'woodcutting level {character_json.get("woodcutting_level", 0)} {character_json.get("woodcutting_xp", 0)}/{character_json.get("woodcutting_max_xp", 0)}')
        self.logger.info(f'mining level {character_json.get("mining_level", 0)} {character_json.get("mining_xp", 0)}/{character_json.get("mining_max_xp", 0)}')
        self.logger.info(f'fishing level {character_json.get("fishing_level", 0)} {character_json.get("fishing_xp", 0)}/{character_json.get("fishing_max_xp", 0)}')
        self.logger.info(f'alchemy level {character_json.get("alchemy_level", 0)} {character_json.get("alchemy_xp", 0)}/{character_json.get("alchemy_max_xp", 0)}')
        self.logger.info(f'cooking level {character_json.get("cooking_level", 0)} {character_json.get("cooking_xp", 0)}/{character_json.get("cooking_max_xp", 0)}')
        if items_crafted:
            self.logger.info(f"{self.current_character}: Items crafted:")
            for item in items_crafted:
                self.logger.info(f"{self.current_character}:   - {item['code']}: {item['quantity']}")
        return xp_gained

    def unequip(self, slot: str):
        """
        Unequips an item from the specified slot.

        Args:
            slot (str): The slot to unequip (e.g., "weapon", "helmet", "ring1").
        """
        slot_attribute = f"{slot.lower()}_slot"
        # Use getattr to dynamically access the attribute
        try:
            slot_value = getattr(self.api.char, slot_attribute)
        except AttributeError:
            print(f"slot '{slot}' not found.")
            return

        if slot_value:
            self.api.actions.unequip_item(slot)
        else:
            self.logger.info(f"Nothing equipped in {slot_attribute}")

    def gather(self, target_quantity: int):
        """
        Makes the character gather resources until the target quantity of the first item is reached.
        Waits for the cooldown period after each gathering.

        Args:
            target_quantity (int): The desired quantity of the first item.
        """
        self.logger.info(f"{self.current_character}: Gather {target_quantity}")
        first_item_code = None
        gathered_quantity = 0

        while gathered_quantity < target_quantity:
            response = None
            try:
                response = self.api.actions.gather()
            except:
                pass

            if not response:
                return False

            details = response.get("data", {}).get("details", {})
            xp_gained = details.get("xp", 0)
            items_gathered = details.get("items", [])

            character_json = response.get("data", {}).get("character", {})
            self.logger.info(f'weaponcraft level {character_json.get("weaponcrafting_level", 0)} {character_json.get("weaponcrafting_xp", 0)}/{character_json.get("weaponcrafting_max_xp", 0)}')
            self.logger.info(f'gearcraft level {character_json.get("gearcrafting_level", 0)} {character_json.get("gearcrafting_xp", 0)}/{character_json.get("gearcrafting_max_xp", 0)}')
            self.logger.info(f'jewelrycraft level {character_json.get("jewelrycrafting_level", 0)} {character_json.get("jewelrycrafting_xp", 0)}/{character_json.get("jewelrycrafting_max_xp", 0)}')
            self.logger.info(f'woodcutting level {character_json.get("woodcutting_level", 0)} {character_json.get("woodcutting_xp", 0)}/{character_json.get("woodcutting_max_xp", 0)}')
            self.logger.info(f'fishing level {character_json.get("fishing_level", 0)} {character_json.get("fishing_xp", 0)}/{character_json.get("fishing_max_xp", 0)}')
            self.logger.info(f'mining level {character_json.get("mining_level", 0)} {character_json.get("mining_xp", 0)}/{character_json.get("mining_max_xp", 0)}')
            self.logger.info(f'alchemy level {character_json.get("alchemy_level", 0)} {character_json.get("alchemy_xp", 0)}/{character_json.get("alchemy_max_xp", 0)}')
            self.logger.info(f'cooking level {character_json.get("cooking_level", 0)} {character_json.get("cooking_xp", 0)}/{character_json.get("cooking_max_xp", 0)}')

            self.logger.info(f"{self.current_character}: Gathered {xp_gained} XP.")
            if items_gathered:
                self.logger.info(f"{self.current_character}: Items gathered:")
                for item in items_gathered:
                    self.logger.info(f"{self.current_character}:   - {item['code']}: {item['quantity']}")
                    if first_item_code is None:
                        first_item_code = item["code"]
                        self.logger.info(f"{self.current_character}: First item detected: {first_item_code}")
                    if item["code"] == first_item_code:
                        gathered_quantity += item["quantity"]

            self.logger.info(f"{self.current_character}: Total {first_item_code} gathered: {gathered_quantity}/{target_quantity}")
            if gathered_quantity >= target_quantity:
                self.logger.info(f"{self.current_character}: Target quantity of {first_item_code} reached. Exiting gather loop.")
                return True
        return False

    def rest(self):
        """
        Makes the character rest repeatedly until HP is fully restored.
        Waits for the cooldown period after each rest.
        """
        while True:
            if (self.eat()):
                return
            
            self.logger.info(f"{self.current_character}: Resting...")
            if self.api.char.hp != self.api.char.max_hp:
                self.api.actions.rest()
                self.logger.info(f"{self.current_character}: Rested. HP: {self.api.char.hp}/{self.api.char.max_hp}")
            return
            
    def eat(self):
        if self.api.char.hp == self.api.char.max_hp:
            self.logger.info(f"Full health, no need to eat")
            return True
        for inventory_item in self.api.char.inventory:
            item_code = inventory_item.code
            item = self.api.items.get(item_code)

            if item.type == 'consumable' and item.subtype == 'food':
                heal_value = 1000
                if item.effects:
                    for effect in item.effects:
                        if effect.code == 'heal':
                            heal_value = effect.attributes['value']
                
                # calculate how much to eat to max out
                desired_heal = self.api.char.max_hp - self.api.char.hp
                quantity: int = min(inventory_item.quantity, round((desired_heal / heal_value) + 1))

                self.logger.info(f"{self.current_character}: eat {quantity} {item.code}")
                response = self.api.actions.use_item(item_code, quantity)
                if response:
                    character_json = response.get("data", {}).get("character", {})
                    hp = character_json['hp']
                    max_hp = character_json['max_hp']
                    if (hp != max_hp):
                        self.logger.info(f"{self.current_character}: Bit peckish stil...what else we got?")
                        return self.eat()
                    return True
        return False

    def fight(self, combats=1):
        """
        Initiates a fight, waits for the cooldown period, and rests if health is below 50%.
        """
        original_x = self.api.char.pos.x
        original_y = self.api.char.pos.y
        original_level = self.api.char.level

        for i in range(combats):
            self.logger.info(f"{self.current_character}: Starting combat {i + 1} of {combats}")

            current_hp = self.api.char.hp
            max_hp = self.api.char.max_hp
            self.logger.info(f"{self.current_character}: Current hp {current_hp}, Max hp {max_hp}")

            if current_hp < (max_hp * .5):
                self.rest()

            self.logger.info(f"{self.current_character}: Fight!!!")
            response = self.api.actions.fight()
            fight_data = response.get("data", {}).get("fight", {})
            result = fight_data.get("result", "unknown")
            xp_gained = fight_data.get("xp", 0)
            gold_gained = fight_data.get("gold", 0)
            drops = fight_data.get("drops", [])

            character_json = response.get("data", {}).get("character", {})
            xp = character_json.get("xp", 0)
            max_hp = character_json.get("max_xp", 0)
            level = character_json.get("level", 0)

            self.logger.info(f"{self.current_character}: Fight result: {result}")
            self.logger.info(f"{self.current_character}: XP gained: {xp_gained}")
            self.logger.info(f"{self.current_character}: Gold gained: {gold_gained}")
            self.logger.info(f"{self.current_character}: Level {level} progress {xp}/{max_hp}")

            if drops:
                self.logger.info(f"{self.current_character}: Drops:")
                for drop in drops:
                    self.logger.info(f"{self.current_character}:   - {drop['code']}: {drop['quantity']}")
            
            if result == "loss":
                self.move_character(original_x, original_y)

            if level > original_level:
                self.logger.info(f"level up! End fight loop")

        return response

    def fight_drop(self, quantity: int, item_code: str):
        total = 0
        losses = 0
        start_x = self.api.char.pos.x
        start_y = self.api.char.pos.y
        while total < quantity and losses < 3:
            self.logger.info(f"{self.current_character}: Fight for {quantity - total} more {item_code}")

            current_hp = self.api.char.hp
            max_hp = self.api.char.max_hp
            self.logger.info(f"{self.current_character}: Current hp {current_hp}, Max hp {max_hp}")

            if current_hp < (max_hp * .5):
                if (self.eat()):
                    self.logger.info("Ate food, no rest for the wicked")
                else:
                    self.rest()

            self.logger.info(f"{self.current_character}: Fight!!!")
            response = self.api.actions.fight()
            if not response:
                self.logger.info(f"fight_drop no response Can't beat monster to get {item_code}")
                return False

            fight_data = response.get("data", {}).get("fight", {})
            result = fight_data.get("result", "unknown")
            xp_gained = fight_data.get("xp", 0)
            gold_gained = fight_data.get("gold", 0)
            drops = fight_data.get("drops", [])

            character_data = response.get("data", {}).get("character", {})
            xp = character_data.get("xp", 0)
            max_hp = character_data.get("max_xp", 0)
            level = character_data.get("level", 0)

            self.logger.info(f"{self.current_character}: Fight result: {result}")
            self.logger.info(f"{self.current_character}: XP gained: {xp_gained}")
            self.logger.info(f"{self.current_character}: Gold gained: {gold_gained}")
            self.logger.info(f"{self.current_character}: Level {level} progress {xp}/{max_hp}")

            if result == "loss":
                self.logger.info(f"Can't beat monster to get {item_code}, losses {losses + 1}")
                self.move_character(start_x, start_y)
                losses += 1

            if drops:
                self.logger.info(f"{self.current_character}: Drops:")
                for drop in drops:
                    self.logger.info(f"{self.current_character}:   - {drop['code']}: {drop['quantity']}")
                    if drop['code'] == item_code:
                        total += drop.get('quantity',1)
        return losses < 3
    
    def get_skill_level(self, skill_name: str) -> int:
        # Construct the attribute name for the skill level
        level_attribute = f"{skill_name.lower()}_level"

        # Use getattr to dynamically access the attribute
        try:
            return getattr(self.api.char, level_attribute)
        except AttributeError:
            # Handle the case where the skill does not exist
            print(f"Skill '{skill_name}' not found.")
            return -1

    def get_slot(self, slot_name: str) -> str:
        level_attribute = f"{slot_name.lower()}"
        if not slot_name.endswith("_slot"):
            slot_name += "_slot"
        try:
            return getattr(self.api.char, level_attribute)
        except AttributeError:
            print(f"slot_name '{slot_name}' not found.")
            return None
        
    def get_character(self):
        """
        Retrieves the current character details
        """
        return self.api.char

    def move_character(self, x: int, y: int):
        """
        Moves the character to the specified (x, y) position, waits for the cooldown period,
        and logs the wait time. Treats the 490 error as a no-op (already at the target location).

        Args:
            x (int): The target x-coordinate.
            y (int): The target y-coordinate.
        """
        if self.api.char.pos.x == x and self.api.char.pos.y == y:
            return
        self.api.actions.move(x,y)

    def exchange_task_coins(self):
        self.logger.info(f"{self.current_character}: exchange task coins")
        response = self.api.actions.taskmaster_exchange_task()
        if response:
            self.logger.info(f"{self.current_character}: Exchanged task coins")
            self.logger.info(response)

    def make_api_request(self, func, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            retry = self.handle_error(e)
            if retry:
                return self.make_api_request(func, args, kwargs)

    def handle_cooldown(self, cooldown: Dict):
        """
        Handles the cooldown period specified in the response.

        Args:
            cooldown (Dict): The cooldown details from the API response.
        """
        remaining_seconds = cooldown.get("remaining_seconds", 0)
        if remaining_seconds > 0:
            self.logger.info(f"{self.current_character}: Waiting for cooldown: {remaining_seconds} seconds")
            time.sleep(remaining_seconds)
            self.logger.info(f"{self.current_character}: Cooldown period over. Ready for the next action.")
        else:
            self.logger.info(f"{self.current_character}: No cooldown. Ready for the next action.")

    def handle_error(self, e: Exception):
        self.logger.info("handle error")
        if isinstance(e, requests.exceptions.HTTPError):
            if e.response is not None:
                if e.response.status_code == 499:
                    try:
                        response_data = e.response.json()
                        error_message = response_data.get("error", {}).get("message", "")
                        if "cooldown" in error_message.lower():
                            match = re.search(r"(\d+\.?\d*) seconds left", error_message)
                            if match:
                                cooldown_seconds = float(match.group(1))
                                self.logger.info(f"{self.current_character}: Cooldown detected. Waiting for {cooldown_seconds} seconds.")
                                time.sleep(cooldown_seconds)
                                return True
                            else:
                                self.logger.error(f"{self.current_character}: Cooldown duration not found in the error message.")
                        else:
                            self.logger.error(f"{self.current_character}: Custom error (499) occurred. Check response headers for details.")
                    except ValueError:
                        self.logger.error(f"{self.current_character}: Failed to parse the response body as JSON.")
                elif e.response.status_code > 400 and e.response.status_code < 500:
                    self.logger.info(f"{self.current_character}: No action taken. Code {e.response.status_code}")
                else:
                    self.logger.error(f"{self.current_character}: HTTP error occurred: {e}")
        else:
            self.logger.error(f"{self.current_character}: An error occurred: {e}")

        return False