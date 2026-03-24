---
sidebar_position: 1
title: Jira Reader — Setup
---

## Overview

Use this reader when requirements live in Jira issues and should be fetched via the Jira REST API.

## Prerequisites

Install the Jira extra:

```bash
pip install testbench-requirement-service[jira]
```

## Setup

1. Configure the Jira server URL and authentication type.
2. Provide credentials either via config or environment variables.
3. Start the server.

## Minimal config (TOML)

```toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"

[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
auth_type = "basic"
```
