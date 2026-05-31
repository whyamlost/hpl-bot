import requests
import re
import asyncio
import aiofiles
import json
import time
import random
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# Bot Token - UPDATED
BOT_TOKEN = "8682300502:AAEipH6-0YvPgdUHZEiwa2sGjgYtrhlUUP4"

USER_DATA_FILE = "user_data.json"

# Kolkata/India Timezone
KOLKATA_TZ = pytz.timezone('Asia/Kolkata')

# Game Settings
BALLS_TO_PLAY = 20
GAME_INTERVAL = 950  # 15 minutes 50 seconds
COUNTDOWN_REFRESH = 5  # Update every 5 seconds
BALL_DELAY = 5  # 5 seconds between balls

# Real browser headers
REAL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; RMX3581 Build/RP1A.201005.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.137 Mobile Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'sec-ch-ua': '"Android WebView";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive',
}

# Different device fingerprints
DEVICE_FINGERPRINTS = [
    {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36',
        'sec-ch-ua': '"Android WebView";v="120", "Not.A/Brand";v="8", "Chromium";v="120"',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36',
        'sec-ch-ua': '"Android WebView";v="119", "Not.A/Brand";v="8", "Chromium";v="119"',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11; RMX3581) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.80 Mobile Safari/537.36',
        'sec-ch-ua': '"Android WebView";v="118", "Not.A/Brand";v="8", "Chromium";v="118"',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.164 Mobile Safari/537.36',
        'sec-ch-ua': '"Android WebView";v="121", "Not.A/Brand";v="8", "Chromium";v="121"',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Redmi Note 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Mobile Safari/537.36',
        'sec-ch-ua': '"Android WebView";v="117", "Not.A/Brand";v="8", "Chromium";v="117"',
    },
]

PROXY_LIST = []

