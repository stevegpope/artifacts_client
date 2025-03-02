import random
from typing import Dict, List
from work.api import CharacterAPI

from work.task_queue import TaskQueue

logger = None
api = CharacterAPI
character: str
items: List[Dict]
monsters: List[Dict]
resources: List[Dict]
task_queue: TaskQueue
m_role: str

def setup_tasks(m_logger, m_token, m_character, role):
    global logger, api, character, items, task_queue, monsters, m_role, resources
    logger = m_logger
    character = m_character
    m_role = role
    api = CharacterAPI(logger, m_token, m_character)
    items = api.fetch_items()
    monsters = api.fetch_monsters()
    resources = api.fetch_resources()
    task_queue = TaskQueue()
    if role == 'fighter':
        gear_up(api)

def fill_orders(character: CharacterAPI, role: str):
    tasks = task_queue.read_tasks()

    chosen_task = None
    index = 1
    for task in tasks:
        task_role = task.get('role',None)
        if task_role == role or task.get('code','') == 'feather':
            chosen_task = task
            task_queue.delete_task(index)
            break
        index += 1

    if not chosen_task:
        if (role == 'fighter'):
            character.fight_xp(25)
            return True
        elif (role == 'gatherer'):
            craft_gear(character)
            return True
    else:
        logger.info(f"fill order for {task['code']}")
        gather(character, task['code'])


