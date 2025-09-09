#!/usr/bin/env python3
"""
Адаптивный менеджер интервью
Координирует фазы, адаптирует сложность, интегрирует HR-анализ
"""

import json
import time
import re
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

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
class PhaseStats:
    """Статистика по фазе"""
    questions_asked: int = 0
    avg_score: float = 0.0
    start_time: float = 0.0
    difficulties_used: List[str] = None
    
    def __post_init__(self):
        if self.difficulties_used is None:
            self.difficulties_used = []

class AdaptiveInterviewManager:
    """Менеджер адаптивного интервью с фазами и профилированием"""
    
    def __init__(self, candidate_data: Dict, openai_client):
        self.candidate_data = candidate_data
        self.openai_client = openai_client
        
        self.profiler = CandidateProfiler(candidate_data)
        
        self.current_phase = InterviewPhase.EXPLORATION
        self.phase_history = []
        self.phase_stats = {phase: PhaseStats() for phase in InterviewPhase}
        
        self.interview_plan = []
        self.covered_areas = []
        self.total_questions = 0
        self.start_time = time.time()
        
        self.current_difficulty = "medium"
        self.consecutive_weak_answers = 0
        self.consecutive_strong_answers = 0
        
        self.qa_history = []
    
    def get_initial_plan_and_question(self, candidate_name: str) -> Dict:
        """Создание начального плана и первого вопроса"""
        
        self.current_phase = InterviewPhase.EXPLORATION
        self.phase_stats[self.current_phase].start_time = time.time()
        self.profiler.profile.name = candidate_name
        
        self.interview_plan = self._create_adaptive_plan()
        
        context = self._build_context_for_gpt()
        context.pop('covered_areas', None)

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
        """Обработка ответа и получение следующего вопроса"""
        
        self.qa_history.append({
            'question': last_question,
            'answer': last_answer,
            'phase': self.current_phase.value,
            'timestamp': time.time()
        })
        
        current_phase_name = self.current_phase.value
        prompt = InterviewPrompts.get_prompt_for_phase(current_phase_name)
        
        context = self._build_context_for_gpt()
        context.update({
            'last_question': last_question,
            'last_answer': last_answer
        })
        
        try:
            messages = [{"role": "user", "content": prompt.format(**context)}]
            response = self.openai_client.get_response_sync(messages)
            gpt_response = self._parse_gpt_response(response)
            
            if gpt_response:
                self._update_candidate_profile(gpt_response)
                
                self._apply_adaptive_logic(gpt_response)
                
                self._update_interview_state(gpt_response)
                
                return gpt_response
            else:
                return self._create_fallback_response(current_phase_name)
                
        except Exception as e:
            print(f"Ошибка обработки ответа: {e}")
            return self._create_fallback_response(current_phase_name)
    
    def _create_adaptive_plan(self) -> List[str]:
        """Создание адаптивного плана на основе конфига и HR-анализа"""
        
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
    
    def _build_context_for_gpt(self) -> Dict:
        """Построение контекста для GPT промптов"""
        
        context = {
            'candidate_name': self.profiler.profile.name,
            'vacancy_title': self.candidate_data.get('vacancy_title', ''),
            'industry': self.candidate_data.get('industry', ''),
            'hr_strengths': ', '.join(self.profiler.profile.hr_strengths[:3]) if self.profiler.profile.hr_strengths else 'Не указаны',
            'hr_concerns': ', '.join(self.profiler.profile.hr_concerns[:3]) if self.profiler.profile.hr_concerns else 'Не указаны',
            'elapsed_minutes': int((time.time() - self.start_time) / 60),
            'questions_count': self.total_questions,
            'interview_plan': ', '.join(self.interview_plan),
            'covered_areas': ', '.join(self.covered_areas),
            'candidate_level': self.profiler.profile.technical_level
        }
        
        profile_context = self.profiler.get_context_for_prompt()
        context.update(profile_context)
        
        return context
    
    def _update_candidate_profile(self, gpt_response: Dict):
        """Обновление профиля кандидата на основе ответа GPT"""
        analysis = gpt_response.get('previous_answer_analysis', {})
        
        if analysis and self.qa_history:
            question_area = gpt_response.get('question_area', 'general')
            
            self.profiler.update_from_answer(question_area, analysis)
    
    def _apply_adaptive_logic(self, gpt_response: Dict):
        """Применение адаптивной логики"""
        
        self._adapt_difficulty(gpt_response)
        
        self._check_phase_transition(gpt_response)
        
        self._adjust_interview_plan(gpt_response)
    
    def _adapt_difficulty(self, gpt_response: Dict):
        """Адаптация сложности вопросов на основе конфига"""
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
    
    def _check_phase_transition(self, gpt_response: Dict):
        """Проверка необходимости смены фазы"""
        
        current_phase_name = self.current_phase.value
        questions_in_phase = self.phase_stats[self.current_phase].questions_asked
        
        recommended_phase = self.profiler.get_recommended_phase(current_phase_name, questions_in_phase)
        
        interview_status = gpt_response.get('interview_status', 'continuing')
        time_management = gpt_response.get('time_management', 'continue')
        
        if interview_status == 'finished' or time_management == 'finish':
            new_phase = InterviewPhase.FINISHED
        elif time_management == 'wrap_up':
            new_phase = InterviewPhase.WRAP_UP
        elif recommended_phase != current_phase_name:
            try:
                new_phase = InterviewPhase(recommended_phase)
            except ValueError:
                new_phase = self.current_phase
        else:
            new_phase = self.current_phase
        
        if new_phase != self.current_phase:
            self._transition_to_phase(new_phase)
    
    def _transition_to_phase(self, new_phase: InterviewPhase):
        """Переход к новой фазе"""
        print(f"🔄 Переход: {self.current_phase.value} → {new_phase.value}")
        
        self.phase_history.append({
            'phase': self.current_phase.value,
            'duration': time.time() - self.phase_stats[self.current_phase].start_time,
            'questions_asked': self.phase_stats[self.current_phase].questions_asked
        })
        
        self.current_phase = new_phase
        self.phase_stats[new_phase].start_time = time.time()
    
    def _adjust_interview_plan(self, gpt_response: Dict):
        """Корректировка плана интервью"""
        current_area = gpt_response.get('current_area')
        
        if current_area and current_area not in self.covered_areas:
            self.covered_areas.append(current_area)
        
        updated_plan = gpt_response.get('interview_plan', [])
        if updated_plan and updated_plan != self.interview_plan:
            self.interview_plan = updated_plan
    
    def _update_interview_state(self, gpt_response: Dict):
        """Обновление общего состояния интервью"""
        
        self.total_questions += 1
        self.phase_stats[self.current_phase].questions_asked += 1
        
        analysis = gpt_response.get('previous_answer_analysis', {})
        if analysis:
            tech_score = analysis.get('technical_score', 0)
            current_stats = self.phase_stats[self.current_phase]
            
            if current_stats.questions_asked == 1:
                current_stats.avg_score = tech_score
            else:
                weight = 1.0 / current_stats.questions_asked
                current_stats.avg_score = (
                    current_stats.avg_score * (1 - weight) + tech_score * weight
                )
        
        difficulty = gpt_response.get('question_difficulty', self.current_difficulty)
        current_stats = self.phase_stats[self.current_phase]
        if difficulty not in current_stats.difficulties_used:
            current_stats.difficulties_used.append(difficulty)
    
    def _parse_gpt_response(self, response: str) -> Optional[Dict]:
        """Улучшенный парсинг JSON ответа от GPT с fallback'ом."""
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1)
                return json.loads(json_str)

            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
                
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"📄 Ответ GPT: {response[:300]}...")
        
        return None
    
    def _create_fallback_response(self, phase: str) -> Dict:
        """Создание fallback ответа при ошибках"""
        fallback_questions = {
            'exploration': f"Расскажите, пожалуйста, о своем опыте работы с технологиями, которые используются в {self.candidate_data.get('industry', 'вашей отрасли')}.",
            'validation': "Приведите конкретный пример проекта, где вы применяли упомянутые технологии.",
            'stress_test': "Как бы вы решили задачу оптимизации производительности в системе с высокой нагрузкой?",
            'soft_skills': "Расскажите о ситуации, когда вам пришлось работать в команде над сложным проектом.",
            'wrap_up': f"Спасибо за интервью, {self.profiler.profile.name}! Есть ли у вас вопросы о позиции?"
        }
        
        return {
            'interview_status': 'continuing' if phase != 'wrap_up' else 'finished',
            'current_phase': phase,
            'candidate_level': self.profiler.profile.technical_level,
            'interview_plan': self.interview_plan,
            'current_area': 'general',
            'previous_answer_analysis': {
                'technical_score': 5,
                'communication_score': 5,
                'depth_score': 5,
                'confidence_score': 5,
                'practical_experience': 5,
                'red_flags': [],
                'strengths_shown': [],
                'analysis_notes': 'Fallback анализ из-за ошибки парсинга'
            },
            'next_question': fallback_questions.get(phase, "Продолжим наше интервью."),
            'question_area': 'general',
            'question_difficulty': self.current_difficulty,
            'question_reasoning': 'Fallback вопрос',
            'interviewer_notes': f'Используется fallback для фазы {phase}',
            'time_management': 'continue' if phase != 'wrap_up' else 'finish',
            'overall_progress': f'Интервью в фазе {phase}',
            'emotional_approach': 'supportive'
        }
    
    def get_final_report(self) -> Dict:
        """Генерация финального отчета на основе конфига"""
        
        profile_summary = self.profiler.generate_final_summary()
        
        phase_summary = {}
        for phase, stats in self.phase_stats.items():
            if stats.questions_asked > 0:
                phase_summary[phase.value] = {
                    'questions_asked': stats.questions_asked,
                    'avg_score': round(stats.avg_score, 1),
                    'difficulties_used': stats.difficulties_used,
                    'duration_minutes': round((time.time() - stats.start_time) / 60, 1) if stats.start_time > 0 else 0
                }
        
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
            decision_text = "Условно рекомендую (требует дополнительной оценки)"
        else:
            recommendation = "no_hire"
            decision_text = "Не рекомендую к найму"
        
        final_report = {
            **profile_summary,
            'phase_breakdown': phase_summary,
            'interview_flow': self.phase_history,
            'adaptive_insights': {
                'final_difficulty': self.current_difficulty,
                'phase_transitions': len(self.phase_history),
                'hr_concerns_addressed': len(self.profiler.get_priority_concerns()) == 0,
                'total_interview_time': round((time.time() - self.start_time) / 60, 1)
            },
            'final_recommendation': {
                'decision': recommendation,
                'decision_text': decision_text,
                'confidence_level': 'high' if red_flags_count == 0 else 'medium' if red_flags_count <= 2 else 'low'
            }
        }
        
        return final_report
    
    def should_end_interview(self, max_time_minutes: int = 25, max_questions: int = 12) -> bool:
        """Проверка условий завершения интервью"""
        elapsed_minutes = (time.time() - self.start_time) / 60
        
        return (
            elapsed_minutes >= max_time_minutes or
            self.total_questions >= max_questions or
            self.current_phase == InterviewPhase.FINISHED
        )