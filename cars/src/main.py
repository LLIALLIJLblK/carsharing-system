from flask import Flask, jsonify, request
from pathlib import Path
import json
import random
import time
import requests
import os
import threading
from werkzeug.exceptions import HTTPException

MANAGMENT_URL = 'http://receiver-car:6070'

HOST = '0.0.0.0'
PORT = 8000
MODULE_NAME = os.getenv('MODULE_NAME')
app = Flask(__name__)

data = None
flag = True


class Car:
    """
    Класс, представляющий автомобиль.

    Атрибуты:
    - brand (str): Марка автомобиля.
    - has_air_conditioner (bool): Наличие кондиционера.
    - has_heater (bool): Наличие обогревателя.
    - has_navigator (bool): Наличие навигатора.
    """
    def __init__(self, brand, has_air_conditioner=False, has_heater=False, has_navigator=False):
        self.speed = 0
        self.coordinates = (0, 0)
        self.occupied_by = None
        self.start_time = None
        self.brand = brand
        self.has_air_conditioner = has_air_conditioner
        self.has_heater = has_heater
        self.has_navigator = has_navigator
        self.is_running = False
        self.tariff = None

    def start(self):
        """
        Запускает поездку автомобиля.

        Возвращает:
        - str: Сообщение о начале поездки.
        """
        if not self.is_running:
            self.is_running = True
            self.start_time = time.time()
            return f"{self.brand} поездка началась."
        else:
            return f"{self.brand} поездка ещё идет."

    def stop(self):
        """
        Останавливает поездку автомобиля.

        Возвращает:
        - str: Сообщение о завершении поездки.
        """
        if self.is_running:
            self.is_running = False
            self.speed = 0
            self.occupied_by = None
            return f"{self.brand} поездка завершена."
        else:
            return f"{self.brand} на парковке."

    def get_status(self):
        """
        Возвращает текущий статус автомобиля.

        Возвращает:
        - dict: Словарь с информацией о статусе автомобиля.
        """
        elapsed_time = 0
        if self.start_time is not None and self.is_running:
            elapsed_time = round(time.time() - self.start_time, 2)  # Время в секундах
        return {
            "brand": self.brand,
            "is_running": self.is_running,
            "speed": self.speed,
            "coordinates": self.coordinates,
            "occupied_by": self.occupied_by,
            "trip_time": elapsed_time,
            "has_air_conditioner": self.has_air_conditioner,
            "has_heater": self.has_heater,
            "has_navigator": self.has_navigator,
            "tariff ": self.tariff
        }

    def update_coordinates(self, x, y):
        """
        Обновляет координаты автомобиля.

        Аргументы:
        - x (float): Новая координата по оси X.
        - y (float): Новая координата по оси Y.
        """
        self.coordinates = (x, y)

    def set_speed(self, speed):
        """
        Устанавливает скорость автомобиля.

        Аргументы:
        - speed (int): Новая скорость автомобиля.

        Возвращает:
        - str: Сообщение об изменении скорости.
        """
        if self.is_running:
            self.speed = speed
            return f"Скорость {self.brand} изменена на {self.speed} км/ч."
        else:
            return f"{self.brand} не парковке, скорость не может быть изменена."

    def occupy(self, person, tarif):
        """
        Арендует автомобиль указанным клиентом.

        Аргументы:
        - person (str): Имя клиента.
        - tarif (str): Тариф аренды.

        Возвращает:
        - str: Сообщение об аренде автомобиля.
        """
        self.occupied_by = person
        self.tariff = tarif
        return f"{self.brand} арендован {self.occupied_by}."


def simulate_drive(car):
    """
    Симулирует движение автомобиля.

    Аргументы:
    - car (Car): Объект автомобиля.
    """
    try:
        while car.is_running:
            new_speed = random.randint(10, 100)
            car.set_speed(new_speed)

            x_change = random.uniform(-2, 2)
            y_change = random.uniform(-2, 2)
            current_coordinates = car.coordinates
            new_coordinates = (current_coordinates[0] + x_change, current_coordinates[1] + y_change)
            car.update_coordinates(*new_coordinates)

            print(f"{car.brand} Скорость: {car.speed:.2f} км/ч, Координаты: {car.coordinates}")
            status = car.get_status()
            requests.post(f'{MANAGMENT_URL}/telemetry/{car.brand}', json={'status': status})
            time.sleep(1)
    except Exception as e:
        print(f"Ошибка при симуляции движения: {e}")


def load_cars_from_json(file_path):
    """
    Загружает список автомобилей из JSON файла.

    Аргументы:
    - file_path (str): Путь к JSON файлу.

    Возвращает:
    - list: Список объектов Car.
    """
    try:
        with open(file_path, 'r') as file:
            cars_data = json.load(file)
            return [Car(**car) for car in cars_data]
    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
        return []
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON в файле {file_path}.")
        return []


