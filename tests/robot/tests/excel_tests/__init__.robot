*** Settings ***
Resource            ../../resources/service_setup.robot

Suite Setup         Start Requirement Service    ExcelFileReader    tests/robot/data/reader_config/excel/ProjectDemo.properties
Suite Teardown      Stop Requirement Service
