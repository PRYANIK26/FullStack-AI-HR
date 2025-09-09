import threading
import queue
import time
import os
import warnings
from typing import Callable, Optional
from RealtimeTTS import TextToAudioStream, EdgeEngine
from config import Config

_tts_initialized = False

class TTSManager:
    def __init__(self, on_playback_finished: Optional[Callable] = None):
        """
        Инициализация TTS Manager
        on_playback_finished: callback который вызывается когда закончилось воспроизведение
        """
        global _tts_initialized
        
        if _tts_initialized:
            print("Warning: TTS уже инициализирован")
        
        _tts_initialized = True
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            self.engine = EdgeEngine(
                rate=Config.TTS_RATE,
                pitch=Config.TTS_PITCH,
                volume=Config.TTS_VOLUME
            )
            
            self.stream = TextToAudioStream(self.engine)
            self.engine.set_voice(Config.TTS_VOICE)
        
        self.on_playback_finished = on_playback_finished
        self.is_playing = False
        self.text_queue = queue.Queue()
        self.stop_requested = False
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
    def speak_text(self, text: str):
        """Добавить текст в очередь на озвучку"""
        if text.strip():
            self.text_queue.put(text.strip())
    
    def speak_text_blocking(self, text: str):
        """Озвучить текст синхронно (блокирующий вызов)"""
        if not text.strip():
            return
            
        self.is_playing = True
        try:
            def single_text_generator():
                yield text.strip()
            
            self.stream.feed(single_text_generator()).play()
            
        finally:
            self.is_playing = False
            if self.on_playback_finished:
                self.on_playback_finished()
    
    def _worker_loop(self):
        """Основной цикл обработки очереди текстов"""
        while not self.stop_requested:
            try:
                text = self.text_queue.get(timeout=1.0)
                
                if text and not self.stop_requested:
                    self.speak_text_blocking(text)
                    
                self.text_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS Worker Error: {e}")
                if self.on_playback_finished:
                    self.on_playback_finished()
    
    def is_currently_playing(self) -> bool:
        """Проверить, идет ли сейчас воспроизведение"""
        return self.is_playing or self.stream.is_playing()
    
    def stop_playback(self):
        """Остановить текущее воспроизведение"""
        try:
            self.stream.stop()
            while not self.text_queue.empty():
                try:
                    self.text_queue.get_nowait()
                    self.text_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error stopping TTS: {e}")
    
    def pause_playback(self):
        """Приостановить воспроизведение"""
        try:
            self.stream.pause()
        except Exception as e:
            print(f"Error pausing TTS: {e}")
    
    def resume_playback(self):
        """Возобновить воспроизведение"""
        try:
            self.stream.resume()
        except Exception as e:
            print(f"Error resuming TTS: {e}")
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """Ждать завершения всех задач в очереди"""
        start_time = time.time()
        while (not self.text_queue.empty() or self.is_currently_playing()):
            if timeout and (time.time() - start_time) > timeout:
                break
            time.sleep(0.1)
    
    def shutdown(self):
        """Завершить работу TTS Manager"""
        self.stop_requested = True
        self.stop_playback()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
    
    def get_available_voices(self):
        """Получить список доступных голосов"""
        return self.engine.get_voices()
    
    def set_voice(self, voice_name: str):
        """Изменить голос"""
        self.engine.set_voice(voice_name)
    
    def test_speech(self, test_text: str = "Тест системы синтеза речи. Все работает корректно."):
        """Тестовая озвучка"""
        self.speak_text(test_text)