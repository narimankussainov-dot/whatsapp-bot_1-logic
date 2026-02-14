# app.py
from flask import Flask, request, jsonify
import config
import logic

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Bot is alive!", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # 1. VERIFY
    if request.method == "GET":
        if (request.args.get("hub.mode") == "subscribe" and
                request.args.get("hub.verify_token") == config.VERIFY_TOKEN):
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403

    # 2. MESSAGE
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

                # Ищем текст или ID файла
                text = ""
                media_id = None

                if msg_type == "text":
                    text = message_data['text']['body']
                elif msg_type == "image":
                    text = "ЧЕК"
                    media_id = message_data['image']['id']
                elif msg_type == "document":
                    text = "ЧЕК"
                    media_id = message_data['document']['id']

                print(f"📩 MSG от {sender_id} ({msg_type})")

                # === 🔥 ГЛАВНАЯ РАЗВИЛКА: АДМИН ИЛИ КЛИЕНТ? ===

                # Важно: Сравниваем телефоны.
                # Meta иногда шлет номер без "+", поэтому лучше сравнивать, содержит ли один другого
                # Или просто жесткое равенство, если форматы совпадают.

                if sender_id == config.ADMIN_PHONE:
                    print("👮‍♂️ Пишет АДМИНИСТРАТОР")
                    logic.process_admin_message(text)
                else:
                    print("👤 Пишет КЛИЕНТ")
                    logic.process_user_message(sender_id, text, message_type=msg_type, media_id=media_id)

        except Exception as e:
            print(f"❌ Ошибка в app.py: {e}")

        return jsonify({"status": "success"}), 200


if __name__ == "__main__":

    app.run(port=5000, debug=True)
