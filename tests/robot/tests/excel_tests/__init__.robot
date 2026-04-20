*** Settings ***
Resource            resources/service_setup.robot

Suite Setup         Start Requirement Service    config=data/config_excel.toml
Suite Teardown      Stop Requirement Service
