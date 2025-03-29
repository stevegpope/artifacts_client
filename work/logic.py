from typing import Dict, List
from work.api import CharacterAPI
import os
from work.smarty import Smarty
from work.tasks import alltasks, fill_orders,setup_tasks

logger = None
api = CharacterAPI
character: str
token: str
role :str

def setup_logic(m_logger, m_token, m_character, m_role):
    global logger, api, character, token, role
    logger = m_logger
    token = m_token
    character = m_character
    role = m_role
    api = CharacterAPI(logger, m_token, m_character)
    setup_tasks(m_logger,m_character, m_role, api)

def process():
    global character,api,token

    bank_x,bank_y = api.find_closest_content('bank','bank')
    api.move_character(bank_x,bank_y)
    api.rest()
    # derobe
    slots = ["rune","shield","helmet","body_armor","leg_armor","boots","ring1","ring2","amulet","artifact1","artifact2","artifact3","utility1","utility2"]
    for slot in slots:
        api.unequip(slot)

    if role == 'smarty':
        smarty = Smarty(logger, api)

    while True:
        if role == 'smarty':
            smarty.do_something_smart()
        else:
            fill_orders(api, role)
            bank_x,bank_y = api.find_closest_content('bank','bank')
            api.move_character(bank_x,bank_y)
            api.deposit_all_inventory_to_bank()

def start_queue(character: CharacterAPI, role: str):
    # Start at the bank
    bank_x,bank_y = character.find_closest_content('bank','bank')
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    while True:
        task = choose_task(role)
        task(character)


def choose_task(role: str):
    global learner
    if role == 'fighter':
        return alltasks()['fill_orders']
    elif role == 'crafter':
        return alltasks()['fill_orders']
    elif role == 'crafter':
        return alltasks()['fill_orders']
    elif role == 'hunter':
        return alltasks()['fill_orders']
