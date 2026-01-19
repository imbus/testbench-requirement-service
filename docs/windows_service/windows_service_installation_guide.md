# Windows Service Installation Guide

## Option 1: FireDaemon

### Installation Steps

1. Open FireDaemon Pro as Administrator.

![FireDaemon GUI Initial](images/firedaemon-1.png)

2. Click the Plus icon (New) or press Ctrl+N to create a new service.
![FireDaemon GUI New Button](images/firedaemon-2.png)
![FireDaemon GUI New Service](images/firedaemon-3.png)

3. Configure the following in the **Program** tab:
   ###### Service Identification:
   - Service Name: `TestBenchRequirementService`
   - Display Name: `TestBench Requirement Service`
   - Custom Prefix String: Check and leave empty ` `
   - Description: `Python-based TestBench Requirement Service`
   - Startup Type: `Automatic (Delayed Start)`
   ###### Program to Run as a Service:
   - Program: Path to the Python service executable
     e.g., `E:\Code\requirement-service-python\.venv\Scripts\testbench-requirement-service.exe`
   - Working Directory: Path to the root directory containing configuration files
     e.g., `E:\Code\requirement-service-python\`
   - Parameters: Startup parameters for the Python service
     e.g., `start --port 8010`
   - Type: `Always Running Program`

![FireDaemon GUI Program Tab Filled](images/firedaemon-4.png)

4. Configure the following in the **Settings** tab:
   ###### General:
   - Show Window: `Hidden`
   - Job Type: `Global`
   ###### Logon:
   Configure if a specific account should run the service.

![FireDaemon GUI Settings Tab Filled](images/firedaemon-5.png)

5. Configure the following in the **Lifecycle** tab:
   ###### Lifecycle:
   - Upon Program Exit: `Stop FireDaemon Service`
   - Console Program: `True`
   - Shutdown By: `Ctrl+C` or `Forceful Termination`

![FireDaemon GUI Lifecycle Tab Filled](images/firedaemon-6.png)

6. Configure the following in the **Logging** tab:
   ###### Output Capture:
   - Capture Stdout in File: Path for stdout logging, e.g., `E:\Code\requirement-service-python\windows_service.log`
   - Capture Stderr in Stdout: `True` or specify a separate path for stderr

![FireDaemon GUI Logging Tab Filled](images/firedaemon-7.png)

7. **Optional:** In the **Dependencies** tab, configure dependencies to other services.
8. **Optional:** In the **Environment** tab, set environment variables.
9. **Optional:** In the **Events** tab, configure start and termination events.
10. Configure the following in the **Scheduling** tab:
    - Overall Launch Delay: e.g., `60 seconds`

![FireDaemon GUI Scheduling Tab Filled](images/firedaemon-8.png)

11. Click the checkmark icon to save the settings and close the service definition.

![FireDaemon GUI Save and Close Button](images/firedaemon-9.png)

12. Select "TestBench Requirement Service" from the services list and click the Start icon (green play button) to start the service.

![FireDaemon GUI Start Service](images/firedaemon-10.png)

13. The service should now be running.

![FireDaemon GUI Service Running](images/firedaemon-11.png)

### Managing the Service

First select the service from the services list.

##### Start service:
![FireDaemon GUI Start Service](images/firedaemon-12.png)

##### Stop service:
![FireDaemon GUI Stop Service](images/firedaemon-13.png)

##### Restart service:
![FireDaemon GUI Restart Service](images/firedaemon-14.png)

##### Edit service:
![FireDaemon GUI Edit Service](images/firedaemon-15.png)

##### Remove service:
![FireDaemon GUI Remove Service](images/firedaemon-16.png)

## Option 2: NSSM

### Installation

1. Open a command prompt (e.g., PowerShell) as Administrator.

2. Configure the service using one of the following methods:

### Method 1: GUI Configuration

1. Run the command `nssm install TestBenchRequirementService`. The GUI will open automatically.
![NSSM GUI Initial](images/nssm-1.png)

2. Configure the following in the **Application** tab:
   - Path: Path to the Python service executable
     e.g., `E:\Code\requirement-service-python\.venv\Scripts\testbench-requirement-service.exe`
   - Startup directory: Path to the root directory containing configuration files
     e.g., `E:\Code\requirement-service-python\`
   - Arguments: Startup parameters for the Python service
     e.g., `start --port 8011`
![NSSM GUI Application Tab Filled](images/nssm-2.png)

3. Configure the following in the **Details** tab:
   - Display name: `TestBench Requirement Service`
   - Description: `Python-based TestBench Requirement Service`
   - Startup type: `Automatic (Delayed)`
![NSSM GUI Details Tab Filled](images/nssm-3.png)

4. **Optional:** In the **Log On** tab, configure the service for specific accounts. Only needed if not using the local system account.

5. **Optional:** In the **Dependencies** tab, configure Windows Service dependencies. Only needed if something must run before the service starts.

6. **Optional:** In the **Process** tab, configure process-related settings such as process priority.

7. **Optional:** In the **Shutdown** tab, specify how the service should handle the Python service shutdown.

8. Configure the following in the **Exit actions** tab:
   - Restart: `Stop Service (oneshot mode)`
![NSSM GUI Exit Actions Tab Filled](images/nssm-4.png)

9. Configure the following in the **I/O** tab:
   - Output (stdout): Path to the log file for stdout output
   - Error (stderr): Path to the log file for stderr output
![NSSM GUI IO Tab Filled](images/nssm-5.png)

10. **Optional:** In the **File rotation** tab, configure log file rotation.

11. **Optional:** In the **Environment** tab, set environment variables for the service.

12. **Optional:** In the **Hooks** tab, define event hooks such as running a command before service start.

13. After completing all settings, click the "Install Service" button to install the service.
![NSSM GUI Install Service Button](images/nssm-6.png)

14. A confirmation dialog should appear upon successful installation.
![NSSM GUI Successful Install](images/nssm-7.png)

### Method 2: CLI Configuration

1. Install the service directly:
```powershell
nssm install TestBenchRequirementService "E:\Code\requirement-service-python\.venv\Scripts\testbench-requirement-service.exe" "start --port 8011"
```

2. Configure application settings (startup directory):
```powershell
nssm set TestBenchRequirementService AppDirectory "E:\Code\requirement-service-python"
```

3. Configure details settings (display name, description, startup type):
```powershell
nssm set TestBenchRequirementService DisplayName "Requirement Service"
nssm set TestBenchRequirementService Description "Python-based Requirement Service"
nssm set TestBenchRequirementService Start SERVICE_DELAYED_AUTO_START
```

4. Configure exit actions (restart behavior):
```powershell
nssm set TestBenchRequirementService AppExit Default StopService
```

5. Configure I/O settings (logging):
```powershell
nssm set TestBenchRequirementService AppStdout "E:\Code\requirement-service-python\logs\stdout.log"
nssm set TestBenchRequirementService AppStderr "E:\Code\requirement-service-python\logs\stderr.log"
nssm set TestBenchRequirementService AppRotateFiles 1
```

### Managing the Service

##### Start service:
```powershell
nssm start TestBenchRequirementService
```

##### Check status:
```powershell
nssm status TestBenchRequirementService
```

##### Edit service:
```powershell
nssm edit TestBenchRequirementService
```

##### Restart service:
```powershell
nssm restart TestBenchRequirementService
```

##### Stop service:
```powershell
nssm stop TestBenchRequirementService
```

##### Remove service:
```powershell
nssm remove TestBenchRequirementService
```