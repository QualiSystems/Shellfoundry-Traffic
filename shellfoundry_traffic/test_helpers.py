import inspect
import json
import os
import time
from os import path
from typing import Optional, Tuple

import yaml
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET

from cloudshell.api.cloudshell_api import (CloudShellAPISession, ResourceAttributesUpdateRequest, AttributeNameValue,
                                           ResourceInfo, UpdateTopologyGlobalInputsRequest, SetConnectorRequest,
                                           CreateReservationResponseInfo)
from cloudshell.helpers.scripts.cloudshell_dev_helpers import attach_to_cloudshell_as
from cloudshell.shell.core.session.cloudshell_session import CloudShellSessionContext
from cloudshell.shell.core.driver_context import (ResourceCommandContext, ResourceContextDetails,
                                                  AutoLoadCommandContext, ConnectivityContext,
                                                  InitCommandContext, AppContext)
from cloudshell.traffic.helpers import wait_for_services, wait_for_connectors
from cloudshell.traffic.health_check import HEALTH_CHECK_STATUS_MODEL
from shellfoundry.utilities.config_reader import Configuration, CloudShellConfigReader

import shellfoundry_traffic.cloudshell_scripts_helpers as script_helpers


def load_devices(devices_env: [str] = ''):
    deployment_root = get_shell_root()
    devices_file = os.environ.get(devices_env, deployment_root + '/devices.yaml')
    with open(devices_file) as f:
        return yaml.safe_load(f)


def print_inventory(inventory) -> None:
    print('\n')
    for r in inventory.resources:
        print(f'{r.relative_address}, {r.model}, {r.name}')
    print('\n')
    for a in inventory.attributes:
        print(f'{a.relative_address}, {a.attribute_name}, {a.attribute_value}')


def assert_health_check(health_check: dict, device: dict) -> None:
    print(json.dumps(health_check, indent=2))
    assert health_check['report']['name'] == device['resource']
    assert type(health_check['report']['result']) is bool


#
# 1st gen helpers used by IxChariot, Avalanche and Xena controller shells. Remove once all controllers are upgraded.
#

def create_session_from_cloudshell_config() -> object:
    test_name = inspect.stack()[1][1]
    f = path.join(path.dirname(path.dirname(test_name)), 'cloudshell_config.yml')
    with open(f, 'r') as f:
        doc = yaml.load(f)
    username = doc['install']['username']
    password = doc['install']['password']
    domain = doc['install']['domain']
    host = doc['install']['host']
    return CloudShellAPISession(host, username, password, domain)

#
# 2nd generation helpers.
#


DEPLOYMENT_XML = '/deployment.xml'


def get_shell_root() -> str:
    index = 1
    test_name = inspect.stack()[index][1]
    while os.path.splitext(test_name)[0] == os.path.splitext(__file__)[0]:
        index += 1
        test_name = inspect.stack()[index][1]
    deployment_dir = path.dirname(test_name)
    if not path.exists(deployment_dir + DEPLOYMENT_XML):
        deployment_dir = path.dirname(deployment_dir)
        if not path.exists(deployment_dir + DEPLOYMENT_XML):
            deployment_dir = path.dirname(deployment_dir)
    return deployment_dir


def get_deployment_root():
    deployment = get_shell_root() + DEPLOYMENT_XML
    return ET.parse(deployment).getroot()


def get_credentials_from_deployment() -> tuple:
    root = get_deployment_root()
    host = root.find('serverRootAddress').text
    username = root.find('username').text
    password = root.find('password').text
    domain = root.find('domain').text
    return host, username, password, domain


def create_session_from_deployment() -> CloudShellAPISession:
    """ Create session from data in deployment yaml file. """
    return CloudShellAPISession(*get_credentials_from_deployment())


def create_session_from_config() -> CloudShellAPISession:
    """ Create session from data in shellfoundry config. """
    config = Configuration(CloudShellConfigReader()).read()
    return CloudShellAPISession(config.host, config.username, config.password, config.domain)


def create_reservation(session: CloudShellAPISession, reservation_name: str, topology_name: Optional[str] = None,
                       global_inputs: Optional[list[UpdateTopologyGlobalInputsRequest]] = None):
    """ Create empty  or topology from reservation based on input. """
    if not global_inputs:
        global_inputs = []
    end_named_reservations(session, reservation_name)
    if topology_name:
        reservation = session.CreateImmediateTopologyReservation(reservation_name, session.username,
                                                                 topologyFullPath=topology_name,
                                                                 globalInputs=global_inputs,
                                                                 durationInMinutes=60)
    else:
        reservation = session.CreateImmediateReservation(reservation_name, session.username, durationInMinutes=60)
    return reservation


def end_named_reservations(session: CloudShellAPISession, reservation_name: str) -> None:
    """ End and delete reservation. """
    reservations = session.GetCurrentReservations(reservationOwner=session.username)
    for reservation in [r for r in reservations.Reservations if r.Name == reservation_name]:
        end_reservation(session, reservation.Id)


def end_reservation(session: CloudShellAPISession, reservation_id: str) -> None:
    """ End and delete reservation. """
    try:
        session.EndReservation(reservation_id)
        while session.GetReservationDetails(reservation_id).ReservationDescription.Status != 'Completed':
            time.sleep(1)
        session.DeleteReservation(reservation_id)
    except Exception as _:
        pass


