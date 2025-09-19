#!/usr/bin/env python3
"""
Система динамического профилирования кандидата
УЛУЧШЕНИЯ:
+ Отслеживание повторяющихся слабых областей
+ Улучшенная адаптация сложности
+ Дополнительная аналитика для тайм-менеджмента
"""

import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from config import AdaptiveInterviewConfig

@dataclass
class CandidateProfile:
    """Расширенный профиль кандидата"""
    
    name: str = ""
    vacancy_title: str = ""
    industry: str = ""
    
    technical_level: str = "unknown"
    communication_style: str = "unknown"
    learning_indicators: List[str] = field(default_factory=list)
    
    total_questions: int = 0
    avg_technical_score: float = 0.0
    avg_communication_score: float = 0.0
    avg_confidence_score: float = 0.0
    
    confirmed_strengths: List[str] = field(default_factory=list)
    confirmed_weaknesses: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    
    hr_strengths: List[str] = field(default_factory=list)
    hr_concerns: List[str] = field(default_factory=list)
    
    area_scores: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    failed_areas: Set[str] = field(default_factory=set)
    strong_areas: Set[str] = field(default_factory=set)
    question_types_asked: Counter = field(default_factory=Counter)
    adaptation_history: List[str] = field(default_factory=list)
    
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
            'red_flags': self.red_flags,
            'failed_areas': list(self.failed_areas),
            'strong_areas': list(self.strong_areas)
        }

