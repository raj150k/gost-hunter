import os
import json
import asyncio
import logging
from datetime import datetime, timedelta

# Telegram Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Telethon
from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import SessionPasswordNeededError

# ======================== 🔥 তোমার ইনফো এখানে বসাও ========================
BOT_TOKEN = "8749787354:AAEdEIfgcex72ZWZEnMKRaGxPjjYitbZ-ps"  # ← BotFather থেকে টোকেন বসাও
ADMIN_ID = 8636937438                                # ← তোমার Telegram ID বসাও
# ========================================================================

ACCOUNTS_FILE = "accounts.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ======================== ডিফল্ট রিপ্লাই মেসেজ ========================

DEFAULT_REPLY_TEMPLATE = """
Hey {name} 🌸
👤 Username : @{username}

Welcome to {boss_name}'s Personal Assistant 🤖

📩 Your message has been received successfully.

Boss is currently offline or busy 💤
But don't worry — your message has been forwarded successfully ✅

💬 As soon as Boss comes online, you'll get a reply.

⏳ Please wait patiently...

😎 My Boss : {boss_name} 🤘
👑 Owner : @{boss_username}
⚡ Assistant : Ghost Hunter

✨ Thank you for messaging ✨
"""

# ======================== ডাটা ম্যানেজমেন্ট ========================

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=4, default=str)

# ======================== অ্যাকাউন্ট ম্যানেজার ========================

class AccountManager:
    def __init__(self):
        self.accounts = load_accounts()
        self.clients = {}
    
    def add_account(self, name, api_id, api_hash, phone):
        if name in self.accounts:
            return f"❌ Account '{name}' already exists!"
        
        self.accounts[name] = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "session_file": f"sessions/{name}",
            "users": {},
            "banned_users": [],
            "reply_message": None,
            "enabled": True,
            "status": "stopped"
        }
        save_accounts(self.accounts)
        return f"✅ Account '{name}' added! Now:\n/startaccount {name}\n/verify {name} <otp>"
    
    def remove_account(self, name):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        if name in self.clients:
            loop = asyncio.get_event_loop()
            loop.create_task(self.disconnect_account(name))
        del self.accounts[name]
        save_accounts(self.accounts)
        return f"✅ Account '{name}' removed!"
    
    async def disconnect_account(self, name):
        try:
            client = self.clients.pop(name, None)
            if client:
                await client.disconnect()
        except:
            pass
    
    def add_ban(self, name, user_id):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        banned = set(self.accounts[name].get("banned_users", []))
        banned.add(user_id)
        self.accounts[name]["banned_users"] = list(banned)
        save_accounts(self.accounts)
        return f"✅ User `{user_id}` banned from '{name}'!"
    
    def remove_ban(self, name, user_id):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        banned = set(self.accounts[name].get("banned_users", []))
        banned.discard(user_id)
        self.accounts[name]["banned_users"] = list(banned)
        save_accounts(self.accounts)
        return f"✅ User `{user_id}` unbanned from '{name}'!"
    
    def set_custom_reply(self, name, reply_text):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        self.accounts[name]["reply_message"] = reply_text
        save_accounts(self.accounts)
        return f"✅ Custom reply set for '{name}'!\n\nUse /showreply {name} to see it."
    
    def reset_custom_reply(self, name):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        self.accounts[name]["reply_message"] = None
        save_accounts(self.accounts)
        return f"✅ Reply reset to default for '{name}'!"
    
    def show_reply(self, name):
        if name not in self.accounts:
            return f"❌ Account '{name}' not found!"
        reply = self.accounts[name].get("reply_message")
        if reply:
            return f"📝 **Current Custom Reply:**\n\n```\n{reply}\n```"
        else:
            return f"📝 **Default Reply:**\n\n```\n{DEFAULT_REPLY_TEMPLATE.strip()}\n```"
    
    def get_accounts_list(self):
        if not self.accounts:
            return "❌ No accounts configured!"
        text = "📋 **Account List:**\n\n"
        for name, config in self.accounts.items():
            status_emoji = {"running": "🟢", "stopped": "🔴", "error": "🟡"}.get(config.get("status"), "⚪")
            text += f"{status_emoji} **{name}**\n"
            text += f"   ├ 👤 Users: {len(config.get('users', {}))}\n"
            text += f"   ├ 🚫 Banned: {len(config.get('banned_users', []))}\n"
            text += f"   └ 📱 {config.get('phone', 'N/A')}\n\n"
        return text

