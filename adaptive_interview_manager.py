#!/usr/bin/env python3
"""
Улучшенный адаптивный менеджер интервью
- Передача полной истории Q&A в GPT
- Детекция повторов и зацикливания  
- Умный тайм-менеджмент с расчетом времени
- Альтернативные стратегии адаптации
"""

import json
import time
import re
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, Counter

from interview_prompts import InterviewPrompts
from candidate_profiler import CandidateProfiler
from config import AdaptiveInterviewConfig

class InterviewPhase(Enum):
    """Фазы адаптивного интервью"""
    EXPLORATION = "exploration"
    VALIDATION = "validation"
    STRESS_TEST = "stress_test"
    SOFT_SKILLS = "soft_skills"
    WRAP_UP = "wrap_up"
    FINISHED = "finished"

@dataclass
class QuestionRecord:
    """Запись о заданном вопросе для детекции повторов"""
    question_text: str
    topic_area: str
    keywords: Set[str]
    phase: str
    timestamp: float
    difficulty: str
    
@dataclass
class PhaseStats:
    """Расширенная статистика по фазе"""
    questions_asked: int = 0
    avg_score: float = 0.0
    start_time: float = 0.0
    difficulties_used: List[str] = field(default_factory=list)
    topics_covered: List[str] = field(default_factory=list)
    weak_answers_count: int = 0
    strong_answers_count: int = 0
    
class TimeManager:
    """Улучшенный менеджер времени, работающий с конфигом."""
    
    def __init__(self, max_interview_minutes: int):
        self.max_interview_minutes = max_interview_minutes
        self.start_time = time.time()
        self.phase_configs = AdaptiveInterviewConfig.PHASE_SETTINGS

    def get_elapsed_minutes(self) -> int:
        return int((time.time() - self.start_time) / 60)

    def get_remaining_minutes(self) -> int:
        elapsed = self.get_elapsed_minutes()
        remaining = self.max_interview_minutes - elapsed
        return max(0, remaining)

    def get_time_status(self) -> str:
        remaining = self.get_remaining_minutes()
        if remaining < 3:
            return "critical_time"
        elif remaining < 7:
            return "need_wrap_up"
        elif remaining < 12:
            return "need_acceleration"
        else:
            return "on_track"

    def should_end_interview(self) -> bool:
        return self.get_remaining_minutes() <= 0

    def get_time_strategy_text_for_phase(self, phase_name: str, phase_history: List[Dict]) -> str:
        """
        Генерирует текстовую стратегию по времени для текущей фазы,
        основываясь на конфиге и реальном времени.
        """
        remaining_minutes = self.get_remaining_minutes()
        
        time_spent_on_other_phases = sum(p['duration'] / 60 for p in phase_history)
        
        current_phase_index = list(self.phase_configs.keys()).index(phase_name)
        planned_remaining_time = sum(
            config['target_duration_minutes'] 
            for phase, config in self.phase_configs.items() 
            if list(self.phase_configs.keys()).index(phase) >= current_phase_index
        )

        time_pressure_ratio = remaining_minutes / max(planned_remaining_time, 1)

        if time_pressure_ratio < 0.5:
            return "КРИТИЧЕСКАЯ НЕХВАТКА ВРЕМЕНИ! Задай 1-2 самых важных вопроса и переходи к следующей фазе."
        elif time_pressure_ratio < 0.8:
            return "Нужно ускориться. Сфокусируйся на ключевых вопросах, избегай углублений."
        elif time_pressure_ratio > 1.2:
            return "Времени достаточно. Можно углубиться в детали или задать дополнительные вопросы."
        else:
            return "Идем по графику. Следуй стандартному плану фазы."

