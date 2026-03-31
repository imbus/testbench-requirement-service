---
sidebar_position: 1
title: Installation
---

# Installation

## Requirements

- **Python 3.10** or higher
- **pip** (included with Python)

---

## Option 1: Install from PyPI *(Recommended)*

The simplest way to install. Requires internet access.

```bash
pip install testbench-requirement-service
```

This installs the base package with the [JSONL reader](../readers/jsonl.md) included. To use the Excel or Jira reader, add the corresponding extra:

| Reader | Install command |
|--------|-----------------|
| [JSONL](../readers/jsonl.md) *(default)* | `pip install testbench-requirement-service` |
| [Excel](../readers/excel.md) | `pip install testbench-requirement-service[excel]` |
| [Jira](../readers/jira.md) | `pip install testbench-requirement-service[jira]` |

You can combine extras:

```bash
pip install testbench-requirement-service[excel,jira]
```

---

## Option 2: Install from a wheel package *(Offline)*

Use this option when installing on a machine without internet access, for example when you received an offline installation package (`.zip`).

**1. Extract the zip:**

Unzip the provided package to a local folder, e.g. `C:\install\`:

```
C:\install\
  testbench_requirement_service-x.y.z-py3-none-any.whl
  <dependency wheels ...>
```

**2. Install from the local folder:**

```bash
pip install --no-index --find-links "C:\install" testbench-requirement-service
```

To include optional extras, add them as usual — pip will resolve them from the local folder:

```bash
pip install --no-index --find-links "C:\install" testbench-requirement-service[excel]
```

:::note
The offline package is platform- and Python-version-specific. Make sure you use the package that matches your system (e.g. `win_amd64`, `py310`).
:::

---

## Option 3: Install from source

Use this option to install directly from the source code, for example when working with a development version.

**1. Clone the repository:**

```bash
git clone https://github.com/imbus/testbench-requirement-service.git
cd testbench-requirement-service
```

**2. Install the package:**

```bash
pip install .
```

With optional extras:

```bash
pip install .[excel,jira]
```

---

## Verify the installation

```bash
testbench-requirement-service --version
```

If the installation was successful, this prints the installed version.

---

## Next steps

Head to the [Quickstart](quickstart.md) to configure and start the service.
