# Resources
from pathlib import Path
import yaml
from utils import menus, helpers

cfg_file = Path('ap_updater.yaml')
config = None
try:
    with open(cfg_file.absolute()) as f:
        config = dict(yaml.safe_load(f))
except FileNotFoundError:
    helpers.init_config(cfg_file)  # First time config?
    with open(cfg_file.absolute()) as f:
        config = dict(yaml.safe_load(f))

if 'worlds' not in config:
    config['worlds'] = dict()
    print("You have no worlds available to update.")

if __name__ == "__main__":
    menus.main_menu(config, cfg_file)
    