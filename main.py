import os
import time
import urllib.request
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

bot_active = True
welcomed_chats = {}

# Har bir chat uchun xotirani saqlab turuvchi lug'at (chat_id: messages_list)
chat_histories = {}

@client.on(events.NewMessage(pattern='/stop', outgoing=True))
async def stop_bot(event):
    global bot_active
    bot_active = False
    await event.edit("🛠 **AI yordamchi vaqtincha o'chirildi!**")

@client.on(events.NewMessage(pattern='/start_bot', outgoing=True))
async def start_bot(event):
    global bot_active
    bot_active = True
    await event.edit("🚀 **AI yordamchi qaytadan yoqildi!**")

@client.on(events.NewMessage(pattern='/clear', outgoing=True))
async def clear_memory(event):
    chat_id = event.chat_id
    if chat_id in chat_histories:
        del chat_histories[chat_id]
    await event.edit("🗑 **Ushbu chat uchun xotira tozalandi!**")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global bot_active
    
    if not bot_active:
        return

    # FAQAT SHAXSIY CHATLARNI QABUL QILISH (Guruh va kanallarni o'tkazib yuborish)
    if event.is_group or event.is_channel:
        return

    sender = await event.get_sender()
    if sender and sender.bot:
        return

    # Shaxsiy chatda o'zingiz yozgan bo'lsangiz to'xtaydi
    messages_iter = client.iter_messages(event.chat_id, limit=1)
    async for last_msg in messages_iter:
        if last_msg.out:
            return

    incoming_message = event.raw_text or ""
    chat_id = event.chat_id
    current_time = time.time()

    try:
        # --- 1. OVOZLI XABARni MATNga O'GIRISH ---
        if event.voice or event.audio:
            await event.reply("🎧 *Ovozli xabar qabul qilindi, tinglab matnga o'giryapman...*")
            file_path = await event.download_media(file="temp_audio.ogg")
            
            with open(file_path, "rb") as audio_file:
                transcript = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio_file
                )
            incoming_message = transcript.text
            os.remove(file_path) # Faylni o'chirib tashlaymiz

        # --- 2. RASMLAR BILAN ISHLASH ---
        if event.photo:
            file_path = await event.download_media(file="temp_image.jpg")
            incoming_message = "[Foydalanuvchi rasm yubordi va shunday dedi: " + (incoming_message or "Rasm bo'yicha fikringizni bildiring") + "]"
            if os.path.exists(file_path):
                os.remove(file_path)

        # --- 3. BANDLIK XABARI (Faqat shaxsiy chat uchun 1 kunda 1 marta) ---
        ONE_DAY_SECONDS = 24 * 60 * 60
        needs_welcome = False
        
        if chat_id not in welcomed_chats:
            needs_welcome = True
        else:
            if current_time - welcomed_chats[chat_id] > ONE_DAY_SECONDS:
                needs_welcome = True

        if needs_welcome:
            welcome_text = (
                "Hozirda **Soibnazarov Ro'zimurod** bandlar, lekin **tez orada yana aloqaga chiqadilar**.\n"
                "🤖 Ungacha ularning o'rniga men — sun'iy intellekt (**AI**) yordamchisi javob beryapman.\n\n"
                "💬 Menga xohlagan matnli, ovozli yoki rasm ko'rinishidagi savollaringizni yuborishingiz mumkin. Qanday yordam bera olaman?"
            )
            await event.reply(welcome_text)
            welcomed_chats[chat_id] = current_time
            return

        # --- 4. XOTIRANI BOSHQARISH VA AI JAVOB QAYTARISH ---
        system_prompt = (
            "Siz Soibnazarov Ro'zimurodning sun'iy intellekt (AI) yordamchisiz. "
            "O'zbek tilida imlo xatolarisiz, savodli va ravon yozing. "
            "MUHIM QOIDA: Foydalanuvchilar egangiz haqida so'rashsa, faqatgina ismini (Soibnazarov Ro'zimurod) aytishingiz mumkin. "
            "Uning ismidan boshqa hech qanday shaxsiy ma'lumotni (manzil, o'qish joyi, nima ish qilishi, telefon raqami va hokazo) mutlaqo bermang. "
            "Agar boshqa shaxsiy ma'lumotlarni so'rashsa, buni aytolmasligingizni bildiring. "
            "Faqat har bir javobingizda qisqacha 'Men Ro'zimurodning AI yordamchisiman' deb eslatib o'ting va savoliga chiroyli emojilar bilan javob bering."
        )

        # Agar bu chat uchun xotira hali mavjud bo'lmasa, uni yaratamiz va system promptni qo'shamiz
        if chat_id not in chat_histories:
            chat_histories[chat_id] = [
                {"role": "system", "content": system_prompt}
            ]

        # Foydalanuvchi xabarini tarixga qo'shamiz
        chat_histories[chat_id].append({"role": "user", "content": incoming_message or "Salom"})

        # Xotira haddan tashqari uzun bo'lib ketmasligi uchun oxirgi 20 ta xabarni saqlab qolamiz (system prompt doim 1-o'rinda qoladi)
        if len(chat_histories[chat_id]) > 21:
            chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-20:]

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat_histories[chat_id]
        )
        
        ai_reply = response.choices[0].message.content
        
        # AI javobini ham tarixga qo'shamiz
        chat_histories[chat_id].append({"role": "assistant", "content": ai_reply})

        await event.reply(ai_reply)
        
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        await event.reply("Hozirda Soibnazarov Ro'zimurod bandlar. Men ularning AI yordamchisiman! 🤖")

def main():
    print("Mukammal AI yordamchi ishga tushdi...")
    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    main()
