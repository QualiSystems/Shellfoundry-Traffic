"""
FLOW: - directory zipped up
      - updated on cloud-shell server
NOTE: - This script is only for updating EXISTING scripts.
      - Scripts MUST be uploaded manually first time. (this tool can still be used to do zipping)

:todo: move the class into shellfoundry_traffic.py and delete the module?
"""

import os
from zipfile import ZipFile
from pathlib import Path

import yaml

from shellfoundry_traffic.test_helpers import create_session_from_config


class ScriptCommandExecutor:

    def __init__(self, script_definition_yaml: str) -> None:
        shell_definition_yaml = Path(os.getcwd()).joinpath(f'{script_definition_yaml}.yaml')
        with open(shell_definition_yaml, 'r') as file:
            self.script_definition = yaml.safe_load(file)
        self.dist = Path(os.getcwd()).joinpath('dist')
        self.script_zip = self.dist.joinpath(f'{self.script_definition["metadata"]["script_name"]}.zip')

    def should_zip(self, file: str) -> bool:
        return file not in self.script_definition['files']['exclude']

    def zip_files(self) -> None:
        with ZipFile(self.script_zip, 'w') as script:
            src = Path(os.getcwd()).joinpath('src')
            for _, _, files in os.walk(src):
                for file in files:
                    if self.should_zip(file):
                        script.write(src.joinpath(file), file)

    def update_script(self):
        session = create_session_from_config()
        os.chdir(self.dist)
        session.UpdateScript(self.script_definition['metadata']['script_name'], self.script_zip.name)
