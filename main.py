from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import join_room, leave_room, send, SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash
import random
from string import ascii_letters
from datetime import datetime
import dotenv
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
socketio = SocketIO(app)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

rooms = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

def generate_code(length):
    while True:
        code = "".join(random.choice(ascii_letters) for _ in range(length))
        if code not in rooms:
            break
    return code

@app.route("/", methods=["POST", "GET"])
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/dashboard", methods=["POST", "GET"])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        name = session['username']
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
    
        if join and not code:
            return render_template("dashboard.html", error="Please fill in a room code.", name=name)
        
        room = code
        if create:
            room = generate_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("dashboard.html", error="Room not found.", name=name)

        session["name"] = name
        session["room"] = room

        return redirect(url_for("room"))

    return render_template("dashboard.html", name=session['username'])

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("dashboard"))
    
    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        if not username or not password:
            return render_template('login.html', form=form, error='Please fill in both fields')
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not check_password_hash(user.password, password):
            print("Debug: Invalid username or password")
            return render_template('login.html', form=form, error='Invalid username or password')
        
        session['username'] = username
        flash('Logged in successfully')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        if not username or not password:
            return render_template('register.html', form=form, error='Please fill in both fields')
        
        password_hash = generate_password_hash(password)
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return render_template('register.html', form=form, error='Username already exists')
        
        new_user = User(username=username, password=password_hash)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    content = {
        "name": session.get("name"),
        "message": data["message"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{content['name']}: {content['message']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if room is None or name is None:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send({"name": name, "message": "joined the room.", "timestamp": timestamp}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined {room} at {timestamp}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send({"name": name, "message": "left the room.", "timestamp": timestamp}, to=room)
    print(f"{name} left {room} at {timestamp}")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)