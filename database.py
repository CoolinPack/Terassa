import sqlite3
import json
from datetime import datetime
from config import config


class Database:
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self.init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                user_surname TEXT NOT NULL,
                user_phone TEXT DEFAULT '',
                user_birth_year TEXT,
                telegram_username TEXT,
                telegram_id TEXT,
                items TEXT NOT NULL,
                total INTEGER NOT NULL,
                delivery_type TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL
            )
        ''')

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
                stop_list INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')

        # Отдельная таблица позволяет стоп-листу работать и для блюд,
        # которые пока отображаются из статического MENU в index.html.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_stop_list (
                dish_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                name TEXT,
                price INTEGER,
                category TEXT,
                updated_at TEXT NOT NULL
            )
        ''')

        # Безопасная миграция старой базы: существующие данные не удаляются.
        self._add_column_if_missing(cursor, 'orders', 'telegram_username', 'TEXT')
        self._add_column_if_missing(cursor, 'orders', 'telegram_id', 'TEXT')
        self._add_column_if_missing(cursor, 'orders', 'user_phone', "TEXT DEFAULT ''")
        self._add_column_if_missing(cursor, 'menu', 'stop_list', 'INTEGER DEFAULT 0')

        conn.commit()
        conn.close()

    @staticmethod
    def _add_column_if_missing(cursor, table, column, definition):
        columns = [row[1] for row in cursor.execute(f'PRAGMA table_info({table})').fetchall()]
        if column not in columns:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

    def save_order(self, order_data):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders
            (user_name, user_surname, user_phone, user_birth_year,
             telegram_username, telegram_id, items, total, delivery_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['user_name'],
            order_data['user_surname'],
            order_data.get('user_phone', ''),
            order_data.get('user_birth_year', ''),
            order_data.get('username') or order_data.get('telegram_username', ''),
            str(order_data.get('telegram_id', '')),
            json.dumps(order_data['items'], ensure_ascii=False),
            int(order_data['total']),
            order_data['delivery_type'],
            datetime.now().strftime('%d.%m.%Y %H:%M')
        ))

        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return order_id

    def get_orders(self, limit=10):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders ORDER BY id DESC LIMIT ?', (limit,))
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders

    def update_order_status(self, order_id, status):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        conn.close()
        return True

    def get_order_by_id(self, order_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        conn.close()
        return dict(order) if order else None

    def get_menu(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM menu ORDER BY category, id')
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def get_dish_by_id(self, dish_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM menu WHERE id = ?', (dish_id,))
        dish = cursor.fetchone()
        conn.close()
        return dict(dish) if dish else None

    def get_category_dishes(self, category):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM menu WHERE category = ? ORDER BY id', (category,))
        dishes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return dishes

    def set_stop_list(self, dish_id, enabled, dish_data=None):
        dish = dish_data or self.get_dish_by_id(dish_id) or {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime('%d.%m.%Y %H:%M')

        cursor.execute('''
            INSERT INTO menu_stop_list (dish_id, enabled, name, price, category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dish_id) DO UPDATE SET
                enabled = excluded.enabled,
                name = excluded.name,
                price = excluded.price,
                category = excluded.category,
                updated_at = excluded.updated_at
        ''', (
            dish_id,
            1 if enabled else 0,
            dish.get('name', ''),
            dish.get('price', 0),
            dish.get('category', ''),
            now
        ))

        # Если блюдо существует в основной таблице меню, синхронизируем и её.
        cursor.execute('UPDATE menu SET stop_list = ? WHERE id = ?', (1 if enabled else 0, dish_id))
        conn.commit()
        conn.close()
        return True

    def get_stop_list_ids(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT dish_id FROM menu_stop_list WHERE enabled = 1')
        ids = [int(row[0]) for row in cursor.fetchall()]
        # Старые записи из menu тоже учитываем.
        cursor.execute('SELECT id FROM menu WHERE stop_list = 1')
        ids.extend(int(row[0]) for row in cursor.fetchall())
        conn.close()
        return sorted(set(ids))

    def get_stop_list(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM menu_stop_list WHERE enabled = 1 ORDER BY category, dish_id')
        result = [dict(row) for row in cursor.fetchall()]
        cursor.execute('SELECT * FROM menu WHERE stop_list = 1 ORDER BY category, id')
        for row in cursor.fetchall():
            item = dict(row)
            if not any(int(x.get('dish_id', -1)) == int(item['id']) for x in result):
                result.append({
                    'dish_id': item['id'],
                    'enabled': 1,
                    'name': item['name'],
                    'price': item['price'],
                    'category': item['category'],
                    'updated_at': item.get('created_at', '')
                })
        conn.close()
        return result

    def get_recommendations(self, dish_id, limit=3):
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return []

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM menu
            WHERE id != ? AND stop_list = 0
            ORDER BY
                CASE WHEN category = ? THEN 0 ELSE 1 END,
                CASE WHEN is_popular = 1 THEN 0 ELSE 1 END,
                id
            LIMIT ?
        ''', (dish_id, dish['category'], limit))
        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return result

    def update_dish_image(self, dish_id, image_path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE menu SET image_path = ? WHERE id = ?',
            (image_path, dish_id)
        )
        conn.commit()
        conn.close()
        return True

    def add_dish(self, dish_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO menu
            (name, price, category, ingredients, description, image_path,
             is_popular, stop_list, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dish_data['name'],
            dish_data['price'],
            dish_data['category'],
            dish_data.get('ingredients', ''),
            dish_data.get('description', ''),
            dish_data.get('image_path', ''),
            dish_data.get('is_popular', 0),
            dish_data.get('stop_list', 0),
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
