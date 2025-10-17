*** Settings ***
Library     ../../resources/APIKeywords.py


*** Test Cases ***
Get Server Name And Version Should Return 200 And String With Name And Version
    ${response}=    Get Server Name And Version
    Should Be Equal    ${response.json()}    RequirementWrapperAPI-1.0.0a2

Get All Projects Should Return 200 And List Of Projects
    ${response}=    Get Projects
    Should Be True    isinstance(${response.json()}, list)
    Length Should Be    ${response.json()}    2
    Should Contain    ${response.json()}    Demo

Get Baselines Should Return 200 And List Of Baselines If Project Exists
    ${response}=    Get Baselines    Demo
    Should Be Equal As Numbers    ${response.status_code}    200
    Should Be True    isinstance(${response.json()}, list)
    Length Should Be    ${response.json()}    2
    Should Contain    ${response.json()[1]}    name
    Should Contain    ${response.json()[1]}    date
    Should Contain    ${response.json()[1]}    type
    Should Be Equal As Strings    ${response.json()[1]["name"]}    Baseline2

Get Baselines Should Return 404 If Project Does Not Exist
    Get Baselines    !?.    validate    value.status_code == 404

Get Requirements Root Should Return 200 And A BaselineObjectNode If Project And Baseline Exist
    ${response}=    Get Requirements Root    Demo    Baseline1
    Should Be True    isinstance(${response.json()}, dict)
    Should Contain    ${response.json()}    name
    Should Contain    ${response.json()}    date
    Should Contain    ${response.json()}    type
    Should Contain    ${response.json()}    children
    Should Be Equal As Strings    ${response.json()["name"]}    Baseline1
    Should Not Be Empty    ${response.json()["children"]}
    Should Contain    ${response.json()["children"][0]["name"]}    Requirement1

Get Requirements Root Should Return 404 If Project Does Not Exist
    Get Requirements Root    ${EMPTY}    Baseline1    validate    value.status_code == 404

Get Requirements Root Should Return 404 If Baseline Does Not Exist
    Get Requirements Root    Demo    ${EMPTY}    validate    value.status_code == 404

Get User Defined Attributes Should Return 200 And List Of UserDefinedAttribute Objects
    ${response}=    Get User Defined Attributes
    Should Be True    isinstance(${response.json()}, list)
    Length Should Be    ${response.json()}    2
    Should Contain    ${response.json()[1]}    name
    Should Contain    ${response.json()[1]}    valueType
    Should Contain    ${response.json()[1]}    stringValue
    Should Contain    ${response.json()[1]}    stringValues
    Should Contain    ${response.json()[1]}    booleanValue
    Should Be Equal As Strings    ${response.json()[1]["name"]}    Status
    Should Be Equal As Strings    ${response.json()[1]["valueType"]}    STRING
    Should Be Equal    ${response.json()[1]["booleanValue"]}    ${None}

Post All User Defined Attributes Should Return 200 And List Of UserDefinedAttributes For RequirementKeys If Project And Baseline Exist
    ${response}=    Post All User Defined Attributes
    ...    Demo
    ...    Baseline1
    ...    body={"keys": [{"id": "req1", "version": "1.0"}, {"id": "req2", "version": "1.0"}, {"id": "req3", "version": "1.0"}], "attributeNames": ["Priority", "Status", "TEST"]}
    Should Be True    isinstance(${response.json()}, list)
    Length Should Be    ${response.json()}    3
    Should Contain    ${response.json()[2]}    key
    Should Contain    ${response.json()[2]["key"]}    id
    Should Contain    ${response.json()[2]["key"]}    version
    Should Be Equal As Strings    ${response.json()[2]["key"]["id"]}    req3
    Should Be Equal As Strings    ${response.json()[2]["key"]["version"]}    1.0
    Should Contain    ${response.json()[2]}    userDefinedAttributes
    Should Be True    isinstance(${response.json()[2]["userDefinedAttributes"]}, list)
    Length Should Be    ${response.json()[2]["userDefinedAttributes"]}    1
    Should Contain    ${response.json()[2]["userDefinedAttributes"][0]}    name
    Should Contain    ${response.json()[2]["userDefinedAttributes"][0]}    valueType
    Should Contain    ${response.json()[2]["userDefinedAttributes"][0]}    stringValue
    Should Contain    ${response.json()[2]["userDefinedAttributes"][0]}    stringValues
    Should Contain    ${response.json()[2]["userDefinedAttributes"][0]}    booleanValue
    Should Be Equal As Strings    ${response.json()[2]["userDefinedAttributes"][0]["name"]}    Priority
    Should Be Equal As Strings    ${response.json()[2]["userDefinedAttributes"][0]["stringValue"]}    High
    Should Be Equal    ${response.json()[2]["userDefinedAttributes"][0]["booleanValue"]}    ${None}

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
    Should Be True    isinstance(${response.json()}, dict)
    Should Contain    ${response.json()}    name
    Should Contain    ${response.json()}    extendedID
    Should Contain    ${response.json()}    key
    Should Contain    ${response.json()}    owner
    Should Contain    ${response.json()}    status
    Should Contain    ${response.json()}    priority
    Should Contain    ${response.json()}    requirement
    Should Contain    ${response.json()}    description
    Should Contain    ${response.json()}    documents
    Should Contain    ${response.json()}    baseline
    Should Be Equal As Strings    ${response.json()["name"]}    Requirement1
    Should Be Equal As Strings    ${response.json()["baseline"]}    Baseline1
    Should Not Be Empty    ${response.json()["key"]}
    Should Contain    ${response.json()["key"]["id"]}    req1
    Should Contain    ${response.json()["key"]["version"]}    1.0
    Should Not Be Empty    ${response.json()["documents"]}
    Should Contain    ${response.json()["documents"]}    login_spec.pdf

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
    Should Be True    isinstance(${response.json()}, list)
    Length Should Be    ${response.json()}    2
    Should Contain    ${response.json()[1]}    name
    Should Contain    ${response.json()[1]}    date
    Should Contain    ${response.json()[1]}    author
    Should Contain    ${response.json()[1]}    comment
    Should Be Equal As Strings    ${response.json()[1]["name"]}    2.0
    Should Be Equal As Strings    ${response.json()[1]["comment"]}    another version

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