class RepetitionDetector:
    """Детектор повторов и зацикливания"""
    
    def __init__(self):
        self.question_history: List[QuestionRecord] = []
        self.topic_frequency = Counter()
        self.failed_topics: Set[str] = set()
        
    def add_question(self, question: str, topic: str, phase: str, difficulty: str):
        """Добавить вопрос в историю"""
        keywords = self._extract_keywords(question)
        
        record = QuestionRecord(
            question_text=question,
            topic_area=topic,
            keywords=keywords,
            phase=phase,
            timestamp=time.time(),
            difficulty=difficulty
        )
        
        self.question_history.append(record)
        self.topic_frequency[topic] += 1
        
    def mark_topic_as_failed(self, topic: str):
        """Отметить тему как неудачную для кандидата"""
        self.failed_topics.add(topic)
        
    def is_repetitive(self, proposed_question: str, proposed_topic: str) -> bool:
        """Проверить, является ли предлагаемый вопрос повтором"""
        
        if self.topic_frequency[proposed_topic] >= 3:
            return True
            
        proposed_keywords = self._extract_keywords(proposed_question)
        
        for record in self.question_history[-3:]:
            common_keywords = proposed_keywords & record.keywords
            if len(common_keywords) >= 2 and len(proposed_keywords) > 0:
                similarity_ratio = len(common_keywords) / len(proposed_keywords)
                if similarity_ratio > 0.6:
                    return True
                    
        return False
    
    def should_avoid_topic(self, topic: str) -> bool:
        """Стоит ли избегать эту тему"""
        return (
            topic in self.failed_topics or 
            self.topic_frequency[topic] >= 2
        )
    
    def get_alternative_topics(self, current_topic: str, available_topics: List[str]) -> List[str]:
        """Получить альтернативные темы"""
        alternatives = []
        
        for topic in available_topics:
            if topic != current_topic and not self.should_avoid_topic(topic):
                alternatives.append(topic)
                
        alternatives.sort(key=lambda t: self.topic_frequency[t])
        
        return alternatives
    
    def _extract_keywords(self, question: str) -> Set[str]:
        """Извлечь ключевые слова из вопроса"""
        stop_words = {'как', 'что', 'где', 'когда', 'почему', 'который', 'которая', 
                     'это', 'для', 'или', 'если', 'можете', 'можно', 'ли', 'вы', 'ваш', 'ваша'}
        
        words = re.findall(r'\b[а-яёa-z]+\b', question.lower())
        keywords = {word for word in words if len(word) > 3 and word not in stop_words}
        
        return keywords
    
    def get_repetition_analysis(self) -> Dict:
        """Получить анализ повторов для GPT"""
        covered_topics = list(self.topic_frequency.keys())
        recent_topics = [record.topic_area for record in self.question_history[-3:]]
        
        return {
            "covered_topics": covered_topics,
            "recent_topics": recent_topics,
            "failed_topics": list(self.failed_topics),
            "topic_frequency": dict(self.topic_frequency),
            "questions_count": len(self.question_history)
        }

class StrategyAdaptor:
    """Адаптер стратегий интервью"""
    
    def __init__(self):
        self.failed_strategies: Set[str] = set()
        self.successful_strategies: Set[str] = set()
        self.current_strategy = "standard"
        
    def adapt_to_weak_answer(self, topic: str, score: int) -> str:
        """Адаптация стратегии при слабом ответе"""
        
        if score <= 3:
            if self.current_strategy != "simplify":
                self.current_strategy = "simplify"
                return "simplify_and_support"
        elif score <= 5:
            if self.current_strategy != "alternative_angle":
                self.current_strategy = "alternative_angle" 
                return "try_alternative_angle"
                
        return "continue_current"
    
    def adapt_to_strong_answer(self, topic: str, score: int) -> str:
        """Адаптация при сильном ответе"""
        
        if score >= 8:
            self.successful_strategies.add(topic)
            if self.current_strategy != "deepen":
                self.current_strategy = "deepen"
                return "deepen_or_move_to_harder"
                
        return "continue_current"
        
    def get_alternative_approach(self, topic: str, current_difficulty: str) -> Dict:
        """Получить альтернативный подход"""
        
        approaches = {
            "simplify_and_support": {
                "difficulty": "easy",
                "approach": "Переходи к базовым вопросам, поддерживай кандидата",
                "question_style": "Практические примеры вместо теории"
            },
            "try_alternative_angle": {
                "difficulty": "medium", 
                "approach": "Подойди к теме с другой стороны",
                "question_style": "Связь с реальным опытом кандидата"
            },
            "deepen_or_move_to_harder": {
                "difficulty": "hard",
                "approach": "Углубись или перейди к более сложным задачам",
                "question_style": "Архитектурные или алгоритмические задачи"
            },
            "switch_topic": {
                "difficulty": current_difficulty,
                "approach": "Полностью смени тему на более знакомую кандидату",
                "question_style": "Найди сильные стороны кандидата"
            }
        }
        
        return approaches.get(self.current_strategy, approaches["simplify_and_support"])

