import telebot
from telebot import types
import json
import os
from flask import Flask
import threading

# ----------------- CONFIG -----------------
TOKEN = "8156062603:AAGPtV0nhKmziDO9KvUjBsvAwk9VExe9Ljc"  # Reemplaza con tu token
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"
ADMINS = [5593967825, 5593967825]  # Reemplaza con los IDs de tus admins

# ----------------- FLASK WEB SERVER -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot activo ✅"

def run_webserver():
    app.run(host="0.0.0.0", port=3000)

# ----------------- FUNCIONES DE DATOS -----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": {}, "products": {}, "reset_keys": []}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ----------------- MENÚ PRINCIPAL -----------------
def main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Productos", callback_data="menu_productos"))
    markup.add(types.InlineKeyboardButton("🔄 Resetear Key", callback_data="menu_reset"))
    markup.add(types.InlineKeyboardButton("🛠 Panel de Admin", callback_data="menu_admin"))
    bot.send_message(chat_id, "✨ Bienvenido a la tienda! Usa /info para ver tu saldo", reply_markup=markup)

@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {"saldo": 0}
        save_data(data)
    main_menu(message.chat.id)

@bot.message_handler(commands=["info"])
def info(message):
    user_id = str(message.from_user.id)
    data = load_data()
    saldo = data["users"].get(user_id, {}).get("saldo", 0)
    bot.send_message(message.chat.id, f"💰 Tu saldo: {saldo} créditos")

