from typing import Dict, List
from work.api import CharacterAPI
import os
from work.smarty import Smarty
from work.tasks import alltasks, fill_orders, gear_up,setup_tasks,find_bank

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
    setup_tasks(m_logger,m_token,m_character, m_role)

def process():
    global character,api,token

    bank_x,bank_y = find_bank()
    api.move_character(bank_x,bank_y)
    api.deposit_all_inventory_to_bank()
    if role == 'smarty':
        smarty = Smarty(logger, api)

    while True:
        if role == 'smarty':
            smarty.do_something_smart()
        else:
            api.rest()
            fill_orders(api, role)
            api.move_character(bank_x,bank_y)
            api.deposit_all_inventory_to_bank()

def start_queue(character: CharacterAPI, role: str):
    # Start at the bank
    bank_x,bank_y = find_bank()
    character.move_character(bank_x,bank_y)
    character.deposit_all_inventory_to_bank()
    gear_up(character)
    while True:
        task = choose_task(role)
        task(character)


def choose_task(role: str):
    global learner
    if role == 'fighter':
        return alltasks()['fill_orders']
    elif role == 'crafter':
        return alltasks()['fill_orders']
    elif role == 'gatherer':
        return alltasks()['fill_orders']
    elif role == 'hunter':
        return alltasks()['fill_orders']