manager = AccountManager()

# ======================== ইউজারবোট ইভেন্ট হ্যান্ডলার ========================

def create_userbot_handlers(client, account_name):
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_reply(event):
        
        if not event.is_private:
            return
        
        config = manager.accounts.get(account_name)
        if not config or not config.get("enabled", True):
            return
        
        me = await client.get_me()
        full = await client(GetFullUserRequest(me.id))
        
        status_str = str(full.users[0].status).lower()
        if "offline" not in status_str and "empty" not in status_str:
            return
        
        sender = await event.get_sender()
        user_id = sender.id
        user_name = sender.first_name or "Unknown"
        username = sender.username or "No Username"
        
        if user_id in config.get("banned_users", []):
            return
        
        now = datetime.now()
        users_data = config.get("users", {})
        
        user_key = str(user_id)
        if user_key not in users_data:
            users_data[user_key] = {"count": 0, "time": now.isoformat()}
        
        data = users_data[user_key]
        last_time = datetime.fromisoformat(data["time"])
        
        if now - last_time > timedelta(minutes=30):
            data["count"] = 0
        
        if data["count"] >= 2:
            return
        
        custom_reply_msg = config.get("reply_message")
        if custom_reply_msg:
            msg = custom_reply_msg.format(
                name=user_name,
                username=f"@{username}" if username != "No Username" else "No Username",
                boss_name=me.first_name or "Boss",
                boss_username=me.username or "boss"
            )
        else:
            msg = DEFAULT_REPLY_TEMPLATE.format(
                name=user_name,
                username=f"@{username}" if username != "No Username" else "No Username",
                boss_name=me.first_name or "Boss",
                boss_username=me.username or "boss"
            )
        
        reply = await event.reply(msg)
        data["count"] += 1
        data["time"] = now.isoformat()
        config["users"] = users_data
        save_accounts(manager.accounts)
        
        async def delete_later():
            await asyncio.sleep(300)
            try:
                await reply.delete()
            except:
                pass
        
        asyncio.create_task(delete_later())

# ======================== অ্যাকাউন্ট স্টার্ট ========================

async def start_account(account_name):
    config = manager.accounts.get(account_name)
    if not config:
        return f"❌ Account '{account_name}' not found!"
    if account_name in manager.clients:
        return f"ℹ️ '{account_name}' is already running!"
    
    try:
        api_id = config["api_id"]
        api_hash = config["api_hash"]
        phone = config["phone"]
        session_file = config["session_file"]
        
        os.makedirs("sessions", exist_ok=True)
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            return f"📱 OTP sent to {phone}. Use /verify {account_name} <code>"
        
        await client.start(phone=phone)
        create_userbot_handlers(client, account_name)
        manager.clients[account_name] = client
        config["status"] = "running"
        save_accounts(manager.accounts)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{account_name}' is now running!"
    
    except SessionPasswordNeededError:
        return f"🔑 2FA required! Use /verify2fa {account_name} <password>"
    except Exception as e:
        config["status"] = "error"
        save_accounts(manager.accounts)
        return f"❌ Error: {str(e)}"


async def verify_account(account_name, code):
    config = manager.accounts.get(account_name)
    if not config:
        return f"❌ Account '{account_name}' not found!"
    try:
        phone = config["phone"]
        api_id = config["api_id"]
        api_hash = config["api_hash"]
        session_file = config["session_file"]
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        await client.sign_in(phone=phone, code=code)
        
        create_userbot_handlers(client, account_name)
        manager.clients[account_name] = client
        config["status"] = "running"
        save_accounts(manager.accounts)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{account_name}' verified & running!"
    
    except SessionPasswordNeededError:
        return f"🔑 2FA required! Use /verify2fa {account_name} <password>"
    except Exception as e:
        return f"❌ Error: {str(e)}"


async def verify_2fa(account_name, password):
    config = manager.accounts.get(account_name)
    if not config:
        return f"❌ Account '{account_name}' not found!"
    try:
        api_id = config["api_id"]
        api_hash = config["api_hash"]
        session_file = config["session_file"]
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        await client.sign_in(password=password)
        
        create_userbot_handlers(client, account_name)
        manager.clients[account_name] = client
        config["status"] = "running"
        save_accounts(manager.accounts)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{account_name}' logged in with 2FA!"
    except Exception as e:
        return f"❌ 2FA error: {str(e)}"


