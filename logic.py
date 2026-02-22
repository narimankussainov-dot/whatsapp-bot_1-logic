import requests
import time
import config
import messages
import sheets

# ПАМЯТЬ
user_states = {}
last_check_sender = None  # Тут будем помнить, кто прислал чек последним


# --- ФУНКЦИИ ОТПРАВКИ (С УНИВЕРСАЛЬНЫМ КОСТЫЛЕМ) ---
# def fix_phone_for_sandbox(phone_number):
#     clean_phone = str(phone_number).replace("+", "").strip()
#     if clean_phone.startswith("77") and len(clean_phone) == 11:
#         return "787" + clean_phone[2:]
#     return clean_phone


def send_whatsapp_media(phone_number, media_type, link=None, media_id=None, caption=None, filename=None):
    url = f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {config.ACCESS_TOKEN}", "Content-Type": "application/json"}
    # final_phone = fix_phone_for_sandbox(phone_number) # ЗАМЕНИ ЗДЕСЬ
    final_phone = str(phone_number).replace("+", "").strip()

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
    # final_phone = fix_phone_for_sandbox(phone_number) # ЗАМЕНИ ЗДЕСЬ
    final_phone = str(phone_number).replace("+", "").strip()
    
    data = {"messaging_product": "whatsapp", "to": final_phone, "type": "text", "text": {"body": message}}
    
    # --- ИЗМЕНЕНИЕ: ЧИТАЕМ ОТВЕТ META ---
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"❌ ОШИБКА ОТПРАВКИ: {response.status_code}")
        print(f"📄 ДЕТАЛИ: {response.text}")
    else:
        print(f"✅ Сообщение отправлено: {response.status_code}")
    # ------------------------------------


def send_whatsapp_buttons(phone_number, text, buttons):
    url = f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {config.ACCESS_TOKEN}", "Content-Type": "application/json"}
    final_phone = str(phone_number).replace("+", "").strip()

    buttons_json = []
    for i, title in enumerate(buttons):
        buttons_json.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}",
                "title": title[:20]  # Жесткое ограничение Meta: 20 символов
            }
        })

    data = {
        "messaging_product": "whatsapp",
        "to": final_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": buttons_json}
        }
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"❌ ОШИБКА КНОПОК: {response.status_code}\n📄 ДЕТАЛИ: {response.text}")


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
        full_caption = (f"🧾 <b>ЧЕК НА ПРОВЕРКУ</b>\n"
                        f"👤 Клиент: +{sender_id}\n"
                        f"ℹ️ {caption_text}\n\n"
                        f"<b>ЧТО ДЕЛАЕМ?</b>\n"
                        f"✅ <b>Принять:</b> отправь <code>+</code>\n"
                        f"⛔️ <b>Отказать:</b> отправь <code>-</code>\n"
                        f"💬 <b>Отказать с причиной:</b> отправь <code>- Не видно сумму</code>")

        files = {'photo': image_data}
        data = {'chat_id': config.TG_ADMIN_ID, 'caption': full_caption, 'parse_mode': 'HTML'}

        tg_response = requests.post(tg_url, files=files, data=data)

        if tg_response.status_code == 200:
            print("[DEBUG] ✅ УСПЕХ! Фото в Telegram.")
        else:
            print(f"[DEBUG] ❌ Ошибка от Telegram: {tg_response.text}")

    except Exception as e:
        print(f"[DEBUG] ❌ КРИТИЧЕСКАЯ ОШИБКА в функции Telegram: {e}")
# -----------------------------------


