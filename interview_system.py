#!/usr/bin/env python3
"""
Система технического интервью с адаптивными фазами
Интегрирует профилирование кандидата и HR-анализ
"""

import argparse
import signal
import sys
import time
import threading
import json
import sqlite3
import uuid
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime

from config import Config
from openai_client import OpenAIClient
from stt_manager import STTManager
from tts_manager import TTSManager

# Импорт новых компонентов
from interview_prompts import InterviewPrompts
from adaptive_interview_manager import AdaptiveInterviewManager

import requests

class InterviewState(Enum):
    GREETING = "greeting"
    WAITING_NAME = "waiting_name"
    PLANNING = "planning"
    INTERVIEWING = "interviewing"
    COMPLETING = "completing"
    FINISHED = "finished"

class InterviewConfig(Config):
    """Конфигурация для адаптивного интервью"""
    
    # Время интервью
    MAX_INTERVIEW_TIME = 1500  # 25 минут
    MIN_QUESTIONS = 5
    MAX_QUESTIONS = 12
    
    # Приветствие (без GPT)
    INTERVIEW_GREETING = "Добрый день! Меня зовут Анна, я проведу с вами техническое собеседование. Как я могу к вам обращаться?"

class InterviewDBManager:
    """Управление БД для интервью"""
    
    def __init__(self, db_path='hr_analysis.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_interview_tables()
    
    def _create_interview_tables(self):
        cursor = self.conn.cursor()
        
        # Таблица сессий интервью
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interviews (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                candidate_name TEXT NOT NULL,
                vacancy_title TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                duration_seconds INTEGER,
                total_questions INTEGER DEFAULT 0,
                interview_plan TEXT,  -- JSON
                final_scores TEXT,    -- JSON
                final_recommendation TEXT,
                interviewer_notes TEXT,
                phase_breakdown TEXT, -- JSON новое поле
                adaptive_insights TEXT, -- JSON новое поле
                status TEXT DEFAULT 'active',
                FOREIGN KEY (analysis_id) REFERENCES analyses (id)
            )
        ''')
        
        # Таблица вопросов-ответов с расширенными полями
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interview_qa (
                id TEXT PRIMARY KEY,
                interview_id TEXT NOT NULL,
                question_number INTEGER,
                question_area TEXT,
                question_text TEXT NOT NULL,
                question_difficulty TEXT,
                question_phase TEXT,  -- новое поле
                answer_text TEXT,
                answer_duration_seconds INTEGER,
                technical_score INTEGER,
                communication_score INTEGER,
                depth_score INTEGER,
                confidence_score INTEGER,
                practical_experience INTEGER, -- новое поле
                red_flags TEXT,  -- JSON
                strengths_shown TEXT,  -- JSON
                analysis_notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')
        
        self.conn.commit()

    def get_candidate_by_analysis_id(self, analysis_id: str) -> Optional[Dict]:
        """Получить конкретного кандидата по analysis_id"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.id as analysis_id, a.result_json,
                   v.title as vacancy_title, v.industry,
                   c.name as candidate_name, c.resume_content
            FROM analyses a
            JOIN vacancies v ON a.vacancy_id = v.id
            JOIN candidates c ON a.candidate_id = c.id
            WHERE a.id = ?
        ''', (analysis_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_candidates_for_interview(self) -> List[Dict]:
        """Получить кандидатов готовых к интервью (для ручного режима)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.id as analysis_id, a.result_json,
                   v.title as vacancy_title, v.industry,
                   c.name as candidate_name, c.resume_content
            FROM analyses a
            JOIN vacancies v ON a.vacancy_id = v.id
            JOIN candidates c ON a.candidate_id = c.id
            WHERE a.needs_interview = TRUE 
            AND a.id NOT IN (
                SELECT analysis_id FROM interviews WHERE status = 'completed'
            )
            ORDER BY a.created_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]
    
    def start_interview(self, analysis_id: str, candidate_name: str, vacancy_title: str) -> str:
        """Начать новое интервью"""
        interview_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO interviews (id, analysis_id, candidate_name, vacancy_title)
            VALUES (?, ?, ?, ?)
        ''', (interview_id, analysis_id, candidate_name, vacancy_title))
        self.conn.commit()
        return interview_id
    
    def save_qa_pair(self, interview_id: str, qa_data: Dict):
        """Сохранить вопрос-ответ с расширенными полями"""
        qa_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        
        analysis = qa_data.get('previous_answer_analysis', {})
        
        cursor.execute('''
            INSERT INTO interview_qa (
                id, interview_id, question_number, question_area, 
                question_text, question_difficulty, question_phase, answer_text, 
                answer_duration_seconds, technical_score, communication_score,
                depth_score, confidence_score, practical_experience, red_flags, 
                strengths_shown, analysis_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            qa_id, interview_id, qa_data.get('question_number', 0),
            qa_data.get('question_area', ''), qa_data.get('question_text', ''),
            qa_data.get('question_difficulty', ''), qa_data.get('question_phase', ''),
            qa_data.get('answer_text', ''), qa_data.get('answer_duration', 0),
            analysis.get('technical_score', 0), analysis.get('communication_score', 0),
            analysis.get('depth_score', 0), analysis.get('confidence_score', 0),
            analysis.get('practical_experience', 0), json.dumps(analysis.get('red_flags', [])),
            json.dumps(analysis.get('strengths_shown', [])), analysis.get('analysis_notes', '')
        ))
        self.conn.commit()
    
    def complete_interview(self, interview_id: str, final_data: Dict):
        """Завершить интервью с расширенными данными"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE interviews 
            SET end_time = CURRENT_TIMESTAMP, duration_seconds = ?, 
                total_questions = ?, interview_plan = ?, final_scores = ?,
                final_recommendation = ?, interviewer_notes = ?, 
                phase_breakdown = ?, adaptive_insights = ?, status = 'completed'
            WHERE id = ?
        ''', (
            final_data.get('duration_seconds', 0),
            final_data.get('total_questions', 0),
            json.dumps(final_data.get('interview_plan', [])),
            json.dumps(final_data.get('final_scores', {})),
            final_data.get('recommendation', ''),
            final_data.get('notes', ''),
            json.dumps(final_data.get('phase_breakdown', {})),
            json.dumps(final_data.get('adaptive_insights', {})),
            interview_id
        ))
        self.conn.commit()

class InterviewSession:
    """Сессия интервью с интеграцией адаптивного менеджера"""
    
    def __init__(self, candidate_data: Dict, openai_client):
        self.candidate_data = candidate_data
        self.candidate_name = None
        self.start_time = time.time()
        self.question_start_time = None
        
        # Инициализация адаптивного менеджера
        self.adaptive_manager = AdaptiveInterviewManager(candidate_data, openai_client)
        
        # Состояние интервью
        self.last_question = None
        self.last_answer = None
        self.question_number = 0
        
        # Накопленные данные для отчета
        self.all_qa_pairs = []
    
    def get_elapsed_minutes(self) -> int:
        return int((time.time() - self.start_time) / 60)
    
    def should_end_interview(self) -> bool:
        return self.adaptive_manager.should_end_interview(
            InterviewConfig.MAX_INTERVIEW_TIME // 60,
            InterviewConfig.MAX_QUESTIONS
        )
    
    def start_question_timer(self):
        self.question_start_time = time.time()
    
    def get_answer_duration(self) -> int:
        if self.question_start_time:
            return int(time.time() - self.question_start_time)
        return 0
    
    def get_initial_plan_and_question(self, candidate_name: str) -> Dict:
        """Получить начальный план и вопрос через адаптивный менеджер"""
        self.candidate_name = candidate_name
        return self.adaptive_manager.get_initial_plan_and_question(candidate_name)
    
    def process_answer_and_get_next(self, last_question: str, last_answer: str) -> Dict:
        """Обработать ответ и получить следующий вопрос"""
        self.last_question = last_question
        self.last_answer = last_answer
        
        # Используем адаптивный менеджер
        result = self.adaptive_manager.process_answer_and_get_next_question(
            last_question, last_answer
        )
        
        # Сохраняем для отчета
        self.all_qa_pairs.append({
            'question': last_question,
            'answer': last_answer,
            'analysis': result.get('previous_answer_analysis', {}),
            'duration': self.get_answer_duration(),
            'phase': result.get('current_phase', 'unknown')
        })
        
        return result
    
    def get_final_report(self) -> Dict:
        """Получить финальный отчет"""
        return self.adaptive_manager.get_final_report()

# --- 2. Замени конструктор __init__ в классе VoiceInterviewAssistant ---
class VoiceInterviewAssistant:
    def __init__(self, analysis_id: Optional[str] = None, main_server_port: int = 5000):
        self.state = InterviewState.GREETING
        self.openai_client = OpenAIClient()
        self.db_manager = InterviewDBManager()
        self.tts_manager = TTSManager(on_playback_finished=self._on_tts_finished)
        self.stt_manager = STTManager(on_phrase_detected=self._on_phrase_detected, on_silence_detected=self._on_silence_detected)
        self.session = None
        self.interview_id = None
        self.is_running = False
        self.is_completing = False
        self.processing_lock = threading.Lock()
        self.start_analysis_id = analysis_id
        self.main_server_port = main_server_port # <-- ДОБАВЛЕНО

    def start(self):
        """Запуск интервью"""
        print("🎙️ Запуск системы адаптивного технического интервью...")
        if not InterviewConfig.OPENAI_API_KEY:
            print("❌ OpenAI API ключ не найден")
            return

        selected_candidate = None
        if self.start_analysis_id:
            print(f"▶️ Автоматический запуск для analysis_id: {self.start_analysis_id}")
            selected_candidate = self.db_manager.get_candidate_by_analysis_id(self.start_analysis_id)
            if not selected_candidate:
                print(f"❌ Кандидат с analysis_id '{self.start_analysis_id}' не найден.")
                return
        else:
            # Ручной режим выбора, если ID не передан
            print("👤 Ручной режим запуска. Выберите кандидата из списка:")
            candidates = self.db_manager.get_candidates_for_interview()
            if not candidates:
                print("❌ Нет кандидатов, готовых к интервью.")
                return
            
            print("\n📋 Кандидаты готовые к интервью:")
            for i, candidate in enumerate(candidates):
                print(f"{i+1}. {candidate['candidate_name']} - {candidate['vacancy_title']}")
            
            try:
                choice = int(input("\n👉 Выберите кандидата (номер): ")) - 1
                if 0 <= choice < len(candidates):
                    selected_candidate = candidates[choice]
                else:
                    print("❌ Неверный выбор.")
                    return
            except (ValueError, KeyboardInterrupt):
                print("\n❌ Отмена.")
                return
        
        # Инициализация сессии
        self.session = InterviewSession(selected_candidate, self.openai_client)
        self.interview_id = self.db_manager.start_interview(
            selected_candidate['analysis_id'],
            selected_candidate['candidate_name'],
            selected_candidate['vacancy_title']
        )
        
        print(f"\n✅ Начинаю адаптивное интервью с {selected_candidate['candidate_name']}")
        print(f"📋 Вакансия: {selected_candidate['vacancy_title']}")
        print(f"⏱️ Максимальное время: {InterviewConfig.MAX_INTERVIEW_TIME//60} минут")
        print("🎤 Говорите после сигнала бота...")
        
        self.is_running = True
        self._change_state(InterviewState.GREETING)
        self._start_greeting()
        
        try:
            while self.is_running:
                time.sleep(0.5)
                if self.session and self.session.should_end_interview():
                    self._complete_interview()
        except KeyboardInterrupt:
            pass 
        finally:
            self.shutdown()

# --- 3. Замени функцию shutdown в классе VoiceInterviewAssistant ---
    def shutdown(self):
        """Корректное завершение работы с отправкой вебхука на очистку."""
        if self.is_running:
             if self.session and not self.is_completing:
                self._complete_interview(is_shutdown=True)

        print("\n🛑 Завершение работы...")
        self.is_running = False
        
        self.stt_manager.stop_listening()
        self.tts_manager.shutdown()
        
        # --- НОВЫЙ БЛОК: ОТПРАВКА ВЕБХУКА НА ОЧИСТКУ ---
        try:
            cleanup_url = f"http://localhost:{self.main_server_port}/webhook/cleanup"
            payload = {"analysis_id": self.start_analysis_id}
            print(f"Отправка сигнала очистки на {cleanup_url}...")
            requests.post(cleanup_url, json=payload, timeout=5)
            print("Сигнал очистки успешно отправлен.")
        except requests.exceptions.RequestException as e:
            print(f"ОШИБКА: Не удалось отправить сигнал очистки: {e}")
        # -----------------------------------------------

        print("✅ Система остановлена.")
    
    def _change_state(self, new_state: InterviewState):
        """Смена состояния с выводом"""
        if self.state != new_state:
            print(f"🔌 {self.state.value} → {new_state.value}")
            self.state = new_state
    
    def _start_greeting(self):
        """Приветствие (простое, без GPT)"""
        greeting = InterviewConfig.INTERVIEW_GREETING
        print(f"🤖 Анна: {greeting}")
        self.tts_manager.speak_text(greeting)
        self._change_state(InterviewState.WAITING_NAME)
    
    def _on_phrase_detected(self):
        """Обработка фразы"""
        pass
    
    def _on_silence_detected(self, sentences: List[str]):
        """Обработка тишины - получен ответ"""
        if not self.is_running:
            return
        
        self.stt_manager.stop_listening()
        
        user_message = " ".join(sentences).strip()
        if not user_message:
            self._restart_listening()
            return
        
        print(f"👤 Кандидат: {user_message}")
        
        threading.Thread(
            target=self._process_candidate_response,
            args=(user_message,),
            daemon=True
        ).start()
    
    def _process_candidate_response(self, response: str):
        """Обработка ответа кандидата"""
        with self.processing_lock:
            try:
                if self.state == InterviewState.WAITING_NAME:
                    self._process_name_and_start_interview(response)
                elif self.state == InterviewState.INTERVIEWING:
                    self._process_interview_answer(response)
            except Exception as e:
                print(f"❌ Ошибка обработки: {e}")
                self._restart_listening()
    
    def _process_name_and_start_interview(self, response: str):
        """Получили ответ с именем - извлекаем через GPT"""
        print("🧠 Извлекаю имя кандидата...")
        
        name_prompt = InterviewPrompts.NAME_EXTRACTION_PROMPT.format(response=response)
        
        try:
            messages = [{"role": "user", "content": name_prompt}]
            gpt_response = self.openai_client.get_response_sync(messages)
            extracted_name = gpt_response.strip().split()[0] if gpt_response.strip() else "Кандидат"
            candidate_name = extracted_name.title()
        except Exception as e:
            print(f"❌ Ошибка извлечения имени: {e}")
            name_words = response.strip().split()
            candidate_name = name_words[0].title() if name_words else "Кандидат"
        
        print(f"📝 Имя кандидата: {candidate_name}")
        self._change_state(InterviewState.PLANNING)
        self._get_interview_plan_and_first_question(candidate_name)
    
    def _get_interview_plan_and_first_question(self, candidate_name: str):
        """Получить план интервью и первый вопрос через адаптивный менеджер"""
        print("🧠 Составляю адаптивный план интервью...")
        
        try:
            gpt_response = self.session.get_initial_plan_and_question(candidate_name)
            
            if gpt_response:
                interview_plan = gpt_response.get('interview_plan', [])
                print(f"📋 Адаптивный план: {', '.join(interview_plan)}")
                question = gpt_response.get('next_question', 'Расскажите немного о себе и вашем опыте.')
                print(f"🤖 Анна: {question}")
                
                self.session.last_question = question
                self.session.question_number += 1
                self.session.start_question_timer()
                
                self.tts_manager.speak_text(question)
                self._change_state(InterviewState.INTERVIEWING)
            else:
                raise Exception("Не удалось получить план интервью")
                
        except Exception as e:
            print(f"❌ Ошибка планирования: {e}")
            fallback_question = f"Здорово, {candidate_name}! Расскажите, пожалуйста, о своем последнем проекте."
            print(f"🤖 Анна: {fallback_question}")
            self.tts_manager.speak_text(fallback_question)
            self.session.last_question = fallback_question
            self._change_state(InterviewState.INTERVIEWING)
    
    def _process_interview_answer(self, answer: str):
        """Обработка технического ответа"""
        print("🧠 Анализирую ответ и готовлю адаптивный следующий вопрос...")
        
        try:
            gpt_response = self.session.process_answer_and_get_next(self.session.last_question, answer)
            
            if gpt_response:
                self._continue_interview_with_result(gpt_response)
            else:
                print("❌ Ошибка анализа, завершаю интервью")
                self._complete_interview()
                
        except Exception as e:
            print(f"❌ Ошибка обработки ответа: {e}")
            self._complete_interview()
    
    def _continue_interview_with_result(self, gpt_response: Dict):
        """Продолжение интервью с результатом от адаптивного менеджера"""
        if self.session.last_answer:
            analysis = gpt_response.get('previous_answer_analysis', {})
            qa_data = {
                'question_number': self.session.question_number - 1,
                'question_area': gpt_response.get('question_area', ''),
                'question_text': self.session.last_question,
                'question_difficulty': gpt_response.get('question_difficulty', 'medium'),
                'question_phase': gpt_response.get('current_phase', 'unknown'),
                'answer_text': self.session.last_answer,
                'answer_duration': self.session.get_answer_duration(),
                'previous_answer_analysis': analysis
            }
            self.db_manager.save_qa_pair(self.interview_id, qa_data)
            
            tech_score = analysis.get('technical_score', 0)
            comm_score = analysis.get('communication_score', 0)
            phase = gpt_response.get('current_phase', 'unknown')
            print(f"📊 Оценка: Техника {tech_score}/10, Коммуникация {comm_score}/10 | Фаза: {phase}")
        
        interview_status = gpt_response.get('interview_status', 'continuing')
        time_management = gpt_response.get('time_management', 'continue')
        
        if interview_status == 'finished' or time_management == 'finish':
            self._complete_interview()
            return
        
        next_question = gpt_response.get('next_question')
        if next_question:
            print(f"🤖 Анна: {next_question}")
            self.session.last_question = next_question
            self.session.question_number += 1
            self.session.start_question_timer()
            self.tts_manager.speak_text(next_question)
        else:
            self._complete_interview()
    
    def _complete_interview(self, is_shutdown=False):
        """Завершение интервью с адаптивным отчетом"""
        if self.is_completing: return
        self.is_completing = True
        self._change_state(InterviewState.COMPLETING)
        
        print("\n📊 Завершаю интервью и составляю адаптивный отчет...")
        final_report = self.session.get_final_report()
        duration = int(time.time() - self.session.start_time)
        final_data = {
            'duration_seconds': duration, 'total_questions': self.session.question_number,
            'interview_plan': final_report.get('interview_stats', {}).get('areas_covered', []),
            'final_scores': final_report.get('final_scores', {}),
            'recommendation': final_report.get('final_recommendation', {}).get('decision', 'unknown'),
            'notes': f"Адаптивное интервью. Фазы: {list(final_report.get('phase_breakdown', {}).keys())}",
            'phase_breakdown': final_report.get('phase_breakdown', {}),
            'adaptive_insights': final_report.get('adaptive_insights', {})
        }
        self.db_manager.complete_interview(self.interview_id, final_data)
        
        candidate_name = final_report.get('candidate_name', 'Кандидат')
        closing_message = f"Спасибо за интервью, {candidate_name}! Мы обсудили {self.session.question_number} вопросов за {duration//60} минут. Результаты будут переданы HR-менеджеру в течение дня."
        
        print(f"🤖 Анна: {closing_message}")
        if not is_shutdown:
            self.tts_manager.speak_text(closing_message)
            wait_time = len(closing_message) * 0.1 
            time.sleep(wait_time) 
        
        self._print_detailed_report(final_report, duration)
        
        self._change_state(InterviewState.FINISHED)
        self.is_running = False
    
    def _print_detailed_report(self, final_report: Dict, duration: int):
        """Вывод детального отчета"""
        print(f"\n" + "="*60)
        print(f"📋 ОТЧЕТ ПО АДАПТИВНОМУ ТЕХНИЧЕСКОМУ ИНТЕРВЬЮ")
        print(f"="*60)
        print(f"👤 Кандидат: {final_report.get('candidate_name', 'N/A')}")
        print(f"💼 Вакансия: {self.session.candidate_data.get('vacancy_title', 'N/A')}")
        print(f"⏱️ Длительность: {duration//60}м {duration%60}с")
        print(f"❓ Вопросов: {self.session.question_number}")
        scores = final_report.get('final_scores', {})
        print(f"📊 Общая оценка: {scores.get('overall_score', 0)}/100")
        print(f"🔧 Технические навыки: {scores.get('technical_avg', 0):.1f}/10")
        print(f"💬 Коммуникация: {scores.get('communication_avg', 0):.1f}/10")
        recommendation = final_report.get('final_recommendation', {})
        print(f"💡 Решение: {recommendation.get('decision_text', 'N/A')}")
        print(f"🎯 Уровень: {final_report.get('final_level', 'N/A')}")
        phase_breakdown = final_report.get('phase_breakdown', {})
        if phase_breakdown:
            print(f"\n📈 Разбивка по фазам:")
            for phase, stats in phase_breakdown.items():
                print(f"  • {phase}: {stats.get('questions_asked', 0)} вопросов, ср.оценка {stats.get('avg_score', 0):.1f}")
        strengths = final_report.get('strengths_confirmed', [])
        if strengths: print(f"💪 Подтвержденные сильные стороны: {', '.join(strengths[:3])}")
        red_flags = final_report.get('red_flags', [])
        if red_flags: print(f"🚩 Красные флаги: {', '.join(set(red_flags))}")
        insights = final_report.get('adaptive_insights', {})
        if insights:
            print(f"🤖 Адаптивные инсайты:")
            print(f"  • Финальная сложность: {insights.get('final_difficulty', 'N/A')}")
            print(f"  • Переходов между фазами: {insights.get('phase_transitions', 0)}")
            print(f"  • HR-concerns проверены: {'Да' if insights.get('hr_concerns_addressed') else 'Нет'}")
        print(f"📝 ID интервью: {self.interview_id}")
        print(f"="*60)
    
    def _on_tts_finished(self):
        """Обработка завершения речи"""
        if self.is_running and self.state in [InterviewState.WAITING_NAME, InterviewState.INTERVIEWING]:
            threading.Timer(1.5, self._restart_listening).start()
    
    def _restart_listening(self):
        """Перезапуск прослушивания"""
        if self.is_running:
            self.stt_manager.start_listening()

# --- 4. Замени функцию main в самом конце файла ---
def main():
    """Главная функция для запуска интервью."""
    parser = argparse.ArgumentParser(description="Система адаптивного технического интервью")
    parser.add_argument("--analysis-id", type=str, help="ID анализа для автоматического запуска интервью")
    parser.add_argument("--port", type=int, default=5000, help="Порт локального main_server для обратного вызова")
    args = parser.parse_args()
    
    assistant = VoiceInterviewAssistant(analysis_id=args.analysis_id, main_server_port=args.port)
    
    def signal_handler(sig, frame):
        print("\nПолучен сигнал завершения, начинаю остановку...")
        assistant.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        assistant.start()
    except Exception as e:
        print(f"\nКритическая ошибка в главном потоке: {e}")
    finally:
        # Убедимся, что shutdown вызовется в любом случае
        if not assistant.is_completing:
            assistant.shutdown()

if __name__ == "__main__":
    main()