class CandidateProfiler:
    """Расширенный класс для динамического профилирования кандидата"""
    
    def __init__(self, candidate_data: Dict):
        self.profile = CandidateProfile()
        self._init_from_candidate_data(candidate_data)
        
        self.failure_threshold = 3.0
        self.success_threshold = 8.0
        
        self.consecutive_failures_in_area = defaultdict(int)
        self.recent_adaptations = []
    
    def _init_from_candidate_data(self, candidate_data: Dict):
        """Инициализация профиля из данных кандидата (без изменений)"""
        self.profile.name = candidate_data.get('candidate_name', '')
        self.profile.vacancy_title = candidate_data.get('vacancy_title', '')
        self.profile.industry = candidate_data.get('industry', '')
        
        self._parse_hr_analysis(candidate_data.get('result_json', '{}'))
    
    def _parse_hr_analysis(self, result_json: str):
        """Расширенный парсинг HR-анализа (без изменений)"""
        try:
            data = json.loads(result_json)
            final_eval = data.get('final_evaluation', {})
            
            self.profile.hr_strengths = final_eval.get('key_strengths', [])
            self.profile.hr_concerns = final_eval.get('critical_concerns', [])
            
            overall_score = final_eval.get('overall_score', 0)
            if overall_score >= 85:
                self.profile.technical_level = "senior_candidate"
            elif overall_score >= 70:
                self.profile.technical_level = "middle_candidate"
            elif overall_score >= 50:
                self.profile.technical_level = "junior_candidate"
                
        except json.JSONDecodeError:
            self.profile.hr_strengths = []
            self.profile.hr_concerns = []
    
    def update_from_answer(self, question_area: str, analysis: Dict):
        """УЛУЧШЕННОЕ обновление профиля на основе анализа ответа"""
        if not analysis:
            return
        
        self.profile.total_questions += 1
        tech_score = analysis.get('technical_score', 0)
        
        self.profile.question_types_asked[question_area] += 1
        
        self._update_average_scores(analysis)
        
        self._update_area_scores(question_area, analysis)
        
        self._track_area_performance(question_area, tech_score)
        
        self._update_technical_level()
        
        self._update_communication_style(analysis)
        
        self._update_strengths_weaknesses(analysis)
        
        self._update_learning_indicators(analysis)
        
        self._update_red_flags(analysis)
    
    def _track_area_performance(self, question_area: str, tech_score: float):
        """НОВОЕ: Отслеживание производительности по областям"""
        
        if tech_score <= self.failure_threshold:
            self.consecutive_failures_in_area[question_area] += 1
            
            if self.consecutive_failures_in_area[question_area] >= 2:
                self.profile.failed_areas.add(question_area)
                print(f"❌ Область '{question_area}' помечена как слабая после {self.consecutive_failures_in_area[question_area]} провалов")
                
        elif tech_score >= self.success_threshold:
            self.consecutive_failures_in_area[question_area] = 0
            
            self.profile.strong_areas.add(question_area)
            
        else:
            if self.consecutive_failures_in_area[question_area] > 0:
                self.consecutive_failures_in_area[question_area] -= 1
    
    def _update_average_scores(self, analysis: Dict):
        """Обновление средних оценок (без изменений)"""
        weight = 1.0 / self.profile.total_questions
        
        tech_score = analysis.get('technical_score', 0)
        comm_score = analysis.get('communication_score', 0)
        conf_score = analysis.get('confidence_score', 0)
        
        if self.profile.total_questions == 1:
            self.profile.avg_technical_score = tech_score
            self.profile.avg_communication_score = comm_score
            self.profile.avg_confidence_score = conf_score
        else:
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
        """Сохранение оценок по техническим областям (без изменений)"""
        tech_score = analysis.get('technical_score', 0)
        if tech_score > 0:
            self.profile.area_scores[question_area].append(tech_score)
    
    def _update_technical_level(self):
        """Динамическое определение технического уровня (без изменений)"""
        avg_tech = self.profile.avg_technical_score
        thresholds = AdaptiveInterviewConfig.CANDIDATE_LEVEL_THRESHOLDS
        
        required_questions = thresholds.get('junior', {}).get('required_questions', 3)
        if self.profile.total_questions < required_questions:
            return

        if avg_tech >= thresholds['senior']['min_technical_score']:
            self.profile.technical_level = "senior"
        elif avg_tech >= thresholds['middle']['min_technical_score']:
            self.profile.technical_level = "middle"
        else:
            self.profile.technical_level = "junior"

    def _update_communication_style(self, analysis: Dict):
        """Определение стиля коммуникации (без изменений)"""
        comm_score = analysis.get('communication_score', 0)
        conf_score = analysis.get('confidence_score', 0)
        
        if conf_score >= 8 and comm_score >= 7:
            self.profile.communication_style = "confident"
        elif conf_score <= 4:
            self.profile.communication_style = "uncertain"
        elif comm_score >= 8:
            self.profile.communication_style = "concise"
        else:
            self.profile.communication_style = "developing"
    
    def _update_strengths_weaknesses(self, analysis: Dict):
        """Обновление подтвержденных сильных/слабых сторон (без изменений)"""
        strengths = analysis.get('strengths_shown', [])
        
        for strength in strengths:
            if strength not in self.profile.confirmed_strengths:
                self.profile.confirmed_strengths.append(strength)
        
        tech_score = analysis.get('technical_score', 0)
        weak_threshold = AdaptiveInterviewConfig.DIFFICULTY_ADAPTATION['weak_answer_threshold']
        if tech_score <= weak_threshold - 1:
            weakness = f"слабые знания в текущей области (оценка {tech_score}/10)"
            if weakness not in self.profile.confirmed_weaknesses:
                self.profile.confirmed_weaknesses.append(weakness)
    
    def _update_learning_indicators(self, analysis: Dict):
        """Отслеживание индикаторов обучаемости (без изменений)"""
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
        """Сбор красных флагов (без изменений)"""
        red_flags = analysis.get('red_flags', [])
        
        for flag in red_flags:
            if flag not in self.profile.red_flags:
                self.profile.red_flags.append(flag)
    
    def get_recommended_phase(self, current_phase: str, questions_in_phase: int) -> str:
        """Рекомендация следующей фазы (без изменений)"""
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
        """УЛУЧШЕННАЯ рекомендация по корректировке сложности вопросов"""
        avg_tech = self.profile.avg_technical_score
        config = AdaptiveInterviewConfig.DIFFICULTY_ADAPTATION
        
        if avg_tech < config['weak_answer_threshold'] and current_difficulty != "easy":
            self.profile.adaptation_history.append("difficulty_decreased_to_easy")
            return "easy"
        elif avg_tech > config['strong_answer_threshold'] and current_difficulty != "hard":
            self.profile.adaptation_history.append("difficulty_increased_to_hard") 
            return "hard"
        elif config['weak_answer_threshold'] <= avg_tech <= config['strong_answer_threshold'] and current_difficulty != "medium":
            self.profile.adaptation_history.append("difficulty_adjusted_to_medium")
            return "medium"
        
        return current_difficulty
    
    def should_avoid_area(self, area: str) -> bool:
        """НОВОЕ: Стоит ли избегать эту область"""
        return (
            area in self.profile.failed_areas or
            self.profile.question_types_asked[area] >= 3
        )
    
    def get_recommended_areas(self, available_areas: List[str]) -> List[str]:
        """НОВОЕ: Получить рекомендуемые области для вопросов"""
        recommendations = []
        
        for area in available_areas:
            if area in self.profile.strong_areas and not self.should_avoid_area(area):
                recommendations.append(area)
        
        for area in available_areas:
            if area not in recommendations and self.profile.question_types_asked[area] == 0:
                recommendations.append(area)
        
        for area in available_areas:
            if area not in recommendations and not self.should_avoid_area(area):
                recommendations.append(area)
        
        return recommendations
    
    def get_priority_concerns(self) -> List[str]:
        """Получить приоритетные concerns для проверки (без изменений)"""
        unchecked_concerns = []
        
        for concern in self.profile.hr_concerns:
            concern_addressed = any(
                concern.lower() in strength.lower() 
                for strength in self.profile.confirmed_strengths
            )
            
            if not concern_addressed:
                unchecked_concerns.append(concern)
        
        return unchecked_concerns[:3]
    
    def get_context_for_prompt(self) -> Dict:
        """РАСШИРЕННАЯ подготовка контекста профиля для промптов"""
        base_context = {
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
        
        base_context.update({
            'failed_areas': list(self.profile.failed_areas),
            'strong_areas': list(self.profile.strong_areas),
            'question_frequency': dict(self.profile.question_types_asked),
            'adaptation_history': self.profile.adaptation_history[-3:],
            'areas_to_avoid': [area for area in self.profile.question_types_asked.keys() if self.should_avoid_area(area)]
        })
        
        return base_context
    
    def generate_final_summary(self) -> Dict:
        """РАСШИРЕННАЯ генерация финального резюме профиля"""
        base_summary = {
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
        
        base_summary['advanced_analytics'] = {
            'failed_areas_count': len(self.profile.failed_areas),
            'strong_areas_count': len(self.profile.strong_areas),
            'most_questioned_area': self.profile.question_types_asked.most_common(1)[0] if self.profile.question_types_asked else None,
            'adaptation_count': len(self.profile.adaptation_history),
            'coverage_completeness': len(self.profile.area_scores) / max(len(self.profile.hr_concerns) + 2, 4),
            'consistency_score': self._calculate_consistency_score()
        }
        
        return base_summary
    
    def _calculate_consistency_score(self) -> float:
        """НОВОЕ: Расчет консистентности ответов кандидата"""
        if len(self.profile.area_scores) < 2:
            return 1.0
        
        all_scores = []
        for scores_list in self.profile.area_scores.values():
            all_scores.extend(scores_list)
        
        if len(all_scores) < 3:
            return 1.0
        
        mean_score = sum(all_scores) / len(all_scores)
        variance = sum((score - mean_score) ** 2 for score in all_scores) / len(all_scores)
        std_dev = variance ** 0.5
        
        consistency = max(0, 1 - (std_dev / 5))
        
        return round(consistency, 2)