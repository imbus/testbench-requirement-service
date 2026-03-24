---
sidebar_position: 3
title: Jira Reader — Testing
---

## Smoke test

1. Export the required Jira env vars (or set them in config).
2. Start the server.
3. Call `/projects` and ensure Jira projects are returned.

```bash
curl -u "admin:mypassword" http://127.0.0.1:8000/projects
```

## Common failures

- Missing `[jira]` dependencies
- Wrong `server_url`
- Missing env vars for the selected `auth_type`
- Network / proxy / certificate issues
