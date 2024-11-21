from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import threading
from datetime import datetime
from enum import Enum
from werkzeug.exceptions import HTTPException

MANAGMENT_URL = 'http://bank-pay:6065' 

HOST = '0.0.0.0'
PORT = 8000
MODULE_NAME = os.getenv('MODULE_NAME')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///payments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class PaymentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


# Модель для хранения клиентов
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invoices = db.relationship('Invoice', backref='client', lazy=True)
    prepayments = db.relationship('Prepayment', backref='client', lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


# Модель для хранения счетов
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Модель для хранения архивированных счетов
class ArchivedInvoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PAID)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Модель для хранения предоплат
class Prepayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Инициализация базы данных
@app.before_first_request
def create_tables():
    """
    Инициализация базы данных перед первым запросом.
    """
    db.create_all()


# Создание клиента
@app.route('/clients', methods=['POST'])
def create_or_exists_client():
    """
    Создание нового клиента или возврат существующего клиента по имени.

    Returns:
        JSON: Информация о клиенте или список клиентов.
    """
    try:
        data = request.json
        name = data.get('name')
        assert name, "Client name is required"
        clients = Client.query.filter(Client.name.ilike(f'%{name}%')).all()
        if clients:
            return jsonify([client.to_dict() for client in clients]), 200
        else:
            client = Client(name=name)
            db.session.add(client)
            db.session.commit()
            return jsonify([{'id': client.id, 'name': client.name}]), 201
    except AssertionError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получение клиента по ID
