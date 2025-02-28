import logging
from transformers import pipeline
from work.api import CharacterAPI

class Smarty:
    def __init__(self, logger: logging.Logger, character: CharacterAPI):
        self.api: CharacterAPI = character
        self.logger = logger
import logging
from transformers import pipeline
from llama_cpp import Llama  # Only needed for GGUF models
from work.api import CharacterAPI

class Smarty:
    def __init__(self, logger: logging.Logger, character: CharacterAPI):
        self.api: CharacterAPI = character
        self.logger = logger
        model_name = 'distilgpt2'

        # Load the selected model
        if model_name == "phi-2":
            self.llm = pipeline("text-generation", model="microsoft/phi-2", device="cuda", torch_dtype="float16")
        elif model_name == "openllama-3b":
            self.llm = pipeline("text-generation", model="openlm-research/open_llama_3b", device="cuda", torch_dtype="float16")
        elif model_name == "gpt-neo-1.3b":
            self.llm = pipeline("text-generation", model="EleutherAI/gpt-neo-1.3B", device="cuda", torch_dtype="float16")
        elif model_name == "gpt2":
            self.llm = pipeline("text-generation", model="gpt2", device="cuda", torch_dtype="float16")
        elif model_name == "distilgpt2":
            self.llm = pipeline("text-generation", model="distilgpt2", device="cuda", torch_dtype="float16")
        elif model_name == "zephyr-7b":
            self.llm = Llama(
                model_path="path/to/zephyr-7b.Q4_K_M.gguf",  # Replace with the actual path to your GGUF file
                n_ctx=2048,  # Context window size
                n_threads=4,  # Number of CPU threads to use
                n_gpu_layers=33,  # Number of layers to offload to GPU (if you have a GPU)
            )
        else:
            raise ValueError(f"Unknown model: {model_name}")
        
    def generate_instructions(self) -> str:
        state = self.api.get_character()
        level = state.get('level',0)
        xp = state.get('xp',0)
        gold = state.get('gold',0)
        mining_xp = state.get('mining_xp',0)
        woodcutting_xp = state.get('woodcutting_xp',0)
        fishing_xp = state.get('fishing_xp',0)
        weaponcrafting_xp = state.get('weaponcrafting_xp',0)
        gearcrafting_xp = state.get('gearcrafting_xp',0)
        jewelrycrafting_xp = state.get('jewelrycrafting_xp',0)
        cooking_xp = state.get('cooking_xp',0)
        alchemy_xp = state.get('alchemy_xp',0)
        hp = state.get('hp',0)
        max_hp = state.get('max_hp',0)
        weapon_slot = state.get('weapon_slot','')
        rune_slot = state.get('rune_slot','')
        shield_slot = state.get('shield_slot','')
        helmet_slot = state.get('helmet_slot','')
        body_armor_slot = state.get('body_armor_slot','')
        leg_armor_slot = state.get('leg_armor_slot','')
        boots_slot = state.get('boots_slot','')
        ring1_slot = state.get('ring1_slot','')
        ring2_slot = state.get('ring2_slot','')
        amulet_slot = state.get('amulet_slot','')
        artifact1_slot = state.get('artifact1_slot','')
        artifact2_slot = state.get('artifact2_slot','')
        artifact3_slot = state.get('artifact3_slot','')
        utility1_slot = state.get('utility1_slot','')
        utility2_slot = state.get('utility2_slot','')
        bag_slot = state.get('bag_slot','')
        task = state.get('task','')
        task_type = state.get('task_type','')
        task_progress = state.get('task_progress',0)
        task_total = state.get('task_total',0)

        # Minimize for the llm
        llmstate = f"""level={level},xp={xp},gold={gold},mining_xp={mining_xp},woodcutting_xp={woodcutting_xp},
        fishing_xp={fishing_xp},weaponcrafting_xp={weaponcrafting_xp},gearcrafting_xp={gearcrafting_xp},
        jewelrycrafting_xp={jewelrycrafting_xp},cooking_xp={cooking_xp},alchemy_xp={alchemy_xp},hp={hp},
        max_hp={max_hp},weapon_slot={weapon_slot},rune_slot={rune_slot},shield_slot={shield_slot},
        helmet_slot={helmet_slot},body_armor_slot={body_armor_slot},leg_armor_slot={leg_armor_slot},
        boots_slot={boots_slot},ring1_slot={ring1_slot},ring2_slot={ring2_slot},amulet_slot={amulet_slot},
        artifact1_slot={artifact1_slot},artifact2_slot={artifact2_slot},artifact3_slot={artifact3_slot},
        utility1_slot={utility1_slot},utility2_slot={utility2_slot},bag_slot={bag_slot},task={task},
        task_type={task_type},task_progress={task_progress},task_total={task_total}"""
        actions = """self.api.choose_task();self.api.complete_task();self.api.craft('item_code',1);
        self.api.deposit_all_inventory_to_bank();self.api.eat();self.api.equip('item_code','slot');
        self.api.exchange_task_coins();self.api.find_monster(level);self.api.fight(number_of_times);
        self.api.gather(number_of_times);self.api.move_character(x,y);self.api.rest();self.api.unequip('slot')"""
        
        sample = """x,y = self.api.find_monster();self.api.move_character(x,y);self.api.fight(10);"""

        prompt = (
            f"Character State: {llmstate}\n"
            f"Actions: {actions}\n"
            "Generate tasks to perform in order to become the world's greatest knight, who must be well-rounded.\n"
            "ONLY generate executable code. Do NOT include explanations, comments, or any text other than code.\n"
            "The code must start with 'CODE:' and must ONLY use the actions provided above.\n"
            "Here is an example of valid output:\n"
            f"{sample}"
        )
    
        # Generate the instructions using the trimmed OpenAPI spec
        response = self.llm(prompt, max_new_tokens=500, num_return_sequences=1)
        print(f"response: {response}")
        return response[0]["generated_text"].strip()

    def execute_instructions(self, instructions: str):
        """Executes the instructions generated by the model."""
        try:
            exec(instructions, {"client": self})
        except Exception as e:
            print(f"Error executing instructions: {e}")

    def start(self):
        """Runs the main loop to periodically retrieve character state and execute instructions."""
        while True:
            instructions = self.generate_instructions()
            print(f"Generated Instructions:\n{instructions}")
            self.execute_instructions(instructions)