class HerculesGameBot:
    def __init__(self):
        self.user_sessions = {}
        self.user_proxies = {}
        self.user_devices = {}
        self.user_tasks = {}
        self.user_countdown_msgs = {}
        self.user_retry_counts = {}
        self.real_headers = REAL_HEADERS

    def get_kolkata_time(self):
        """Get current time in Kolkata/India timezone"""
        return datetime.now(KOLKATA_TZ)

    def format_time(self, dt):
        """Format datetime to HH:MM:SS AM/PM"""
        return dt.strftime("%I:%M:%S %p")

    async def load_user_data(self):
        try:
            async with aiofiles.open(USER_DATA_FILE, 'r') as f:
                data = await f.read()
                if data:
                    loaded_data = json.loads(data)
                    for uid, info in loaded_data.items():
                        if uid not in self.user_sessions:
                            self.user_sessions[uid] = {}
                        self.user_sessions[uid]['mobile'] = info.get('mobile')
                        self.user_sessions[uid]['user_id'] = info.get('user_id')
                        self.user_sessions[uid]['device_headers'] = info.get('device_headers')
        except FileNotFoundError:
            pass

    async def save_user_data(self):
        save_data = {}
        for uid, info in self.user_sessions.items():
            save_data[uid] = {
                'mobile': info.get('mobile'),
                'user_id': info.get('user_id'),
                'device_headers': info.get('device_headers')
            }
        async with aiofiles.open(USER_DATA_FILE, 'w') as f:
            await f.write(json.dumps(save_data, indent=2))

    def get_random_device_headers(self, telegram_user_id):
        if telegram_user_id not in self.user_devices:
            device = random.choice(DEVICE_FINGERPRINTS)
            self.user_devices[telegram_user_id] = device
        return self.user_devices[telegram_user_id]

    def get_proxy_for_user(self, telegram_user_id):
        if PROXY_LIST and telegram_user_id not in self.user_proxies:
            proxy = random.choice(PROXY_LIST)
            self.user_proxies[telegram_user_id] = proxy
            return {'http': proxy, 'https': proxy}
        return None

    async def send_otp(self, mobile: str, telegram_user_id: int) -> tuple:
        try:
            session = requests.Session()
            device_headers = self.get_random_device_headers(telegram_user_id)
            headers = self.real_headers.copy()
            headers['User-Agent'] = device_headers['User-Agent']
            headers['sec-ch-ua'] = device_headers['sec-ch-ua']
            
            proxy = self.get_proxy_for_user(telegram_user_id)
            if proxy:
                session.proxies.update(proxy)
            
            if telegram_user_id not in self.user_sessions:
                self.user_sessions[telegram_user_id] = {}
            self.user_sessions[telegram_user_id]['session'] = session
            self.user_sessions[telegram_user_id]['device_headers'] = device_headers
            
            login_url = "https://www.herculespremierleague.com/home/login"
            response = session.get(login_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            token = soup.find('input', {'name': 'token'}).get('value')
            
            data = {'mobile': mobile, 'token': token}
            response = session.post(login_url, data=data, headers=headers, allow_redirects=False)
            
            if response.status_code == 303:
                self.user_sessions[telegram_user_id]['mobile'] = mobile
                await self.save_user_data()
                return True, "OTP sent successfully!"
            return False, "Failed to send OTP!"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def verify_otp(self, mobile: str, otp: str, telegram_user_id: int) -> tuple:
        try:
            user_data = self.user_sessions.get(telegram_user_id)
            if not user_data or not user_data.get('session'):
                return False, "Session expired! Use /login again"
            
            session = user_data['session']
            device_headers = user_data.get('device_headers', self.get_random_device_headers(telegram_user_id))
            headers = self.real_headers.copy()
            headers['User-Agent'] = device_headers['User-Agent']
            headers['sec-ch-ua'] = device_headers['sec-ch-ua']
            
            verify_url = "https://www.herculespremierleague.com/home/verify"
            response = session.get(verify_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            token = soup.find('input', {'name': 'token'}).get('value')
            
            data = {
                'mobile': mobile,
                'token': token,
                'otp1': otp[0], 'otp2': otp[1], 'otp3': otp[2], 'otp4': otp[3]
            }
            response = session.post(verify_url, data=data, headers=headers, allow_redirects=True)
            
            if 'dashboard' in response.url:
                await self.save_user_data()
                return True, "Login successful!"
            return False, "Wrong OTP!"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def get_user_id(self, telegram_user_id: int) -> tuple:
        try:
            user_data = self.user_sessions.get(telegram_user_id)
            if not user_data or not user_data.get('session'):
                return False, "Session expired!"
            
            session = user_data['session']
            device_headers = user_data.get('device_headers', self.get_random_device_headers(telegram_user_id))
            headers = self.real_headers.copy()
            headers['User-Agent'] = device_headers['User-Agent']
            headers['sec-ch-ua'] = device_headers['sec-ch-ua']
            
            game_url = "https://www.herculespremierleague.com/home/game"
            response = session.get(game_url, headers=headers, allow_redirects=False)
            
            if response.status_code in [301, 302, 303, 307]:
                location = response.headers.get('location', '')
                match = re.search(r'userid=(\d+)', location)
                if match:
                    user_id = match.group(1)
                    user_data['user_id'] = user_id
                    await self.save_user_data()
                    return True, user_id
            
            return False, "User ID not found"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def start_game(self, user_id: str, telegram_user_id: int) -> tuple:
        try:
            user_data = self.user_sessions.get(telegram_user_id)
            if not user_data or not user_data.get('session'):
                return False, "Session expired!"
            
            session = user_data['session']
            device_headers = user_data.get('device_headers', self.get_random_device_headers(telegram_user_id))
            headers = self.real_headers.copy()
            headers['User-Agent'] = device_headers['User-Agent']
            headers['sec-ch-ua'] = device_headers['sec-ch-ua']
            headers['Origin'] = 'https://www.herculespremierleague.com'
            headers['Referer'] = f'https://www.herculespremierleague.com/game/index.html?userid={user_id}'
            
            game_url = "https://www.herculespremierleague.com/api/gameballs"
            data = {'userid': user_id}
            response = session.post(game_url, data=data, headers=headers)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except:
                    import gzip
                    import io
                    if response.headers.get('Content-Encoding') == 'gzip':
                        buf = io.BytesIO(response.content)
                        f = gzip.GzipFile(fileobj=buf)
                        decoded = f.read().decode('utf-8')
                        result = json.loads(decoded)
                    else:
                        result = response.json()
                
                if result.get('isGameAllowed') == 1:
                    return True, {
                        'loggedSession': result.get('loggedSession'),
                        'total_cashback': int(result.get('totalCashback', 0)),
                        'current_ball_number': result.get('ballnumber', 1)
                    }
                return False, result.get('message', 'Game not allowed')
            return False, f"Failed! Status: {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def play_ball(self, user_id: str, ball_number: int, logged_session: str, telegram_user_id: int) -> tuple:
        try:
            user_data = self.user_sessions.get(telegram_user_id)
            if not user_data or not user_data.get('session'):
                return False, "Session expired!"
            
            session = user_data['session']
            device_headers = user_data.get('device_headers', self.get_random_device_headers(telegram_user_id))
            headers = self.real_headers.copy()
            headers['User-Agent'] = device_headers['User-Agent']
            headers['sec-ch-ua'] = device_headers['sec-ch-ua']
            headers['Origin'] = 'https://www.herculespremierleague.com'
            headers['Referer'] = f'https://www.herculespremierleague.com/game/index.html?userid={user_id}'
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            
            post_url = "https://www.herculespremierleague.com/api/postscore"
            data = f'userid={user_id}&ballnumber={ball_number}&score=6&loggedSession={logged_session}'
            response = session.post(post_url, data=data, headers=headers)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except:
                    import gzip
                    import io
                    if 'gzip' in response.headers.get('Content-Encoding', ''):
                        buf = io.BytesIO(response.content)
                        f = gzip.GzipFile(fileobj=buf)
                        decoded = f.read().decode('utf-8')
                        result = json.loads(decoded)
                    else:
                        result = response.json()
                
                if result.get('isGameAllowed') == 1:
                    return True, {
                        'loggedSession': result.get('loggedSession'),
                        'total_cashback': int(result.get('totalCashback', 0)),
                        'last_ball_cashback': result.get('lastballcashback', '0'),
                        'current_ball_number': result.get('ballnumber', ball_number + 1)
                    }
                return False, result.get('message', 'Game over')
            return False, f"Failed! Status: {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def play_full_game_with_retry(self, user_id: str, telegram_user_id: int, context, chat_id: int, is_first_game=False, retry_count=0):
        """Play exactly 20 balls with auto-retry on failure"""
        
        MAX_RETRIES = 999999  # Infinite retries
        
        if retry_count > 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔄 **Retry #{retry_count}** - Attempting to play again...\n⏳ Please wait 10 seconds...",
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(10)
        
        try:
            # Start game
            success, game_data = await self.start_game(user_id, telegram_user_id)
            
            if not success:
                # Retry on failure
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Game start failed: {game_data}\n🔄 Will retry in 30 seconds...",
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(30)
                return await self.play_full_game_with_retry(user_id, telegram_user_id, context, chat_id, is_first_game, retry_count + 1)

            logged_session = game_data['loggedSession']
            total_cashback = game_data['total_cashback']
            current_ball = game_data['current_ball_number']
            
            balls_played = 0
            runs_scored = 0
            ball_details = []
            
            # Send initial message
            current_time = self.get_kolkata_time()
            time_str = self.format_time(current_time)
            
            msg = f"🎮 **🏏 HPL AUTO RUN 🏏** 🎮\n\n"
            msg += f"⚡ **Playing {BALLS_TO_PLAY} balls | 6 runs each**\n"
            msg += f"⏰ Started: `{time_str}`\n\n"
            msg += f"🔄 Playing...\n"
            
            progress_msg = await context.bot.send_message(
                chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN
            )
            
            # Play each ball with retry on individual ball failure
            for ball_num in range(1, BALLS_TO_PLAY + 1):
                ball_success = False
                ball_retry = 0
                ball_result = None
                
                while not ball_success and ball_retry < 10:  # Max 10 retries per ball
                    success, result = await self.play_ball(user_id, current_ball, logged_session, telegram_user_id)
                    
                    if success:
                        ball_success = True
                        ball_result = result
                        break
                    else:
                        ball_retry += 1
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Ball {ball_num} failed: {result}\n🔄 Retry #{ball_retry} in 10 seconds...",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await asyncio.sleep(10)
                
                if not ball_success:
                    # If ball fails after retries, restart entire game
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Ball {ball_num} failed after 10 retries!\n🔄 Restarting entire game...",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return await self.play_full_game_with_retry(user_id, telegram_user_id, context, chat_id, is_first_game, retry_count + 1)
                
                logged_session = ball_result['loggedSession']
                total_cashback = ball_result['total_cashback']
                last_cashback = ball_result['last_ball_cashback']
                current_ball = ball_result['current_ball_number']
                
                balls_played = ball_num
                runs_scored += 6
                ball_details.append(f"🏏 Ball {ball_num}: 6 runs | +{last_cashback}💰")
                
                # Update message LIVE after each ball
                current_time = self.get_kolkata_time()
                time_str = self.format_time(current_time)
                
                msg = f"🎮 **🏏 HPL AUTO RUN 🏏** 🎮\n\n"
                msg += f"⚡ **Progress:** {balls_played}/{BALLS_TO_PLAY} balls\n"
                msg += f"⭐ **Total Runs:** {runs_scored}\n"
                msg += f"💰 **Cashback:** {total_cashback}\n"
                msg += f"⏰ `{time_str}`\n\n"
                
                if ball_details:
                    msg += f"📊 **Last balls:**\n"
                    for detail in ball_details[-3:]:
                        msg += f"{detail}\n"
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=progress_msg.message_id,
                        text=msg, parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    print(f"Edit error: {e}")
                
                # Ball delay
                if ball_num < BALLS_TO_PLAY:
                    await asyncio.sleep(BALL_DELAY)
            
            # Game completed successfully
            minutes_interval = GAME_INTERVAL // 60
            seconds_interval = GAME_INTERVAL % 60
            
            final_msg = f"✅ **🏆 GAME COMPLETED! 🏆** ✅\n\n"
            final_msg += f"🏏 **Balls Played:** {balls_played}/{BALLS_TO_PLAY}\n"
            final_msg += f"⭐ **Total Runs:** {runs_scored}\n"
            final_msg += f"💰 **Total Cashback:** {total_cashback}\n\n"
            
            if not is_first_game:
                final_msg += f"⏰ **Next auto-play in {minutes_interval} min {seconds_interval} sec**\n"
                final_msg += f"🔄 Auto-play active!\n\n"
            
            final_msg += f"🔗 `https://www.herculespremierleague.com/home/dashboard`"
            
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=progress_msg.message_id,
                text=final_msg, parse_mode=ParseMode.MARKDOWN
            )
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"Game error: {error_msg}")
            
            # Retry on any exception
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Error occurred: {error_msg[:100]}\n🔄 Retrying entire game in 30 seconds... (Attempt #{retry_count + 1})",
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(30)
            return await self.play_full_game_with_retry(user_id, telegram_user_id, context, chat_id, is_first_game, retry_count + 1)

    async def countdown_and_play(self, context, chat_id, user_id):
        """Countdown for GAME_INTERVAL seconds then play again - updates every COUNTDOWN_REFRESH seconds"""
        
        # Delete old countdown message if exists
        if user_id in self.user_countdown_msgs:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=self.user_countdown_msgs[user_id])
            except:
                pass
        
        countdown_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ **Starting countdown...**",
            parse_mode=ParseMode.MARKDOWN
        )
        self.user_countdown_msgs[user_id] = countdown_msg.message_id
        
        remaining = GAME_INTERVAL
        minutes_interval = GAME_INTERVAL // 60
        seconds_interval = GAME_INTERVAL % 60
        
        while remaining > 0 and user_id in self.user_tasks and self.user_tasks[user_id].get('active', False):
            minutes = remaining // 60
            seconds = remaining % 60
            countdown_text = f"⏰ **Next auto-play in:**\n`{minutes:02d}:{seconds:02d}`\n\n"
            countdown_text += f"⚙️ **Settings:**\n"
            countdown_text += f"• Interval: {minutes_interval} min {seconds_interval} sec\n"
            countdown_text += f"• Refresh: Every {COUNTDOWN_REFRESH} sec\n"
            countdown_text += f"• Balls: {BALLS_TO_PLAY} (6 runs each)\n\n"
            countdown_text += f"🔄 Game will start automatically!"
            
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=countdown_msg.message_id,
                    text=countdown_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            await asyncio.sleep(COUNTDOWN_REFRESH)
            remaining -= COUNTDOWN_REFRESH
        
        if user_id in self.user_tasks and self.user_tasks[user_id].get('active', False):
            # Delete countdown message
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=countdown_msg.message_id)
                if user_id in self.user_countdown_msgs:
                    del self.user_countdown_msgs[user_id]
            except:
                pass
            
            # Play next game
            await self.play_game_and_schedule(context, chat_id, user_id, is_first_game=False)

    async def play_game_and_schedule(self, context, chat_id, user_id, is_first_game=False):
        """Play game and schedule next game after GAME_INTERVAL seconds"""
        user_data = self.user_sessions.get(user_id)
        if not user_data or not user_data.get('user_id'):
            await context.bot.send_message(chat_id=chat_id, text="❌ Session expired! Use /login again")
            if user_id in self.user_tasks:
                del self.user_tasks[user_id]
            return
        
        # Play the game with auto-retry
        success = await self.play_full_game_with_retry(user_data['user_id'], user_id, context, chat_id, is_first_game)
        
        # Schedule next game only if not the first game
        if not is_first_game and success and user_id in self.user_tasks and self.user_tasks[user_id].get('active', False):
            asyncio.create_task(self.countdown_and_play(context, chat_id, user_id))

    async def start_auto_play(self, context, chat_id, user_id):
        """Start the auto-play cycle - plays FIRST game instantly, then countdown"""
        if user_id in self.user_tasks:
            self.user_tasks[user_id]['active'] = False
        
        self.user_tasks[user_id] = {
            'active': True,
            'chat_id': chat_id
        }
        
        # Play FIRST game immediately
        user_data = self.user_sessions.get(user_id)
        if user_data and user_data.get('user_id'):
            # Play first game
            await self.play_full_game_with_retry(user_data['user_id'], user_id, context, chat_id, is_first_game=True)
            
            # After first game, start countdown for next game
            if user_id in self.user_tasks and self.user_tasks[user_id].get('active', False):
                asyncio.create_task(self.countdown_and_play(context, chat_id, user_id))

    async def stop_auto_play(self, user_id):
        """Stop auto-play for user"""
        if user_id in self.user_tasks:
            self.user_tasks[user_id]['active'] = False
            del self.user_tasks[user_id]
            return True
        return False


