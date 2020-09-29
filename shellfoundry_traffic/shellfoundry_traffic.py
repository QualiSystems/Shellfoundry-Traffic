#!/usr/bin/env python
"""
shellfoundry_traffic CLI command.
"""

import os
import subprocess
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path
from xml.etree import ElementTree

import yaml

from shellfoundry.commands.generate_command import GenerateCommandExecutor
from shellfoundry.commands.install_command import InstallCommandExecutor
from shellfoundry.commands.pack_command import PackCommandExecutor


popenargs = ['py', '-3', '-m', 'pip', 'show', 'shellfoundry_traffic']
pip_output = subprocess.run(popenargs, stdout=subprocess.PIPE).stdout.decode()
try:
    version = pip_output.strip().split('\n')[1].split()[1]
except IndexError:
    version = r'N/A'


def _get_main_class(shell_definition_yaml: str) -> str:
    tosca_meta = Path(os.getcwd()).joinpath(f'{shell_definition_yaml}.yaml')
    with open(tosca_meta, 'r') as file:
        shell_definition = yaml.load(file)
        return shell_definition['metadata']['traffic']['main_class']


def _set_toska_meta(shell_definition_yaml: str) -> None:
    tosca_meta = Path(os.getcwd()).joinpath('TOSCA-Metadata').joinpath('TOSCA.meta')
    with open(tosca_meta, 'r') as file:
        meta_data = yaml.load(file)
        meta_data['Entry-Definitions'] = f'{shell_definition_yaml}.yaml'
    with open(tosca_meta, 'w') as file:
        yaml.dump(meta_data, file)


def generate(shell_definition_yaml: str) -> None:
    """ Set Entry-Definitions in TOSCA.meta to the requested shell-definition yaml and call shellfoundry generate. """
    _set_toska_meta(shell_definition_yaml)
    pack(shell_definition_yaml)
    GenerateCommandExecutor().generate()


def install(shell_definition_yaml: str) -> None:
    """ Set MainClass in drivermetadata yaml to the requested class and call shellfoundry install. """
    pack(shell_definition_yaml)
    InstallCommandExecutor().install()


def pack(shell_definition_yaml: str) -> None:
    """ Set MainClass in drivermetadata yaml to the requested class and call shellfoundry pack. """
    _set_toska_meta(shell_definition_yaml)
    drivermetadata_xml = Path(os.getcwd()).joinpath('src').joinpath('drivermetadata.xml')
    drivermetadata = ElementTree.parse(drivermetadata_xml)
    main_class = _get_main_class(shell_definition_yaml)
    drivermetadata.getroot().attrib['MainClass'] = main_class
    drivermetadata.getroot().attrib['Name'] = main_class.split('.')[1]
    drivermetadata.write(drivermetadata_xml)
    PackCommandExecutor().pack()


def generate_cli(parsed_args: Namespace) -> None:
    """ Extract CLI attributes and call shellfoundry-traffic generate. """
    generate(parsed_args.yaml)


def install_cli(parsed_args: Namespace) -> None:
    """ Extract CLI attributes and call shellfoundry-traffic install. """
    install(parsed_args.yaml)


def pack_cli(parsed_args: Namespace) -> None:
    """ Extract CLI attributes and call shellfoundry-traffic pack. """
    pack(parsed_args.yaml)


def main(args=None) -> None:
    """ shellfoundry_traffic CLI command implementation. """
    parser = ArgumentParser(description='shellfoundry wrapper for traffic shells',
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-V', '--version', action='version', version=version)
    parser.add_argument('-y', '--yaml', required=True, metavar='YAML file', type=str,
                        help='local shell-definition.yaml file')

    subparsers = parser.add_subparsers(help='type "shellfoundry-traffic [subcommand] -h" for help.')

    parser_install = subparsers.add_parser('install', formatter_class=RawDescriptionHelpFormatter,
                                           description='set shell-definition.yaml and main class, then install')
    parser_install.set_defaults(func=install_cli)

    parser_generate = subparsers.add_parser('generate', formatter_class=RawDescriptionHelpFormatter,
                                            description='set shell-definition.yaml file then generate')
    parser_generate.set_defaults(func=generate_cli)

    parser_pack = subparsers.add_parser('pack', formatter_class=RawDescriptionHelpFormatter,
                                        description='set shell-definition.yaml file and main class, then pack')
    parser_pack.set_defaults(func=pack_cli)

    parsed_args = parser.parse_args(args)
    parsed_args.func(parsed_args)


if __name__ == '__main__':
    main((sys.argv[1:]))
