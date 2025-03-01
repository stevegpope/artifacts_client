import time
import logging
from work.logic import process, setup_logic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)
is_busy = False
position_x = 0
position_y = 0

def process_data():
    """Simulate processing data."""
    process()
  

def main_loop(token,character,role):
    """Run the main loop."""
    setup_logic(logger, token, character, role)
        
    try:
        process_data()
    except KeyboardInterrupt:
        logger.info("Main loop stopped.")