import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
import json
import os
from datetime import datetime, timezone, timedelta
from config import config
from database import db
from menu_data import init_menu
from admin_upload import ImageUploader
from flask import Flask, request, jsonify
import threading

# ============ ИНИЦИАЛИЗАЦИЯ ============

bot = telebot.TeleBot(config.BOT_TOKEN)
uploader = ImageUploader(bot)

init_menu()

upload_sessions = {}

app = Flask(__name__)

VN_TZ = timezone(timedelta(hours=7))

def vn_now():
    return datetime.now(VN_TZ)

def vn_now_str():
    return vn_now().strftime('%d.%m.%Y %H:%M')


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


# ============ ЭНДПОИНТЫ ДЛЯ RENDER HEALTH CHECK ============

@app.route('/')
def home():
    return jsonify({'status': 'ok', 'message': 'Terassa Bot is running', 'version': '1.2.0'})

@app.route('/healthz')
def health():
    return jsonify({'status': 'healthy'}), 200


# ============ КОМАНДЫ БОТА ============

@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_url = "https://coolinpack.github.io/Terassa/"

    reply_markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True
    )
    reply_markup.add(KeyboardButton(text="🍽 Открыть меню", web_app=WebAppInfo(url=web_app_url)))

    bot.send_message(
        message.chat.id,
        "🍷 Добро пожаловать в Terassa!\n\n🏛️ Ресторан итальянской кухни\n\nНажмите кнопку ниже, чтобы сделать заказ:",
        reply_markup=reply_markup
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
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")


@bot.message_handler(commands=['whoami'])
def whoami(message):
    bot.send_message(
        message.chat.id,
        f"Твой ID: `{message.chat.id}`\n"
        f"Username: @{message.from_user.username}\n"
        f"ADMIN_CHAT_ID в конфиге: `{config.ADMIN_CHAT_ID}`\n"
        f"Совпадает: {str(message.chat.id) == str(config.ADMIN_CHAT_ID)}",
        parse_mode="Markdown"
    )


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
    status_emoji = {'new': '🆕', 'accepted': '👨‍🍳', 'ready': '✅', 'courier': '🚴', 'completed': '📦'}
    for order in orders:
        status = order.get('status', 'new')
        emoji = status_emoji.get(status, '❓')
        response += f"*#{order['id']}* {emoji} {status}\n"
        response += f"👤 {order['user_name']} {order['user_surname']}\n"
        
        # Добавляем кликабельную ссылку на ID клиента для удобства админа
        client_tg_id = order.get('telegram_id')
        if client_tg_id:
            response += f"🆔 ID: [{client_tg_id}](tg://user?id={client_tg_id})\n"
            
        response += f"💰 {order['total']} ₫\n"
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
        markup.add(InlineKeyboardButton(f"{dish['id']}. {dish['name']}", callback_data=f"upload_{dish['id']}"))
    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="upload_cancel"))
    bot.send_message(message.chat.id, "📸 Выберите блюдо для загрузки картинки:", reply_markup=markup)

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
        f"📸 Отправьте фото для блюда:\n\n🍽 {dish['name']}\n💰 {dish['price']} ₫\n\nПросто отправьте фотографию",
        call.message.chat.id, call.message.message_id
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
    file_id = message.photo[-1].file_id
    success, result = uploader.save_image_from_telegram(file_id, dish_id)
    if success:
        bot.reply_to(message, f"✅ Картинка загружена для блюда:\n🍽 {dish['name']}\n\n📁 {result}")
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
        "📝 Добавление блюда.\n\nФормат:\n/add_dish Название | Цена | Категория | Ингредиенты | Описание\n\n"
        "Пример:\n/add_dish Пицца Маргарита | 550 | Горячее | томаты, моцарелла, базилик | Классическая пицца"
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
            f"✅ Блюдо добавлено!\n\nID: {dish_id}\nНазвание: {dish_data['name']}\n"
            f"Цена: {dish_data['price']} ₫\nКатегория: {dish_data['category']}\n\nТеперь загрузите картинку: /upload"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