async def stop_account(account_name):
    if account_name not in manager.accounts:
        return f"❌ Account '{account_name}' not found!"
    if account_name in manager.clients:
        try:
            client = manager.clients.pop(account_name)
            await client.disconnect()
        except:
            pass
    manager.accounts[account_name]["status"] = "stopped"
    save_accounts(manager.accounts)
    return f"✅ Account '{account_name}' stopped!"

# ======================== বট কমান্ড ========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    help_text = """
🤖 **Ghost Admin Bot**

📌 **Account Commands:**
/addaccount <name> <api_id> <api_hash> <phone>
/removeaccount <name>
/startaccount <name>
/stopaccount <name>
/verify <name> <otp>
/verify2fa <name> <password>

📌 **User Control:**
/ban <name> <user_id>
/unban <name> <user_id>

📌 **Reply Customization:**
/setreply <name> <your_message>
/resetreply <name>
/showreply <name>

📌 **Info:**
/accounts
/stats <name>

💡 **setreply-এ ইউজ করো:** {name}, {username}, {boss_name}, {boss_username}
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def add_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 4:
        await update.message.reply_text("❌ /addaccount <name> <api_id> <api_hash> <phone>")
        return
    try:
        api_id = int(context.args[1])
    except:
        await update.message.reply_text("❌ api_id must be number")
        return
    await update.message.reply_text(manager.add_account(context.args[0], api_id, context.args[2], context.args[3]))


async def remove_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /removeaccount <name>")
        return
    await update.message.reply_text(manager.remove_account(context.args[0]))


async def start_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /startaccount <name>")
        return
    await update.message.reply_text(await start_account(context.args[0]))


async def stop_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /stopaccount <name>")
        return
    await update.message.reply_text(await stop_account(context.args[0]))


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /verify <name> <otp>")
        return
    await update.message.reply_text(await verify_account(context.args[0], context.args[1]))


async def verify_2fa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /verify2fa <name> <password>")
        return
    await update.message.reply_text(await verify_2fa(context.args[0], " ".join(context.args[1:])))


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /ban <account> <user_id>")
        return
    try:
        await update.message.reply_text(manager.add_ban(context.args[0], int(context.args[1])))
    except:
        await update.message.reply_text("❌ Invalid user_id")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /unban <account> <user_id>")
        return
    try:
        await update.message.reply_text(manager.remove_ban(context.args[0], int(context.args[1])))
    except:
        await update.message.reply_text("❌ Invalid user_id")


async def setreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /setreply <name> <message>\n\nUse: {name}, {username}, {boss_name}, {boss_username}")
        return
    await update.message.reply_text(manager.set_custom_reply(context.args[0], " ".join(context.args[1:])))


async def resetreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /resetreply <name>")
        return
    await update.message.reply_text(manager.reset_custom_reply(context.args[0]))


async def showreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /showreply <name>")
        return
    await update.message.reply_text(manager.show_reply(context.args[0]), parse_mode="Markdown")


async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(manager.get_accounts_list(), parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ /stats <name>")
        return
    name = context.args[0]
    config = manager.accounts.get(name)
    if not config:
        await update.message.reply_text(f"❌ Account '{name}' not found!")
        return
    await update.message.reply_text(f"""
📊 **{name}**
━━━━━━━━━━━━━
📱 {config.get('phone', 'N/A')}
🔘 {'🟢 Running' if config.get('status')=='running' else '🔴 Stopped'}
👥 Users: {len(config.get('users', {}))}
🚫 Banned: {len(config.get('banned_users', []))}
💬 Reply: {'✅ Custom' if config.get('reply_message') else '❌ Default'}
""", parse_mode="Markdown")


# ======================== মেইন ========================

def main():
    os.makedirs("sessions", exist_ok=True)
    
    if BOT_TOKEN == "7854123690:AAH_your_bot_token_here":
        print("❌ ERROR: তোমার বট টোকেন বসাওনি! admin_bot.py-র উপরে BOT_TOKEN বসাও।")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("addaccount", add_account_command))
    app.add_handler(CommandHandler("removeaccount", remove_account_command))
    app.add_handler(CommandHandler("startaccount", start_account_command))
    app.add_handler(CommandHandler("stopaccount", stop_account_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("verify2fa", verify_2fa_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("setreply", setreply_command))
    app.add_handler(CommandHandler("resetreply", resetreply_command))
    app.add_handler(CommandHandler("showreply", showreply_command))
    app.add_handler(CommandHandler("accounts", accounts_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    print("🤖 Ghost Admin Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