game_bot = HerculesGameBot()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    minutes_interval = GAME_INTERVAL // 60
    seconds_interval = GAME_INTERVAL % 60
    
    await update.message.reply_text(
        "🏏 **🏆 HPL AUTO RUN BOT 🏆** 🏏\n\n"
        "🤖 **Features:**\n"
        f"• ⚡ 6 runs per ball (MAX SCORE)\n"
        f"• 🎯 Exactly {BALLS_TO_PLAY} balls per game\n"
        f"• ⏱️ {BALL_DELAY} second gap between balls (FIXED)\n"
        f"• 🔄 AUTO-PLAY every {minutes_interval} min {seconds_interval} sec\n"
        f"• ⏰ Countdown updates every {COUNTDOWN_REFRESH} seconds (SMOOTH)\n"
        f"• 🕐 Kolkata/India timezone\n"
        f"• 💰 Real-time cashback tracking\n"
        f"• 🔁 Auto-retry on any error (infinite attempts)\n\n"
        "📌 **Commands:**\n"
        "• `/login` - Login to HPL account\n"
        "• `/stop` - Stop auto-play\n"
        "• `/status` - Check auto-play status\n\n"
        "⚡ Use /login to start!",
        parse_mode=ParseMode.MARKDOWN
    )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in game_bot.user_tasks and game_bot.user_tasks[user_id].get('active'):
        await update.message.reply_text("⚠️ Auto-play already running! Use /stop first to login again.")
        return
    
    await update.message.reply_text(
        "📱 **Enter your mobile number:**\n\nExample: `9876543210`",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = 'waiting_mobile'


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stopped = await game_bot.stop_auto_play(user_id)
    
    if stopped:
        await update.message.reply_text(
            "⏹️ **Auto-play stopped!**\n\nUse /login to start again.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("❌ No active auto-play session found.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    minutes_interval = GAME_INTERVAL // 60
    seconds_interval = GAME_INTERVAL % 60
    
    if user_id in game_bot.user_tasks and game_bot.user_tasks[user_id].get('active'):
        user_data = game_bot.user_sessions.get(user_id, {})
        current_time = game_bot.get_kolkata_time()
        await update.message.reply_text(
            "✅ **Auto-play is ACTIVE**\n\n"
            f"📱 Mobile: `{user_data.get('mobile', 'Unknown')}`\n"
            f"🆔 User ID: `{user_data.get('user_id', 'Unknown')}`\n"
            f"🕐 Server Time: `{game_bot.format_time(current_time)}`\n"
            f"🔄 Status: Running\n"
            f"⏰ Interval: {minutes_interval} min {seconds_interval} sec\n"
            f"⚡ Countdown Refresh: Every {COUNTDOWN_REFRESH} sec\n"
            f"🏏 Balls per game: {BALLS_TO_PLAY}\n"
            f"🔁 Auto-retry: Enabled (infinite)\n\n"
            f"Use `/stop` to stop auto-play",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ **Auto-play is NOT active**\n\nUse `/login` to start auto-play!",
            parse_mode=ParseMode.MARKDOWN
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_user_id = update.effective_user.id
    message_text = update.message.text.strip()
    state = context.user_data.get('state')
    
    if state == 'waiting_mobile':
        mobile = re.sub(r'\D', '', message_text)
        if len(mobile) < 10 or len(mobile) > 15:
            await update.message.reply_text("❌ Invalid number! Send 10-digit number")
            return
        
        context.user_data['mobile'] = mobile
        
        await update.message.reply_text("📤 Sending OTP...")
        
        success, msg = await game_bot.send_otp(mobile, telegram_user_id)
        
        if success:
            await update.message.reply_text("✅ OTP sent! Enter 4-digit code:")
            context.user_data['state'] = 'waiting_otp'
        else:
            await update.message.reply_text(f"❌ {msg}\nUse /login to try again")
            context.user_data['state'] = None
    
    elif state == 'waiting_otp':
        otp = message_text.strip()
        if not otp.isdigit() or len(otp) != 4:
            await update.message.reply_text("❌ Enter valid 4-digit OTP!")
            return
        
        mobile = context.user_data.get('mobile')
        
        await update.message.reply_text("🔐 Verifying OTP...")
        
        success, msg = await game_bot.verify_otp(mobile, otp, telegram_user_id)
        
        if success:
            await update.message.reply_text("✅ Login successful! Fetching user data...")
            
            success, user_id_val = await game_bot.get_user_id(telegram_user_id)
            
            if success and user_id_val:
                minutes_interval = GAME_INTERVAL // 60
                seconds_interval = GAME_INTERVAL % 60
                
                await update.message.reply_text(
                    f"✅ **Logged in!**\n🆔 User ID: `{user_id_val}`\n\n"
                    f"🔄 **Starting auto-play mode!**\n"
                    f"⚡ **FIRST GAME STARTS NOW!**\n"
                    f"⏰ Will play {BALLS_TO_PLAY} balls every {minutes_interval} min {seconds_interval} sec\n"
                    f"📊 Countdown updates every {COUNTDOWN_REFRESH} seconds\n"
                    f"⏱️ {BALL_DELAY} second gap between each ball\n"
                    f"🔁 Auto-retry on any error (infinite attempts)\n\n"
                    f"❌ Use `/stop` to stop auto-play",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                await game_bot.start_auto_play(context, update.effective_chat.id, telegram_user_id)
                context.user_data['state'] = None
            else:
                await update.message.reply_text(f"❌ Failed to get user ID!\n\n{user_id_val}")
                context.user_data['state'] = None
        else:
            await update.message.reply_text(f"❌ {msg}\nUse /login to try again")
            context.user_data['state'] = None


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred! The bot will auto-retry.\nUse /status to check."
            )
    except:
        pass


async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    await game_bot.load_user_data()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    minutes_interval = GAME_INTERVAL // 60
    seconds_interval = GAME_INTERVAL % 60
    
    print("="*50)
    print("🏏 HPL AUTO RUN BOT - 20 BALLS 🏏")
    print("="*50)
    print("✅ Bot running with:")
    print(f"⚡ 6 runs per ball")
    print(f"🎯 {BALLS_TO_PLAY} balls per game")
    print(f"⏱️ {BALL_DELAY} sec FIXED delay between balls")
    print(f"🔄 AUTO-PLAY every {minutes_interval} min {seconds_interval} sec")
    print(f"⏰ Countdown updates every {COUNTDOWN_REFRESH} sec (SMOOTH)")
    print(f"🕐 Kolkata/India timezone")
    print(f"🔁 AUTO-RETRY on any error (infinite)")
    print(f"💾 Session saved automatically")
    print("="*50)
    print("📌 Commands:")
    print("   /login  - Login once (plays FIRST game instantly)")
    print("   /stop   - Stop auto-play")
    print("   /status - Check status")
    print("="*50)
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())