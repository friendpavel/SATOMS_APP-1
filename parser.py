import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import logging
import json
import re
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive'
}

def clean_price(price_str):
    """Очистка строки цены от пробелов, символа рубля и конвертация в число"""
    if price_str and price_str != 'N/A':
        return price_str.replace(' ', '').replace('₽', '').replace(',', '.').strip()
    return price_str

def get_all_categories(soup):
    """Получение всех категорий из каталога"""
    categories = []
    catalog_items = soup.find_all('a', class_='catalog-item__name')
    for item in catalog_items:
        if 'href' in item.attrs:
            category_url = f"https://platferrum.ru{item['href']}"
            category_name = item.text.strip()
            categories.append((category_url, category_name))
            logging.info(f'Найдена категория: {category_name} - {category_url}')
    return categories

def get_total_pages(json_data):
    """Получение общего количества страниц и общего количества товаров из JSON"""
    try:
        # Детальный путь к ROOT_QUERY и catalog
        default_data = json_data.get('runtimeConfig', {}).get('apollo', {}).get('default', {})
        root_query = default_data.get('ROOT_QUERY', {})
        
        # Ищем объект catalog среди ключей ROOT_QUERY
        catalog_data = None
        for key, value in root_query.items():
            if isinstance(value, dict) and 'last_page' in value:
                catalog_data = value
                break
        
        if not catalog_data:
            logging.warning('Не найден объект catalog с параметрами пагинации')
            return 1, 0
            
        # Получаем количество страниц и общее количество товаров
        last_page = catalog_data.get('last_page')
        total_items = catalog_data.get('total')
        per_page = catalog_data.get('per_page')
        
        if last_page is not None:
            logging.info(f'Найдено - страниц: {last_page}, товаров всего: {total_items}, товаров на странице: {per_page}')
            return int(last_page), int(total_items or 0)
            
        logging.warning('Не найден параметр last_page в данных каталога')
        return 1, 0
        
    except Exception as e:
        logging.error(f'Ошибка при получении параметров пагинации: {e}')
        return 1, 0

