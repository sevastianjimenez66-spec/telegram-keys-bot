# main.py
import os
import sqlite3
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types

TOKEN = os.environ.get("8339543175:AAE1XgQiAuDaW51fAh7q0rizN3Auf429Xio")  # <- variable de entorno en Render
ADMIN_ID = 5593967825  # reemplaza solo si quieres otro admin

if not TOKEN:
    raise SystemExit("ERROR: TELEGRAM_TOKEN no está definida en las variables de entorno.")

# Bot
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Flask para health check / keep-alive
app = Flask(__name__)
@app.route("/")
def home():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

# DB init
DB_PATH = "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    user_id INTEGER PRIMARY KEY,
                    creditos INTEGER DEFAULT 0,
                    admin INTEGER DEFAULT 0
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS duraciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto_id INTEGER,
                    nombre TEXT,
                    precio INTEGER
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duracion_id INTEGER,
                    key TEXT,
                    usada INTEGER DEFAULT 0
                )""")
    conn.commit()
    conn.close()

init_db()

# util
def registrar_usuario(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (user_id, creditos, admin) VALUES (?, 0, 0)", (user_id,))
        conn.commit()
    conn.close()

def es_admin(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT admin FROM usuarios WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r and r[0] == 1

# Handlers
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    registrar_usuario(msg.from_user.id)
    if msg.from_user.id == ADMIN_ID:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE usuarios SET admin=1 WHERE user_id=?", (msg.from_user.id,))
        conn.commit()
        conn.close()

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Productos", "💰 Mis créditos")
    if es_admin(msg.from_user.id):
        kb.add("⚙️ Panel Admin")
    await msg.answer("Bienvenido. Selecciona una opción:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🛒 Productos")
async def listar_productos(msg: types.Message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nombre FROM productos")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await msg.reply("No hay productos disponibles.")
        return
    kb = types.InlineKeyboardMarkup()
    for pid, nombre in rows:
        kb.add(types.InlineKeyboardButton(nombre, callback_data=f"producto_{pid}"))
    await msg.reply("Elige un producto:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("producto_"))
async def ver_duraciones(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nombre, precio FROM duraciones WHERE producto_id=?", (pid,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await call.message.edit_text("Este producto no tiene duraciones.")
        return
    kb = types.InlineKeyboardMarkup()
    for did, nombre, precio in rows:
        kb.add(types.InlineKeyboardButton(f"{nombre} — {precio} créditos", callback_data=f"duracion_{did}"))
    await call.message.edit_text("Selecciona la duración:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("duracion_"))
async def comprar(call: types.CallbackQuery):
    did = int(call.data.split("_")[1])
    user_id = call.from_user.id

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT nombre, precio FROM duraciones WHERE id=?", (did,))
    dur = c.fetchone()
    if not dur:
        await call.message.edit_text("Duración no encontrada.")
        conn.close()
        return

    c.execute("SELECT creditos FROM usuarios WHERE user_id=?", (user_id,))
    credits = c.fetchone()
    credits = credits[0] if credits else 0

    c.execute("SELECT id, key FROM keys WHERE duracion_id=? AND usada=0 LIMIT 1", (did,))
    keyrow = c.fetchone()
    if not keyrow:
        await call.message.edit_text("No hay keys disponibles para esta opción.")
        conn.close()
        return

    key_id, key_val = keyrow
    price = dur[1]
    if credits < price:
        await call.message.edit_text(f"No tienes créditos suficientes. Necesitas {price}, tienes {credits}.")
        conn.close()
        return

    c.execute("UPDATE usuarios SET creditos = creditos - ? WHERE user_id=?", (price, user_id))
    c.execute("UPDATE keys SET usada=1 WHERE id=?", (key_id,))
    conn.commit()
    conn.close()

    await call.message.edit_text(f"Compra exitosa 🎉\nTu key:\n\n{key_val}")

@dp.message_handler(lambda m: m.text == "⚙️ Panel Admin")
async def panel_admin(msg: types.Message):
    if not es_admin(msg.from_user.id):
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Agregar Producto", "➕ Agregar Duración")
    kb.add("➕ Agregar Key", "➕ Agregar Créditos")
    kb.add("⬅️ Volver")
    await msg.reply("Panel admin:", reply_markup=kb)

# Ejecutar Flask en hilo y bot en polling
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    executor.start_polling(dp, skip_updates=True)
