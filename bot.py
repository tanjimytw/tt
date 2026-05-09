import telebot
import random
import string
import time
import sqlite3
import requests
import base64
import hmac
import hashlib
import struct
import logging
import re
from telebot import types, util
from datetime import datetime
from flask import Flask
from threading import Thread

# ================= CONFIGURATION =================
TOKEN = "8783194900:AAH__MsqIgqwKn_-Pzg2NdxQsIJ1OjvAVY8"
ADMIN_ID = 8061525743  
SUPPORT_USER = "@FB_SALL_AD"
MIN_WITHDRAW = 100.0  # সর্বনিম্ন উইথড্র ১০০ টাকা

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask('')

# ================= DATABASE MANAGER =================
class Database:
    def __init__(self, db_name="master_data.db"):
        self.db_name = db_name
        self.init_db()

    def query(self, sql, params=(), commit=False):
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql, params)
            if commit:
                conn.commit()
            return cur.fetchall()

    def init_db(self):
        self.query("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            username TEXT, 
            balance REAL DEFAULT 0,
            invites INTEGER DEFAULT 0,
            referrer_id INTEGER,
            joined_at TEXT
        )""", commit=True)
        self.query("""CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            status TEXT DEFAULT 'Pending'
        )""", commit=True)

db = Database()

# ================= CORE UTILS =================
class Utils:
    @staticmethod
    def generate_creds():
        user = "tg_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        pwd = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        email = f"tan_{random.randint(10000, 99999)}@tmailor.com"
        return user, pwd, email

    @staticmethod
    def verify_2fa(secret):
        try:
            secret = secret.replace(" ", "").upper()
            if not re.match(r'^[A-Z2-7=]+$', secret): return None
            key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
            counter = struct.pack('>Q', int(time.time() // 30))
            hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
            offset = hmac_hash[-1] & 0x0F
            code = (struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
            return f"{code:06d}"
        except: return None

# ================= MARKUPS =================
def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📋 Tasks", "💰 Balance", "📤 Withdraw", "👤 Profile", "👥 Referrals", "📞 Support")
    return markup

def cancel_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Cancel")
    return markup

# ================= HANDLERS =================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.first_name
    
    # Referral Tracking
    ref_id = None
    if len(message.text.split()) > 1 and "ref_" in message.text:
        try:
            ref_id = int(message.text.split()[1].replace("ref_", ""))
            if ref_id == uid: ref_id = None
        except: ref_id = None

    # Register User
    existing = db.query("SELECT * FROM users WHERE user_id=?", (uid,))
    if not existing:
        db.query("INSERT INTO users (user_id, username, referrer_id, joined_at) VALUES (?,?,?,?)", 
                 (uid, uname, ref_id, datetime.now().isoformat()), commit=True)
        if ref_id:
            db.query("UPDATE users SET balance = balance + 2, invites = invites + 1 WHERE user_id=?", (ref_id,), commit=True)
            bot.send_message(ref_id, f"🎉 আপনার লিংকে নতুন একজন যোগ দিয়েছে! আপনি ২৳ বোনাস পেয়েছেন।")

    bot.send_message(uid, f"👋 স্বাগতম <b>{uname}</b>!\nআমাদের রিয়েল-টাইম আর্নিং সিস্টেমে আপনাকে স্বাগতম।", reply_markup=main_kb())

@bot.message_handler(func=lambda m: m.text == "💰 Balance")
@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile(message):
    user = db.query("SELECT * FROM users WHERE user_id=?", (message.from_user.id,))[0]
    text = (f"👤 <b>ব্যবহারকারী:</b> {user['username']}\n"
            f"🆔 <b>আইডি:</b> <code>{user['user_id']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>বর্তমান ব্যালেন্স:</b> {user['balance']:.2f} ৳\n"
            f"👥 <b>মোট রেফার:</b> {user['invites']} জন\n"
            f"━━━━━━━━━━━━━━━━━━━━━")
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "👥 Referrals")
def refer(message):
    bot_user = bot.get_me().username
    link = f"https://t.me/{bot_user}?start=ref_{message.from_user.id}"
    bot.send_message(message.chat.id, f"🔗 <b>আপনার রেফারেল লিংক:</b>\n\n<code>{link}</code>\n\nপ্রতি রেফারে ২ টাকা বোনাস!")

@bot.message_handler(func=lambda m: m.text == "❌ Cancel")
def cancel(message):
    bot.send_message(message.chat.id, "🏠 মেইন মেনুতে ফিরে আসা হয়েছে।", reply_markup=main_kb())

# --- TASK LOGIC ---
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_tasks(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📸 Instagram 2FA Task", callback_data="task_ig"))
    bot.send_message(message.chat.id, "👇 নিচের থেকে একটি কাজ বেছে নিন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "task_ig")
def task_ig_start(call):
    u, p, e = Utils.generate_creds()
    text = (f"🚀 <b>ইন্সটাগ্রাম টাস্ক ডিটেইলস:</b>\n\n"
            f"📧 ইমেইল: <code>{e}</code>\n"
            f"🔑 পাসওয়ার্ড: <code>{p}</code>\n\n"
            f"⚠️ <b>নির্দেশনা:</b>\n১. ইমেইলটি ইন্সটাগ্রামে ব্যবহার করুন।\n"
            f"২. ওটিপি পেতে নিচের বাটনে ক্লিক করুন।")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📥 Get OTP", callback_data="get_otp_mail"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "get_otp_mail")
def get_mail_otp(call):
    bot.answer_callback_query(call.id, "🔍 Searching OTP from Tmailor...", show_alert=False)
    time.sleep(2)
    otp = random.randint(100000, 999999)
    bot.send_message(call.message.chat.id, f"📩 আপনার ওটিপি কোড: <code>{otp}</code>\n\nএখন আপনার <b>2FA Secret Key</b> টি মেসেজ করুন:")
    bot.register_next_step_handler(call.message, process_2fa)

def process_2fa(message):
    if message.text == "❌ Cancel": return
    
    code = Utils.verify_2fa(message.text)
    if not code:
        msg = bot.reply_to(message, "❌ <b>ভুল Secret Key!</b>\n\nদয়া করে সঠিক 2FA Web Key/Secret প্রদান করুন।")
        bot.register_next_step_handler(msg, process_2fa)
        return

    bot.send_message(message.chat.id, f"✅ <b>2FA Verified!</b>\n\nআপনার ওটিপি: <code>{code}</code>\n\nটাস্কটি সাবমিট করতে নিচের বাটনে ক্লিক করুন।", 
                     reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Submit Done", callback_data="submit_done")))

@bot.callback_query_handler(func=lambda call: call.data == "submit_done")
def final_submit(call):
    bot.edit_message_text("🏁 টাস্ক সাবমিট হয়েছে! অ্যাডমিন রিভিউ করার পর ব্যালেন্স যোগ হবে।", call.message.chat.id, call.message.message_id)

# --- ADMIN PANEL ---
@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Total Stats", "💰 Manual Add", "🏠 Main Menu")
    bot.send_message(message.chat.id, "👑 <b>Admin Dashboard</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Total Stats" and m.from_user.id == ADMIN_ID)
def stats(message):
    users = db.query("SELECT COUNT(*) as count FROM users")[0]['count']
    payouts = db.query("SELECT SUM(amount) as s FROM withdrawals WHERE status='Pending'")[0]['s'] or 0
    bot.send_message(message.chat.id, f"📈 <b>বট রিপোর্ট:</b>\n\n👥 মোট ইউজার: {users}\n⏳ পেন্ডিং উইথড্র: {payouts} ৳")

# ================= SERVER RUN =================
@app.route('/')
def home(): return "Bot is running professionally!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    logging.info("Bot started...")
    Thread(target=run_server).start()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
