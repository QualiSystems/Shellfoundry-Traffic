"""
Test cloudshell_traffic script CLI command.
"""
import os
import shutil
from pathlib import Path
from typing import List
from zipfile import ZipFile

import pytest
import yaml
from _pytest.fixtures import SubRequest

from shellfoundry_traffic.shellfoundry_traffic import main


@pytest.fixture
def dist() -> Path:
    """ Yields empty dist folder. """
    dist = Path(__file__).parent.joinpath('dist')
    shutil.rmtree(dist, ignore_errors=True)
    os.mkdir(dist)
    yield dist


@pytest.fixture(params=['script-definition'])
def script_definition_yaml(request: SubRequest) -> str:
    """ Yields shell definition yaml attribute for testing. """
    yield request.param


@pytest.mark.parametrize('args', [['script', '-h']])
def test_sub_commands(args: List[str]) -> None:
    """ Test general behaviour of shellfoundry_traffic sub commands. """
    with pytest.raises(SystemExit) as cm:
        main(args)
    assert cm.value.code == 0


def test_script(dist: Path, script_definition_yaml) -> None:
    """ Test script sub command. """
    main(['--yaml', script_definition_yaml, 'script'])
    excluded_files = _get_script_definition(script_definition_yaml)["files"]["exclude"]
    assert excluded_files[0] not in _get_script_zip(dist, script_definition_yaml).filelist


def _get_script_definition(script_definition_yaml: str) -> dict:
    script_definition_yaml = Path(__file__).parent.joinpath(f'{script_definition_yaml}.yaml')
    with open(script_definition_yaml, 'r') as file:
        return yaml.safe_load(file)


def _get_script_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    script_zip = dist.joinpath(f'{_get_script_definition(shell_definition_yaml)["metadata"]["script_name"]}.zip')
    return ZipFile(script_zip, 'r')