# ----------------- CALLBACK HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    data = load_data()
    text = call.data

    # ---------- MENÚ PRINCIPAL ----------
    if text == "menu_productos":
        if not data["products"]:
            bot.edit_message_text("❌ No hay productos disponibles", call.message.chat.id, call.message.message_id)
            return
        markup = types.InlineKeyboardMarkup()
        for prod in data["products"]:
            markup.add(types.InlineKeyboardButton(f"📦 {prod}", callback_data=f"producto_{prod}"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_inicio"))
        bot.edit_message_text("🛒 Productos disponibles:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text == "menu_reset":
        msg = bot.edit_message_text("🔄 Por favor envía la key que deseas resetear", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(msg, resetear_key_step)

    elif text == "menu_admin":
        if int(user_id) not in ADMINS:
            bot.answer_callback_query(call.id, "❌ No tienes permisos de admin")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Agregar Producto", callback_data="admin_agregar_producto"))
        markup.add(types.InlineKeyboardButton("🗑 Borrar Producto", callback_data="admin_borrar_producto"))
        markup.add(types.InlineKeyboardButton("🔑 Agregar Keys", callback_data="admin_agregar_keys"))
        markup.add(types.InlineKeyboardButton("💳 Agregar Saldo", callback_data="admin_agregar_saldo"))
        markup.add(types.InlineKeyboardButton("🔄 Ver Keys para Resetear", callback_data="admin_ver_reset"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_inicio"))
        bot.edit_message_text("🛠 Panel de Admin", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text == "menu_inicio":
        bot.edit_message_text("✨ Menú principal", call.message.chat.id, call.message.message_id)
        main_menu(call.message.chat.id)

    # ---------- PRODUCTOS ----------
    elif text.startswith("producto_"):
        prod = text.split("_", 1)[1]
        if prod not in data["products"]:
            bot.answer_callback_query(call.id, "❌ Producto no existe")
            return
        markup = types.InlineKeyboardMarkup()
        for dur in data["products"][prod]:
            stock = len(data["products"][prod][dur]["keys"])
            markup.add(types.InlineKeyboardButton(f"{dur} días - Stock: {stock}", callback_data=f"comprar_{prod}_{dur}"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_productos"))
        bot.edit_message_text(f"📦 Producto: {prod}", call.message.chat.id, call.message.message_id, reply_markup=markup)

    # ---------- COMPRA ----------
    elif text.startswith("comprar_"):
        _, prod, dur = text.split("_")
        stock = len(data["products"][prod][dur]["keys"])
        if stock == 0:
            bot.answer_callback_query(call.id, "❌ No hay stock disponible")
            return
        precio = data["products"][prod][dur]["precio"]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Confirmar compra", callback_data=f"confirmar_{prod}_{dur}"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data=f"producto_{prod}"))
        bot.edit_message_text(f"💵 Precio: {precio}\nDeseas comprar {dur} días de {prod}?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text.startswith("confirmar_"):
        _, prod, dur = text.split("_")
        user_data = data["users"].get(user_id)
        if user_data["saldo"] < data["products"][prod][dur]["precio"]:
            bot.answer_callback_query(call.id, "❌ No tienes suficiente saldo")
            return
        key = data["products"][prod][dur]["keys"].pop(0)
        user_data["saldo"] -= data["products"][prod][dur]["precio"]
        save_data(data)
        bot.edit_message_text(f"🎉 Compra exitosa!\nTu key: `{key}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif text == "cancelar":
        bot.edit_message_text("❌ Compra cancelada", call.message.chat.id, call.message.message_id)

    # ---------- ADMIN ----------
    elif text == "admin_agregar_producto":
        msg = bot.edit_message_text("✏ Escribe el nombre del nuevo producto", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(msg, admin_agregar_producto)

    elif text == "admin_borrar_producto":
        if not data["products"]:
            bot.answer_callback_query(call.id, "❌ No hay productos para borrar")
            return
        markup = types.InlineKeyboardMarkup()
        for prod in data["products"]:
            markup.add(types.InlineKeyboardButton(prod, callback_data=f"admin_borrar_{prod}"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_admin"))
        bot.edit_message_text("🗑 Selecciona un producto para borrar", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text.startswith("admin_borrar_"):
        prod = text.split("_",2)[2]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Sí, borrar", callback_data=f"admin_confirmar_borrar_{prod}"))
        markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data="menu_admin"))
        bot.edit_message_text(f"⚠ ¿Deseas borrar el producto '{prod}'?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text.startswith("admin_confirmar_borrar_"):
        prod = text.split("_",3)[3]
        data["products"].pop(prod, None)
        save_data(data)
        bot.edit_message_text(f"✅ Producto '{prod}' borrado correctamente", call.message.chat.id, call.message.message_id)

    elif text == "admin_agregar_keys":
        if not data["products"]:
            bot.answer_callback_query(call.id, "❌ No hay productos para agregar keys")
            return
        markup = types.InlineKeyboardMarkup()
        for prod in data["products"]:
            markup.add(types.InlineKeyboardButton(prod, callback_data=f"admin_keys_{prod}"))
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_admin"))
        bot.edit_message_text("🔑 Selecciona un producto para agregar keys", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text.startswith("admin_keys_"):
        prod = text.split("_",2)[2]
        msg = bot.edit_message_text("⏳ Duración de la key (1, 7, 30 días)", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(msg, lambda m: admin_agregar_keys_duracion(m, prod))

    elif text == "admin_agregar_saldo":
        msg = bot.edit_message_text("💳 Ingresa el ID del usuario a recargar", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(msg, admin_agregar_saldo_usuario)

    elif text == "admin_ver_reset":
        if not data["reset_keys"]:
            bot.answer_callback_query(call.id, "❌ No hay keys para resetear")
            return
        markup = types.InlineKeyboardMarkup()
        for idx, rk in enumerate(data["reset_keys"]):
            markup.add(
                types.InlineKeyboardButton(f"{rk['key']} de {rk['user']} ✅", callback_data=f"reset_{idx}_ok"),
                types.InlineKeyboardButton("❌", callback_data=f"reset_{idx}_no")
            )
        markup.add(types.InlineKeyboardButton("⬅ Volver", callback_data="menu_admin"))
        bot.edit_message_text("🔄 Keys para resetear", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif text.startswith("reset_"):
        _, idx, accion = text.split("_")
        idx = int(idx)
        rk = data["reset_keys"][idx]
        if accion == "ok":
            bot.send_message(rk["user"], f"✅ Tu key {rk['key']} fue reseteada correctamente")
        else:
            bot.send_message(rk["user"], f"❌ Tu key {rk['key']} no fue reseteada")
        data["reset_keys"].pop(idx)
        save_data(data)
        bot.answer_callback_query(call.id, "Acción realizada")

# ----------------- FUNCIONES ADMIN Y RESET -----------------
def admin_agregar_producto(message):
    nombre = message.text
    data = load_data()
    if nombre in data["products"]:
        bot.send_message(message.chat.id, "❌ Producto ya existe")
        return
    data["products"][nombre] = {}
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Producto '{nombre}' agregado")

def admin_agregar_keys_duracion(message, prod):
    dur = message.text
    if dur not in ["1","7","30"]:
        bot.send_message(message.chat.id, "❌ Duración inválida")
        return
    msg = bot.send_message(message.chat.id, "💰 Precio de la key")
    bot.register_next_step_handler(msg, lambda m: admin_agregar_keys_precio(m, prod, dur))

def admin_agregar_keys_precio(message, prod, dur):
    try:
        precio = int(message.text)
    except:
        bot.send_message(message.chat.id, "❌ Precio inválido")
        return
    msg = bot.send_message(message.chat.id, "🔑 Envía la key")
    bot.register_next_step_handler(msg, lambda m: admin_agregar_keys_final(m, prod, dur, precio))

def admin_agregar_keys_final(message, prod, dur, precio):
    key = message.text
    data = load_data()
    if dur not in data["products"][prod]:
        data["products"][prod][dur] = {"precio": precio, "keys": []}
    data["products"][prod][dur]["keys"].append(key)
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Key agregada correctamente al producto {prod} ({dur} días)")

def admin_agregar_saldo_usuario(message):
    user_id = message.text
    msg = bot.send_message(message.chat.id, "💳 Ingresa la cantidad a recargar")
    bot.register_next_step_handler(msg, lambda m: admin_agregar_saldo_final(m, user_id))

def admin_agregar_saldo_final(message, user_id):
    try:
        cantidad = int(message.text)
    except:
        bot.send_message(message.chat.id, "❌ Cantidad inválida")
        return
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {"saldo": 0}
    data["users"][user_id]["saldo"] += cantidad
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Saldo agregado correctamente a {user_id}")

def resetear_key_step(message):
    key = message.text
    user_id = message.from_user.id
    data = load_data()
    data["reset_keys"].append({"key": key, "user": user_id})
    save_data(data)
    bot.send_message(message.chat.id, "✅ Key enviada. Espera a que un admin la reseteé")

# ----------------- INICIO DEL BOT -----------------
if __name__ == "__main__":
    threading.Thread(target=run_webserver).start()
    bot.infinity_polling()
