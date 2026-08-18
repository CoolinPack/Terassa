import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    # Telegram Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
    GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')  # группа "Заявки на доставку"

    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', './terassa.db')

    # Static files
    IMAGES_FOLDER = 'static/images'
    UPLOAD_FOLDER = 'uploads'

config = Config()
