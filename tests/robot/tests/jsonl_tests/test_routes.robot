*** Settings ***
Library     resources/APIKeywords.py    reuse_session=True


*** Test Cases ***
Get Server Name And Version Should Return 200 And String With Name And Version
    ${response}=    Get Server Name And Version
    Should Be Equal    ${response.json()}    TestBenchRequirementService-1.0.0b6

Get All Projects Should Return 200 And List Of Projects
    ${response}=    Get Projects
    ${projects}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${projects}, list)
    Length Should Be    ${projects}    2
    Should Contain    ${projects}    Demo

Get Baselines Should Return 200 And List Of Baselines If Project Exists
    ${response}=    Get Baselines    Demo
    Should Be Equal As Numbers    ${response.status_code}    200
    ${baselines}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${baselines}, list)
    Length Should Be    ${baselines}    2
    Should Contain    ${baselines[1]}    name
    Should Contain    ${baselines[1]}    date
    Should Contain    ${baselines[1]}    type
    Should Be Equal As Strings    ${baselines[1]["name"]}    Baseline2

Get Baselines Should Return 404 If Project Does Not Exist
    Get Baselines    !?.    validate    value.status_code == 404

Get Requirements Root Should Return 200 And A BaselineObjectNode If Project And Baseline Exist
    ${response}=    Get Requirements Root    Demo    Baseline1
    ${requirements_root}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${requirements_root}, dict)
    Should Contain    ${requirements_root}    name
    Should Contain    ${requirements_root}    date
    Should Contain    ${requirements_root}    type
    Should Contain    ${requirements_root}    children
    Should Be Equal As Strings    ${requirements_root["name"]}    Baseline1
    Should Not Be Empty    ${requirements_root["children"]}
    Should Contain    ${requirements_root["children"][0]["name"]}    Requirement1

Get Requirements Root Should Return 404 If Project Does Not Exist
    Get Requirements Root    ${EMPTY}    Baseline1    validate    value.status_code == 404

Get Requirements Root Should Return 404 If Baseline Does Not Exist
    Get Requirements Root    Demo    ${EMPTY}    validate    value.status_code == 404

Get User Defined Attributes Should Return 200 And List Of UserDefinedAttribute Objects
    ${response}=    Get User Defined Attributes
    ${user_defined_attributes}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${user_defined_attributes}, list)
    Length Should Be    ${user_defined_attributes}    2
    Should Contain    ${user_defined_attributes[1]}    name
    Should Contain    ${user_defined_attributes[1]}    valueType
    Should Contain    ${user_defined_attributes[1]}    stringValue
    Should Contain    ${user_defined_attributes[1]}    stringValues
    Should Contain    ${user_defined_attributes[1]}    booleanValue
    Should Be Equal As Strings    ${user_defined_attributes[1]["name"]}    Status
    Should Be Equal As Strings    ${user_defined_attributes[1]["valueType"]}    STRING
    Should Be Equal    ${user_defined_attributes[1]["booleanValue"]}    ${None}

Post All User Defined Attributes Should Return 200 And List Of UserDefinedAttributes For RequirementKeys If Project And Baseline Exist
    ${response}=    Post All User Defined Attributes
    ...    Demo
    ...    Baseline1
    ...    body={"keys": [{"id": "req1", "version": "1.0"}, {"id": "req2", "version": "1.0"}, {"id": "req3", "version": "1.0"}], "attributeNames": ["Priority", "Status", "TEST"]}
    ${response_json}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${response_json}, list)
    Length Should Be    ${response_json}    3
    Should Contain    ${response_json[2]}    key
    Should Contain    ${response_json[2]["key"]}    id
    Should Contain    ${response_json[2]["key"]}    version
    Should Be Equal As Strings    ${response_json[2]["key"]["id"]}    req3
    Should Be Equal As Strings    ${response_json[2]["key"]["version"]}    1.0
    Should Contain    ${response_json[2]}    userDefinedAttributes
    Should Be True    isinstance(${response_json[2]["userDefinedAttributes"]}, list)
    Length Should Be    ${response_json[2]["userDefinedAttributes"]}    1
    Should Contain    ${response_json[2]["userDefinedAttributes"][0]}    name
    Should Contain    ${response_json[2]["userDefinedAttributes"][0]}    valueType
    Should Contain    ${response_json[2]["userDefinedAttributes"][0]}    stringValue
    Should Contain    ${response_json[2]["userDefinedAttributes"][0]}    stringValues
    Should Contain    ${response_json[2]["userDefinedAttributes"][0]}    booleanValue
    Should Be Equal As Strings    ${response_json[2]["userDefinedAttributes"][0]["name"]}    Priority
    Should Be Equal As Strings    ${response_json[2]["userDefinedAttributes"][0]["stringValue"]}    High
    Should Be Equal    ${response_json[2]["userDefinedAttributes"][0]["booleanValue"]}    ${None}

