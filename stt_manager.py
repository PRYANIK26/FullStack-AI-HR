
import threading
import time
import logging
from typing import Callable, Optional, List
from RealtimeSTT import AudioToTextRecorder
from config import Config

class STTManager:
    def __init__(self,
                 on_phrase_detected: Optional[Callable[[], None]] = None,
                 on_silence_detected: Optional[Callable[[List[str]], None]] = None):
        """
        Инициализация STT-менеджера.
        :param on_phrase_detected: Колбэк, вызываемый при распознавании КАЖДОЙ фразы.
        :param on_silence_detected: Колбэк, вызываемый после наступления "длинной" тишины.
        """
        logging.getLogger().setLevel(logging.WARNING)
        
        self.on_phrase_detected = on_phrase_detected
        self.on_silence_detected = on_silence_detected
        
        self.is_listening = False
        self.full_sentences = []
        self.recorder = None
        self.silence_timer = None
        self.silence_timeout = Config.SILENCE_TIMEOUT
        
        self.listen_thread = None
        self._init_recorder()

    def _init_recorder(self):
        """Инициализация рекордера с нужными параметрами."""
        recorder_config = {
            'spinner': False,
            'model': Config.STT_MODEL,
            'language': Config.STT_LANGUAGE,
            'silero_sensitivity': 0.05,
            'webrtc_sensitivity': 3,
            'post_speech_silence_duration': 0.7,
            'min_length_of_recording': 0.5,
            'min_gap_between_recordings': 0,
            
            'enable_realtime_transcription': True,
            'realtime_model_type': 'tiny.en',
            'realtime_processing_pause': 0.02,
            'on_realtime_transcription_update': self._on_realtime_update,
            
            'silero_deactivity_detection': True,
            'beam_size': 5,
            'beam_size_realtime': 3,
            'no_log_file': True,
            'silero_use_onnx': True,
        }
        self.recorder = AudioToTextRecorder(**recorder_config)
        print("STT Recorder инициализирован с real-time моделью для сброса таймера.")

    def _on_realtime_update(self, text: str):
        """
        Колбэк для real-time обновлений.
        Используется ТОЛЬКО для сброса таймера долгой паузы во время речи.
        Не используется для финальной обработки фраз.
        """
        if not self.is_listening:
            return
            
        if text.strip():
            self._reset_silence_timer_during_speech()

    def _reset_silence_timer_during_speech(self):
        """
        Сбрасывает таймер долгой паузы во время речи.
        Вызывается real-time моделью при обнаружении речи.
        """
        if self.silence_timer:
            self.silence_timer.cancel()
            self.silence_timer = None
            print("\033[91mSTT: ⏰ Таймер долгой паузы сброшен - обнаружена речь\033[0m")

    def start_listening(self):
        """Запускает основной поток прослушивания. Полностью сбрасывает предыдущее состояние."""
        if self.is_listening:
            print("STT: Прослушивание уже активно.")
            return

        self.is_listening = True
        self.full_sentences.clear()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        print("STT: Начинаю прослушивание...")

    def stop_listening(self):
        """Полностью и надежно останавливает прослушивание и обработку."""
        if not self.is_listening:
            return
            
        self.is_listening = False
        self._cancel_silence_timer()
        print("STT: Прослушивание остановлено.")

    def _listen_loop(self):
        """
        Основной цикл прослушивания. Работает, пока is_listening=True.
        Использует колбэк для обработки каждой фразы.
        """
        while self.is_listening:
            try:
                self.recorder.text(self._process_recognized_phrase)
            except Exception as e:
                if self.is_listening:
                    print(f"STT Listen Error: {e}")
                    time.sleep(1)

    def _process_recognized_phrase(self, text: str):
        """
        Колбэк, вызываемый для КАЖДОЙ распознанной фразы.
        Исправленная логика: сначала проверяем на дубль, потом сбрасываем таймер.
        """
        if not self.is_listening:
            return

        processed_text = self._preprocess_text(text)

        if not processed_text:
            return

        if self.full_sentences and self.full_sentences[-1] == processed_text:
            print(f"STT: ДУБЛЬ ПРОПУЩЕН: '{processed_text}'")
            return


        print(f"STT: Распознана новая фраза: '{processed_text}'")
        self.full_sentences.append(processed_text)

        self._start_silence_timer()

        if self.on_phrase_detected:
            self.on_phrase_detected()

    def _start_silence_timer(self):
        """Запускает новый таймер 'длинной' тишины после завершения фразы."""
        self._cancel_silence_timer()
        self.silence_timer = threading.Timer(self.silence_timeout, self._on_silence_timeout)
        self.silence_timer.start()
        print(f"STT: 🕐 Запущен таймер долгой паузы ({self.silence_timeout}с)")

    def _cancel_silence_timer(self):
        """Отменяет текущий таймер 'длинной' тишины."""
        if self.silence_timer:
            self.silence_timer.cancel()
            self.silence_timer = None

    def _on_silence_timeout(self):
        """
        Срабатывает ТОЛЬКО после "длинной" тишины.
        Отправляет накопленные фразы в main.py.
        """
        if not self.is_listening:
            return
            
        if self.full_sentences and self.on_silence_detected:
            sentences_copy = self.full_sentences.copy()
            self.full_sentences.clear()
            print(f"STT: ⏰ Обнаружена длинная тишина. Передаю {len(sentences_copy)} фраз.")
            self.on_silence_detected(sentences_copy)
        

    def _preprocess_text(self, text: str) -> str:
        """Очистка и форматирование распознанного текста."""
        if not text: return ""
        text = text.strip()
        if text.startswith("..."): text = text[3:].strip()
        if text.endswith("..."): text = text[:-3].strip()
        while text and text[0] in '.,?!':
            text = text[1:].strip()
        if text: text = text[0].upper() + text[1:]
        return text