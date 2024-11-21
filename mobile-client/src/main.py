import requests
import random
import time
import os
from flask import Flask, jsonify, request
import threading
from werkzeug.exceptions import HTTPException
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity

HOST = '0.0.0.0'
PORT = 8000
MODULE_NAME = os.getenv('MODULE_NAME')

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'ASDFASDF45454534534AADsa'  # Замените на свой секретный ключ
jwt = JWTManager(app)

MANAGMENT_URL = 'http://com-mobile:6066'
PAYMENT_URL = 'http://payment_system:8000'
CARS_URL = 'http://cars:8000'
flag = True

data = {
    'user1': 'password1',
    'user2': 'password2',
    'user3': 'password3',
    'user4': 'password4'
}

@app.route('/login', methods=['POST'])
def login():
    """
    Аутентификация пользователя и генерация JWT-токена.

    Метод: POST
    URL: /login
    Тело запроса:
    {
        "username": "user1",
        "password": "password1"
    }

    Возвращает:
    - JWT-токен в случае успешной аутентификации.
    - Сообщение об ошибке в случае неверных учетных данных.
    """
    data_request = request.json
    username = data_request.get('username')
    password = data_request.get('password')

    # Проверка пользователя и пароля
    if username in data and data[username] == password:
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token)
    else:
        return jsonify({"error": "Неверные учетные данные"}), 401

@app.route('/cars', methods=['POST'])
@jwt_required()
def get_cars():
    """
    Выбор и запрос авто (автоматически выбирает из свободных машин и выбирает тариф).

    Метод: POST
    URL: /cars
    Тело запроса:
    {
        "name": "Иван Иванов",
        "experience": 1
    }

    Возвращает:
    - Информация о предоплате.
    """
    data = request.json
    name = data.get('name')
    experience = data.get('experience')
    cars = get_car()
    while len(cars) == 0:
        cars = get_car()
        time.sleep(1)
    tariff = get_tariff()
    selected_auto = cars[random.randint(0, len(cars)-1)]
    selected_tariff = tariff[random.randint(0, len(tariff)-1)]
    print(f"Выбранный автомобиль {selected_auto} и тариф {selected_tariff}")
    prepayment = select_auto_and_prepayment(name, experience, selected_auto, selected_tariff)

    return jsonify(prepayment)

@app.route('/start_drive', methods=['POST'])
@jwt_required()
def start_drive():
    """
    Начало поездки.

    Метод: POST
    URL: /start_drive
    Тело запроса:
    {
        "name": "Иван Иванов"
    }

    Возвращает:
    - Сообщение о начале поездки.
    - Сообщение об ошибке, если доступ не разрешен.
    """
    data = request.json
    name = data.get('name')
    client_access = access(name)
    if client_access['access']:
        response = start_travel(client_access['car'])
        return jsonify(response)
    else:
        return jsonify({"error": "Доступ на данную операцию не разрешён"}), 404

@app.route('/stop_drive', methods=['POST'])
@jwt_required()
def stop_drive():
    """
    Остановка поездки.

    Метод: POST
    URL: /stop_drive
    Тело запроса:
    {
        "name": "Иван Иванов"
    }

    Возвращает:
    - Информация о поездке.
    - Сообщение об ошибке, если доступ не разрешен.
    """
    global data
    global flag
    data1 = request.json
    name = data1.get('name')
    client_access = access(name)
    if client_access['access']:
        stop_travel(client_access['car'])
        while flag:
            time.sleep(1)
        flag = True
        return jsonify(data)
    else:
        return jsonify({"error": "Доступ на данную операцию не разрешён"}), 404

@app.route('/prepayment', methods=['POST'])
@jwt_required()
def prepayment():
    """
    Подтверждение предоплаты.

    Метод: POST
    URL: /prepayment
    Тело запроса:
    {
        "id": "prepayment_id"
    }

    Возвращает:
    - Информация о предоплате.
    - Сообщение об ошибке, если предоплата не подтверждена.
    """
    data = request.json
    prepayment_id = data.get('id')
    prepayment = confirm_prepayment(prepayment_id)
    if prepayment.status_code == 200:
        return jsonify(prepayment.json())
    else:
        return jsonify(prepayment.json()), 404

@app.route('/final_pay', methods=['POST'])
@jwt_required()
def final_pay():
    """
    Финальная оплата.

    Метод: POST
    URL: /final_pay
    Тело запроса:
    {
        "id": "invoice_id"
    }

    Возвращает:
    - Информация о финальной оплате.
    - Сообщение об ошибке, если оплата не подтверждена.
    """
    global data
    data1 = request.json
    invoice_id = data1.get('id')
    response = confirm_payment(invoice_id)
    if response.status_code == 200:
        while flag:
            time.sleep(1)
        return jsonify(data)
    else:
        return jsonify(None), 404

