# config.py

# ACCESS_TOKEN = "EAAUeWsYuTiYBQqjDGnBw9U74l1LbM4RjG5r0275HLZBPFWDTitDd0O2o9PZCZBanHwJgRGGesxKNjl7NdCGBVOzKCwsM631ybcxYxnNiQ3NmsNlROvZCsmstgGsFA6Jx3ZAQ2t7w13X5Ghu2QalMGG4gZBZAGygQSYn5omgXZC6ZBHaIDJaRQacxqZAI6MmnZAnFwZDZD"
#
# PHONE_NUMBER_ID = "992621413930838"
# VERIFY_TOKEN = "super_secret_password_123"
# VERSION = "v19.0"
#
# ADMIN_PHONE = "77472126808"
#
#
# # НАСТРОЙКИ TELEGRAM
# TG_BOT_TOKEN = "8588496508:AAF_N9awVbS_PqInXoxqeD5EPayPpwyuVYc"
# TG_ADMIN_ID = "1286560578"


import os

# --- META (WHATSAPP) ---
# Если переменной нет на сервере, бот не запустится (защита)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "super_secret_password_123")
VERSION = "v19.0"

# --- TELEGRAM ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_ADMIN_ID = os.getenv("TG_ADMIN_ID")

# --- ПРОЧЕЕ ---
# Если мы полностью перешли на Telegram-уведомления, эта строка может быть не нужна.
# Но лучше пока оставить её пустой или заполнить, если в коде остались ссылки на неё.
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "77472126808")
