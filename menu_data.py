from database import db

# Начальные данные меню
MENU_DATA = [
    {
        "name": "Цезарь с креветками",
        "price": 890,
        "category": "Салаты",
        "ingredients": "креветки, салат айсберг, пармезан, соус цезарь",
        "description": "Классический цезарь с тигровыми креветками",
        "image_path": "static/images/dish_1.jpg",
        "is_popular": 1
    },
    {
        "name": "Стейк рибай",
        "price": 2150,
        "category": "Горячее",
        "ingredients": "говядина рибай, соль, перец, розмарин",
        "description": "Мраморный стейк рибай на гриле",
        "image_path": "static/images/dish_2.jpg",
        "is_popular": 1
    },
    {
        "name": "Паста карбонара",
        "price": 750,
        "category": "Горячее",
        "ingredients": "спагетти, бекон, яйцо, пармезан",
        "description": "Классическая итальянская паста",
        "image_path": "static/images/dish_3.jpg",
        "is_popular": 0
    },
    {
        "name": "Греческий салат",
        "price": 590,
        "category": "Салаты",
        "ingredients": "помидоры, огурцы, фета, оливки",
        "description": "Свежий греческий салат с сыром фета",
        "image_path": "static/images/dish_4.jpg",
        "is_popular": 0
    },
    {
        "name": "Тирамису",
        "price": 450,
        "category": "Десерты",
        "ingredients": "савоярди, маскарпоне, кофе, какао",
        "description": "Классический итальянский десерт",
        "image_path": "static/images/dish_5.jpg",
        "is_popular": 1
    },
    {
        "name": "Лимонный тарт",
        "price": 420,
        "category": "Десерты",
        "ingredients": "песочное тесто, лимонный курд, меренга",
        "description": "Нежный лимонный тарт с безе",
        "image_path": "static/images/dish_6.jpg",
        "is_popular": 0
    },
    {
        "name": "Лосось на гриле",
        "price": 1250,
        "category": "Горячее",
        "ingredients": "лосось, лимон, укроп, оливковое масло",
        "description": "Стейк лосося с овощами гриль",
        "image_path": "static/images/dish_7.jpg",
        "is_popular": 0
    },
    {
        "name": "Ризотто с грибами",
        "price": 680,
        "category": "Горячее",
        "ingredients": "рис арборио, белые грибы, пармезан",
        "description": "Кремовое ризотто с лесными грибами",
        "image_path": "static/images/dish_8.jpg",
        "is_popular": 0
    },
    {
        "name": "Капучино",
        "price": 220,
        "category": "Напитки",
        "ingredients": "эспрессо, молоко, пена",
        "description": "Нежный капучино",
        "image_path": "static/images/dish_9.jpg",
        "is_popular": 0
    },
    {
        "name": "Лимонад",
        "price": 250,
        "category": "Напитки",
        "ingredients": "лимон, лайм, мята, сахарный сироп",
        "description": "Освежающий домашний лимонад",
        "image_path": "static/images/dish_10.jpg",
        "is_popular": 0
    }
]

def init_menu():
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM menu')
    count = cursor.fetchone()[0]
    
    if count == 0:
        for item in MENU_DATA:
            cursor.execute('''
                INSERT INTO menu 
                (name, price, category, ingredients, description, image_path, is_popular, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                item['name'],
                item['price'],
                item['category'],
                item['ingredients'],
                item['description'],
                item['image_path'],
                item['is_popular']
            ))
        conn.commit()
        print("✅ Меню инициализировано")
    else:
        print(f"ℹ️ Меню уже существует ({count} блюд)")
    
    conn.close()

def get_menu_json():
    menu = db.get_menu()
    for item in menu:
        if item.get('ingredients'):
            item['ingredients_list'] = item['ingredients'].split(', ')
    return menu

if __name__ == "__main__":
    init_menu()