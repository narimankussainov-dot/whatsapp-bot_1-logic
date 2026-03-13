import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# URL твоей таблицы
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LDVw4oWi_8vBYR08FVqoM9YBexA98DTLHO2-BzS1WGk/edit?pli=1&gid=0#gid=0"


def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json_str:
        return None
    try:
        creds_dict = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client.open_by_url(GOOGLE_SHEET_URL).sheet1
    except Exception as e:
        print(f"❌ ОШИБКА подключения к Google Sheets: {e}")
        return None


def update_client_progress(phone_number, branch, step_description):
    """Просто добавляет новую строку (лог) для каждого шага клиента."""
    sheet = get_google_sheet()
    if not sheet: return

    kz_time = datetime.now() + timedelta(hours=5)
    formatted_time = kz_time.strftime("%d.%m.%Y %H:%M:%S")

    # Очищаем номер на всякий случай
    phone_str = f"+{phone_number}".replace("++", "+")

    try:
        # Убрали поиск (findall). Теперь просто всегда добавляем новую строку!
        sheet.append_row([formatted_time, phone_str, branch, step_description])
        print(f"📝 Лог записан: {phone_str} | {branch} | {step_description}")

    except Exception as e:
        print(f"❌ Ошибка записи в таблицу: {e}")


def add_answer_to_last_step(phone_number, user_answer):
    """Находит самую последнюю запись клиента и добавляет его ответ в колонку E"""
    sheet = get_google_sheet()
    if not sheet: return

    phone_str = f"+{phone_number}".replace("++", "+")

    try:
        # Ищем все строки, где упоминается этот номер
        cells = sheet.findall(phone_str, in_column=2)

        if cells:
            # Берем САМУЮ ПОСЛЕДНЮЮ ячейку из найденных (это и есть текущий шаг клиента)
            last_cell = cells[-1]

            # Записываем ответ клиента в 5-ю колонку (E) этой же строки
            sheet.update_cell(last_cell.row, 5, user_answer)
            print(f"✍️ Ответ клиента записан: {phone_str} -> {user_answer}")

    except Exception as e:
        print(f"❌ Ошибка записи ответа в таблицу: {e}")