from work.api import CharacterAPI
import os
from work.tasks import alltasks,setup_tasks,find_bank

logger = None
api = CharacterAPI
character: str
token: str

def setup_logic(m_logger, m_token, m_character):
    global logger, api, character, token
    logger = m_logger
    token = m_token
    character = m_character
    api = CharacterAPI(logger, m_token, m_character)
    setup_tasks(m_logger,m_token,m_character)

def process():
    global character,api,token
    if (character == 'baz'):
        logger.info("Start Fighter")
        start_queue(api, 'fighter')
    elif (character == 'baz1'):
        logger.info("Start Crafter")
        start_queue(api, 'crafter')
    elif (character == 'baz2'):
        logger.info("Start Gatherer")
        start_queue(api, 'gatherer')
    elif (character == 'baz3'):
        logger.info("Start Gatherer")
        start_queue(api, 'gatherer')
    elif (character == 'baz4'):
        start_queue(api, 'hunter')
        #logger.info("Start smarty")
        #from work.smarty import Smarty
        #smarty = Smarty(logger, api)
        #smarty.start()

def start_queue(character: CharacterAPI, role: str):
    # Start at the bank
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()

    while True:
        task = choose_task(role)
        task(character)

TASKS_FILE_PATH = "C:\\Users\\sarah\\Desktop\\code\\artifacts\\work\\tasks\\tasks.txt"

def read_task_from_file():

    """Read tasks from tasks.txt and add them to the local queue."""
    if not os.path.exists(TASKS_FILE_PATH):
        print("tasks.txt not found. Skipping.")
        return

    with open(TASKS_FILE_PATH, "r") as file:
        for line in file:
            line = line.strip()  # Remove leading/trailing whitespace
            if line:  # Skip empty lines
                role, name = line.split(",", 1)  # Split into role, name
                task = {"role": role, "name": name}
                return task
            
    return None

def clear_tasks_file():
    """Clear the contents of tasks.txt after processing."""
    with open(TASKS_FILE_PATH, "w") as file:
        file.write("")  # Clear the file
    logger.info("Cleared tasks.txt")

def choose_task(role: str):
    global learner
    task = read_task_from_file()
    if task and task['role'] == role:
        logger.info(f"New task {task}")
        clear_tasks_file()
        return alltasks()[task['name']]

    logger.info("Default task")

    if role == 'fighter':
        return alltasks()['kill_next_weakest']
    elif role == 'crafter':
        return alltasks()['hunt_chickens']
    elif role == 'gatherer':
        return alltasks()['hunt_chickens']
    elif role == 'hunter':
        return alltasks()['hunt_chickens']
