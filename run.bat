@echo on
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set "LAUNCHER_VERSION=1.0.0"
set "LOGFILE=launcher.log"
set "PY_FILE=main.py"
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "EXITCODE=0"
set "BASE_PACKAGES=customtkinter docker PyYAML pywin32"

type nul > "%LOGFILE%"

echo [INFO] Launcher version: %LAUNCHER_VERSION%
>> "%LOGFILE%" echo [INFO] Launcher version: %LAUNCHER_VERSION%
echo [INFO] Start time: %date% %time%
>> "%LOGFILE%" echo [INFO] Start time: %date% %time%
echo [INFO] Working directory: %CD%
>> "%LOGFILE%" echo [INFO] Working directory: %CD%
echo [INFO] Target Python file: %PY_FILE%
>> "%LOGFILE%" echo [INFO] Target Python file: %PY_FILE%
echo [INFO] Project path should use ASCII letters, numbers, hyphen, or underscore.
>> "%LOGFILE%" echo [INFO] Project path should use ASCII letters, numbers, hyphen, or underscore.

echo [INFO] Checking target Python file.
>> "%LOGFILE%" echo [INFO] Checking target Python file.
if not exist "%PY_FILE%" goto ERROR_PY_MISSING

echo [INFO] Checking system Python.
>> "%LOGFILE%" echo [INFO] Checking system Python.
where python >nul 2>&1
if errorlevel 1 goto ERROR_PYTHON_MISSING
python --version >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_PYTHON_MISSING

echo [INFO] Checking virtual environment.
>> "%LOGFILE%" echo [INFO] Checking virtual environment.
if exist "%VENV_PY%" goto SKIP_VENV_CREATE
goto CREATE_VENV

:CREATE_VENV
echo [INFO] Creating virtual environment.
>> "%LOGFILE%" echo [INFO] Creating virtual environment.
python -m venv "%VENV_DIR%" >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_VENV_CREATE
goto CHECK_VENV_PYTHON

:SKIP_VENV_CREATE
echo [INFO] Virtual environment already exists.
>> "%LOGFILE%" echo [INFO] Virtual environment already exists.
goto CHECK_VENV_PYTHON

:CHECK_VENV_PYTHON
echo [INFO] Checking virtual environment Python.
>> "%LOGFILE%" echo [INFO] Checking virtual environment Python.
if not exist "%VENV_PY%" goto ERROR_VENV_PYTHON
"%VENV_PY%" --version >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_VENV_PYTHON
goto UPGRADE_PIP

:UPGRADE_PIP
echo [INFO] Upgrading pip.
>> "%LOGFILE%" echo [INFO] Upgrading pip.
"%VENV_PY%" -m pip install --upgrade pip >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_PIP_UPGRADE
goto CHECK_REQUIREMENTS

:CHECK_REQUIREMENTS
echo [INFO] Checking requirements.txt.
>> "%LOGFILE%" echo [INFO] Checking requirements.txt.
if exist "requirements.txt" goto INSTALL_REQUIREMENTS
goto FIRST_INSTALL

:INSTALL_REQUIREMENTS
echo [INFO] Installing from requirements.txt with no dependencies.
>> "%LOGFILE%" echo [INFO] Installing from requirements.txt with no dependencies.
"%VENV_PY%" -m pip install -r "requirements.txt" --no-deps >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_REQUIREMENTS_INSTALL
goto VERIFY_PACKAGES

:FIRST_INSTALL
echo [INFO] requirements.txt not found. Installing base packages with dependencies.
>> "%LOGFILE%" echo [INFO] requirements.txt not found. Installing base packages with dependencies.
"%VENV_PY%" -m pip install %BASE_PACKAGES% >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_FIRST_INSTALL
goto FREEZE_REQUIREMENTS

:FREEZE_REQUIREMENTS
echo [INFO] Freezing requirements.txt.
>> "%LOGFILE%" echo [INFO] Freezing requirements.txt.
"%VENV_PY%" -m pip freeze > "requirements.txt" 2>> "%LOGFILE%"
if errorlevel 1 goto ERROR_FREEZE
goto VERIFY_PACKAGES

:VERIFY_PACKAGES
echo [INFO] Verifying critical packages.
>> "%LOGFILE%" echo [INFO] Verifying critical packages.
"%VENV_PY%" -c "import tkinter, customtkinter, docker, yaml" >> "%LOGFILE%" 2>&1
if errorlevel 1 goto REPAIR_PACKAGES
goto CHECK_BROWSER_RUNTIME

