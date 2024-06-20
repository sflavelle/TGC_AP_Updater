import inquirer
from simple_term_menu import TerminalMenu
import sys
from utils.helpers import *


def main_menu(config: dict, config_file):
    options = [
        "[u] update worlds",
        "[w] configure worlds",
        "[s] set up script",
        "[x] exit program"
    ]

    num_worlds = len(config["worlds"]) if 'worlds' in config else 0

    print(f"You currently have {num_worlds} configured. What would you like to do?")
    menu = TerminalMenu(options)
    menu_select_index = menu.show()
    match menu_select_index:
        case 0:
            run_updates(config, config_file)
            main_menu(config, config_file)
        case 1:
            worlds(config, config_file)
        case 2:
            configure(config, config_file)
        case 3:
            save_config(config_file, config)
            sys.exit(0)


def worlds(config: dict, config_file):
    worlds_config = config['worlds'] if 'worlds' in config else dict()
    options = [
        "[a] add a world",
        "[m] modify a world",
        "[r] remove a world",
        "[x] exit world config"
    ]

    # If there aren't any worlds available, only show options to add or exit
    if len(worlds_config) == 0:
        options = [options[0], options[3]]

    menu = TerminalMenu(options)
    menu_select_index = menu.show()
    match menu_select_index:
        case 0:
            world_add(config, config_file)
        case 1:
            if len(options) == 2:
                save_config(config_file, config)
                main_menu(config, config_file)
            else:
                world_mod(config, config_file)
        case 2:
            world_del(config, config_file)
        case 3:
            save_config(config_file, config)
            main_menu(config, config_file)


def world_add(config: dict, config_file):
    worlds_config = config['worlds'] if 'worlds' in config else dict()
    questions = [
        inquirer.Text("world_name", message="What's the name of the world to be added?"),
        inquirer.Text("world_slug", message="What's its GitHub slug? (in the format 'author/repo')",
                      validate=lambda _, r: validate_github_repo(config, r)),
        inquirer.List("world_type", message="How can we access the world?",
                      choices=[
                          (".apworld file, separate download", 'apworld'),
                          (".apworld file, inside a zip", "apworld_zip"),
                          ("Git repo only", "git_only")
                      ]),
        inquirer.Text("world_filename", ignore=lambda x: x["world_type"] == "git_only",
                      message="What's the name of the apworld we're looking for?"),
        inquirer.Text("world_foldername", ignore=lambda x: x["world_type"] != "git_only",
                      message="What's the name of the world's folder?")
    ]
    answers = inquirer.prompt(questions)

    worlds_config[answers["world_name"]] = {
        "slug": answers["world_slug"],
        "type": answers["world_type"],
        "filename": f"{answers['world_filename']}.apworld" if answers['world_filename'] else None,
        "foldername": answers['world_foldername'] if answers['world_foldername'] else None,
        "version": None
    }

    config['worlds'] = dict(sorted(worlds_config.items()))
    worlds(config, config_file)
