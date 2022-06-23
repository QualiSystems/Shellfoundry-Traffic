"""
Test helpers for shells and scripts testing.
"""
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from cloudshell.api.cloudshell_api import (
    CloudShellAPISession,
    CreateReservationResponseInfo,
    ResourceAttributesUpdateRequest,
    ResourceInfo,
    UpdateTopologyGlobalInputsRequest,
)
from cloudshell.helpers.scripts.cloudshell_dev_helpers import attach_to_cloudshell_as
from cloudshell.shell.core.driver_context import (
    AppContext,
    AutoLoadCommandContext,
    AutoLoadDetails,
    ConnectivityContext,
    InitCommandContext,
    ResourceCommandContext,
    ResourceContextDetails,
)
from cloudshell.shell.core.session.cloudshell_session import CloudShellSessionContext
from shellfoundry.utilities.config_reader import CloudShellConfigReader, Configuration

import shellfoundry_traffic.cloudshell_scripts_helpers as script_helpers


def load_devices(devices_env: str) -> dict:
    """Load devices from devices file."""
    devices_file = os.environ[devices_env]
    with open(devices_file, "r") as devices:
        return yaml.safe_load(devices)


# flake8: noqa: T001
def print_inventory(inventory: AutoLoadDetails) -> None:
    """Print inventory resources and attributes."""
    print("\n")
    for resource in inventory.resources:
        print(f"{resource.relative_address}, {resource.model}, {resource.name}")
    print("\n")
    for attribute in inventory.attributes:
        print(f"{attribute.relative_address}, {attribute.attribute_name}, {attribute.attribute_value}")


def create_session_from_config() -> CloudShellAPISession:
    """Create session from data in shellfoundry config."""
    config = Configuration(CloudShellConfigReader()).read()
    session = CloudShellAPISession(config.host, config.username, config.password, config.domain)
    # session.domain is Domain ID so we save the domain name in session.domain_name
    session.domain_name = config.domain
    return session


def create_reservation(
    session: CloudShellAPISession,
    reservation_name: str,
    topology_name: Optional[str] = None,
    global_inputs: Optional[List[UpdateTopologyGlobalInputsRequest]] = None,
) -> CreateReservationResponseInfo:
    """Create empty or topology from reservation based on input."""
    if not global_inputs:
        global_inputs = []
    end_named_reservations(session, reservation_name)
    if topology_name:
        reservation = session.CreateImmediateTopologyReservation(
            reservation_name,
            session.username,
            topologyFullPath=topology_name,
            globalInputs=global_inputs,
            durationInMinutes=60,
        )
    else:
        reservation = session.CreateImmediateReservation(reservation_name, session.username, durationInMinutes=60)
    return reservation


def end_named_reservations(session: CloudShellAPISession, reservation_name: str) -> None:
    """End and delete reservation."""
    reservations = session.GetCurrentReservations(reservationOwner=session.username)
    for reservation in [r for r in reservations.Reservations if r.Name == reservation_name]:
        end_reservation(session, reservation.Id)


def end_reservation(session: CloudShellAPISession, reservation_id: str) -> None:
    """End and delete reservation."""
    try:
        session.EndReservation(reservation_id)
        while session.GetReservationDetails(reservation_id).ReservationDescription.Status != "Completed":
            time.sleep(1)
        session.DeleteReservation(reservation_id)
    except Exception:
        pass


