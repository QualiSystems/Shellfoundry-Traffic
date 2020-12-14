"""
FLOW: - directory zipped up
      - updated on cloud-shell server
NOTE: - This script is only for updating EXISTING scripts.
      - Scripts MUST be uploaded manually first time. (this tool can still be used to do zipping)

:todo: move the class into shellfoundry_traffic_cmd.py and delete the module?
"""

import os
from zipfile import ZipFile
from pathlib import Path
from shutil import copyfile

import yaml

from shellfoundry_traffic.test_helpers import create_session_from_config

SRC_DIR = Path(os.getcwd()).joinpath('src')


class ScriptCommandExecutor:

    def __init__(self, script_definition: str) -> None:
        script_definition_yaml = (script_definition if script_definition.endswith('.yaml') else
                                  f'{script_definition}.yaml')
        script_definition_yaml_full_path = Path(os.getcwd()).joinpath(script_definition_yaml)
        with open(script_definition_yaml_full_path, 'r') as file:
            self.script_definition = yaml.safe_load(file)
        self.dist = Path(os.getcwd()).joinpath('dist')
        self.script_zip = self.dist.joinpath(f'{self.script_definition["metadata"]["script_name"]}.zip')

    def get_main(self) -> None:
        """ Get requested content for __main__ file. """
        if self.script_definition.get('files') and self.script_definition['files'].get('main'):
            new_main_file_name = self.script_definition['files']['main']
            new_main_path = SRC_DIR.joinpath(new_main_file_name)
            existing_main_path = SRC_DIR.joinpath('__main__.py')
            copyfile(new_main_path, existing_main_path)

    def should_zip(self, file: str) -> bool:
        """ Returns whether the file should be added to the shell zip file or not. """
        if self.script_definition.get('files') and self.script_definition['files'].get('exclude'):
            if file in self.script_definition['files']['exclude']:
                return False
        else:
            return True

    def zip_files(self) -> None:
        with ZipFile(self.script_zip, 'w') as script:
            for _, _, files in os.walk(SRC_DIR):
                for file in files:
                    if self.should_zip(file):
                        script.write(SRC_DIR.joinpath(file), file)

    def update_script(self):
        session = create_session_from_config()
        os.chdir(self.dist)
        session.UpdateScript(self.script_definition['metadata']['script_name'], self.script_zip.name)
        os.chdir('..')