def gear_up(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    contents = character.get_bank_contents()

    data = contents['data']
    character_data = character.get_character()
    for item in data:
        equip_better_item(character, item['code'], character_data)

def equip_better_item(character: CharacterAPI, item_code, character_data):
    new_item = get_item(item_code)
    item_type = new_item.get('type', None)
    item_level = new_item.get('level',1)

    if item_level > character_data.get('level',1):
        return False
    
    slots = ['weapon_slot','rune_slot','shield_slot','helmet_slot','body_armor_slot','leg_armor_slot','boots_slot','ring1_slot','ring2_slot','amulet_slot','bag_slot']

    if item_type:
        if item_type == 'ring':
            original_item = character_data.get(f'ring1_slot', None)
            if not equip_from_bank_if_better(character, new_item, original_item, 'ring1', character_data):
                original_item = character_data.get(f'ring2_slot', None)
                return equip_from_bank_if_better(character, new_item, original_item, 'ring2', character_data)
            else:
                return True
        else:
            slot = f'{item_type}_slot'
            if not slot in slots:
                return False
            original_item = character_data.get(slot, None)
            result = equip_from_bank_if_better(character, new_item, original_item, item_type, character_data)
            original_item = character_data.get(slot, None)
            return result
    return False

def equip_from_bank_if_better(character:CharacterAPI, new_item, original_item, slot, character_data):
    if not original_item:
        logger.info(f"{new_item['code']} is better than nothing, changing {slot}")
        character.withdraw_from_bank(new_item['code'],1)
        character.unequip(slot)
        character.equip(new_item['code'],slot)
        character_data[f"{slot}_slot"] = new_item['code']
        return True
    else:
        original = get_item(original_item)
        if original.get('level',0) < new_item.get('level',0):
            logger.info(f"{new_item['code']} is better than {original_item}, changing {slot}")
            character.unequip(slot)
            character.withdraw_from_bank(new_item['code'],1)
            character.equip(new_item['code'],slot)
            character_data[f"{slot}_slot"] = new_item['code']

    return True

def get_item(item_code):
    for item in items:
        if item['code'] == item_code:
            return item
    return None


def eat(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    character.withdraw_from_bank('small_health_potion',1)
    character.eat()
    return


def craft_gear(character: CharacterAPI):
    # - pick a skill
    # - choose an item at the highest level we can craft
    skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking']
    skill = random.choice(skills)
    item = choose_highest_item(character, skill)
    logger.info(f'highest level item {item}')
    craft_item(character, item)

def craft_item(character: CharacterAPI, item: Dict, quantity: int = 1):
    # - go to the bank and try to get everything needed
    # - until we have it:
    #   - order the items from gatherers
    #   - gather ourselves and come back
    craft = item.get('craft',None)
    if not craft:
        logger.info(f'cannot craft {item}')
        return False

    requirements = craft.get('items',{})

    first_pass = True
    while True:
        need_something = False
        for requirement in requirements:
            required_quantity = requirement['quantity'] * quantity
            if (character.withdraw_from_bank(requirement['code'],required_quantity)):
                logger.info(f"Already have {required_quantity} enough {requirement['code']} to craft")
            else:
                need_something = True
                if first_pass:
                    first_pass = False
                    if not order_items(character, requirement['code'],required_quantity):
                        logger.error(f"cannot get {requirement['code']}")
                        return False
        if not need_something:
            break
        else:
            fill_orders(character, m_role)

    logger.info(f"requirements met, go craft {item['code']}")
    skill = craft['skill']
    shop_x,shop_y = character.find_closest_content('workshop',skill)
    character.move_character(shop_x, shop_y)
    character.move_character(shop_x,shop_y)
    character.craft(item['code'],quantity)
    return True

def order_items(character: CharacterAPI, item_code: str, quantity: int):
    logger.info(f'Ordering {quantity} {item_code}')
    item = get_item(item_code)
    if item['type'] != 'resource':
        logger.info(f'item is not resource to gather: {item}')
        return False

    subtype = item.get('subtype','')
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    if subtype == 'mob':
        for index in range(quantity):
            task_queue.create_task({"role":"fighter","code": item_code})
        return True
    
    if item.get('craft', None) != None:
        logger.info(f'to gather {item_code} we need to craft it')
        if item_code == 'copper' or item_code == 'iron':
            for index in range(quantity):
                task_queue.create_task({"role":"gatherer","code": item_code})
        else:
            for index in range(quantity):
                craft_item(character, item, quantity)
        return True

    for index in range(quantity):
        task_queue.create_task({"role":"gatherer","code": item_code})
    return True

def gather_copper(character : CharacterAPI):
    logger.info("Gathering a copper")
    copper_x,copper_y = find_copper()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()
    character.move_character(copper_x, copper_y)
    character.gather(10)
    character.move_character(forge_x,forge_y)
    character.craft('copper',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    return True

def gather_iron(character : CharacterAPI):
    logger.info("Gathering an iron")
    bank_x,bank_y = find_bank()
    iron_x,iron_y = character.find_closest_content('resource','iron_rocks')
    forge_x,forge_y = find_forge()
    character.move_character(iron_x, iron_y)
    character.gather(10)
    character.move_character(forge_x,forge_y)
    character.craft('iron',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    return True

def choose_highest_item(character:CharacterAPI, skill: str):
    character_data = character.get_character()
    skill_level = character_data.get(f"{skill}_level", 0)
    
    craftable_items = [
        item for item in items
        if item.get("craft")
        and item["craft"].get("skill") == skill
        and item["craft"].get("level", 0) <= skill_level
    ]
    
    if not craftable_items:
        logger.info(f'cannot craft anything for {skill}')
        exit(1)
    
    highest_level = max(item.get("level", 0) for item in craftable_items)
    
    highest_level_items = [
        item for item in craftable_items
        if item.get("level") == highest_level
    ]

    chosen_item = random.choice(highest_level_items)
    craft = chosen_item.get('craft','')
    craft_items = craft.get('items','')
    for item in craft_items:
        if item['code'] == 'wooden_stick':
            return craft_gear(character)
        
    if chosen_item:
        return chosen_item
    else:
        return choose_highest_item(character, skill)

def gather(character: CharacterAPI, item_code: str):
    logger.info(f'Gather one {item_code}')

    if item_code == 'copper':
        return gather_copper(character)
    elif item_code == 'iron':
        return gather_iron(character)
    
    item = get_item(item_code)
    if item['type'] != 'resource':
        logger.info(f'item is not resource to gather: {item}')
        return False

    subtype = item.get('subtype','')
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    if subtype == 'mob':
        x,y = find_monster_drop(character, item_code)
        character.move_character(x,y)
        character.rest()
        character.fight(1)
        return True
    
    if item.get('craft', None) != None:
        logger.info(f'to gather {item_code} need to craft it')
        craft_item(character, item)
        return True

    x,y = find_resource_drop(character,item_code)
    character.move_character(x,y)
    character.gather(1)
    x,y = find_bank()
    character.move_character(x,y)
    character.deposit_all_inventory_to_bank()
    return True

def find_resource_drop(character: CharacterAPI, item_code: str):
    for resource in resources:
        drops = resource.get('drops',None)
        if drops:
            for drop in drops:
                if drop.get('code','') == item_code:
                    return character.find_closest_content('resource',resource['code'])
    return None


def find_monster_drop(character: CharacterAPI, item_code: str):
    for monster in monsters:
        drops = monster.get('drops',None)
        if drops:
            for drop in drops:
                if drop.get('code','') == item_code:
                    return character.find_closest_content('monster',monster['code'])
    return None

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

def gather_sunflowers_and_craft_potions(character: CharacterAPI):
    flowers_x,flowers_y = find_sunflowers()
    bank_x,bank_y = find_bank()
    alchemy_x,alchemy_y = find_alchemy()

    response = character.withdraw_from_bank('sunflower',60)
    while response:
        character.move_character(alchemy_x,alchemy_y)
        character.craft('small_health_potion',20)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()
        response = character.withdraw_from_bank('sunflower',60)

    character.move_character(flowers_x, flowers_y)
    character.gather(60)
    character.move_character(alchemy_x,alchemy_y)
    character.craft('small_health_potion',20)
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

def gather_copper_and_craft_weapons(character: CharacterAPI):
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
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()

    response = character.withdraw_from_bank('copper_ore',10)
    while response:
        character.move_character(forge_x,forge_y)
        character.craft('copper',1)
        character.move_character(bank_x,bank_y)
        character.deposit_all_inventory_to_bank()
        response = character.withdraw_from_bank('copper_ore',10)


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

def hunt_chickens(character: CharacterAPI):
    x,y = character.find_closest_content('monster','chicken')
    character.move_character(x,y)
    character.fight(25)
    x,y = find_bank()
    character.move_character(x,y)
    character.deposit_all_inventory_to_bank()

def cut_ash_like_mad(character: CharacterAPI):
    base_x,base_y = character.find_closest_content('resource','ash_tree')
    character.move_character(base_x, base_y)
    character.gather(3000)

def find_bank():
    logger.info("bank at (4,1)")
    return 4,1

def find_alchemy():
    logger.info("alchemy at (2,3)")
    return 2,3

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
    
    # Take as many health potions with us as possible
    logger.info("Get some potions for fighting")
    x,y = find_bank()
    character.move_character(x,y)
    if character.withdraw_all('small_health_potion'):
        character.equip_utility('small_health_potion')

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
