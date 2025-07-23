import os
import tempfile
import logging
from PIL import Image
from fpdf import FPDF
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден! Добавь в Railway → Variables")

# 🌐 Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sigmabot")

# 📈 Счётчики
stats = {
    "converted_images": 0,
    "converted_txts": 0,
    "users": set()
}

# 📄 TXT → PDF
def txt_to_pdf(txt_path: str, output_path: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            pdf.multi_cell(0, 8, line.strip())
    pdf.output(output_path)

# 📷 Обработка файла
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    stats["users"].add(user_id)

    tg_file = None
    filename = None
    ext = None

    if msg.document:
        tg_file = await context.bot.get_file(msg.document.file_id)
        filename = msg.document.file_name or "file"
        ext = os.path.splitext(filename)[-1].lower()
    elif msg.photo:
        tg_file = await context.bot.get_file(msg.photo[-1].file_id)
        filename = "photo.jpg"
        ext = ".jpg"
    else:
        await msg.reply_text("⚠ Пришли файл: PNG, JPG или TXT.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, f"input{ext}")
        output_path = os.path.join(tmp, "output")

        await tg_file.download_to_drive(input_path)

        try:
            if ext in [".png", ".jpg", ".jpeg"]:
                img = Image.open(input_path)
                if ext == ".png":
                    output_path += ".jpg"
                    img.convert("RGB").save(output_path, "JPEG")
                else:
                    output_path += ".png"
                    img.save(output_path, "PNG")
                stats["converted_images"] += 1
                out_name = os.path.basename(output_path)
                with open(output_path, "rb") as f:
                    await msg.reply_document(InputFile(f, filename=out_name))
            elif ext == ".txt":
                output_path += ".pdf"
                txt_to_pdf(input_path, output_path)
                stats["converted_txts"] += 1
                with open(output_path, "rb") as f:
                    await msg.reply_document(InputFile(f, filename="converted.pdf"))
            else:
                await msg.reply_text("❌ Поддерживаются только .png, .jpg, .jpeg, .txt")
        except Exception as e:
            logger.exception("Ошибка при обработке файла")
            await msg.reply_text("💥 Ошибка при конвертации. Проверь формат файла.")

# 📌 Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Я бот для конвертации файлов!\n"
        "📷 PNG ↔ JPG\n📄 TXT → PDF\n\n"
        "Просто пришли файл или напиши /help"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Команды:</b>\n"
        "/start – Приветствие\n"
        "/help – Все команды\n"
        "/convert – Как работает\n"
        "/stats – Статистика\n"
        "/about – Про бота",
        parse_mode="HTML"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>File Converter Bot</b> by @sigmadev\n"
        "🚀 Работает на python-telegram-bot 20.8\n"
        "🔥 Хостинг: Railway\n"
        "🛠 Исходник: по запросу\n",
        parse_mode="HTML"
    )

async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 Просто отправь:\n"
        "1. PNG или JPG — конвертирую в другой формат\n"
        "2. TXT — сделаю PDF\n"
        "⚠ Поддерживаются только .png, .jpg, .jpeg, .txt"
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 <b>Статистика:</b>\n"
        f"👥 Пользователей: {len(stats['users'])}\n"
        f"🖼 Картинок конвертировано: {stats['converted_images']}\n"
        f"📄 TXT → PDF: {stats['converted_txts']}",
        parse_mode="HTML"
    )

# 🚀 Запуск
def main():
    logger.info("Бот запускается...")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("convert", convert))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

    app.run_polling()

if __name__ == "__main__":
    main()
