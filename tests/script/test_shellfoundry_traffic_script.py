"""
Test cloudshell_traffic script CLI command.
"""
# pylint: disable=redefined-outer-name
import os
import shutil
from pathlib import Path
from typing import Iterable, List
from zipfile import ZipFile

import pytest
import yaml
from _pytest.fixtures import SubRequest

from shellfoundry_traffic.script_utils import SRC_DIR, ScriptCommandExecutor
from shellfoundry_traffic.shellfoundry_traffic_cmd import main


@pytest.fixture
def dist() -> Iterable[Path]:
    """Yields empty dist folder."""
    dist = Path(__file__).parent.joinpath("dist")
    shutil.rmtree(dist, ignore_errors=True)
    if not dist.exists():
        os.mkdir(dist)
    yield dist
    shutil.rmtree(dist, ignore_errors=True)


@pytest.fixture(params=["script-definition.yaml"])
def script_definition_yaml(request: SubRequest) -> str:
    """Yields shell definition yaml attribute for testing."""
    return request.param


@pytest.mark.parametrize("args", [["script", "-h"]])
def test_sub_commands(args: List[str]) -> None:
    """Test general behaviour of shellfoundry_traffic sub commands."""
    with pytest.raises(SystemExit) as exception_info:
        main(args)
    assert exception_info.value.code == 0


@pytest.mark.skip("Fix Me")
def test_script(dist: Path, script_definition_yaml: str) -> None:
    """Test script sub command."""
    main(["--yaml", script_definition_yaml, "script"])
    excluded_files = _get_script_definition(script_definition_yaml)["files"]["exclude"]
    assert excluded_files[0] not in _get_script_zip(dist, script_definition_yaml).filelist


def test_get_main(script_definition_yaml: str) -> None:
    """Test get_main method."""
    os.chdir(Path(__file__).parent)
    with open(SRC_DIR.joinpath("__main__.py"), "w"):
        pass
    script_command = ScriptCommandExecutor(script_definition=script_definition_yaml)
    script_command.get_main()
    script_definition = _get_script_definition(script_definition_yaml)
    new_main_file_name = script_definition["files"]["main"]
    with open(SRC_DIR.joinpath(new_main_file_name), "r") as new_main_file:
        new_main_content = new_main_file.read()
    with open(SRC_DIR.joinpath("__main__.py"), "r") as main_file:
        existing_main_content = main_file.read()
    assert new_main_content == existing_main_content


def _get_script_definition(script_definition: str) -> dict:
    script_definition_yaml = script_definition if script_definition.endswith(".yaml") else f"{script_definition}.yaml"
    script_definition_yaml_full_path = Path(os.getcwd()).joinpath(script_definition_yaml)
    with open(script_definition_yaml_full_path, "r") as file:
        return yaml.safe_load(file)


def _get_script_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    script_zip = dist.joinpath(f'{_get_script_definition(shell_definition_yaml)["metadata"]["script_name"]}.zip')
    return ZipFile(script_zip, "r")
