import inspect
import json
import os
import time
from os import path
from typing import Optional, Tuple

import yaml
import xml.etree.ElementTree as ET

from cloudshell.api.cloudshell_api import (CloudShellAPISession, ResourceAttributesUpdateRequest, AttributeNameValue,
                                           ResourceInfo, CreateReservationResponseInfo, SetConnectorRequest)
from cloudshell.helpers.scripts.cloudshell_dev_helpers import attach_to_cloudshell_as
from cloudshell.shell.core.session.cloudshell_session import CloudShellSessionContext
from cloudshell.shell.core.driver_context import (ResourceCommandContext, ResourceContextDetails, AutoLoadCommandContext,
                                                  ConnectivityContext, InitCommandContext, AppContext)
from cloudshell.traffic.helpers import wait_for_services, wait_for_connectors
from cloudshell.traffic.healthcheck import HEALTHCHECK_STATUS_MODEL
from shellfoundry.utilities.config_reader import Configuration, CloudShellConfigReader

import shellfoundry_traffic.cloudshell_scripts_helpers as script_helpers


def load_devices(devices_env=''):
    deployment_root = get_shell_root()
    devices_file = os.environ.get(devices_env, deployment_root + '/devices.yaml')
    with open(devices_file) as f:
        return yaml.safe_load(f)


def print_inventory(inventory):
    print('\n')
    for r in inventory.resources:
        print(f'{r.relative_address}, {r.model}, {r.name}')
    print('\n')
    for a in inventory.attributes:
        print(f'{a.relative_address}, {a.attribute_name}, {a.attribute_value}')


def assert_health_check(health_check, device):
    print(json.dumps(health_check, indent=2))
    assert health_check['report']['name'] == device['resource']
    assert type(health_check['report']['result']) is bool


#
# 1st gen helpers used by IxChariot, Avalanche and Xena controller shells. Remove once all controllers are upgraded.
#

def create_session_from_cloudshell_config():

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
# 2nd generation helers.
#

def get_shell_root():
    index = 1
    test_name = inspect.stack()[index][1]
    while os.path.splitext(test_name)[0] == os.path.splitext(__file__)[0]:
        index += 1
        test_name = inspect.stack()[index][1]
    deployment_dir = path.dirname(test_name)
    if not path.exists(deployment_dir + '/deployment.xml'):
        deployment_dir = path.dirname(deployment_dir)
        if not path.exists(deployment_dir + '/deployment.xml'):
            deployment_dir = path.dirname(deployment_dir)
    return deployment_dir


def get_deployment_root():
    deployment = get_shell_root() + '/deployment.xml'
    return ET.parse(deployment).getroot()


def get_credentials_from_deployment():
    root = get_deployment_root()
    host = root.find('serverRootAddress').text
    username = root.find('username').text
    password = root.find('password').text
    domain = root.find('domain').text
    return host, username, password, domain


def create_session_from_deployment() -> CloudShellAPISession:
    return CloudShellAPISession(*get_credentials_from_deployment())


def create_session_from_config() -> CloudShellAPISession:
    config = Configuration(CloudShellConfigReader()).read()
    return CloudShellAPISession(config.host, config.username, config.password, config.domain)


def create_topology_reservation(session, topology_path, global_inputs, reservation_name='tg regression tests'):
    end_named_reservations(session, reservation_name)
    _, owner, _, _ = get_credentials_from_deployment()
    return session.CreateImmediateTopologyReservation(reservationName=reservation_name, owner=owner,
                                                      topologyFullPath=topology_path, globalInputs=global_inputs,
                                                      durationInMinutes=60)


def create_reservation(session: CloudShellAPISession,
                       reservation_name: Optional[str] = 'tg regression tests',
                       topology_name: Optional[str] = None) -> CreateReservationResponseInfo:
    """ Create new named reservation. If there is already existing resrvation with the same name it will be ended. """
    end_named_reservations(session, reservation_name)
    _, owner, _, _ = get_credentials_from_deployment()
    if topology_name:
        return session.CreateImmediateTopologyReservation(reservation_name, owner, topologyFullPath=topology_name,
                                                          durationInMinutes=60)
    else:
        return session.CreateImmediateReservation(reservation_name, owner, durationInMinutes=60)


def end_named_reservations(session, reservation_name):
    _, owner, _, _ = get_credentials_from_deployment()
    reservations = session.GetCurrentReservations(reservationOwner=owner)
    for reservation in [r for r in reservations.Reservations if r.Name == reservation_name]:
        end_reservation(session, reservation.Id)


