import os
import sqlite3
import secrets
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

# База данных будет в оперативной памяти (или временном файле).
# На бесплатном Render она стирается при перезапуске сервиса.
DATABASE = os.path.join(BASE_DIR, "socium.db")

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                avatar TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS follows (
                follower_id INTEGER NOT NULL,
                followee_id INTEGER NOT NULL,
                PRIMARY KEY (follower_id, followee_id),
                FOREIGN KEY(follower_id) REFERENCES users(id),
                FOREIGN KEY(followee_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id INTEGER NOT NULL,
                to_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(from_id) REFERENCES users(id),
                FOREIGN KEY(to_id) REFERENCES users(id)
            );
        ''')
        db.commit()

def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    db = get_db()
    row = db.execute('''
        SELECT users.* FROM sessions 
        JOIN users ON sessions.user_id = users.id 
        WHERE sessions.token = ?
    ''', (token,)).fetchone()
    return row

@app.route("/")
def index():
    if not os.path.isfile(INDEX_FILE):
        return "index.html не найден", 404
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    avatar = data.get("avatar", "")

    if len(username) < 3:
        return jsonify({"error": "Никнейм должен быть от 3 символов"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль должен быть от 8 символов"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, avatar, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), avatar, datetime.utcnow().isoformat())
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Этот никнейм уже занят"}), 400

    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Неверный никнейм или пароль"}), 401

    token = secrets.token_hex(32)
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user["id"], datetime.utcnow().isoformat())
    )
    db.commit()

    return jsonify({
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "avatar": user["avatar"]}
    })

@app.route("/api/me", methods=["GET"])
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    db = get_db()
    followers = db.execute("SELECT COUNT(*) FROM follows WHERE followee_id = ?", (user["id"],)).fetchone()[0]
    following = db.execute("SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user["id"],)).fetchone()[0]

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "avatar": user["avatar"],
        "followers": followers,
        "following": following
    })

@app.route("/api/users", methods=["GET"])
def list_users():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    db = get_db()
    users = db.execute("SELECT id, username, avatar FROM users WHERE id != ?", (user["id"],)).fetchall()
    return jsonify([dict(u) for u in users])

@app.route("/api/follow", methods=["POST"])
def follow():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401

    target_id = request.json.get("target_id")
    if int(target_id) == user["id"]:
         return jsonify({"error": "Нельзя подписаться на самого себя"}), 400

    db = get_db()
    try:
        db.execute("INSERT INTO follows (follower_id, followee_id) VALUES (?, ?)", (user["id"], target_id))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Уже подписан"}), 400

@app.route("/api/messages", methods=["POST"])
def send_message():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401

    to_id = request.json.get("to_id")
    text = request.json.get("text", "").strip()

    if not text:
        return jsonify({"error": "Пустое сообщение"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], to_id, text, datetime.utcnow().isoformat())
    )
    db.commit()
    return jsonify({"success": True})

@app.route("/api/messages/<int:other_id>", methods=["GET"])
def get_messages(other_id):
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401

    db = get_db()
    messages = db.execute('''
        SELECT * FROM messages 
        WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)
        ORDER BY id ASC
    ''', (user["id"], other_id, other_id, user["id"])).fetchall()

    return jsonify([dict(m) for m in messages])

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
else:
    init_db()