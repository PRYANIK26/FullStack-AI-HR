import os
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()

class Config:
    # OpenAI API
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-4o-mini"  # Замени на gpt-5-nano когда будет доступен
    
    # STT настройки
    STT_MODEL = "large-v2"
    STT_REALTIME_MODEL = "small"
    STT_LANGUAGE = None  # Автоопределение
    SILENCE_TIMEOUT = 2  # Секунд до обработки
    
    # TTS настройки  
    TTS_VOICE = "ru-RU-SvetlanaNeural"
    TTS_RATE = 30
    TTS_PITCH = 0
    TTS_VOLUME = 0
    
    # Системные промпты
    SYSTEM_PROMPT = """Ты голосовой помощник. Отвечай кратко и по делу на русском языке. 
Твои ответы будут озвучены, поэтому избегай сложных форматирований, списков и символов.
Говори естественно, как в живом разговоре."""
    
    # Streaming настройки
    SENTENCE_ENDINGS = ['.', '!', '?', '...', '…']
    MIN_SENTENCE_LENGTH = 3  # Минимальная длина предложения для TTS
    MAX_CHUNK_WAIT_TIME = 2.0  # Максимальное время ожидания следующего чанка
    
    # История
    MAX_HISTORY_MESSAGES = 100  # Максимум сообщений в истории

    # Виртуальные аудиоустройства
    VIRTUAL_CABLE_A_OUTPUT = "CABLE-A Output"    # Откуда бот слушает Chrome
    VIRTUAL_CABLE_B_INPUT = "CABLE-B Input"      # Куда бот говорит в Chrome
    USE_VIRTUAL_AUDIO = False