:REPAIR_PACKAGES
echo [INFO] Critical packages missing or broken. Repairing environment.
>> "%LOGFILE%" echo [INFO] Critical packages missing or broken. Repairing environment.
"%VENV_PY%" -m pip install %BASE_PACKAGES% >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_REPAIR_INSTALL
goto FREEZE_REQUIREMENTS_AFTER_REPAIR

:FREEZE_REQUIREMENTS_AFTER_REPAIR
echo [INFO] Refreshing requirements.txt after repair.
>> "%LOGFILE%" echo [INFO] Refreshing requirements.txt after repair.
"%VENV_PY%" -m pip freeze > "requirements.txt" 2>> "%LOGFILE%"
if errorlevel 1 goto ERROR_FREEZE
goto VERIFY_PACKAGES_AFTER_REPAIR

:VERIFY_PACKAGES_AFTER_REPAIR
echo [INFO] Verifying critical packages after repair.
>> "%LOGFILE%" echo [INFO] Verifying critical packages after repair.
"%VENV_PY%" -c "import tkinter, customtkinter, docker, yaml" >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_REPAIR_INSTALL
goto CHECK_BROWSER_RUNTIME

:CHECK_BROWSER_RUNTIME
echo [INFO] Browser automation runtime is not required for this project.
>> "%LOGFILE%" echo [INFO] Browser automation runtime is not required for this project.
goto RUN_SCRIPT

:RUN_SCRIPT
echo [INFO] Running Python script.
>> "%LOGFILE%" echo [INFO] Running Python script.
"%VENV_PY%" "%PY_FILE%" >> "%LOGFILE%" 2>&1
if errorlevel 1 goto ERROR_SCRIPT_RUN
echo [SUCCESS] Python script finished successfully.
>> "%LOGFILE%" echo [SUCCESS] Python script finished successfully.
goto END

:ERROR_PY_MISSING
echo [ERROR] Target Python file is missing: %PY_FILE%
>> "%LOGFILE%" echo [ERROR] Target Python file is missing: %PY_FILE%
set "EXITCODE=1"
goto END

:ERROR_PYTHON_MISSING
echo [ERROR] System Python was not found or cannot run.
>> "%LOGFILE%" echo [ERROR] System Python was not found or cannot run.
set "EXITCODE=1"
goto END

:ERROR_VENV_CREATE
echo [ERROR] Failed to create virtual environment.
>> "%LOGFILE%" echo [ERROR] Failed to create virtual environment.
set "EXITCODE=1"
goto END

:ERROR_VENV_PYTHON
echo [ERROR] Virtual environment Python is missing or broken.
>> "%LOGFILE%" echo [ERROR] Virtual environment Python is missing or broken.
set "EXITCODE=1"
goto END

:ERROR_PIP_UPGRADE
echo [ERROR] Failed to upgrade pip.
>> "%LOGFILE%" echo [ERROR] Failed to upgrade pip.
set "EXITCODE=1"
goto END

:ERROR_REQUIREMENTS_INSTALL
echo [ERROR] Failed to install requirements.txt.
>> "%LOGFILE%" echo [ERROR] Failed to install requirements.txt.
set "EXITCODE=1"
goto END

:ERROR_FIRST_INSTALL
echo [ERROR] Failed to install base packages.
>> "%LOGFILE%" echo [ERROR] Failed to install base packages.
set "EXITCODE=1"
goto END

:ERROR_REPAIR_INSTALL
echo [ERROR] Failed to repair critical packages.
>> "%LOGFILE%" echo [ERROR] Failed to repair critical packages.
set "EXITCODE=1"
goto END

:ERROR_FREEZE
echo [ERROR] Failed to write requirements.txt.
>> "%LOGFILE%" echo [ERROR] Failed to write requirements.txt.
set "EXITCODE=1"
goto END

:ERROR_PLAYWRIGHT_INSTALL
echo [ERROR] Failed to install Playwright browser runtime.
>> "%LOGFILE%" echo [ERROR] Failed to install Playwright browser runtime.
set "EXITCODE=1"
goto END

:ERROR_SCRIPT_RUN
echo [ERROR] Python script exited with an error.
>> "%LOGFILE%" echo [ERROR] Python script exited with an error.
set "EXITCODE=1"
goto END

:END
echo [INFO] End time: %date% %time%
>> "%LOGFILE%" echo [INFO] End time: %date% %time%
echo [INFO] Full log saved to: %LOGFILE%
>> "%LOGFILE%" echo [INFO] Full log saved to: %LOGFILE%
pause
exit /b %EXITCODE%
