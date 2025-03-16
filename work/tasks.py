import random
from time import sleep
from typing import Dict, List
from work.api import CharacterAPI
from artifactsmmo_wrapper.subclasses import *

from work.task_queue import TaskQueue

logger = None
api = CharacterAPI
character: str
resources: List[Dict]
task_queue: TaskQueue
m_role: str
current_orders = TaskQueue
banned_orders = TaskQueue

def setup_tasks(m_logger, m_character, role, m_api):
    global logger, api, character, task_queue, m_role, current_orders, banned_orders
    logger = m_logger
    character = m_character
    m_role = role
    api = m_api
    task_queue = TaskQueue()
    current_orders = TaskQueue(f"C:\\Users\\sarah\\Desktop\\code\\artifacts\\work\\tasks\\current_orders_{m_character}.json")
    banned_orders = TaskQueue(f"C:\\Users\\sarah\\Desktop\\code\\artifacts\\work\\tasks\\banned_orders_{m_character}.json")

def fill_orders(character: CharacterAPI, role: str):
    character.deposit_all_inventory_to_bank()
    tasks = task_queue.read_tasks()
    logger.info(f"Fill orders for {role}")

    chosen_tasks = []
    chosen_code = None
    tasks_to_delete = []  # Track indices to remove after processing
    banned_tasks = banned_orders.read_tasks()

    # Scan for tasks, collect up to 10 matching tasks
    for index, task in enumerate(tasks, start=1):
        task_role = task.get('role', None)
        task_code = task.get('code', '')

        if not chosen_tasks:
            # First matching task — lock in the code and role
            if (task_role == role or (task_role == 'forager' and (role == 'crafter' or role == 'tasker')) or role == 'smarty') and not task_code in banned_tasks:
                logger.info(f'first banned tasks: {banned_tasks}, code {task_code}')
                chosen_tasks.append(task)
                chosen_code = task_code
                tasks_to_delete.append(index)
        else:
            # Only collect tasks with the same role+code
            if (task_role == role or (task_role == 'forager' and (role == 'crafter' or role == 'tasker'))) and task_code == chosen_code and not task_code in banned_tasks:
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
            character.fight_xp()
            return True
        elif role == 'crafter':
            craft_orders(character)
            return True
        elif role == 'tasker':
            do_tasks(character)
        elif role == 'forager':
            gather_highest(character)
        elif role == 'chef':
            craft_gear(character, 'cooking')
        elif role == 'alchemist':
            craft_gear(character, 'alchemy')
        elif role == 'recycler':
            recycle(character)
        elif role == 'potion_maker':
            item = character.get_item('small_health_potion')
            craft_item(character, item, 10)
        elif role == 'fight_looper':
            fight_same(character)
    else:
        # Perform the gathered tasks
        task_count = len(chosen_tasks)
        logger.info(f"Filling order for {chosen_code} - {task_count} tasks")
        if not gather(character, chosen_code, task_count):
            logger.info(f'cannot gather {chosen_code}!, re-insert tasks')
            banned_orders.create_task(chosen_code)
            logger.info(f'banned tasks after add: {banned_orders.read_tasks()}')
            for task in chosen_tasks:
                task_queue.create_task(task)
    return True

def fight_same(character: CharacterAPI):
    character.fight(100)

def recycle(character: CharacterAPI):
    logger.info("Go recycling")
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    contents = character.get_bank_contents()
    character.unequip('weapon')
    found_something = False
    for bankitem in contents:
        item = api.get_item(bankitem['code'])
        craft = item.craft
        if not craft:
            continue
        if craft['level'] > 15:
            continue
        skill = craft['skill']
        requirements = craft['items']
        needs_crystal = False
        for requirement in requirements:
            if requirement['code'] == 'jasper_crystal':
                needs_crystal = True
                break

        if needs_crystal:
            logger.info(f"{item.code} requires crystal, do not recycle")
            continue

        skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting']
        if skill not in skills:
            continue
        shop_x,shop_y = character.find_closest_content('workshop',skill)
        quantity = character.withdraw_all(item.code)
        if quantity == 0:
            continue
        character.move_character(shop_x,shop_y)
        character.recycle(item.code,quantity)
        character.move_character(x,y)
        character.deposit_all_inventory_to_bank()
        found_something = True
    if not found_something:
        logger.info(f"nothing to recycle, quit")
        exit(0)

