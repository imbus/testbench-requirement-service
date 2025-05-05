*** Settings ***
Resource            ../../resources/service_setup.robot

Suite Setup         Start Requirement Service    JsonlFileReader    tests/robot/data/reader_config/jsonl/reader_config.py
Suite Teardown      Stop Requirement Service
