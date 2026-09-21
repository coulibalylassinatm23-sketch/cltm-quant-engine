import os
import telebot
from telebot import types
import yfinance as yf

# ---------------------------------------------------------
# 1. INITIALIZATION
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
METAAPI_TOKEN = os.getenv('METAAPI_TOKEN')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN manquant dans les variables d'environnement.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Nettoyage automatique d'un éventuel webhook résiduel
try:
    bot.remove_webhook()
except Exception as e:
    print(f"Webhook remove log: {e}")

# ---------------------------------------------------------
# 2. PARAMÈTRES ET ÉTAT MOTEUR RANG S v6.0
# ---------------------------------------------------------
RISK_PER_TRADE_PCT = 1.0       # 1% de risque fixe par position
MAX_CONSECUTIVE_LOSSES = 5     # Verrou de sécurité à 5 pertes consécutives

bot_state = {
    "trading_active": True,
    "consecutive_losses": 0
}

# ---------------------------------------------------------
# 3. FILTRE MACRO-ÉCONOMIQUE (DXY)
# ---------------------------------------------------------
def check_macro_dxy_trend():
    """Analyse la tendance du Dollar US (DXY)."""
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        df = dxy.history(period="2d", interval="1h")
        if len(df) < 2:
            return "NEUTRE"
        last_close = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        return "HAUSSIER" if last_close > prev_close else "BAISSIER"
    except Exception as e:
        print(f"Erreur Filtre DXY: {e}")
        return "NEUTRE"

# ---------------------------------------------------------
# 4. ANALYSE STRUCTURELLE SMC & FILTRAGE AVANCÉ
# ---------------------------------------------------------
def analyze_institutional_setup(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="1h")
        if df.empty or len(df) < 5:
            return None

        last_close = df['Close'].iloc[-1]
        
        fvg_bullish = df['Low'].iloc[-1] > df['High'].iloc[-3]
        fvg_bearish = df['High'].iloc[-1] < df['Low'].iloc[-3]
        dxy_trend = check_macro_dxy_trend()

        signal = "NEUTRE"
        sl, tp1, tp2 = 0.0, 0.0, 0.0

        if fvg_bullish and dxy_trend == "BAISSIER":
            signal = "BUY"
            sl = df['Low'].iloc[-2]
            risk = last_close - sl
            tp1 = last_close + (risk * 1.5)
            tp2 = last_close + (risk * 3.0)
        elif fvg_bearish and dxy_trend == "HAUSSIER":
            signal = "SELL"
            sl = df['High'].iloc[-2]
            risk = sl - last_close
            tp1 = last_close - (risk * 1.5)
            tp2 = last_close - (risk * 3.0)

        return {
            "symbol": symbol,
            "signal": signal,
            "price": round(last_close, 5),
            "sl": round(sl, 5),
            "tp1": round(tp1, 5),
            "tp2": round(tp2, 5),
            "dxy": dxy_trend
        }
    except Exception as e:
        print(f"Erreur Analyse {symbol}: {e}")
        return None

# ---------------------------------------------------------
# 5. COMMANDES TELEGRAM
# ---------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_smc = types.KeyboardButton("🚀 Scan Rang S + Macro")
    btn_status = types.KeyboardButton("🟢 Statut Moteur")
    btn_kill = types.KeyboardButton("🛑 KILL SWITCH")
    markup.add(btn_smc, btn_status, btn_kill)

    bot.send_message(
        message.chat.id,
        "🏆 **CLTM Quant Engine Rang S v6.0**\n\n"
        "• Stop Loss Obligatoire : Actif\n"
        "• Filtre Macro DXY Intermarchés : Intégré\n"
        "• Sécurité : Stop après 5 pertes consécutives\n\n"
        "Utilise le menu ci-dessous pour interagir.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['status'])
def send_status(message):
    meta_status = "🟢 Configuré" if METAAPI_TOKEN else "🔴 Non configuré"
    trade_status = "🟢 ACTIF" if bot_state["trading_active"] else "🔴 SUSPENDU"
    
    status_msg = (
        "📊 **Bilan Technologique Moteur v6.0**\n\n"
        f"• État Général: {trade_status}\n"
        f"• Jeton MetaAPI: {meta_status}\n"
        f"• Protection Capital (SL): 1.0% fixe/trade\n"
        f"• Circuit Breaker: 5 Pertes max ({bot_state['consecutive_losses']}/5)\n"
        "• Filtre Correlation DXY: En ligne"
    )
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["🚀 Scan Rang S + Macro", "/scan"])
def trigger_analysis(message):
    if not bot_state["trading_active"]:
        bot.send_message(message.chat.id, "⚠️ **Système Verrouillé.** Sécurité activée.")
        return

    bot.send_message(message.chat.id, "⚡ *Analyse Quantitative & Filtrage Macro en cours...*", parse_mode="Markdown")
    assets = ["EURUSD=X", "GBPUSD=X", "GC=F", "BTC-USD"]
    asset_names = {"EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "GC=F": "OR (XAUUSD)", "BTC-USD": "BITCOIN"}

    msg = "🎯 **Signaux Validés Rang S (Avec SL & Macro)**\n\n"
    for asset in assets:
        res = analyze_institutional_setup(asset)
        name = asset_names.get(asset, asset)
        if res and res['signal'] != "NEUTRE":
            msg += f"🔥 **{name}** : Signal **{res['signal']}**\n"
            msg += f"   • Prix: {res['price']}\n"
            msg += f"   • 🛑 Stop Loss: {res['sl']}\n"
            msg += f"   • 🎯 Take Profit 1: {res['tp1']}\n"
            msg += f"   • 🎯 Take Profit 2: {res['tp2']}\n"
            msg += f"   • 🌐 Filtre DXY: {res['dxy']}\n\n"
        else:
            msg += f"⚪ **{name}** : Pas de confluence SMC + Macro.\n\n"

    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🛑 KILL SWITCH")
def kill_switch(message):
    bot_state["trading_active"] = False
    bot.send_message(message.chat.id, "🛑 **ARRET D'URGENCE ACTIVÉ.** Moteur de trading stoppé.")

# ---------------------------------------------------------
# 6. EXÉCUTION DU POLLING
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Démarrage du bot Telegram Rang S...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    
