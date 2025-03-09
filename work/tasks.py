import random
from time import sleep
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
    items = api.items
    monsters = api.monsters
    resources = api.resources
    task_queue = TaskQueue()

banned_tasks = []

def fill_orders(character: CharacterAPI, role: str):
    global banned_tasks
    tasks = task_queue.read_tasks()
    logger.info(f"Fill orders for {role}")

    chosen_tasks = []
    chosen_code = None
    tasks_to_delete = []  # Track indices to remove after processing

    # Scan for tasks, collect up to 10 matching tasks
    for index, task in enumerate(tasks, start=1):
        logger.info(f"what about {task}")
        task_role = task.get('role', None)
        task_code = task.get('code', '')

        if not chosen_tasks:
            # First matching task — lock in the code and role
            if ((task_role == role or (task_role == 'forager' and role == 'crafter')) or role == 'smarty') and not task_code in banned_tasks:
                logger.info(f'first banned tasks: {banned_tasks}, code {task_code}')
                chosen_tasks.append(task)
                chosen_code = task_code
                tasks_to_delete.append(index)
        else:
            # Only collect tasks with the same role+code
            if (task_role == role or (task_role == 'forager' and role == 'crafter')) and task_code == chosen_code:
                chosen_tasks.append(task)
                tasks_to_delete.append(index)

        if len(chosen_tasks) >= 10:
            break

    # Delete tasks after iteration, in **reverse order** so indexes remain valid
    for index in reversed(tasks_to_delete):
        task_queue.delete_task(index)

    if role == 'fighter':
        gear_up(character)

    if not chosen_tasks:
        # Fallback behavior if no tasks found
        if role == 'fighter':
            character.fight_xp(50)
            return True
        elif role == 'crafter':
            craft_gear(character)
            return True
        elif role == 'tasker':
            do_tasks(character)
        elif role == 'forager':
            gather_highest(character)
        elif role == 'chef':
            craft_gear(character, 'cooking')
        elif role == 'alchemist':
            craft_gear(character, 'alchemy')
    else:
        # Perform the gathered tasks
        task_count = len(chosen_tasks)
        logger.info(f"Filling order for {chosen_code} - {task_count} tasks")
        if not gather(character, chosen_code, task_count):
            logger.info(f'cannot gather {chosen_code}!, re-insert tasks')
            banned_tasks.append(chosen_code)
            logger.info(f'banned tasks after add: {banned_tasks}')
            for task in chosen_tasks:
                task_queue.create_task(task)
    return True

def gather_highest(character: CharacterAPI):
    skills = ['mining', 'woodcutting', 'fishing','alchemy']
    skill = random.choice(skills)
    logger.info(f'think I will go {skill} now')
    if skill == 'mining':
        logger.info(f"try and get pick")
        if character.withdraw_from_bank('iron_pickaxe',1):
            character.unequip('weapon')
            character.equip('iron_pickaxe','weapon')
    elif skill == 'woodcutting':
        logger.info(f"try and get axe")
        if character.withdraw_from_bank('iron_axe',1):
            character.unequip('weapon')
            character.equip('iron_axe','weapon')
    elif skill == 'alchemy':
        logger.info(f"try and get gloves")
        if character.withdraw_from_bank('leather_gloves',1):
            character.unequip('weapon')
            character.equip('leather_gloves','weapon')
    elif skill == 'fishing':
        logger.info(f"try and get fishing rod")
        if character.withdraw_from_bank('spruce_fishing_rod',1):
            character.unequip('weapon')
            character.equip('spruce_fishing_rod','weapon')

    character_data = character.get_character()
    skill_level = character_data.get(f"{skill}_level", 0)
    x,y = choose_random_resource(character, skill, skill_level)
    character.move_character(x,y)
    character.gather(10)
    x,y = find_bank()
    character.move_character(x,y)
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()

def rest(character: CharacterAPI):
    character.rest()

def hunt_monsters(character: CharacterAPI):
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    character.fight_xp(25)


def gear_up(character: CharacterAPI):
    x,y = find_bank()
    character.move_character(x,y)
    contents = character.get_bank_contents()

    character_data = character.get_character()
    for item in contents:
        equip_better_item(character, item['code'], character_data)
        item = get_item(item['code'])
        if item['type'] == 'consumable' and item['subtype'] == 'food':
            logger.info(f"load up on food {item['code']}")
            character.withdraw_all(item['code'])

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


