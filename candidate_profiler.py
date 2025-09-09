#!/usr/bin/env python3
"""
Система динамического профилирования кандидата
Определяет уровень, сильные/слабые стороны в реальном времени
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from config import AdaptiveInterviewConfig

@dataclass
class CandidateProfile:
    """Профиль кандидата, обновляемый в реальном времени"""
    
    # Базовая информация
    name: str = ""
    vacancy_title: str = ""
    industry: str = ""
    
    # Динамически определяемые характеристики
    technical_level: str = "unknown"  # junior/middle/senior/unknown
    communication_style: str = "unknown"  # confident/uncertain/verbose/concise
    learning_indicators: List[str] = field(default_factory=list)
    
    # Накопленная статистика
    total_questions: int = 0
    avg_technical_score: float = 0.0
    avg_communication_score: float = 0.0
    avg_confidence_score: float = 0.0
    
    # Выявленные паттерны
    confirmed_strengths: List[str] = field(default_factory=list)
    confirmed_weaknesses: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    
    # HR-анализ для сравнения
    hr_strengths: List[str] = field(default_factory=list)
    hr_concerns: List[str] = field(default_factory=list)
    
    # Метрики по областям
    area_scores: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь для передачи в промпты"""
        return {
            'name': self.name,
            'technical_level': self.technical_level,
            'communication_style': self.communication_style,
            'learning_indicators': self.learning_indicators,
            'total_questions': self.total_questions,
            'avg_technical_score': self.avg_technical_score,
            'avg_communication_score': self.avg_communication_score,
            'confirmed_strengths': self.confirmed_strengths,
            'confirmed_weaknesses': self.confirmed_weaknesses,
            'red_flags': self.red_flags
        }