# ============ ОБРАБОТКА ЗАКАЗОВ (WEBHOOK) ============

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        data = request.get_json(silent=True) or {}

        required = ['user_name', 'user_surname', 'items', 'total', 'delivery_type']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing {field}'}), 400

        for item in data.get('items', []):
            try:
                item_id = int(item.get('id'))
            except (TypeError, ValueError):
                continue
            if item_id in db.get_stop_list_ids():
                recommendations = db.get_recommendations(item_id, 3)
                return jsonify({
                    'error': 'Одно из блюд в заказе временно недоступно',
                    'dish_id': item_id,
                    'recommendations': recommendations
                }), 409

        # При оформлении заказа обновляем username пользователя в БД
        telegram_id = str(data.get('telegram_id', '')).strip()
        if telegram_id:
            db.upsert_user(
                telegram_id=telegram_id,
                username=data.get('username') or None,
                first_name=data.get('user_name'),
                last_name=data.get('user_surname'),
            )

        order_id = db.save_order(data)

        items_text = ""
        for idx, item in enumerate(data['items'], 1):
            items_text += f"{idx}. {item['name']} x{item['quantity']} = {item['price'] * item['quantity']} ₫\n"

        delivery_text = "Заберу с собой" if data['delivery_type'] == 'pickup' else "Доставка"

        raw_username = (data.get('username') or '').strip()
        username_display = raw_username if raw_username and raw_username.lower() != 'не указан' else 'не указан'

        client_telegram_id = data.get('telegram_id')
        
        # Формируем красивую ссылку на Telegram аккаунт админу для быстрой связи
        if client_telegram_id:
            telegram_id_display = f"[{client_telegram_id}](tg://user?id={client_telegram_id})"
        else:
            telegram_id_display = 'не указан'

        message = f"""🆕 *НОВЫЙ ЗАКАЗ # {order_id}*

👤 *Клиент:* {data['user_name']} {data['user_surname']}
📱 *Telegram:* @{username_display}
🆔 *Telegram ID:* {telegram_id_display}

📦 *Тип:* {delivery_text}

🛒 *Состав заказа:*
{items_text}
💰 *Итого:* {data['total']} ₫

⏰ *Время:* {vn_now_str()}
"""

        target_chat = config.GROUP_CHAT_ID or config.ADMIN_CHAT_ID
        bot.send_message(target_chat, message, parse_mode="Markdown")

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("✅ Принять заказ", callback_data=f"status_{order_id}_accepted"))
        
        # Если есть telegram_id клиента, добавляем удобную кнопку связи прямо под заказом
        if client_telegram_id:
            markup.add(InlineKeyboardButton("💬 Написать клиенту", url=f"tg://user?id={client_telegram_id}"))

        bot.send_message(target_chat, f"Управление заказом #{order_id}:", reply_markup=markup)

        return jsonify({'success': True, 'order_id': order_id})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/menu', methods=['GET'])
def get_menu():
    menu = db.get_menu()
    stop_ids = db.get_stop_list_ids()
    for item in menu:
        item['stop_list'] = bool(int(item.get('stop_list', 0)) or int(item['id']) in stop_ids)

    known_ids = {int(item['id']) for item in menu}
    for item in db.get_stop_list():
        dish_id = int(item['dish_id'])
        if dish_id not in known_ids:
            menu.append({
                'id': dish_id,
                'name': item.get('name', ''),
                'price': item.get('price', 0),
                'category': item.get('category', ''),
                'stop_list': True
            })
    return jsonify(menu)


def normalize_id(value):
    return str(value or '').strip()

def is_admin_telegram_id(telegram_id):
    admin_id = normalize_id(config.ADMIN_CHAT_ID)
    current_id = normalize_id(telegram_id)
    return bool(admin_id and current_id and current_id == admin_id)


@app.route('/admin/check', methods=['GET', 'OPTIONS'])
def admin_check():
    if request.method == 'OPTIONS':
        return ('', 204)
    telegram_id = request.args.get('telegram_id', '')
    return jsonify({'is_admin': is_admin_telegram_id(telegram_id), 'telegram_id': telegram_id})


# ============ СИНХРОНИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ ============