@app.route('/payment', methods=['POST'])
@jwt_required()
def payment():
    """
    Реализация ответа платежа.

    Метод: POST
    URL: /payment
    Тело запроса:
    {
        "data": "payment_data"
    }

    Возвращает:
    - Сообщение "ok".
    """
    global data
    global flag
    data = request.json
    flag = False
    return jsonify("ok")

@app.route('/final', methods=['POST'])
@jwt_required()
def final():
    """
    Реализация ответа финального платежа.

    Метод: POST
    URL: /final
    Тело запроса:
    {
        "data": "final_payment_data"
    }

    Возвращает:
    - Сообщение "ok".
    """
    global data
    global flag
    data = request.json
    flag = False
    return jsonify("ok")

def get_car():
    """
    Получение информации о доступных автомобилях.

    Возвращает:
    - Список доступных автомобилей.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.get(f'{MANAGMENT_URL}/cars')
        assert response.status_code == 200, "Ошибка при получении доступных автомобилей"
        print("Информация о доступных автомобилях:", response.json())
        return response.json()
    except Exception as e:
        print("Ошибка при получении доступных автомобилей:", e)
        return []

def get_tariff():
    """
    Получение информации о доступных тарифах.

    Возвращает:
    - Список доступных тарифов.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.get(f'{MANAGMENT_URL}/tariff')
        assert response.status_code == 200, "Ошибка при получении доступных тарифов"
        print("Информация о доступных тарифах:", response.json())
        return response.json()
    except Exception as e:
        print("Ошибка при получении доступных тарифов:", e)
        return []

def select_auto_and_prepayment(name, experience, brand, tariff):
    """
    Выбор автомобиля и предоплата.

    Аргументы:
    - name: Имя клиента.
    - experience: Опыт клиента.
    - brand: Марка автомобиля.
    - tariff: Тариф.

    Возвращает:
    - Информация о предоплате.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{MANAGMENT_URL}/select/car/{brand}', json={'client_name': name, 'experience': experience, 'tariff': tariff})
        assert response.status_code == 200, "Ошибка при выборе автомобиля и предоплате"
        print("Информация о предоплате:", response.json())
        return response.json()
    except Exception as e:
        print("Ошибка при выборе автомобиля и предоплате:", e)
        return {}

def confirm_prepayment(prepayment_id):
    """
    Подтверждение предоплаты.

    Аргументы:
    - prepayment_id: Идентификатор предоплаты.

    Возвращает:
    - Ответ сервера.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{PAYMENT_URL}/prepayment/{prepayment_id}/confirm')
        assert response.status_code == 200, "Ошибка при подтверждении предоплаты"
        print("Предоплата подтверждена:", response.json())
        return response
    except Exception as e:
        print("Ошибка при подтверждении предоплаты:", e)
        return response

def confirm_payment(invoice_id: int):
    """
    Подтверждение оплаты.

    Аргументы:
    - invoice_id: Идентификатор счета.

    Возвращает:
    - Ответ сервера.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{PAYMENT_URL}/invoices/{invoice_id}/confirm')
        assert response.status_code == 200, "Ошибка при подтверждении оплаты"
        print("Оплата потверждена:", response.json())
        return response
    except Exception as e:
        print("Ошибка при подтверждении оплаты:", e)
        return response

def access(name):
    """
    Проверка доступа к операции.

    Аргументы:
    - name: Имя клиента.

    Возвращает:
    - Информация о доступе.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{CARS_URL}/car/occupy/{name}')
        assert response.status_code == 200, "Ошибка при проверке доступа"
        print(response.json()['message'])
        return response.json()
    except Exception as e:
        print("Ошибка при проверке доступа:", e)
        return response.json()

def start_travel(brand):
    """
    Начало поездки.

    Аргументы:
    - brand: Марка автомобиля.

    Возвращает:
    - Информация о начале поездки.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{CARS_URL}/car/start/{brand}')
        assert response.status_code == 200, "Ошибка при начале поездки"
        print(response.json()['message'])
        return response.json()
    except Exception as e:
        print("Ошибка при начале поездки:", e)
        return response.json()

def stop_travel(brand):
    """
    Остановка поездки.

    Аргументы:
    - brand: Марка автомобиля.

    Возвращает:
    - Информация об остановке поездки.
    - Сообщение об ошибке, если запрос не удался.
    """
    try:
        response = requests.post(f'{CARS_URL}/car/stop/{brand}')
        assert response.status_code == 200, "Ошибка при остановке поездки"
        print(response.json()['message'])
        return response.json()
    except Exception as e:
        print("Ошибка при остановке поездки:", e)
        return response.json()

@app.errorhandler(HTTPException)
def handle_exception(e):
    """
    Обработка ошибок HTTP.

    Аргументы:
    - e: Исключение HTTP.

    Возвращает:
    - JSON с информацией об ошибке.
    """
    response = e.get_response()
    return jsonify({
        "status": e.code,
        "name": e.name,
    }), e.code

def start_web():
    """
    Запуск веб-сервера в отдельном потоке.
    """
    threading.Thread(target=lambda: app.run(
        host=HOST, port=PORT, debug=True, use_reloader=False
    )).start()