def process_telegram_update(data):
    global last_check_sender

    try:
        if "message" not in data:
            return

        message = data["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        # Проверка ID админа
        if str(chat_id) != str(config.TG_ADMIN_ID):
            print(f"⛔ Чужой ID: {chat_id}")
            return

        client_phone = None
        rejection_reason = None

        # === ЛОГИКА КОМАНД ===

        # 1. ПРИНЯТЬ (+)
        if text == "+" or text.lower() == "ok":
            if last_check_sender:
                client_phone = last_check_sender
            else:
                requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id,
                                    "text": "⚠️ Я забыл номер последнего клиента. Используй: /approve НОМЕР"})
                return

        # 2. ОТКЛОНИТЬ (-)
        elif text.startswith("-"):
            if last_check_sender:
                client_phone = last_check_sender
                reason = text[1:].strip()
                if not reason:
                    reason = "Оплата не найдена или сумма некорректна."
                rejection_reason = reason
            else:
                requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id,
                                    "text": "⚠️ Я забыл номер. Используй WhatsApp для ответа вручную."})
                return

        # 3. РУЧНОЙ ВВОД (/approve)
        elif text.startswith("/approve"):
            parts = text.split()
            if len(parts) >= 2:
                client_phone = parts[1].replace("+", "").strip()

        # === ВЫПОЛНЕНИЕ ДЕЙСТВИЙ ===

        if client_phone:
            # Если это ОТКАЗ
            if rejection_reason:
                print(f"[LOGIC] Отказ клиенту {client_phone}. Причина: {rejection_reason}")
                msg_text = f"✋ *Оплата не подтверждена.*\n\nПричина: _{rejection_reason}_\n\nПожалуйста, проверьте чек и отправьте его снова."
                send_whatsapp_message(client_phone, msg_text)

                requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id, "text": f"🛑 Отказ отправлен клиенту +{client_phone}"})
                return

            # Если это ОДОБРЕНИЕ (Админ нажал +)
            current_state = user_states.get(client_phone)

            # --- НОВАЯ ВЕТКА: ДОП. ПРОДАЖИ (ЗАПИСЬ В ГУГЛ) ---
            if "UPSELL" in str(current_state):
                print(f"[LOGIC] Оплата ДОП. ПРОДАЖИ подтверждена. Клиент {client_phone}")

                # 1. Отправляем финальную ссылку клиенту
                send_whatsapp_message(client_phone, messages.MSG_UPSELL_SUCCESS)

                # 2. Записываем в Google Таблицу!
                try:
                    sheets.add_payment_record(client_phone, service_name="Вебинар (Доп)", status="Оплачено")
                except Exception as e:
                    print(f"❌ Ошибка записи в таблицу: {e}")

                # 3. Сбрасываем статус
                user_states[client_phone] = "START"

                # 4. Отчет админу
                requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id,
                                    "text": f"✅ Оплата подтверждена! Клиенту +{client_phone} отправлена ссылка. Данные занесены в таблицу Google!"})
                return  # Выходим, дальше идти не нужно

            # --- НОВАЯ ВЕТКА: ПРАКТИКУМ ---
            if "PRACTICUM" in str(current_state):
                print(f"[LOGIC] Оплата ПРАКТИКУМА подтверждена. Клиент {client_phone}")

                # Отправляем сообщение об успехе
                send_whatsapp_message(client_phone, messages.MSG_A_SUCCESS)

                # Опционально: можно тут тоже записывать в Google Таблицу
                # sheets.add_payment_record(client_phone, service_name="Практикум", status="Оплачено")

                user_states[client_phone] = "START"

                requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id,
                                    "text": f"✅ Оплата подтверждена! Клиенту +{client_phone} отправлено финальное сообщение."})
                return  # Выходим, дальше идти не нужно


            # --- ИЗМЕНЕНИЕ: ОТПРАВЛЯЕМ ОФЕРТУ ВМЕСТО ПОДАРКОВ ---

            print(f"[LOGIC] Оплата подтверждена. Отправляем оферту клиенту {client_phone}")

            # 1. Отправляем PDF Оферты
            send_whatsapp_media(client_phone, "document", link=messages.URL_PDF_OFFERTA,
                                caption=None, filename=messages.NAME_PDF_OFFERTA)

            # 2. Отправляем текст "Согласны?"
            time.sleep(1)
            send_whatsapp_message(client_phone, messages.MSG_OFFERTA_TEXT)

            # 3. Меняем статус (чтобы ждать ответ клиента)
            is_alliance = "ALLIANCE" in str(current_state) or "АЛЬЯНС" in str(current_state)

            if is_alliance:
                user_states[client_phone] = "WAITING_OFFERTA_ALLIANCE"
            else:
                user_states[client_phone] = "WAITING_OFFERTA_GUILD"

            # Подтверждение Админу
            requests.post(f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}/sendMessage",
                          json={"chat_id": chat_id,
                                "text": f"✅ Оплата подтверждена! Клиенту +{client_phone} отправлена оферта."})

    except Exception as e:
        print(f"❌ Ошибка в Telegram Logic: {e}")


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

    current_state = user_states.get(sender_id, "START")
    print(f"User: {sender_id} | State: {current_state}")

    if text_lower == "/reset":
        user_states[sender_id] = "START"
        send_whatsapp_message(sender_id, "🔄 Сброс.")
        return


    # --- НОВЫЙ БЛОК: ЛОВЕЦ СЛОВА "НУЖНО" ---
    if text_lower == "нужно":
        send_whatsapp_message(sender_id, messages.MSG_UPSELL_PAYMENT)
        user_states[sender_id] = "WAITING_UPSELL_PAYMENT"
        return
    # ----------------------------------------

    # --- НОВЫЙ БЛОК: СТАРТ ВОРОНКИ "ИНТЕРЕСНО" ---
    if text_lower == "интересно":
        send_whatsapp_message(sender_id, messages.MSG_INT_1)
        send_whatsapp_buttons(sender_id, messages.MSG_INT_2, ["✅ Ия Да", "❌ Жоқ Нет"])
        user_states[sender_id] = "INTEREST_START"
        return

    # Обработка ответа Да/Нет
    if current_state == "INTEREST_START":
        if any(w in text_lower for w in ["да", "ия", "иә"]):
            send_whatsapp_buttons(sender_id, messages.MSG_INT_CHOICE,
                                  ["📚Онлайн практикум", "📄Образец документа", "🎯Сессия"])
            user_states[sender_id] = "INTEREST_CHOICE"
        else:
            send_whatsapp_message(sender_id, messages.MSG_INT_REJECT)
            user_states[sender_id] = "START"

    # Выбор направления
    elif current_state == "INTEREST_CHOICE":
        if "практикум" in text_lower:
            send_whatsapp_message(sender_id, messages.MSG_A1)
            user_states[sender_id] = "A_WAIT_REASON"
        elif "документ" in text_lower:
            send_whatsapp_buttons(sender_id, messages.MSG_B1, ["Я из 20%", "Скорее из 80%"])
            user_states[sender_id] = "B_WAIT_STAT"
        elif "сесси" in text_lower:
            send_whatsapp_buttons(sender_id, messages.MSG_C1, ["🔴 Да, срочно", "🟡 Нет, не срочно"])
            user_states[sender_id] = "C_WAIT_URGENCY"

    # --- ВЕТКА А: ПРАКТИКУМ ---
    elif current_state == "A_WAIT_REASON":
        send_whatsapp_buttons(sender_id, messages.MSG_A2_A3, ["🔥 Да, занимаю!", "❌ Нет"])
        user_states[sender_id] = "A_WAIT_DECISION"

    elif current_state == "A_WAIT_DECISION":
        if "да" in text_lower or "занимаю" in text_lower:
            send_whatsapp_message(sender_id, messages.MSG_A4_PAY)
            user_states[sender_id] = "WAITING_PRACTICUM_PAYMENT"
        else:
            send_whatsapp_message(sender_id, messages.MSG_INT_REJECT)
            user_states[sender_id] = "START"

    # --- ВЕТКА Б: ДОКУМЕНТ ---
    elif current_state == "B_WAIT_STAT":
        if "80" in text_lower:
            send_whatsapp_message(sender_id, messages.MSG_B_80)
        else:
            send_whatsapp_message(sender_id, messages.MSG_B_20)

        time.sleep(2)
        send_whatsapp_buttons(sender_id, messages.MSG_B2, ["⭐ Да, резидент", "👤 Не резидент"])
        user_states[sender_id] = "B_WAIT_RESIDENT"

    elif current_state == "B_WAIT_RESIDENT":
        if "да" in text_lower:
            send_whatsapp_message(sender_id, messages.MSG_B3_LINK_YES)
        else:
            send_whatsapp_message(sender_id, messages.MSG_B3_LINK_NO)
        user_states[sender_id] = "START"

    # --- ВЕТКА С: СЕССИЯ ---
    elif current_state == "C_WAIT_URGENCY":
        send_whatsapp_buttons(sender_id, messages.MSG_C2, ["✅ Да, готов(а)!", "🤔 Не уверен(а)"])
        user_states[sender_id] = "C_WAIT_READY"

    elif current_state == "C_WAIT_READY":
        if "да" in text_lower or "готов" in text_lower:
            send_whatsapp_message(sender_id, messages.MSG_C3_YES)
        else:
            send_whatsapp_message(sender_id, messages.MSG_C3_NO)
        user_states[sender_id] = "START"
    # ----------------------------------------------------------------




    # --- СТАРТ ---
    if current_state == "START":
        send_whatsapp_message(sender_id, messages.MSG_WELCOME)
        time.sleep(1)  # Короткая пауза для текста

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


        # --- ПРИЕМ ЧЕКА И ОТПРАВКА В TELEGRAM ---
        elif current_state in ["WAITING_FOR_ALLIANCE_PAYMENT", "WAITING_FOR_GUILD_PAYMENT",
                               "WAITING_ADMIN_ALLIANCE", "WAITING_ADMIN_GUILD",
                               "WAITING_UPSELL_PAYMENT", "WAITING_ADMIN_UPSELL",
                               "WAITING_PRACTICUM_PAYMENT", "WAITING_ADMIN_PRACTICUM"]:

            print(f"[DEBUG] Мы внутри блока проверки оплаты. Тип сообщения: {message_type}")

            if message_type in ["image", "document"]:
                print(f"[DEBUG] Это картинка или документ. Media ID: {media_id}")
                global last_check_sender
                last_check_sender = sender_id
                print(f"[DEBUG] Запомнили клиента для быстрой проверки: {last_check_sender}")

                send_whatsapp_message(sender_id,
                                      messages.MSG_A4_WAIT if "PRACTICUM" in current_state else messages.MSG_WAIT_FOR_ADMIN)

                is_alliance = "ALLIANCE" in current_state
                is_upsell = "UPSELL" in current_state
                is_practicum = "PRACTICUM" in current_state

                if is_alliance:
                    branch_name = "АЛЬЯНС"
                elif is_upsell:
                    branch_name = "ДОП. ПРОДАЖА"
                elif is_practicum:
                    branch_name = "ПРАКТИКУМ"
                else:
                    branch_name = "ГИЛЬДИЯ"

                # ВЫЗЫВАЕМ ФУНКЦИЮ отправки в ТГ
                if media_id:
                    send_image_to_telegram(sender_id, media_id, f"Ветка: {branch_name}")
                else:
                    print("[DEBUG] ❌ ОШИБКА: Пришел документ, но нет media_id!")

                # Меняем статус ожидания
                if is_alliance:
                    user_states[sender_id] = "WAITING_ADMIN_ALLIANCE"
                elif is_upsell:
                    user_states[sender_id] = "WAITING_ADMIN_UPSELL"
                elif is_practicum:
                    user_states[sender_id] = "WAITING_ADMIN_PRACTICUM"
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
