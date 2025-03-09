# config.py
import configparser
import os

def load_config():
    """Load configuration from a file or environment variables."""
    config = configparser.ConfigParser()
    
    # Load from config.ini file
    if os.path.exists('config.ini'):
        config.read('config.ini')
    else:
        raise RuntimeError
    
    return config


config = load_config()
TOKEN = config['DEFAULT']['token']
if not TOKEN:
    os.getenv("SECRET_TOKEN")