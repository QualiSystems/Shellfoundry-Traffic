"""
Test cloudshell_traffic CLI command.
"""
import importlib.util
import os
import pytest
import shutil
import yaml
from pathlib import Path
from typing import List
from xml.etree import ElementTree
from zipfile import ZipFile

from _pytest.fixtures import SubRequest

from cloudshell.rest.api import PackagingRestApiClient
from shellfoundry.utilities.config_reader import Configuration, CloudShellConfigReader
from shellfoundry_traffic.shellfoundry_traffic import main, _get_main_class


SHELL_FOUNDRY_TRAFFIC_TESTS = 'c:/temp/shell_foundry_traffic_tests'


@pytest.fixture
def dist() -> Path:
    """ Yields empty dist folder. """
    dist = Path(__file__).parent.joinpath('dist')
    shutil.rmtree(dist, ignore_errors=True)
    os.mkdir(dist)
    yield dist


@pytest.fixture(params=['shell-definition-1', 'shell-definition-2'])
def script_definition_yaml(request: SubRequest) -> str:
    """ Yields shell definition yaml attribute for testing. """
    yield request.param


@pytest.mark.parametrize('args', [['-V'], ['--version'], ['-h'], ['--help'], ['--version', '-h']])
def test_command(args: List[str]) -> None:
    """ Test general behaviour of shellfoundry_traffic command. """
    with pytest.raises(SystemExit) as cm:
        main(args)
    assert cm.value.code == 0


@pytest.mark.parametrize('args', [['generate', '-h'], ['pack', '-h'], ['install', '-h']])
def test_sub_commands(args: List[str]) -> None:
    """ Test general behaviour of shellfoundry_traffic sub commands. """
    with pytest.raises(SystemExit) as cm:
        main(args)
    assert cm.value.code == 0


def test_pack(dist: Path, script_definition_yaml) -> None:
    """ Test pack sub command. """
    main(['--yaml', script_definition_yaml, 'pack'])
    shell_zip = _get_shell_zip(dist, script_definition_yaml)
    assert Path(shell_zip.filename).name == f'{_template_name(script_definition_yaml)}.zip'
    assert f'{script_definition_yaml}.yaml' in shell_zip.namelist()
    driver_zip = _get_driver_zip(dist, script_definition_yaml)
    drivermetadata_xml = driver_zip.read('drivermetadata.xml')
    drivermetadata = ElementTree.fromstring(drivermetadata_xml)
    main_class = _get_main_class(script_definition_yaml)
    assert drivermetadata.attrib['MainClass'] == main_class
    assert drivermetadata.attrib['Name'] == main_class.split('.')[1]


def test_generate(dist: Path, script_definition_yaml) -> None:
    """ Test generate sub command. """
    main(['--yaml', script_definition_yaml, 'generate'])
    data_model_py = Path(__file__).parent.joinpath('src').joinpath('data_model.py')
    spec = importlib.util.spec_from_file_location("data_model", data_model_py)
    data_model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data_model)
    assert hasattr(data_model, _template_name(script_definition_yaml))


def test_install(dist: Path, script_definition_yaml) -> None:
    """ Test install sub command. """
    main(['--yaml', script_definition_yaml, 'install'])
    config = Configuration(CloudShellConfigReader()).read()
    api = PackagingRestApiClient(config.host, config.port, config.username, config.password, config.domain)
    assert api.get_shell(_template_name(script_definition_yaml))


def _template_name(shell_definition_yaml: str) -> str:
    tosca_meta = Path(os.getcwd()).joinpath(f'{shell_definition_yaml}.yaml')
    with open(tosca_meta, 'r') as file:
        shell_definition = yaml.safe_load(file)
        return shell_definition['metadata']['template_name']


def _get_shell_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    shell_zip = dist.joinpath(f'{_template_name(shell_definition_yaml)}.zip')
    return ZipFile(shell_zip, 'r')


def _get_driver_zip(dist: Path, shell_definition_yaml: str) -> ZipFile:
    shell_zip = _get_shell_zip(dist, shell_definition_yaml)
    tosca_meta = Path(os.getcwd()).joinpath(f'{shell_definition_yaml}.yaml')
    with open(tosca_meta, 'r') as file:
        shell_definition = yaml.safe_load(file)
        artifacts_driver_file = list(shell_definition['node_types'].values())[0]['artifacts']['driver']['file']
    shell_zip.extract(artifacts_driver_file, path=SHELL_FOUNDRY_TRAFFIC_TESTS)
    return ZipFile(Path(SHELL_FOUNDRY_TRAFFIC_TESTS).joinpath(artifacts_driver_file), 'r')
