@echo off
cls
echo ===========================
echo      SERVER LAUNCHER 
echo ===========================
echo.
echo Starting servers...

REM --- ЭТАП 1: ЗАПУСК СЕРВЕРОВ В НОВЫХ ОКНАХ ---

REM --- Проверка наличия виртуального окружения ---
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found in 'venv' folder.
    echo Please create it first.
    pause
    exit /b
)

echo Activating virtual environment...
call venv\Scripts\activate

echo.

REM Запускаем Flask-сервер (main_server.py)
echo Starting Main Flask Server (main_server.py)...
start "Main Server" cmd /k "cd /d "%~dp0" && python main_server.py"

REM Ждем пару секунд, чтобы сервер успел запуститься перед туннелем
timeout /t 3 /nobreak >nul

REM Запускаем LocalTunnel с твоим субдоменом
echo Starting LocalTunnel for fullstack-server...
start "LocalTunnel" cmd /k "lt --port 5000 --subdomain fullstack-server"


echo.
echo =================================================================
echo  Servers are starting up in separate windows.
echo  Wait until both windows show that they are running correctly.
echo =================================================================
echo.
echo Press any key to check the health of the public server...
pause >nul


REM --- ЭТАП 2: ПРОВЕРКА ЗДОРОВЬЯ ПО КНОПКЕ ---

echo.
echo Checking server health...
echo Making request to https://fullstack-server.loca.lt/health

REM Используем PowerShell для отправки запроса и получения HTTP-статуса
powershell -Command "try { $response = Invoke-WebRequest -Uri 'https://fullstack-server.loca.lt/health' -UseBasicParsing -TimeoutSec 15; Write-Host 'Status Code:' $response.StatusCode; exit $response.StatusCode } catch { Write-Host 'Error:' $_.Exception.Message; exit 1 }"

if %errorlevel% equ 200 (
    echo.
    echo ---------------------------------------------------
    echo  SUCCESS: Server is healthy (HTTP 200 OK)!
    echo ---------------------------------------------------
) else (
    echo.
    echo ---------------------------------------------------
    echo  ERROR: Server check failed!
    echo  Status code received: %errorlevel%
    echo  Check the Main Server and LocalTunnel windows for errors.
    echo ---------------------------------------------------
)

echo.
echo Press any key to close this control window...
pause >nul