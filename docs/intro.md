---
sidebar_position: 1
title: Introduction
---

TestBench Requirement Service is a small REST API that provides unified access to requirements coming from different sources (JSONL, Excel/text files, Jira).

## Core concepts

- **Project**: a top-level grouping of requirements (how this is determined depends on the active reader).
- **Baseline**: a version/snapshot of a project's requirements.
- **Requirements tree**: the baseline content is exposed as a tree with folders/groups and leaf requirements.

## How it works (high level)

- The server runs a Sanic app and delegates all domain logic to a configured `RequirementReader` implementation.
- Reader configuration can be stored inline in the main config file or in a separate reader config file.

## Where to go next

- Quickstart: [getting-started/quickstart.md](getting-started/quickstart.md)
- Server: [server/overview.md](server/overview.md)
- Configuration: [configuration/config-file.md](configuration/config-file.md)
- Pick a reader: [readers/jsonl/setup.md](readers/jsonl/setup.md), [readers/excel/setup.md](readers/excel/setup.md), [readers/jira/setup.md](readers/jira/setup.md)
- Windows service (optional): [windows_service/windows_service_installation_guide.md](windows_service/windows_service_installation_guide.md)