Post All User Defined Attributes Should Return 400 If Request Body Is Empty
    Post All User Defined Attributes    Demo    Baseline1    {}    validate    value.status_code == 400

Post All User Defined Attributes Should Return 400 If Request Body Is Invalid
    Post All User Defined Attributes
    ...    Demo
    ...    Baseline1
    ...    {"keys": {"id": "req1", "version": "1.0"}, "attributeName": "Priority"}
    ...    validate
    ...    value.status_code == 400

Post All User Defined Attributes Should Return 404 If Project Does Not Exist
    Post All User Defined Attributes
    ...    !
    ...    Baseline1
    ...    {"keys": [], "attributeNames": []}
    ...    validate
    ...    value.status_code == 404

Post All User Defined Attributes Should Return 404 If Baseline Does Not Exist
    Post All User Defined Attributes
    ...    Demo
    ...    !#!
    ...    {"keys": [], "attributeNames": []}
    ...    validate
    ...    value.status_code == 404

Post Extended Requirement Should Return 200 And A ExtendedRequirementObject If Project And Baseline Exist
    ${response}=    Post Extended Requirement    Demo    Baseline1    {"id": "req1", "version": "1.0"}
    ${extended_requirement}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${extended_requirement}, dict)
    Should Contain    ${extended_requirement}    name
    Should Contain    ${extended_requirement}    extendedID
    Should Contain    ${extended_requirement}    key
    Should Contain    ${extended_requirement}    owner
    Should Contain    ${extended_requirement}    status
    Should Contain    ${extended_requirement}    priority
    Should Contain    ${extended_requirement}    requirement
    Should Contain    ${extended_requirement}    description
    Should Contain    ${extended_requirement}    documents
    Should Contain    ${extended_requirement}    baseline
    Should Be Equal As Strings    ${extended_requirement["name"]}    Requirement1
    Should Be Equal As Strings    ${extended_requirement["baseline"]}    Baseline1
    Should Not Be Empty    ${extended_requirement["key"]}
    Should Contain    ${extended_requirement["key"]["id"]}    req1
    Should Contain    ${extended_requirement["key"]["version"]}    1.0
    Should Not Be Empty    ${extended_requirement["documents"]}
    Should Contain    ${extended_requirement["documents"]}    login_spec.pdf

Post Extended Requirement Should Return 400 If Request Body Is Empty
    Post Extended Requirement    Demo    Baseline1    {}    validate    value.status_code == 400

Post Extended Requirement Should Return 400 If Request Body Is Invalid
    Post Extended Requirement
    ...    Demo
    ...    Baseline1
    ...    {"keys": [{"id": "req1", "version": "1.0"}]}
    ...    validate
    ...    value.status_code == 400

Post Extended Requirement Should Return 404 If Project Does Not Exist
    Post Extended Requirement
    ...    ${Empty}
    ...    Baseline1
    ...    {"id": "req1", "version": "1.0"}
    ...    validate
    ...    value.status_code == 404

Post Extended Requirement Should Return 404 If Baseline Does Not Exist
    Post Extended Requirement
    ...    Demo
    ...    ${EMPTY}
    ...    {"id": "req1", "version": "1.0"}
    ...    validate
    ...    value.status_code == 404

Post Requirement Versions Should Return 200 And List Of RequirementVersionObjects If Project And Baseline Exist
    ${response}=    Post Requirement Versions    Demo    Baseline1    {"id": "req8", "version": "1.0"}
    ${requirement_versions}=    Set Variable    ${response.json()}
    Should Be True    isinstance(${requirement_versions}, list)
    Length Should Be    ${requirement_versions}    2
    Should Contain    ${requirement_versions[1]}    name
    Should Contain    ${requirement_versions[1]}    date
    Should Contain    ${requirement_versions[1]}    author
    Should Contain    ${requirement_versions[1]}    comment
    Should Be Equal As Strings    ${requirement_versions[1]["name"]}    2.0
    Should Be Equal As Strings    ${requirement_versions[1]["comment"]}    another version

Post Requirement Versions Should Return 400 If Request Body Is Empty
    Post Requirement Versions    Demo    Baseline1    {}    validate    value.status_code == 400

Post Requirement Versions Should Return 400 If Request Body Is Invalid
    Post Requirement Versions
    ...    Demo
    ...    Baseline1
    ...    {"version": "1.0"}
    ...    validate
    ...    value.status_code == 400

Post Requirement Versions Should Return 404 If Project Does Not Exist
    Post Requirement Versions
    ...    abc
    ...    Baseline1
    ...    {"id": "req1", "version": "1.0"}
    ...    validate
    ...    value.status_code == 404

Post Requirement Versions Should Return 404 If Baseline Does Not Exist
    Post Requirement Versions
    ...    Demo
    ...    öäü
    ...    {"id": "req1", "version": "1.0"}
    ...    validate
    ...    value.status_code == 404
