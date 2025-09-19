import openai
import time
import threading
import logging
from datetime import datetime
from typing import List, Dict, Callable, Generator
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        
    def get_response_sync(self, messages: List[Dict[str, str]]) -> str:
        """Синхронный запрос - получаем полный ответ сразу"""
        request_id = int(time.time() * 1000000) % 1000000
        
        print(f"🚀 [REQ-{request_id}] Отправка синхронного запроса к OpenAI")
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            content = response.choices[0].message.content.strip()
            
            print(f"✅ [REQ-{request_id}] Получен ответ за {response_time:.0f}мс (длина: {len(content)} символов)")
            
            return content
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            logger.error(f"❌ [REQ-{request_id}] Ошибка через {response_time:.0f}мс: {e}")
            raise Exception(f"OpenAI API Error: {e}")
    
    def get_response_stream(self, messages: List[Dict[str, str]], 
                          sentence_callback: Callable[[str], None]) -> str:
        """
        Потоковый запрос - собираем чанки в предложения и отправляем их через callback
        Возвращает полный текст ответа
        """
        request_id = int(time.time() * 1000000) % 1000000
        
        logger.info(f"🌊 [STREAM-{request_id}] Начало потокового запроса к OpenAI")
        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                reasoning_effort="minimal",
                stream=True
            )
            
            full_response = ""
            current_sentence = ""
            sentence_count = 0
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    current_time = time.time()
                    
                    if first_chunk_time is None:
                        first_chunk_time = current_time
                        time_to_first_chunk = (first_chunk_time - start_time) * 1000
                        logger.info(f"⚡ [STREAM-{request_id}] Первый чанк через {time_to_first_chunk:.0f}мс")
                    
                    chunk_text = chunk.choices[0].delta.content
                    full_response += chunk_text
                    current_sentence += chunk_text
                    chunk_count += 1
                    
                    if self._is_sentence_complete(current_sentence):
                        sentence = current_sentence.strip()
                        if len(sentence) >= Config.MIN_SENTENCE_LENGTH:
                            sentence_count += 1
                            chunk_time = (current_time - start_time) * 1000
                            logger.info(f"📦 [STREAM-{request_id}] Предложение #{sentence_count} готово через {chunk_time:.0f}мс: '{sentence[:50]}...' (длина: {len(sentence)})")
                            sentence_callback(sentence)
                        current_sentence = ""
            
            if current_sentence.strip():
                sentence = current_sentence.strip()
                if len(sentence) >= Config.MIN_SENTENCE_LENGTH:
                    sentence_count += 1
                    logger.info(f"📦 [STREAM-{request_id}] Финальное предложение #{sentence_count}: '{sentence[:50]}...' (длина: {len(sentence)})")
                    sentence_callback(sentence)
                elif sentence:
                    sentence_count += 1
                    logger.info(f"📦 [STREAM-{request_id}] Короткий финальный фрагмент #{sentence_count}: '{sentence}' (длина: {len(sentence)})")
                    sentence_callback(sentence)
            
            end_time = time.time()
            total_time = (end_time - start_time) * 1000
            
            logger.info(f"🏁 [STREAM-{request_id}] Поток завершен за {total_time:.0f}мс | "
                       f"Чанков: {chunk_count} | Предложений: {sentence_count} | "
                       f"Символов: {len(full_response)}")
                    
            return full_response.strip()
            
        except Exception as e:
            end_time = time.time()
            total_time = (end_time - start_time) * 1000
            logger.error(f"❌ [STREAM-{request_id}] Ошибка потока через {total_time:.0f}мс: {e}")
            raise Exception(f"OpenAI Streaming Error: {e}")
    
    def get_response_stream_with_timeout(self, messages: List[Dict[str, str]], 
                                       sentence_callback: Callable[[str], None]) -> str:
        """
        Потоковый запрос с таймаутом - если долго нет новых чанков, 
        отправляем накопленное предложение
        """
        request_id = int(time.time() * 1000000) % 1000000
        
        logger.info(f"⏰ [TIMEOUT-{request_id}] Начало потокового запроса с таймаутом к OpenAI")
        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0
        timeout_triggers = 0
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                reasoning_effort="minimal",
                stream=True
            )
            
            full_response = ""
            current_sentence = ""
            last_chunk_time = time.time()
            sentence_count = 0
            
            def timeout_sender():
                nonlocal current_sentence, timeout_triggers
                while True:
                    time.sleep(0.1)
                    current_time = time.time()
                    if current_sentence and current_time - last_chunk_time > Config.MAX_CHUNK_WAIT_TIME:
                        timeout_triggers += 1
                        wait_time = (current_time - last_chunk_time) * 1000
                        sentence = current_sentence.strip()
                        if sentence:
                            logger.info(f"⏱️ [TIMEOUT-{request_id}] Таймаут #{timeout_triggers} через {wait_time:.0f}мс: '{sentence[:50]}...'")
                            sentence_callback(sentence)
                        current_sentence = ""
                        break
            
            timeout_thread = None
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    current_time = time.time()
                    
                    if first_chunk_time is None:
                        first_chunk_time = current_time
                        time_to_first_chunk = (first_chunk_time - start_time) * 1000
                        logger.info(f"⚡ [TIMEOUT-{request_id}] Первый чанк через {time_to_first_chunk:.0f}мс")
                    
                    chunk_text = chunk.choices[0].delta.content
                    full_response += chunk_text
                    current_sentence += chunk_text
                    last_chunk_time = current_time
                    chunk_count += 1
                    
                    if timeout_thread is None:
                        timeout_thread = threading.Thread(target=timeout_sender, daemon=True)
                        timeout_thread.start()
                    
                    if self._is_sentence_complete(current_sentence):
                        sentence = current_sentence.strip()
                        if len(sentence) >= Config.MIN_SENTENCE_LENGTH:
                            sentence_count += 1
                            chunk_time = (current_time - start_time) * 1000
                            logger.info(f"📦 [TIMEOUT-{request_id}] Предложение #{sentence_count} готово через {chunk_time:.0f}мс: '{sentence[:50]}...' (длина: {len(sentence)})")
                            sentence_callback(sentence)
                        current_sentence = ""
                        if timeout_thread and timeout_thread.is_alive():
                            timeout_thread = threading.Thread(target=timeout_sender, daemon=True)
                            timeout_thread.start()
            
            if current_sentence.strip():
                sentence = current_sentence.strip()
                if sentence:
                    sentence_count += 1
                    logger.info(f"📦 [TIMEOUT-{request_id}] Финальный фрагмент #{sentence_count}: '{sentence[:50]}...'")
                    sentence_callback(sentence)
            
            end_time = time.time()
            total_time = (end_time - start_time) * 1000
            
            logger.info(f"🏁 [TIMEOUT-{request_id}] Поток с таймаутом завершен за {total_time:.0f}мс | "
                       f"Чанков: {chunk_count} | Предложений: {sentence_count} | "
                       f"Таймаутов: {timeout_triggers} | Символов: {len(full_response)}")
                    
            return full_response.strip()
            
        except Exception as e:
            end_time = time.time()
            total_time = (end_time - start_time) * 1000
            logger.error(f"❌ [TIMEOUT-{request_id}] Ошибка потока с таймаутом через {total_time:.0f}мс: {e}")
            raise Exception(f"OpenAI Streaming with Timeout Error: {e}")
    
    def _is_sentence_complete(self, text: str) -> bool:
        """Проверить, закончено ли предложение"""
        text = text.strip()
        if not text:
            return False
            
        for ending in Config.SENTENCE_ENDINGS:
            if text.endswith(ending):
                return True
                
        return False