class CandidateProfiler:
    """Класс для динамического профилирования кандидата"""
    
    def __init__(self, candidate_data: Dict):
        self.profile = CandidateProfile()
        self._init_from_candidate_data(candidate_data)
        
        # Паттерны для определения стиля коммуникации
        self.communication_patterns = {
            'confident': ['высокий confidence_score', 'развернутые ответы', 'конкретные примеры'],
            'uncertain': ['низкий confidence_score', 'частые паузы', 'неопределенные ответы'],
            'verbose': ['длинные ответы', 'много деталей', 'отклонения от темы'],
            'concise': ['краткие ответы', 'по существу', 'структурированно']
        }
    
    def _init_from_candidate_data(self, candidate_data: Dict):
        """Инициализация профиля из данных кандидата"""
        self.profile.name = candidate_data.get('candidate_name', '')
        self.profile.vacancy_title = candidate_data.get('vacancy_title', '')
        self.profile.industry = candidate_data.get('industry', '')
        
        # Парсинг HR-анализа
        self._parse_hr_analysis(candidate_data.get('result_json', '{}'))
    
    def _parse_hr_analysis(self, result_json: str):
        """Расширенный парсинг HR-анализа"""
        try:
            data = json.loads(result_json)
            final_eval = data.get('final_evaluation', {})
            
            self.profile.hr_strengths = final_eval.get('key_strengths', [])
            self.profile.hr_concerns = final_eval.get('critical_concerns', [])
            
            # Попытка определить предварительный уровень из HR-анализа
            overall_score = final_eval.get('overall_score', 0)
            if overall_score >= 85:
                self.profile.technical_level = "senior_candidate"
            elif overall_score >= 70:
                self.profile.technical_level = "middle_candidate"
            elif overall_score >= 50:
                self.profile.technical_level = "junior_candidate"
                
        except json.JSONDecodeError:
            # Fallback если JSON поврежден
            self.profile.hr_strengths = []
            self.profile.hr_concerns = []
    
    def update_from_answer(self, question_area: str, analysis: Dict):
        """Обновление профиля на основе анализа ответа"""
        if not analysis:
            return
        
        self.profile.total_questions += 1
        
        # Обновление средних оценок
        self._update_average_scores(analysis)
        
        # Сохранение оценок по областям
        self._update_area_scores(question_area, analysis)
        
        # Определение уровня кандидата
        self._update_technical_level()
        
        # Анализ стиля коммуникации
        self._update_communication_style(analysis)
        
        # Обновление сильных/слабых сторон
        self._update_strengths_weaknesses(analysis)
        
        # Отслеживание индикаторов обучаемости
        self._update_learning_indicators(analysis)
        
        # Сбор красных флагов
        self._update_red_flags(analysis)
    
    def _update_average_scores(self, analysis: Dict):
        """Обновление средних оценок"""
        # Используем скользящее среднее
        weight = 1.0 / self.profile.total_questions
        
        tech_score = analysis.get('technical_score', 0)
        comm_score = analysis.get('communication_score', 0)
        conf_score = analysis.get('confidence_score', 0)
        
        if self.profile.total_questions == 1:
            # Первый ответ
            self.profile.avg_technical_score = tech_score
            self.profile.avg_communication_score = comm_score
            self.profile.avg_confidence_score = conf_score
        else:
            # Обновление скользящего среднего
            self.profile.avg_technical_score = (
                self.profile.avg_technical_score * (1 - weight) + tech_score * weight
            )
            self.profile.avg_communication_score = (
                self.profile.avg_communication_score * (1 - weight) + comm_score * weight
            )
            self.profile.avg_confidence_score = (
                self.profile.avg_confidence_score * (1 - weight) + conf_score * weight
            )
    
    def _update_area_scores(self, question_area: str, analysis: Dict):
        """Сохранение оценок по техническим областям"""
        tech_score = analysis.get('technical_score', 0)
        if tech_score > 0:
            self.profile.area_scores[question_area].append(tech_score)
    
    def _update_technical_level(self):
        """Динамическое определение технического уровня на основе конфига"""
        avg_tech = self.profile.avg_technical_score
        thresholds = AdaptiveInterviewConfig.CANDIDATE_LEVEL_THRESHOLDS
        
        # Проверяем только если задано достаточно вопросов для определения
        required_questions = thresholds.get('junior', {}).get('required_questions', 3)
        if self.profile.total_questions < required_questions:
            return

        # Логика определения уровня из конфига
        if avg_tech >= thresholds['senior']['min_technical_score']:
            self.profile.technical_level = "senior"
        elif avg_tech >= thresholds['middle']['min_technical_score']:
            self.profile.technical_level = "middle"
        else:
            self.profile.technical_level = "junior"

    def _update_communication_style(self, analysis: Dict):
        """Определение стиля коммуникации"""
        comm_score = analysis.get('communication_score', 0)
        conf_score = analysis.get('confidence_score', 0)
        
        # Простая эвристика на основе оценок
        if conf_score >= 8 and comm_score >= 7:
            self.profile.communication_style = "confident"
        elif conf_score <= 4:
            self.profile.communication_style = "uncertain"
        elif comm_score >= 8:
            self.profile.communication_style = "concise"
        else:
            self.profile.communication_style = "developing"
    
    def _update_strengths_weaknesses(self, analysis: Dict):
        """Обновление подтвержденных сильных/слабых сторон"""
        strengths = analysis.get('strengths_shown', [])
        
        # Добавляем новые сильные стороны (избегаем дубликатов)
        for strength in strengths:
            if strength not in self.profile.confirmed_strengths:
                self.profile.confirmed_strengths.append(strength)
        
        # Определение слабых сторон на основе низких оценок
        tech_score = analysis.get('technical_score', 0)
        weak_threshold = AdaptiveInterviewConfig.DIFFICULTY_ADAPTATION['weak_answer_threshold']
        if tech_score <= weak_threshold - 1: # если оценка еще ниже порога "слабого ответа"
            weakness = f"слабые знания в текущей области (оценка {tech_score}/10)"
            if weakness not in self.profile.confirmed_weaknesses:
                self.profile.confirmed_weaknesses.append(weakness)
    
    def _update_learning_indicators(self, analysis: Dict):
        """Отслеживание индикаторов обучаемости"""
        notes = analysis.get('analysis_notes', '').lower()
        
        learning_keywords = {
            'curious': ['интересуется', 'задает вопросы', 'хочет узнать'],
            'adaptive': ['пытается применить', 'думает о применении', 'связывает с опытом'],
            'systematic': ['структурированный подход', 'методично', 'по шагам'],
            'growth_mindset': ['готов изучать', 'хочет развиваться', 'признает пробелы']
        }
        
        for indicator, keywords in learning_keywords.items():
            if any(keyword in notes for keyword in keywords):
                if indicator not in self.profile.learning_indicators:
                    self.profile.learning_indicators.append(indicator)
    
    def _update_red_flags(self, analysis: Dict):
        """Сбор красных флагов"""
        red_flags = analysis.get('red_flags', [])
        
        for flag in red_flags:
            if flag not in self.profile.red_flags:
                self.profile.red_flags.append(flag)
    
    def get_recommended_phase(self, current_phase: str, questions_in_phase: int) -> str:
        """Рекомендация следующей фазы на основе профиля и конфига"""
        rules = AdaptiveInterviewConfig.PHASE_TRANSITION_RULES

        if current_phase == "exploration" and rules.get('exploration_to_validation'):
            rule = rules['exploration_to_validation']
            if (questions_in_phase >= rule['min_questions'] and self.profile.technical_level != "unknown") or \
               (questions_in_phase >= rule['fallback_after_questions']):
                return "validation"

        elif current_phase == "validation":
            if rules.get('validation_to_stress_test') and \
               self.profile.avg_technical_score >= rules['validation_to_stress_test']['min_avg_score'] and \
               questions_in_phase >= rules['validation_to_stress_test']['min_questions']:
                return "stress_test"
            if rules.get('validation_to_soft_skills') and \
               questions_in_phase >= rules['validation_to_soft_skills']['min_questions']:
                return "soft_skills"

        elif current_phase == "stress_test" and rules.get('stress_test_to_soft_skills'):
            if questions_in_phase >= rules['stress_test_to_soft_skills']['min_questions']:
                return "soft_skills"

        elif current_phase == "soft_skills" and rules.get('soft_skills_to_wrap_up'):
            if questions_in_phase >= rules['soft_skills_to_wrap_up']['min_questions']:
                return "wrap_up"

        elif current_phase == "wrap_up":
            return "finished"
        
        return current_phase
    
    def should_adjust_difficulty(self, current_difficulty: str) -> str:
        """Рекомендация по корректировке сложности вопросов из конфига"""
        avg_tech = self.profile.avg_technical_score
        config = AdaptiveInterviewConfig.DIFFICULTY_ADAPTATION
        
        if avg_tech < config['weak_answer_threshold'] and current_difficulty != "easy":
            return "easy"
        elif avg_tech > config['strong_answer_threshold'] and current_difficulty != "hard":
            return "hard"
        elif config['weak_answer_threshold'] <= avg_tech <= config['strong_answer_threshold'] and current_difficulty != "medium":
            return "medium"
        
        return current_difficulty
    
    def get_priority_concerns(self) -> List[str]:
        """Получить приоритетные concerns для проверки"""
        # Возвращаем HR-concerns, которые еще не были проверены
        unchecked_concerns = []
        
        for concern in self.profile.hr_concerns:
            # Простая проверка - если concern еще не "опровергнут" сильными сторонами
            concern_addressed = any(
                concern.lower() in strength.lower() 
                for strength in self.profile.confirmed_strengths
            )
            
            if not concern_addressed:
                unchecked_concerns.append(concern)
        
        return unchecked_concerns[:3]  # Топ-3 для фокуса
    
    def get_context_for_prompt(self) -> Dict:
        """Подготовка контекста профиля для промптов"""
        return {
            'candidate_level': self.profile.technical_level,
            'communication_style': self.profile.communication_style,
            'avg_scores': {
                'technical': round(self.profile.avg_technical_score, 1),
                'communication': round(self.profile.avg_communication_score, 1),
                'confidence': round(self.profile.avg_confidence_score, 1)
            },
            'confirmed_strengths': self.profile.confirmed_strengths,
            'confirmed_weaknesses': self.profile.confirmed_weaknesses,
            'learning_indicators': self.profile.learning_indicators,
            'red_flags': self.profile.red_flags,
            'priority_concerns': self.get_priority_concerns()
        }
    
    def generate_final_summary(self) -> Dict:
        """Генерация финального резюме профиля"""
        return {
            'candidate_name': self.profile.name,
            'final_level': self.profile.technical_level,
            'final_scores': {
                'technical_avg': round(self.profile.avg_technical_score, 1),
                'communication_avg': round(self.profile.avg_communication_score, 1),
                'confidence_avg': round(self.profile.avg_confidence_score, 1),
                'overall_score': round(
                    (self.profile.avg_technical_score + self.profile.avg_communication_score) / 2 * 10
                )
            },
            'strengths_confirmed': self.profile.confirmed_strengths,
            'weaknesses_identified': self.profile.confirmed_weaknesses,
            'red_flags': self.profile.red_flags,
            'learning_potential': self.profile.learning_indicators,
            'hr_validation': {
                'strengths_validated': [
                    s for s in self.profile.hr_strengths 
                    if any(s.lower() in conf.lower() for conf in self.profile.confirmed_strengths)
                ],
                'concerns_confirmed': [
                    c for c in self.profile.hr_concerns
                    if any(c.lower() in weak.lower() for weak in self.profile.confirmed_weaknesses)
                ]
            },
            'interview_stats': {
                'total_questions': self.profile.total_questions,
                'areas_covered': list(self.profile.area_scores.keys()),
                'performance_by_area': {
                    area: round(sum(scores) / len(scores), 1)
                    for area, scores in self.profile.area_scores.items()
                    if scores
                }
            }
        }