import os
import tempfile
from PIL import Image
from fpdf import FPDF
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "7606009503:AAGY5Cdbhqc3nqJCtAidevTc69DGy63n-Z8" # вставь в Railway переменные окружения

# 🧊 Команда старта
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Отправь мне файл:\n📷 PNG/JPG → конвертация\n📄 TXT → PDF")

# 📄 TXT → PDF
def txt_to_pdf(txt_path, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    with open(txt_path, 'r', encoding='utf-8') as file:
        for line in file:
            pdf.cell(200, 10, txt=line.strip(), ln=True)
    pdf.output(output_path)

# 🔁 Обработка файлов
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    new_file = await context.bot.get_file(file_id)

    with tempfile.TemporaryDirectory() as tmp:
        original_path = os.path.join(tmp, "input")
        output_path = os.path.join(tmp, "output")

        if update.message.document:
            filename = update.message.document.file_name
            ext = os.path.splitext(filename)[-1].lower()
            original_path += ext
            await new_file.download_to_drive(original_path)

            if ext in ['.png', '.jpg', '.jpeg']:
                image = Image.open(original_path)
                if ext == '.png':
                    output_path += ".jpg"
                    rgb = image.convert("RGB")
                    rgb.save(output_path, "JPEG")
                else:
                    output_path += ".png"
                    image.save(output_path, "PNG")
                await update.message.reply_document(document=InputFile(output_path), filename=os.path.basename(output_path))

            elif ext == '.txt':
                output_path += ".pdf"
                txt_to_pdf(original_path, output_path)
                await update.message.reply_document(document=InputFile(output_path), filename="converted.pdf")
            else:
                await update.message.reply_text("❌ Поддерживаются только .png, .jpg, .jpeg, .txt")

        elif update.message.photo:
            await new_file.download_to_drive(original_path + ".jpg")
            img = Image.open(original_path + ".jpg")
            output_path += ".png"
            img.save(output_path, "PNG")
            await update.message.reply_document(document=InputFile(output_path), filename="converted.png")

# 🔁 Запуск бота
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
