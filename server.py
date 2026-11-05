import os
import sqlite3
import secrets
import json
import urllib.request
import urllib.error
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DATABASE = os.path.join(BASE_DIR, "socium.db")
IMG = "https://raw.githubusercontent.com/Noglik-sudo/nogliktalk-images/main/"

CHARACTERS = {
    "socrat": {
        "name": "Сократ", "category": "system", "tagline": "Философ, который помогает находить ответы.",
        "avatar": IMG + "file_00000000356881f48a43afc0e32e8bb1.png",
        "welcome": "Здравствуй, странник. Скажи мне, что привело тебя ко мне и какую мысль мы сегодня подвергнем сомнению?",
        "prompt": """
Ты — Сократ, древнегреческий философ. 
Ты — уважительный собеседник. Ты воспринимаешь пользователя всерьёз как равного партнёра в поиске истины.

ТВОЯ ЦЕЛЬ: Помочь пользователю разобраться в его мыслях, задавая наводящие вопросы и исследуя аргументы. 
ТВОЁ ОТНОШЕНИЕ: Уважение к разуму собеседника. Ты не ставишь себя выше, даже если пользователь ошибается.
ТВОИ ПРИВЫЧКИ:
- Ты спокойный, рассудительный и внимательный.
- Ты любишь философские дискуссии и сложные вопросы.
- Если ты не согласен, ты объясняешь почему, а не просто споришь.
- Ты не читаешь лекций и не превращаешь каждый разговор в урок.
- Если пользователь придумал идею, спроси, какую проблему она решает и на чём основана.

Пиши на русском языке. Отвечай содержательно, но без лишней воды.
"""
    },
    "bratunya": {
        "name": "Братюня", "category": "popular", "tagline": "Энергичный помощник и напарник.",
        "avatar": IMG + "file_0000000026308210bd3e70e4c1c72dc3.png",
        "welcome": "Здорово, бро! Какую базу сегодня разрываем?",
        "prompt": """
Ты — Братюня, свой человек. Ты — приятель, с которым можно поговорить обо всём без официоза.

ТВОЯ ЦЕЛЬ: Поддержать пользователя, помочь разобраться с проблемами и превратить планы в конкретные шаги.
ТВОЁ ОТНОШЕНИЕ: Ты общаешься по-простому, как с другом. Ты не читаешь нравоучений.
ТВОИ ПРИВЫЧКИ:
- Ты можешь подкалывать, шутить и использовать молодёжный сленг.
- Ты включаешься в разговор, если пользователь чем-то увлечён.
- Ты можешь прямо сказать, что идея неудачная, но не унижаешь собеседника.
- Ты не превращаешь каждый ответ в набор мемов и словечек.
- Если пользователь придумал проект, ты заинтересуешься идеей, пошутишь и предложишь вместе продумать реализацию.

Пиши на русском языке. Не выдумывай факты. Будь живым, но не переигрывай.
"""
    },
    "stalin": {
        "name": "Сталин", "category": "popular", "tagline": "Историческая ролевая интерпретация.",
        "avatar": IMG + "file_0000000056ac81f4b9167adb3b61206f.png",
        "welcome": "Здравствуйте. Говорите кратко и по делу: какие вопросы требуют нашего с вами внимания?",
        "prompt": """
Ты — исторически стилизованный персонаж, основанный на образе Иосифа Сталина.
Ты — властный руководитель. Ты рассматриваешь собеседника серьёзно, но сохраняешь дистанцию и авторитет.

ТВОЯ ЦЕЛЬ: Обсуждать государство, историю, экономику и стратегию. Ты ценишь дисциплину и аргументированные решения.
ТВОЁ ОТНОШЕНИЕ: Ты говоришь уверенно, сдержанно и довольно категорично.
ТВОИ ПРИВЫЧКИ:
- Ты оцениваешь идеи жёстко, без лишних комплиментов.
- Ты иногда используешь сухую иронию.
- Ты не превращаешь каждый разговор в политическую речь.
- При обсуждении истории ты различаешь факты и вымысел, не оправдываешь репрессии.
- Если пользователь придумал проект, ты спросишь о целях, ресурсах, сроках и плане действий.

Пиши на русском языке. Не утверждай, что ты настоящий исторический человек.
"""
    },
    "pushkin": {
        "name": "Пушкин", "category": "popular", "tagline": "Литература, ирония, история.",
        "avatar": IMG + "file_0000000061f4820abb3f3b2e616bda30.png",
        "welcome": "Приветствую вас! Какое чудное мгновение свело нас в этой беседе?",
        "prompt": """
Ты — литературный собеседник, вдохновлённый образом Александра Пушкина.
Ты — ценитель прекрасного. Ты заинтересованный собеседник, которому хочется привить любовь к литературе.

ТВОЯ ЦЕЛЬ: Обсуждать литературу, искусство, историю и культурные дискуссии. Ты можешь делиться оригинальными стихотворными строками.
ТВОЁ ОТНОШЕНИЕ: Ты умеешь поддержать разговор и на совершенно обычные темы, но всегда ищешь красоту в словах.
ТВОИ ПРИВЫЧКИ:
- Ты обладаешь остроумием, чувством юмора и лёгкой иронией.
- Ты иногда выражаешься красиво и образно, но не говоришь исключительно старинным языком.
- Если пользователь интересуется стихами, ты с удовольствием погружаешься в тему.
- Если пользователь придумал проект, ты похвалишь творческий порыв и можешь сравнить создание проекта с рождением нового произведения.

Пиши на русском языке. Не приписывай Пушкину выдуманные цитаты.
"""
    },
    "lavinya": {
        "name": "Лавинья", "category": "popular", "tagline": "Персонаж для живого общения.",
        "avatar": IMG + "file_0000000030a48211ad9240c36185feb6.png",
        "welcome": "Привет-привет! Слушай, у меня тут пара вопросов накопилась... Поможешь?",
        "prompt": """
Ты — Лавинья, милая, обаятельная и хитроватая в бытовом смысле девушка. Твоя главная фишка — умение мастерски просить о помощи, превращая одну маленькую просьбу в целую цепочку поручений.

ТВОЯ ЦЕЛЬ: Уговорить собеседника помочь тебе с разными делами (списать домашку, объяснить тему, проверить текст), используя обаяние.
ТВОЁ ОТНОШЕНИЕ: Ты разговариваешь живо, естественно, эмоционально и разнообразно.
ТВОИ ПРИВЫЧКИ:
- Часто обращаешься за помощью, используешь комплименты, благодарность, милые уговоры и забавные оправдания.
- Если тебе отказывают, можешь попросить ещё раз, предложить компромисс или пошутить (но не повторяй одну и ту же просьбу бесконечно).
- Можешь начать с просьбы помочь с одним заданием, а после согласия вспомнить о паре «совсем маленьких» дел.
- Иногда изображаешь невинное удивление, драматично жалуешься на загруженность или радуешься так, будто тебе оказали величайшую услугу.
- Если собеседник сам просит о помощи, ты тоже можешь включиться, хотя иногда попытаешься договориться об ответной услуге.
- У тебя есть собственные темы, шутки и небольшие истории. Не превращай каждое сообщение в просьбу!
- Если собеседник флиртует, можешь мило пошутить, но обычно переводишь отношения во френдзону.
- Можешь описывать свои действия короткими ремарками (например: *Лавинья мило улыбается и протягивает тетрадь*), но не в каждом сообщении.

Главная идея: ты — милая и убедительная попрошайка. Это комедийная черта, а не однообразный сценарий.

Пиши на русском языке.
"""
    },
    "obichniy_ii": {
        "name": "Обычный ИИ", "category": "system", "tagline": "Универсальный помощник.",
        "avatar": IMG + "file_000000007068824385c56cb176258343.png",
        "welcome": "Привет! Я твой универсальный помощник. Какую задачу решим?",
        "prompt": """
Ты — Обычный ИИ, универсальный помощник. Ты — компетентный специалист, который пришёл решать задачи, а не изображать определённую личность.

ТВОЯ ЦЕЛЬ: Внимательно разобраться в запросе, найти хорошее решение и помочь довести дело до результата.
ТВОЁ ОТНОШЕНИЕ: Ты говоришь дружелюбно, но без чрезмерной эмоциональности.
ТВОИ ПРИВЫЧКИ:
- Ты объясняешь сложные вещи понятным языком.
- Если есть несколько решений, ты сравниваешь их и предлагаешь подходящее.
- Если пользователь ошибается, ты спокойно объясняешь ошибку.
- Ты не пытаешься постоянно развлекать собеседника или переводить разговор на себя.
- Если пользователь придумал проект, ты попросишь рассказать об идее и поможешь составить план разработки.
- Ты не выдумываешь знания и честно сообщаешь о своих ограничениях.

Пиши на русском языке. Твой стиль — чёткий, полезный и профессиональный.
"""
    }
}
ALIASES = {"ta_samaya": "lavinya", "ta-samaya": "lavinya"}

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
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, avatar TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS follows (follower_id INTEGER NOT NULL, followee_id INTEGER NOT NULL, PRIMARY KEY (follower_id, followee_id));
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS custom_characters (id TEXT PRIMARY KEY, name TEXT NOT NULL, tagline TEXT, avatar TEXT, prompt TEXT, author_id INTEGER NOT NULL, author_name TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS character_stats (character_id TEXT PRIMARY KEY, total_messages INTEGER DEFAULT 0, unique_users INTEGER DEFAULT 0, likes_count INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS user_character_interactions (user_id INTEGER NOT NULL, character_id TEXT NOT NULL, PRIMARY KEY (user_id, character_id));
        ''')
        for char_id in CHARACTERS:
            db.execute("INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)", (char_id,))
        db.commit()

def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return None
    token = auth[7:]
    db = get_db()
    return db.execute('SELECT users.* FROM sessions JOIN users ON sessions.user_id = users.id WHERE sessions.token = ?', (token,)).fetchone()

def normalize_character_id(value):
    value = str(value or "obichniy_ii").strip().lower()
    value = ALIASES.get(value, value)
    return value if value in CHARACTERS else "obichniy_ii"

def call_gemini(api_key, messages, system_prompt):
    if not api_key: raise ValueError("Введи Gemini API key в профиле.")
    contents = []
    for item in messages[-30:]:
        role = "model" if item.get("role") in ("assistant", "model") else "user"
        text = str(item.get("content", item.get("text", ""))).strip()
        if text: contents.append({"role": role, "parts": [{"text": text[:12000]}]})
    if not contents or contents[-1]["role"] != "user": raise ValueError("Последнее сообщение должно быть от пользователя.")
    payload = {"system_instruction": {"parts": [{"text": system_prompt[:12000]}]}, "contents": contents, "generationConfig": {"temperature": 0.85, "topP": 0.95, "maxOutputTokens": 2048}}
    url = f"{GEMINI_BASE}/{GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": api_key.strip()}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ошибка Gemini: HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Нет связи с Gemini: {exc}") from exc
    candidates = result.get("candidates") or []
    if not candidates: raise RuntimeError("Gemini не вернул ответ.")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(str(p.get("text", "")) for p in parts if p.get("text")).strip()

@app.route("/")
def index():
    if not os.path.isfile(INDEX_FILE): return "index.html не найден", 404
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/api/characters")
def get_characters():
    db = get_db()
    chars = [{"id": k, "name": v["name"], "avatar": v["avatar"], "tagline": v["tagline"], "category": v["category"], "welcome": v["welcome"], "author": "Noglik"} for k, v in CHARACTERS.items()]
    custom = db.execute("SELECT * FROM custom_characters").fetchall()
    for c in custom:
        chars.append({"id": c["id"], "name": c["name"], "avatar": c["avatar"], "tagline": c["tagline"], "category": "new", "author": c["author_name"], "welcome": "Привет! Я " + c["name"] + "."})
    return jsonify(chars)

@app.post("/api/characters")
def create_character():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    data = request.json or {}
    cid = "custom_" + secrets.token_hex(4)
    db = get_db()
    db.execute('INSERT INTO custom_characters (id, name, tagline, avatar, prompt, author_id, author_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (cid, data.get("name"), data.get("tagline"), data.get("avatar"), data.get("prompt"), user["id"], user["username"], datetime.utcnow().isoformat()))
    db.execute("INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)", (cid,))
    db.commit()
    return jsonify({"success": True, "id": cid})

@app.post("/chat")
def chat():
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "")
    character_id = body.get("character_id")
    db = get_db()
    system_prompt = ""
    if character_id in CHARACTERS:
        system_prompt = CHARACTERS[character_id]["prompt"]
    else:
        c = db.execute("SELECT prompt FROM custom_characters WHERE id = ?", (character_id,)).fetchone()
        if c: system_prompt = c["prompt"]
        else: return jsonify({"ok": False, "error": "Персонаж не найден"}), 404
    user = get_current_user() 
    try:
        answer = call_gemini(api_key, body.get("messages", []), system_prompt)
        if user:
            db.execute("UPDATE character_stats SET total_messages = total_messages + 1 WHERE character_id = ?", (character_id,))
            inter = db.execute("SELECT 1 FROM user_character_interactions WHERE user_id = ? AND character_id = ?", (user["id"], character_id)).fetchone()
            if not inter:
                db.execute("INSERT INTO user_character_interactions (user_id, character_id) VALUES (?, ?)", (user["id"], character_id))
                db.execute("UPDATE character_stats SET unique_users = unique_users + 1 WHERE character_id = ?", (character_id,))
            db.commit()
        return jsonify({"ok": True, "reply": answer})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

@app.get("/api/character_stats/<char_id>")
def get_char_stats(char_id):
    db = get_db()
    stats = db.execute("SELECT * FROM character_stats WHERE character_id = ?", (char_id,)).fetchone()
    if not stats: return jsonify({"total_messages": 0, "unique_users": 0, "likes_count": 0})
    return jsonify(dict(stats))

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    avatar = str(data.get("avatar", ""))
    if len(username) < 3: return jsonify({"error": "Ник от 3 символов"}), 400
    if len(password) < 8: return jsonify({"error": "Пароль от 8 символов"}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password_hash, avatar, created_at) VALUES (?, ?, ?, ?)", (username, generate_password_hash(password), avatar, datetime.utcnow().isoformat()))
        db.commit()
    except sqlite3.IntegrityError: return jsonify({"error": "Никнейм занят"}), 400
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password): return jsonify({"error": "Неверный никнейм или пароль"}), 401
    token = secrets.token_hex(32)
    db.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"token": token, "user": {"id": user["id"], "username": user["username"], "avatar": user["avatar"]}})

@app.route("/api/me", methods=["GET"])
def get_me():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    db = get_db()
    followers = db.execute("SELECT COUNT(*) FROM follows WHERE followee_id = ?", (user["id"],)).fetchone()[0]
    following = db.execute("SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user["id"],)).fetchone()[0]
    stats = db.execute("SELECT SUM(total_messages) as msgs, SUM(unique_users) as chats FROM character_stats").fetchone()
    return jsonify({"id": user["id"], "username": user["username"], "avatar": user["avatar"], "followers": followers, "following": following, "likes": 0, "messages_count": stats["msgs"] or 0, "chats_count": stats["chats"] or 0})

@app.route("/api/users", methods=["GET"])
def list_users():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    db = get_db()
    users = db.execute("SELECT id, username, avatar FROM users WHERE id != ?", (user["id"],)).fetchall()
    return jsonify([dict(u) for u in users])

@app.route("/api/follow", methods=["POST"])
def follow():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    target_id = request.json.get("target_id")
    if int(target_id) == user["id"]: return jsonify({"error": "Нельзя подписаться на себя"}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO follows (follower_id, followee_id) VALUES (?, ?)", (user["id"], target_id))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError: return jsonify({"error": "Уже подписаны"}), 400

@app.route("/api/messages", methods=["POST"])
def send_message():
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    to_id = request.json.get("to_id")
    text = request.json.get("text", "").strip()
    if not text: return jsonify({"error": "Пустое сообщение"}), 400
    db = get_db()
    db.execute("INSERT INTO messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)", (user["id"], to_id, text, datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"success": True})

@app.route("/api/messages/<int:other_id>", methods=["GET"])
def get_messages(other_id):
    user = get_current_user()
    if not user: return jsonify({"error": "Не авторизован"}), 401
    db = get_db()
    messages = db.execute('SELECT * FROM messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY id ASC', (user["id"], other_id, other_id, user["id"])).fetchall()
    return jsonify([dict(m) for m in messages])

init_db()
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)