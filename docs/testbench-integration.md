---
sidebar_position: 5
title: TestBench Integration
---
# TestBench Integration

This page explains how to connect TestBench to the running TestBench Requirement Service.

---

## Overview

TestBench communicates with the Requirement Service through the **RMProxy** (Requirement Management Proxy) component. The connection is configured via a `.properties` file in the TestBench installation directory.

---

## Requirements

- TestBench Requirement Service is installed and running (see [Quick Start](getting-started/quickstart.md)).
- You know the host and port the service is listening on.
- You have set credentials with `testbench-requirement-service set-credentials`.

---

## Configuration in TestBench

The RMProxy is a component of the TestBench installation, located at e.g.:

```
C:\imbus\TestBench\iTB_RMProxy\
```

It contains two relevant configuration files:

### 1. Wrapper configuration

Located in the `wrapper-config` subdirectory, e.g.:

```
C:\imbus\TestBench\iTB_RMProxy\wrapper-config\requirement-service-wrapper.properties
```

This file registers the Requirement Service as a repository and points to its settings. **You typically do not need to change anything here**, but verify it contains:

```properties
de.imbus.itb.re.wrapper.class=de.imbus.testbench.service.rm.RequirementServiceWrapper

# Repository ID shown in TestBench
name=RequirementService

settings = ../RequirementService/settings.properties
```

The `name` value is the repository identifier that appears in TestBench. The `settings` path points to the service settings file (relative to the wrapper config file).

### 2. Service settings

Located at (relative to the RMProxy directory):

```
C:\imbus\TestBench\iTB_RMProxy\RequirementService\settings.properties
```

**This is the file you need to edit.** Set the URL to match the host and port the Requirement Service is listening on:

```properties
# Server configuration
server.url=http://127.0.0.1:8020
```

If you configured HTTPS, use `https://` instead and ensure the TestBench host trusts the certificate.

---

## Verifying the Connection

1. Start the Requirement Service:
   ```bash
   testbench-requirement-service start
   ```
2. Open TestBench and trigger an import of requirements. Check the service logs for incoming requests.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Connection refused` | Service is not running or port mismatch | Start the service; verify `host` and `port` in config. |
| `401 Unauthorized` | Wrong credentials | Re-run `testbench-requirement-service set-credentials` |
| `500 Server Error` | Service or reader misconfiguration | Check service logs; run `configure --view` to inspect current settings. |

---

## Network Considerations

- By default the service listens on `127.0.0.1` (loopback only). To accept connections from another machine (e.g. TestBench running on a different host), set `host = "0.0.0.0"` in `config.toml`.
- If a firewall is in place, open the configured port (default `8020`).
- For production deployments, consider enabling HTTPS — see [Configuration](configuration.md#https--tls)