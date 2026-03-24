---
sidebar_position: 1
title: Server (Sanic)
---

## What runs where

The Requirement Service is a Sanic-based HTTP server. It serves:

- Swagger UI at `/docs`
- OpenAPI JSON at `/docs/openapi.json`
- OpenAPI YAML at `/openapi.yaml`

## Start the service

Use the Python CLI entrypoint `testbench-requirement-service`.

- `init`: interactive wizard to create `config.toml`
- `configure`: update config interactively
- `set-credentials`: set Basic Auth credentials
- `start`: run the server

## Configuration files

- Default config file: `config.toml`
- Legacy config file: `config.py` (deprecated)

Reader configuration can be:

- Inline under `[testbench-requirement-service.reader_config]` in `config.toml`, or
- A separate file referenced by `reader_config_path`, or
- Overridden at runtime via `start --reader-config <path>`

## Authentication

API endpoints require HTTP Basic Auth. Swagger UI and static assets are reachable without authentication by default.
