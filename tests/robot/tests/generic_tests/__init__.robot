*** Settings ***
Resource            ../../resources/service_setup.robot

Suite Setup         Start Requirement Service    JsonlFileReader    jsonl_config.py
Suite Teardown      Stop Requirement Service
