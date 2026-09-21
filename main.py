import os
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask
import telebot
from telebot import types
import yfinance as yf

# ---------------------------------------------------------
# 1. SERVEUR FLASK EN ARRIÈRE-PLAN (Render Online)
# ---------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot Quantique Rang S - News Guard actif en ligne !", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------------------------------------------------
# 2. INITIALISATION TELEGRAM & CLÉS API
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
METAAPI_TOKEN = os.getenv('METAAPI_TOKEN')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN manquant dans les variables d'environnement.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

try:
    bot.remove_webhook()
except Exception as e:
    print(f"Webhook remove log: {e}")

# Moteur global et stockage mémoire
trading_engine = {
    "trading_active": True,
    "consecutive_losses": 0,
    "risk_percent": 0.01,
    "active_account_id": os.getenv('METAAPI_ACCOUNT_ID', None),
    "accounts": {},
    "news_guard_active": True  # Activation par défaut du filtre anti-news
}

user_forms = {}

# ---------------------------------------------------------
# 3. FILTRE D'ANNONCES ÉCONOMIQUES MAJEURES (NEWS GUARD)
# ---------------------------------------------------------
def check_high_impact_news():
    """
    Vérifie si une annonce économique à fort impact (NFP, CPI, FED, etc.) 
    est imminente (fenêtre de 30 minutes avant/après).
    """
    if not trading_engine["news_guard_active"]:
        return False, "Filtre News désactivé manuellement."

    try:
        # Récupération du calendrier économique hebdomadaire public (JSON)
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return False, None # En cas de mini coupure réseau, on laisse passer pour ne pas bloquer bêtement

        events = response.json()
        now_utc = datetime.now(timezone.utc)

        for event in events:
            # On ne cible que les annonces à fort impact (High) sur les monnaies majeures
            impact = event.get("impact", "")
            country = event.get("country", "")
            if impact.lower() == "high" and country in ["USD", "EUR", "GBP", "ALL"]:
                date_str = event.get("date") # Format ISO ex: 2026-09-21T14:30:00-04:00
                if not date_str:
                    continue
                
                event_time = datetime.fromisoformat(date_str).astimezone(timezone.utc)
                
                # Fenêtre de sécurité : 30 minutes avant et 30 minutes après l'annonce
                time_diff = (event_time - now_utc).total_seconds() / 60.0
                
                # Si l'événement est dans moins de 30 min ou s'est produit il y a moins de 30 min
                if -30 <= time_diff <= 30:
                    event_title = event.get("title", "Annonce Inconnue")
                    return True, f"🚨 **ALERTE NEWS MAJEURE** : `{event_title}` ({country}) prévue à {event_time.strftime('%H:%M')} UTC (Écart: {int(time_diff)} min)."

    except Exception as e:
        print(f"Erreur vérification news: {e}")
    
    return False, None

