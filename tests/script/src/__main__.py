
from cloudshell.workflow.orchestration.sandbox import Sandbox
from cloudshell.workflow.orchestration.setup.default_setup_orchestrator import DefaultSetupWorkflow
from script import TestOrchestration

sandbox = Sandbox()

script_instance = TestOrchestration(sandbox)

DefaultSetupWorkflow().register(sandbox)

sandbox.workflow.add_to_preparation(script_instance.preparation, None)

sandbox.workflow.add_to_provisioning(script_instance.provisioning, None)

sandbox.workflow.add_to_connectivity(script_instance.connectivity, None)

sandbox.execute_setup()
