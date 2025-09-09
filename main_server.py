import os
import json
import requests
import subprocess
import sys
import threading
import signal
from flask import Flask, request, jsonify

from telemost_bot import TelemostBot

EXTERNAL_WEBHOOK_URL = "https://tralala-production.up.railway.app/webhook/bdb03062-4727-4f7c-91bb-fcc0e4d474e9"
SERVER_PORT = 5000

PYTHON_EXECUTABLE = os.path.join(os.path.dirname(__file__), 'venv', 'Scripts', 'python.exe')
if not os.path.exists(PYTHON_EXECUTABLE):
    PYTHON_EXECUTABLE = os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python')
    if not os.path.exists(PYTHON_EXECUTABLE):
        PYTHON_EXECUTABLE = sys.executable

app = Flask(__name__)

CANDIDATE_DATA_STORE = {}
ACTIVE_PROCESSES = {}

@app.route('/approve-interview', methods=['POST'])
def approve_interview():
    print("="*50 + "\nПолучен запрос на ПОДТВЕРЖДЕНИЕ...")
    data = request.get_json()
    analysis_id = data.get('analysis_id')
    if not analysis_id: return jsonify({"status": "error", "message": "Нет analysis_id"}), 400
    CANDIDATE_DATA_STORE[analysis_id] = data
    print(f"Данные для {analysis_id} сохранены.")
    data['webhook_type'] = "interview_approved"
    try:
        requests.post(EXTERNAL_WEBHOOK_URL, json=data, timeout=10).raise_for_status()
        print("Подтверждение успешно переслано.")
        return jsonify({"status": "success", "message": "Подтверждение отправлено."}), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Ошибка вебхука: {e}"}), 502

@app.route('/webhook/create-conference', methods=['GET', 'POST'])
def webhook_create_conference():
    """Запускает telemost_bot.py и СОХРАНЯЕТ ЕГО PID."""
    print("="*50 + "\nПолучен ВЕБХУК на СОЗДАНИЕ КОНФЕРЕНЦИИ...")
    analysis_id = request.args.get('analysis_id') if request.method == 'GET' else (request.get_json() or {}).get('analysis_id')
    if not analysis_id: return jsonify({"status": "error", "message": "Параметр 'analysis_id' не найден"}), 400
    
    try:
        script_path = os.path.join(os.path.dirname(__file__), 'telemost_bot.py')
        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, script_path, '--analysis-id', analysis_id, '--port', str(SERVER_PORT)],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        ACTIVE_PROCESSES[analysis_id] = {"telemost_bot_pid": process.pid}
        print(f"Процесс telemost_bot для {analysis_id} запущен с PID: {process.pid}")
        return jsonify({"status": "accepted", "message": "Процесс создания конференции запущен."}), 202
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось запустить telemost_bot: {e}"}), 500

@app.route('/webhook/forward-invite', methods=['POST'])
def forward_invite():
    print("="*50 + "\nПолучен локальный вебхук от бота с готовой ссылкой...")
    data = request.get_json()
    analysis_id = data.get('analysis_id')
    conference_url = data.get('conference_url')
    candidate_data = CANDIDATE_DATA_STORE.get(analysis_id)
    payload = {"webhook_type": "invite_participant", "analysis_id": analysis_id,
               "conference_invite_url": conference_url, "candidate_data": candidate_data}
    try:
        requests.post(EXTERNAL_WEBHOOK_URL, json=payload, timeout=10).raise_for_status()
        print("Вебхук-приглашение успешно переслан на внешний сервер.")
        return jsonify({"status": "success"}), 200
    except requests.exceptions.RequestException as e:
        print(f"ОШИБКА пересылки приглашения: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook/start-assistant', methods=['POST'])
def webhook_start_assistant():
    """Запускает interview_system.py и СОХРАНЯЕТ ЕГО PID."""
    print("="*50 + "\nПОЛУЧЕН СИГНАЛ! Запускаю голосового ассистента...")
    data = request.get_json()
    analysis_id = data.get('analysis_id')
    if not analysis_id: return jsonify({"status": "error", "message": "analysis_id не найден"}), 400
    
    try:
        script_path = os.path.join(os.path.dirname(__file__), 'interview_system.py')
        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, script_path, '--analysis-id', analysis_id, '--port', str(SERVER_PORT)],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        if analysis_id in ACTIVE_PROCESSES:
            ACTIVE_PROCESSES[analysis_id]["interview_system_pid"] = process.pid
        else:
            ACTIVE_PROCESSES[analysis_id] = {"interview_system_pid": process.pid}
        print(f"Процесс interview_system для {analysis_id} запущен с PID: {process.pid}")
        return jsonify({"status": "success", "message": "Процесс голосового ассистента запущен."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось запустить interview_system: {e}"}), 500

@app.route('/webhook/cleanup', methods=['POST'])
def webhook_cleanup():
    """Принимает сигнал от interview_system и убивает все связанные процессы."""
    print("="*50 + "\nПолучен сигнал на ОЧИСТКУ...")
    data = request.get_json()
    analysis_id = data.get('analysis_id')
    if not analysis_id:
        return jsonify({"status": "error", "message": "analysis_id не найден"}), 400

    print(f"Начинаю очистку для analysis_id: {analysis_id}")
    
    if analysis_id in ACTIVE_PROCESSES:
        pids_to_kill = ACTIVE_PROCESSES[analysis_id]
        print(f"Найдены процессы для уничтожения: {pids_to_kill}")

        telemost_pid = pids_to_kill.get("telemost_bot_pid")
        if telemost_pid:
            try:
                subprocess.run(f"taskkill /F /T /PID {telemost_pid}", check=True, shell=True, capture_output=True)
                print(f"Отправлен сигнал завершения процессу telemost_bot (PID: {telemost_pid})")
            except Exception as e:
                print(f"Не удалось убить процесс telemost_bot (PID: {telemost_pid}): {e}")
        
        interview_pid = pids_to_kill.get("interview_system_pid")
        if interview_pid:
            try:
                subprocess.run(f"taskkill /F /T /PID {interview_pid}", check=True, shell=True, capture_output=True)
                print(f"Отправлен сигнал завершения процессу interview_system (PID: {interview_pid})")
            except Exception as e:
                print(f"Не удалось убить процесс interview_system (PID: {interview_pid}): {e}")

        del ACTIVE_PROCESSES[analysis_id]
        print(f"Запись для {analysis_id} удалена из хранилища активных процессов.")
        return jsonify({"status": "success", "message": "Процессы остановлены."}), 200
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Нет активных процессов для analysis_id: {analysis_id}")
        return jsonify({"status": "not_found", "message": "Активные процессы не найдены."}), 404

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    print(f"Основной сервер запущен на порту {SERVER_PORT}")
    app.run(host='0.0.0.0', port=SERVER_PORT)