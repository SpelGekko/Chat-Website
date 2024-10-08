from flask import Flask, render_template, request, session, redirect, url_for  # Import Flask module
from flask_socketio import join_room, leave_room, send, SocketIO  # Import Flask-SocketIO module
import random  # Import random module
from string import ascii_letters
from datetime import datetime

app = Flask(__name__)  # Create an instance of Flask class
app.config["SECRET_KEY"] = "123"
socketio = SocketIO(app)  # Create an instance of SocketIO class

rooms = {}  # Create a dictionary to store the rooms

def generate_code(Length):
    while True:
        code =""
        for _ in range(Length):
            code += random.choice(ascii_letters)
        if code not in rooms:
            break
    return code

@app.route("/", methods=["POST", "GET"])  # Define the route of the app
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
    
        if not name:
            return render_template("home.html", error="Please fill in a name.")
        if join != False and not code:
            return render_template("home.html", error="Please fill in a room code.")
        
        room = code
        if create != False:
            room = generate_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room not found.")

        session["name"] = name
        session["room"] = room

        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")  # Define the route of the app
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    
    return render_template("room.html", code=room, messages = rooms[room]["messages"])

@socketio.on("message")  # When a user sends a message
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    content ={
        "name": session.get("name"),
        "message": data["message"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{content['name']}: {content['message']}")

@socketio.on("connect")  # When a user joins a room
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

@socketio.on("disconnect")  # When a user leaves a room
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

if __name__ == "__main__":  # If this script is executed, then...
    socketio.run(app, debug=True)  # Run the app
