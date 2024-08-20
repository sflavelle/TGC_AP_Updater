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
                          ("Archipelago/lib/worlds", "compiled"),
                          ("Archipelago/custom_worlds", "0.5.0+")
                      ]),
        inquirer.Text("github_token",
                      message="Do you have a GitHub token? Creating one to use here will let you"
                              "bypass rate limits for unauthenticated requests."
                              "Otherwise, just press Enter to skip this question.")
    ]

    setup_answers = inquirer.prompt(setup_questions)
    config['ap_path'] = setup_answers['ap_path']
    config['ap_type'] = setup_answers['ap_type']
    config['github_token'] = setup_answers['github_token'] if len(setup_answers['github_token']) > 0 else None

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


def run_updates(config, config_path, worlds_to_update):
    gh_token: str = config['github_token'] or None
    gh = Github(gh_token)
    dl = Pypdl(allow_reuse=True)

    def get_latest_world(release: GitRelease, match: str):
        for asset in release.assets:
            if asset.name == match or asset.name.endswith(".zip"):
                return asset.browser_download_url

    worlds = [w for w in config['worlds'] if w in worlds_to_update]

    pbar = tqdm(total=len(worlds), unit='world')
    for world in worlds:
        pbar.set_description(f"Checking {world}...")
        slug = config['worlds'][world]["slug"]
        worldtype = config['worlds'][world]["type"]
        tagprefix = config['worlds'][world]["tagprefix"] if "tagprefix" in config['worlds'][world] else None
        filename = config['worlds'][world]["filename"]
        foldername = config['worlds'][world]['foldername'] if "foldername" in config['worlds'][world] else None
        version = config['worlds'][world]['version'] if "version" in config['worlds'][world] else None

        git_release = None

        finalpath = (config["ap_path"]
                     + ('/lib/' if config["ap_type"] == "compiled" else '/')
                     + ('custom_' if config["ap_type"] == "0.5.0+" else '')
                     + "worlds/"
                     + (filename or foldername))
        print(finalpath)
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
                for release in repo.get_releases():
                    if version == release.tag_name:
                        pbar.set_description(f"{world} is already up to date.")
                        sleep(2)
                        pbar.update(1)
                        continue
                    if tagprefix is not None:
                        if tagprefix not in release.tag_name: continue
                    for asset in release.assets:
                        if asset.name.startswith(filename) or asset.name.endswith(".zip"):
                            version = release.tag_name
                            git_release = release
                    if git_release: break
            except GithubException as e:
                if e.status == "404":
                    pbar.set_description(f"There are no releases for {world} - it's possible this world has only pre-releases.")
                    sleep(2)
                pbar.update(1)
                continue

            world_url = get_latest_world(git_release, filename)
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
