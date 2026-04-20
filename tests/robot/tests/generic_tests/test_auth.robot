*** Settings ***
Library     resources/APIKeywords.py    reuse_session=False


*** Test Cases ***
Get Server Name And Version Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Get Server Name And Version    validate    value.status_code == 401

Get Server Name And Version Should Return 401 With Invalid Auth
    Set Credentials    user    ${EMPTY}
    Get Server Name And Version    validate    value.status_code == 401

Get Projects Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Get Projects    validate    value.status_code == 401

Get Projects Should Return 401 With Invalid Auth
    Set Credentials    ${EMPTY}    1234
    Get Projects    validate    value.status_code == 401

Get Baselines Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Get Baselines    Demo    validate    value.status_code == 401

Get Baselines Should Return 401 With Invalid Auth
    Set Credentials    user    user
    Get Baselines    Demo    validate    value.status_code == 401

Get Requirements Root Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Get Requirements Root    Demo    Baseline1    validate    value.status_code == 401

Get Requirements Root Should Return 401 With Invalid Auth
    Set Credentials    !    ?
    Get Requirements Root    Demo    Baseline1    validate    value.status_code == 401

Get User Defined Attributes Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Get User Defined Attributes    validate    value.status_code == 401

Get User Defined Attributes Should Return 401 With Invalid Auth
    Set Credentials    admin    ${EMPTY}
    Get User Defined Attributes    validate    value.status_code == 401

Post All User Defined Attributes Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Post All User Defined Attributes    Demo    Baseline1    {}    validate    value.status_code == 401

Post All User Defined Attributes Should Return 401 With Invalid Auth
    Set Credentials    username    password
    Post All User Defined Attributes    Demo    Baseline1    {}    validate    value.status_code == 401

Post Extended Requirement Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Post Extended Requirement    Demo    Baseline1    {}    validate    value.status_code == 401

Post Extended Requirement Should Return 401 With Invalid Auth
    Set Credentials    username    password
    Post Extended Requirement    Demo    Baseline1    {}    validate    value.status_code == 401

Post Requirement Versions Should Return 401 Without Auth
    Set Credentials    ${EMPTY}    ${EMPTY}
    Post Requirement Versions    Demo    Baseline1    {}    validate    value.status_code == 401

Post Requirement Versions Should Return 401 With Invalid Auth
    Set Credentials    admin    1234
    Post Requirement Versions    Demo    Baseline1    {}    validate    value.status_code == 401
