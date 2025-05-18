from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import Update
from pytgcalls.types.input_stream import InputStream, AudioPiped
from youtubesearchpython import VideosSearch
from yt_dlp import YoutubeDL
from collections import deque
import asyncio, os

api_id = 23446876
api_hash = "0e59ef9f19f0bbf7ea5188ed0169656f"
bot_token = "8057793323:AAGmKtEeJVQP5flTMQFEpVlSoiQs6Zl8C1I"

app = Client("search_voice_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
pytgcalls = PyTgCalls(app)

voice_chats = {}
play_queues = {}
is_playing = {}

def ensure_silence_file():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    silence_path = "downloads/silence.mp3"
    if not os.path.exists(silence_path):
        os.system("ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 1 " + silence_path + " -y")
ensure_silence_file()

def search_youtube(query):
    results = VideosSearch(query, limit=1).result()
    if results['result']:
        return results['result'][0]['link']
    return None

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return f"downloads/{info['title']}.mp3"

def add_to_queue(chat_id: int, file_path: str):
    if chat_id not in play_queues:
        play_queues[chat_id] = deque()
    play_queues[chat_id].append(file_path)

async def check_and_play_next(chat_id: int):
    if is_playing.get(chat_id, False):
        return
    if chat_id in play_queues and play_queues[chat_id]:
        next_track = play_queues[chat_id].popleft()
        is_playing[chat_id] = True
        try:
            await pytgcalls.join_group_call(
                chat_id,
                InputStream(AudioPiped(next_track)),
                stream_type="local",
            )
            voice_chats[chat_id] = next_track
        except Exception as e:
            print(f"خطا در پخش ویس‌کال: {e}")
            is_playing[chat_id] = False
            await check_and_play_next(chat_id)

@pytgcalls.on_stream_end()
async def on_stream_end_handler(_, update: Update):
    chat_id = update.chat_id
    is_playing[chat_id] = False
    await check_and_play_next(chat_id)

@app.on_message(filters.private | filters.group)
async def handle_message(client, message: Message):
    if message.text and message.text.lower().startswith("سیرچ"):
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            return await message.reply("نام آهنگ؟")
        query = parts[1]
        url = search_youtube(query)
        if not url:
            return await message.reply("نتیجه‌ای یافت نشد")
        path = download_audio(url)
        await message.reply_audio(path)
        add_to_queue(message.chat.id, path)
        await check_and_play_next(message.chat.id)

    elif message.audio or message.voice:
        file = await message.download(file_name=f"downloads/audio_{message.message_id}.mp3")
        add_to_queue(message.chat.id, file)
        await check_and_play_next(message.chat.id)

@app.on_message(filters.command("صف") & filters.group)
async def show_queue(client, message):
    queue = play_queues.get(message.chat.id, [])
    if not queue:
        await message.reply("صف خالی است")
    else:
        msg = "\n".join([f"{i+1}. {os.path.basename(track)}" for i, track in enumerate(queue)])
        await message.reply(f"صف پخش:\n{msg}")

@app.on_message(filters.command("ردکردن") & filters.group)
async def skip_track(client, message):
    await pytgcalls.leave_group_call(message.chat.id)
    is_playing[message.chat.id] = False
    await check_and_play_next(message.chat.id)

@app.on_message(filters.command("پایان") & filters.group)
async def stop_call(client, message):
    await pytgcalls.leave_group_call(message.chat.id)
    is_playing[message.chat.id] = False
    if message.chat.id in voice_chats:
        del voice_chats[message.chat.id]

@app.on_message(filters.command("پاکسازی") & filters.group)
async def clear_files(client, message):
    if os.path.exists("downloads"):
        for f in os.listdir("downloads"):
            if f.endswith(".mp3"):
                os.remove(os.path.join("downloads", f))
    await message.reply("فایل‌های صوتی حذف شدند")

@app.on_message(filters.command("joinvc") & filters.group)
async def join_vc(client, message):
    await pytgcalls.join_group_call(
        message.chat.id,
        InputStream(AudioPiped("downloads/silence.mp3")),
        stream_type="local",
    )

@app.on_message(filters.command("leftvc") & filters.group)
async def leave_vc(client, message):
    await pytgcalls.leave_group_call(message.chat.id)

async def main():
    await app.start()
    await pytgcalls.start()
    print("ربات آماده است")
    await idle()
    await app.stop()

asyncio.run(main())
