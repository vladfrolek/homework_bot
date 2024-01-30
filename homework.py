import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import HomeworkStatusError, TokenError, SendException


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 20
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logging.StreamHandler(sys.stdout)


def check_tokens():
    """Проверяет значения переменных окружения."""
    token_list = {
        'Токен Практикума': PRACTICUM_TOKEN,
        'Токен Телеграма': TELEGRAM_TOKEN,
        'Чат ID': TELEGRAM_CHAT_ID
    }
    for name, token in token_list.items():
        if not token:
            logging.critical('Отсутсвует обязательная переменная окружения')
            raise TokenError(f'{name} пустой')


def send_message(bot, text):
    """Отправляет сообщение в ТГ."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text)
        logging.debug("Cообщение отправлено")
    except SendException:
        logging.error('Сообщение не отправлено')


def get_api_answer(timestamp):
    """Получает ответ API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            logging.error('Endpoint недоступен')
            raise ConnectionError
        return response.json()
    except requests.RequestException:
        logging.error('Сбой при запросе к эндпоинту')


def check_response(response):
    """Проверяет ответ API на соответствие структур данных."""
    if not isinstance(response, dict):
        logging.error('Не ожидаемый ключ ответа')
        raise TypeError('Not dict')
    if 'homeworks' not in response:
        logging.error('Не ожидаемый ключ ответа')
        raise KeyError('Key "homeworks" not found')
    if not isinstance(response.get('homeworks'), list):
        logging.error('Не ожидаемый ключ ответа')
        raise TypeError('not list')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    status = homework.get('status')
    if not status:
        logging.error('Неожиданный статус домашней работы')
        raise KeyError
    homework_name = homework.get('homework_name')
    if not homework_name:
        logging.error('Неожиданный статус домашней работы')
        raise KeyError
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise HomeworkStatusError
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            homework = get_api_answer(timestamp)
            current_homework = check_response(homework)
            if current_homework:
                verdict = parse_status(current_homework[0])
                send_message(bot, verdict)
            timestamp = homework['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interruption')