def fetch_data_from_all_categories():
    """Сбор данных со всех категорий каталога"""
    base_url = 'https://platferrum.ru/catalog'
    all_data = []
    seen_names = set()
    
    try:
        # Получаем начальную страницу
        response = requests.get(base_url, headers=HEADERS)
        if response.status_code != 200:
            logging.error(f'Ошибка получения страницы каталога: {response.status_code}')
            return all_data
            
        soup = BeautifulSoup(response.content, 'html.parser')
        categories = get_all_categories(soup)
        
        for category_url, category_name in categories:
            processed_items = 0
            logging.info(f'Обработка категории: {category_name}')
            page = 1
            
            # Получаем первую страницу категории для определения общего количества страниц и товаров
            first_page_url = f"{category_url}?region-delivery=36&pageSize=30&page=1"
            response = requests.get(first_page_url, headers=HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                script_tag = soup.find('script', text=re.compile('window.__APP_STATE__'))
                
                if not script_tag:
                    logging.warning(f'Не найден APP_STATE для категории {category_name}')
                    continue
                
                json_str = script_tag.string.split('window.__APP_STATE__ = ')[1].strip()
                json_data = json.loads(json_str)
                total_pages, total_items = get_total_pages(json_data)
                logging.info(f'Категория {category_name}: страниц - {total_pages}, товаров - {total_items}')
            else:
                logging.error(f'Ошибка получения первой страницы категории: {response.status_code}')
                continue
            
            while page <= total_pages:
                url = f"{category_url}?region-delivery=36&pageSize=30&page={page}"
                try:
                    response = requests.get(url, headers=HEADERS)
                    if response.status_code != 200:
                        logging.error(f'Ошибка получения страницы {url}: {response.status_code}')
                        break
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    script_tag = soup.find('script', text=re.compile('window.__APP_STATE__'))
                    
                    if not script_tag:
                        logging.warning(f'Не найден APP_STATE для категории {category_name}')
                        break
                    
                    json_str = script_tag.string.split('window.__APP_STATE__ = ')[1].strip()
                    json_data = json.loads(json_str)
                    
                    # Получаем актуальное количество страниц из JSON
                    if page == 1:
                        total_pages, total_items = get_total_pages(json_data)
                        logging.info(f'Всего страниц в категории {category_name}: {total_pages}')
                    
                    # Обработка товаров на странице
                    catalog_items = json_data.get('runtimeConfig', {}).get('apollo', {}).get('default', {})
                    items_processed = False
                    
                    # Обновляем счетчик обработанных товаров
                    items_on_page = 0
                    for key, value in catalog_items.items():
                        if isinstance(value, dict) and key.startswith('CatalogItem:'):
                            try:
                                name = value.get('name')
                                if not name or name in seen_names:
                                    continue
                                
                                seen_names.add(name)
                                
                                # Получаем все возможные цены
                                regions = value.get('regions', {})
                                regions_data = regions.get('data', [])
                                
                                # Инициализация цен значением по умолчанию
                                unit_price = 'N/A'
                                min_price = 'N/A'
                                max_price = 'N/A'
                                
                                # Получаем цену из первого предложения
                                if regions_data and regions_data[0].get('offers'):
                                    first_offer = regions_data[0]['offers'][0]
                                    unit_price = first_offer.get('storesMinPrice')
                                    
                                # Получаем мин/макс цены из объекта
                                try:
                                    min_price = float(value.get('minPrice', 0))
                                    min_price = round(min_price, 2) if min_price != 0 else 'N/A'
                                except (ValueError, TypeError):
                                    min_price = 'N/A'
                                    
                                try:
                                    max_price = float(value.get('maxPrice', 0))
                                    max_price = round(max_price, 2) if max_price != 0 else 'N/A'
                                except (ValueError, TypeError):
                                    max_price = 'N/A'
                                
                                # Если есть unit_price, преобразуем его в число и округляем
                                if unit_price != 'N/A':
                                    try:
                                        unit_price = round(float(unit_price), 2)
                                    except (ValueError, TypeError):
                                        unit_price = 'N/A'
                                
                                # Логика замены значений
                                if unit_price == 'N/A' and min_price != 'N/A':
                                    unit_price = min_price
                                elif unit_price != 'N/A' and min_price == 'N/A' and max_price == 'N/A':
                                    min_price = unit_price
                                    max_price = unit_price
                                
                                selected_unit = regions.get('selectedUnit', {})
                                sign_nat = selected_unit.get('signNat', 'N/A')
                                
                                all_data.append((
                                    name,
                                    'platferrum',
                                    str(unit_price),
                                    min_price,
                                    max_price,
                                    sign_nat,
                                    datetime.now().date()
                                ))
                                items_processed = True
                                items_on_page += 1
                                processed_items += 1
                                logging.info(f'Добавлены данные: {name} - {unit_price} {sign_nat}')
                                
                            except Exception as e:
                                logging.error(f'Ошибка при обработке элемента в категории {category_name}: {e}')
                    
                    if not items_processed:
                        logging.warning(f'Нет товаров на странице {page} в категории {category_name}')
                        break
                    
                    logging.info(f'Обработана страница {page} из {total_pages}. Товаров на странице: {items_on_page}')
                    logging.info(f'Всего обработано товаров в категории: {processed_items} из {total_items}')
                    
                    if processed_items >= total_items:
                        logging.info(f'Обработаны все товары категории {category_name}')
                        break
                    
                    page += 1
                    time.sleep(2)  # Увеличиваем задержку между запросами
                    
                except Exception as e:
                    logging.error(f'Ошибка при обработке страницы {page} категории {category_name}: {e}')
                    break
                
    except Exception as e:
        logging.error(f'Ошибка при сборе данных: {e}')
    
    logging.info(f'Всего собрано уникальных товаров: {len(all_data)}')
    return all_data

# Функция для сохранения данных в базу данных
def store_data(data):
    conn = sqlite3.connect('platferrum.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            unit_price TEXT,
            min_price REAL,
            max_price REAL,
            sign_nat TEXT,
            date TIMESTAMP
        )
    ''')
    cursor.executemany('''
        INSERT INTO prices (name, type, unit_price, min_price, max_price, sign_nat, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()

def data_exists_for_today():
    """Проверяет, есть ли данные за сегодняшнюю дату в БД"""
    conn = sqlite3.connect('platferrum.db')
    cursor = conn.cursor()
    # Гарантируем, что таблица существует
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            unit_price TEXT,
            min_price REAL,
            max_price REAL,
            sign_nat TEXT,
            date TIMESTAMP
        )
    ''')
    today = datetime.now().date()
    cursor.execute("SELECT 1 FROM prices WHERE date = ?", (today,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# Основная функция для запуска парсера
def main():
    if data_exists_for_today():
        print("Данные за сегодня уже есть в базе. Парсинг не требуется.")
        return
    data = fetch_data_from_all_categories()
    print(f"Всего уникальных товаров: {len(data)}")
    store_data(data)

if __name__ == '__main__':
    import time
    from datetime import datetime, timedelta

    def wait_until_next_8am():
        now = datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"Ожидание до следующего запуска парсинга: {int(wait_seconds)} секунд или {int(wait_seconds / 60)} минут")
        print(f"Следующий запуск парсинга в {target.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(wait_seconds)

    # Сначала проверяем, есть ли данные за сегодня
    if not data_exists_for_today():
        main()
    # Далее всегда ждем до 8:00 следующего дня и запускаем парсер
    while True:
        wait_until_next_8am()
        main()