def gather_highest(character: CharacterAPI, skill: str = None):
    skills = ['mining', 'woodcutting', 'fishing','alchemy']
    quantity = 10
    if not skill:
        skill = random.choice(skills)
    else:
        quantity = 50

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

    skill_level = character.get_skill_level(skill)
    x,y = choose_random_resource(character, skill, skill_level)
    character.move_character(x,y)
    character.gather(quantity)
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()

def hunt_monsters(character: CharacterAPI):
    bank_x,bank_y = character.find_closest_content('bank','bank')
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    character.fight_xp(25)

def gear_up(character: CharacterAPI):
    logger.info(f"gear_up")
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    contents = character.get_bank_contents()

    for item_dict in contents:
        equip_better_item(character, item_dict['code'])
        item = api.get_item(item_dict['code'])
        if item.type == 'consumable' and item.subtype == 'food':
            logger.info(f"load up on food {item.code}")
            character.withdraw_all(item.code)

def equip_better_item(character: CharacterAPI, item_code):
    new_item = api.get_item(item_code)
    item_type = new_item.type
    item_level = new_item.level
    if not item_level:
        if new_item.craft:
            item_level = new_item.craft['level']

    character_data = character.get_character()
    if not item_level or item_level > character_data.level:
        return False
    
    slots = ['weapon_slot','rune_slot','shield_slot','helmet_slot','body_armor_slot','leg_armor_slot','boots_slot','ring1_slot','ring2_slot','amulet_slot','bag_slot']

    if item_type:
        if item_type == 'ring':
            original_item = character_data.ring1_slot
            if not equip_from_bank_if_better(character, new_item, original_item, 'ring1', character_data):
                original_item = character_data.ring2_slot
                return equip_from_bank_if_better(character, new_item, original_item, 'ring2', character_data)
            else:
                return True
        elif item_code == 'small_health_potion':
            if character.withdraw_all('small_health_potion'):
                character.equip_utility('small_health_potion')
        else:
            slot = f'{item_type}_slot'
            if not slot in slots:
                return False
            try:
                original_item = getattr(character_data, slot)
                logger.info(f"{slot}:{original_item}")
            except AttributeError:
                print(f"slot '{slot}' not found.")
                return

            return equip_from_bank_if_better(character, new_item, original_item, item_type, character_data)
    return False

def equip_from_bank_if_better(character:CharacterAPI, new_item: Item, original_item, slot, character_data):
    logger.info(f"is {new_item.code} better than {original_item} for {slot}")
    if not original_item:
        logger.info(f"{new_item.code} is better than nothing, changing {slot}")
        character.withdraw_from_bank(new_item.code,1)
        character.unequip(slot)
        character.equip(new_item.code,slot)
        return True
    else:
        original = api.get_item(original_item)
        new_level = new_item.level
        if not new_level and new_item.craft:
            new_level = new_item.craft['level']
        original_level = original.level
        if not original_level and original.craft:
            original_level = original.craft['level']

        if new_level > original_level:
            logger.info(f"{new_item.code} has a higher level ({new_level}) than {original_item} ({original_level}), equipping {slot}")
            character.unequip(slot)
            character.withdraw_from_bank(new_item.code, 1)
            character.equip(new_item.code, slot)
            return True
    return False


