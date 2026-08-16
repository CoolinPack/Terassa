import sqlite3
import json
from datetime import datetime
from config import config

class Database:
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                user_surname TEXT NOT NULL,
                user_phone TEXT NOT NULL,
                user_birth_year TEXT,
                items TEXT NOT NULL,
                total INTEGER NOT NULL,
                delivery_type TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL
            )
        ''')
        
        # Таблица меню
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                category TEXT NOT NULL,
                ingredients TEXT,
                description TEXT,
                image_path TEXT,
                is_popular INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_order(self, order_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO orders 
            (user_name, user_surname, user_phone, user_birth_year, 
             items, total, delivery_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['user_name'],
            order_data['user_surname'],
            order_data['user_phone'],
            order_data.get('user_birth_year', ''),
            json.dumps(order_data['items'], ensure_ascii=False),
            order_data['total'],
            order_data['delivery_type'],
            datetime.now().strftime('%d.%m.%Y %H:%M')
        ))
        
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return order_id
    
    def get_orders(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM orders 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders
    
    def update_order_status(self, order_id, status):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE orders 
            SET status = ? 
            WHERE id = ?
        ''', (status, order_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_order_by_id(self, order_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        conn.close()
        return dict(order) if order else None
    
    def get_menu(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM menu ORDER BY category, id')
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    
    def get_dish_by_id(self, dish_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM menu WHERE id = ?', (dish_id,))
        dish = cursor.fetchone()
        conn.close()
        return dict(dish) if dish else None
    
    def update_dish_image(self, dish_id, image_path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE menu 
            SET image_path = ? 
            WHERE id = ?
        ''', (image_path, dish_id))
        
        conn.commit()
        conn.close()
        return True
    
    def add_dish(self, dish_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO menu 
            (name, price, category, ingredients, description, image_path, is_popular, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dish_data['name'],
            dish_data['price'],
            dish_data['category'],
            dish_data.get('ingredients', ''),
            dish_data.get('description', ''),
            dish_data.get('image_path', ''),
            dish_data.get('is_popular', 0),
            datetime.now().strftime('%d.%m.%Y %H:%M')
        ))
        
        dish_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return dish_id
    
    def delete_dish(self, dish_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM menu WHERE id = ?', (dish_id,))
        conn.commit()
        conn.close()
        return True

db = Database()