import os
import time
import requests
import telebot

# --- CONFIGURATION INITIALE & SÉCURITÉ ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8836745281:AAEKRiN91gtatRCcBuIsUur4myqXszwOLr4")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6524605343"))

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Variables de contrôle du bot (Rang S)
BOT_ACTIVE = True
CONSECUTIVE_LOSSES = 0
MAX_CONSECUTIVE_LOSSES = 3

def check_admin(message):
    return message.from_user.id == ADMIN_CHAT_ID

@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = True
    bot.reply_to(message, "🚀 **CLTM Quant Engine [Rang S] Activé**\n\nLe moteur d'analyse SMC/DXY et la gestion du risque sont opérationnels 24h/24.")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = False
    bot.reply_to(message, "🛑 **CLTM Quant Engine Désactivé**\n\nToutes les analyses et exécutions sont suspendues.")

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not check_admin(message):
        return
    status_text = "🟢 ACTIF" if BOT_ACTIVE else "🔴 INACTIF"
    bot.reply_to(message, f"📊 **Statut CLTM Quant Engine**\n\n- État: {status_text}\n- Pertes consécutives: {CONSECUTIVE_LOSSES}/{MAX_CONSECUTIVE_LOSSES}\n- Modèle de risque: Actuaire Dynamique (Rang S)")

def run_trading_engine():
    global BOT_ACTIVE, CONSECUTIVE_LOSSES
    print("CLTM Quant Engine démarré sur Render...")
    
    # Notification Telegram au démarrage du serveur
    try:
        bot.send_message(ADMIN_CHAT_ID, "🖥️ **Serveur Cloud Render connecté !**\nCLTM Quant Engine est prêt à recevoir vos ordres.")
    except Exception as e:
        print(f"Erreur d'envoi Telegram initial: {e}")

    # Boucle d'exécution continue
    bot.polling(non_stop=True, interval=2)

if __name__ == "__main__":
    run_trading_engine()
  
