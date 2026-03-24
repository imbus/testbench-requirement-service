---
sidebar_position: 2
title: Authentication
---

API endpoints require HTTP Basic Authentication.

## Set credentials

Generate and store a password hash and salt in your config:

```bash
testbench-requirement-service set-credentials
```

## Quick check (curl)

```bash
curl -u "admin:mypassword" http://127.0.0.1:8000/projects
```

Typical responses:

- Missing `Authorization` header: `401`
- Invalid credentials: `403`

## Public endpoints

Swagger UI and OpenAPI endpoints are typically reachable without authentication:

- `/docs`
- `/docs/openapi.json`
- `/openapi.yaml`