@app.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """
    Получение информации о клиенте по ID.

    Args:
        client_id (int): ID клиента.

    Returns:
        JSON: Информация о клиенте.
    """
    try:
        client = Client.query.get_or_404(client_id)
        return jsonify({'id': client.id, 'name': client.name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Отправка счёта на оплату
@app.route('/invoices', methods=['POST'])
def create_invoice():
    """
    Создание нового счёта для клиента.

    Returns:
        JSON: Информация о созданном счёте.
    """
    try:
        data = request.json
        client_id = data.get('client_id')
        amount = data.get('amount')
        assert client_id is not None and amount is not None, "Client ID and amount are required"
        invoice = Invoice(client_id=client_id, amount=amount)
        db.session.add(invoice)
        db.session.commit()
        return jsonify({'id': invoice.id, 'amount': invoice.amount, 'status': invoice.status.value, 'client_id': invoice.client_id}), 201
    except AssertionError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получение всех счетов по ID клиента
@app.route('/clients/<int:client_id>/invoices', methods=['GET'])
def get_invoices_by_client(client_id: int):
    """
    Получение всех счетов для клиента по его ID.

    Args:
        client_id (int): ID клиента.

    Returns:
        JSON: Список счетов клиента.
    """
    try:
        client = Client.query.get_or_404(client_id)
        invoices = Invoice.query.filter_by(client_id=client.id).all()
        return jsonify([{'id': invoice.id, 'amount': invoice.amount, 'status': invoice.status.value} for invoice in invoices])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получение оплаты
@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id: int):
    """
    Получение информации о счёте по его ID.

    Args:
        invoice_id (int): ID счёта.

    Returns:
        JSON: Информация о счёте.
    """
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        return jsonify({'id': invoice.id, 'amount': invoice.amount, 'status': invoice.status.value, 'client_id': invoice.client_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Подтверждение оплаты
@app.route('/invoices/<int:invoice_id>/confirm', methods=['POST'])
def confirm_payment(invoice_id: int):
    """
    Подтверждение оплаты счёта.

    Args:
        invoice_id (int): ID счёта.

    Returns:
        JSON: Информация о подтверждённом счёте.
    """
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        client = Client.query.get(invoice.client_id)
        invoice.status = PaymentStatus.PAID
        db.session.commit()
        requests.post(f'{MANAGMENT_URL}/confirm_payment/{client.name}', json={'id': invoice.id, 'status': invoice.status.value})
        return jsonify({'id': invoice.id, 'status': invoice.status.value})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Отправка чека
@app.route('/invoices/<int:invoice_id>/receipt', methods=['GET'])
def send_receipt(invoice_id: int):
    """
    Отправка чека и архивирование счёта.

    Args:
        invoice_id (int): ID счёта.

    Returns:
        JSON: Информация о чеке.
    """
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        receipt = {
            'id': invoice.id,
            'amount': invoice.amount,
            'status': invoice.status.value,
            'created_at': invoice.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'client_id': invoice.client_id
        }
        archived_invoice = ArchivedInvoice(
            client_id=invoice.client_id,
            amount=invoice.amount,
            created_at=invoice.created_at)
        db.session.add(archived_invoice)
        db.session.delete(invoice)
        db.session.commit()
        return jsonify({'message': 'Receipt sent', 'receipt': receipt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получение всех архивированных счетов
@app.route('/clients/<int:client_id>/archived_invoices', methods=['GET'])
def get_archived_invoices_by_client(client_id: int):
    """
    Получение всех архивированных счетов для клиента по его ID.

    Args:
        client_id (int): ID клиента.

    Returns:
        JSON: Список архивированных счетов клиента.
    """
    try:
        client = Client.query.get_or_404(client_id)
        archived_invoices = ArchivedInvoice.query.filter_by(client_id=client.id).all()
        return jsonify([{
            'id': archived_invoice.id,
            'amount': archived_invoice.amount,
            'status': archived_invoice.status.value,
            'created_at': archived_invoice.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for archived_invoice in archived_invoices])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Создание предоплаты
@app.route('/clients/<int:client_id>/prepayment', methods=['POST'])
def create_prepayment(client_id: int):
    """
    Создание новой предоплаты для клиента.

    Args:
        client_id (int): ID клиента.

    Returns:
        JSON: Информация о созданной предоплате.
    """
    try:
        data = request.json
        amount = data.get('amount')
        assert amount is not None, "Amount is required"
        prepayment = Prepayment(client_id=client_id, amount=amount)
        db.session.add(prepayment)
        db.session.commit()
        return jsonify({'id': prepayment.id, 'amount': prepayment.amount, 'client_id': prepayment.client_id, 'status': prepayment.status.value}), 201
    except AssertionError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Подтверждение предоплаты
@app.route('/prepayment/<int:prepayment_id>/confirm', methods=['POST'])
def confirm_prepayment(prepayment_id: int):
    """
    Подтверждение предоплаты.

    Args:
        prepayment_id (int): ID предоплаты.

    Returns:
        JSON: Информация о подтверждённой предоплате.
    """
    try:
        prepayment = Prepayment.query.get_or_404(prepayment_id)
        client = Client.query.get(prepayment.client_id)
        prepayment.status = PaymentStatus.PAID
        db.session.commit()
        requests.post(f'{MANAGMENT_URL}/confirm_prepayment/{client.name}', json={'id': prepayment.id, 'status': prepayment.status.value})
        return jsonify({'id': prepayment.id, 'status': prepayment.status.value})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получение всех предоплат по ID клиента
@app.route('/clients/<int:client_id>/prepayments', methods=['GET'])
def get_prepayments_by_client(client_id: int):
    """
    Получение всех предоплат для клиента по его ID.

    Args:
        client_id (int): ID клиента.

    Returns:
        JSON: Список предоплат клиента.
    """
    try:
        client = Client.query.get_or_404(client_id)
        prepayments = Prepayment.query.filter_by(client_id=client.id).all()
        return jsonify([{'id': prepayment.id, 'amount': prepayment.amount, 'status': prepayment.status.value} for prepayment in prepayments])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(HTTPException)
def handle_exception(e):
    """
    Обработчик исключений HTTP.

    Args:
        e (HTTPException): Исключение HTTP.

    Returns:
        JSON: Информация об ошибке.
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