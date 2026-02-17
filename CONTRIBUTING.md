# Contributing

Thank you for considering contributing to TestBench Requirement Service! We appreciate your help in making this project even better. Please take a moment to read through this guide to understand how you can contribute effectively.

## Development Setup

To get started with development, follow these steps to clone the repository and set up your environment.

**1. Fork the repository**

Start by forking the repository to your own account.

**2.  Clone your forked repository**

After forking, clone your forked version of the repository to your local machine.

**3. Set up the virtual environment**

We provide a script to automatically set up the virtual environment and install all the necessary dependencies.

Run the following command from the project’s root directory:
```powershell
python bootstrap.py
```

The script `bootstrap.py` creates a virtual environment and installs both development and test dependencies.

**4. Activate the virtual environment**

Once the setup is complete, activate the virtual environment:
- on macOS/Linux:
    ```bash
    source .venv/bin/activate
    ```
- on Windows:
    ```powershell
    .venv\Scripts\activate
    ```
 
## Running Tests

If you want to contribute code, it's important to ensure that everything works correctly. You can run the tests to make sure the code passes all the required checks.

**Run the Robot Framework Tests**

To run the tests, execute the following from the project's root directory:
```powershell
robot --pythonpath tests/robot tests/robot/tests
```

This uses `--pythonpath tests/robot` to enable clean import paths in test files.

**Run specific test suites:**
```powershell
# Excel tests only
robot --pythonpath tests/robot tests/robot/tests/excel_tests

# JSONL tests only
robot --pythonpath tests/robot tests/robot/tests/jsonl_tests

# Generic tests only
robot --pythonpath tests/robot tests/robot/tests/generic_tests
```

**Run from test directory:**
```powershell
cd tests/robot
robot --pythonpath . tests
```