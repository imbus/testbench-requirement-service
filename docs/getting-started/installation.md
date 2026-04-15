---
sidebar_position: 1
title: Installation
---

# Installation

There are two options depending on whether you want to install Python or not:

- **[Option 1: Ready-to-use executable](#option-1-ready-to-use-executable)** (**No Python required**. Download a zip, extract, run. Best for Windows service deployments.)
- **[Option 2: Install with Python](#option-2-install-with-python)** (For users who have Python or are installing it. Managed via pip.)

---

## Option 1: Ready-to-use executable

The executable is a self-contained zip archive. No Python, no pip, no virtual environment needed. All three readers (JSONL, Excel, Jira) are included.

**1. Download the zip**

Either use the zip you received directly, or download it from the [GitHub releases page](https://github.com/imbus/testbench-requirement-service/releases) — expand **Assets** and pick the file for your platform (e.g. `testbench-requirement-service-x.y.z-win_amd64.zip`).

**2. Extract to a permanent location**

Unzip to a folder you won't move later, for example `C:\TestBenchRequirementService\`:

```
C:\TestBenchRequirementService\
  testbench-requirement-service.exe
  <support files>
```

**3. Verify**

```cmd
C:\TestBenchRequirementService\testbench-requirement-service.exe --version
```

:::tip Running as a Windows service
Point NSSM or FireDaemon directly to `testbench-requirement-service.exe` in the extracted folder. See the [Windows service guide](../windows-service-installation.md).
:::

---

## Option 2: Install with Python

Use this option if you have Python installed or are about to install it.

### Requirements

- **Python 3.10–3.14** — 3.13 recommended ([download](https://www.python.org/downloads/))
- **pip** (included with Python)

### Set up a virtual environment

:::note
For [From source](#from-source-developers): skip this step and create the virtual environment inside the cloned repository instead (shown there).
:::

A virtual environment keeps the installation isolated and provides a stable, predictable path to the executable. Navigate to the directory where you want the service to live, then run:

```bash
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

:::tip Running as a Windows service
With a venv, point NSSM or FireDaemon to `.venv\Scripts\testbench-requirement-service.exe` (full absolute path). See the [Windows service guide](../windows-service-installation.md).
:::

---

### From PyPI *(online, recommended)*

```bash
pip install testbench-requirement-service
```

The base install includes the [JSONL reader](../readers/jsonl.md). Add extras for other readers:

| Reader | Install command |
|--------|-----------------|
| [JSONL](../readers/jsonl.md) *(default)* | `pip install testbench-requirement-service` |
| [Excel](../readers/excel.md) | `pip install testbench-requirement-service[excel]` |
| [Jira](../readers/jira.md) | `pip install testbench-requirement-service[jira]` |
| All readers | `pip install testbench-requirement-service[excel,jira]` |

Verify:
```bash
testbench-requirement-service --version
```

---

### From a wheel file *(offline)*

Use this if you received a `.whl` file or downloaded one from the [GitHub releases page](https://github.com/imbus/testbench-requirement-service/releases) (look for `testbench_requirement_service-x.y.z-py3-none-any.whl` in the Assets).

```bash
pip install testbench_requirement_service-x.y.z-py3-none-any.whl
```

With optional extras:

```bash
pip install "testbench_requirement_service-x.y.z-py3-none-any.whl[excel,jira]"
```

Verify:

```bash
testbench-requirement-service --version
```

:::note Fully offline install
By default pip still fetches dependencies from PyPI. To install on a machine with no internet access:

**On a machine with internet access**, download the wheel and all its dependencies into a local folder:

```bash
pip download "testbench_requirement_service-x.y.z-py3-none-any.whl[excel,jira]" -d ./wheels
```

This saves every required wheel into `./wheels/`. Copy that folder together with the `.whl` file to the target machine.

**On the target machine**, install entirely from the local folder:

```bash
pip install --no-index --find-links ./wheels "testbench_requirement_service-x.y.z-py3-none-any.whl[excel,jira]"
```
:::

---

### From source *(developers)*

```bash
git clone https://github.com/imbus/testbench-requirement-service.git
cd testbench-requirement-service
```

Create and activate the virtual environment inside the cloned repository. See [Set up a virtual environment](#set-up-a-virtual-environment).

Install with all readers and development dependencies:

```bash
pip install -e .[excel,jira,dev]
```

Verify:

```bash
testbench-requirement-service --version
```

---

## Next steps

Head to the [Quickstart](quickstart.md) to configure and start the service.
