import os
import sys
import logging
import asyncio
import threading
from flask import Flask
import telebot
from metaapi_cloud_sdk import MetaApi

# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Récupération des variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")

if not TELEGRAM_TOKEN or not METAAPI_TOKEN:
    logging.error("Variables d'environnement TELEGRAM_TOKEN ou METAAPI_TOKEN manquantes !")
    sys.exit(1)

# Initialisation du Bot Telegram
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Serveur web Flask pour Render (health check)
app = Flask(__name__)

@app.route('/')
def home():
    return "CLTM Quant Engine est en cours d'exécution.", 200

# Dictionnaire temporaire pour la saisie utilisateur
user_states = {}

# --- COMMANDES TELEGRAM ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Scan Quantique Ultra", "💼 Gérer mes Comptes MT")
    markup.row("🛡️ News Guard: ON", "📊 Tableau de Bord")
    markup.row("🔴 Activer Kill Switch")
    bot.send_message(
        message.chat.id,
        "👋 Bienvenue sur **CLTM Quant Engine** !\nSélectionnez une option ci-dessous :",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "💼 Gérer mes Comptes MT")
def manage_accounts(message):
    markup = telebot.types.InlineKeyboardMarkup()
    btn_add = telebot.types.InlineKeyboardButton("➕ Connecter un Nouveau Compte MT", callback_data="add_mt_account")
    markup.add(btn_add)
    bot.send_message(
        message.chat.id,
        "💼 **GESTION COMPTES METATRADER**\n\nSélectionnez une action :",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "add_mt_account")
def start_add_account(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = {'step': 1}
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "1️⃣ Entrez un **Nom de repère** pour ce compte :", parse_mode="Markdown")

# Fonction asynchrone d'initialisation et de création de compte MetaAPI
async def create_metaapi_account_async(data):
    api = MetaApi(token=METAAPI_TOKEN)
    account = await api.metatrader_account_api.create_account({
        'name': data['name'],
        'type': 'cloud',
        'login': data['login'],
        'password': data['password'],
        'server': data['server'],
        'platform': data['platform'].lower(),
        'magic': 1000
    })
    return account

@bot.message_handler(func=lambda msg: msg.chat.id in user_states)
def process_account_steps(message):
    chat_id = message.chat.id
    state = user_states[chat_id]
    step = state.get('step', 0)

    if step == 1:
        state['name'] = message.text.strip()
        state['step'] = 2
        bot.send_message(chat_id, "2️⃣ Entrez la **Plateforme** (`MT4` ou `MT5`) :", parse_mode="Markdown")

    elif step == 2:
        platform = message.text.strip().upper()
        if platform not in ["MT4", "MT5"]:
            bot.send_message(chat_id, "⚠️ Veuillez écrire exactement `MT4` ou `MT5` :", parse_mode="Markdown")
            return
        state['platform'] = platform
        state['step'] = 3
        bot.send_message(chat_id, "3️⃣ Entrez le nom exact du **Serveur** (ex: `MetaQuotes-Demo`) :", parse_mode="Markdown")

    elif step == 3:
        state['server'] = message.text.strip()
        state['step'] = 4
        bot.send_message(chat_id, "4️⃣ Entrez le **Login** (Numéro de compte) :", parse_mode="Markdown")

    elif step == 4:
        state['login'] = message.text.strip()
        state['step'] = 5
        bot.send_message(chat_id, "5️⃣ Entrez le **Mot de passe** MetaTrader :", parse_mode="Markdown")

    elif step == 5:
        state['password'] = message.text.strip()
        bot.send_message(chat_id, "⏳ **Déploiement du compte sur MetaAPI en cours...**", parse_mode="Markdown")

        try:
            # Exécution dans une boucle d'événements dédiée
            account = asyncio.run(create_metaapi_account_async(state))

            bot.send_message(
                chat_id,
                f"✅ **Compte connecté avec succès !**\n\n"
                f"• **Nom** : {state['name']}\n"
                f"• **ID MetaAPI** : `{account.id}`\n"
                f"• **Serveur** : {state['server']}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Erreur MetaAPI: {e}")
            bot.send_message(
                chat_id,
                f"❌ **Échec de la connexion MetaAPI :**\n`{str(e)}`",
                parse_mode="Markdown"
            )

        del user_states[chat_id]

# --- LANCEMENT DU SERVEUR FLASK ET DU BOT ---

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    # Lancement de Flask dans un thread séparé pour le health check de Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Démarrage du bot Telegram
    logging.info("Lancement du bot Telegram...")
    try:
        # Nettoyage du webhook et des messages en attente
        bot.remove_webhook(drop_pending_updates=True)
        bot.infinity_polling(timeout=30, long_polling_timeout=5)
    except Exception as e:
        logging.critical(f"Erreur fatale bot: {e}")
    
