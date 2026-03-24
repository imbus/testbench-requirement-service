---
sidebar_position: 3
title: Excel Reader — Testing
---

## Smoke test

1. Start the server.
2. Verify projects and baselines are discovered.

```bash
curl -u "admin:mypassword" http://127.0.0.1:8000/projects
```

## Common failures

- Missing `[excel]` dependencies
- Misconfigured separators / column indices
- Windows path escaping issues in `.properties`
