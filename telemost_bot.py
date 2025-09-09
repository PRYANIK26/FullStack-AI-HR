from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
import pickle
import os
import undetected_chromedriver as uc
import argparse
import json
import requests

class TelemostBot:
    def __init__(self, analysis_id: str, main_server_port: int = 5000, keep_alive_minutes=60):
        """
        Инициализация бота для создания конференций в Яндекс Телемост
        """
        self.driver = None
        self.conference_url = None
        self.cookies_file = "telemost_cookies.pkl"
        self.keep_alive_minutes = keep_alive_minutes
        self.analysis_id = analysis_id 
        self.main_server_url = f"http://localhost:{main_server_port}" 
        
    def setup_driver(self):
        """Настройка и запуск веб-драйвера Chrome с использованием undetected_chromedriver"""
        print("Запускаем защищенный браузер...")

        chrome_options = uc.ChromeOptions()

        prefs = {
            "profile.default_content_setting_values": {
                "media_stream_mic": 1,
                "media_stream_camera": 1,
                "media_stream": 1,
                "notifications": 2
            },
            "profile.content_settings.exceptions.media_stream_mic": {
                "https://telemost.yandex.ru,*": {
                    "last_modified": "13312394482235522",
                    "setting": 1
                }
            },
            "profile.content_settings.exceptions.media_stream_camera": {
                "https://telemost.yandex.ru,*": {
                    "last_modified": "13312394482235522", 
                    "setting": 1
                }
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument('--use-fake-ui-for-media-stream')
        chrome_options.add_argument('--autoplay-policy=no-user-gesture-required')

        self.driver = uc.Chrome(options=chrome_options, use_subprocess=True)
        
        self.driver.maximize_window()
        
    def save_cookies(self):
        """Сохранение куки в файл"""
        try:
            with open(self.cookies_file, "wb") as file:
                pickle.dump(self.driver.get_cookies(), file)
            print("Куки сохранены")
        except Exception as e:
            print(f"Не удалось сохранить куки: {e}")
    
    def load_cookies(self):
        """Загрузка куки из файла"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, "rb") as file:
                    cookies = pickle.load(file)
                    
                    current_url = self.driver.current_url
                    current_domain = current_url.split('/')[2]
                    
                    cookies_loaded = 0
                    for cookie in cookies:
                        try:
                            cookie_domain = cookie.get('domain', '')
                            
                            if (cookie_domain == current_domain or 
                                cookie_domain.endswith('.' + current_domain) or
                                current_domain.endswith(cookie_domain.lstrip('.')) or
                                'yandex.ru' in cookie_domain):
                                
                                self.driver.add_cookie(cookie)
                                cookies_loaded += 1
                                
                        except Exception:
                            continue
                    
                    if cookies_loaded > 0:
                        print(f"Куки загружены: {cookies_loaded} шт.")
                        return True
                    else:
                        print("Не удалось загрузить куки (несовместимые домены)")
                        return False
            else:
                print("Файл с куки не найден")
                return False
        except Exception as e:
            print(f"Ошибка загрузки куки: {e}")
            return False
    
    def delete_cookies(self):
        """Удаление файла с куки"""
        try:
            if os.path.exists(self.cookies_file):
                os.remove(self.cookies_file)
                print("Файл с куки удален")
        except Exception as e:
            print(f"Ошибка удаления куки: {e}")
    
    def handle_captcha(self):
        """Обработка капчи 'Я не робот'"""
        print("Обнаружена капча - обрабатываем...")
        
        captcha_handled = False
        
        try:
            captcha_checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.CheckboxCaptcha-Button"))
            )
            captcha_checkbox.click()
            print("Капча нажата (по CSS селектору)")
            time.sleep(3)
            captcha_handled = True
            
        except (TimeoutException, NoSuchElementException):
            print("Не удалось найти элемент капчи по CSS, пробуем другие способы...")
        
        if not captcha_handled:
            try:
                captcha_checkbox = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-labelledby="checkbox-label"]'))
                )
                captcha_checkbox.click()
                print("Капча нажата (по aria-labelledby)")
                time.sleep(3)
                captcha_handled = True
                
            except (TimeoutException, NoSuchElementException):
                print("Не удалось найти элемент капчи по aria-labelledby...")
        
        if not captcha_handled:
            try:
                captcha_checkbox = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[role="checkbox"]'))
                )
                captcha_checkbox.click()
                print("Капча нажата (по role='checkbox')")
                time.sleep(3)
                captcha_handled = True
                
            except (TimeoutException, NoSuchElementException):
                print("Не удалось найти элемент капчи по role, пробуем координаты...")
        
        if not captcha_handled:
            try:
                x_coord = 637
                y_coord = 477
                
                actions = ActionChains(self.driver)
                actions.move_to_element(self.driver.find_element(By.TAG_NAME, "body")).perform()
                
                actions = ActionChains(self.driver)
                actions.move_by_offset(x_coord, y_coord).click().perform()
                
                print(f"Капча нажата (по координатам {x_coord}, {y_coord})")
                time.sleep(3)
                captcha_handled = True
                
            except Exception as e:
                print(f"Не удалось обработать капчу по координатам: {e}")
        
        return captcha_handled
    
    def wait_for_manual_login(self):
        """Ожидание ручного входа пользователя"""
        print("\n" + "="*60)
        print("ТРЕБУЕТСЯ РУЧНОЙ ВХОД")
        print("="*60)
        print("1. Войдите в свой аккаунт Яндекс в открытом браузере")
        print("2. Дойдите до главной страницы telemost.yandex.ru")
        print("3. Нажмите Enter в консоли когда будете готовы")
        print("="*60)
        
        input("Нажмите Enter когда войдете в аккаунт...")
        
        max_attempts = 30
        for attempt in range(max_attempts):
            current_url = self.driver.current_url
            print(f"Проверка {attempt + 1}: {current_url}")
            
            if "telemost.yandex.ru" in current_url and "passport" not in current_url:
                print("Отлично! Вы на странице Телемоста.")
                self.save_cookies()
                return True
            
            if re.match(r'https://telemost\.yandex\.ru/j/\d+', current_url):
                print("Отлично! Вы уже в конференции.")
                self.save_cookies()
                return True
                
            time.sleep(2)
        
        print("Не удалось определить, что вы вошли в систему.")
        return False
    
    def create_conference(self):
        """Попытка создать конференцию"""
        print("Пытаемся создать конференцию...")
        
        try:
            create_button = None
            
            try:
                create_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-test-id="create-call-button"]'))
                )
                print("Кнопка найдена по data-test-id")
            except TimeoutException:
                pass
            
            if not create_button:
                try:
                    create_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Создать видеовстречу')]]"))
                    )
                    print("Кнопка найдена по XPath")
                except TimeoutException:
                    pass
            
            if not create_button:
                try:
                    create_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'CreateCallButton')]"))
                    )
                    print("Кнопка найдена по классу")
                except TimeoutException:
                    pass
            
            if create_button:
                create_button.click()
                print("Кнопка 'Создать видеовстречу' нажата")
                
                start_time = time.time()
                timeout = 30
                
                while (time.time() - start_time) < timeout:
                    current_url = self.driver.current_url
                    
                    if "passport.yandex.ru" in current_url:
                        print("Куки невалидные - перенаправило на авторизацию")
                        return "invalid_cookies"
                    
                    if re.match(r'https://telemost\.yandex\.ru/j/\d+', current_url):
                        self.conference_url = current_url
                        print(f"КОНФЕРЕНЦИЯ СОЗДАНА!")
                        print(f"ССЫЛКА: {self.conference_url}")
                        self.save_cookies()
                        return "success"
                    
                    time.sleep(1)
                
                print("Превышено время ожидания создания конференции")
                return "timeout"
            else:
                print("Не удалось найти кнопку 'Создать видеовстречу'")
                return "button_not_found"
                
        except Exception as e:
            print(f"Ошибка при создании конференции: {e}")
            return "error"
        

    def _send_webhook_to_main_server(self, endpoint: str, payload: dict):
        """Отправляет вебхук на локальный main_server."""
        try:
            url = f"{self.main_server_url}{endpoint}"
            print(f"Отправка локального вебхука на {url}...")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("Локальный вебхук успешно отправлен.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"ОШИБКА: Не удалось отправить локальный вебхук: {e}")
            return False

    def monitor_conference(self):
        """Мониторит конференцию и запускает ассистента, когда кто-то подключится."""
        if not self.driver or not self.conference_url:
            print("Ошибка: Мониторинг невозможен, нет активной сессии браузера.")
            return

        print("\n" + "="*60)
        print("Бот в конференции. Перехожу в режим НАБЛЮДЕНИЯ.")
        print("Ожидаю подключения второго участника...")
        print("="*60)

        try:
            invite_text_xpath = "//*[contains(text(), 'Чтобы пригласить других участников')]"
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, invite_text_xpath))
            )
            print("Статус: Один участник в конференции (бот). Ожидание...")

            WebDriverWait(self.driver, 1800).until_not(
                EC.presence_of_element_located((By.XPATH, invite_text_xpath))
            )

            print("\n!!! ВТОРОЙ УЧАСТНИК ПОДКЛЮЧИЛСЯ !!!")
            print("Отправляю сигнал на запуск голосового ассистента...")

            self._send_webhook_to_main_server(
                endpoint="/webhook/start-assistant",
                payload={"analysis_id": self.analysis_id}
            )

        except TimeoutException:
            print("Таймаут ожидания: второй участник не подключился за 30 минут.")
        except Exception as e:
            print(f"Ошибка во время мониторинга: {e}")
        finally:
            print("Мониторинг завершен. Бот будет поддерживать сессию.")
            self.keep_alive()
    
    def run(self):
        """Основной метод: создает конференцию, отправляет вебхук и начинает мониторинг."""
        try:
            self.setup_driver()
            self.driver.get("https://telemost.yandex.ru/")
            time.sleep(3)

            if "showcaptcha" in self.driver.current_url:
                if self.handle_captcha():
                    self.driver.get("https://telemost.yandex.ru/")
                    time.sleep(3)
                else:
                    print("Капча не пройдена, просим ручной вход.")
            
            if self.load_cookies():
                print("Обновляем страницу с загруженными куки...")
                self.driver.refresh()
                time.sleep(5)
                
                result = self.create_conference()
                if result == "success":
                    self._send_webhook_to_main_server(
                        endpoint="/webhook/forward-invite",
                        payload={"analysis_id": self.analysis_id, "conference_url": self.conference_url}
                    )
                    self.monitor_conference()
                    return
                
                if result == "invalid_cookies":
                    self.delete_cookies()
            
            if self.wait_for_manual_login():
                if self.create_conference() == "success":
                    self._send_webhook_to_main_server(
                        endpoint="/webhook/forward-invite",
                        payload={"analysis_id": self.analysis_id, "conference_url": self.conference_url}
                    )
                    self.monitor_conference()
                    return

            print("ПРОВАЛ! Не удалось создать конференцию после всех попыток.")
            self.driver.quit()

        except Exception as e:
            print(f"Критическая ошибка в TelemostBot: {e}")
            if self.driver:
                self.driver.quit()


    def keep_alive(self):
        """Держит браузер открытым после успешного подключения."""
        if not self.driver: return
        
        print("\n" + "="*60)
        print("Бот в конференции. Соединение будет поддерживаться.")
        print(f"Сессия продлится {self.keep_alive_minutes} минут.")
        print("Нажмите Ctrl+C в этом окне, чтобы завершить сессию бота.")
        print("="*60)
        try:
            time.sleep(self.keep_alive_minutes * 60)
            print("Время сессии истекло.")
        except KeyboardInterrupt:
            print("\nСессия прервана вручную.")
        finally:
            self.driver.quit()
            print("Браузер закрыт.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yandex Telemost Observer Bot")
    parser.add_argument("--analysis-id", type=str, required=True, help="ID анализа для этого запуска")
    parser.add_argument("--port", type=int, default=5000, help="Порт локального main_server")
    parser.add_argument("--keep-alive", type=int, default=60, help="Время в минутах для поддержания сессии")
    args = parser.parse_args()

    print("Телемост Бот-Наблюдатель")
    print("="*50)
    
    bot = TelemostBot(
        analysis_id=args.analysis_id,
        main_server_port=args.port,
        keep_alive_minutes=args.keep_alive
    )
    bot.run()