class TestHelpers:
    """ Manage test session and reservation. """

    def __init__(self, session: CloudShellAPISession) -> None:
        self.session = session
        self.reservation = None
        self.reservation_id = ''

    def create_topology_reservation(self, topology_name,
                                    global_inputs: Optional[list[UpdateTopologyGlobalInputsRequest]] = None,
                                    reservation_name: str = 'tg regression tests') -> CreateReservationResponseInfo:
        """ Create new reservation from topology. End existing reservation with the same name if exist. """
        self.reservation = create_reservation(self.session, reservation_name, topology_name, global_inputs)
        self.reservation_id = self.reservation.Reservation.Id
        return self.reservation

    def create_reservation(self, reservation_name: str = 'tg regression tests') -> CreateReservationResponseInfo:
        """ Create new empty reservation. End existing reservation with the same name if exist. """
        self.reservation = create_reservation(self.session, reservation_name)
        self.reservation_id = self.reservation.Reservation.Id
        return self.reservation

    def end_reservation(self) -> None:
        """ End and delete reservation. """
        end_reservation(self.session, self.reservation_id)
        self.reservation = None
        self.reservation_id = ''

    def autoload_command_context(self, family: str, model: str, address: str,
                                 attributes: Optional[dict] = None) -> AutoLoadCommandContext:
        return AutoLoadCommandContext(*self._conn_and_res(family, model, address, attributes, 'Resource', ''))

    def service_init_command_context(self, model: str, attributes: Optional[dict] = None) -> InitCommandContext:
        return InitCommandContext(*self._conn_and_res('CS_CustomService', model, 'na', attributes, 'Service', ''))

    def resource_init_command_context(self, family: str, model: str, address: str, attributes: Optional[dict] = None,
                                      full_name='Testing/testing') -> InitCommandContext:
        return InitCommandContext(*self._conn_and_res(family, model, address, attributes, 'Resource', full_name))

    def resource_command_context(self, resource_name: Optional[str] = None,
                                 service_name: Optional[str] = None) -> ResourceCommandContext:
        """ Create reservation, add service to reservation, get context details and create ResourceCommandContext. """
        os.environ['DEVBOOTSTRAP'] = 'True'
        self.debug_attach_from_deployment(resource_name, service_name)
        reservation = script_helpers.get_reservation_context_details()
        resource = script_helpers.get_resource_context_details()
        connectivity = ConnectivityContext(self.session.host, '8029', '9000', self.session.token_id, '9.1',
                                           CloudShellSessionContext.DEFAULT_API_SCHEME)
        return ResourceCommandContext(connectivity, resource, reservation, [])

    def create_autoload_resource(self, model: str, full_name: str, address: Optional[str] = 'na',
                                 attributes: Optional[list] = None) -> ResourceInfo:
        """ Create resource for Autoload testing. """
        folder = path.dirname(full_name)
        name = path.basename(full_name)
        existing_resource = [r for r in self.session.GetResourceList().Resources if r.Name == name]
        if existing_resource:
            self.session.DeleteResource(existing_resource[0].Name)
        resource = self.session.CreateResource(resourceModel=model, resourceName=name, folderFullPath=folder,
                                               resourceAddress=address,
                                               resourceDescription='should be removed after test')
        self.session.UpdateResourceDriver(resource.Name, model)
        if attributes:
            self.session.SetAttributesValues([ResourceAttributesUpdateRequest(full_name, attributes)])
        return resource

    def create_health_check_services(self, source: str,
                                     aliases: Optional[dict] = None) -> None:
        """ Create health check service and connect it to to the requested source. """
        if not aliases:
            aliases = {HEALTH_CHECK_STATUS_MODEL: 'none'}
        for alias, status_selector in aliases.items():
            attributes = [AttributeNameValue(f'{HEALTH_CHECK_STATUS_MODEL}.status_selector', status_selector)]
            self.session.AddServiceToReservation(self.reservation_id, HEALTH_CHECK_STATUS_MODEL, alias, attributes)
            connector = SetConnectorRequest(source, alias, Direction='bi', Alias=alias)
            self.session.SetConnectorsInReservation(self.reservation_id, [connector])
        wait_for_services(self.session, self.reservation_id, list(aliases.keys()), timeout=8)
        wait_for_connectors(self.session, self.reservation_id, list(aliases.keys()))

    def debug_attach_from_deployment(self, resource_name: Optional[str] = None,
                                     service_name: Optional[str] = None) -> None:
        attach_to_cloudshell_as(server_address=self.session.host,
                                user=self.session.username,
                                password=self.session.password,
                                reservation_id=self.reservation_id,
                                domain=self.session.domain,
                                resource_name=resource_name,
                                service_name=service_name)

    def _conn_and_res(self, family: str, model: str, address: str, attributes: dict, type_: str,
                      full_name: str) -> Tuple[ConnectivityContext, ResourceContextDetails]:
        if not attributes:
            attributes = {}
        connectivity = ConnectivityContext(self.session.host, '8029', '9000', self.session.token_id, '9.1',
                                           CloudShellSessionContext.DEFAULT_API_SCHEME)
        resource = ResourceContextDetails(id='ididid', name=path.basename(full_name), fullname=full_name, type=type_,
                                          address=address, model=model, family=family, attributes=attributes,
                                          app_context=AppContext('', ''), networks_info='', description='',
                                          shell_standard='', shell_standard_version='')
        return connectivity, resource
