*** Settings ***
Library     Process
Library     Collections
Library     OperatingSystem


*** Variables ***
${service_process}      None


*** Keywords ***
Start Requirement Service
    [Arguments]
    ...    ${config}=${EMPTY}
    ...    ${reader_class}=${EMPTY}
    ...    ${reader_config}=${EMPTY}
    ...    ${host}=${EMPTY}
    ...    ${port}=${EMPTY}
    ${command}=    Create List    testbench-requirement-service    start
    IF    "${config}"    Append To List    ${command}    --config    ${config}
    IF    "${reader_class}"
        Append To List    ${command}    --reader-class    ${reader_class}
    END
    IF    "${reader_config}"
        Append To List    ${command}    --reader-config    ${reader_config}
    END
    IF    "${host}"    Append To List    ${command}    --host    ${host}
    IF    "${port}"    Append To List    ${command}    --port    ${port}

    ${cwd}=    Set Variable    ${CURDIR}/..
    ${process}=    Start Process
    ...    @{command}
    ...    cwd=${cwd}
    ...    stdout=logs/testbench-requirement-service.log
    ...    stderr=STDOUT
    Set Suite Variable    ${service_process}    ${process}
    Sleep    2s
    ${is_running}=    Is Process Running    ${service_process}
    IF    ${is_running} == False
        Terminate Process    ${service_process}    kill=True
        ${result}=    Get Process Result    ${service_process}
        Log    Service process output: ${result.stdout}    ERROR
        Log    Service process error: ${result.stderr}    ERROR
        Fail    Service process crashed during startup with return code ${result.rc}
    END

Stop Requirement Service
    ${is_running}=    Is Process Running    ${service_process}
    IF    ${is_running}
        ${os}=    Evaluate    platform.system()    platform

        IF    "${os}" == "Windows"
            ${pid}=    Get Process Id    ${service_process}
            Log    Attempting to kill PID: ${pid} on Windows
            Run Process    taskkill    /F    /T    /PID    ${pid}
            ${result}=    Wait For Process    ${service_process}    timeout=5s    on_timeout=continue
        ELSE
            Log    Attempting to terminate process on ${os}
            Terminate Process    ${service_process}    kill=True
            ${result}=    Wait For Process    ${service_process}    timeout=5s    on_timeout=continue
        END

        Log    Service process output: ${result.stdout}
        Log    Service process error: ${result.stderr}
    END
