"""
Main entry point for cloudshell_traffic CLI.
"""
import sys

from shellfoundry_traffic.shellfoundry_traffic_cmd import main

main((sys.argv[1:]))
