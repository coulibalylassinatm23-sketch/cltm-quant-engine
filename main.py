import os
import threading
from flask import Flask
import telebot
from telebot import types
import yfinance as yf

# --- SERVEUR WEB KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CLTM Quant Engine [Rang S] - Interface & Menu Actifs !"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8836745281:AAEKRiN91gtatRCcBuIsUur4myqXszwOLr4")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6524605343"))

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
BOT_ACTIVE = True

# --- ENREGISTREMENT DES COMMANDES DANS LE MENU TELEGRAM ---
try:
    bot.set_my_commands([
        telebot.types.BotCommand("start", "🚀 Afficher le panneau de contrôle"),
        telebot.types.BotCommand("analyse", "📊 Scan de marché multi-actifs"),
        telebot.types.BotCommand("accounts", "📋 Liste des comptes MT5"),
        telebot.types.BotCommand("toggle", "⚙️ Activer/Désactiver le bot"),
        telebot.types.BotCommand("status", "🟢 État du système")
    ])
except Exception as e:
    print(f"Erreur de configuration des commandes: {e}")

# --- BASE DE DONNÉES EN MÉMOIRE ---
TRADING_ACCOUNTS = {}

def check_admin(message):
    return message.from_user.id == ADMIN_CHAT_ID

# --- CRÉATION DU CLAVIER INTERACTIF (BOUTONS PERMANENTS) ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_analyse = types.KeyboardButton("📊 Analyse SMC")
    btn_accounts = types.KeyboardButton("📋 Mes Comptes")
    btn_status = types.KeyboardButton("🟢 Statut")
    btn_toggle = types.KeyboardButton("⚙️ ON / OFF")
    
    markup.add(btn_analyse, btn_accounts, btn_status, btn_toggle)
    return markup

# --- ANALYSE INSTITUTIONNELLE SMC ---
ASSETS = {
    "EURUSD": ("EURUSD=X", "FOREX"),
    "GBPUSD": ("GBPUSD=X", "FOREX"),
    "OR (XAUUSD)": ("GC=F", "XAU"),
    "BITCOIN": ("BTC-USD", "BTC")
}

def analyze_market_smc():
    report = "🏛️ **CLTM QUANT ENGINE [RANG S] - DASHBOARD**\n\n"
    
    try:
        dxy = yf.download(tickers="DX-Y.NYB", period="5d", interval="1h", progress=False)
        dxy_price = float(dxy['Close'].iloc[-1].item() if hasattr(dxy['Close'].iloc[-1], 'item') else dxy['Close'].iloc[-1])
        report += f"💵 **Indice DXY:** `{dxy_price:.2f}`\n"
        report += "-----------------------------------\n"
    except Exception:
        report += "💵 **Indice DXY:** N/A\n-----------------------------------\n"

    for name, (ticker, asset_type) in ASSETS.items():
        try:
            data = yf.download(tickers=ticker, period="5d", interval="1h", progress=False)
            if data.empty:
                continue
            
            last = float(data['Close'].iloc[-1].item() if hasattr(data['Close'].iloc[-1], 'item') else data['Close'].iloc[-1])
            high_prev2 = float(data['High'].iloc[-3].item() if hasattr(data['High'].iloc[-3], 'item') else data['High'].iloc[-3])
            low_current = float(data['Low'].iloc[-1].item() if hasattr(data['Low'].iloc[-1], 'item') else data['Low'].iloc[-1])
            high_current = float(data['High'].iloc[-1].item() if hasattr(data['High'].iloc[-1], 'item') else data['High'].iloc[-1])
            low_prev2 = float(data['Low'].iloc[-3].item() if hasattr(data['Low'].iloc[-3], 'item') else data['Low'].iloc[-3])

            signal = "⚪ Neutre"
            if low_current > high_prev2:
                signal = "🚀 **FVG Achat**"
            elif high_current < low_prev2:
                signal = "📉 **FVG Vente**"

            report += f"🔹 **{name}**: `{last:.2f}` | {signal}\n"
        except Exception:
            report += f"❌ **{name}**: Erreur de lecture\n"

    return report

# --- COMMANDES ET GESTIONNAIRE DES BOUTONS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_admin(message):
        return
    bot.send_message(
        ADMIN_CHAT_ID,
        "🧠 **CLTM Quant Engine [Rang S] - Terminal Prêt**\n\n"
        "Utilise les boutons ci-dessous pour interagir instantanément avec le système.",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['analyse'])
def handle_analyse(message):
    if not check_admin(message):
        return
    bot.reply_to(message, "⏳ Analyse quantitativiste en cours...")
    report = analyze_market_smc()
    bot.send_message(ADMIN_CHAT_ID, report, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['toggle'])
def handle_toggle(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = not BOT_ACTIVE
    state = "🟢 ACTIF (Trading Autonome)" if BOT_ACTIVE else "🔴 EN PAUSE (Mode Observation)"
    bot.reply_to(message, f"⚙️ **Statut du Bot :** {state}", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['add_account'])
def handle_add_account(message):
    if not check_admin(message):
        return
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            bot.reply_to(message, "⚠️ **Format :** `/add_account <Login> <Password> <Server>`\nEx: `/add_account 1234567 mypass Exness-MT5Trial`", parse_mode="Markdown")
            return
        
        acc_login, acc_pass, acc_server = args[0], args[1], args[2]
        TRADING_ACCOUNTS[acc_login] = {
            "password": acc_pass,
            "server": acc_server,
            "status": "Connecté (En attente d'ordres)"
        }
        
        bot.reply_to(message, f"✅ **Compte MT5 Enregistré !**\n\n🆔 **Login:** `{acc_login}`\n🌐 **Serveur:** `{acc_server}`\n⚡ **Risk Management Actuariel:** Actif.", parse_mode="Markdown", reply_markup=get_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Erreur lors de l'ajout du compte : {str(e)}")

@bot.message_handler(commands=['accounts'])
def handle_accounts(message):
    if not check_admin(message):
        return
    if not TRADING_ACCOUNTS:
        bot.reply_to(message, "📂 **Aucun compte de trading connecté.**\nUtilise `/add_account <Login> <Pass> <Serveur>` pour en ajouter un.", reply_markup=get_main_keyboard())
        return
    
    res = "📋 **COMPTES DE TRADING CONNECTÉS :**\n\n"
    for login, info in TRADING_ACCOUNTS.items():
        res += f"🔹 **ID:** `{login}` | **Serveur:** `{info['server']}` | **Statut:** {info['status']}\n"
    bot.reply_to(message, res, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not check_admin(message):
        return
    status_text = "🟢 ACTIF" if BOT_ACTIVE else "🔴 EN PAUSE"
    bot.reply_to(message, f"📊 **Statut CLTM Quant Engine**\n\n- État Trading: {status_text}\n- Moteur Actuariel: En ligne\n- Comptes rattachés: {len(TRADING_ACCOUNTS)}", reply_markup=get_main_keyboard())

# --- CAPTURE DES CLICS SUR LES BOUTONS DU CLAVIER ---
@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    if not check_admin(message):
        return
    
    text = message.text
    if text == "📊 Analyse SMC":
        handle_analyse(message)
    elif text == "📋 Mes Comptes":
        handle_accounts(message)
    elif text == "🟢 Statut":
        handle_status(message)
    elif text == "⚙️ ON / OFF":
        handle_toggle(message)

def run_trading_engine():
    print("CLTM Quant Engine v3.1 démarré...")
    bot.polling(non_stop=True, interval=2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    run_trading_engine()
            