class AdaptiveInterviewConfig(Config):
    """Расширенная конфигурация для адаптивного интервью"""
    
    # Настройки времени интервью
    MAX_INTERVIEW_TIME_MINUTES = 15
    MIN_INTERVIEW_TIME_MINUTES = 5
    MAX_QUESTIONS_PER_INTERVIEW = 15
    MIN_QUESTIONS_PER_INTERVIEW = 5

    SOFT_SKILLS_TIME_THRESHOLDS = {
        'critical': 2,  # минут, когда остается время только на 1 вопрос
        'low': 3       # минут, когда остается время на 2 вопроса
    }
    
    # Настройки фаз интервью
    PHASE_SETTINGS = {
        'exploration': {
            'min_questions': 2,
            'max_questions': 4,
            'target_duration_minutes': 5,
            'preferred_difficulty': 'medium'
        },
        'validation': {
            'min_questions': 2,
            'max_questions': 5,
            'target_duration_minutes': 8,
            'preferred_difficulty': 'medium'
        },
        'stress_test': {
            'min_questions': 1,
            'max_questions': 3,
            'target_duration_minutes': 6,
            'preferred_difficulty': 'hard'
        },
        'soft_skills': {
            'min_questions': 2,
            'max_questions': 4,
            'target_duration_minutes': 5,
            'preferred_difficulty': 'medium'
        },
        'wrap_up': {
            'min_questions': 1,
            'max_questions': 2,
            'target_duration_minutes': 1,
            'preferred_difficulty': 'easy'
        }
    }
    
    # Пороги для определения уровня кандидата
    CANDIDATE_LEVEL_THRESHOLDS = {
        'junior': {
            'max_technical_score': 5.0,
            'max_experience_score': 4.0,
            'required_questions': 3
        },
        'middle': {
            'min_technical_score': 4.0,
            'max_technical_score': 7.5,
            'min_experience_score': 4.0,
            'required_questions': 3
        },
        'senior': {
            'min_technical_score': 7.0,
            'min_experience_score': 6.0,
            'required_questions': 3
        }
    }
    
    # Настройки адаптации сложности
    DIFFICULTY_ADAPTATION = {
        'consecutive_weak_threshold': 2,    # после 2 слабых ответов упрощаем
        'consecutive_strong_threshold': 2,  # после 2 сильных ответов усложняем
        'weak_answer_threshold': 4.0,      # оценка ≤ 4 считается слабой
        'strong_answer_threshold': 8.0,    # оценка ≥ 8 считается сильной
        'adaptation_smoothing': 0.3        # фактор сглаживания адаптации
    }
    
    # Настройки переходов между фазами
    PHASE_TRANSITION_RULES = {
        'exploration_to_validation': {
            'min_questions': 2,
            'level_determined': True,
            'fallback_after_questions': 4
        },
        'validation_to_stress_test': {
            'min_avg_score': 6.0,
            'min_questions': 2,
            'no_critical_red_flags': True
        },
        'validation_to_soft_skills': {
            'max_avg_score': 6.0,  # если не прошел в stress_test
            'min_questions': 3
        },
        'stress_test_to_soft_skills': {
            'min_questions': 1,
            'always_transition': True
        },
        'soft_skills_to_wrap_up': {
            'min_questions': 2,
            'always_transition': True
        }
    }
    
    # Критерии завершения интервью
    INTERVIEW_COMPLETION_CRITERIA = {
        'max_time_exceeded': True,
        'max_questions_reached': True,
        'all_phases_completed': True,
        'critical_red_flags_count': 8,     # автозавершение при 5+ красных флагах
        'candidate_stress_level': 'high'   # завершение при высоком стрессе
    }
    
    # Настройки обратной связи и эмоциональных реакций
    EMOTIONAL_RESPONSES = {
        'supportive_phrases': [
            "Понимаю, это сложный вопрос. Попробуем подойти с другой стороны...",
            "Не волнуйтесь, давайте разберем это по шагам...",
            "Отлично, что вы честно говорите о своих пробелах. Это показывает зрелость.",
        ],
        'encouraging_phrases': [
            "Отличное направление мысли! Продолжайте...",
            "Именно так! Расскажите больше об этом опыте...",
            "Вы на правильном пути. Какие еще варианты решения видите?",
        ],
        'challenging_phrases': [
            "Интересно. А как бы вы решали это в production среде?",
            "Хорошо. Теперь более сложная задача...",
            "А что, если нагрузка увеличится в 10 раз?",
        ],
        'redirecting_phrases': [
            "Давайте сфокусируемся на практической стороне...",
            "Вернемся к конкретной реализации...",
            "Хорошо, попробуем другой подход...",
        ]
    }
    
    # Приоритеты областей проверки по типам вакансий
    VACANCY_FOCUS_AREAS = {
        'frontend': [
            'technical_basics',  # JS, React, CSS
            'practical_experience',  # проекты
            'problem_solving',   # алгоритмы
            'soft_skills'       # командная работа
        ],
        'backend': [
            'technical_basics',  # языки, фреймворки
            'system_design',    # архитектура
            'problem_solving',  # алгоритмы
            'practical_experience'  # опыт
        ],
        'fullstack': [
            'technical_basics',
            'practical_experience',
            'system_design',
            'soft_skills'
        ],
        'mobile': [
            'technical_basics',  # iOS/Android
            'practical_experience',
            'problem_solving',
            'soft_skills'
        ],
        'devops': [
            'system_design',    # инфраструктура
            'technical_basics', # инструменты
            'problem_solving',  # troubleshooting
            'soft_skills'      # коммуникация с командами
        ],
        'qa': [
            'technical_basics', # тестирование
            'problem_solving',  # поиск багов
            'practical_experience',
            'soft_skills'
        ]
    }
    
    # Ключевые слова для определения типа вакансии
    VACANCY_TYPE_KEYWORDS = {
        'frontend': ['frontend', 'фронтенд', 'react', 'vue', 'angular', 'javascript', 'js', 'css', 'html'],
        'backend': ['backend', 'бэкенд', 'python', 'java', 'node', 'api', 'database', 'server'],
        'fullstack': ['fullstack', 'фулстек', 'полный стек'],
        'mobile': ['mobile', 'мобил', 'ios', 'android', 'react native', 'flutter'],
        'devops': ['devops', 'девопс', 'docker', 'kubernetes', 'aws', 'ci/cd', 'infrastructure'],
        'qa': ['qa', 'тестиров', 'test', 'quality assurance']
    }
    
    # Настройки интеграции с HR-анализом
    HR_ANALYSIS_INTEGRATION = {
        'max_concerns_to_address': 3,       # максимум concerns для проверки
        'concern_validation_questions': 2,   # вопросов на каждый concern
        'strength_validation_questions': 1,  # вопросов на каждую strength
        'concern_priority_boost': 2.0,      # приоритет concern-вопросов
        'fallback_plan_areas': [            # если HR-анализ недоступен
            'general_background',
            'technical_basics', 
            'practical_experience',
            'soft_skills'
        ]
    }
    
    # Настройки профилирования кандидата
    CANDIDATE_PROFILING = {
        'confidence_calculation': {
            'questions_for_stable_average': 3,
            'smoothing_factor': 0.3,
            'outlier_threshold': 2.0  # стандартные отклонения
        },
        'learning_indicators': {
            'curiosity_keywords': ['интересно', 'хочу узнать', 'изучу', 'почитаю'],
            'adaptation_keywords': ['применю', 'попробую', 'использую'],
            'growth_keywords': ['развиваюсь', 'учусь', 'изучаю', 'планирую']
        },
        'red_flag_patterns': {
            'blame_shifting': ['не моя вина', 'команда виновата', 'заказчик не понимал'],
            'overconfidence': ['это просто', 'легко делается', 'все знаю'],
            'lack_of_growth': ['не нужно изучать', 'зачем это', 'работает и ладно']
        }
    }
    
    # Настройки отчетности
    REPORTING_CONFIG = {
        'score_weights': {
            'technical_score': 0.4,
            'communication_score': 0.2,
            'practical_experience': 0.2,
            'problem_solving': 0.1,
            'soft_skills': 0.1
        },
        'recommendation_thresholds': {
            'strong_hire': 80,      # >= 80 баллов
            'hire': 65,             # 65-79 баллов  
            'conditional_hire': 50, # 50-64 балла
            'no_hire': 0           # < 50 баллов
        },
        'red_flag_impact': {
            'critical': -20,        # критичные флаги
            'major': -10,          # серьезные флаги
            'minor': -5            # незначительные флаги
        }
    }
    
    @classmethod
    def get_phase_config(cls, phase_name: str) -> Dict:
        """Получить конфигурацию для фазы"""
        return cls.PHASE_SETTINGS.get(phase_name, cls.PHASE_SETTINGS['exploration'])
    
    @classmethod
    def determine_vacancy_type(cls, vacancy_title: str, industry: str = "") -> str:
        """Определить тип вакансии по названию и отрасли"""
        text = f"{vacancy_title} {industry}".lower()
        
        for vacancy_type, keywords in cls.VACANCY_TYPE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return vacancy_type
        
        return 'fullstack'  # default
    
    @classmethod
    def get_focus_areas_for_vacancy(cls, vacancy_type: str) -> List[str]:
        """Получить приоритетные области для типа вакансии"""
        return cls.VACANCY_FOCUS_AREAS.get(vacancy_type, cls.VACANCY_FOCUS_AREAS['fullstack'])
    
    @classmethod
    def get_emotional_response(cls, response_type: str) -> str:
        """Получить эмоциональную реакцию по типу"""
        phrases = cls.EMOTIONAL_RESPONSES.get(f"{response_type}_phrases", [])
        if phrases:
            import random
            return random.choice(phrases)
        return "Понятно. Продолжим."
    
    @classmethod
    def should_transition_phase(cls, current_phase: str, phase_stats: Dict) -> bool:
        """Проверить, нужно ли переходить к следующей фазе"""
        transition_key = f"{current_phase}_transition"
        if transition_key in cls.PHASE_TRANSITION_RULES:
            rules = cls.PHASE_TRANSITION_RULES[transition_key]
            
            # Проверяем все условия
            for condition, value in rules.items():
                if condition == 'min_questions' and phase_stats.get('questions_asked', 0) < value:
                    return False
                elif condition == 'min_avg_score' and phase_stats.get('avg_score', 0) < value:
                    return False
                # Дополнительные условия можно добавить здесь
            
            return True
        
        return False