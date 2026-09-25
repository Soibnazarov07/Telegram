import os
import re
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI

# ================== SOZLAMALAR ==================
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
SESSION_STRING = os.environ["SESSION_STRING"]

AI_MODEL = "openai/gpt-oss-120b"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

bot_active = True
welcomed_chats = {}
chat_histories = {}
allowed_groups = set()

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[’‘ʻʼ`´]", "'", text)
    return text

NAME_KEYWORDS = [
    "ro'zimurod",
    "rozimurod",
    "ro'zi",
    "rozi",
    "ruzi",
    "ro'zibek",
    "rozibek",
    "ruzibek",
    "soibnazarov",
    "soib",
]

# ================== BUYRUQLAR ==================
@client.on(events.NewMessage(pattern="/stop", outgoing=True))
async def stop_bot(event):
    global bot_active
    bot_active = False
    await event.edit("🛠 **AI yordamchi vaqtincha o'chirildi!**")


@client.on(events.NewMessage(pattern="/start_bot", outgoing=True))
async def start_bot(event):
    global bot_active
    bot_active = True
    await event.edit("🚀 **AI yordamchi qaytadan yoqildi!**")


@client.on(events.NewMessage(pattern="/clear", outgoing=True))
async def clear_memory(event):
    chat_id = event.chat_id
    if chat_id in chat_histories:
        del chat_histories[chat_id]
    await event.edit("🗑 **Ushbu chat uchun xotira tozalandi!**")


@client.on(events.NewMessage(pattern="/add_group", outgoing=True))
async def add_group(event):
    if not event.is_group:
        await event.edit("❌ Bu buyruq faqat **guruh**da ishlaydi!")
        return
    allowed_groups.add(event.chat_id)
    title = getattr(event.chat, "title", str(event.chat_id))
    await event.edit(f"✅ Guruh qo'shildi:\n**{title}**\n`{event.chat_id}`")


@client.on(events.NewMessage(pattern="/remove_group", outgoing=True))
async def remove_group(event):
    if not event.is_group:
        await event.edit("❌ Bu buyruq faqat **guruh**da ishlaydi!")
        return
    if event.chat_id in allowed_groups:
        allowed_groups.discard(event.chat_id)
        title = getattr(event.chat, "title", str(event.chat_id))
        await event.edit(f"🗑 Guruh olib tashlandi:\n**{title}**\n`{event.chat_id}`")
    else:
        await event.edit("ℹ️ Bu guruh allaqachon ro'yxatda yo'q.")


@client.on(events.NewMessage(pattern="/list_groups", outgoing=True))
async def list_groups(event):
    if not allowed_groups:
        await event.edit("📭 Hozircha hech qanday guruh qo'shilmagan.\n\nGuruhga kirib `/add_group` yuboring.")
        return
    text = "✅ **Ruxsat etilgan guruhlar:**\n\n"
    for gid in allowed_groups:
        text += f"• `{gid}`\n"
    await event.edit(text)


# ================== ASOSIY HANDLER ==================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global bot_active

    if not bot_active:
        return

    if event.is_group:
        if event.chat_id not in allowed_groups:
            return

        text_norm = normalize_text(event.raw_text or "")
        is_mentioned = event.mentioned
        has_name = any(keyword in text_norm for keyword in NAME_KEYWORDS)

        if not (is_mentioned or has_name):
            return

    elif event.is_channel:
        return

    sender = await event.get_sender()
    if sender and getattr(sender, "bot", False):
        return

    try:
        async for last_msg in client.iter_messages(event.chat_id, limit=1):
            if last_msg.out:
                return
    except Exception:
        pass

    incoming_message = (event.raw_text or "").strip()
    chat_id = event.chat_id
    current_time = time.time()

    try:
        if event.voice or event.audio:
            status = await event.reply("🎧 Ovozli xabar qabul qilindi, matnga o‘girilmoqda...")
            file_path = await event.download_media(file="temp_audio.ogg")
            try:
                with open(file_path, "rb") as audio_file:
                    transcript = groq_client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=audio_file,
                        language="uz",
                    )
                incoming_message = transcript.text or ""
            finally:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            try:
                await status.delete()
            except Exception:
                pass

        if event.photo:
            file_path = await event.download_media(file="temp_image.jpg")
            caption = incoming_message or "Rasm bo‘yicha fikringizni bildiring"
            incoming_message = f"[Foydalanuvchi rasm yubordi. Caption: {caption}]"
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

        if not incoming_message:
            incoming_message = "Salom"

        ONE_DAY = 24 * 60 * 60
        needs_welcome = (
            chat_id not in welcomed_chats
            or (current_time - welcomed_chats[chat_id]) > ONE_DAY
        )

        if needs_welcome:
            welcome_text = (
                "Hozirda **Soibnazarov Ro'zimurod** bandlar, lekin tez orada yana aloqaga chiqadilar.\n"
                "🤖 Ungacha ularning o‘rniga men — sun’iy intellekt (**AI**) yordamchisi javob beryapman.\n\n"
                "💬 Matn, ovoz yoki rasm yuborishingiz mumkin."
            )
            await event.reply(welcome_text)
            welcomed_chats[chat_id] = current_time

        system_prompt = (
            "Siz Soibnazarov Ro'zimurodning sun'iy intellekt (AI) yordamchisiz. "
            "O'zbek tilida imlo xatolarisiz, savodli va ravon yozing. "
            "MUHIM QOIDA: Foydalanuvchilar egangiz haqida so'rashsa, faqatgina ismini "
            "(Soibnazarov Ro'zimurod) aytishingiz mumkin. "
            "Uning ismidan boshqa hech qanday shaxsiy ma'lumotni "
            "(manzil, o'qish joyi, nima ish qilishi, telefon raqami va hokazo) mutlaqo bermang. "
            "Agar boshqa shaxsiy ma'lumotlarni so'rashsa, buni aytolmasligingizni bildiring. "
            "Har bir javobingizda qisqacha «Men Ro'zimurodning AI yordamchisiman» deb eslatib o'ting "
            "va savoliga chiroyli emojilar bilan javob bering. "
            "Javoblaringiz qisqa, aniq va foydali bo'lsin.\n\n"
            "MAXSUS QOIDA (Tug'ilgan kun): "
            "Agar foydalanuvchi tug'ilgan kun tabrigi yozsa (masalan: 'tug'ilgan kuningiz bilan', "
            "'tabriklayman', 'yaxshi kunlar tilayman', 'bayramingiz muborak', 'tug'ilgan kun muborak' va h.k.), "
            "samimiy va HAR XIL uslubda minnatdorchilik bildiring. "
            "Har safar bir xil javob bermang! "
            "Masalan quyidagilardan birini yoki o'zingiz yangi chiroyli variant yarating:\n"
            "• «Rahmat! 😊 Tabrikingiz uchun katta rahmat! Men Ro'zimurodning AI yordamchisiman menga istalgan savolingizni berishingiz mumkin.»\n"
            "• «Juda xursandman, rahmat! 🎉 Yaxshi tilaklaringiz uchun tashakkur. Men Ro'zimurodning AI yordamchisiman menga istalgan savolingizni berishingiz mumkin.»\n"
            "• «Katta rahmat! 🙏 Tabrikingiz yurakka yetdi. Men Ro'zimurodning AI yordamchisiman menga istalgan savolingizni berishingiz mumkin.»\n"
            "• «Rahmat, do'st! 💫 Yaxshi kunlar o'zingizga ham. Men Ro'zimurodning AI yordamchisiman menga istalgan savolingizni berishingiz mumkin.»\n"
            "• «Tabrigingiz uchun chin dildan rahmat! 😊 Men Ro'zimurodning AI yordamchisiman menga istalgan savolingizni berishingiz mumkin.»\n"
            "Javobni qisqa, samimiy va emojilar bilan bezating."
        )

        if chat_id not in chat_histories:
            chat_histories[chat_id] = [{"role": "system", "content": system_prompt}]

        chat_histories[chat_id].append({"role": "user", "content": incoming_message})

        if len(chat_histories[chat_id]) > 21:
            chat_histories[chat_id] = (
                [chat_histories[chat_id][0]] + chat_histories[chat_id][-20:]
            )

        response = groq_client.chat.completions.create(
            model=AI_MODEL,
            messages=chat_histories[chat_id],
            temperature=0.85,  # biroz ko'proq xilma-xillik uchun
            max_tokens=1024,
        )

        ai_reply = (response.choices[0].message.content or "").strip()
        if not ai_reply:
            ai_reply = "Hozirda javob bera olmadim. Birozdan keyin qayta yozing. 🤖"

        chat_histories[chat_id].append({"role": "assistant", "content": ai_reply})
        await event.reply(ai_reply)

    except Exception as e:
        print(f"[XATO] chat={chat_id}: {type(e).__name__}: {e}")
        try:
            await event.reply(
                "Hozirda Soibnazarov Ro'zimurod bandlar. "
                "Men ularning AI yordamchisiman! 🤖\n"
                "Birozdan keyin qayta urinib ko‘ring."
            )
        except Exception:
            pass


def main():
    print(f"✅ AI yordamchi ishga tushdi | Model: {AI_MODEL}")
    print(f"📌 Ruxsat etilgan guruhlar: {len(allowed_groups)} ta")
    client.start()
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
