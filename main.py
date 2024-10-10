from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import join_room, leave_room, send, SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import random
from string import ascii_letters
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from waitress import serve
from flask_cors import CORS
import jwt
from flask_mail import Mail, Message

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = str(os.environ.get("SECRET_KEY"))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.example.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'false').lower() in ['true', '1', 't']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER', 'your-email@example.com')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS', 'your-email-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'your-email@example.com')

mail = Mail(app)

# Enable CORS for your Flask app
CORS(app, resources={r"/*": {"origins": ["https://chat.blackstonebloods.com"]}})

# Initialize SocketIO with CORS allowed origins
socketio = SocketIO(app, cors_allowed_origins=["https://chat.blackstonebloods.com"])
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
rooms = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(120), nullable=True)

    def generate_verification_token(self, expires_sec=3600):
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_sec)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
        return token

    @staticmethod
    def verify_verification_token(token):
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return None  # Token has expired
        except jwt.InvalidTokenError:
            return None  # Invalid token
        return User.query.get(user_id)

class TempUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    verification_token = db.Column(db.String(120), nullable=True)

    def generate_verification_token(self, expires_sec=3600):
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_sec)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
        return token

    @staticmethod
    def verify_verification_token(token):
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return None  # Token has expired
        except jwt.InvalidTokenError:
            return None  # Invalid token
        return TempUser.query.get(user_id)
    
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])  # Add email field
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
        
        if not user.email_verified:
            print("Debug: Email not verified")
            return render_template('login.html', form=form, error='Please verify your email before logging in')

        session['username'] = username
        flash('Logged in successfully')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', form=form)

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = generate_password_hash(form.password.data)
        email = form.email.data

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Username or email already exists.")
            return redirect(url_for("register"))

        existing_temp_user = TempUser.query.filter((TempUser.username == username) | (TempUser.email == email)).first()
        if existing_temp_user:
            flash("Username or email already exists in temporary users.")
            return redirect(url_for("register"))

        new_temp_user = TempUser(username=username, password=password, email=email)
        db.session.add(new_temp_user)
        db.session.commit()  # Commit the temporary user to the database to get the user ID

        # Generate verification token
        new_temp_user.verification_token = new_temp_user.generate_verification_token()
        db.session.commit()  # Commit the token to the database

        # Send verification email
        token = new_temp_user.verification_token
        msg = Message('Email Verification', sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[email])
        msg.body = f'''To verify your email, visit the following link:
{url_for('verify_email', token=token, _external=True)}

If you did not make this request then simply ignore this email.
'''
        try:
            mail.send(msg)
            flash("Registration successful. Please check your email to verify your account.", 'info')
        except Exception as e:
            print(f"An error occurred while sending the email: {str(e)}")  # Debug statement
            db.session.delete(new_temp_user)
            db.session.commit()
            return redirect(url_for("register"))

        return redirect(url_for("login"))

    return render_template("register.html", form=form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/verify_email/<token>')
def verify_email(token):
    temp_user = TempUser.verify_verification_token(token)
    if temp_user is None:
        flash('The verification link is invalid or has expired.', 'danger')
        return redirect(url_for('register'))

    # Move user from TempUser to User
    new_user = User(username=temp_user.username, password=temp_user.password, email=temp_user.email, email_verified=True)
    db.session.add(new_user)
    db.session.delete(temp_user)
    db.session.commit()

    flash('Your email has been verified! You can now log in.', 'success')
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

