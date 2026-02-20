import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# URL твоей таблицы (ВСТАВЬ СВОЮ ССЫЛКУ СЮДА)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LDVw4oWi_8vBYR08FVqoM9YBexA98DTLHO2-BzS1WGk/edit?pli=1&gid=0#gid=0"


def get_google_sheet():
    """Подключается к Google Таблицам с помощью ключа из Render"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # Достаем секретный JSON из настроек Render
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS")

    if not creds_json_str:
        print("❌ ОШИБКА: Переменная GOOGLE_CREDENTIALS не найдена на сервере!")
        return None

    try:
        # Превращаем строку в словарь и авторизуемся
        creds_dict = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)

        # Открываем первый лист таблицы по ссылке
        sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1
        return sheet
    except Exception as e:
        print(f"❌ ОШИБКА подключения к Google Sheets: {e}")
        return None


def add_payment_record(phone_number, service_name="Доп. услуга", status="Оплачено"):
    """Добавляет новую строку в таблицу"""
    sheet = get_google_sheet()
    if sheet:
        # 1. Берем время сервера (UTC) и добавляем 5 часов (Казахстан)
        kz_time = datetime.now() + timedelta(hours=5)

        # 2. Меняем формат на привычный: День.Месяц.Год Часы:Минуты:Секунды
        formatted_time = kz_time.strftime("%d.%m.%Y %H:%M:%S")

        # Данные должны идти в том же порядке, что и твои столбцы:
        # Дата | Телефон | Услуга | Статус
        row_data = [formatted_time, f"+{phone_number}", service_name, status]

        # Добавляем строку в конец таблицы
        sheet.append_row(row_data)
        print(f"✅ Данные клиента +{phone_number} успешно записаны в Google Таблицу!")