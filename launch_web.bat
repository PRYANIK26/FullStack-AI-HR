@echo off
cls
echo ===========================================
echo      STREAMLIT & NGROK LAUNCHER
echo ===========================================
echo.

REM --- Проверка наличия виртуального окружения ---
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found in 'venv' folder.
    echo Please create it first.
    pause
    exit /b
)

REM --- ЭТАП 1: ЗАПУСК NGROK В ОТДЕЛЬНОМ ОКНЕ ---
echo Starting Ngrok tunnel in a new window...
REM Запускаем ngrok. Он будет пытаться подключиться к порту 8501, как только тот станет доступен.
REM Убрана опция --url=, так как она не поддерживается в ngrok http.
REM Вместо этого используем опцию --hostname= для фиксированного домена (требуется платный план ngrok).
REM Для бесплатного плана просто используем ngrok http 8501
start "Ngrok Tunnel" cmd /k "ngrok http --url=myra-unpleasurable-overjudiciously.ngrok-free.app 8501"

echo Waiting for Ngrok to initialize...
timeout /t 3 /nobreak >nul

REM --- ЭТАП 2: ЗАПУСК STREAMLIT В ЭТОМ ОКНЕ ---
echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Starting Streamlit application on port 8501...
REM Запускаем Streamlit на стандартном порту 8501, который слушает ngrok
streamlit run web_page.py

echo.
echo ===========================================
echo Streamlit server has been stopped.
echo You can now close this window.
echo ===========================================
pause