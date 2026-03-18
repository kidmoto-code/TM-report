import os
import time
import requests
from bs4 import BeautifulSoup as BS
from functools import wraps
from typing import Optional, Tuple, List, Dict, Any


def retry(attempts: int = 3, delay: int = 6):
    """
    Декоратор для повторного выполнения функции при возникновении ошибок.

    :param attempts: Количество попыток (по умолчанию 3)
    :param delay: Задержка между попытками в секундах (по умолчанию 6)
    :return: Результат выполнения функции или исключение
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < attempts - 1:
                        time.sleep(delay)
            raise last_exception if last_exception else Exception("Unknown error")
        return wrapper
    return decorator


class GetHTML:
    """
    Базовый класс для получения HTML-данных с сайта ФИПС.
    """
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.102 Safari/537.36 Edg/104.0.1293.63'

    def __init__(self, number: str, casetype: str):
        """
        Инициализация объекта для работы с ФИПС.

        :param number: Номер патента/заявки
        :param casetype: Тип объекта ИС ('PAT', 'DE', 'PM', 'TM', 'TMAP')
        """
        self.number = number
        self.casetype = casetype.upper()

    def check_casetype(self) -> bool:
        """Проверяет корректность типа объекта ИС."""
        return self.casetype in ['PAT', 'DE', 'PM', 'TM', 'TMAP']

    def get_url(self) -> str:
        """Формирует URL для запроса к ФИПС."""
        return f'https://www1.fips.ru/registers-doc-view/fips_servlet?DB=RU{self.casetype}&DocNumber={self.number}&TypeFile=html'

    @retry(attempts=3, delay=6)
    def get_response(self, url: str) -> requests.models.Response:
        """
        Выполняет GET-запрос к указанному URL.

        :param url: URL для запроса
        :return: Объект Response
        :raises: RequestException при ошибках запроса
        """
        headers = {'User-Agent': self.user_agent}
        return requests.get(url, headers=headers, timeout=30)

    def get_soup(self, response: requests.models.Response) -> BS:
        """Создает объект BeautifulSoup из ответа сервера."""
        return BS(response.content, 'html.parser')


    @retry(attempts=3, delay=5)
    def _initialize(self) -> None:
        """Инициализация объекта с обработкой ошибок."""
        self.url = self.get_url()
        response = self.get_response(self.url)
        self._soup = self.get_soup(response)

        self._is_available = self._check_availability()
        self._is_valid = self._validate_data() if self._is_available else False

    # ==================== Проверки ====================
    def _check_availability(self) -> bool:
        """Проверяет доступность документа на сервере."""
        return 'Документ с данным номером отсутствует' not in self._soup.text

    def _validate_data(self) -> bool:
        """Проверяет валидность полученных данных."""
        pass


class TradeMark(GetHTML):
    """
    Класс для работы с товарными знаками в реестре ФИПС.
    Реализует повторные попытки при ошибках и проверку валидности данных.
    """

    # ==================== Инициализация ====================
    def __init__(self, number: str, casetype: str = 'TM'):
        """
        Инициализация объекта товарного знака.

        :param number: Номер товарного знака
        :param casetype: Тип дела (по умолчанию 'TM')
        :param max_retries: Максимальное количество попыток запроса
        :param retry_delay: Задержка между попытками в секундах
        """
        super().__init__(number, casetype)

        if not self.check_casetype():
            raise ValueError(f"Неподдерживаемый тип объекта: {self.casetype}")

        self._initialize()

    # ============== Переопределение валидации полученных данных ===========
    def _validate_data(self) -> bool:
        """Проверяет валидность полученных данных."""
        required_sections = [
            self._soup.find('td', id='BibR'),
            self._soup.find('td', id='BibL'),
            self._soup.find_all('p', class_='bib')
        ]

        test_fields = [
            self.applicationdate,
            self.registrationdate,
            self.holdername
        ]

        return all(required_sections) and all(test_fields)

    # ==================== Внутренние методы извлечения ====================
    def _get_imagelink(self) -> Optional[str]:
        """Извлекает ссылку на изображение товарного знака."""
        for link in self._soup.find_all('a', target='_blank'):
            href = link.get('href', '').lower()
            if any(ext in href for ext in ('jpg', 'png', 'jpeg')):
                return link.get('href')
        return None

    @retry(attempts=3, delay=10)
    def _save_image(self) -> None:
        """
        Сохраняет изображение товарного знака в папку images.
        Применен декоратор retry для повторных попыток при ошибках.

        :raises: ValueError если image_link не установлен
        :raises: requests.exceptions.RequestException при ошибках загрузки
        :raises: OSError при ошибках сохранения файла
        """
        if not self.imagelink:
            raise ValueError("Ссылка на изображение не найдена")

        # Создаем папку images если ее нет
        os.makedirs('images', exist_ok=True)

        # Формируем путь для сохранения
        self._image_path = os.path.join('images', f'{self.number}.jpg')

        # Загружаем и сохраняем изображение
        response = requests.get(self.imagelink, stream=True, timeout=30)
        response.raise_for_status()

        with open(self._image_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

    def _get_applicationdate(self) -> Optional[str]:
        """Извлекает дату подачи заявки."""
        for info in self._soup.find('td', id='BibR').find_all('p'):
            if '(220)' in info.text:
                return info.text.strip()[26:].split('\n')[0].strip()
        return None

    def _get_registrationdate(self) -> Optional[str]:
        """Извлекает дату регистрации."""
        for info in self._soup.find('td', id='BibR').find_all('p'):
            if '(151)' in info.text:
                return info.text.split(': ')[1].strip()
        return None

    def _get_holdername(self) -> Optional[str]:
        """Извлекает имя правообладателя и адрес."""
        holders = []
        for info in self._soup.find_all('p', class_='bib'):
            if '(732)' in info.text:
                holders.append(info.text.strip())
        return holders[-1][6:].replace('\n\n', ' ').strip() if holders else None

    def _get_representative(self) -> Optional[str]:
        """Извлекает имя представителя и адрес для переписки."""
        representatives = []
        for info in self._soup.find_all('p', class_='bib'):
            if '(750)' in info.text:
                representatives.append(info.text.strip())
        return representatives[-1][6:].replace('\n\n', ' ').strip() if representatives else None

    def _get_MKTU(self) -> Tuple[List[str], List[str]]:
        """Извлекает классы МКТУ и их номера."""
        classes = []
        classes_numbers = []

        try:
            mktu_section = [c for c in self._soup.find_all('p', class_='bib') if '(511)' in c.text][0]
            for mktu in mktu_section.find_all('b'):
                class_text = mktu.text.split('.')[0].replace('\n\t\t\t', '').strip()
                classes.append(class_text)
                classes_numbers.append(class_text[:2])
        except (IndexError, AttributeError):
            pass

        return classes, classes_numbers

    def _get_unprotected(self) -> Optional[str]:
        """Извлекает неохраняемые элементы товарного знака."""
        for info in self._soup.find_all('p', class_='bib'):
            if '(526)' in info.text:
                parts = info.text.strip()[6:].split('\n')
                return parts[2].strip() if len(parts) > 2 else None
        return None

    def _get_validity(self) -> Optional[str]:
        """Извлекает дату истечения срока действия."""
        validity_list = []

        for info in self._soup.find_all('p', class_='bib'):
            if '(186)' in info.text:
                validity_list.append(info.text.strip()[-10:])

        if validity_list:
            return validity_list[-1]

        for info in self._soup.find('td', id='BibL').find_all('p'):
            if '(181)' in info.text:
                return info.text.strip()[-10:]

        return None

    # ==================== Публичные свойства ====================
    @property
    def is_available(self) -> bool:
        """Возвращает True если документ существует на сервере ФИПС."""
        return self._is_available

    @property
    def is_valid(self) -> bool:
        """Возвращает True если документ содержит все необходимые данные."""
        return self._is_valid

    @property
    def imagelink(self) -> Optional[str]:
        """Ссылка на изображение товарного знака."""
        if not hasattr(self, '_imagelink'):
            self._imagelink = self._get_imagelink() if self._soup else None
        return self._imagelink

    @property
    def image_path(self) -> Optional[str]:
        """
        Полный путь к сохраненному изображению товарного знака.
        None если изображение не было сохранено.
        """
        if not hasattr(self, '_image_path'):
            self._save_image()
        return getattr(self, '_image_path', None)

    @property
    def applicationdate(self) -> Optional[str]:
        """Дата подачи заявки."""
        if not hasattr(self, '_applicationdate'):
            self._applicationdate = self._get_applicationdate() if self._soup else None
        return self._applicationdate

    @property
    def registrationdate(self) -> Optional[str]:
        """Дата регистрации."""
        if not hasattr(self, '_registrationdate'):
            self._registrationdate = self._get_registrationdate() if self._soup else None
        return self._registrationdate

    @property
    def holdername(self) -> Optional[str]:
        """Правообладатель и адрес."""
        if not hasattr(self, '_holdername'):
            self._holdername = self._get_holdername() if self._soup else None
        return self._holdername

    @property
    def representative(self) -> Optional[str]:
        """Представитель и адрес для переписки."""
        if not hasattr(self, '_representative'):
            self._representative = self._get_representative() if self._soup else None
        return self._representative

    @property
    def classes(self) -> Tuple[List[str], List[str]]:
        """Кортеж (полные классы МКТУ, номера классов)."""
        if not hasattr(self, '_classes'):
            self._classes = self._get_MKTU() if self._soup else ([], [])
        return self._classes

    @property
    def classes_numbers(self) -> List[str]:
        """Список номеров классов МКТУ."""
        return self.classes[1]

    @property
    def unprotected(self) -> Optional[str]:
        """Неохраняемые элементы товарного знака."""
        if not hasattr(self, '_unprotected'):
            self._unprotected = self._get_unprotected() if self._soup else None
        return self._unprotected

    @property
    def validity(self) -> Optional[str]:
        """Дата истечения срока действия."""
        if not hasattr(self, '_validity'):
            self._validity = self._get_validity() if self._soup else None
        return self._validity

    # ==================== Дополнительные методы ====================
    def to_dict(self) -> Dict[str, Any]:
        """
        Возвращает все данные в виде словаря.

        :return: Словарь с данными о товарном знаке
        """
        return {
            'number': self.number,
            'type': self.casetype,
            'is_available': self.is_available,
            'is_valid': self.is_valid,
            'imagelink': self.imagelink,
            'application_date': self.applicationdate,
            'registration_date': self.registrationdate,
            'holder_name': self.holdername,
            'representative': self.representative,
            'classes': self.classes[0],
            'classes_numbers': self.classes_numbers,
            'unprotected_elements': self.unprotected,
            'validity_date': self.validity
        }


class Application(TradeMark):
    """
    Класс для работы с заявками на товарные знаки в реестре ФИПС.
    Реализует повторные попытки при ошибках и проверку валидности данных.
    """

    # ==================== Инициализация ====================
    def __init__(self, number: str, casetype: str = 'TMAP'):
        """
        Инициализация объекта товарного знака.

        :param number: Номер заявки
        :param casetype: Тип дела (по умолчанию 'TMAP')
        :param max_retries: Максимальное количество попыток запроса
        :param retry_delay: Задержка между попытками в секундах
        """
        super().__init__(number, casetype)


    # ======= Переопределение внутренних методов извлечения =========
    def _get_applicationdate(self) -> Optional[str]:
        """Извлекает дату подачи заявки."""
        for info in self._soup.find('td', id='BibR').find_all('p'):
            if '(200)' in info.text:
                return info.text.strip()[31:]
        return None

    def _get_holdername(self) -> Optional[str]:
        """Извлекает имя правообладателя и адрес."""
        holders = []
        for info in self._soup.find_all('p', class_='bib'):
            if '(731)' in info.text:
                holders.append(info.text.strip())
        return holders[-1][6:].replace('\n\n', ' ').strip() if holders else None
