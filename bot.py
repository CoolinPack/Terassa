import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import json
import os
from datetime import datetime
from config import config
from database import db
from menu_data import init_menu, get_menu_json
from admin_upload import ImageUploader
from flask import Flask, request, jsonify
import threading

# ============ ИНИЦИАЛИЗАЦИЯ ============

bot = telebot.TeleBot(config.BOT_TOKEN)
uploader = ImageUploader(bot)

# Инициализируем меню при старте
init_menu()

# Временное хранилище для загрузки фото
upload_sessions = {}

# Flask приложение
app = Flask(__name__)

# ============ ЭНДПОИНТЫ ДЛЯ RENDER HEALTH CHECK ============

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'Terassa Bot is running',
        'version': '1.0.0'
    })

@app.route('/healthz')
def health():
    return jsonify({'status': 'healthy'}), 200

# ============ КОМАНДЫ БОТА ============

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    
    # 🔥 СЮДА ВСТАВЬ СВОЙ URL MINI APP (GitHub Pages)
    web_app_url = "https://coolinpack.github.io/Terassa/"
    
    web_app_btn = InlineKeyboardButton(
        text="🍽 Открыть меню",
        web_app=WebAppInfo(url=web_app_url)
    )
    markup.add(web_app_btn)
    
    bot.send_message(
        message.chat.id,
        "🍷 Добро пожаловать в Terassa!\n\n"
        "🏛️ Ресторан итальянской кухни\n\n"
        "Нажмите кнопку ниже, чтобы сделать заказ:",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 *Команды бота Terassa:*

/start - Открыть меню
/orders - Просмотр заказов (админ)
/upload - Загрузить картинку (админ)
/add_dish - Добавить блюдо (админ)
/help - Помощь

👨‍🍳 *Для администратора:*
• Заказы приходят автоматически
• /orders - список заказов
• /upload - загрузка картинок
• /add_dish - добавить блюдо
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

# ============ КОМАНДЫ АДМИНИСТРАТОРА ============

@bot.message_handler(commands=['orders'])
def show_orders(message):
    if str(message.chat.id) != config.ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ Нет прав")
        return
    
    orders = db.get_orders(10)
    
    if not orders:
        bot.reply_to(message, "📭 Заказов нет")
        return
    
    response = "📋 *Последние заказы:*\n\n"
    
    status_emoji = {
        'new': '🆕',
        'cooking': '👨‍🍳',
        'ready': '✅',
        'completed': '📦'
    }
    
    for order in orders:
        status = order.get('status', 'new')
        emoji = status_emoji.get(status, '❓')
        response += f"*#{order['id']}* {emoji} {status}\n"
        response += f"👤 {order['user_name']} {order['user_surname']}\n"
        response += f"💰 {order['total']} ₽\n"
        response += f"⏰ {order['created_at']}\n\n"
    
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(commands=['upload'])
def upload_image_command(message):
    if str(message.chat.id) != config.ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ Нет прав")
        return
    
    menu = db.get_menu()
    
    if not menu:
        bot.reply_to(message, "📭 Меню пусто. Сначала добавьте блюда: /add_dish")
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for dish in menu:
        btn = InlineKeyboardButton(
            f"{dish['id']}. {dish['name']}",
            callback_data=f"upload_{dish['id']}"
        )
        markup.add(btn)
    
    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="upload_cancel"))
    
    bot.send_message(
        message.chat.id,
        "📸 Выберите блюдо для загрузки картинки:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('upload_'))
def handle_upload_callback(call):
    if str(call.message.chat.id) != config.ADMIN_CHAT_ID:
        bot.answer_callback_query(call.id, "⛔ Нет прав")
        return
    
    if call.data == 'upload_cancel':
        bot.edit_message_text("❌ Отменено", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    dish_id = int(call.data.split('_')[1])
    dish = db.get_dish_by_id(dish_id)
    
    if not dish:
        bot.answer_callback_query(call.id, "❌ Блюдо не найдено")
        return
    
    upload_sessions[call.message.chat.id] = dish_id
    
    bot.edit_message_text(
        f"📸 Отправьте фото для блюда:\n\n"
        f"🍽 {dish['name']}\n"
        f"💰 {dish['price']} ₽\n\n"
        f"Просто отправьте фотографию",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if str(message.chat.id) != config.ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ Нет прав")
        return
    
    if message.chat.id not in upload_sessions:
        bot.reply_to(message, "❌ Сначала используйте /upload")
        return
    
    dish_id = upload_sessions[message.chat.id]
    dish = db.get_dish_by_id(dish_id)
    
    if not dish:
        bot.reply_to(message, "❌ Блюдо не найдено")
        return
    
    # Скачиваем фото
    file_id = message.photo[-1].file_id
    success, result = uploader.save_image_from_telegram(file_id, dish_id)
    
    if success:
        bot.reply_to(
            message,
            f"✅ Картинка загружена для блюда:\n"
            f"🍽 {dish['name']}\n\n"
            f"📁 {result}"
        )
        del upload_sessions[message.chat.id]
    else:
        bot.reply_to(message, f"❌ Ошибка: {result}")

@bot.message_handler(commands=['add_dish'])
def add_dish_command(message):
    if str(message.chat.id) != config.ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ Нет прав")
        return
    
    bot.reply_to(
        message,
        "📝 Добавление блюда.\n\n"
        "Формат:\n"
        "/add_dish Название | Цена | Категория | Ингредиенты | Описание\n\n"
        "Пример:\n"
        "/add_dish Пицца Маргарита | 550 | Горячее | томаты, моцарелла, базилик | Классическая пицца"
    )

@bot.message_handler(commands=['add_dish'], func=lambda m: True)
def process_add_dish(message):
    if str(message.chat.id) != config.ADMIN_CHAT_ID:
        return
    
    try:
        parts = message.text.replace('/add_dish ', '').split(' | ')
        if len(parts) < 3:
            bot.reply_to(message, "❌ Недостаточно данных. Формат: Название | Цена | Категория | Ингредиенты | Описание")
            return
        
        dish_data = {
            'name': parts[0].strip(),
            'price': int(parts[1].strip()),
            'category': parts[2].strip(),
            'ingredients': parts[3].strip() if len(parts) > 3 else '',
            'description': parts[4].strip() if len(parts) > 4 else '',
            'is_popular': 0
        }
        
        dish_id = db.add_dish(dish_data)
        bot.reply_to(
            message,
            f"✅ Блюдо добавлено!\n\n"
            f"ID: {dish_id}\n"
            f"Название: {dish_data['name']}\n"
            f"Цена: {dish_data['price']} ₽\n"
            f"Категория: {dish_data['category']}\n\n"
            f"Теперь загрузите картинку: /upload"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

# ============ ОБРАБОТКА ЗАКАЗОВ (WEBHOOK) ============

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        
        # Проверяем обязательные поля
        required = ['user_name', 'user_surname', 'user_phone', 'items', 'total', 'delivery_type']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing {field}'}), 400
        
        # Сохраняем заказ
        order_id = db.save_order(data)
        
        # Формируем чек для админа
        items_text = ""
        for idx, item in enumerate(data['items'], 1):
            items_text += f"{idx}. {item['name']} x{item['quantity']} = {item['price'] * item['quantity']} ₽\n"
        
        delivery_text = "Заберу с собой" if data['delivery_type'] == 'pickup' else "Доставка"
        
        message = f"""
🆕 *НОВЫЙ ЗАКАЗ # {order_id}*

👤 *Клиент:* {data['user_name']} {data['user_surname']}
📞 *Телефон:* {data['user_phone']}
🎂 *Год рождения:* {data.get('user_birth_year', 'не указан')}

📦 *Тип:* {delivery_text}

🛒 *Состав заказа:*
{items_text}

💰 *Итого:* {data['total']} ₽

⏰ *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        # Отправляем админу
        bot.send_message(config.ADMIN_CHAT_ID, message, parse_mode="Markdown")
        
        # Кнопки управления статусом
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("👨‍🍳 Готовится", callback_data=f"status_{order_id}_cooking"),
            InlineKeyboardButton("✅ Готов", callback_data=f"status_{order_id}_ready")
        )
        markup.add(
            InlineKeyboardButton("📦 Выдан", callback_data=f"status_{order_id}_completed")
        )
        
        bot.send_message(
            config.ADMIN_CHAT_ID,
            f"Управление заказом #{order_id}:",
            reply_markup=markup
        )
        
        return jsonify({'success': True, 'order_id': order_id})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/menu', methods=['GET'])
def get_menu():
    menu = get_menu_json()
    return jsonify(menu)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def handle_status_callback(call):
    if str(call.message.chat.id) != config.ADMIN_CHAT_ID:
        bot.answer_callback_query(call.id, "⛔ Нет прав")
        return
    
    try:
        _, order_id, new_status = call.data.split('_')
        order_id = int(order_id)
        
        db.update_order_status(order_id, new_status)
        
        status_texts = {
            'new': '🆕 Новый',
            'cooking': '👨‍🍳 Готовится',
            'ready': '✅ Готов',
            'completed': '📦 Выдан'
        }
        
        bot.answer_callback_query(
            call.id,
            f"Статус заказа #{order_id}: {status_texts.get(new_status, new_status)}"
        )
        
        bot.edit_message_text(
            f"✅ Статус заказа #{order_id} обновлён: {status_texts.get(new_status, new_status)}",
            call.message.chat.id,
            call.message.message_id
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

# ============ ЗАПУСК ============

def run_bot():
    print("🤖 Бот запущен и слушает команды...")
    bot.infinity_polling()

if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask для вебхуков
    print("🌐 Flask сервер запущен на порту 5000")
    app.run(host='0.0.0.0', port=5000)
