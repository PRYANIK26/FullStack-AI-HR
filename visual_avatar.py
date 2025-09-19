# visual_avatar.py

import cv2
import threading
from flask import Flask, request, jsonify
import time
import os

# --- КОНФИГУРАЦИЯ ---
VIDEO_FILES = {
    "speaking": "speaking.mp4",
    "typing": "typing.mp4"
}
WINDOW_NAME = "Interview Avatar Anna"
SERVER_PORT = 8000  # Порт, на котором аватар будет слушать команды
# --------------------

class VideoPlayer:
    def __init__(self):
        self.current_state = "typing"  # Начальное состояние - "печатает/ждет"
        self.video_captures = {}
        self.stop_event = threading.Event()
        
        # Загружаем оба видеофайла при старте
        for state, filename in VIDEO_FILES.items():
            if not os.path.exists(filename):
                raise FileNotFoundError(f"Видеофайл не найден: {filename}. Убедитесь, что он лежит в той же папке.")
            self.video_captures[state] = cv2.VideoCapture(filename)
            if not self.video_captures[state].isOpened():
                raise IOError(f"Не удалось открыть видеофайл: {filename}")

    def set_state(self, new_state: str):
        """Изменяет состояние аватара ('speaking' или 'typing')."""
        if new_state in VIDEO_FILES:
            if self.current_state != new_state:
                print(f"AVATAR: Переключение состояния -> {new_state.upper()}")
                self.current_state = new_state
        else:
            print(f"AVATAR: Предупреждение - неизвестное состояние '{new_state}'")

    def run_loop(self):
        """Основной цикл, который отображает видео в окне."""
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        
        while not self.stop_event.is_set():
            # Выбираем текущее видео для проигрывания
            cap = self.video_captures[self.current_state]
            
            # Читаем кадр
            ret, frame = cap.read()
            
            if ret:
                # Если кадр успешно прочитан, показываем его
                cv2.imshow(WINDOW_NAME, frame)
            else:
                # Если видео закончилось, перематываем его на начало для зацикливания
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Ожидаем 25 мс и проверяем, не нажата ли клавиша 'q' для выхода
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break
        
        # После выхода из цикла освобождаем ресурсы
        for cap in self.video_captures.values():
            cap.release()
        cv2.destroyAllWindows()
        print("AVATAR: Окно закрыто.")

    def start(self):
        """Запускает проигрывание видео в отдельном потоке."""
        self.video_thread = threading.Thread(target=self.run_loop)
        self.video_thread.start()
        print("AVATAR: Видео-поток запущен.")

    def stop(self):
        """Останавливает проигрывание видео."""
        self.stop_event.set()
        if self.video_thread:
            self.video_thread.join()

# --- СЕРВЕР ДЛЯ УПРАВЛЕНИЯ АВАТАРОМ ---
app = Flask(__name__)
video_player = VideoPlayer()

@app.route('/set_state', methods=['POST'])
def set_state():
    """Эндпоинт для смены состояния аватара."""
    data = request.get_json()
    new_state = data.get('state')
    
    if not new_state:
        return jsonify({"status": "error", "message": "Параметр 'state' не найден"}), 400
        
    video_player.set_state(new_state)
    return jsonify({"status": "success", "new_state": new_state}), 200

def run_flask_app():
    """Запускает Flask-сервер."""
    app.run(host='0.0.0.0', port=SERVER_PORT)
    # После завершения работы сервера останавливаем и видеоплеер
    video_player.stop()

if __name__ == '__main__':
    # Запускаем плеер
    video_player.start()
    
    # Запускаем сервер для управления в основном потоке
    print(f"AVATAR: Сервер управления запущен на порту {SERVER_PORT}")
    print("AVATAR: Нажмите 'q' в окне с видео, чтобы закрыть аватар.")
    run_flask_app()