*** Settings ***
Library     Process
Library     Collections


*** Variables ***
${service_process}      None


*** Keywords ***
Start Requirement Service
    [Arguments]    ${reader_class}=${EMPTY}    ${reader_config}=${EMPTY}
    ${command}=    Create List    testbench-requirement-service    start    --dev
    IF    "${reader_class}"
        Append To List    ${command}    --reader-class    ${reader_class}
    END
    IF    "${reader_config}"
        Append To List    ${command}    --reader-config    ${reader_config}
    END
    ${process}=    Start Process    @{command}
    Set Suite Variable    ${service_process}    ${process}
    Sleep    1s
    ${is_running}=    Is Process Running    ${service_process}
    IF    ${is_running} == False
        Terminate Process    ${service_process}    kill=True
        ${result}=    Get Process Result    ${service_process}
        Log    Service process output: ${result.stdout}    ERROR
        Log    Service process error: ${result.stderr}    ERROR
        Fail    Service process crashed during startup with return code ${result.rc}
    END

Stop Requirement Service
    Terminate Process    ${service_process}    kill=True