def craft_gear(character: CharacterAPI, skill: str = None):
    if not skill:
        # - pick a skill if not given
        # - choose an item at the highest level we can craft
        skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking','alchemy']
        character_data = character.get_character()
        lowest_skill: str
        lowest_level = 100
        quantity = 1
        for skill in skills:
            skill_level = character_data.get(f"{skill}_level", 0)
            if skill_level < lowest_level:
                lowest_level = skill_level
                lowest_skill = skill
                lowest_choice_level = skill_level - 10
    else:
        quantity = 10
        lowest_skill = skill
        lowest_choice_level = 1

    item = choose_highest_item(character, lowest_skill, lowest_choice_level)
    logger.info(f'highest level item {item}')
    while not item and not item['code'] in banned_orders:
        item = choose_highest_item(character, random.choice(skills))
    
    if not craft_item(character, item, quantity):
        logger.info(f"can't craft {item['code']} now, banned")
        banned_orders.append(item['code'])
        current_orders.remove(item['code'])
    else:
        logger.info(f"finished making {item['code']}, removing from current orders")
        current_orders.remove(item['code'])
    logger.info(f"current orders {current_orders}")
    logger.info(f"banned orders {banned_orders}")

def craft_item(character: CharacterAPI, item: Dict, quantity: int = 1):
    # - go to the bank and try to get everything needed
    # - until we have it:
    #   - order the items from crafters
    #   - gather ourselves and come back
    craft = item.get('craft',None)
    if not craft:
        logger.info(f'cannot craft {item}')
        return False

    requirements = craft.get('items',{})
    bank_x,bank_y=find_bank()
    character.move_character(bank_x,bank_y)

    need_something = has_requirements(character, requirements, False, quantity)
    if need_something == 2:
        logger.info(f"Cannot craft this, bailing")
        return False
                
    while need_something != 0:
        fill_orders(character, m_role)
        need_something = has_requirements(character, requirements, True, quantity)

    logger.info(f"requirements met, go craft {item['code']}")
    skill = craft['skill']
    shop_x,shop_y = character.find_closest_content('workshop',skill)
    character.move_character(shop_x, shop_y)
    character.move_character(shop_x,shop_y)
    character.craft(item['code'],quantity)
    character.move_character(bank_x,bank_y)
    character.deposit_to_bank(item['code'],quantity)
    return True

def has_requirements(character: CharacterAPI, requirements, ordered: bool, quantity: int):
    need_something = 0
    for requirement in requirements:
        required_quantity = requirement['quantity'] * quantity
        logger.info(f"check for {required_quantity} {requirement['code']}")
        if (character.withdraw_from_bank(requirement['code'],required_quantity)):
            logger.info(f"Already have {required_quantity} enough {requirement['code']} to craft")
        else:
            logger.info(f"not enough {requirement['code']}")
            need_something = 1
            if not ordered:
                if not order_items(character, requirement['code'],required_quantity):
                    logger.error(f"cannot get {requirement['code']}")
                    need_something = 2
                
    return need_something

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
    
    # raw wolf meat is mislabeled!
    if subtype == 'mob' or item_code == 'raw_wolf_meat' or item_code == 'milk_bucket' or item_code == 'raw_beef':
        for index in range(quantity):
            task_queue.create_task({"role":"fighter","code": item_code})
        return True
    
    if item.get('craft', None) != None:
        logger.info(f'to gather {item_code} we need to craft it')
        craft_item(character, item, quantity)
        return True

    for index in range(quantity):
        task_queue.create_task({"role":"forager","code": item_code})
    return True

