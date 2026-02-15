import requests
import time
import config
import messages

# ПАМЯТЬ
user_states = {}
last_check_sender = None


# --- ФУНКЦИИ ОТПРАВКИ (С УНИВЕРСАЛЬНЫМ КОСТЫЛЕМ) ---
def fix_phone_for_sandbox(phone_number):
    clean_phone = str(phone_number).replace("+", "").strip()
    if clean_phone.startswith("77") and len(clean_phone) == 11:
        return "787" + clean_phone[2:]
    return clean_phone


def send_whatsapp_media(phone_number, media_type, link=None, media_id=None, caption=None, filename=None):
    url = f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {config.ACCESS_TOKEN}", "Content-Type": "application/json"}
    final_phone = fix_phone_for_sandbox(phone_number)

    media_object = {}
    if link: media_object["link"] = link
    elif media_id: media_object["id"] = media_id
    if caption: media_object["caption"] = caption
    if filename and media_type == "document": media_object["filename"] = filename

    data = {"messaging_product": "whatsapp", "to": final_phone, "type": media_type, media_type: media_object}
    
    # --- ИЗМЕНЕНИЕ ---
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"❌ ОШИБКА МЕДИА: {response.status_code}")
        print(f"📄 ДЕТАЛИ: {response.text}")
    # -----------------


def send_whatsapp_message(phone_number, message):
    url = f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {config.ACCESS_TOKEN}", "Content-Type": "application/json"}
    final_phone = fix_phone_for_sandbox(phone_number)
    
    data = {"messaging_product": "whatsapp", "to": final_phone, "type": "text", "text": {"body": message}}
    
    # --- ИЗМЕНЕНИЕ: ЧИТАЕМ ОТВЕТ META ---
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"❌ ОШИБКА ОТПРАВКИ: {response.status_code}")
        print(f"📄 ДЕТАЛИ: {response.text}")
    else:
        print(f"✅ Сообщение отправлено: {response.status_code}")
    # ------------------------------------


# --- ФУНКЦИЯ ОТПРАВКИ В TELEGRAM ---
# Обновленная функция отправки (с проверкой токена)
def send_image_to_telegram(sender_id, media_id, caption_text):
    print(f"[DEBUG] 🚀 Начинаем отправку в Telegram для {sender_id}")

    # ПРОВЕРКА: Видит ли бот токен?
    if not config.TG_BOT_TOKEN or not config.TG_ADMIN_ID:
        print("[DEBUG] ❌ ОШИБКА: Нет токена Telegram или ID админа в конфиге!")
        return

    try:
        # 1. Получаем ссылку
        url_query = f"https://graph.facebook.com/{config.VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {config.ACCESS_TOKEN}"}

        print(f"[DEBUG] 1. Запрашиваем URL фото у Meta: {media_id}")
        response_url = requests.get(url_query, headers=headers)

        if response_url.status_code != 200:
            print(f"[DEBUG] ❌ Ошибка получения URL от Meta: {response_url.text}")
            return

        image_url = response_url.json().get("url")
        print(f"[DEBUG] 2. URL получен. Скачиваем байты...")

        # 2. Скачиваем
        image_data = requests.get(image_url, headers=headers).content
        print(f"[DEBUG] 3. Фото скачано ({len(image_data)} байт). Отправляем в TG...")

        # 3. Отправляем
        tg_url = f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendPhoto"
        full_caption = f"Check from +{sender_id}\nInfo: {caption_text}"

        files = {'photo': image_data}
        data = {'chat_id': config.TG_ADMIN_ID, 'caption': full_caption}

        tg_response = requests.post(tg_url, files=files, data=data)

        if tg_response.status_code == 200:
            print("[DEBUG] ✅ УСПЕХ! Фото в Telegram.")
        else:
            print(f"[DEBUG] ❌ Ошибка от Telegram: {tg_response.text}")

    except Exception as e:
        print(f"[DEBUG] ❌ КРИТИЧЕСКАЯ ОШИБКА в функции Telegram: {e}")
# -----------------------------------


# ==========================================
# 👮‍♂️ ЛОГИКА АДМИНИСТРАТОРА
# ==========================================
def process_admin_message(text):
    global last_check_sender
    text_lower = text.strip().lower()

    if not last_check_sender:
        send_whatsapp_message(config.ADMIN_PHONE, "Нет активных чеков на проверку.")
        return

    # Получаем текущий статус клиента, чтобы понять, из какой он ветки
    client_state = user_states.get(last_check_sender, "")

    # 1. АДМИН ОДОБРЯЕТ (+)
    if text_lower in ["+", "ок", "ok", "все нормально", "да"]:

        send_whatsapp_message(config.ADMIN_PHONE,
                              f"✅ Оплата клиента {last_check_sender} подтверждена! Отправляю оферту.")

        # Отправляем оферту клиенту
        send_whatsapp_media(last_check_sender, "document", link=messages.URL_PDF_OFFERTA,
                            caption=messages.MSG_OFFERTA_TEXT, filename=messages.NAME_PDF_OFFERTA)

        # РАЗВИЛКА: Ставим правильный статус ожидания ответа на оферту
        if client_state == "WAITING_ADMIN_ALLIANCE":
            user_states[last_check_sender] = "WAITING_OFFERTA_ALLIANCE"
        elif client_state == "WAITING_ADMIN_GUILD":
            user_states[last_check_sender] = "WAITING_OFFERTA_GUILD"

        last_check_sender = None

        # 2. АДМИН ОТКЛОНЯЕТ (Комментарий)
    else:
        send_whatsapp_message(config.ADMIN_PHONE, f"❌ Комментарий отправлен клиенту.")
        send_whatsapp_message(last_check_sender, f"{messages.MSG_PAYMENT_REJECTED} «{text}»")
        send_whatsapp_message(last_check_sender, "Пожалуйста, отправьте правильный чек.")
        # Статус клиента не меняем, он остается WAITING_ADMIN_... и может снова слать чек


