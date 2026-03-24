---
sidebar_position: 1
title: JSONL Reader — Setup
---

## Overview

Use this reader when your requirements are stored as JSON Lines (`.jsonl`) files on disk.

## Prerequisites

- No extra dependencies beyond the base package.

## Setup

1. Create a directory for your requirements.
2. Place project folders inside that directory.
3. Place one or more `.jsonl` baseline files inside each project folder.
4. Add `UserDefinedAttributes.json` at the top level of the requirements directory.

## Minimal config

Put this into your `config.toml`:

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```