# ---------------------------------------------------------
# 4. INTERACTION DYNAMIQUE METAAPI
# ---------------------------------------------------------
def create_metaapi_account(name, type_mt, server, login, password):
    url = "https://mt-provisioning-api-v1.agium.celp.metatrader.com/users/current/accounts"
    headers = {"auth-token": METAAPI_TOKEN, "Content-Type": "application/json"}
    payload = {
        "name": name, "type": "cloud", "login": str(login),
        "password": password, "server": server, "platform": type_mt.lower(), "application": "MetaTrader"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            data = response.json()
            account_id = data.get("id")
            deploy_url = f"https://mt-provisioning-api-v1.agium.celp.metatrader.com/users/current/accounts/{account_id}/deploy"
            requests.post(deploy_url, headers=headers, timeout=10)
            return True, account_id
        else:
            return False, f"Erreur MetaAPI ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Erreur de connexion MetaAPI: {e}"

def get_account_balance(account_id):
    if not METAAPI_TOKEN or not account_id:
        return 10000.0
    url = f"https://mt-client-api-v1.agium.celp.metatrader.com/users/current/accounts/{account_id}/account-information"
    headers = {"auth-token": METAAPI_TOKEN}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return float(data.get("equity", data.get("balance", 10000.0)))
    except Exception:
        pass
    return 10000.0

def calculate_dynamic_lot(account_id, entry_price, sl_price, symbol):
    balance = get_account_balance(account_id)
    risk_amount = balance * trading_engine["risk_percent"]
    sl_pips = abs(entry_price - sl_price)
    if sl_pips == 0:
        return 0.01
    pip_value = 10.0 if "USD" in symbol else 1.0
    lot_size = risk_amount / (sl_pips * pip_value * 100)
    return round(max(0.01, min(lot_size, 10.0)), 2)

def execute_metaapi_order(symbol, action, sl, tp1, tp2):
    # VERIFICATION NEWS GUARD AVANT EXECUTION
    has_news, news_reason = check_high_impact_news()
    if has_news:
        return False, f"Bloqué par le News Guard 🛑\n{news_reason}"

    account_id = trading_engine["active_account_id"]
    if not METAAPI_TOKEN or not account_id:
        return False, "Aucun compte connecté ou jeton API manquant."

    url = f"https://mt-client-api-v1.agium.celp.metatrader.com/users/current/accounts/{account_id}/trade"
    headers = {"auth-token": METAAPI_TOKEN, "Content-Type": "application/json"}
    
    clean_symbol = symbol.replace("=X", "").replace("-USD", "USD").replace("GC=F", "XAUUSD")
    order_type = "ORDER_TYPE_BUY" if "BUY" in action else "ORDER_TYPE_SELL"

    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1d", interval="1m")
    current_price = df['Close'].iloc[-1] if not df.empty else sl
    lot = calculate_dynamic_lot(account_id, current_price, sl, clean_symbol)

    payload = {
        "actionType": order_type, "symbol": clean_symbol, "volume": lot,
        "stopLoss": sl, "takeProfit": tp1, "comment": f"Rang S Prime Guard [{lot} Lots]"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            return True, f"Ordre exécuté avec succès ! Lot: {lot}"
        else:
            return False, f"Erreur Execution ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Erreur Réseau: {e}"

# ---------------------------------------------------------
# 5. ALGORITHME RANG S
# ---------------------------------------------------------
def check_macro_dxy_trend():
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        df = dxy.history(period="3d", interval="1h")
        if len(df) < 2:
            return "NEUTRE"
        return "HAUSSIER" if df['Close'].iloc[-1] > df['Close'].iloc[-2] else "BAISSIER"
    except Exception:
        return "NEUTRE"

def analyze_ultra_setup(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df_h4 = ticker.history(period="10d", interval="1h")
        if df_h4.empty or len(df_h4) < 10:
            return None
        h4_trend = "BULL" if df_h4['Close'].iloc[-1] > df_h4['Close'].iloc[-10] else "BEAR"

        df_h1 = ticker.history(period="5d", interval="1h")
        last_close = df_h1['Close'].iloc[-1]
        fvg_bullish = df_h1['Low'].iloc[-1] > df_h1['High'].iloc[-3]
        fvg_bearish = df_h1['High'].iloc[-1] < df_h1['Low'].iloc[-3]
        dxy_trend = check_macro_dxy_trend()

        signal = "NEUTRE"
        sl, tp1, tp2 = 0.0, 0.0, 0.0

        if fvg_bullish and h4_trend == "BULL" and dxy_trend == "BAISSIER":
            signal = "BUY 🟩 (Rang S Prime)"
            sl = df_h1['Low'].iloc[-2]
            risk = last_close - sl
            tp1 = round(last_close + (risk * 2.0), 5)
            tp2 = round(last_close + (risk * 3.5), 5)
        elif fvg_bearish and h4_trend == "BEAR" and dxy_trend == "HAUSSIER":
            signal = "SELL 🟥 (Rang S Prime)"
            sl = df_h1['High'].iloc[-2]
            risk = sl - last_close
            tp1 = round(last_close - (risk * 2.0), 5)
            tp2 = round(last_close - (risk * 3.5), 5)

        execution_log = ""
        if "Rang S" in signal and trading_engine["trading_active"]:
            success, msg = execute_metaapi_order(symbol, signal, sl, tp1, tp2)
            execution_log = f"\n   └ 🤖 *Auto-Trade:* {'✅ Exécuté' if success else '🛡️ ' + msg}"

        return {
            "symbol": symbol, "signal": signal, "price": round(last_close, 5),
            "sl": round(sl, 5), "tp1": tp1, "tp2": tp2, 
            "dxy": dxy_trend, "h4": h4_trend, "exec_log": execution_log
        }
    except Exception:
        return None

# ---------------------------------------------------------
# 6. INTERFACE TELEGRAM
# ---------------------------------------------------------
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_scan = types.KeyboardButton("🚀 Scan Quantique Ultra")
    btn_accounts = types.KeyboardButton("💼 Gérer mes Comptes MT")
    btn_status = types.KeyboardButton("📊 Tableau de Bord")
    
    news_label = "🛡️ News Guard: ON" if trading_engine["news_guard_active"] else "⚠️ News Guard: OFF"
    btn_news_toggle = types.KeyboardButton(news_label)
    
    if trading_engine["trading_active"]:
        btn_kill = types.KeyboardButton("🛑 Activer Kill Switch")
    else:
        btn_kill = types.KeyboardButton("🔄 Réarmer le Moteur")
        
    markup.add(btn_scan, btn_accounts)
    markup.add(btn_news_toggle, btn_status)
    markup.add(btn_kill)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    active_acc = trading_engine["active_account_id"] or "Aucun"
    welcome_text = (
        "⚡ *CLTM Quant Engine v7.0 - NEWS GUARD*\n"
        "________________________________________\n\n"
        "Moteur SMC avec protection anti-annonces majeures.\n\n"
        f"• *Statut Moteur:* " + ("🟢 EN LIGNE" if trading_engine["trading_active"] else "🔴 STOPPÉ") + "\n"
        f"• *Filtre News (NFP/CPI):* " + ("🛡️ ACTIF" + " (Protégé)" if trading_engine["news_guard_active"] else "⚠️ INACTIF") + "\n"
        f"• *Compte Actif:* `{active_acc}`\n"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- BOUTON TOGGLE NEWS GUARD ---
@bot.message_handler(func=lambda m: "News Guard" in m.text)
def toggle_news_guard(message):
    trading_engine["news_guard_active"] = not trading_engine["news_guard_active"]
    status_text = "🛡️ **Filtre News Guard activé.** Le bot se protégera automatiquement des annonces NFP/CPI." if trading_engine["news_guard_active"] else "⚠️ **Filtre News Guard désactivé.** Attention au slippage sur annonces !"
    bot.send_message(message.chat.id, status_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- GESTION DES COMPTES (Identique) ---
@bot.message_handler(func=lambda m: m.text == "💼 Gérer mes Comptes MT")
def manage_accounts_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for name, data in trading_engine["accounts"].items():
        acc_id = data["account_id"]
        is_active = (acc_id == trading_engine["active_account_id"])
        icon = "🟢 (Actif)" if is_active else "⚪"
        markup.add(types.InlineKeyboardButton(f"{icon} {name} - ID: {acc_id}", callback_data=f"set_{acc_id}"))
    markup.add(types.InlineKeyboardButton("➕ Connecter un Nouveau Compte MT", callback_data="add_acc"))
    if trading_engine["active_account_id"]:
        markup.add(types.InlineKeyboardButton("🔌 Déconnecter le Compte Actif", callback_data="disconnect_acc"))

    bot.send_message(
        message.chat.id,
        "💼 *GESTION COMPTES METATRADER*\n________________________________________\n\nSélectionnez un compte :",
        parse_mode="Markdown", reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    if call.data == "add_acc":
        user_forms[call.message.chat.id] = {}
        msg = bot.send_message(call.message.chat.id, "1️⃣ Entrez un **Nom de repère** pour ce compte (ex: *Compte FTMO*) :", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_name)
    elif call.data.startswith("set_"):
        acc_id = call.data.replace("set_", "")
        trading_engine["active_account_id"] = acc_id
        bot.answer_callback_query(call.id, "Compte sélectionné !")
        bot.send_message(call.message.chat.id, f"✅ **Compte MT Actif :** `{acc_id}`", parse_mode="Markdown", reply_markup=get_main_keyboard())
    elif call.data == "disconnect_acc":
        trading_engine["active_account_id"] = None
        bot.answer_callback_query(call.id, "Compte déconnecté.")
        bot.send_message(call.message.chat.id, "🔌 **Compte déconnecté.**", reply_markup=get_main_keyboard())

def step_name(message):
    user_forms[message.chat.id]["name"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "2️⃣ Entrez la **Plateforme** (`MT4` ou `MT5`) :", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_platform)

def step_platform(message):
    platform = message.text.strip().upper()
    if platform not in ["MT4", "MT5"]: platform = "MT5"
    user_forms[message.chat.id]["platform"] = platform
    msg = bot.send_message(message.chat.id, "3️⃣ Entrez le **Nom exact du Serveur** (ex: `ICMarkets-Live18`) :", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_server)

def step_server(message):
    user_forms[message.chat.id]["server"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "4️⃣ Entrez le **Login MetaTrader** (Numéro de compte) :", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_login)

def step_login(message):
    user_forms[message.chat.id]["login"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "5️⃣ Entrez le **Mot de passe MetaTrader** :", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_password)

def step_password(message):
    password = message.text.strip()
    form = user_forms[message.chat.id]
    bot.send_message(message.chat.id, "⏳ *Déploiement du compte sur MetaAPI en cours...*", parse_mode="Markdown")
    
    success, result = create_metaapi_account(form["name"], form["platform"], form["server"], form["login"], password)

    if success:
        account_id = result
        trading_engine["accounts"][form["name"]] = {"account_id": account_id, "login": form["login"], "server": form["server"]}
        trading_engine["active_account_id"] = account_id
        bot.send_message(message.chat.id, f"🎉 *Compte Connecté avec Succès !*\n• **ID :** `{account_id}`", parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        bot.send_message(message.chat.id, f"❌ *Échec :*\n{result}", parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- SCAN & STATUS ---
@bot.message_handler(func=lambda m: m.text in ["🚀 Scan Quantique Ultra", "/scan"])
def trigger_analysis(message):
    if not trading_engine["trading_active"]:
        bot.send_message(message.chat.id, "⚠️ *Moteur Verrouillé.*", reply_markup=get_main_keyboard())
        return

    # Vérification préventive des annonces avant d'afficher le scan
    has_news, news_reason = check_high_impact_news()
    if has_news and trading_engine["news_guard_active"]:
        bot.send_message(message.chat.id, f"🛡️ **SCAN MIS EN PAUSE PAR LE NEWS GUARD**\n\n{news_reason}\n\n*Le bot refuse de trader pendant cette période à haut risque pour protéger ton capital.*", parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    bot.send_message(message.chat.id, "⚡ *Analyse Tri-Timeframe & Vérification News Guard...*", parse_mode="Markdown")
    assets = ["EURUSD=X", "GBPUSD=X", "GC=F", "BTC-USD"]
    asset_names = {"EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "GC=F": "OR (XAUUSD)", "BTC-USD": "BITCOIN"}

    active_acc = trading_engine["active_account_id"] or "Aucun"
    msg = f"🎯 *RÉSULTATS DU SCAN (Compte: `{active_acc}`)*\n________________________________________\n\n"

    for asset in assets:
        res = analyze_ultra_setup(asset)
        name = asset_names.get(asset, asset)
        if res and "Rang S" in res['signal']:
            msg += f"🔥 *{name}* : Signal *{res['signal']}*\n"
            msg += f"   ├ 💵 Prix: `{res['price']}` | 🛑 SL: `{res['sl']}`\n"
            msg += f"   ├ 🎯 TP1: `{res['tp1']}` | 🎯 TP2: `{res['tp2']}`\n"
            msg += f"   ├ 🌐 DXY: {res['dxy']} | H4: {res['h4']}{res['exec_log']}\n\n"
        else:
            msg += f"⚪ *{name}* : Neutre (Pas de setup SMC).\n"

    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text in ["📊 Tableau de Bord", "/status"])
def send_status(message):
    active_acc = trading_engine["active_account_id"] or "Aucun"
    equity = get_account_balance(active_acc) if active_acc != "Aucun" else "N/A"
    news_status = "🛡️ Actif (Sécurisé)" if trading_engine["news_guard_active"] else "⚠️ Inactif"
    
    status_msg = (
        "📊 *TABLEAU DE BORD - RANG S PRIME*\n"
        "________________________________________\n\n"
        f"• *Moteur:* " + ("🟢 EN LIGNE" if trading_engine["trading_active"] else "🔴 SUSPENDU") + "\n"
        f"• *Filtre News Guard:* {news_status}\n"
        f"• *Compte Actif ID:* `{active_acc}`\n"
        f"• *Équité Estimée:* `{equity} $`\n"
    )
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text in ["🛑 Activer Kill Switch", "🔄 Réarmer le Moteur"])
def toggle_kill_switch(message):
    if "Réarmer" in message.text:
        trading_engine["trading_active"] = True
        bot.send_message(message.chat.id, "🟢 *MOTEUR RÉARMÉ.*", reply_markup=get_main_keyboard())
    else:
        trading_engine["trading_active"] = False
        bot.send_message(message.chat.id, "🛑 *KILL SWITCH ACTIVÉ.*", reply_markup=get_main_keyboard())

# ---------------------------------------------------------
# 7. DÉMARRAGE DU BOT
# ---------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("Démarrage du bot Telegram Rang S avec News Guard...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
        
