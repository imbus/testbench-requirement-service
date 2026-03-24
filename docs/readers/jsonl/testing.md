---
sidebar_position: 3
title: JSONL Reader — Testing
---

## Smoke test

1. Start the server.
2. Call the projects endpoint.

Example (replace credentials as needed):

```bash
curl -u "admin:mypassword" http://127.0.0.1:8000/projects
```

## Common failures

- Wrong `requirements_path`
- Missing `UserDefinedAttributes.json`
- Invalid JSONL schema
