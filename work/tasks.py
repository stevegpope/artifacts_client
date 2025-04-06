import random
from time import sleep
from typing import Dict, List
from work.api import CharacterAPI
from artifactsmmo_wrapper.subclasses import Item, Monster, Resource
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
    current_orders.clear_tasks()
    banned_orders.clear_tasks()

def fill_orders(character: CharacterAPI, role: str):
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()
    tasks = task_queue.read_tasks()
    logger.info(f"Fill orders for {role}")
    
    # Sort tasks so that 'crafter' roles come first. This will unlock crafters faster
    sorted_tasks = sorted(tasks, key=lambda x: x.get('role') == 'crafter', reverse=True)

    chosen_tasks = []
    chosen_code = None
    tasks_to_delete = []  # Track indices to remove after processing
    banned_tasks = banned_orders.read_tasks()

    for index, task in enumerate(sorted_tasks, start=1):
        task_role = task.get('role', None)
        task_code = task.get('code', '')

        if not chosen_tasks:
            # First matching task — lock in the code and role
            if task_code in banned_tasks:
                continue
            match = role == task_role
            if match or role == 'forager' or role == 'tasker' or role == 'crafter' or role == 'support':
                logger.info(f'first banned tasks: {banned_tasks}, code {task_code}')
                chosen_tasks.append(task)
                chosen_code = task_code
                tasks_to_delete.append(index)
        else:
            # Only collect tasks with the same role+code
            if task_code == chosen_code:
                chosen_tasks.append(task)
                tasks_to_delete.append(index)

        if len(chosen_tasks) >= 10:
            break

    # Delete tasks after iteration, in **reverse order** so indexes remain valid
    for index in reversed(tasks_to_delete):
        task_queue.delete_task(index)

    if not chosen_tasks:
        # Fallback behavior if no tasks found
        if role == 'fighter':
            character.fight_xp()
        elif role == 'crafter':
            craft_orders(character)
        elif role == 'top_crafter':
            craft_orders(character, top=True)
        elif role == 'tasker':
            do_tasks(character, fight_tasker=False)
        elif role == 'fight_tasker':
            do_tasks(character, fight_tasker=True)
        elif role == 'forager':
            gather_highest(character)
        elif role == 'chef':
            craft_available(character, 'cooking')
        elif role == 'recycler':
            recycle(character)
        elif role == 'potion_maker':
            item = character.get_item('minor_health_potion')
            craft_item(character, item, 10)
        elif role == 'lumberjack':
            gather_highest(character, 'woodcutting')
        elif role == 'fisherman':
            gather_highest(character, 'fishing')
        elif role == 'scavenger':
            gather_highest(character,'alchemy')
        elif role == 'alchemist':
            craft_available(character, 'alchemy')
        elif role == 'pig_hunter':
            hunt(character, 'pig')
        elif role == 'support':
            craft_support(character)
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

def craft_support(character: CharacterAPI):
    # TODO: choose items based on baz level, but our crafters are not high enough level!
    items = ['earth_boost_potion','air_boost_potion','fire_boost_potion','water_boost_potion','minor_health_potion']
    item = character.get_item(random.choice(items))
    craft_item(character, item, 10)

def hunt(character: CharacterAPI, monster_code: str):
    x,y = character.find_closest_content('monster',monster_code)
    monster = character.api.monsters.get(monster_code)
    character.gear_up(monster)
    character.move_character(x,y)
    character.fight(25)
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)

def recycle(character: CharacterAPI):
    logger.info(f"{character.api.char.name} Go recycling")
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    contents = character.get_bank_contents()
    found_something = False
    for bankitem in contents:
        existing_quantity = bankitem.get('quantity',1)
        if existing_quantity <= 5:
            logger.info(f"recycle not recycling {bankitem['code']}, only have {existing_quantity}")
            continue

        item = character.get_item(bankitem['code'])
        craft = item.craft
        if not craft:
            continue
        skill = craft['skill']

        skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting']
        if skill not in skills:
            continue

        quantity = character.withdraw_all_but_5(item.code, contents)
        if quantity == 0:
            logger.info(f"{character.api.char.name} got {quantity} {item.code} to recycle, skipping")
            continue
        else:
            logger.info(f"{character.api.char.name} got {quantity} {item.code} to recycle")
        shop_x,shop_y = character.find_closest_content('workshop',skill)
        character.move_character(shop_x,shop_y)
        character.recycle(item.code,quantity)
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        character.deposit_all_inventory_to_bank()
        found_something = True
    if not found_something:
        logger.info(f"nothing to recycle, quit")
        return False

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
            logger.info(f"{character} withdrew rod, equip")
            character.unequip('weapon')
            character.equip('spruce_fishing_rod','weapon')
        else:
            logger.info(f"{character} cannot withdrew rod, do not equip")

    skill_level = character.get_skill_level(skill)
    x,y = choose_random_resource(character, skill, skill_level)
    character.move_character(x,y)
    character.gather(quantity)
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    character.unequip('weapon')
    character.deposit_all_inventory_to_bank()