# ==========================================
# 👤 ЛОГИКА ПОЛЬЗОВАТЕЛЯ
# ==========================================
def process_user_message(sender_id, text, message_type="text", media_id=None):
    global last_check_sender
    text_lower = text.strip().lower()

    if text_lower == "/reset":
        user_states[sender_id] = "START"
        send_whatsapp_message(sender_id, "🔄 Сброс.")
        return

    current_state = user_states.get(sender_id, "START")
    print(f"User: {sender_id} | State: {current_state}")

    # --- СТАРТ ---
    if current_state == "START":
        send_whatsapp_message(sender_id, messages.MSG_WELCOME)
        time.sleep(1)  # Короткая пауза для текста
        # Если нужно отправить Оферту в начале, раскомментируй:
        # send_whatsapp_media(sender_id, "document", link=messages.URL_PDF_OFFERTA, caption=messages.MSG_OFFERTA_TEXT, filename="Ofert.pdf")

        time.sleep(1)
        send_whatsapp_message(sender_id, messages.MSG_INSTRUCT)
        user_states[sender_id] = "WAITING_FOR_FORM"

    elif current_state == "WAITING_FOR_FORM":
        if any(w in text_lower for w in ["готово", "done", "+"]):
            send_whatsapp_message(sender_id, messages.MSG_AINASH_1)
            send_whatsapp_message(sender_id, messages.MSG_AINASH_2)
            user_states[sender_id] = "WAITING_FOR_STAFF_ANSWER"
        else:
            send_whatsapp_message(sender_id, "Напишите 'ГОТОВО'.")

    # --- ВЫБОР ВЕТКИ ---
    elif current_state == "WAITING_FOR_STAFF_ANSWER":
        if any(w in text_lower for w in ["да", "иә"]):
            # Ветка АЛЬЯНС
            send_whatsapp_media(sender_id, "image", link=messages.URL_IMG_ALLIANCE_1, caption=None)
            time.sleep(3)  # Ждем картинку
            send_whatsapp_media(sender_id, "image", link=messages.URL_IMG_ALLIANCE_2, caption=messages.MSG_ALLIANCE_INTRO)
            time.sleep(4)
            send_whatsapp_message(sender_id, messages.MSG_ALLIANCE_OFFER)
            user_states[sender_id] = "WAITING_FOR_ALLIANCE_DECISION"

        elif any(w in text_lower for w in ["нет", "жоқ"]):
            # Ветка ГИЛЬДИЯ
            send_whatsapp_media(sender_id, "image", link=messages.URL_IMG_GUILD_1, caption=None)
            time.sleep(3)
            send_whatsapp_media(sender_id, "image", link=messages.URL_IMG_GUILD_2, caption=messages.MSG_GUILD_INTRO)
            time.sleep(4)  # Ждем картинки
            send_whatsapp_message(sender_id, messages.MSG_GUILD_OFFER)
            user_states[sender_id] = "WAITING_FOR_GUILD_DECISION"
        else:
            send_whatsapp_message(sender_id, "ДА или НЕТ?")

    # --- СОГЛАСИЕ НА ОПЛАТУ ---
    elif current_state == "WAITING_FOR_ALLIANCE_DECISION":
        if any(w in text_lower for w in ["да", "иә"]):
            send_whatsapp_message(sender_id, messages.MSG_ALLIANCE_PAYMENT)
            user_states[sender_id] = "WAITING_FOR_ALLIANCE_PAYMENT"
        elif any(w in text_lower for w in ["нет", "жоқ"]):
            send_whatsapp_message(sender_id, messages.MSG_REFUSAL_LINK)
            user_states[sender_id] = "START"

    elif current_state == "WAITING_FOR_GUILD_DECISION":
        if any(w in text_lower for w in ["да", "иә"]):
            send_whatsapp_message(sender_id, messages.MSG_GUILD_PAYMENT)
            user_states[sender_id] = "WAITING_FOR_GUILD_PAYMENT"
        elif any(w in text_lower for w in ["нет", "жоқ"]):
            send_whatsapp_message(sender_id, messages.MSG_REFUSAL_LINK)
            user_states[sender_id] = "START"

    # --- СТАРЫЙ БЛОК КОДА ДЛЯ ПРОВЕРКИ ЧЕРЕЗ WHATSAPP
    # --- ПРИЕМ ЧЕКА И ОТПРАВКА АДМИНУ ---
    # elif current_state in ["WAITING_FOR_ALLIANCE_PAYMENT", "WAITING_FOR_GUILD_PAYMENT", "WAITING_ADMIN_ALLIANCE",
    #                        "WAITING_ADMIN_GUILD"]:
    #
    #     if message_type in ["image", "document"]:
    #         send_whatsapp_message(sender_id, messages.MSG_WAIT_FOR_ADMIN)
    #
    #         # Определяем, откуда пришел клиент
    #         is_alliance = "ALLIANCE" in current_state
    #
    #         branch_name = "АЛЬЯНС (VIP)" if is_alliance else "ГИЛЬДИЯ"
    #         send_whatsapp_message(config.ADMIN_PHONE,
    #                               f"🛎 ПРОВЕРКА ОПЛАТЫ!\nВетка: {branch_name}\nКлиент: {sender_id}\n\nНапишите '+', чтобы принять.")
    #
    #         if media_id:
    #             send_whatsapp_media(config.ADMIN_PHONE, message_type, media_id=media_id, caption="Чек клиента")
    #
    #         last_check_sender = sender_id
    #
    #         # Фиксируем статус ожидания админа (раздельный!)
    #         if is_alliance:
    #             user_states[sender_id] = "WAITING_ADMIN_ALLIANCE"
    #         else:
    #             user_states[sender_id] = "WAITING_ADMIN_GUILD"
    #     else:
    #         send_whatsapp_message(sender_id, "Пожалуйста, отправьте чек (картинку или PDF).")


    # --- ПРИЕМ ЧЕКА И ОТПРАВКА В TELEGRAM ---
    elif current_state in ["WAITING_FOR_ALLIANCE_PAYMENT", "WAITING_FOR_GUILD_PAYMENT",
                                   "WAITING_ADMIN_ALLIANCE", "WAITING_ADMIN_GUILD"]:

        print(f"[DEBUG] Мы внутри блока проверки оплаты. Тип сообщения: {message_type}")

        if message_type in ["image", "document"]:
            print(f"[DEBUG] Это картинка или документ. Media ID: {media_id}")

            send_whatsapp_message(sender_id, messages.MSG_WAIT_FOR_ADMIN)

            is_alliance = "ALLIANCE" in current_state
            branch_name = "АЛЬЯНС" if is_alliance else "ГИЛЬДИЯ"

            # ВЫЗЫВАЕМ ФУНКЦИЮ
            if media_id:
                send_image_to_telegram(sender_id, media_id, f"Ветка: {branch_name}")
            else:
                print("[DEBUG] ❌ ОШИБКА: Пришел документ, но нет media_id!")

            if is_alliance:
                user_states[sender_id] = "WAITING_ADMIN_ALLIANCE"
            else:
                user_states[sender_id] = "WAITING_ADMIN_GUILD"
        else:
            print(f"[DEBUG] Это НЕ картинка. Это: {text}")
            send_whatsapp_message(sender_id, "Пожалуйста, отправьте чек (картинку или PDF).")


    # --- ФИНАЛ: СОГЛАСИЕ С ОФЕРТОЙ И ПОДАРКИ ---
    elif current_state in ["WAITING_OFFERTA_ALLIANCE", "WAITING_OFFERTA_GUILD"]:

        # Определяем ветку
        is_alliance = "ALLIANCE" in current_state

        # 1. Поздравление
        msg_congrats = messages.MSG_ALLIANCE_CONGRATS if is_alliance else messages.MSG_GUILD_CONGRATS
        send_whatsapp_message(sender_id, msg_congrats)

        time.sleep(3)

        # 2. Подарки (РАЗНЫЕ!)
        if is_alliance:
            # === ПОДАРКИ ДЛЯ АЛЬЯНСА ===
            # Пример: Документ + Картинка (или как решишь в messages.py)
            send_whatsapp_media(sender_id, "document", link=messages.URL_GIFT_ALLIANCE_1,
                                caption="🎁 Ваш подарок", filename="Альянс резидентіне арналған сыйлық.pdf")
            time.sleep(2)
            send_whatsapp_media(sender_id, "document", link=messages.URL_GIFT_ALLIANCE_2,
                                caption="🎁 Ваш подарок", filename="Подарок для резидента Альянс")
        else:
            # === ПОДАРКИ ДЛЯ ГИЛЬДИИ ===
            send_whatsapp_media(sender_id, "document", link=messages.URL_GIFT_GUILD_1,
                                caption="🎁 Ваш подарок", filename="Гильдия резидентіне арналған сыйлық.pdf")
            time.sleep(2)
            send_whatsapp_media(sender_id, "document", link=messages.URL_GIFT_GUILD_2,
                                caption="🎁 Ваш подарок", filename="Подарок для резидента Гильдии.pdf")


        user_states[sender_id] = "START"
