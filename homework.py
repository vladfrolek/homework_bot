import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import TokenError


load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет значения переменных окружения."""
    tokens = (
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID'
    )
    empty_tokens = [token for token in tokens if not globals()[token]]
    if empty_tokens:
        msg = f'Отсутсвует переменная окружения {empty_tokens}'
        logger.critical(msg)
        raise TokenError(msg)


def send_message(bot, text):
    """Отправляет сообщение в ТГ."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text)
    except telegram.TelegramError:
        logger.error('Ошибка при отправке сообщения в телеграмм')
    else:
        logger.debug("Cообщение отправлено")


def get_api_answer(timestamp):
    """Получает ответ API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            raise requests.RequestException('Endpoint недоступен')
        if not response.json():
            raise requests.exceptions.InvalidJSONError
        else:
            return response.json()
    except requests.RequestException:
        raise ConnectionError('Сбой при запросе к эндпоинту')


def check_response(response):
    """Проверяет ответ API на соответствие структур данных."""
    if not isinstance(response, dict):
        raise TypeError('Not dict')
    if 'current_date' not in response:
        logger.warning('Key "current_date" not found')
    if not isinstance(response.get('current_date'), int):
        logger.warning('not int')
    if 'homeworks' not in response:
        raise KeyError('Key "homeworks" not found')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('not list')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    status = homework.get('status')
    if not status:
        raise KeyError('Неожиданный статус домашней работы')
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Неожиданный статус домашней работы')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise ValueError('Неожиданный статус домашней работы')
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
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s - %(name)s - %(levelname)s - line %(lineno)s - '
                '%(funcName)s - %(message)s'),
        level=logging.DEBUG
    )
    logging.StreamHandler(sys.stdout)
    try:
        main()
    except KeyboardInterrupt:
        print('Interruption')
