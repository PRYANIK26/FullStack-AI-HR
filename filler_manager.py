
import random
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict

class FillerManager:
    """
    Управляет выбором и предоставлением контекстно-зависимых 
    фраз-заполнителей, используя систему взвешенных оценок.
    """

    def __init__(self):
        self.categories_priority: Dict[str, int] = {
            'CLARIFYING': 1,
            'SUPPORTIVE': 2,
            'ENCOURAGING_SHORT': 3,
            'ACKNOWLEDGING_LONG': 3,
            'ENCOURAGING_POSITIVE': 4,
            'NEUTRAL': 5
        }
        
        self.keywords_weights: List[Tuple[str, Set[str], int]] = [
            ('SUPPORTIVE', {'не знаю', 'не уверен', 'сложно сказать', 'затрудняюсь', 'не помню', 'не сталкивался', 'не приходилось', 'не могу сказать'}, 10),
            ('CLARIFYING', {'повторите', 'не расслышал', 'имеете в виду', 'правильно ли я', 'уточнить'}, 8),
            ('ENCOURAGING_POSITIVE', {'конечно', 'разумеется', 'успешно', 'справился', 'улучшил', 'оптимизировал', 'достиг', 'реализовал', 'внедрил'}, 5)
        ]
        
        self.phrases: Dict[str, List[str]] = {
            'NEUTRAL': ["Так, поняла. Секунду, пожалуйста", "Хорошо, спасибо. Секунду, пожалуйста", "Так, ясно. Секунду, пожалуйста", "Принято. Секунду, пожалуйста", "Секундочку..."],
            'SUPPORTIVE': ["Ничего страшного, это непростой вопрос. Дайте мне момент.", "Понимаю, не волнуйтесь. Давайте двигаться дальше. Секунду, пожалуйста", "Спасибо за честность, это тоже важный показатель. Секунду.", "Хорошо, пропустим этот момент. Обдумываю следующий шаг."],
            'ENCOURAGING_POSITIVE': ["Отличный пример, спасибо! Сейчас сформулирую следующий вопрос.", "Звучит убедительно. Мне нужно мгновение, чтобы это обработать.", "Именно это я и хотела услышать. Дайте подумать.", "Впечатляет. Хорошо, секунду."],
            'ENCOURAGING_SHORT': ["Поняла. Сейчас подумаю, как лучше раскрыть эту тему.", "Хорошо. Секунду, пожалуйста.", "Краткость - сестра таланта. Так, дайте мне момент."],
            'ACKNOWLEDGING_LONG': ["Спасибо за такой развернутый ответ. Мне нужно время, чтобы всё учесть.", "Очень подробно, благодарю. Обрабатываю информацию.", "Я вас услышала. Много интересных деталей, секунду."],
            'CLARIFYING': ["Да, конечно, сейчас переформулирую.", "Без проблем. Следующий вопрос будет другим.", "Поняла ваш вопрос. Секунду."]
        }
        
        self.length_thresholds = { 'very_short': 50, 'long': 500 }
        self.length_bonus_points = 3

    def _analyze_text(self, text: str) -> str:
        """
        Анализирует текст ответа, используя систему очков,
        и возвращает категорию-победителя.
        """
        lower_text = text.lower()
        scores = defaultdict(int)
        
        for category, keywords, weight in self.keywords_weights:
            found_count = sum(1 for keyword in keywords if re.search(r'\b' + re.escape(keyword) + r'\b', lower_text))
            if found_count > 0:
                scores[category] += found_count * weight

        text_len = len(text)
        if text_len < self.length_thresholds['very_short']:
            scores['ENCOURAGING_SHORT'] += self.length_bonus_points
        if text_len > self.length_thresholds['long']:
            scores['ACKNOWLEDGING_LONG'] += self.length_bonus_points
            
        if not scores:
            return 'NEUTRAL'
            
        max_score = max(scores.values())
        
        top_categories = [category for category, score in scores.items() if score == max_score]
        
        if len(top_categories) > 1:
            winner = sorted(top_categories, key=lambda cat: self.categories_priority[cat])[0]
            return winner
        else:
            return top_categories[0]

    def get_phrase(self, user_answer: str) -> str:
        """
        Основной метод. Получает ответ пользователя, анализирует его
        и возвращает подходящую фразу-заполнитель.
        """
        if not user_answer or not user_answer.strip():
            category = 'NEUTRAL'
        else:
            category = self._analyze_text(user_answer)
        
        selected_phrase = random.choice(self.phrases[category])
        
        print(f"💬 FillerManager: Ответ определен как '{category}'. Выбрана фраза: '{selected_phrase}'")
        
        return selected_phrase