BASE_DIR = Path(__file__).resolve().parent.parent
# Загружаем список автомобилей из файла
cars = load_cars_from_json(f'{BASE_DIR}/data/cars.json')


@app.route('/car/status/all', methods=['GET'])
def get_all_car_statuses():
    """
    Возвращает статусы всех автомобилей.

    Возвращает:
    - JSON: Список статусов всех автомобилей.
    """
    try:
        statuses = [car.get_status() for car in cars]
        requests.post(f'{MANAGMENT_URL}/car/status/all', json={'cars': statuses})
        return jsonify(statuses)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/car/start/<string:brand>', methods=['POST'])
def start_car(brand):
    """
    Запускает поездку указанного автомобиля.

    Аргументы:
    - brand (str): Марка автомобиля.

    Возвращает:
    - JSON: Сообщение о начале поездки.
    """
    try:
        car = next((car for car in cars if car.brand.lower() == brand.lower()), None)
        assert car is not None, "Автомобиль не найден."

        message = car.start()
        thread = threading.Thread(target=simulate_drive, args=(car,))
        thread.start()
        return jsonify({"message": message})
    except AssertionError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/car/stop/<string:brand>', methods=['POST'])
def stop_car(brand):
    """
    Останавливает поездку указанного автомобиля.

    Аргументы:
    - brand (str): Марка автомобиля.

    Возвращает:
    - JSON: Сообщение о завершении поездки.
    """
    try:
        car = next((car for car in cars if car.brand.lower() == brand.lower()), None)
        assert car is not None, "Автомобиль не найден."

        status = car.get_status()
        response = requests.post(f'{MANAGMENT_URL}/return/{car.occupied_by}', json={'status': status})
        assert response.status_code == 200, "Ошибка при возврате автомобиля."

        message = car.stop()
        return jsonify({"message": message})
    except AssertionError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/emergency/<string:brand>', methods=['POST'])
def emergency(brand):
    """
    Останавливает поездку указанного автомобиля в экстренном режиме.

    Аргументы:
    - brand (str): Марка автомобиля.

    Возвращает:
    - JSON: Сообщение о завершении поездки.
    """
    try:
        car = next((car for car in cars if car.brand.lower() == brand.lower()), None)
        assert car is not None, "Автомобиль не найден."

        message = car.stop()
        return jsonify({"message": message})
    except AssertionError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/car/status/<string:brand>', methods=['GET'])
def get_car_status(brand):
    """
    Возвращает статус указанного автомобиля.

    Аргументы:
    - brand (str): Марка автомобиля.

    Возвращает:
    - JSON: Статус автомобиля.
    """
    try:
        car = next((car for car in cars if car.brand.lower() == brand.lower()), None)
        assert car is not None, "Автомобиль не найден."

        status = car.get_status()
        requests.post(f'{MANAGMENT_URL}/car/status', json={'status': status})
        return jsonify(status)
    except AssertionError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/access/<string:person>', methods=['POST'])
def access(person):
    """
    Проверяет доступ клиента к автомобилю.

    Аргументы:
    - person (str): Имя клиента.

    Возвращает:
    - JSON: Сообщение о доступе.
    """
    global data
    global flag
    try:
        data = request.json
        flag = False
        return jsonify("ok")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/car/occupy/<string:person>', methods=['POST'])
def occupy_car(person):
    """
    Арендует автомобиль указанным клиентом.

    Аргументы:
    - person (str): Имя клиента.

    Возвращает:
    - JSON: Сообщение об аренде автомобиля.
    """
    global data
    global flag
    try:
        requests.post(f'{MANAGMENT_URL}/access/{person}')
        while flag:
            time.sleep(1)
        if data['access']:
            brand = data['car']
            car = next((car for car in cars if car.brand.lower() == brand.lower()), None)
            assert car is not None, "Автомобиль не найден."
            assert person is not None, "Не указан клиент."

            tariff = data['tariff']
            message = car.occupy(person, tariff)
            flag = True
            return jsonify({"access": True, "car": car.brand, "message": message})
        else:
            return jsonify({"access": False, "message": "Доступ до автомобиля не разрешен."}), 404
    except AssertionError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(HTTPException)
def handle_exception(e):
    """
    Обрабатывает HTTP исключения.

    Аргументы:
    - e (HTTPException): Исключение.

    Возвращает:
    - JSON: Информация об ошибке.
    """
    response = e.get_response()
    return jsonify({
        "status": e.code,
        "name": e.name,
    }), e.code


def start_web():
    """
    Запускает веб-сервер в отдельном потоке.
    """
    try:
        threading.Thread(target=lambda: app.run(
            host=HOST, port=PORT, debug=True, use_reloader=False
        )).start()
    except Exception as e:
        print(f"Ошибка при запуске веб-сервера: {e}")


if __name__ == "__main__":
    start_web()