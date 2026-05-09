import telebot
import sqlite3
import time
import base64
import hmac
import hashlib
import struct
from telebot import types
from flask import Flask
from threading import Thread

# ================= CONFIGURATION =================
TOKEN = "8783194900:AAH__MsqIgqwKn_-Pzg2NdxQsIJ1OjvAVY8"
ADMIN_ID = 8061525743 
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask('')

# ================= DATABASE & SETTINGS =================
def init_db():
    conn = sqlite3.connect("bot_master.db")
    cur = conn.cursor()
    # ইউজার টেবিল
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
    # রিপোর্ট টেবিল
    cur.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, content TEXT)")
    # সেটিংস টেবিল (যেখানে টেক্সট ও রেট সেভ থাকবে)
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    
    # ডিফল্ট সেটিংস (যদি আগে থেকে না থাকে)
    default_settings = [
        ('ig_2fa_msg', '🔐 আপনার 2FA Key (Secret Key) টি এখানে পাঠান:'),
        ('ig_cookie_msg', '🍪 আপনার Instagram Cookies টি এখানে পেস্ট করুন:'),
        ('welcome_msg', '👋 স্বাগতম! আমাদের বটে কাজ করে টাকা ইনকাম করুন।'),
        ('rate_msg', '💰 বর্তমান রেট: প্রতি একাউন্ট ৫-১০ টাকা।')
    ]
    cur.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", default_settings)
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect("bot_master.db")
    res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return res[0] if res else "Not Set"

# ================= 2FA LOGIC =================
def get_2fa_otp(secret):
    try:
        secret = secret.replace(" ", "").upper()
        key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
        counter = struct.pack('>Q', int(time.time() // 30))
        hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = (struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"
    except:
        return None

# ================= KEYBOARDS =================
def main_menu(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📋 Tasks", "💰 Balance", "👤 Profile", "📞 Support")
    if uid == ADMIN_ID:
        markup.add("👑 Admin Panel")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📝 Edit Texts", "💰 Add Balance", "📜 View Reports", "🏠 Home")
    return markup

# ================= HANDLERS =================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    conn = sqlite3.connect("bot_master.db")
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()
    bot.send_message(uid, get_setting('welcome_msg'), reply_markup=main_menu(uid))

# --- 📋 TASK SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def tasks(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📸 Instagram 2FA", "🍪 IG Cookies", "🔙 Back")
    bot.send_message(message.chat.id, get_setting('rate_msg'), reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📸 Instagram 2FA")
def ig_2fa(message):
    msg = bot.send_message(message.chat.id, get_setting('ig_2fa_msg'), reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_2fa)

def process_2fa(message):
    if message.text == "🔙 Back": return
    otp = get_2fa_otp(message.text)
    if otp:
        bot.send_message(message.chat.id, f"✅ আপনার কোড: <code>{otp}</code>", reply_markup=main_menu(message.from_user.id))
    else:
        msg = bot.send_message(message.chat.id, "⚠️ ভুল Key! দয়া করে সঠিক 2FA Key দিন:")
        bot.register_next_step_handler(msg, process_2fa)

@bot.message_handler(func=lambda m: m.text == "🍪 IG Cookies")
def ig_cookie(message):
    msg = bot.send_message(message.chat.id, get_setting('ig_cookie_msg'))
    bot.register_next_step_handler(msg, save_cookie)

def save_cookie(message):
    conn = sqlite3.connect("bot_master.db")
    conn.execute("INSERT INTO reports (user_id, type, content) VALUES (?,?,?)", (message.from_user.id, "Cookie", message.text))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ কুকি জমা হয়েছে!", reply_markup=main_menu(message.from_user.id))

# ================= 👑 ADMIN CONTROL =================

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel" and m.from_user.id == ADMIN_ID)
def admin_p(message):
    bot.send_message(message.chat.id, "স্বাগতম তানজিম বস! কি এডিট করতে চান?", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "📝 Edit Texts" and m.from_user.id == ADMIN_ID)
def edit_list(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Welcome Text", callback_data="set_welcome_msg"))
    markup.add(types.InlineKeyboardButton("2FA Instruction", callback_data="set_ig_2fa_msg"))
    markup.add(types.InlineKeyboardButton("Cookie Instruction", callback_data="set_ig_cookie_msg"))
    markup.add(types.InlineKeyboardButton("Rate/Price Text", callback_data="set_rate_msg"))
    bot.send_message(message.chat.id, "কোন টেক্সটটি পরিবর্তন করবেন?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def callback_set_text(call):
    key = call.data.replace("set_", "")
    msg = bot.send_message(call.message.chat.id, f"নতুন টেক্সটটি লিখে পাঠান (Key: {key}):")
    bot.register_next_step_handler(msg, update_setting, key)

def update_setting(message, key):
    conn = sqlite3.connect("bot_master.db")
    conn.execute("UPDATE settings SET value=? WHERE key=?", (message.text, key))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ সফলভাবে আপডেট হয়েছে!", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🔙 Back" or m.text == "🏠 Home")
def back_home(message):
    bot.send_message(message.chat.id, "মেইন মেনু", reply_markup=main_menu(message.from_user.id))

# ================= RUN =================
if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    bot.infinity_polling()
    
