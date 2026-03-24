---
sidebar_position: 1
title: Excel Reader — Setup
---

## Overview

Use this reader when requirements are stored in Excel files (`.xlsx`, `.xls`) or delimited text files (`.csv`, `.tsv`, `.txt`).

## Prerequisites

Install the Excel extra:

```bash
pip install testbench-requirement-service[excel]
```

## Setup

1. Create the requirements root directory.
2. Place project folders inside it.
3. Place baseline files inside each project folder.
4. Provide reader configuration either inline (TOML) or via a `.properties` file.

## Minimal config (TOML)

```toml
[testbench-requirement-service]
reader_class = "ExcelRequirementReader"

[testbench-requirement-service.reader_config]
requirementsDataPath = "requirements/excel/"
columnSeparator = ";"
arrayValueSeparator = ","
baselineFileExtensions = ".tsv,.csv,.txt"
"requirement.id" = 1
"requirement.version" = 6
"requirement.name" = 3
```
