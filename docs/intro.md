---
sidebar_position: 1
title: Introduction
---

# Introduction

[**TestBench Requirement Service**](https://github.com/imbus/testbench-requirement-service) is a lightweight, asynchronous REST API service for [imbus TestBench](https://www.testbench.com) that provides unified access to requirements from multiple sources, including Jira, Excel/text files, and JSONL.

## Features

- **Multiple data sources**: read requirements from JSONL files, Excel spreadsheets (`.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt`), or Jira via its REST API.
- **Unified REST API**: a single API surface regardless of the underlying data source.
- **Interactive setup**: a CLI wizard (`init`) that generates a complete configuration in seconds.
- **Swagger UI**: built-in interactive API documentation at `/docs`.
- **HTTPS & mTLS**: optional TLS termination and mutual TLS for production deployments.
- **Reverse proxy support**: first-class configuration for Nginx, Apache, and similar proxies.
- **Extensible**: create your own `RequirementReader` to connect any data source.

## Core concepts

| Concept | Description |
|---------|-------------|
| **Project** | A top-level grouping of requirements. How projects are discovered depends on the active reader (directories on disk, Jira projects, etc.). |
| **Baseline** | A version or snapshot of a project's requirements. |
| **Requirements tree** | The baseline content exposed as a tree of folders/groups and leaf requirements. |
| **Reader** | A pluggable component that knows how to fetch projects, baselines, and requirements from a specific data source. |

## How it works

The service runs a [Sanic](https://sanic.dev)-based HTTP server and delegates all domain logic to a configured `RequirementReader` implementation. Reader configuration can live inline in the main `config.toml` or in a separate file.

```
┌──────────────────────────────────────┐
│          TestBench RM Proxy          │
└───────────────────┬──────────────────┘
                    │  HTTP (Basic Auth)
┌───────────────────▼──────────────────┐
│    TestBench Requirement Service     │
│                (Sanic)               │
├──────────────────────────────────────┤
│          RequirementReader           │
├────────────┬────────────┬────────────┤
│    JSONL   │   Excel    │    Jira    │
└──────┬─────┴──────┬─────┴──────┬─────┘
       │            │            │
 .jsonl files  .xlsx/.csv  Jira REST API
```

## Where to go next

- **New here?** Start with the [Installation](getting-started/installation.md) and [Quickstart](getting-started/quickstart.md) guides.
- **Configuring the service?** See the [Configuration](configuration.md) page.
- **Choosing a reader?** Check the [Readers overview](readers/index.md) for a comparison, then dive into [JSONL](readers/jsonl.md), [Excel](readers/excel.md), or [Jira](readers/jira.md).
- **Running as a Windows service?** See the [Windows service guide](windows-service-installation/index.md).
- **CLI reference?** See the [CLI commands](cli-commands.md) page.
