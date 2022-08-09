"""
Test cloudshell_traffic CLI command.
"""
# pylint: disable=redefined-outer-name
import importlib.util
import os
import shutil
from pathlib import Path
from typing import List
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
import yaml
from _pytest.fixtures import SubRequest
from cloudshell.rest.api import PackagingRestApiClient
from cloudshell.rest.exceptions import ShellNotFoundException
from shellfoundry.utilities.config_reader import CloudShellConfigReader, Configuration

from shellfoundry_traffic.shellfoundry_traffic_cmd import _get_main_class, main

SHELL_FOUNDRY_TRAFFIC_TESTS = "c:/temp/shell_foundry_traffic_tests"


@pytest.fixture
def dist() -> Path:
    """Yields empty dist folder."""
    dist = Path(__file__).parent.joinpath("dist")
    shutil.rmtree(dist, ignore_errors=True)
    os.mkdir(dist)
    return dist


@pytest.fixture(scope="session")
def packaging_api() -> PackagingRestApiClient:
    """Yields packaging API object."""
    config = Configuration(CloudShellConfigReader()).read()
    return PackagingRestApiClient(config.host, config.port, config.username, config.password, config.domain)


@pytest.fixture(params=["shell-definition-1", "shell-definition-2"])
def shell_definition_yaml(request: SubRequest) -> str:
    """Yields shell definition yaml attribute for testing."""
    return request.param


@pytest.mark.parametrize("args", [["-V"], ["--version"], ["-h"], ["--help"], ["--version", "-h"]])
def test_command(args: List[str]) -> None:
    """Test general behaviour of shellfoundry_traffic command."""
    with pytest.raises(SystemExit) as exception_info:
        main(args)
    assert exception_info.value.code == 0


@pytest.mark.parametrize("args", [["generate", "-h"], ["pack", "-h"], ["install", "-h"]])
def test_sub_commands(args: List[str]) -> None:
    """Test general behaviour of shellfoundry_traffic sub commands."""
    with pytest.raises(SystemExit) as exception_info:
        main(args)
    assert exception_info.value.code == 0


def test_pack(dist: Path, shell_definition_yaml: str) -> None:
    """Test pack sub command."""
    main(["--yaml", shell_definition_yaml, "pack"])
    shell_zip = _get_shell_zip(dist, shell_definition_yaml)
    assert Path(shell_zip.filename).name == f"{_template_name(shell_definition_yaml)}.zip"
    assert f"{shell_definition_yaml}.yaml" in shell_zip.namelist()
    driver_zip = _get_driver_zip(dist, shell_definition_yaml)
    driver_metadata_xml = driver_zip.read("drivermetadata.xml")
    driver_metadata = ElementTree.fromstring(driver_metadata_xml)
    main_class = _get_main_class(shell_definition_yaml + ".yaml")
    assert driver_metadata.attrib["MainClass"] == main_class
    assert driver_metadata.attrib["Name"] == main_class.split(".")[1]


def test_generate(dist: Path, shell_definition_yaml: str) -> None:
    """Test generate sub command."""
    main(["--yaml", shell_definition_yaml, "generate"])
    data_model_py = Path(__file__).parent.joinpath("src").joinpath("data_model.py")
    spec = importlib.util.spec_from_file_location("data_model", data_model_py)
    data_model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data_model)
    assert hasattr(data_model, _template_name(shell_definition_yaml))


def test_install(dist: Path, shell_definition_yaml: str, packaging_api: PackagingRestApiClient) -> None:
    """Test install sub command."""
    main(["--yaml", shell_definition_yaml, "install"])
    assert packaging_api.get_shell(_template_name(shell_definition_yaml))


def test_toska_standard(dist: Path, packaging_api: PackagingRestApiClient) -> None:
    """Test that a specific tosca standard can be installed.

    Requires shell-definition file using the tested standard.
    """
    shell_definition_yaml = "shell-definition-standard"
    try:
        packaging_api.delete_shell(_template_name(shell_definition_yaml))
    except ShellNotFoundException:
        pass
    main(["--yaml", shell_definition_yaml, "install"])
    assert packaging_api.get_shell(_template_name(shell_definition_yaml))


def _template_name(shell_definition_yaml: str) -> str:
    tosca_meta = Path(__file__).parent.joinpath(f"{shell_definition_yaml}.yaml")
    with open(tosca_meta, "r") as file:
        shell_definition = yaml.safe_load(file)
        return shell_definition["metadata"]["template_name"]


def _get_shell_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    shell_zip = dist.joinpath(f"{_template_name(shell_definition_yaml)}.zip")
    return ZipFile(shell_zip, "r")


def _get_driver_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    shell_zip = _get_shell_zip(dist, shell_definition_yaml)
    tosca_meta = Path(__file__).parent.joinpath(f"{shell_definition_yaml}.yaml")
    with open(tosca_meta, "r") as file:
        shell_definition = yaml.safe_load(file)
        artifacts_driver_file = list(shell_definition["node_types"].values())[0]["artifacts"]["driver"]["file"]
    shell_zip.extract(artifacts_driver_file, path=SHELL_FOUNDRY_TRAFFIC_TESTS)
    return ZipFile(Path(SHELL_FOUNDRY_TRAFFIC_TESTS).joinpath(artifacts_driver_file), "r")
