---
sidebar_position: 7
title: Windows Service Installation
---

The TestBench Requirement Service can be deployed as a Windows service for automatic startup and process management.

For the full installation guide covering NSSM, FireDaemon, YAJSW, and Windows Task Scheduler, see the [**Windows Service Installation Guide**](../docs/windows-service-installation).

Use these values when following the central guide:

| Placeholder | Value |
|-------------|-------|
| `<serviceName>` | `TestBenchRequirementService` |
| `<serviceDisplayName>` | `TestBench Requirement Service` |
| `<serviceExecutable>` | `testbench-requirement-service.exe` |
| `<servicePort>` | `8020` |
| `<serviceInstallDir>` | Your installation directory, e.g. `C:\TestBenchRequirementService` |

:::note[Executable path]
- **Ready-to-use executable**: `C:\TestBenchRequirementService\testbench-requirement-service.exe`
- **Python venv**: `C:\TestBenchRequirementService\.venv\Scripts\testbench-requirement-service.exe`

See [Installation](getting-started/installation.md) for details.
:::