import random
import string
import time
import hashlib
import hmac
import base64
import struct
import telebot
from telebot import types
import sqlite3
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8710250567:AAGlNXEebORVmQVNxQhUcruesskKrN2iSgQ"
ADMIN_ID = 8061525743
CHANNEL_USERNAME = "@DailyReportUpdate"
SUPPORT_ID = "@Tanjim_admin_support"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        invites INTEGER DEFAULT 0,
        referrer_id INTEGER,
        joined_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_username TEXT,
        password TEXT,
        fa_secret TEXT,
        timestamp TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def generate_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6)) + "acc"

def generate_random_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def get_totp_code(secret):
    try:
        secret = secret.replace(" ", "").upper()
        key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
        counter = struct.pack('>Q', int(time.time() // 30))
        hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = (struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"
    except:
        return "❌ ভুল কি!"

# ================= KEYBOARDS (Reply & Inline) =================

def main_menu():
    # Reply Keyboard Button ✅
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📋 কাজ"),
        types.KeyboardButton("💰 ব্যালেন্স"),
        types.KeyboardButton("🏦 টাকা উত্তোলন"),
        types.KeyboardButton("🏆 লিডারবোর্ড"),
        types.KeyboardButton("🎁 Invite & Earn"),
        types.KeyboardButton("📞 সাপোর্ট")
    )
    return markup

def admin_panel_menu():
    # Admin Reply Keyboard ✅
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 স্ট্যাটাস", "👥 ইউজার লিস্ট", "📜 উইথড্র হিস্টরি", "🏠 মেইন মেনু")
    return markup

# ================= HANDLERS =================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.first_name
    
    conn = sqlite3.connect("users.db")
    conn.execute("INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?,?,?)", 
                 (uid, uname, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    if uid == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 <b>স্বাগতম তানজিম বস!</b>\nআপনি অ্যাডমিন হিসেবে লগইন করেছেন।", reply_markup=admin_panel_menu())
    else:
        bot.send_message(message.chat.id, f"👋 স্বাগতম <b>{uname}</b>!\nকাজে যোগ দিতে নিচের মেনু ব্যবহার করুন।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📋 কাজ")
def task_select(message):
    # Inline Keyboard Button ✅
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📸 Instagram 2FA (৳2.50)", callback_data="start_ig_task"))
    bot.send_message(message.chat.id, "👇 নিচের থেকে টাস্কটি শুরু করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "start_ig_task")
def ig_task_init(call):
    user_id = call.from_user.id
    username = generate_username()
    password = generate_random_password()
    
    text = f"""
🚀 <b>নতুন টাস্ক জেনারেট হয়েছে!</b>
━━━━━━━━━━━━━━━━━━━━
👤 <b>Username:</b> <code>{username}</code>
🔑 <b>Password:</b> <code>{password}</code>
━━━━━━━━━━━━━━━━━━━━
⚠️ এই তথ্য দিয়ে একাউন্ট খুলে <b>2FA Secret Key</b> টি পাঠান।
"""
    # Inline Button ✅
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔐 Secret Key পাঠান", callback_data=f"send_key_{username}_{password}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_key_"))
def ask_key(call):
    data = call.data.split("_")
    username, password = data[2], data[3]
    msg = bot.send_message(call.message.chat.id, "🔑 আপনার <b>2FA Secret Key</b> টি এখানে পেস্ট করুন:")
    bot.register_next_step_handler(msg, save_task, username, password)

def save_task(message, username, password):
    secret = message.text.strip()
    uid = message.from_user.id
    otp = get_totp_code(secret)
    
    # অ্যাডমিনের কাছে পাঠানোর ইনলাইন বাটন ✅
    admin_btn = types.InlineKeyboardMarkup()
    admin_btn.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
    )
    
    # অ্যাডমিনকে জানানো
    bot.send_message(ADMIN_ID, f"🆕 <b>নতুন রিপোর্ট!</b>\nUID: <code>{uid}</code>\nUser: <code>{username}</code>\nPass: <code>{password}</code>\nKey: <code>{secret}</code>\nOTP: <code>{otp}</code>", reply_markup=admin_btn)
    
    bot.send_message(message.chat.id, "✅ আপনার টাস্ক জমা হয়েছে! অ্যাডমিন চেক করে ব্যালেন্স যোগ করে দিবে।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 ব্যালেন্স")
def check_balance(message):
    conn = sqlite3.connect("users.db")
    res = conn.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    conn.close()
    bal = res[0] if res else 0
    bot.send_message(message.chat.id, f"💰 আপনার বর্তমান ব্যালেন্স: <b>{bal:.2f} ৳</b>")

@bot.message_handler(func=lambda m: m.text == "🏠 মেইন মেনু")
def go_back(message):
    bot.send_message(message.chat.id, "🏠 মেইন মেনু", reply_markup=main_menu())

# ================= RUN =================
if __name__ == "__main__":
    print("Bot is active...")
    bot.infinity_polling()
                     
