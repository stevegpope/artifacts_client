import math
import time
import requests
import logging
from typing import Optional, Dict, List, Tuple
import re
from artifactsmmo_wrapper import wrapper, logger, ArtifactsAPI
from artifactsmmo_wrapper.subclasses import *

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
        return self.api.items.get(item_code)
    
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
        inventory = self.api.char.inventory

        if not inventory:
            self.logger.info(f"{self.current_character}: Inventory is empty. Nothing to deposit.")
            return

        for item in inventory:
            code = item.code
            quantity = item.quantity

            # Skip empty slots or items with zero quantity
            if not code or quantity <= 0:
                continue

            self.api.actions.bank_deposit_item(code, quantity)

        self.logger.info(f"{self.current_character}: All items deposited into the bank.")

    def fight_xp(self):
        self.logger.info('Fight loop')
        level = self.api.char.level
        target_monster_level = level - 10

        monsters = self.api.monsters.get(min_level=target_monster_level)
        if not monsters:
            self.logger.info('No monsters found within the level range')
            return None
        
        # Find the monster closest to target_monster_level
        closest_monster = min(monsters, key=lambda x: abs(x.level - target_monster_level))
        self.logger.info(f'Closest monster found: {closest_monster.name} (Level {closest_monster.level})')
        
        x,y = self.find_closest_content('monster', closest_monster.code)
        self.move_character(x, y)

        fights = 0
        while True:
            response = self.fight()
            data = response.get("data", {})
            character_data = data.get("character", {})
            new_level = character_data['level']
            fights += 1

            # Check if the player leveled up
            if new_level > level:
                self.logger.info(f"Level up! New level: {new_level}")
                return
            if fights >= 10:
                self.logger.info("enough fighting for now, check tasks")
                return

    def find_closest_content(self, content_type: str, content_code: str):
        maps_data = self.api.maps.get(content_code=content_code, content_type=content_type)

        char_x = self.api.char.pos.x
        char_y = self.api.char.pos.y
        
        # Initialize variables to store the closest tile's coordinates and distance
        closest_distance = float('inf')
        x = None
        y = None
        
        # Iterate through all map tiles
        for tile in maps_data:
            # Calculate the Euclidean distance between the character and the tile
            distance = math.sqrt((tile.x - char_x)**2 + (tile.y - char_y)**2)
            
            # Update the closest tile if this tile is closer
            if distance < closest_distance:
                closest_distance = distance
                x = tile.x
                y = tile.y
        
        self.logger.info(f"closest {content_type} {content_code} at {x},{y}")
        return x,y

    def get_bank_contents(self, page: int = 1) -> List[Dict]:
        all_data = []
        response = self.api.account.get_bank_items(page = page)
        total_pages = response.get("pages",1)
        self.logger.info(f"{self.current_character}: Fetched page {page} of {total_pages}")
        all_data.extend(response.get("data",[]))
        page += 1
        if page <= total_pages:
            return self.get_bank_contents(page)
        return all_data
    
    def withdraw_all(self, code: str) -> int:
        contents = self.get_bank_contents()
        for item in contents:
            if item["code"] == code:
                quantity = item['quantity']
                take = min(25,quantity)
                self.withdraw_from_bank(code,take)
                return take
        return 0

    def withdraw_from_bank(self, code: str, quantity: int) -> Optional[Dict]:
        try:
            response = self.api.actions.bank_withdraw_item(code, quantity)
            if response:
                self.logger.info(f"{self.current_character}: Successfully withdrew {quantity} of {code} from the bank")
                return response
            else:
                self.logger.error(f"{self.current_character}: Failed to withdraw items from the bank.")
        except:
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
            self.logger.info(f"{self.current_character}: Successfully recycled {quantity} of {code}.")
            return response
        else:
            self.logger.error(f"{self.current_character}: Failed to recycle")
            return None

    def choose_task(self) -> Optional[Dict]:
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
        x, y = self.find_taskmaster()
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

    def find_taskmaster(self):
        self.logger.info(f"{self.current_character}: items taskmaster at (4,13)")
        return 4, 13

    def complete_task(self):
        self.logger.info(f"{self.current_character}: Complete task")
        response = self.api.actions.taskmaster_complete_task()
        if response:
            self.logger.info(f"{self.current_character}: Successfully completed task: {response}")

    def trade_task_items(self, code: str, quantity: int):
        payload = {
            "code": code,
            "quantity": quantity
        }

        self.logger.info(f"{self.current_character}: Trade in {quantity} {code}")
        response = self.api.actions.taskmaster_trade_task(code, quantity)
        if response:
            self.logger.info(f"{self.current_character}: Successfully traded items")

    def equip_utility(self, code: str):
        existing_quantity = 0
        slot = 'utility1'
        if self.api.char.utility1_slot == code or self.api.char.utility1_slot == '':
            slot = 'utility1'
            existing_quantity = self.api.char.utility1_slot_quantity
        elif self.api.char.utility2_slot == code or self.api.char.utility2_slot == '':
            slot = 'utility2'
            existing_quantity = self.api.char.utility2_slot_quantity
        else:
            self.logger.info("No slots available")

        for item in self.api.char.inventory:
            if item.code == code:
                quantity = item['quantity']
                max_equip = 100 - existing_quantity
                equip_quantity = min(quantity, max_equip)

                payload = {
                    "code": code,
                    "slot": slot,
                    "quantity": equip_quantity
                }

                self.logger.info(f"{self.current_character}: Equip {equip_quantity} {code} into {slot}")
                response = self.api.actions.equip_item(code, slot, quantity)
                if response:
                    self.logger.info(f"{self.current_character}: Successfully equipped {code} into {slot}.")

    def equip(self, code: str, slot: str):
        """
        Equips an item with the specified code into the specified slot.

        Args:
            code (str): The code of the item to equip (e.g., "wooden_staff").
            slot (str): The slot to equip the item into (e.g., "weapon").
        """
        self.logger.info(f"{self.current_character}: Equip {code} into {slot}")
        try:
            response = self.api.actions.equip_item(code, slot)
        except:
            pass

        if response:
            self.logger.info(f"{self.current_character}: Successfully equipped {code} into {slot}.")
            return True
        return False

    def craft(self, item_code: str, amount: int = 1):
        """
        Crafts an item with the specified code and waits for the cooldown period.

        Args:
            item_code (str): The code of the item to craft (e.g., "wooden_staff").
            amount (int): The number of items to craft. Defaults to 1.
        """
        self.logger.info(f"{self.current_character}: Crafting {item_code} {amount} time(s)")
        self.unequip('weapon')

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
        self.logger.info(f"{self.current_character}: Unequip {slot}")
        slot_attribute = f"{slot.lower()}_slot"
        # Use getattr to dynamically access the attribute
        try:
            slot_value = getattr(self.api.char, slot_attribute)
            self.logger.info(f"{slot_attribute}:{slot_value}")
        except AttributeError:
            print(f"slot '{slot}' not found.")
            return

        if slot_value:
            self.logger.info("unequip")
            response = self.api.actions.unequip_item(slot)
            if response:
                self.logger.info(f"{self.current_character}: Successfully unequipped item from slot: {slot}")
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
            response = self.api.actions.gather()
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
            response = self.api.actions.rest()
            if not response:
                return
            
            data = response.get("data", None)
            if data:
                character_data = data.get("data", {})
                hp = character_data.get("hp", 0)
                max_hp = character_data.get("max_hp", 0)
                hp_restored = response.get("data", {}).get("hp_restored", 0)

                self.logger.info(f"{self.current_character}: Restored {hp_restored} HP. Current HP: {hp}/{max_hp}")

                if hp >= max_hp:
                    self.logger.info(f"{self.current_character}: Character HP is fully restored.")
                    return
            
    def eat(self):
        for inventory_item in self.api.char.inventory:
            item_code = inventory_item.code
            item = self.api.items.get(item_code)

            if item.type == 'consumable' and item.subtype == 'food':
                response = self.api.actions.use_item(item_code, 1)
                if response:
                    self.logger.info(f"{self.current_character}: Ate {item.code}")
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

        for i in range(combats):
            self.logger.info(f"{self.current_character}: Starting combat {i + 1} of {combats}")

            current_hp = self.api.char.hp
            max_hp = self.api.char.max_hp
            self.logger.info(f"{self.current_character}: Current hp {current_hp}, Max hp {max_hp}")

            if current_hp / max_hp:
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

        return response

    def fight_drop(self, quantity: int, item_code: str):
        total = 0
        while total < quantity:
            self.logger.info(f"{self.current_character}: Fight for {quantity - total} more {item_code}")

            current_hp = self.api.char.hp
            max_hp = self.api.char.max_hp
            self.logger.info(f"{self.current_character}: Current hp {current_hp}, Max hp {max_hp}")

            if current_hp / max_hp:
                if (self.eat()):
                    self.logger.info("Ate food, no rest for the wicked")
                else:
                    self.logger.info(f"{self.current_character}: Health is below 50%. Resting...")
                    self.rest()

            self.logger.info(f"{self.current_character}: Fight!!!")
            response = self.api.actions.fight()
            if not response:
                self.logger.info(f"Can't beat monster to get {item_code}")
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
                self.logger.info(f"Can't beat monster to get {item_code}")
                return False

            if drops:
                self.logger.info(f"{self.current_character}: Drops:")
                for drop in drops:
                    self.logger.info(f"{self.current_character}:   - {drop['code']}: {drop['quantity']}")
                    if drop['code'] == item_code:
                        total += drop.get('quantity',1)
        return True
    
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

    def get_slot(self, slot_name: str) -> int:
        level_attribute = f"{slot_name.lower()}_slot"
        try:
            return getattr(self.api.char, level_attribute)
        except AttributeError:
            print(f"slot_name '{slot_name}' not found.")
            return -1
        
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
        self.logger.info(f"{self.current_character}: Move to {x},{y}")
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
                    self.logger.info(f"{self.current_character}: No action taken trying to {context}. Code {e.response.status_code}")
                else:
                    self.logger.error(f"{self.current_character}: HTTP error occurred: {e}")
        else:
            self.logger.error(f"{self.current_character}: An error occurred during {context}: {e}")

        return False