from typing import Dict
from work.api import CharacterAPI
import os

logger = None
api = CharacterAPI
character: str

def setup_tasks(m_logger, m_token, m_character):
    global logger, api, character
    logger = m_logger
    character = m_character
    api = CharacterAPI(logger, m_token, m_character)

def craft(character: CharacterAPI, code: str = 'copper_armor'):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    response = character.get_item_spec(code)
    if not response:
        logger.info(f"No item {code}")
        return
    
    craft_data = response.get("data", {}).get("craft", {})
    if not craft_data:
        logger.info(f"No item {code}")
        return
    
    skill = craft_data.get('skill','')
    items = craft_data.get('items',[])
    for item in items:
        item_code = item.get('code','')
        item_quantity = item.get('quantity',0)
        response = character.withdraw_from_bank(item_code,item_quantity)
        if not response:
            logger.info(f"Not enough {item_code} to make {code}")
            return
        
    x,y = character.find_closest_content('workshop', skill)
    character.move_character(x,y)
    character.craft(code)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def make_gear(character: CharacterAPI):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.withdraw_from_bank('feather',2)
    character.withdraw_from_bank('copper',5)
    x,y = character.find_closest_content('workshop', 'gearcrafting')
    character.move_character(x,y)
    character.unequip('weapon')
    character.craft('copper_legs_armor',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def gather_sunflowers_and_craft_gear(character: CharacterAPI):
    flowers_x,flowers_y = find_sunflowers()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()

    response = character.withdraw_from_bank('copper',6)
    while response:
        x,y = character.find_closest_content('workshop', 'jewelrycrafting')
        character.move_character(x,y)
        character.craft('copper_ring',1)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()
        response = character.withdraw_from_bank('copper',6)

    character.move_character(flowers_x, flowers_y)
    character.gather(10)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def gather_copper_and_craft_gear(character: CharacterAPI):
    copper_x,copper_y = find_copper()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()

    response = character.withdraw_from_bank('copper',6)
    while response:
        x,y = character.find_closest_content('workshop', 'jewelrycrafting')
        character.move_character(x,y)
        character.craft('copper_ring',1)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()
        response = character.withdraw_from_bank('copper',6)

    character.move_character(copper_x, copper_y)
    character.gather(10)
    character.move_character(forge_x,forge_y)
    character.craft('copper',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def gather_copper_and_craft_weapons_loop(character: CharacterAPI):
    copper_x,copper_y = find_copper()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()

    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

    while True:
        response = character.withdraw_from_bank('copper',6)
        while response:
            x,y = character.find_closest_content('workshop', 'weaponcrafting')
            character.move_character(x,y)
            character.craft('copper_dagger',1)
            character.move_character(bank_x,bank_y)
            character.deposit_all_inventory_to_bank()
            response = character.withdraw_from_bank('copper',6)

        character.move_character(copper_x, copper_y)
        character.gather(10)
        character.move_character(forge_x,forge_y)
        character.craft('copper',1)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()


def do_tasks(character: CharacterAPI):
    task = character.choose_task()
    handle_task(character, task)

def clear_copper_ore(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    character.withdraw_all('copper_ore')

    x,y = find_forge()
    character.move_character(x,y)
    character.craft('copper',10)

def clear_ash_wood(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    character.withdraw_all('ash_wood')

    x,y = character.find_closest_content('workshop', 'woodcutting')
    character.move_character(x,y)
    character.craft('ash_plank',10)

    x,y = find_gearcraft()
    character.move_character(x,y)
    character.craft('wooden_shield',1)

def kill_next_weakest(character: CharacterAPI):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    character.fight_xp()

def make_wooden_shield(character: CharacterAPI):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.withdraw_from_bank('ash_plank',4)

    shop_x,shop_y = find_weaponcraft()
    character.move_character(shop_x, shop_y)
    character.unequip("weapon")
    character.craft('wooden_staff')
    character.move_character(bank_x,bank_y)
    character.deposit_to_bank('wooden_staff',1)

def gather_copper(character : CharacterAPI):
    copper_x,copper_y = find_copper()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()
    character.move_character(copper_x, copper_y)
    character.gather(30)
    character.move_character(forge_x,forge_y)
    character.craft('copper',3)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def gather_wood_loop(character: CharacterAPI):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    wood_x,wood_y = character.find_closest_content('resource', 'ash_tree')
    woodcutting_x,woodcutting_y = character.find_closest_content('workshop', 'woodcutting')
    character.deposit_all_inventory_to_bank()

    while True:
        character.move_character(wood_x, wood_y)
        character.gather(10)
        character.move_character(woodcutting_x,woodcutting_y)
        character.craft('ash_plank',1)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()

def find_bank():
    logger.info("bank at (4,1)")
    return 4,1

def find_monster():
    logger.info("chicken at (0,1)")
    # there is a chicken at 0,1
    return 0,1

def find_weaponcraft():
    logger.info("weaponcraft at (2,1)")
    return 2,1

def find_gearcraft():
    logger.info("gearcraft at (3,1)")
    return 3,1

def find_copper():
    logger.info("copper rocks at (2,0)")
    return 2,0

def find_sunflowers():
    logger.info("sunflowers at (2,2)")
    return 2,2

def find_forge():
    logger.info("forge at (1,5)")
    return 1,5

def find_taskmaster():
    logger.info("taskmaster at (1,2)")
    return 1,2


def handle_monsters_task(character: CharacterAPI, task_data: Dict):
    logger.info(f"Handling monsters task: {task_data}")
    
    # Find the closest monster and move to its location
    x, y = character.find_closest_content("monster", task_data['code'])
    character.move_character(x, y)
    
    # Check if 'progress' key exists in task_data
    if 'progress' in task_data:
        progress = task_data['progress']
    else:
        progress = 0
    
    # Calculate the number of combats needed
    total = task_data['total']
    combats = total - progress + 1
    
    # Engage in combat
    character.fight(combats)
    
    # Find the taskmaster and move to their location
    x, y = find_taskmaster()
    character.move_character(x, y)
    
    # Complete the task
    character.complete_task()

def handle_unknown_task(task_data: Dict):
    """
    Handles an unknown task type.

    Args:
        task_data (Dict): The task data.
    """
    logger.warning(f"Unknown task type: {task_data.get('type')}")
    # Add your logic for handling unknown tasks here

# Dictionary to map task types to their respective handlers
task_handlers = {
    "monsters": handle_monsters_task,
}

def handle_task(character: CharacterAPI, task_data: Dict):
    """
    Dispatches the task to the appropriate handler based on its type.

    Args:
        task_data (Dict): The task data.
    """
    task_type = task_data.get("type")
    handler = task_handlers.get(task_type, handle_unknown_task)
    handler(character, task_data)

def exchange_task_coins(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    character.withdraw_from_bank('tasks_coin',6)
    x,y = find_taskmaster()
    character.move_character(x,y)
    character.exchange_task_coins()
    x,y = find_bank()
    character.move_character(x,y)
    character.deposit_all_inventory_to_bank()

def alltasks():
    function_mapping = {name: obj for name, obj in globals().items() if callable(obj)}
    return function_mapping