def craft_gear(character: CharacterAPI, skill: str = None):
    skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking','alchemy']
    if not skill:
        # - pick a skill if not given
        # - choose an item at the highest level we can craft
        skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking','alchemy']
        lowest_skill: str
        lowest_level = 100
        quantity = 1
        for skill in skills:
            skill_level = character.get_skill_level(skill)
            logger.info(f"skill {skill} level {skill_level}")
            if skill_level < lowest_level:
                lowest_level = skill_level
                lowest_skill = skill
                lowest_choice_level = skill_level - 10
                logger.info(f"skill {skill} level {skill_level}, lowest allowed {lowest_choice_level}")
    else:
        quantity = 10
        lowest_skill = skill
        skill_level = character.get_skill_level(skill)
        lowest_choice_level = skill_level - 10

    item = choose_highest_item(character, lowest_skill, lowest_choice_level)
    if not item:
        logger.info(f"cannot craft anything for {skill}, try another skill while we wait")
        return craft_gear(character, random.choice(skills))
    
    if not craft_item(character, item, quantity):
        logger.info(f"can't craft {item.code} now, banned")
        banned_orders.create_task(item.code)
        current_orders.delete_entry(item.code)
    else:
        logger.info(f"finished making {item.code}, removing from current orders")
        current_orders.delete_entry(item.code)
    logger.info(f"current orders {current_orders.read_tasks()}")
    logger.info(f"banned orders {banned_orders.read_tasks()}")
    return True

def craft_orders(character: CharacterAPI):
    orders = current_orders.read_tasks()
    for code in orders:
        item = character.get_item(code)
        logger.info(f"craft order {item}")
        if item and item.craft and has_requirements(character, item.craft['items'], ordered=True) == 0:
            logger.info(f"enough to go craft order {code}")
            logger.info(f"craft_orders requirements met, go craft {code}")
            skill = item.craft['skill']
            shop_x,shop_y = character.find_closest_content('workshop',skill)
            character.move_character(shop_x, shop_y)
            character.move_character(shop_x,shop_y)
            xp = character.craft(item.code,1)
            logger.info(f"craft item result {xp}")
            x,y = character.find_closest_content('bank','bank')
            character.move_character(x,y)
            character.deposit_all_inventory_to_bank()
            current_orders.delete_entry(code)
    
    logger.info(f"done checking current orders, go make something else")
    craft_gear(character)


def craft_item(character: CharacterAPI, item: Item, quantity: int = 1):
    logger.info(f"craft {item}")
    code = item.code
    craft = item.craft
    if not craft:
        logger.info(f'cannot craft {item}')
        return False

    skill_level = character.get_skill_level(craft['skill'])
    item_level = craft['level']
    if item_level > skill_level:
        logger.info(f"{item.code} is too high level {item_level} for me at {skill_level}")
        return False

    requirements = craft.get('items',{})
    bank_x,bank_y=character.find_closest_content('bank','bank')
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

    for requirement in requirements:
        if requirement['code'] == 'jasper_crystal':
            logger.info("This requires jasper_crytal, not doing that")
            return False

    need_something = has_requirements(character, requirements, False, quantity)
    if need_something == 2:
        logger.info(f"Cannot craft {code}, bailing")
        return False

    logger.info(f"Need something to craft {code}: {need_something}")

    while need_something != 0:
        fill_orders(character, m_role)
        need_something = has_requirements(character, requirements, True, quantity)
        logger.info(f"Still need something to craft {code}: {need_something}")

    logger.info(f"requirements met, go craft {code}")
    skill = craft['skill']
    shop_x,shop_y = character.find_closest_content('workshop',skill)
    character.move_character(shop_x, shop_y)
    character.move_character(shop_x,shop_y)
    xp = character.craft(item.code,quantity)
    logger.info(f"craft item result {xp}")
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    return xp != -1

