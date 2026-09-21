import os
import threading
from flask import Flask
import telebot

# --- SERVEUR WEB POUR KEEP-ALIVE (RENDER) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CLTM Quant Engine [Rang S] est en ligne et actif !"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8836745281:AAEKRiN91gtatRCcBuIsUur4myqXszwOLr4")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6524605343"))

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

BOT_ACTIVE = True

def check_admin(message):
    return message.from_user.id == ADMIN_CHAT_ID

@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = True
    bot.reply_to(message, "🚀 **CLTM Quant Engine [Rang S] Activé**\n\nLe moteur d'analyse SMC/DXY et la gestion du risque sont opérationnels 24h/24.")

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not check_admin(message):
        return
    status_text = "🟢 ACTIF" if BOT_ACTIVE else "🔴 INACTIF"
    bot.reply_to(message, f"📊 **Statut CLTM Quant Engine**\n\n- État: {status_text}\n- Serveur Web: En ligne\n- Modèle: Rang S")

def run_trading_engine():
    print("CLTM Quant Engine démarré sur Render...")
    try:
        bot.send_message(ADMIN_CHAT_ID, "🖥️ **Serveur Cloud Render connecté !**\nKeep-Alive Web + Telegram actifs.")
    except Exception as e:
        print(f"Erreur d'envoi Telegram: {e}")

    bot.polling(non_stop=True, interval=2)

if __name__ == "__main__":
    # Lancement du serveur Web dans un thread séparé
    threading.Thread(target=run_web_server, daemon=True).start()
    # Lancement du bot Telegram
    run_trading_engine()
    
