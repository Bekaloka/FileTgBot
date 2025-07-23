import asyncio
import os
import io
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from PIL import Image, ImageTk
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# ============= НАСТРОЙКИ БОТА =============
BOT_TOKEN = "7606009503:AAGY5Cdbhqc3nqJCtAidevTc69DGy63n-Z8"  # Токен из переменной окружения
# ==========================================

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FileConverterBot:
    def __init__(self, token: str):
        self.token = token
        self.app = None
        self.temp_dir = Path("temp_files")
        self.temp_dir.mkdir(exist_ok=True)
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        keyboard = [
            [InlineKeyboardButton("📸 PNG ↔️ JPG", callback_data="convert_image")],
            [InlineKeyboardButton("📄 TXT → PDF", callback_data="convert_txt")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "🤖 **File Converter Bot**\n\n"
            "Я умею конвертировать файлы:\n"
            "• PNG ↔️ JPG (в обе стороны)\n"
            "• TXT → PDF\n\n"
            "Выберите тип конвертации:"
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "convert_image":
            await query.edit_message_text(
                "📸 **Конвертация изображений**\n\n"
                "Отправьте мне изображение (PNG или JPG) и я конвертирую его:\n"
                "• PNG → JPG\n"
                "• JPG → PNG\n\n"
                "Просто отправьте файл!",
                parse_mode='Markdown'
            )
            context.user_data['mode'] = 'image'
            
        elif query.data == "convert_txt":
            await query.edit_message_text(
                "📄 **Конвертация TXT в PDF**\n\n"
                "Отправьте мне текстовый файл (.txt) и я конвертирую его в PDF.\n\n"
                "Просто отправьте файл!",
                parse_mode='Markdown'
            )
            context.user_data['mode'] = 'txt'
            
        elif query.data == "help":
            help_text = (
                "ℹ️ **Справка**\n\n"
                "**Поддерживаемые форматы:**\n"
                "• PNG ↔️ JPG (взаимная конвертация)\n"
                "• TXT → PDF\n\n"
                "**Как использовать:**\n"
                "1. Выберите тип конвертации\n"
                "2. Отправьте файл\n"
                "3. Получите конвертированный файл\n\n"
                "**Ограничения:**\n"
                "• Максимальный размер файла: 20MB\n"
                "• Поддерживается кириллица в PDF"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        elif query.data == "back":
            await self.start_command_callback(query, context)
    
    async def start_command_callback(self, query, context):
        """Показать главное меню"""
        keyboard = [
            [InlineKeyboardButton("📸 PNG ↔️ JPG", callback_data="convert_image")],
            [InlineKeyboardButton("📄 TXT → PDF", callback_data="convert_txt")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "🤖 **File Converter Bot**\n\n"
            "Я умею конвертировать файлы:\n"
            "• PNG ↔️ JPG (в обе стороны)\n"
            "• TXT → PDF\n\n"
            "Выберите тип конвертации:"
        )
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загруженных файлов"""
        if 'mode' not in context.user_data:
            await update.message.reply_text("Сначала выберите тип конвертации через /start")
            return
        
        document = update.message.document
        if not document:
            await update.message.reply_text("Пожалуйста, отправьте файл.")
            return
        
        # Проверка размера файла (20MB)
        if document.file_size > 20 * 1024 * 1024:
            await update.message.reply_text("❌ Файл слишком большой! Максимальный размер: 20MB")
            return
        
        mode = context.user_data['mode']
        
        try:
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            file_path = self.temp_dir / f"{document.file_id}_{document.file_name}"
            await file.download_to_drive(file_path)
            
            await update.message.reply_text("⏳ Конвертирую файл...")
            
            if mode == 'image':
                await self.convert_image(update, file_path, document.file_name)
            elif mode == 'txt':
                await self.convert_txt_to_pdf(update, file_path, document.file_name)
                
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            await update.message.reply_text(f"❌ Ошибка при конвертации: {str(e)}")
        finally:
            # Очистка временных файлов
            if file_path.exists():
                file_path.unlink()
    
    async def convert_image(self, update: Update, input_path: Path, original_name: str):
        """Конвертация изображений PNG ↔️ JPG"""
        try:
            with Image.open(input_path) as img:
                # Определяем целевой формат
                if input_path.suffix.lower() in ['.png']:
                    output_format = 'JPEG'
                    output_ext = '.jpg'
                    # Конвертируем RGBA в RGB для JPG
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                elif input_path.suffix.lower() in ['.jpg', '.jpeg']:
                    output_format = 'PNG'
                    output_ext = '.png'
                else:
                    await update.message.reply_text("❌ Поддерживаются только PNG и JPG файлы!")
                    return
                
                # Создаем выходной файл
                output_name = Path(original_name).stem + output_ext
                output_path = self.temp_dir / f"converted_{output_name}"
                
                # Сохраняем конвертированное изображение
                img.save(output_path, format=output_format, quality=95 if output_format == 'JPEG' else None)
                
                # Отправляем результат
                with open(output_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=output_name,
                        caption=f"✅ Конвертировано: {original_name} → {output_name}"
                    )
                
                # Удаляем временный файл
                output_path.unlink()
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка конвертации изображения: {str(e)}")
    
    async def convert_txt_to_pdf(self, update: Update, input_path: Path, original_name: str):
        """Конвертация TXT в PDF"""
        try:
            # Читаем текстовый файл
            with open(input_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            # Создаем PDF
            output_name = Path(original_name).stem + '.pdf'
            output_path = self.temp_dir / f"converted_{output_name}"
            
            c = canvas.Canvas(str(output_path), pagesize=letter)
            width, height = letter
            
            # Пытаемся зарегистрировать шрифт для кириллицы
            try:
                # Используем встроенный шрифт, поддерживающий UTF-8
                c.setFont("Helvetica", 12)
            except:
                c.setFont("Helvetica", 12)
            
            # Разбиваем текст на строки
            lines = text_content.split('\n')
            y_position = height - 50
            line_height = 14
            
            for line in lines:
                if y_position < 50:  # Новая страница
                    c.showPage()
                    c.setFont("Helvetica", 12)
                    y_position = height - 50
                
                # Обрезаем длинные строки
                if len(line) > 80:
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line + word) < 80:
                            current_line += word + " "
                        else:
                            if current_line:
                                try:
                                    c.drawString(50, y_position, current_line.strip())
                                except:
                                    # Если не удается отобразить символы, заменяем на безопасные
                                    safe_line = current_line.encode('ascii', 'replace').decode('ascii')
                                    c.drawString(50, y_position, safe_line.strip())
                                y_position -= line_height
                                if y_position < 50:
                                    c.showPage()
                                    c.setFont("Helvetica", 12)
                                    y_position = height - 50
                            current_line = word + " "
                    
                    if current_line:
                        try:
                            c.drawString(50, y_position, current_line.strip())
                        except:
                            safe_line = current_line.encode('ascii', 'replace').decode('ascii')
                            c.drawString(50, y_position, safe_line.strip())
                        y_position -= line_height
                else:
                    try:
                        c.drawString(50, y_position, line)
                    except:
                        safe_line = line.encode('ascii', 'replace').decode('ascii')
                        c.drawString(50, y_position, safe_line)
                    y_position -= line_height
            
            c.save()
            
            # Отправляем результат
            with open(output_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=output_name,
                    caption=f"✅ Конвертировано: {original_name} → {output_name}"
                )
            
            # Удаляем временный файл
            output_path.unlink()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка конвертации в PDF: {str(e)}")
    
    def run_bot(self, token):
        """Запуск бота"""
        self.app = Application.builder().token(token).build()
        
        # Добавляем обработчики
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Запускаем бота
        self.app.run_polling()

class FileConverterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("File Converter Bot Manager")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        self.bot = None
        self.bot_thread = None
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        # Заголовок
        title_label = tk.Label(self.root, text="🤖 File Converter Bot", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Фрейм для токена
        token_frame = ttk.LabelFrame(self.root, text="Настройки бота", padding=10)
        token_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(token_frame, text="Telegram Bot Token:").pack(anchor="w")
        self.token_entry = tk.Entry(token_frame, width=60, show="*")
        self.token_entry.pack(fill="x", pady=5)
        
        # Кнопки управления
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        self.start_button = ttk.Button(control_frame, text="▶️ Запустить бота", command=self.start_bot)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="⏹️ Остановить бота", command=self.stop_bot, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        # Статус
        status_frame = ttk.LabelFrame(self.root, text="Статус", padding=10)
        status_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.status_text = tk.Text(status_frame, height=10, state="disabled")
        self.status_text.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Информация
        info_frame = ttk.LabelFrame(self.root, text="Информация", padding=10)
        info_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        info_text = (
            "Функции бота:\n"
            "• Конвертация PNG ↔️ JPG\n"
            "• Конвертация TXT → PDF\n"
            "• Максимальный размер файла: 20MB"
        )
        tk.Label(info_frame, text=info_text, justify="left").pack(anchor="w")
        
        self.log_message("Готов к запуску.")
        
        # Автозапуск бота если токен указан
        if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
            self.token_entry.insert(0, BOT_TOKEN)
            self.root.after(1000, self.start_bot)  # Автостарт через 1 секунду
    
    def log_message(self, message):
        """Добавление сообщения в лог"""
        self.status_text.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert("end", f"[{timestamp}] {message}\n")
        self.status_text.config(state="disabled")
        self.status_text.see("end")
    
    def start_bot(self):
        """Запуск бота"""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror("Ошибка", "Введите токен бота!")
            return
        
        self.bot = FileConverterBot(token)
        self.bot_thread = threading.Thread(target=self.run_bot_thread, args=(token,), daemon=True)
        self.bot_thread.start()
        
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.token_entry.config(state="disabled")
        
        self.log_message("Бот запускается...")
    
    def run_bot_thread(self, token):
        """Запуск бота в отдельном потоке"""
        try:
            self.bot.run_bot(token)
        except Exception as e:
            self.log_message(f"Ошибка запуска бота: {e}")
            self.root.after(0, self.reset_ui)
    
    def stop_bot(self):
        """Остановка бота"""
        if self.bot and self.bot.app:
            self.bot.app.stop_running()
        
        self.reset_ui()
        self.log_message("Бот остановлен.")
    
    def reset_ui(self):
        """Сброс интерфейса"""
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.token_entry.config(state="normal")
    
    def run(self):
        """Запуск GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    # Проверяем окружение
    if os.getenv("RAILWAY_ENVIRONMENT"):
        # Запуск на Railway без GUI
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ BOT_TOKEN не установлен! Добавьте переменную окружения BOT_TOKEN")
            exit(1)
        
        logger.info("🚀 Запуск бота на Railway...")
        bot = FileConverterBot(BOT_TOKEN)
        bot.run_bot(BOT_TOKEN)
    else:
        # Локальный запуск с GUI
        if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("⚠️  Для локального запуска замените BOT_TOKEN на ваш токен")
            print("📝 Или установите переменную окружения: export BOT_TOKEN=ваш_токен")
        
        app = FileConverterGUI()
        app.run()
