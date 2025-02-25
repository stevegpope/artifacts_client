import math
import time
import requests
import logging
from typing import Optional, Dict, List, Tuple
import re

class CharacterAPI:
    def __init__(self, logger: logging.Logger, token: str, character_name: str):
        """
        Initializes the CharacterAPI with the provided logger, token, and character name.

        Args:
            logger (logging.Logger): The logger instance.
            token (str): The bearer token for authorization.
            character_name (str): The name of the character.
        """
        self.logger = logger
        self.current_token = token
        self.current_character = character_name
        self.character = self.get_character()
        self.logger.info(self.character)

    def deposit_all_inventory_to_bank(self):
        """
        Iterates through the character's inventory and deposits all items into the bank.
        """
        if not self.character:
            self.logger.error(f"{self.current_character}: Character data not available.")
            return

        inventory = self.character.get("inventory", [])
        if not inventory:
            self.logger.info(f"{self.current_character}: Inventory is empty. Nothing to deposit.")
            return

        for item in inventory:
            code = item.get("code")
            quantity = item.get("quantity", 0)

            # Skip empty slots or items with zero quantity
            if not code or quantity <= 0:
                continue

            self.deposit_to_bank(code, quantity)

        self.logger.info(f"{self.current_character}: All items deposited into the bank.")

    def fight_xp(self):
        self.logger.info('Fight loop')

        monster_level = 1
        character = self.get_character()
        level = character['level']
        first_loss = False

        while True:
            response = self.make_api_request('GET', f'/monsters?&max_level={monster_level}')
        
            if not response or 'data' not in response:
                self.logger.error('No monsters found or invalid response')
                return None
        
            monsters = response['data']
            if not monsters:
                self.logger.info('No monsters found within the level range')
                return None
        
            weakest_monster = max(monsters, key=lambda x: x['level'])
            self.logger.info(f'Weakest monster found: {weakest_monster["name"]} (Level {weakest_monster["level"]})')
        
            x,y = self.find_closest_content('monster', weakest_monster['code'])
            self.move_character(x,y)
            response = self.fight()
            data = response.get("data", {})
            fight_data = data.get("fight", {})
            character_data = data.get("character",{})
            new_level = character_data['level']
            result = fight_data.get("result", "unknown")

            # Go back on a loss
            if result != 'win':
                first_loss = True
                monster_level -= 1
                self.rest()
                self.logger.info(f"Lost, going back to level {monster_level}")

            # Go up if we never lost
            if not first_loss:
                monster_level += 1
                self.rest()
                self.logger.info(f"Never lost, going up to level {monster_level}")

            # Try to go up on level up
            if new_level > level:
                level = new_level
                monster_level += 1
                self.rest()
                self.logger.info(f"Level up, going up to level {monster_level}")


    def find_closest_content(self, content_type: str, content_code: str):
        details = self.get_character()
        # Get the character's current position
        char_x = details['x']
        char_y = details['y']
        
        # Initialize variables to store the closest tile's coordinates and distance
        closest_distance = float('inf')
        x = None
        y = None
        
        # Iterate through all map tiles
        maps_data = self.fetch_maps(content_type, content_code)
        for tile in maps_data:
            # Calculate the Euclidean distance between the character and the tile
            distance = math.sqrt((tile['x'] - char_x)**2 + (tile['y'] - char_y)**2)
            
            # Update the closest tile if this tile is closer
            if distance < closest_distance:
                closest_distance = distance
                x = tile['x']
                y = tile['y']
        
        return x,y

    def get_bank_contents(self) -> Optional[Dict]:
        self.logger.info(f"{self.current_character}: Getting bank contents")
        
        # Make the API request
        response = self.make_api_request(
            "GET",
            f"/my/bank/items"
        )

        if response:
            self.logger.info(f"{self.current_character}: {response}")
            return response
        
        return None

    def withdraw_all(self, code: str) -> int:
        contents = self.get_bank_contents()
        data = contents['data']
        for item in data:
            if item['code'] == code:
                quantity = item['quantity']
                self.withdraw_from_bank(code,quantity)
                return quantity
        return 0

    def withdraw_from_bank(self, code: str, quantity: int) -> Optional[Dict]:
        """
        Withdraws the specified item from the character's bank.

        Args:
            code (str): The code of the item to withdraw (e.g., "wooden_staff").
            quantity (int): The quantity of the item to withdraw.

        Returns:
            Optional[Dict]: The API response, or None if the request fails.
        """
        self.logger.info(f"{self.current_character}: Withdrawing {quantity} of {code} from the bank.")
        
        # Prepare the payload
        payload = {
            "code": code,
            "quantity": quantity
        }

        # Make the API request
        response = self.make_api_request(
            "POST",
            f"/my/{self.current_character}/action/bank/withdraw",
            payload
        )

        if response:
            self.logger.info(f"{self.current_character}: Successfully withdrew {quantity} of {code} from the bank.")
            return response
        else:
            self.logger.error(f"{self.current_character}: Failed to withdraw items from the bank.")
            return None
    
    def deposit_to_bank(self, code: str, quantity: int) -> Optional[Dict]:
        """
        Deposits the specified item into the character's bank.

        Args:
            code (str): The code of the item to deposit (e.g., "wooden_staff").
            quantity (int): The quantity of the item to deposit.

        Returns:
            Optional[Dict]: The API response, or None if the request fails.
        """

        if (quantity <= 0):
            return
        
        self.logger.info(f"{self.current_character}: Depositing {quantity} of {code} into the bank.")
        
        # Prepare the payload
        payload = {
            "code": code,
            "quantity": quantity
        }

        # Make the API request
        response = self.make_api_request(
            "POST",
            f"/my/{self.current_character}/action/bank/deposit",
            payload
        )

        if response:
            self.logger.info(f"{self.current_character}: Successfully deposited {quantity} of {code} into the bank.")
            return response
        else:
            self.logger.error(f"{self.current_character}: Failed to deposit items into the bank.")
            return None

    def choose_task(self) -> Optional[Dict]:
        """
        Returns the current task from the character data if one exists.
        Otherwise, requests a new task from the API.

        Returns:
            Optional[Dict]: The current or newly assigned task data, or None if no task is available.
        """
        if not self.character:
            self.logger.error(f"{self.current_character}: Character data not available.")
            return None

        # Check if the character already has a task
        current_task = self.character.get("task")
        current_task_type = self.character.get("task_type")
        task_total = self.character.get("task_total", 0)
        task_progress = self.character.get("task_progress", 0)

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
        self.logger.info("{self.current_character}: No current task. Requesting a new task...")
        x, y = self.find_taskmaster()
        self.move_character(x, y)
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/task/new")
        if not response:
            self.logger.error("{self.current_character}: Failed to request a new task.")
            return None

        # Extract the task data from the response
        task_data = response.get("data", {}).get("task", {})
        if not task_data:
            self.logger.error("{self.current_character}: No task data found in the response.")
            return None

        # Log the assigned task details
        self.logger.info(f"{self.current_character}: Assigned task: {task_data['code']} (Type: {task_data['type']})")
        self.logger.info(f"{self.current_character}:   - Total: {task_data['total']}")
        self.logger.info(f"{self.current_character}:   - Rewards: {task_data['rewards']}")

        return task_data

    def find_taskmaster(self):
        self.logger.info("{self.current_character}: taskmaster at (1,2)")
        return 1, 2

    def complete_task(self):
        self.logger.info(f"{self.current_character}: Complete task")
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/task/complete")
        if response:
            self.logger.info(f"{self.current_character}: Successfully completed task: {response}")

    def equip(self, code: str, slot: str):
        """
        Equips an item with the specified code into the specified slot.

        Args:
            code (str): The code of the item to equip (e.g., "wooden_staff").
            slot (str): The slot to equip the item into (e.g., "weapon").
        """
        self.logger.info(f"{self.current_character}: Equip {code} into {slot}")
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/equip", {"code": code, "slot": slot})
        if response:
            self.logger.info(f"{self.current_character}: Successfully equipped {code} into {slot}.")

    def craft(self, item_code: str, amount: int = 1):
        """
        Crafts an item with the specified code and waits for the cooldown period.

        Args:
            item_code (str): The code of the item to craft (e.g., "wooden_staff").
            amount (int): The number of items to craft. Defaults to 1.
        """
        self.logger.info(f"{self.current_character}: Crafting {item_code} {amount} time(s)")

        for _ in range(amount):
            response = self.make_api_request("POST", f"/my/{self.current_character}/action/crafting", {"code": item_code})
            if not response:
                self.logger.error(f"{self.current_character}: Failed to craft item.")
                return

            # Log the crafting results
            details = response.get("data", {}).get("details", {})
            xp_gained = details.get("xp", 0)
            items_crafted = details.get("items", [])

            character_json = response.get("data", {}).get("character", {})

            self.logger.info(f"{self.current_character}: Crafted {item_code}")
            self.logger.info(f'weaponcraft level {character_json.get("weaponcrafting_level", 0)} {character_json.get("weaponcrafting_xp", 0)}/{character_json.get("weaponcrafting_max_xp", 0)}')
            self.logger.info(f'gearcraft level {character_json.get("gearcrafting_level", 0)} {character_json.get("gearcrafting_xp", 0)}/{character_json.get("gearcrafting_max_xp", 0)}')
            self.logger.info(f'jewelrycraft level {character_json.get("jewelrycrafting_level", 0)} {character_json.get("jewelrycrafting_xp", 0)}/{character_json.get("jewelrycrafting_max_xp", 0)}')
            self.logger.info(f'alchemy level {character_json.get("alchemy_level", 0)} {character_json.get("alchemy_xp", 0)}/{character_json.get("alchemy_max_xp", 0)}')
            if items_crafted:
                self.logger.info(f"{self.current_character}: Items crafted:")
                for item in items_crafted:
                    self.logger.info(f"{self.current_character}:   - {item['code']}: {item['quantity']}")

    def unequip(self, slot: str):
        """
        Unequips an item from the specified slot.

        Args:
            slot (str): The slot to unequip (e.g., "weapon", "helmet", "ring1").
        """
        self.logger.info(f"{self.current_character}: Unequip {slot}")
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/unequip", {"slot": slot})
        if response:
            self.logger.info(f"{self.current_character}: Successfully unequipped item from slot: {slot}")

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
            response = self.make_api_request("POST", f"/my/{self.current_character}/action/gathering")
            if not response:
                continue

            details = response.get("data", {}).get("details", {})
            xp_gained = details.get("xp", 0)
            items_gathered = details.get("items", [])

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
                return

    def rest(self):
        """
        Makes the character rest repeatedly until HP is fully restored.
        Waits for the cooldown period after each rest.
        """
        while True:
            self.logger.info(f"{self.current_character}: Resting...")
            response = self.make_api_request("POST", f"/my/{self.current_character}/action/rest")
            if not response:
                return

            character_data = response.get("data", {}).get("character", {})
            hp = character_data.get("hp", 0)
            max_hp = character_data.get("max_hp", 0)
            hp_restored = response.get("data", {}).get("hp_restored", 0)

            self.logger.info(f"{self.current_character}: Restored {hp_restored} HP. Current HP: {hp}/{max_hp}")

            if hp >= max_hp:
                self.logger.info(f"{self.current_character}: Character HP is fully restored.")
                return
            
    def eat(self, character_data):
        for item in character_data['inventory']:
            if item['code'] == 'apple':
                payload = {
                    "code": 'apple',
                    "quantity": 1
                }

                response = self.make_api_request(
                    "POST",
                    f"/my/{self.current_character}/action/use",
                    payload
                )
                if response:
                    self.logger.info(f"{self.current_character}: Ate an apple")
                    character_json = response.get("data", {}).get("character", {})
                    hp = character_json['hp']
                    max_hp = character_json['max_hp']
                    if (hp < (max_hp/2)):
                        self.eat(character_data)
                    return True
        return False

    def fight(self, combats=1):
        """
        Initiates a fight, waits for the cooldown period, and rests if health is below 50%.
        """
        character_data = self.get_character()
        original_x = character_data.get('x',0)
        original_y = character_data.get('y',0)

        for i in range(combats):
            self.logger.info(f"{self.current_character}: Starting combat {i + 1} of {combats}")

            character_data = self.get_character()
            current_hp = character_data.get("hp", 0)
            max_hp = character_data.get("max_hp", 1)
            self.logger.info(f"{self.current_character}: Current hp {current_hp}, Max hp {max_hp}")

            if current_hp / max_hp < 0.5:
                if (self.eat(character_data)):
                    self.logger.info("Ate food, no rest for the wicked")
                else:
                    self.logger.info(f"{self.current_character}: Health is below 50%. Resting...")
                    self.rest()

            self.logger.info(f"{self.current_character}: Fight!!!")
            response = self.make_api_request("POST", f"/my/{self.current_character}/action/fight")
            if not response:
                self.logger.info("Fucker moved me!")
                self.move_character(original_x, original_y)
                self.fight(combats - i)
                return

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
            
        return response

    def get_character(self):
        """
        Retrieves the current character details
        """
        response = self.make_api_request("GET", f"/my/characters")
        if not response:
            return None

        characters_data = response.get("data", [])
        for character in characters_data:
            if character.get("name") == self.current_character:
                return character

        self.logger.error(f"Character '{self.current_character}' not found.")
        return None

    def move_character(self, x: int, y: int):
        """
        Moves the character to the specified (x, y) position, waits for the cooldown period,
        and logs the wait time. Treats the 490 error as a no-op (already at the target location).

        Args:
            x (int): The target x-coordinate.
            y (int): The target y-coordinate.
        """
        self.logger.info(f"{self.current_character}: Move to {x},{y}")
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/move", {"x": x, "y": y})
        if response:
            self.logger.info(f"{self.current_character}: Moved to {response['data']['destination']}")

    def exchange_task_coins(self):
        self.logger.info(f"{self.current_character}: exchange task coins")
        response = self.make_api_request("POST", f"/my/{self.current_character}/action/task/exchange")
        if response:
            self.logger.info(f"{self.current_character}: Exchanged task coins")
            self.logger.info(response)

    def get_item_spec(self, code: str):
        return self.make_api_request("GET", f"/items/{code}")

    def fetch_maps(self, content_type: str = None, content_code: str = None) -> List[Dict]:
        """
        Fetches the entire map data from the ArtifactsMMO API by handling pagination.

        Args:
            content_type (str, optional): The type of content to filter by. Defaults to None.
            content_code (str, optional): The code of the content to filter by. Defaults to None.

        Returns:
            List[Dict]: A list of all map data entries across all pages.
        """
        all_data = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            # Build the query string based on provided parameters
            query_params = f"page={page}"
            if content_type:
                query_params += f"&content_type={content_type}"
            if content_code:
                query_params += f"&content_code={content_code}"

            # Make the API request with the constructed query string
            response = self.make_api_request("GET", f"/maps?{query_params}")
            if not response:
                break

            # Append the data and update pagination details
            all_data.extend(response.get("data", []))
            total_pages = response.get("pages", 1)
            self.logger.info(f"{self.current_character}: Fetched page {page} of {total_pages}")
            page += 1

        return all_data

    def make_api_request(self, method: str, endpoint: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        """
        Makes an API request and returns the JSON response.

        Args:
            method (str): The HTTP method (e.g., "GET", "POST").
            endpoint (str): The API endpoint (e.g., "/action/rest").
            payload (Optional[Dict]): The request payload for POST requests.
            base_url (str): The base URL for the request. Defaults to "https://api.artifactsmmo.com".

        Returns:
            Optional[Dict]: The JSON response, or None if the request fails.
        """
        url = f"https://api.artifactsmmo.com{endpoint}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.current_token}"
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=payload)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            response_data = response.json()
            
            if isinstance(response_data, dict):
                data = response_data.get("data", {})
                
                if isinstance(data, dict):
                    cooldown = data.get("cooldown", {})
                    
                    if cooldown:
                        self.handle_cooldown(cooldown)

            return response.json()

        except requests.exceptions.RequestException as e:
            retry = self.handle_error(e, context=f"{method} request to {endpoint}")
            if retry:
                return self.make_api_request(method, endpoint, payload)

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

    def handle_error(self, e: requests.exceptions.RequestException, context: str = "API call"):
        """
        Handles errors from API requests and logs relevant details.
        If the error is a 499 with a cooldown message, waits for the specified cooldown.

        Args:
            e (requests.exceptions.RequestException): The exception object.
            context (str): A description of the context where the error occurred.
        """
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
            self.logger.error(f"{self.current_character}: An error occurred during {context}: {e}")

        return False