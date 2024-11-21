import requests
import time
import jwt  # Импортируем библиотеку для работы с JWT

MOBILE_URL = 'http://0.0.0.0:8002'
client = {"name": "Иван Иванов", "experience": 1}

# Функция для генерации JWT-токена
def generate_jwt_token(client_id, secret_key):
    payload = {
        'client_id': client_id,
        'exp': time.time() + 3600  # Токен действителен в течение 1 часа
    }
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token

# Тест базового сценария поездки клиента от аренды до завершения поездки
def test_full_func():
    secret_key = 'your_secret_key'  # Замените на ваш секретный ключ
    client_id = 1  # Замените на реальный client_id, если он у вас есть

    # Генерируем JWT-токен
    token = generate_jwt_token(client_id, secret_key)

    # Добавляем токен в заголовки запросов
    headers = {
        'Authorization': f'Bearer {token}'
    }

    prepayment = requests.post(f'{MOBILE_URL}/cars', json=client, headers=headers)
    time.sleep(2)
    response = requests.post(f'{MOBILE_URL}/prepayment', json=prepayment.json(), headers=headers)
    time.sleep(2)
    car = requests.post(f'{MOBILE_URL}/start_drive', json=client, headers=headers)
    time.sleep(5)  # Сколько времени будет длиться поездка
    invoice = requests.post(f'{MOBILE_URL}/stop_drive', json=client, headers=headers)
    time.sleep(2)
    response = requests.post(f'{MOBILE_URL}/final_pay', json=invoice.json(), headers=headers)
    time.sleep(2)
    assert response.status_code == 200
    data = response.json()
    assert 'car' in data
    assert 'created_at' in data
    assert 'elapsed_time' in data
    assert 'name' in data
    assert 'final_amount' in data
    assert 'tarif' in data

# Запуск теста
test_full_func()