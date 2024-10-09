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
import os
from dotenv import load_dotenv
from waitress import serve

# Load environment variables from .env file
load_dotenv()

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

class CSRFForm(FlaskForm):
    pass

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
    
    form = CSRFForm()
    
    # Filter the list of rooms in the session to only include existing rooms
    if 'rooms' in session:
        session['rooms'] = [room for room in session['rooms'] if room in rooms]
        session.modified = True  # Ensure session is saved

    if request.method == "POST" and form.validate_on_submit():
        name = session['username']
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
        
        print(f"Form submitted: join={join}, create={create}, code={code}")
    
        if join and not code:
            print("Debug: Join requested but no code provided")
            return render_template("dashboard.html", error="Please fill in a room code.", name=name, form=form)
        
        room = code
        if create:
            room = generate_code(4)
            print(f"Debug: Created room {room}")
            rooms[room] = {"members": 0, "messages": [], "creator": name}
        elif code not in rooms:
            print(f"Debug: Room {code} not found")
            return render_template("dashboard.html", error="Room not found.", name=name, form=form)

        if 'rooms' not in session:
            session['rooms'] = []
        
        session['rooms'].append(room)
        session.modified = True  # Ensure session is saved
        print(f"User {name} joined room: {room}")

        return redirect(url_for("room", room_code=room))

    return render_template("dashboard.html", name=session['username'], rooms=session.get('rooms', []), form=form)

@app.route("/delete_room/<room_code>", methods=["POST"])
def delete_room(room_code):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    if room_code in rooms and rooms[room_code]['creator'] == username:
        socketio.emit('room_deleted', {'room': room_code}, to=room_code)
        del rooms[room_code]
        if 'rooms' in session and room_code in session['rooms']:
            session['rooms'].remove(room_code)
            session.modified = True  # Ensure session is saved
        print(f"Room {room_code} deleted by {username}")
    
    return redirect(url_for('dashboard'))

@app.route("/room/<room_code>")
def room(room_code):
    if 'rooms' not in session or room_code not in session['rooms']:
        print(f"Debug: Room {room_code} not in session or not in user's rooms")
        return redirect(url_for("dashboard"))
    
    if room_code not in rooms:
        print(f"Debug: Room {room_code} not found in rooms")
        return redirect(url_for("dashboard"))
    
    form = CSRFForm()
    print(f"Debug: Rendering room {room_code}")
    return render_template("room.html", code=room_code, messages=rooms[room_code]["messages"], rooms=rooms, form=form)

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

@socketio.on("join")
def handle_join(data):
    room = data["room"]
    join_room(room)
    name = session.get("username")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send({"name": name, "message": "joined the room.", "timestamp": timestamp}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined {room} at {timestamp}")

@socketio.on("message")
def handle_message(data):
    room = data["room"]
    content = {
        "name": session.get("username"),
        "message": data["message"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{content['name']}: {content['message']}")

@socketio.on("disconnect")
def handle_disconnect():
    user_rooms = session.get("rooms", [])
    name = session.get("username")
    for room in user_rooms:
        leave_room(room)
        if room in rooms:
            rooms[room]["members"] -= 1
            if rooms[room]["members"] <= 0:
                del rooms[room]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        send({"name": name, "message": "left the room.", "timestamp": timestamp}, to=room)
        print(f"{name} left {room} at {timestamp}")

