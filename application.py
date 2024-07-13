import jwt
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from models import db, Admin, Company, Location, Sensor, SensorData
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
application.config['SECRET_KEY'] = 'your_secret_key'
db.init_app(application)

def generate_token(admin):
    token = jwt.encode({
        'admin_id': admin.id,
        'exp': datetime.utcnow() + timedelta(hours=1)
    }, application.config['SECRET_KEY'], algorithm='HS256')
    return token

def authenticate_admin():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return False
    try:
        token = auth_header.split(" ")[1]
        data = jwt.decode(token, application.config['SECRET_KEY'], algorithms=['HS256'])
        admin = Admin.query.get(data['admin_id'])
        if not admin:
            return False
        g.admin = admin
        return True
    except (IndexError, jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate_admin():
            return jsonify({"message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_company_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        company_api_key = request.args.get('company_api_key') or request.headers.get('company_api_key')
        if not company_api_key:
            return jsonify({"message": "company_api_key is required"}), 401
        company = Company.query.filter_by(company_api_key=company_api_key).first()
        if not company:
            return jsonify({"message": "Invalid company API key"}), 401
        g.company = company
        return f(*args, **kwargs)
    return decorated_function

@application.cli.command('create-admin')
def create_admin():
    """Create a new admin user"""
    username = input("Enter username: ")
    password = input("Enter password: ")
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user {username} created.")

@application.route('/api/v1/login', methods=['POST'])
def login():
    data = request.json
    admin = Admin.query.filter_by(username=data['username']).first()
    if not admin or not check_password_hash(admin.password, data['password']):
        return jsonify({"message": "Invalid credentials"}), 401
    token = generate_token(admin)
    return jsonify({"token": token}), 200

@application.route('/api/v1/companies', methods=['POST'])
@require_admin
def create_company():
    data = request.json
    new_company = Company(company_name=data['company_name'], company_api_key=str(uuid.uuid4()))
    db.session.add(new_company)
    db.session.commit()
    return jsonify({"message": "Company created", "company_api_key": new_company.company_api_key}), 201

@application.route('/api/v1/locations', methods=['POST'])
@require_admin
@require_company_api_key
def create_location():
    data = request.json
    new_location = Location(company_id=g.company.id, location_name=data['location_name'],
                            location_country=data['location_country'], location_city=data['location_city'],
                            location_meta=data['location_meta'])
    db.session.add(new_location)
    db.session.commit()
    return jsonify({"message": "Location created"}), 201

@application.route('/api/v1/locations', methods=['GET'])
@require_admin
@require_company_api_key
def get_locations():
    locations = Location.query.filter_by(company_id=g.company.id).all()
    return jsonify([{
        "id": loc.id,
        "location_name": loc.location_name,
        "location_country": loc.location_country,
        "location_city": loc.location_city,
        "location_meta": loc.location_meta
    } for loc in locations]), 200

@application.route('/api/v1/locations/<int:location_id>', methods=['GET'])
@require_admin
@require_company_api_key
def get_location(location_id):
    location = Location.query.filter_by(id=location_id, company_id=g.company.id).first()
    if not location:
        return jsonify({"message": "Location not found"}), 404
    return jsonify({
        "id": location.id,
        "location_name": location.location_name,
        "location_country": location.location_country,
        "location_city": location.location_city,
        "location_meta": location.location_meta
    }), 200

@application.route('/api/v1/locations/<int:location_id>', methods=['PUT'])
@require_admin
@require_company_api_key
def update_location(location_id):
    data = request.json
    location = Location.query.filter_by(id=location_id, company_id=g.company.id).first()
    if not location:
        return jsonify({"message": "Location not found"}), 404
    location.location_name = data.get('location_name', location.location_name)
    location.location_country = data.get('location_country', location.location_country)
    location.location_city = data.get('location_city', location.location_city)
    location.location_meta = data.get('location_meta', location.location_meta)
    db.session.commit()
    return jsonify({"message": "Location updated"}), 200

@application.route('/api/v1/locations/<int:location_id>', methods=['DELETE'])
@require_admin
@require_company_api_key
def delete_location(location_id):
    location = Location.query.filter_by(id=location_id, company_id=g.company.id).first()
    if not location:
        return jsonify({"message": "Location not found"}), 404
    db.session.delete(location)
    db.session.commit()
    return jsonify({"message": "Location deleted"}), 200

@application.route('/api/v1/sensors', methods=['POST'])
@require_admin
@require_company_api_key
def create_sensor():
    data = request.json
    location = Location.query.filter_by(id=data['location_id'], company_id=g.company.id).first()
    if not location:
        return jsonify({"message": "Invalid location or location does not belong to the company"}), 400
    new_sensor = Sensor(location_id=location.id, sensor_name=data['sensor_name'],
                        sensor_category=data['sensor_category'], sensor_meta=data['sensor_meta'],
                        sensor_api_key=str(uuid.uuid4()))
    db.session.add(new_sensor)
    db.session.commit()
    return jsonify({"message": "Sensor created", "sensor_api_key": new_sensor.sensor_api_key}), 201

@application.route('/api/v1/sensors', methods=['GET'])
@require_admin
@require_company_api_key
def get_sensors():
    sensors = Sensor.query.join(Location).filter(Location.company_id == g.company.id).all()
    return jsonify([{
        "id": sensor.id,
        "location_id": sensor.location_id,
        "sensor_name": sensor.sensor_name,
        "sensor_category": sensor.sensor_category,
        "sensor_meta": sensor.sensor_meta,
        "sensor_api_key": sensor.sensor_api_key
    } for sensor in sensors]), 200

@application.route('/api/v1/sensors/<int:sensor_id>', methods=['GET'])
@require_admin
@require_company_api_key
def get_sensor(sensor_id):
    sensor = Sensor.query.join(Location).filter(Sensor.id == sensor_id, Location.company_id == g.company.id).first()
    if not sensor:
        return jsonify({"message": "Sensor not found"}), 404
    return jsonify({
        "id": sensor.id,
        "location_id": sensor.location_id,
        "sensor_name": sensor.sensor_name,
        "sensor_category": sensor.sensor_category,
        "sensor_meta": sensor.sensor_meta,
        "sensor_api_key": sensor.sensor_api_key
    }), 200

@application.route('/api/v1/sensors/<int:sensor_id>', methods=['PUT'])
@require_admin
@require_company_api_key
def update_sensor(sensor_id):
    data = request.json
    sensor = Sensor.query.join(Location).filter(Sensor.id == sensor_id, Location.company_id == g.company.id).first()
    if not sensor:
        return jsonify({"message": "Sensor not found"}), 404
    sensor.sensor_name = data.get('sensor_name', sensor.sensor_name)
    sensor.sensor_category = data.get('sensor_category', sensor.sensor_category)
    sensor.sensor_meta = data.get('sensor_meta', sensor.sensor_meta)
    db.session.commit()
    return jsonify({"message": "Sensor updated"}), 200

@application.route('/api/v1/sensors/<int:sensor_id>', methods=['DELETE'])
@require_admin
@require_company_api_key
def delete_sensor(sensor_id):
    sensor = Sensor.query.join(Location).filter(Sensor.id == sensor_id, Location.company_id == g.company.id).first()
    if not sensor:
        return jsonify({"message": "Sensor not found"}), 404
    db.session.delete(sensor)
    db.session.commit()
    return jsonify({"message": "Sensor deleted"}), 200

@application.route('/api/v1/sensor_data', methods=['POST'])
@require_admin
def insert_sensor_data():
    data = request.json
    sensor = Sensor.query.filter_by(sensor_api_key=data['api_key']).first()
    if not sensor:
        return jsonify({"message": "Invalid sensor API key"}), 400
    for entry in data['json_data']:
        new_data = SensorData(sensor_id=sensor.id, data=entry, timestamp=datetime.now())
        db.session.add(new_data)
        print(f"Inserted data: {new_data.data} for sensor: {sensor.id}")
    db.session.commit()
    return jsonify({"message": "Data inserted"}), 201

@application.route('/api/v1/sensor_data', methods=['GET'])
@require_admin
@require_company_api_key
def get_sensor_data():
    try:
        from_timestamp = datetime.fromtimestamp(int(request.args.get('from')))
        to_timestamp = datetime.fromtimestamp(int(request.args.get('to')))
        sensor_ids = request.args.get('sensor_id')
        if sensor_ids:
            sensor_ids = sensor_ids.strip('[]').split(',')
            sensor_ids = [int(sid) for sid in sensor_ids]
        else:
            return jsonify({"message": "sensor_id is required"}), 400
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid parameters"}), 400

    data = SensorData.query.filter(SensorData.sensor_id.in_(sensor_ids),
                                   SensorData.timestamp.between(from_timestamp, to_timestamp)).all()

    return jsonify([{
        "sensor_id": d.sensor_id,
        "data": d.data,
        "timestamp": d.timestamp.isoformat()
    } for d in data]), 200


def create_app():
    with application.app_context():
        db.create_all()
    return application

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)