def has_requirements(character: CharacterAPI, requirements, ordered: bool, quantity: int = 1):
    need_something = 0
    bank_contents = api.get_bank_contents()
    for requirement in requirements:
        required_quantity = requirement['quantity'] * quantity
        logger.info(f"check for {required_quantity} {requirement['code']}")
        found = False
        for item in bank_contents:
            if requirement['code'] == item['code'] and item['quantity'] >= requirement['quantity']:
                logger.info(f"Already have {required_quantity} enough {requirement['code']} to craft")
                found = True
        if not found:
            logger.info(f"not enough {requirement['code']}")
            need_something = 1
            if not ordered:
                if not order_items(character, requirement['code'],required_quantity):
                    logger.error(f"cannot get {requirement['code']}")
                    need_something = 2
    if need_something == 0:
        logger.info("Have all the stuff the in bank, get it out")
        for requirement in requirements:
            required_quantity = requirement['quantity'] * quantity
            if (character.withdraw_from_bank(requirement['code'],required_quantity)):
                logger.info(f"Withdrew {required_quantity} {requirement['code']} to craft")
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
    item = api.get_item(item_code)
    if item.type != 'resource':
        logger.info(f'item is not resource to gather: {item}')
        return False

    subtype = item.subtype
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    # raw wolf meat is mislabeled!
    if subtype == 'mob' or item_code == 'raw_wolf_meat' or item_code == 'milk_bucket' or item_code == 'raw_beef':
        for index in range(quantity):
            task_queue.create_task({"role":"fighter","code": item_code})
        return True
    
    if item.craft != None:
        logger.info(f'to gather {item_code} we need to craft it')
        if not craft_item(character, item, quantity):
            logger.info(f"cannot craft {item_code}, add to orders")
        else:
            return True

    for index in range(quantity):
        task_queue.create_task({"role":"forager","code": item_code})
    return True

def choose_highest_item(character: CharacterAPI, skill: str, lowest_skill: int = 1) -> Item:
    logger.info(f"choose_highest_item: current orders {current_orders.read_tasks()}")
    logger.info(f"choose_highest_item: banned orders {banned_orders.read_tasks()}")
    skill_level = character.get_skill_level(skill)
    logger.info(f"choose_highest_item {skill} skill level {skill_level}, lowest {lowest_skill}")
    
    # Get all craftable items at or below the character's skill level
    craftable_items = []
    items = api.all_items()
    banned_tasks = banned_orders.read_tasks()

    for item in items:
        item: Item
        craft = item.craft

        if craft:
            if craft.get("skill") == skill:
                item_level = craft.get("level")
                if item_level >= skill_level:
                    continue

                if item_level < lowest_skill:
                    continue

                if item.code in banned_tasks:
                    continue

                logger.info(f"craft item {item.code} level {item_level}, my skill level {skill_level}")
                craftable_items.append(item)

    if not craftable_items:
        logger.info(f'cannot craft anything for {skill}')
        sleep(5)
        return None

    # Exclude items already in current_orders
    valid_items = [
        item for item in craftable_items
        if item.code not in current_orders.read_tasks()
        and item.code not in banned_orders.read_tasks()
        and item.code not in ['wooden_stick', 'jasper_crystal']
    ]

    if not valid_items:
        logger.warning(f"No valid items to craft for {skill} after filtering")
        return None

    # Find the highest level remaining items
    highest_level = max(item.craft.get("level") for item in valid_items)

    highest_level_items = [
        item for item in valid_items
        if item.craft.get("level") == highest_level
    ]

    chosen_item = random.choice(highest_level_items)

    if chosen_item:
        current_orders.create_task(chosen_item.code)
        return chosen_item
    else:
        logger.warning(f"Failed to choose a craft item for {skill}")
        sleep(5)
        return None


def gather(character: CharacterAPI, item_code: str, quantity: int):
    logger.info(f'Gather {quantity} {item_code}')

    item = api.get_item(item_code)

    subtype = item.subtype
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    if subtype == 'mob' or item_code == 'milk_bucket' or item_code == 'raw_wolf_meat':
        x,y = find_monster_drop(character, item_code)
        character.move_character(x,y)
        character.rest()
        if not character.fight_drop(quantity, item_code):
            logger.info(f"cannot fight to get {item_code}")
            banned_orders.create_task(item_code)
            return False
        return True

    if item.craft != None:
        logger.info(f'to gather {item_code} need to craft it')
        batch_size = 5
        while quantity > 0:
            current_batch = min(batch_size, quantity)
            if not craft_item(character, item, current_batch):
                logger.info(f"cannot craft {item_code}")
                banned_orders.create_task(item_code)
                return False
            quantity -= current_batch
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

    logger.info(f"find resource drop for {item_code}")
    x,y,success = find_resource_drop(character,item_code)
    if not success:
        logger.info(f"cannot find {item_code}")
        banned_orders.create_task(item_code)
        return False

    character.move_character(x,y)
    result = character.gather(quantity)
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()
    return result

