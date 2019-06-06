import datetime
from functools import wraps
from flask import Flask, request, render_template, session
from flask_sqlalchemy import SQLAlchemy
from threading import Thread

plants = {
    "Cucumber": [1, 4, 20, 155],
    "Green onion": [1, 3, 10, 200],
    "Dill": [1, 4, 15, 137],
    "Tomato": [1, 4, 20, 255],
    "Parsley": [1, 4, 12, 175]
}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = url = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "uwef76g8itu59wugi76f865dg4oit4th9@@hsuygd"
db = SQLAlchemy(app)


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(32), nullable=False, unique=True)
    device_name = db.Column(db.String(32), nullable=False)
    last_upload_date = db.Column(db.DateTime, default=datetime.datetime.now())
    temperature = db.Column(db.Float, default=0)
    humidity = db.Column(db.Float, default=0)
    ph = db.Column(db.Float, default=0)
    is_enabled = db.Column(db.Boolean, default=False)
    irr_intensity = db.Column(db.Integer, default=1)
    irr_time = db.Column(db.Integer, default=1)
    irr_on = db.Column(db.Boolean, default=False)
    light_intensity = db.Column(db.Integer, default=76)

    def __repr__(self):
        return f"<DEVICE {self.device_name} {self.device_id} {self.is_enabled}>"


def irritation():
    while True:
        devices = Device.query.all()
        for device in devices:
            date = datetime.datetime.now()
            if date.hour % (24 // device.irr_intensity) == 0 and date.minute < device.irr_time:
                device.irr_on = True
            else:
                device.irr_on = False
        db.session.commit()


def default_device(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("device_id", None) is None:
            try:
                session["device_id"] = Device.query.all()[0].device_id
            except Exception:
                session["device_id"] = None
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
@default_device
def index():
    device = Device.query.filter_by(device_id=session["device_id"]).first()
    if device is None:
        return render_template("empty.html")
    time_error = (datetime.datetime.now() - device.last_upload_date).seconds >= 20
    return render_template("index.html", time_error=time_error, device_name=device.device_name,
                           temperature=device.temperature,
                           humidity=device.humidity,
                           ph=device.ph)


@app.route("/settings", methods=["GET", "POST"])
@default_device
def settings():
    device = Device.query.filter_by(device_id=session["device_id"]).first()
    if device is None:
        return render_template("empty.html")
    if request.form.get("type") == "params_form":
        device.is_enabled = bool(int(request.form.get("enabled", False)))
        device.irr_intensity = int(request.form.get("intense", 1))
        device.irr_time = int(request.form.get("time", 1))
        device.light_intensity = int(request.form.get("light", 76))
        db.session.commit()
    if request.form.get("type") == "templates_form":
        plant = plants[request.form.get("template")]
        device.is_enabled = bool(plant[0])
        device.irr_intensity = plant[1]
        device.irr_time = plant[2]
        device.light_intensity = plant[3]
        db.session.commit()
    if request.form.get("type") == "device_form":
        device_tmp = Device.query.filter_by(device_id=request.form.get("device", device.id)).first()
        if device_tmp is not None:
            session["device_id"] = device_tmp.device_id
            device = device_tmp
    if request.form.get("type") == "rename_form":
        device.device_name = request.form.get("name", device.device_name)
        db.session.commit()
    return render_template("settings.html", current_id=session["device_id"],
                           devices=Device.query.all(),
                           device_name=device.device_name,
                           device_id=device.device_id,
                           is_enabled=device.is_enabled,
                           irr_intensity=device.irr_intensity,
                           irr_time=device.irr_time,
                           light_intensity=device.light_intensity,
                           plants=plants.keys())


@app.route("/arduino/<string:ident>")
def get_data_from_arduino(ident):
    data = request.args.get("data", None)
    device = Device.query.filter_by(device_id=ident).first()
    if device is None and len(ident) <= 32:
        device = Device(device_id=ident,
                        device_name="SmartGrowth Device")
        db.session.add(device)
        db.session.commit()
    if data is not None:
        data = [float(i) for i in data.split(";")]
        device.temperature = data[0]
        device.humidity = data[1]
        device.ph = data[2]
        device.last_upload_date = datetime.datetime.now()
        db.session.commit()
    return ";".join(map(str, [int(device.is_enabled),
                              int(device.irr_on),
                              device.light_intensity]))


db.create_all()
Thread(target=irritation).start()


if __name__ == '__main__':
    app.run()
