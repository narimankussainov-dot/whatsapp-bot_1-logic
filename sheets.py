import os
import json
import gspread
from gspread.exceptions import CellNotFound  # <-- Добавили обработку ошибок поиска
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
    """Ищет клиента по номеру. Если есть - обновляет шаг. Если нет - создает новую строку."""
    sheet = get_google_sheet()
    if not sheet: return

    kz_time = datetime.now() + timedelta(hours=5)
    formatted_time = kz_time.strftime("%d.%m.%Y %H:%M:%S")

    # Очищаем номер на всякий случай
    phone_str = f"+{phone_number}".replace("++", "+")

    try:
        try:
            # Ищем клиента во втором столбце (Колонка B)
            cell = sheet.find(phone_str, in_column=2)

            # Если нашли — обновляем ячейки в этой строке
            sheet.update_cell(cell.row, 1, formatted_time)  # Дата и Время
            sheet.update_cell(cell.row, 3, branch)  # Ветка
            sheet.update_cell(cell.row, 4, step_description)  # Шаг
            print(f"🔄 CRM Обновлен: {phone_str} -> {step_description}")

        except CellNotFound:
            # Если не нашли (новый клиент) — добавляем новую строку
            sheet.append_row([formatted_time, phone_str, branch, step_description])
            print(f"✅ CRM Новый клиент: {phone_str} -> {step_description}")

    except Exception as e:
        print(f"❌ Ошибка записи в таблицу: {e}")