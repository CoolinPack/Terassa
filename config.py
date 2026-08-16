import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', './terassa.db')
    
    # Static files
    IMAGES_FOLDER = 'static/images'
    UPLOAD_FOLDER = 'uploads'

config = Config()