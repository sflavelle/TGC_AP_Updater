from time import sleep

import inquirer
import yaml
import zipfile
import os
import shutil
from pathlib import Path
from pypdl import Pypdl
from git import Repo
from github import Github, GithubException, GitRelease
from tqdm import tqdm


def init_config(config_path) -> None:
    config = dict()
    print("Config file missing: doing some initial setup.")
    setup_questions = [
        inquirer.Path('ap_path',
                      message="Please enter the path to your Archipelago directory.",
                      path_type=inquirer.Path.DIRECTORY,
                      exists=True,
                      normalize_to_absolute_path=True),
        inquirer.List('ap_type',
                      message="Where is your Archipelago's world folder?",
                      choices=[
                          ("Archipelago/worlds", "source"),
                          ("Archipelago/lib/worlds", "compiled")
                      ])
    ]

    setup_answers = inquirer.prompt(setup_questions)
    config['ap_path'] = setup_answers['ap_path']
    config['ap_type'] = setup_answers['ap_type']

    with open(config_path.absolute(), 'w', ) as f:
        yaml.dump(config, f, sort_keys=False)


def save_config(config_path, config) -> None:
    try:
        with open(config_path.absolute(), 'w', ) as f:
            yaml.dump(config, f, sort_keys=False)
    except:
        print("Oh no!")


def validate_github_repo(config: dict, repo: str):
    gh_token: str = config['github_token'] or None
    gh = Github(gh_token)
    try:
        repo = gh.get_repo(full_name_or_id=repo)
    except GithubException as e:
        if e.status == "404":
            raise inquirer.errors.ValidationError('',
                                                  reason="The GitHub repo specified does not exist. Is there a typo?")
    return True


def run_updates(config, config_path):
    gh_token: str = config['github_token'] or None
    gh = Github(gh_token)
    dl = Pypdl(allow_reuse=True)

    def get_latest_world(release: GitRelease, match: str):
        for asset in release.assets:
            if asset.name == match or asset.name.endswith(".zip"):
                return asset.browser_download_url

    pbar = tqdm(total=len(config["worlds"]), unit='world')
    for world in config['worlds']:
        pbar.set_description(f"Checking {world}...")
        slug = config['worlds'][world]["slug"]
        worldtype = config['worlds'][world]["type"]
        filename = config['worlds'][world]["filename"]
        foldername = config['worlds'][world]['foldername']
        version = config['worlds'][world]['version']


        finalpath = (config["ap_path"]
                     + ('/lib/' if worldtype == "compiled" else '/')
                     + "worlds/"
                     + (filename or foldername))
        try:
            repo = gh.get_repo(full_name_or_id=slug)
        except GithubException as e:
            print(e)
            if e.status == "404":
                print(f"The GitHub repo for {world} does not exist. Is there a typo?")
            print(f"Skipping {world}.")

            continue
        if worldtype in ["apworld", "apworld_zip"]:
            try:
                latest = repo.get_latest_release()
            except GithubException as e:
                if e.status == "404":
                    print(f"There are no releases for {world} - it's possible this world has only pre-releases.")
                continue
            if version == latest.tag_name:
                pbar.set_description(f"{world} is already up to date.")
                sleep(2)
                pbar.update(1)
                continue

            world_url = get_latest_world(latest, filename)
            file = dl.start(url=world_url,
                            file_path='/tmp',
                            retries=3,
                            overwrite=True,
                            display=False)
            if dl.completed:
                if worldtype == "apworld_zip":
                    with zipfile.ZipFile(file.path) as z:
                        zip_filename = [name for name in z.namelist() if name.endswith('.apworld')]
                        with open(finalpath,
                                  'wb') as f:
                            f.write(z.read(zip_filename[0]))
                elif worldtype == "apworld":
                    shutil.copy(file.path, finalpath)

                # Update world version in config
                version = latest.tag_name
        else:
            repo_git = None
            if os.path.exists(f"repositories/{slug}"):
                repo_git = Repo(f"repositories/{slug}")
            else:
                repo_git = Repo.clone_from(repo.git_url, f"repositories/{slug}")
            repo_latest = repo_git.commit()
            if version == repo_latest.name_rev:
                print(f"{world} is already up to date.")
                continue

            try:
                remote = repo_git.remote()
                remote.pull()
            finally:
                print("fuck")

            os.symlink(f"{repo_git.git_dir}/worlds/{foldername}", finalpath, True)
            version = repo_latest.name_rev

        pbar.set_description("Saving installed version to config")
        config['worlds'][world]['version'] = version
        save_config(config_path, config)
        pbar.update(1)