def gather_copper(character : CharacterAPI):
    logger.info("Gathering a copper")
    copper_x,copper_y = find_copper()
    bank_x,bank_y = find_bank()
    forge_x,forge_y = find_forge()
    character.move_character(bank_x,bank_y)
    if character.withdraw_from_bank('copper_ore', 10):
        logger.info('enough in the bank to go craft copper')
    else:
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
    character.move_character(bank_x,bank_y)
    if character.withdraw_from_bank('iron_ore', 10):
        logger.info('enough in the bank to go craft iron')
    else:
        character.move_character(iron_x, iron_y)
        character.gather(10)
    character.move_character(forge_x,forge_y)
    character.craft('iron',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    return True

current_orders = []
banned_orders = []

def choose_highest_item(character: CharacterAPI, skill: str, lowest_choice_level: int = 0):
    global current_orders
    logger.info(f"choose_highest_item: current orders {current_orders}")
    character_data = character.get_character()
    skill_level = character_data.get(f"{skill}_level", 0)
    logger.info(f"choose_highest_item {skill} skill level {skill_level}")
    if not lowest_choice_level:
        lowest_choice_level = skill_level - 10
    
    # Get all craftable items at or below the character's skill level
    craftable_items = []

    for item in items:
        craft = item.get('craft')
        if craft:
            if craft.get("skill") == skill:
                item_level = craft.get("level", 0)
                if item_level <= skill_level and item_level >= lowest_choice_level and item['code'] not in banned_orders:
                    craftable_items.append(item)
    
    if not craftable_items:
        logger.info(f'cannot craft anything for {skill}')
        sleep(5)
        return None

    # Exclude items already in current_orders
    valid_items = [
        item for item in craftable_items
        if item['code'] not in current_orders
        and item['code'] not in ['wooden_stick', 'jasper_crystal']
    ]

    if not valid_items:
        logger.warning(f"No valid items to craft for {skill} after filtering")
        return None  # Could return None and handle it gracefully outside this function

    # Find the highest level remaining items
    highest_level = max(item.get("level", 0) for item in valid_items)

    highest_level_items = [
        item for item in valid_items
        if item.get("level") == highest_level
    ]

    chosen_item = random.choice(highest_level_items)

    if chosen_item:
        current_orders.append(chosen_item['code'])
        return chosen_item
    else:
        logger.warning(f"Failed to choose a craft item for {skill}")
        sleep(5)
        return None


def gather(character: CharacterAPI, item_code: str, quantity: int):
    logger.info(f'Gather {quantity} {item_code}')

    item = get_item(item_code)
    if item['type'] != 'resource':
        logger.info(f'item is not resource to gather: {item}')
        return False

    subtype = item.get('subtype','')
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    if subtype == 'mob' or item_code == 'milk_bucket' or item_code == 'raw_wolf_meat':
        x,y = find_monster_drop(character, item_code)
        character.move_character(x,y)
        character.rest()
        return character.fight_drop(quantity, item_code)
    
    if item.get('craft', None) != None:
        logger.info(f'to gather {item_code} need to craft it')
        craft_item(character, item, quantity)
        return True

    if subtype == 'mining':
        logger.info(f"try and get pick")
        if character.withdraw_from_bank('iron_pickaxe',1):
            character.unequip('weapon')
            character.equip('iron_pickaxe','weapon')
    elif subtype == 'woodcutting':
        logger.info(f"try and get axe")
        if character.withdraw_from_bank('iron_axe',1):
            character.unequip('weapon')
            character.equip('iron_axe','weapon')
    elif subtype == 'alchemy':
        logger.info(f"try and get gloves")
        if character.withdraw_from_bank('leather_gloves',1):
            character.unequip('weapon')
            character.equip('leather_gloves','weapon')
    elif subtype == 'fishing':
        logger.info(f"try and get fishing rod")
        if character.withdraw_from_bank('spruce_fishing_rod',1):
            character.unequip('weapon')
            character.equip('spruce_fishing_rod','weapon')

    x,y = find_resource_drop(character,item_code)
    character.move_character(x,y)
    result = character.gather(quantity)
    x,y = find_bank()
    character.move_character(x,y)
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()
    return result

def choose_random_resource(character: CharacterAPI, skill: str, skill_level: int):
    # Find all resources matching the skill
    skill_resources = [res for res in resources if res.get('skill', '') == skill]

    # Find all resources below the skill level
    eligible_resources = [res for res in skill_resources if res.get('level', 1) <= skill_level]

    if not eligible_resources:
        logger.warning(f"No eligible resources found below the skill level {skill_level}.")
        return None  # Handle no valid resource found

    # Find the closest level to skill_level (maximum level that is still below skill_level)
    closest_level = max(res.get('level', 1) for res in eligible_resources)

    # Get all resources that match this closest level
    closest_resources = [res for res in eligible_resources if res.get('level', 1) == closest_level]

    # Randomly choose from the closest resources
    chosen_resource = random.choice(closest_resources)

    logger.info(f"heading down to the ol {chosen_resource['code']}, level {chosen_resource.get('level', 1)}")
    return character.find_closest_content('resource', chosen_resource['code'])

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
