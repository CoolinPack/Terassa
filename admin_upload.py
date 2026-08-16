import os
import shutil
from datetime import datetime
from config import config
from database import db
import telebot

class ImageUploader:
    def __init__(self, bot):
        self.bot = bot
        self.images_folder = config.IMAGES_FOLDER
        self.upload_folder = config.UPLOAD_FOLDER
        
        os.makedirs(self.images_folder, exist_ok=True)
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def save_image_from_telegram(self, file_id, dish_id):
        try:
            file_info = self.bot.get_file(file_id)
            downloaded_file = self.bot.download_file(file_info.file_path)
            
            filename = f"dish_{dish_id}.jpg"
            filepath = os.path.join(self.images_folder, filename)
            
            with open(filepath, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            db.update_dish_image(dish_id, f"static/images/{filename}")
            
            return True, f"static/images/{filename}"
        except Exception as e:
            return False, str(e)
    
    def save_image_from_local(self, source_path, dish_id):
        try:
            ext = os.path.splitext(source_path)[1]
            filename = f"dish_{dish_id}{ext}"
            dest_path = os.path.join(self.images_folder, filename)
            
            shutil.copy2(source_path, dest_path)
            
            db.update_dish_image(dish_id, f"static/images/{filename}")
            
            return True, f"static/images/{filename}"
        except Exception as e:
            return False, str(e)
    
    def get_dishes_without_images(self):
        menu = db.get_menu()
        return [d for d in menu if not d.get('image_path') or d['image_path'] == '']
    
    def get_all_dishes(self):
        return db.get_menu()