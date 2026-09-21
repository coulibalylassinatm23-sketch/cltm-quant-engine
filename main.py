import os
import threading
import requests
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
    return "Bot Quantique Rang S - Provisioning Dynamique en ligne !", 200

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

# Moteur global et stockage mémoire des comptes enregistrés
trading_engine = {
    "trading_active": True,
    "consecutive_losses": 0,
    "risk_percent": 0.01,
    "active_account_id": os.getenv('METAAPI_ACCOUNT_ID', None),
    "accounts": {}  # { "NomCompte": {"account_id": "xxx", "login": "123", "server": "yyy"} }
}

# Mémoire temporaire pour la saisie guidée par étape
user_forms = {}

# ---------------------------------------------------------
# 3. INTERACTION DYNAMIQUE METAAPI (Provisioning automatique)
# ---------------------------------------------------------
def create_metaapi_account(name, type_mt, server, login, password):
    """
    Crée et déploie automatiquement un nouveau compte MetaTrader 
    sur la plateforme MetaAPI à partir des identifiants saisis sur Telegram.
    """
    if not METAAPI_TOKEN:
        return False, "Le jeton global METAAPI_TOKEN n'est pas configuré sur le serveur Render."

    url = "https://mt-provisioning-api-v1.agium.celp.metatrader.com/users/current/accounts"
    headers = {
        "auth-token": METAAPI_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "name": name,
        "type": "cloud",
        "login": str(login),
        "password": password,
        "server": server,
        "platform": type_mt.lower(), # mt4 ou mt5
        "application": "MetaTrader"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            data = response.json()
            account_id = data.get("id")
            
            # Lancement automatique du déploiement du compte cloud
            deploy_url = f"https://mt-provisioning-api-v1.agium.celp.metatrader.com/users/current/accounts/{account_id}/deploy"
            requests.post(deploy_url, headers=headers, timeout=10)
            
            return True, account_id
        else:
            return False, f"Erreur MetaAPI ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Erreur de connexion MetaAPI: {e}"

def get_account_balance(account_id):
    """Récupère le solde/équité en temps réel du compte via MetaAPI"""
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
        "actionType": order_type,
        "symbol": clean_symbol,
        "volume": lot,
        "stopLoss": sl,
        "takeProfit": tp1,
        "comment": f"Rang S Prime [{lot} Lots]"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            return True, f"Ordre placé avec succès sur MetaTrader ! Lot: {lot}"
        else:
            return False, f"Erreur Execution ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Erreur Réseau: {e}"

# ---------------------------------------------------------
# 4. ALGORITHME RANG S (Multi-Timeframe & DXY)
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
            execution_log = f"\n   └ 🤖 *Auto-Trade:* {'✅ Executé' if success else '⚠️ ' + msg}"

        return {
            "symbol": symbol, "signal": signal, "price": round(last_close, 5),
            "sl": round(sl, 5), "tp1": tp1, "tp2": tp2, 
            "dxy": dxy_trend, "h4": h4_trend, "exec_log": execution_log
        }
    except Exception:
        return None

# ---------------------------------------------------------
# 5. INTERFACE TELEGRAM & FORMULAIRE GUIDÉ
# ---------------------------------------------------------
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_scan = types.KeyboardButton("🚀 Scan Quantique Ultra")
    btn_accounts = types.KeyboardButton("💼 Gérer mes Comptes MT")
    btn_status = types.KeyboardButton("📊 Tableau de Bord")
    
    if trading_engine["trading_active"]:
        btn_kill = types.KeyboardButton("🛑 Activer Kill Switch")
    else:
        btn_kill = types.KeyboardButton("🔄 Réarmer le Moteur")
        
    markup.add(btn_scan, btn_accounts)
    markup.add(btn_status, btn_kill)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    active_acc = trading_engine["active_account_id"] or "Aucun"
    welcome_text = (
        "⚡ *CLTM Quant Engine v6.0 - PRIME RANG S*\n"
        "________________________________________\n\n"
        "Interface de gestion multi-comptes dynamique.\n\n"
        f"• *Statut Moteur:* " + ("🟢 EN LIGNE" if trading_engine["trading_active"] else "🔴 STOPPÉ") + "\n"
        f"• *Compte MT Actif:* `{active_acc}`\n"
        f"• *Comptes Configurés:* {len(trading_engine['accounts'])}\n"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- GESTION ET CONNEXION DE COMPTES ---
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
        "💼 *GESTION COMPTES METATRADER*\n"
        "________________________________________\n\n"
        "Sélectionnez un compte ou ajoutez-en un nouveau :",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    if call.data == "add_acc":
        user_forms[call.message.chat.id] = {}
        msg = bot.send_message(call.message.chat.id, "1️⃣ Entrez un **Nom de repère** pour ce compte (ex: *Mon Compte Réel FTMO*) :", parse_mode="Markdown")
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

# --- ÉTAPES DU FORMULAIRE TELEGRAM ---
def step_name(message):
    user_forms[message.chat.id]["name"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "2️⃣ Entrez la **Plateforme** (`MT4` ou `MT5`) :", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_platform)

def step_platform(message):
    platform = message.text.strip().upper()
    if platform not in ["MT4", "MT5"]:
        platform = "MT5"
    user_forms[message.chat.id]["platform"] = platform
    msg = bot.send_message(message.chat.id, "3️⃣ Entrez le **Nom exact du Serveur** (ex: `ICMarkets-Live18` ou `Exness-MT5Real`) :", parse_mode="Markdown")
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
    
    bot.send_message(message.chat.id, "⏳ *Connexion et déploiement du compte sur MetaAPI en cours...*", parse_mode="Markdown")
    
    success, result = create_metaapi_account(
        name=form["name"],
        type_mt=form["platform"],
        server=form["server"],
        login=form["login"],
        password=password
    )

    if success:
        account_id = result
        trading_engine["accounts"][form["name"]] = {
            "account_id": account_id,
            "login": form["login"],
            "server": form["server"]
        }
        trading_engine["active_account_id"] = account_id
        
        bot.send_message(
            message.chat.id,
            f"🎉 *Compte MetaTrader Connecté avec Succès !*\n\n"
            f"• **Nom :** `{form['name']}`\n"
            f"• **Serveur :** `{form['server']}`\n"
            f"• **Account ID MetaAPI :** `{account_id}`\n\n"
            f"Le bot est désormais configuré pour trader sur ce compte.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ *Échec de la connexion :*\n{result}\n\nVérifiez vos identifiants et réessayez.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

# --- SCAN & STATUS ---
@bot.message_handler(func=lambda m: m.text in ["🚀 Scan Quantique Ultra", "/scan"])
def trigger_analysis(message):
    if not trading_engine["trading_active"]:
        bot.send_message(message.chat.id, "⚠️ *Moteur Verrouillé.* Réarmez-le dans le menu.", reply_markup=get_main_keyboard())
        return

    bot.send_message(message.chat.id, "⚡ *Analyse Tri-Timeframe (H4/H1/Macro DXY) & Auto-Trade...*", parse_mode="Markdown")
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
            msg += f"   ├ 🎯 TP1 (1:2): `{res['tp1']}` | 🎯 TP2 (1:3.5): `{res['tp2']}`\n"
            msg += f"   ├ 🌐 DXY Macro: {res['dxy']} | Trend H4: {res['h4']}{res['exec_log']}\n\n"
        else:
            msg += f"⚪ *{name}* : Neutre (Pas de confluence SMC).\n"

    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text in ["📊 Tableau de Bord", "/status"])
def send_status(message):
    active_acc = trading_engine["active_account_id"] or "Aucun"
    equity = get_account_balance(active_acc) if active_acc != "Aucun" else "N/A"
    
    status_msg = (
        "📊 *TABLEAU DE BORD GLOBAL*\n"
        "________________________________________\n\n"
        f"• *Moteur:* " + ("🟢 EN LIGNE" if trading_engine["trading_active"] else "🔴 SUSPENDU") + "\n"
        f"• *Compte Actif ID:* `{active_acc}`\n"
        f"• *Équité Estimée:* `{equity} $`\n"
        f"• *Comptes Sauvegardés:* {len(trading_engine['accounts'])}\n"
    )
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text in ["🛑 Activer Kill Switch", "🔄 Réarmer le Moteur"])
def toggle_kill_switch(message):
    if "Réarmer" in message.text:
        trading_engine["trading_active"] = True
        bot.send_message(message.chat.id, "🟢 *MOTEUR RÉARMÉ.* L'auto-trading est actif.", reply_markup=get_main_keyboard())
    else:
        trading_engine["trading_active"] = False
        bot.send_message(message.chat.id, "🛑 *KILL SWITCH ACTIVÉ.* Le moteur est verrouillé.", reply_markup=get_main_keyboard())

# ---------------------------------------------------------
# 6. DÉMARRAGE DU BOT
# ---------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("Démarrage du bot Telegram Rang S Dynamique...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