def craft_available(character: CharacterAPI, skill: str):
    contents = character.get_bank_contents()

    item = choose_lowest_item(character, skill, 1)
    if not item:
        logger.info(f"craft_available cannot craft anything for {skill}, we are done")
        exit(0)

    logger.info(f"{character.api.char.name} craft_available craft {item.code}")
    space = character.api.char.get_inventory_space()
    space_per_item = 0
    for craftitem in item.craft.get('items',[]):
        space_per_item += craftitem.get('quantity',1)

    batch_size = int(space / space_per_item)

    if has_requirements(character, item.code,  item.craft['items'], ordered=True, quantity=batch_size, contents=contents) != 0:
        logger.info(f"{character.api.char.name} cannot get stuff to craft {batch_size} {item.code} currently, try later")
        return False
    
    if not craft_item(character, item, batch_size, ordered=True):
        logger.info(f"craft_available can't craft {item.code} now, leaving in place")
    else:
        logger.info(f"craft_available finished making {item.code}, removing from current orders")
        current_orders.delete_entry(item.code)
    logger.info(f"craft_available current orders {current_orders.read_tasks()}")
    logger.info(f"craft_available banned orders {banned_orders.read_tasks()}")
    return True

def craft_gear(character: CharacterAPI, skill: str = None, top: bool = False):
    skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking','alchemy']
    if top or not skill:
        # - pick a skill if not given
        # - choose an item at the lowest level we can craft that is over level - 10
        skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking','alchemy']
        lowest_skill: str
        lowest_level = 100
        quantity = 1
        if top:
            skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting']
            lowest_skill = random.choice(skills)
            skill_level = character.get_skill_level(lowest_skill)
            lowest_choice_level = (skill_level // 5) * 5
            logger.info(f"craft_gear skill {lowest_skill} level {skill_level}, top craft level {lowest_choice_level}")
        else:
            for skill in skills:
                skill_level = character.get_skill_level(skill)
                logger.info(f"craft_gear skill {skill} level {skill_level}")
                if skill_level < lowest_level:
                    lowest_level = skill_level
                    lowest_skill = skill
                    lowest_choice_level = skill_level - 10
                    logger.info(f"craft_gear skill {skill} level {skill_level}, lowest allowed {lowest_choice_level}")
        ordered = False
    else:
        quantity = 25
        lowest_skill = skill
        skill_level = character.get_skill_level(skill)
        lowest_choice_level = 1
        ordered = False # no ordering items for you

    item = choose_lowest_item(character, lowest_skill, lowest_choice_level)
    if not item:
        logger.info(f"craft_gear cannot craft anything for {skill}, try another skill while we wait")
        return False

    logger.info(f"craft_gear craft {item.code}")
    
    if not craft_item(character, item, quantity, ordered):
        logger.info(f"craft_gear can't craft {item.code} now, leaving in place")
    else:
        logger.info(f"craft_gear finished making {item.code}, removing from current orders")
        current_orders.delete_entry(item.code)
    logger.info(f"craft_gear current orders {current_orders.read_tasks()}")
    logger.info(f"craft_gear banned orders {banned_orders.read_tasks()}")
    return True

def craft_orders(character: CharacterAPI, top: bool = False):
    orders = current_orders.read_tasks()
    contents = character.get_bank_contents()
    for code in orders:
        item = character.get_item(code)
        logger.info(f"craft_orders craft order {item}")
        if item and item.craft and has_requirements(character, item.code, item.craft['items'], ordered=True, contents=contents) == 0:
            logger.info(f"craft_orders enough to go craft order {code}")
            logger.info(f"craft_orders requirements met, go craft {code}")
            skill = item.craft['skill']
            shop_x,shop_y = character.find_closest_content('workshop',skill)
            character.move_character(shop_x, shop_y)
            character.move_character(shop_x,shop_y)
            xp = character.craft(item.code,1)
            logger.info(f"craft_orders craft item result {xp}")
            x,y = character.find_closest_content('bank','bank')
            character.move_character(x,y)
            character.deposit_all_inventory_to_bank()
            current_orders.delete_entry(code)
    
    craft_gear(character, top = top)
    recycle(character)

def craft_item(character: CharacterAPI, item: Item, quantity: int = 1, ordered: bool = False, return_to_bank: bool = True):
    logger.info(f"craft_item craft {quantity} {item}")
    code = item.code
    craft = item.craft
    if not craft:
        logger.info(f'craft_item cannot craft {item}')
        return False

    skill_level = character.get_skill_level(craft['skill'])
    item_level = craft['level']
    if item_level > skill_level:
        logger.info(f"craft_item {item.code} is too high level {item_level} for me at {skill_level}")
        return False

    requirements = craft.get('items',{})
    bank_x,bank_y=character.find_closest_content('bank','bank')
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

    need_something = has_requirements(character,item.code, requirements, ordered, quantity)
    if need_something == 2:
        logger.info(f"craft_item Cannot craft {code}, bailing")
        return False

    logger.info(f"craft_item Need something to craft {code}: {need_something}")

    while need_something != 0:
        fill_orders(character, m_role)
        need_something = has_requirements(character, item.code,requirements, True, quantity)
        logger.info(f"craft_item Still need something to craft {code}: {need_something}")

    logger.info(f"craft_item requirements met, go craft {code}")
    skill = craft['skill']
    shop_x,shop_y = character.find_closest_content('workshop',skill)
    character.move_character(shop_x, shop_y)
    character.move_character(shop_x,shop_y)
    xp = character.craft(item.code,quantity)
    logger.info(f"craft_item craft item result {xp}")
    if return_to_bank:
        character.move_character(bank_x,bank_y)
        character.deposit_to_bank(item.code, quantity)
    return xp != -1

def has_requirements(character: CharacterAPI, item_code: str, requirements, ordered: bool, quantity: int = 1, contents: List[Dict] = None):
    need_something = 0
    if contents:
        bank_contents = contents
    else:
        bank_contents = character.get_bank_contents()
    for requirement in requirements:
        required_quantity = requirement['quantity'] * quantity
        logger.info(f"has_requirements check for {required_quantity} {requirement['code']}")
        found = False
        for item in bank_contents:
            if requirement['code'] == item['code'] and item['quantity'] >= required_quantity:
                logger.info(f"has_requirements Already have {required_quantity} enough {requirement['code']} to craft {item_code}")
                found = True
        if not found:
            logger.info(f"has_requirements not enough {requirement['code']}")
            need_something = 1
            if not ordered:
                if not order_items(character, requirement['code'],required_quantity):
                    logger.error(f"has_requirements cannot get {requirement['code']}, tried to order {required_quantity} of them")
                    need_something = 2
    if need_something == 0:
        logger.info(f"has_requirements Have all the stuff in the bank to make {item_code}, get it out")
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        for requirement in requirements:
            required_quantity = requirement['quantity'] * quantity
            if (character.withdraw_from_bank(requirement['code'],required_quantity)):
                logger.info(f"has_requirements Withdrew {required_quantity} {requirement['code']} to craft")
            else:
                logger.info(f"has_requirements not enough {requirement['code']}")
                need_something = 1
                if not ordered:
                    if not order_items(character, requirement['code'],required_quantity):
                        logger.error(f"has_requirements cannot get {requirement['code']}, bank time")
                        need_something = 2
                
    return need_something

def order_items(character: CharacterAPI, item_code: str, quantity: int):
    item: Item = character.get_item(item_code)
    logger.info(f'Ordering {quantity} {item_code} type {item.type}')
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
    
    if item.craft is not None:
        logger.info(f'order_items To gather {item_code}, we need to craft it')
        space = character.api.char.get_inventory_space()
        space_per_item = 0
        for craftitem in item.craft.get('items',[]):
            space_per_item += craftitem.get('quantity',1)

        batch_size = min(int(space / space_per_item), quantity)
        logger.info(f"{item.code} requires {space_per_item} space per item, full space {space}, batch size {batch_size}")
        
        while quantity > 0:
            current_batch = min(batch_size, quantity)
            logger.info(f"Crafting batch of {current_batch}")
            
            if not craft_item(character, item, current_batch):
                logger.info(f"order_items cannot craft {item_code}")
                for _ in range(quantity):  
                    task_queue.create_task({"role": "forager", "code": item_code})
                return False
            
            quantity -= current_batch
        
        logger.info(f"Successfully crafted the full requested amount of {item_code}")
        return True

    for index in range(quantity):
        task_queue.create_task({"role":m_role,"code": item_code})
    return True

def choose_lowest_item(character: CharacterAPI, skill: str, lowest_skill: int = 1) -> Item:
    logger.info(f"choose_lowest_item: current orders {current_orders.read_tasks()}")
    logger.info(f"choose_lowest_item: banned orders {banned_orders.read_tasks()}")
    skill_level = character.get_skill_level(skill)
    logger.info(f"choose_lowest_item {skill} skill level {skill_level}, lowest {lowest_skill}")
    
    # Get all craftable items at or below the character's skill level
    craftable_items = []
    items = character.all_items()
    banned_tasks = banned_orders.read_tasks()

    logger.info(f"there are {len(items)} items in total")
    for item in items:
        item: Item
        craft = item.craft

        if craft:
            if craft.get("skill") == skill:
                item_level = craft.get("level")
                if item_level > skill_level:
                    continue

                if item_level < lowest_skill:
                    continue

                if item.code in banned_tasks:
                    logger.info(f"skip {item.code}, banned")
                    continue

                logger.info(f"craft item {item.code} level {item_level}, my skill level {skill_level}")
                craftable_items.append(item)

    if not craftable_items:
        logger.info(f'choose_lowest_item cannot craft anything for {skill}')
        sleep(5)
        return None

    # Exclude items already in current_orders
    valid_items = [
        item for item in craftable_items
        if item.code not in current_orders.read_tasks()
        and item.code not in banned_orders.read_tasks()
        and item.code not in ['wooden_stick']
    ]

    if not valid_items:
        logger.warning(f"No valid items to craft for {skill} after filtering")
        return None

    chosen_item = random.choice(valid_items)

    if chosen_item:
        current_orders.create_task(chosen_item.code)
        return chosen_item
    else:
        logger.warning(f"Failed to choose a craft item for {skill}")
        sleep(5)
        return None


def gather(character: CharacterAPI, item_code: str, quantity: int, return_to_bank: bool = True):
    logger.info(f'Gather {quantity} {item_code}')

    item: Item = character.get_item(item_code)

    subtype = item.subtype
    if subtype == 'task':
        logger.info(f'cannot gather task item {item}')
        return False
    
    if subtype == 'mob' or item_code == 'milk_bucket' or item_code == 'raw_wolf_meat':
        if hunt_for_items(character, item_code, quantity):
            if return_to_bank:
                x,y = character.find_closest_content('bank','bank')
                character.move_character(x,y)
                character.deposit_all_inventory_to_bank()
            return True
        else:
            logger.info(f"could not find or fight to get {item_code}")
            return False

    if item.craft != None:
        logger.info(f'gather to gather {item_code} need to craft it {item.craft}')
        space = character.api.char.get_inventory_space()
        space_per_item = 0
        for craftitem in item.craft.get('items',[]):
            space_per_item += craftitem.get('quantity',1)

        batch_size = min(int(space / space_per_item), quantity)
        logger.info(f"{item.code} requires {space_per_item} space per item, batch size {batch_size}")
        while quantity > 0:
            current_batch = min(batch_size, quantity)
            if not craft_item(character, item, current_batch, return_to_bank=return_to_bank):
                logger.info(f"gather cannot craft {item_code}")
                return False
            quantity -= current_batch
        return True

    item_skill = item.subtype
    skill_level = character.get_skill_level(item_skill)
    if item.level > skill_level:
        logger.info(f'cannot gather high level {item} level {item.level}, {character.api.char.name} {item_skill}: {skill_level}')
        return False
    else:
        logger.info(f'ok to gather {item} level {item.level}, {character.api.char.name} {item_skill}: {skill_level}')

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
            logger.info(f"{character} withdrew rod, equip")
            character.unequip('weapon')
            character.equip('spruce_fishing_rod','weapon')
        else:
            logger.info(f"{character} cannot withdrew rod, do not equip")

    logger.info(f"find resource drop for {item_code}")
    x,y,success = find_resource_drop(character,item_code)
    if not success:
        logger.info(f"cannot find {item_code}")
        banned_orders.create_task(item_code)
        return False

    character.move_character(x,y)
    result = character.gather(quantity)
    if return_to_bank:
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        character.unequip('weapon')
        character.deposit_all_inventory_to_bank()
    return result

def choose_random_resource(character: CharacterAPI, skill: str, skill_level: int):
    # Find all resources matching the skill
    skill_resources = character.api.resources.get(skill=skill)
    logger.info(f"choose_random_resource skill resources {skill_resources}, my skill {skill_level}")

    # Find all resources below the skill level
    eligible_resources = [res for res in skill_resources if res.level <= skill_level]

    if not eligible_resources:
        logger.warning(f"choose_random_resource No eligible resources found below the skill level {skill_level}.")
        return None  # Handle no valid resource found

    # Find the closest level to skill_level (maximum level that is still below skill_level)
    closest_level = max(res.level for res in eligible_resources)
    logger.info(f"choose_random_resource closest level {closest_level}")

    # Get all resources that match this closest level
    closest_resources = [res for res in eligible_resources if res.level == closest_level]
    logger.info(f"choose_random_resource closest resources {closest_resources}")

    # Randomly choose from the closest resources
    chosen_resource = random.choice(closest_resources)

    logger.info(f"choose_random_resource heading down to the ol {chosen_resource.code}, level {chosen_resource.level}")
    return character.find_closest_content('resource', chosen_resource.code)

def find_resource_drop(character: CharacterAPI, item_code: str):
    resources = character.api.resources.get(drop=item_code)
    if resources and len(resources) > 0:
        resource = resources[0]
        logger.info(f"resource {resource.code} drops {item_code}")
        x,y = character.find_closest_content('resource',resource.code)
        return x,y,True
    return None, None, False

def hunt_for_items(character, item_code, quantity):
    monsters = character.api.monsters.get(drop=item_code)
    for monster in monsters:
        monster: Monster
        x,y = character.find_closest_content('monster',monster.code)
        if (x, y) != (None, None):
            logger.info(f"monster {monster.code} is on the map")
        else:
            logger.info(f"monster {monster.code} is not on the map")
            continue

        drops = monster.drops
        if drops:
            for drop in drops:
                if drop.code == item_code:
                    character.gear_up(monster)
                    x,y = character.find_closest_content('monster',monster.code)
                    if (x, y) != (None, None):
                        character.move_character(x,y)
                        character.rest()
                        if not character.fight_drop(quantity, item_code):
                            logger.info(f"cannot fight to get {item_code}")
                            return False
                        return True
                    else:
                        logger.info(f"cannot find monster on map")
                        return False
    return False

def do_tasks(character: CharacterAPI, fight_tasker: bool = False):
    task = character.choose_task(fight_tasker)
    handle_task(character, task)

def handle_monsters_task(character: CharacterAPI, task_data: Dict):
    logger.info(f"Handling monsters task: {task_data}")

    if 'progress' in task_data:
        progress = task_data['progress']
    else:
        progress = 0
    
    # Calculate the number of combats needed
    total = task_data['total']
    combats = total - progress

    while combats > 0:
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        monster = character.api.monsters.get(code=task_data['code'])
        character.gear_up(monster)

        # Find the closest monster and move to its location
        x, y = character.find_closest_content("monster", task_data['code'])
        character.move_character(x, y)
        fights = min(combats,50)
        character.fight(fights)
        combats -= fights
    
    x, y = character.find_taskmaster(fight_task=True)
    character.move_character(x, y)
    character.complete_task()

ordered_item_task = False
def handle_items_task(character: CharacterAPI, task_data: Dict):
    global ordered_item_task
    logger.info(f"Handling items task: {task_data}")
    
    # Check if 'progress' key exists in task_data
    if 'progress' in task_data:
        progress = task_data['progress']
    else:
        progress = 0
    
    total = task_data['total']
    quantity = total - progress 
    batch_size = character.api.char.get_inventory_space() - 25 # leave room for extras

    while quantity > 0:
        current_batch = min(batch_size, quantity)
        x,y = character.find_closest_content('bank','bank')
        character.move_character(x,y)
        if character.withdraw_from_bank(task_data['code'],current_batch):
            logger.info(f"Got {current_batch} from the bank, go exchange")
        else:
            if not gather(character, task_data['code'], current_batch, return_to_bank=False):
                if not ordered_item_task:
                    logger.info(f"handle_items_task cannot gather {task_data['code']}, ordering")
                    order_items(character, task_data['code'], quantity)
                    ordered_item_task = True
                return
        
        x, y = character.find_closest_content('tasks_master','items')
        character.move_character(x, y)
        character.trade_task_items(task_data['code'], current_batch)
        
        quantity -= current_batch

    ordered_item_task = False
    x, y = character.find_closest_content('tasks_master','items')
    character.move_character(x, y)
    character.complete_task()
    character.choose_task()
    trade_coins(character)

def trade_coins(character: CharacterAPI):
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    character.deposit_all_inventory_to_bank()
    quantity = character.withdraw_all('tasks_coin')
    if quantity > 6:
        x, y = character.find_closest_content('tasks_master','items')
        character.move_character(x, y)
        while quantity >= 6:
            character.exchange_task_coins()
            quantity -= 6
    x,y = character.find_closest_content('bank','bank')
    character.move_character(x,y)
    character.deposit_all_inventory_to_bank()
    

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