class TestHelpers:
    """Manage test session and reservation."""

    def __init__(self, session: CloudShellAPISession) -> None:
        self.session = session
        self.reservation: CreateReservationResponseInfo = None
        self.reservation_id = ""

    def create_topology_reservation(
        self,
        topology_name: str,
        global_inputs: Optional[List[UpdateTopologyGlobalInputsRequest]] = None,
        reservation_name: str = "tg regression tests",
    ) -> CreateReservationResponseInfo:
        """Create new reservation from topology. End existing reservation with the same name if exist."""
        self.reservation = create_reservation(self.session, reservation_name, topology_name, global_inputs)
        self.reservation_id = self.reservation.Reservation.Id
        return self.reservation

    def create_reservation(self, reservation_name: str = "tg regression tests") -> CreateReservationResponseInfo:
        """Create new empty reservation. End existing reservation with the same name if exist."""
        self.reservation = create_reservation(self.session, reservation_name)
        self.reservation_id = self.reservation.Reservation.Id
        return self.reservation

    def end_reservation(self) -> None:
        """End and delete reservation."""
        end_reservation(self.session, self.reservation_id)
        self.reservation = None
        self.reservation_id = ""

    def autoload_command_context(
        self, family: str, model: str, address: str, attributes: Optional[dict] = None
    ) -> AutoLoadCommandContext:
        """Create AutoLoadCommandContext for the requested resource."""
        return AutoLoadCommandContext(*self._conn_and_res(family, model, address, "Resource", "", attributes))

    def service_init_command_context(self, model: str, attributes: Optional[dict] = None) -> InitCommandContext:
        """Create InitCommandContext for the requested service model."""
        return InitCommandContext(*self._conn_and_res("CS_CustomService", model, "na", "Service", "", attributes))

    def resource_init_command_context(
        self,
        family: str,
        model: str,
        address: str,
        attributes: Optional[dict] = None,
        full_name: str = "Testing/testing",
    ) -> InitCommandContext:
        """Create InitCommandContext for the requested resource."""
        return InitCommandContext(*self._conn_and_res(family, model, address, "Resource", full_name, attributes))

    def resource_command_context(
        self, resource_name: Optional[str] = None, service_name: Optional[str] = None
    ) -> ResourceCommandContext:
        """Create ResourceCommandContext for the given resource/service."""
        self.attach_to_cloudshell_as(resource_name, service_name)
        reservation = script_helpers.get_reservation_context_details()
        resource = script_helpers.get_resource_context_details()
        connectivity = ConnectivityContext(
            self.session.host,
            "8029",
            "9000",
            self.session.token_id,
            "9.1",
            CloudShellSessionContext.DEFAULT_API_SCHEME,
        )
        return ResourceCommandContext(connectivity, resource, reservation, [])

    def create_autoload_resource(
        self,
        model: str,
        full_name: str,
        address: Optional[str] = "na",
        attributes: Optional[list] = None,
    ) -> ResourceInfo:
        """Create resource for Autoload testing."""
        folder = Path(full_name).parent.as_posix()
        name = Path(full_name).name
        existing_resource = [r for r in self.session.GetResourceList().Resources if r.Name == name]
        if existing_resource:
            self.session.DeleteResource(existing_resource[0].Name)
        resource = self.session.CreateResource(
            resourceModel=model,
            resourceName=name,
            folderFullPath=folder,
            resourceAddress=address,
            resourceDescription="should be removed after test",
        )
        self.session.UpdateResourceDriver(resource.Name, model)
        if attributes:
            self.session.SetAttributesValues([ResourceAttributesUpdateRequest(full_name, attributes)])
        return resource

    def attach_to_cloudshell_as(self, resource_name: Optional[str] = None, service_name: Optional[str] = None) -> None:
        """Mock ES behaviour on local machine so the test can create local objects such as contexts, sandboxes etc."""
        os.environ["DEVBOOTSTRAP"] = "True"
        attach_to_cloudshell_as(
            server_address=self.session.host,
            user=self.session.username,
            password=self.session.password,
            reservation_id=self.reservation_id,
            domain=self.session.domain_name,
            resource_name=resource_name,
            service_name=service_name,
        )

    def _conn_and_res(
        self,
        family: str,
        model: str,
        address: str,
        type_: str,
        full_name: str,
        attributes: Optional[dict] = None,
    ) -> Tuple[ConnectivityContext, ResourceContextDetails]:
        if not attributes:
            attributes = {}
        connectivity = ConnectivityContext(
            self.session.host,
            "8029",
            "9000",
            self.session.token_id,
            "9.1",
            CloudShellSessionContext.DEFAULT_API_SCHEME,
        )
        resource = ResourceContextDetails(
            id="ididid",
            name=Path(full_name).name,
            fullname=full_name,
            type=type_,
            address=address,
            model=model,
            family=family,
            attributes=attributes,
            app_context=AppContext("", ""),
            networks_info="",
            description="",
            shell_standard="",
            shell_standard_version="",
        )
        return connectivity, resource
