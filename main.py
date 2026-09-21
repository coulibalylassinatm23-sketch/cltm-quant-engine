import os
import threading
from flask import Flask
import telebot
import yfinance as yf

# --- SERVEUR WEB KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CLTM Quant Engine [Rang S] - Serveur Web & Analyse SMC Actifs !"

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

# --- MODULE D'ANALYSE FINANCIÈRE (SMC & DXY) ---
def get_market_analysis(symbol="EURUSD=X"):
    try:
        data = yf.download(tickers=symbol, period="5d", interval="1h", progress=False)
        dxy_data = yf.download(tickers="DX-Y.NYB", period="5d", interval="1h", progress=False)

        if data.empty:
            return "⚠️ Impossible de récupérer les données de marché."

        # Extraire les valeurs uniques scalaires
        last_close = float(data['Close'].iloc[-1].item() if hasattr(data['Close'].iloc[-1], 'item') else data['Close'].iloc[-1])
        dxy_close = float(dxy_data['Close'].iloc[-1].item() if hasattr(dxy_data['Close'].iloc[-1], 'item') else dxy_data['Close'].iloc[-1]) if not dxy_data.empty else 0.0

        high_prev2 = float(data['High'].iloc[-3].item() if hasattr(data['High'].iloc[-3], 'item') else data['High'].iloc[-3])
        low_current = float(data['Low'].iloc[-1].item() if hasattr(data['Low'].iloc[-1], 'item') else data['Low'].iloc[-1])
        high_current = float(data['High'].iloc[-1].item() if hasattr(data['High'].iloc[-1], 'item') else data['High'].iloc[-1])
        low_prev2 = float(data['Low'].iloc[-3].item() if hasattr(data['Low'].iloc[-3], 'item') else data['Low'].iloc[-3])

        fvg_detected = "Aucun FVG détecté"
        if low_current > high_prev2:
            fvg_detected = "🚀 **FVG Haussier détecté !**"
        elif high_current < low_prev2:
            fvg_detected = "📉 **FVG Baissier détecté !**"

        report = (
            f"📊 **ANALYSE DE MARCHÉ CLTM (SMC)**\n\n"
            f"🔹 **Actif:** {symbol.replace('=X', '')}\n"
            f"🔹 **Prix Actuel:** `{last_close:.5f}`\n"
            f"💵 **Indice DXY:** `{dxy_close:.2f}`\n\n"
            f"🔍 **Signal SMC:**\n{fvg_detected}\n\n"
            f"⚡ *Moteur Quantitatif opérationnel.*"
        )
        return report
    except Exception as e:
        return f"❌ Erreur lors de l'analyse : {str(e)}"

# --- COMMANDES TELEGRAM ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_admin(message):
        return
    global BOT_ACTIVE
    BOT_ACTIVE = True
    bot.reply_to(message, "🚀 **CLTM Quant Engine [Rang S] Activé**\n\nUtilise /analyse pour lancer un scan de marché.")

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not check_admin(message):
        return
    status_text = "🟢 ACTIF" if BOT_ACTIVE else "🔴 INACTIF"
    bot.reply_to(message, f"📊 **Statut CLTM Quant Engine**\n\n- État: {status_text}\n- Serveur Web: En ligne\n- Analyseur SMC: Prêt")

@bot.message_handler(commands=['analyse'])
def handle_analyse(message):
    if not check_admin(message):
        return
    bot.reply_to(message, "⏳ Analyse des flux SMC & DXY en cours...")
    report = get_market_analysis("EURUSD=X")
    bot.send_message(ADMIN_CHAT_ID, report, parse_mode="Markdown")

def run_trading_engine():
    print("CLTM Quant Engine démarré...")
    bot.polling(non_stop=True, interval=2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    run_trading_engine()
    