@app.route('/user/sync', methods=['POST', 'OPTIONS'])
def user_sync():
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        data = request.json or {}
        telegram_id = str(data.get('telegram_id', '')).strip()
        if not telegram_id:
            return jsonify({'error': 'telegram_id required'}), 400

        db.upsert_user(
            telegram_id=telegram_id,
            username=data.get('username') or None,
            first_name=data.get('first_name') or None,
            last_name=data.get('last_name') or None,
            birth_date=data.get('birth_date') or None,
            gender=data.get('gender') or None
        )
        user = db.get_user(telegram_id)
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/stop-list', methods=['POST', 'OPTIONS'])
def admin_stop_list():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        data = request.json or {}
        telegram_id = data.get('telegram_id')
        dish_id = int(data.get('dish_id'))
        enabled = bool(data.get('enabled'))

        if not is_admin_telegram_id(telegram_id):
            return jsonify({'error': 'Нет прав'}), 403

        dish = db.get_dish_by_id(dish_id) or {
            'id': dish_id,
            'name': data.get('name', ''),
            'price': int(data.get('price', 0) or 0),
            'category': data.get('category', '')
        }
        db.set_stop_list(dish_id, enabled, dish)
        return jsonify({'success': True, 'dish_id': dish_id, 'stop_list': enabled})
    except (TypeError, ValueError):
        return jsonify({'error': 'Некорректный ID блюда'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/add-dish', methods=['POST', 'OPTIONS'])
def admin_add_dish():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        data = request.json or {}
        if not is_admin_telegram_id(data.get('telegram_id')):
            return jsonify({'error': 'Нет прав'}), 403

        name = str(data.get('name', '')).strip()
        category = str(data.get('category', '')).strip()
        ingredients = str(data.get('ingredients', '')).strip()
        description = str(data.get('description', '')).strip()
        price = int(data.get('price', 0) or 0)
        if not name or not category or price <= 0:
            return jsonify({'error': 'Название, категория и цена обязательны'}), 400

        dish_id = db.add_dish({
            'name': name, 'price': price, 'category': category,
            'ingredients': ingredients, 'description': description, 'is_popular': 0
        })
        dish = db.get_dish_by_id(dish_id)
        return jsonify({'success': True, 'dish': dish})
    except (TypeError, ValueError):
        return jsonify({'error': 'Цена должна быть числом'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/recommendations/<int:dish_id>', methods=['GET'])
def recommendations(dish_id):
    return jsonify(db.get_recommendations(dish_id, 3))


# ============ ИСТОРИЯ ЗАКАЗОВ КЛИЕНТА ============

@app.route('/orders/by-telegram/<telegram_id>', methods=['GET'])
def orders_by_telegram(telegram_id):
    orders = db.get_orders_by_telegram_id(telegram_id)
    return jsonify(orders)


# ============ СТАТУСЫ ЗАКАЗА (WORKFLOW) ============

STATUS_LABELS = {
    'new': '🆕 Новый',
    'accepted': '👨‍🍳 Принят, готовится',
    'ready': '✅ Готов к выдаче',
    'courier': '🚴 Курьер уже в пути',
    'completed': '📦 Выдан'
}

CLIENT_MESSAGES = {
    'accepted': "👨‍🍳 Ваш заказ #{id} принят и готовится!",
    'ready': "✅ Ваш заказ #{id} готов! Ждём вас за самовывозом.",
    'courier': "🚴 Ваш заказ #{id} передан курьеру — уже в пути к вам!",
    'completed': "📦 Заказ #{id} выдан. Спасибо, что выбрали Terassa!"
}

def next_status_markup(order_id, current_status, delivery_type):
    order = db.get_order_by_id(order_id)
    client_id = order.get('telegram_id') if order else None
    
    markup = InlineKeyboardMarkup(row_width=1)
    if current_status == 'new':
        markup.add(InlineKeyboardButton("✅ Принять заказ", callback_data=f"status_{order_id}_accepted"))
    elif current_status == 'accepted':
        if delivery_type == 'pickup':
            markup.add(InlineKeyboardButton("✅ Готов (уведомить гостя)", callback_data=f"status_{order_id}_ready"))
        else:
            markup.add(InlineKeyboardButton("🚴 Выдали курьеру", callback_data=f"status_{order_id}_courier"))
    elif current_status in ('ready', 'courier'):
        markup.add(InlineKeyboardButton("📦 Выдан", callback_data=f"status_{order_id}_completed"))
        
    # Дублируем кнопку связи для удобства на любом этапе
    if client_id:
        markup.add(InlineKeyboardButton("💬 Написать клиенту", url=f"tg://user?id={client_id}"))
        
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def handle_status_callback(call):
    try:
        _, order_id, new_status = call.data.split('_')
        order_id = int(order_id)
        order = db.get_order_by_id(order_id)
        if not order:
            bot.answer_callback_query(call.id, "❌ Заказ не найден")
            return

        db.update_order_status(order_id, new_status)

        label = STATUS_LABELS.get(new_status, new_status)
        bot.answer_callback_query(call.id, f"Статус заказа #{order_id}: {label}")
        bot.edit_message_text(
            f"Заказ #{order_id} — {label}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=next_status_markup(order_id, new_status, order.get('delivery_type', 'pickup'))
        )

        client_id = order.get('telegram_id')
        client_text = CLIENT_MESSAGES.get(new_status)
        if client_id and client_text:
            try:
                bot.send_message(int(client_id), client_text.format(id=order_id))
            except Exception as e:
                print(f"Не удалось уведомить клиента {client_id}: {e}")

    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")


# ============ ЗАПУСК ============

def run_bot():
    print("🤖 Бот запущен и слушает команды...")
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Не удалось сбросить webhook: {e}")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🌐 Flask сервер запущен на порту 5000")
    app.run(host='0.0.0.0', port=5000)