def choose_random_resource(character: CharacterAPI, skill: str, skill_level: int):
    # Find all resources matching the skill
    skill_resources = character.api.resources.get(skill=skill)
    logger.info(f"skill resources {skill_resources}")

    # Find all resources below the skill level
    eligible_resources = [res for res in skill_resources if res.level <= skill_level]

    if not eligible_resources:
        logger.warning(f"No eligible resources found below the skill level {skill_level}.")
        return None  # Handle no valid resource found

    # Find the closest level to skill_level (maximum level that is still below skill_level)
    closest_level = max(res.level for res in eligible_resources)

    # Get all resources that match this closest level
    closest_resources = [res for res in eligible_resources if res.level == closest_level]

    # Randomly choose from the closest resources
    chosen_resource = random.choice(closest_resources)

    logger.info(f"heading down to the ol {chosen_resource.code}, level {chosen_resource.level}")
    return character.find_closest_content('resource', chosen_resource.code)

def find_resource_drop(character: CharacterAPI, item_code: str):
    resources = character.api.resources.get(drop=item_code)
    if resources and len(resources) > 0:
        resource = resources[0]
        logger.info(f"resource {resource.code} drops {item_code}")
        x,y = character.find_closest_content('resource',resource.code)
        return x,y,True
    return None, None, False

def find_monster_drop(character: CharacterAPI, item_code: str):
    monsters = character.api.monsters.get(drop=item_code)
    for monster in monsters:
        drops = monster.drops
        if drops:
            for drop in drops:
                if drop.code == item_code:
                    return character.find_closest_content('monster',monster.code)
    return None

def make_gear(character: CharacterAPI):
    bank_x,bank_y = character.find_closest_content('bank','bank')
    character.move_character(bank_x,bank_y)
    character.withdraw_from_bank('feather',2)
    character.withdraw_from_bank('copper',5)
    x,y = character.find_closest_content('workshop', 'gearcrafting')
    character.move_character(x,y)
    character.unequip('weapon')
    character.craft('copper_legs_armor',1)
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

def do_tasks(character: CharacterAPI):
    task = character.choose_task()
    handle_task(character, task)

def find_taskmaster():
    logger.info("taskmaster at (4,13)")
    return 4,13

def handle_monsters_task(character: CharacterAPI, task_data: Dict):
    logger.info(f"Handling monsters task: {task_data}")

    if 'progress' in task_data:
        progress = task_data['progress']
    else:
        progress = 0
    
    # Calculate the number of combats needed
    total = task_data['total']
    combats = total - progress

    if combats > 0:
        # Take as many health potions with us as possible
        logger.info("Get some potions for fighting")
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        if character.withdraw_all('small_health_potion'):
            character.equip_utility('small_health_potion')

        # Find the closest monster and move to its location
        x, y = character.find_closest_content("monster", task_data['code'])
        character.move_character(x, y)
        character.fight(combats)
    
    x, y = find_taskmaster()
    character.move_character(x, y)
    character.complete_task()

def handle_items_task(character: CharacterAPI, task_data: Dict):
    logger.info(f"Handling items task: {task_data}")
    
    # Check if 'progress' key exists in task_data
    if 'progress' in task_data:
        progress = task_data['progress']
    else:
        progress = 0
    
    total = task_data['total']
    quantity = total - progress 
    batch_size = 50

    while quantity > 0:
        current_batch = min(batch_size, quantity)
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        if character.withdraw_from_bank(task_data['code'],current_batch):
            logger.info(f"Got {current_batch} from the bank, go exchange")
        else:
            gather(character, task_data['code'], current_batch)
            character.withdraw_from_bank(task_data['code'],current_batch)
        
        x, y = character.find_closest_content('tasks_master','items')
        character.move_character(x, y)
        
        character.trade_task_items(task_data['code'], current_batch)
        
        quantity -= current_batch

    x, y = character.find_closest_content('tasks_master','items')
    character.move_character(x, y)
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
    "items": handle_items_task
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

def alltasks():
    function_mapping = {name: obj for name, obj in globals().items() if callable(obj)}
    return function_mapping
