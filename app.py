# app.py
from flask import Flask, request, jsonify
import config
import logic

app = Flask(__name__)

# --- ГЛАВНАЯ СТРАНИЦА (ЧТОБЫ RENDER ВИДЕЛ, ЧТО МЫ ЖИВЫ) ---
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Bot is alive!", 200

# --- WEBHOOK (СЮДА СТУЧИТ META) ---
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # 1. VERIFY (ПРОВЕРКА ТОКЕНА)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == config.VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    # 2. MESSAGE (ПОЛУЧЕНИЕ СООБЩЕНИЯ)
    if request.method == "POST":
        data = request.json
        try:
            if ('entry' in data and 
                'changes' in data['entry'][0] and 
                'value' in data['entry'][0]['changes'][0] and 
                'messages' in data['entry'][0]['changes'][0]['value']):
                
                message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
                sender_id = message_data['from']
                msg_type = message_data['type']
                
                text = ""
                media_id = None
                
                # ОПРЕДЕЛЯЕМ ТИП
                if msg_type == "text":
                    text = message_data['text']['body']
                elif msg_type == "image":
                    text = "ЧЕК"
                    media_id = message_data['image']['id']
                elif msg_type == "document":
                    text = "ЧЕК"
                    media_id = message_data['document']['id']

                print(f"📩 MSG от {sender_id} ({msg_type})")

                # ПРОВЕРКА: АДМИН ИЛИ КЛИЕНТ?
                # Очищаем номера от лишнего
                clean_sender = str(sender_id).replace("+", "").strip()
                clean_admin = str(config.ADMIN_PHONE).replace("+", "").strip()

                if clean_sender == clean_admin:
                    print("👮‍♂️ Пишет АДМИНИСТРАТОР")
                    logic.process_admin_message(text)
                else:
                    print("👤 Пишет КЛИЕНТ")
                    logic.process_user_message(sender_id, text, message_type=msg_type, media_id=media_id)

        except Exception as e:
            print(f"❌ Ошибка в app.py: {e}")

        return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