class AdaptiveInterviewManager:
    """Улучшенный менеджер адаптивного интервью"""
    
    def __init__(self, candidate_data: Dict, openai_client):
        self.candidate_data = candidate_data
        self.openai_client = openai_client
        
        self.profiler = CandidateProfiler(candidate_data)
        self.time_manager = TimeManager(AdaptiveInterviewConfig.MAX_INTERVIEW_TIME_MINUTES)
        self.repetition_detector = RepetitionDetector()
        self.strategy_adaptor = StrategyAdaptor()
        
        self.current_phase = InterviewPhase.EXPLORATION
        self.phase_history = []
        self.phase_stats = {phase: PhaseStats() for phase in InterviewPhase}
        
        self.interview_plan = []
        self.covered_areas = []
        self.total_questions = 0
        
        self.current_difficulty = "medium"
        self.consecutive_weak_answers = 0
        self.consecutive_strong_answers = 0
        
        self.qa_history = []
        self.detailed_qa_history = []
        
    def get_initial_plan_and_question(self, candidate_name: str) -> Dict:
        """Создание начального плана с тайм-менеджментом"""
        
        self.current_phase = InterviewPhase.EXPLORATION
        self.phase_stats[self.current_phase].start_time = time.time()
        self.profiler.profile.name = candidate_name
        
        self.interview_plan = self._create_adaptive_plan()
        
        context = self._build_enhanced_context_for_gpt()
        prompt = InterviewPrompts.INITIAL_PLANNING_PROMPT
        
        try:
            messages = [{"role": "user", "content": prompt.format(**context)}]
            response = self.openai_client.get_response_sync(messages)
            gpt_response = self._parse_gpt_response(response)
            
            if gpt_response:
                self._update_interview_state(gpt_response)
                return gpt_response
            else:
                return self._create_fallback_response("exploration")
                
        except Exception as e:
            print(f"Ошибка получения плана: {e}")
            return self._create_fallback_response("exploration")
    
    def process_answer_and_get_next_question(self, last_question: str, last_answer: str) -> Dict:
        """Улучшенная обработка с детекцией повторов и адаптацией"""
        
        self._add_to_qa_history(last_question, last_answer)
        
        current_phase_name = self.current_phase.value
        prompt = InterviewPrompts.get_prompt_for_phase(current_phase_name)
        
        context = self._build_enhanced_context_for_gpt()
        safe_last_answer = last_answer.replace('{', '{{').replace('}', '}}')
        context.update({
            'last_question': last_question,
            'last_answer': safe_last_answer
        })
        
        messages = [{"role": "user", "content": prompt.format(**context)}]
        response = self.openai_client.get_response_sync(messages)
        gpt_response = self._parse_gpt_response(response)
        
        if gpt_response:
            
            self.detailed_qa_history.append({
                    'question': last_question,
                    'answer': last_answer,
                    'analysis': gpt_response.get('previous_answer_analysis', {})
                })
            
            next_question = gpt_response.get('next_question', '')
            question_area = gpt_response.get('question_area', 'general')
            
            if self._is_repetitive_response(gpt_response):
                print("🔄 Детектирован повтор, запрашиваю альтернативу...")
                gpt_response = self._get_alternative_question(context, current_phase_name)
            
            self._update_candidate_profile(gpt_response)
            self._apply_enhanced_adaptive_logic(gpt_response)
            self._update_interview_state(gpt_response)
            
            return gpt_response
        else:
            return self._create_fallback_response(current_phase_name)
                
    
    def _add_to_qa_history(self, question: str, answer: str):
        """Добавить Q&A в историю"""
        self.qa_history.append({
            'question': question,
            'answer': answer,
            'phase': self.current_phase.value,
            'timestamp': time.time(),
            'question_number': len(self.qa_history) + 1
        })
    
    def _build_enhanced_context_for_gpt(self) -> Dict:
        """Расширенный контекст с историей Q&A и тайм-менеджментом"""
        
        context = {
            'candidate_name': self.profiler.profile.name,
            'vacancy_title': self.candidate_data.get('vacancy_title', ''),
            'industry': self.candidate_data.get('industry', ''),
            'hr_strengths': ', '.join(self.profiler.profile.hr_strengths[:3]) if self.profiler.profile.hr_strengths else 'Не указаны',
            'hr_concerns': ', '.join(self.profiler.profile.hr_concerns[:3]) if self.profiler.profile.hr_concerns else 'Не указаны',
        }
        
        context.update({
            'max_interview_minutes': self.time_manager.max_interview_minutes,
            'elapsed_minutes': self.time_manager.get_elapsed_minutes(),
            'remaining_minutes': self.time_manager.get_remaining_minutes(),
            'time_status': self.time_manager.get_time_status(),
            'time_strategy_text': self.time_manager.get_time_strategy_text_for_phase(
                self.current_phase.value, self.phase_history
            )
        })
        
        qa_history_text = self._format_qa_history_for_gpt()
        context.update({
            'qa_history': qa_history_text,
            'questions_count': len(self.qa_history),
            'total_questions': self.total_questions,
        })
        
        repetition_analysis = self.repetition_detector.get_repetition_analysis()
        context.update({
            'covered_topics': ', '.join(repetition_analysis['covered_topics']),
            'covered_areas': ', '.join(self.covered_areas),
            'interview_plan': ', '.join(self.interview_plan),
        })
        
        profile_context = self.profiler.get_context_for_prompt()
        context.update(profile_context)
        
        context.update({
            'strong_areas': ', '.join(self.profiler.profile.confirmed_strengths[:3]),
            'confirmed_strong_areas': ', '.join(self.profiler.profile.confirmed_strengths),
            'technical_summary': f"Уровень: {self.profiler.profile.technical_level}, Ср.оценка: {self.profiler.profile.avg_technical_score:.1f}",
            'overall_assessment': f"Техуровень: {self.profiler.profile.technical_level}, Вопросов: {self.total_questions}"
        })
        
        if self.current_phase == InterviewPhase.SOFT_SKILLS:
            remaining = self.time_manager.get_remaining_minutes()
            priority_questions = InterviewPrompts.get_priority_questions_for_time(remaining, 'soft_skills')
            context['time_priority_questions'] = ', '.join(priority_questions)
        
        return context
    
    def _format_qa_history_for_gpt(self) -> str:
        """Форматирование истории Q&A для GPT"""
        if not self.qa_history:
            return "История пуста - это первый вопрос"
            
        formatted_history = []
        
        recent_qa = self.qa_history[-6:] if len(self.qa_history) > 6 else self.qa_history
        
        for i, qa in enumerate(recent_qa, 1):
            formatted_history.append(
                f"Q{i} ({qa['phase']}): {qa['question']}\n"
                f"A{i}: {qa['answer'][:200]}{'...' if len(qa['answer']) > 200 else ''}\n"
            )
        
        return "\n".join(formatted_history)
    
    def _is_repetitive_response(self, gpt_response: Dict) -> bool:
        """Проверить, является ли ответ GPT повтором"""
        next_question = gpt_response.get('next_question', '')
        question_area = gpt_response.get('question_area', 'general')
        
        return self.repetition_detector.is_repetitive(next_question, question_area)
    
    def _get_alternative_question(self, context: Dict, phase: str) -> Dict:
        """Получить альтернативный вопрос при детекции повтора"""
        
        alternative_instruction = """
        ВАЖНО: Предыдущий вопрос был похож на уже заданные. 
        Найди СОВЕРШЕННО ДРУГУЮ область или подход.
        Приоритет: избежать повторения любой ценой.
        """
        
        context['alternative_instruction'] = alternative_instruction
        
        available_areas = ['technical_basics', 'practical_experience', 'problem_solving', 'system_design', 'soft_skills']
        alternatives = self.repetition_detector.get_alternative_topics('current', available_areas)
        context['suggested_alternatives'] = ', '.join(alternatives[:3])
        
        prompt = InterviewPrompts.get_prompt_for_phase(phase)
        enhanced_prompt = prompt + "\n\n" + alternative_instruction + "\nВозможные альтернативы: {suggested_alternatives}"
        
        try:
            messages = [{"role": "user", "content": enhanced_prompt.format(**context)}]
            response = self.openai_client.get_response_sync(messages)
            return self._parse_gpt_response(response)
        except:
            return self._create_fallback_response(phase)
    
    def _update_candidate_profile(self, gpt_response: Dict):
        """Обновление профиля с анализом стратегий"""
        analysis = gpt_response.get('previous_answer_analysis', {})
        
        if analysis and self.qa_history:
            question_area = gpt_response.get('question_area', 'general')
            tech_score = analysis.get('technical_score', 0)
            
            self.profiler.update_from_answer(question_area, analysis)
            
            if tech_score <= 4:
                self.repetition_detector.mark_topic_as_failed(question_area)
                adaptation = self.strategy_adaptor.adapt_to_weak_answer(question_area, tech_score)
                print(f"🔄 Слабый ответ в {question_area}, адаптация: {adaptation}")
            elif tech_score >= 8:
                adaptation = self.strategy_adaptor.adapt_to_strong_answer(question_area, tech_score)
                print(f"✅ Сильный ответ в {question_area}, адаптация: {adaptation}")
    
    def _apply_enhanced_adaptive_logic(self, gpt_response: Dict):
        """Расширенная адаптивная логика"""
        
        self._adapt_difficulty(gpt_response)
        
        self._adapt_to_time_constraints(gpt_response)
        
        self._check_enhanced_phase_transition(gpt_response)
        
        next_question = gpt_response.get('next_question', '')
        question_area = gpt_response.get('question_area', 'general')
        difficulty = gpt_response.get('question_difficulty', 'medium')
        
        if next_question:
            self.repetition_detector.add_question(
                next_question, question_area, self.current_phase.value, difficulty
            )
    
    def _adapt_to_time_constraints(self, gpt_response: Dict):
        """Адаптация к временным ограничениям"""
        time_status = self.time_manager.get_time_status()
        
        if time_status == "critical_time":
            if self.current_phase not in [InterviewPhase.WRAP_UP, InterviewPhase.FINISHED]:
                print("⏰ КРИТИЧЕСКОЕ ВРЕМЯ! Принудительный переход к wrap_up")
                self._transition_to_phase(InterviewPhase.WRAP_UP)
                
        elif time_status == "need_wrap_up":
            if self.current_phase == InterviewPhase.STRESS_TEST:
                print("⏰ Мало времени, пропускаем stress_test → soft_skills")
                self._transition_to_phase(InterviewPhase.SOFT_SKILLS)
            elif self.current_phase not in [InterviewPhase.SOFT_SKILLS, InterviewPhase.WRAP_UP]:
                print("⏰ Время заканчивается, ускоряемся к soft_skills")
                
        elif time_status == "need_acceleration":
            print("⏰ Нужно ускориться, сокращаем глубину вопросов")
    
    def _check_enhanced_phase_transition(self, gpt_response: Dict):
        """Улучшенная проверка переходов с приоритетом на завершение фазы."""
        
        current_phase_name = self.current_phase.value
        questions_in_phase = self.phase_stats[self.current_phase].questions_asked
        
        recommended_phase_name = self.profiler.get_recommended_phase(current_phase_name, questions_in_phase)
        
        if recommended_phase_name != current_phase_name:
            print(f"✅ Условия для перехода созрели. Переходим в '{recommended_phase_name}'.")
            try:
                new_phase = InterviewPhase(recommended_phase_name)
                self._transition_to_phase(new_phase)
                return
            except ValueError:
                pass

        analysis = gpt_response.get('previous_answer_analysis', {})
        if analysis.get('adaptation_needed') and analysis['adaptation_needed'] != 'none':
            print("💡 LLM запросил адаптацию (уточняющий вопрос). Переход фазы отложен.")
            return

        interview_status = gpt_response.get('interview_status', 'continuing')
        time_management = gpt_response.get('time_management', {})
        
        if isinstance(time_management, dict):
            time_status = time_management.get('status', 'continue')
        else:
            time_status = time_management

        if interview_status == 'finished':
            self._transition_to_phase(InterviewPhase.FINISHED)
        elif time_status in ['need_wrap_up', 'critical_time']:
            self._transition_to_phase(InterviewPhase.WRAP_UP)
    
    def _adapt_difficulty(self, gpt_response: Dict):
        """Адаптация сложности (без изменений из оригинала)"""
        analysis = gpt_response.get('previous_answer_analysis', {})
        tech_score = analysis.get('technical_score', 5)
        config = AdaptiveInterviewConfig.DIFFICULTY_ADAPTATION
        
        if tech_score <= config['weak_answer_threshold']:
            self.consecutive_weak_answers += 1
            self.consecutive_strong_answers = 0
        elif tech_score >= config['strong_answer_threshold']:
            self.consecutive_strong_answers += 1
            self.consecutive_weak_answers = 0
        else:
            self.consecutive_weak_answers = 0
            self.consecutive_strong_answers = 0
        
        recommended_difficulty = self.profiler.should_adjust_difficulty(self.current_difficulty)
        
        if self.consecutive_weak_answers >= config['consecutive_weak_threshold'] and self.current_difficulty != "easy":
            self.current_difficulty = "easy"
        elif self.consecutive_strong_answers >= config['consecutive_strong_threshold'] and self.current_difficulty != "hard":
            self.current_difficulty = "hard"
        else:
            self.current_difficulty = recommended_difficulty
    
    def _create_adaptive_plan(self) -> List[str]:
        """Создание адаптивного плана (без изменений)"""
        vacancy_type = AdaptiveInterviewConfig.determine_vacancy_type(
            self.candidate_data.get('vacancy_title', ''),
            self.candidate_data.get('industry', '')
        )
        base_plan = AdaptiveInterviewConfig.get_focus_areas_for_vacancy(vacancy_type)

        hr_concerns = self.profiler.profile.hr_concerns
        priority_areas = []
        
        for concern in hr_concerns[:AdaptiveInterviewConfig.HR_ANALYSIS_INTEGRATION['max_concerns_to_address']]:
            concern_lower = concern.lower()
            if any(keyword in concern_lower for keyword in ['алгоритм', 'структур', 'задач']):
                priority_areas.append('problem_solving')
            elif any(keyword in concern_lower for keyword in ['архитектур', 'дизайн', 'систем']):
                priority_areas.append('system_design')
            elif any(keyword in concern_lower for keyword in ['команд', 'лидер', 'управлен']):
                priority_areas.append('soft_skills')
            elif any(keyword in concern_lower for keyword in ['технолог', 'фреймворк', 'язык']):
                priority_areas.append('technical_basics')
        
        all_areas = priority_areas + base_plan
        unique_plan = []
        for area in all_areas:
            if area not in unique_plan:
                unique_plan.append(area)
        
        return unique_plan[:4]
    
    def _transition_to_phase(self, new_phase: InterviewPhase):
        """Переход к новой фазе (без изменений)"""
        print(f"🔄 Переход: {self.current_phase.value} → {new_phase.value}")
        
        self.phase_history.append({
            'phase': self.current_phase.value,
            'duration': time.time() - self.phase_stats[self.current_phase].start_time,
            'questions_asked': self.phase_stats[self.current_phase].questions_asked
        })
        
        self.current_phase = new_phase
        self.phase_stats[new_phase].start_time = time.time()
    
    def _update_interview_state(self, gpt_response: Dict):
        """Обновление состояния (расширенное)"""
        
        self.total_questions += 1
        self.phase_stats[self.current_phase].questions_asked += 1
        
        analysis = gpt_response.get('previous_answer_analysis', {})
        if analysis:
            tech_score = analysis.get('technical_score', 0)
            current_stats = self.phase_stats[self.current_phase]
            
            if tech_score <= 4:
                current_stats.weak_answers_count += 1
            elif tech_score >= 8:
                current_stats.strong_answers_count += 1
            
            if current_stats.questions_asked == 1:
                current_stats.avg_score = tech_score
            else:
                weight = 1.0 / current_stats.questions_asked
                current_stats.avg_score = (
                    current_stats.avg_score * (1 - weight) + tech_score * weight
                )
        
        difficulty = gpt_response.get('question_difficulty', self.current_difficulty)
        topic = gpt_response.get('question_area', 'general')
        
        current_stats = self.phase_stats[self.current_phase]
        if difficulty not in current_stats.difficulties_used:
            current_stats.difficulties_used.append(difficulty)
            
        if topic not in current_stats.topics_covered:
            current_stats.topics_covered.append(topic)
            
        if topic not in self.covered_areas:
            self.covered_areas.append(topic)
    
    def _parse_gpt_response(self, response: str) -> Optional[Dict]:
        """Улучшенный парсинг с поддержкой новых полей"""
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1)
                parsed = json.loads(json_str)
                return self._validate_and_clean_response(parsed)

            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
                return self._validate_and_clean_response(parsed)
                
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"📄 Ответ GPT: {response[:300]}...")
        
        return None
    
    def _validate_and_clean_response(self, response: Dict) -> Dict:
        """Валидация и очистка ответа GPT"""
        
        required_fields = {
            'interview_status': 'continuing',
            'current_phase': self.current_phase.value,
            'candidate_level': self.profiler.profile.technical_level,
            'next_question': 'Продолжим наше интервью.',
            'question_area': 'general',
            'question_difficulty': 'medium'
        }
        
        for field, default_value in required_fields.items():
            if field not in response:
                response[field] = default_value
        
        if 'time_management' not in response:
            response['time_management'] = {
                'status': self.time_manager.get_time_status(),
                'remaining_minutes': self.time_manager.get_remaining_minutes(),
                'priority_actions': [],
                'time_strategy': 'standard'
            }
        
        if 'repetition_analysis' not in response:
            response['repetition_analysis'] = {
                'similar_questions_asked': [],
                'avoided_repetition': 'none',
                'alternative_approach': 'standard'
            }
        
        return response
    
    def _create_fallback_response(self, phase: str) -> Dict:
        """Создание fallback ответа (расширенное)"""
        fallback_questions = {
            'exploration': f"Расскажите о технологиях, которые вы используете в повседневной работе.",
            'validation': "Приведите конкретный пример того, как вы решали техническую проблему.",
            'stress_test': "Представьте, что система работает медленно. Ваши действия?",
            'soft_skills': "Опишите ситуацию командной работы над проектом.",
            'wrap_up': f"Спасибо за интервью! Есть ли у вас вопросы о позиции?"
        }
        
        return {
            'interview_status': 'continuing' if phase != 'wrap_up' else 'finished',
            'current_phase': phase,
            'candidate_level': self.profiler.profile.technical_level,
            'interview_plan': self.interview_plan,
            'current_area': 'general',
            'time_management': {
                'status': self.time_manager.get_time_status(),
                'remaining_minutes': self.time_manager.get_remaining_minutes(),
                'priority_actions': ['fallback_mode'],
                'time_strategy': 'fallback strategy due to parsing error'
            },
            'repetition_analysis': {
                'similar_questions_asked': [],
                'avoided_repetition': 'fallback mode',
                'alternative_approach': 'using predefined fallback question'
            },
            'previous_answer_analysis': {
                'technical_score': 5, 'communication_score': 5, 'depth_score': 5,
                'confidence_score': 5, 'practical_experience': 5, 'red_flags': [],
                'strengths_shown': [], 'analysis_notes': 'Fallback анализ',
                'knowledge_gaps': [], 'adaptation_needed': 'continue with fallback'
            },
            'next_question': fallback_questions.get(phase, "Продолжим интервью."),
            'question_area': 'general',
            'question_difficulty': self.current_difficulty,
            'question_reasoning': f'Fallback вопрос для фазы {phase}',
            'alternative_strategies': ['fallback', 'standard'],
            'interviewer_notes': f'Fallback mode activated for phase {phase}',
            'overall_progress': f'Fallback в фазе {phase}',
            'emotional_approach': 'supportive'
        }
    
    def get_final_report(self) -> Dict:
        """Финальный отчет с расширенной аналитикой"""
        
        profile_summary = self.profiler.generate_final_summary()
        
        phase_summary = {}
        for phase, stats in self.phase_stats.items():
            if stats.questions_asked > 0:
                phase_summary[phase.value] = {
                    'questions_asked': stats.questions_asked,
                    'avg_score': round(stats.avg_score, 1),
                    'difficulties_used': stats.difficulties_used,
                    'topics_covered': stats.topics_covered,
                    'weak_answers_count': stats.weak_answers_count,
                    'strong_answers_count': stats.strong_answers_count,
                    'duration_minutes': round((time.time() - stats.start_time) / 60, 1) if stats.start_time > 0 else 0
                }
        
        repetition_stats = self.repetition_detector.get_repetition_analysis()
        
        overall_score = profile_summary['final_scores']['overall_score']
        red_flags_count = len(profile_summary['red_flags'])
        thresholds = AdaptiveInterviewConfig.REPORTING_CONFIG['recommendation_thresholds']
        
        if overall_score >= thresholds['strong_hire'] and red_flags_count == 0:
            recommendation = "strong_hire"
            decision_text = "Настоятельно рекомендую к найму"
        elif overall_score >= thresholds['hire'] and red_flags_count <= 1:
            recommendation = "hire"
            decision_text = "Рекомендую к найму"
        elif overall_score >= thresholds['conditional_hire'] and red_flags_count <= 2:
            recommendation = "conditional_hire"
            decision_text = "Условно рекомендую"
        else:
            recommendation = "no_hire"
            decision_text = "Не рекомендую к найму"
        
        return {
            **profile_summary,
            'phase_breakdown': phase_summary,
            'interview_flow': self.phase_history,
            'repetition_analysis': repetition_stats,
            'adaptive_insights': {
                'final_difficulty': self.current_difficulty,
                'phase_transitions': len(self.phase_history),
                'hr_concerns_addressed': len(self.profiler.get_priority_concerns()) == 0,
                'total_interview_time': self.time_manager.get_elapsed_minutes(),
                'time_efficiency': 'good' if self.time_manager.get_remaining_minutes() > 2 else 'tight',
                'questions_per_minute': round(self.total_questions / max(self.time_manager.get_elapsed_minutes(), 1), 2),
                'failed_topics_count': len(self.repetition_detector.failed_topics),
                'strategy_adaptations': len(self.strategy_adaptor.failed_strategies) + len(self.strategy_adaptor.successful_strategies)
            },
            'final_recommendation': {
                'decision': recommendation,
                'decision_text': decision_text,
                'confidence_level': 'high' if red_flags_count == 0 else 'medium' if red_flags_count <= 2 else 'low'
            }
        }
    
    def should_end_interview(self, max_time_minutes: int = 25, max_questions: int = 12) -> bool:
        """Проверка условий завершения с расширенной логикой"""
        
        last_analysis = {}
        if self.detailed_qa_history:
            last_analysis = self.detailed_qa_history[-1].get('analysis', {})

        criteria = AdaptiveInterviewConfig.INTERVIEW_COMPLETION_CRITERIA

        if criteria.get('max_time_exceeded', True) and self.time_manager.should_end_interview():
            print("⏰ Время интервью истекло, завершаем.")
            return True
            
        max_q = AdaptiveInterviewConfig.MAX_QUESTIONS_PER_INTERVIEW
        if criteria.get('max_questions_reached', True) and self.total_questions >= max_q:
            print(f"🏁 Достигнут лимит в {max_q} вопросов, завершаем.")
            return True
            
        if criteria.get('all_phases_completed', True) and self.current_phase == InterviewPhase.FINISHED:
            return True
            
        red_flag_limit = criteria.get('critical_red_flags_count')
        if red_flag_limit is not None and len(self.profiler.profile.red_flags) >= red_flag_limit:
            
            if last_analysis.get('adaptation_needed') and last_analysis['adaptation_needed'] != 'none':
                print(f"🚩 Лимит флагов ({red_flag_limit}) достигнут, но LLM запросил адаптацию. Даем еще один шанс.")
                return False

            print(f"🚩 Превышен лимит красных флагов ({red_flag_limit}), завершаем интервью.")
            return True
        
        return False