def end_reservation(session, reservation_id):
    try:
        session.EndReservation(reservation_id)
        while session.GetReservationDetails(reservation_id).ReservationDescription.Status != 'Completed':
            time.sleep(1)
        session.DeleteReservation(reservation_id)
    except Exception as _:
        pass


def autoload_command_context(session: CloudShellAPISession, family: str, model: str, address: str,
                             attributes: Optional[dict] = None) -> AutoLoadCommandContext:
    return AutoLoadCommandContext(*_conn_and_res(session, family, model, address, attributes, 'Resource', ''))


def service_init_command_context(session: CloudShellAPISession, model: str,
                                 attributes: Optional[dict] = None) -> InitCommandContext:
    return InitCommandContext(*_conn_and_res(session, 'CS_CustomService', model, 'na', attributes, 'Service', ''))


def resource_init_command_context(session: CloudShellAPISession, family: str, model: str, address: str,
                                  attributes: Optional[dict] = None, full_name='Testing/testing') -> InitCommandContext:
    return InitCommandContext(*_conn_and_res(session, family, model, address, attributes, 'Resource', full_name))


def resource_command_context(session: CloudShellAPISession, reservation_id: str, resource_name: Optional[str] = None,
                             service_name: Optional[str] = None) -> ResourceCommandContext:
    """ Create reservation, add service to reservation, get context details and create ResourceCommandContext. """
    os.environ['DEVBOOTSTRAP'] = 'True'
    debug_attach_from_deployment(reservation_id, resource_name, service_name)
    reservation = script_helpers.get_reservation_context_details()
    resource = script_helpers.get_resource_context_details()
    connectivity = ConnectivityContext(session.host, '8029', '9000', session.token_id, '9.1',
                                       CloudShellSessionContext.DEFAULT_API_SCHEME)
    return ResourceCommandContext(connectivity, resource, reservation, [])


def create_autoload_resource(session: CloudShellAPISession, model: str, full_name: str, address: Optional[str] = 'na',
                             attributes: Optional[list] = None) -> ResourceInfo:
    """ Create resource for Autoload testing. """
    folder = path.dirname(full_name)
    name = path.basename(full_name)
    existing_resource = [r for r in session.GetResourceList().Resources if r.Name == name]
    if existing_resource:
        session.DeleteResource(existing_resource[0].Name)
    resource = session.CreateResource(resourceModel=model, resourceName=name, folderFullPath=folder,
                                      resourceAddress=address, resourceDescription='should be removed after test')
    session.UpdateResourceDriver(resource.Name, model)
    if attributes:
        session.SetAttributesValues([ResourceAttributesUpdateRequest(full_name, attributes)])
    return resource


def create_healthcheck_services(session: CloudShellAPISession, reservation_id: str, source: str,
                                aliases: Optional[dict] = None) -> None:
    """ Create health check service and connect it to to the requested source. """
    if not aliases:
        aliases = {HEALTHCHECK_STATUS_MODEL: 'none'}
    for alias, status_selector in aliases.items():
        attributes = [AttributeNameValue(f'{HEALTHCHECK_STATUS_MODEL}.status_selector', status_selector)]
        session.AddServiceToReservation(reservation_id, HEALTHCHECK_STATUS_MODEL, alias, attributes)
        connector = SetConnectorRequest(source, alias, Direction='bi', Alias=alias)
        session.SetConnectorsInReservation(reservation_id, [connector])
    wait_for_services(session, reservation_id, list(aliases.keys()), timeout=8)
    wait_for_connectors(session, reservation_id, list(aliases.keys()))


def debug_attach_from_deployment(reservation_id, resource_name=None, service_name=None):
    host, username, password, domain = get_credentials_from_deployment()
    attach_to_cloudshell_as(server_address=host,
                            user=username,
                            password=password,
                            reservation_id=reservation_id,
                            domain=domain,
                            resource_name=resource_name,
                            service_name=service_name)


def _conn_and_res(session: CloudShellAPISession, family: str, model: str, address: str, attributes: dict, type: str,
                  full_name: str) -> Tuple[ConnectivityContext, ResourceContextDetails]:
    if not attributes:
        attributes = {}
    connectivity = ConnectivityContext(session.host, '8029', '9000', session.token_id, '9.1',
                                       CloudShellSessionContext.DEFAULT_API_SCHEME)
    resource = ResourceContextDetails(id='ididid', name=path.basename(full_name), fullname=full_name, type=type,
                                      address=address, model=model, family=family, attributes=attributes,
                                      app_context=AppContext('', ''), networks_info='', description='',
                                      shell_standard='', shell_standard_version='')
    return connectivity, resource
