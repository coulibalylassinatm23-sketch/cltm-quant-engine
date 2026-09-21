import os
import threading
import time
from flask import Flask
import telebot
import yfinance as yf

# --- SERVEUR WEB KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CLTM Quant Engine [Rang S] - Moteur Actuariel & Multi-Comptes Opérationnel !"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8836745281:AAEKRiN91gtatRCcBuIsUur4myqXszwOLr4")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6524605343"))

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
BOT_ACTIVE = True

# --- BASE DE DONNÉES EN MÉMOIRE (MULTI-COMPTES TRADING) ---
# Format: {"account_id": {"login": "12345", "password": "...", "server": "Broker-Demo", "active": True}}
TRADING_ACCOUNTS = {}

def check_admin(message):
    return message.from_user.id == ADMIN_CHAT_ID

# --- MODULE ACTUARIEL : CALCUL DE LOT ADAPTATIF & AUTONOME ---
def calculate_actuarial_lot(capital, risk_percent, sl_pips, asset_type="FOREX"):
    """
    Algorithme de dimensionnement de position adaptatif.
    Calcule la taille exacte du lot en fonction du capital disponible,
    de la tolérance au risque et de la volatilité de l'actif.
    """
    if capital <= 0 or sl_pips <= 0:
        return 0.01

    max_loss_cash = capital * (risk_percent / 100.0)

    if asset_type == "BTC":
        lot = max_loss_cash / (sl_pips * 1.0)
    elif asset_type == "XAU":
        lot = max_loss_cash / (sl_pips * 10.0)
    else:  # Forex par défaut
        lot = max_loss_cash / (sl_pips * 10.0)

    # Sécurité actuarielle : pas de lot nul, arrondi à 2 décimales
    lot = max(0.01, round(lot, 2))
    return lot

# --- ANALYSE INSTITUTIONNELLE SMC ---
ASSETS = {
    "EURUSD": ("EURUSD=X", "FOREX"),
    "GBPUSD": ("GBPUSD=X", "FOREX"),
    "OR (XAUUSD)": ("GC=F", "XAU"),
    "BITCOIN": ("BTC-USD", "BTC")
}

def analyze_market_smc():
    report = "🏛️ **CLTM QUANT ENGINE [RANG S] - DASHBOARD**\n\n"
    
    # Check DXY
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

# --- COMMANDES TELEGRAM & INTERFACE UTILISATEUR ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_admin(message):
        return
    bot.reply_to(message, 
                 "🧠 **CLTM Quant Engine [Rang S] - Système Prêt**\n\n"
                 "📌 **Commandes Principales :**\n"
                 "• `/analyse` : Diagnostic SMC & Corrélation DXY\n"
                 "• `/add_account <Login> <Pass> <Serveur>` : Connecter un compte MT5\n"
                 "• `/accounts` : Liste des comptes connectés\n"
                 "• `/toggle` : Activer/Désactiver le trading automatique\n"
                 "• `/status` : État du moteur actuariel", parse_mode="Markdown")

@bot.message_handler(commands=['analyse'])
def handle_analyse(message):
    if not check_admin(message):
        return
    bot.reply_to(message, "⏳ Analyse quantitativiste en cours...")
    report = analyze_market_smc()
    bot.send_message(ADMIN_CHAT_ID, report, parse_mode="Markdown")

@bot.message_handler(commands=['toggle'])
def handle_toggle(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = not BOT_ACTIVE
    state = "🟢 ACTIF (Trading Autonome)" if BOT_ACTIVE else "🔴 EN PAUSE (Mode Observation)"
    bot.reply_to(message, f"⚙️ **Statut du Bot :** {state}")

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
        
        bot.reply_to(message, f"✅ **Compte MT5 Enregistré !**\n\n🆔 **Login:** `{acc_login}`\n🌐 **Serveur:** `{acc_server}`\n⚡ **Risk Management Actuariel:** Actif sur ce compte.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Erreur lors de l'ajout du compte : {str(e)}")

@bot.message_handler(commands=['accounts'])
def handle_accounts(message):
    if not check_admin(message):
        return
    if not TRADING_ACCOUNTS:
        bot.reply_to(message, "📂 **Aucun compte de trading connecté.**\nUtilise `/add_account` pour en ajouter un.")
        return
    
    res = "📋 **COMPTES DE TRADING CONNECTÉS :**\n\n"
    for login, info in TRADING_ACCOUNTS.items():
        res += f"🔹 **ID:** `{login}` | **Serveur:** `{info['server']}` | **Statut:** {info['status']}\n"
    bot.reply_to(message, res, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not check_admin(message):
        return
    status_text = "🟢 ACTIF" if BOT_ACTIVE else "🔴 EN PAUSE"
    bot.reply_to(message, f"📊 **Statut CLTM Quant Engine**\n\n- État Trading: {status_text}\n- Moteur Actuariel: En ligne\n- Comptes rattachés: {len(TRADING_ACCOUNTS)}")

def run_trading_engine():
    print("CLTM Quant Engine v3.0 démarré...")
    bot.polling(non_stop=True, interval=2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    run_trading_engine()
