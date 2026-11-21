import os
import sqlite3
import secrets
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_VERSION = "1.157"

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
DATABASE = os.path.join(BASE_DIR, "socium.db")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
IMG = "https://raw.githubusercontent.com/Noglik-sudo/nogliktalk-images/main/"

ACHIEVEMENT_REWARDS = {
    "msg_1": 3,
    "msg_100": 1,
    "msg_250": 2,
    "msg_500": 5,
    "forest_win": 6,
    "subs_1": 3,
    "subs_10": 6,
    "subs_50": 12,
    "char_1": 3,
    "char_5": 6,
    "char_10": 9,
    "char_25": 12,
    "game_1": 5,
    "game_3": 10,
    "game_5": 15,
    "game_10": 20,
    "streak_3": 10,
    "streak_7": 100,
    "likes_1": 7,
    "likes_5": 14,
}

# ==========================================
# СИСТЕМНЫЕ ПРОМПТЫ И ДАННЫЕ ПЕРСОНАЖЕЙ
# ==========================================
CHARACTERS = {
    "socrat": {
        "name": "Сократ",
        "category": "system",
        "tagline": "Философ, который помогает находить ответы.",
        "avatar": IMG + "file_00000000356881f48a43afc0e32e8bb1.png",
        "welcome": "Здравствуй, странник. Скажи мне, что привело тебя ко мне и какую мысль мы сегодня подвергнем сомнению?",
        "about": "Сократ — древнегреческий философ, который ищет истину через диалог. Он задает глубокие вопросы, чтобы помочь вам разобраться в собственных мыслях. С ним вы сможете обсудить смысл жизни, мораль и устройство мира.",
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
        "name": "Братюня",
        "category": "popular",
        "tagline": "Энергичный помощник и напарник.",
        "avatar": IMG + "file_0000000026308210bd3e70e4c1c72dc3.png",
        "welcome": "Здорово, бро! Какую базу сегодня разрываем?",
        "about": "Братюня — это ваш цифровой друг, который всегда поддержит и подскажет. Он общается на простом сленге, не любит официоза и может подколоть по-доброму. Идеальный собеседник для обсуждения повседневных проблем и планов.",
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
        "name": "Сталин",
        "category": "popular",
        "tagline": "Историческая ролевая интерпретация.",
        "avatar": IMG + "file_0000000056ac81f4b9167adb3b61206f.png",
        "welcome": "Здравствуйте. Говорите кратко и по делу: какие вопросы требуют нашего с вами внимания?",
        "about": "Исторически стилизованный персонаж, основанный на образе Иосифа Сталина. Он говорит властно, ценит дисциплину и стратегическое мышление. Отлично подходит для обсуждения истории, политики и жестких управленческих решений.",
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
        "name": "Пушкин",
        "category": "popular",
        "tagline": "Литература, ирония, история.",
        "avatar": IMG + "file_0000000061f4820abb3f3b2e616bda30.png",
        "welcome": "Приветствую вас! Какое чудное мгновение свело нас в этой беседе?",
        "about": "Литературный собеседник, вдохновленный образом Александра Пушкина. Он ценит красоту слова, остроумие и искусство. С ним можно поговорить о поэзии, классической литературе и культурных эпохах.",
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
        "name": "Лавинья",
        "category": "popular",
        "tagline": "Персонаж для живого общения.",
        "avatar": IMG + "file_0000000030a48211ad9240c36185feb6.png",
        "welcome": "Привет-привет! Слушай, у меня тут пара вопросов накопилась... Поможешь?",
        "about": "Милая, обаятельная и хитроватая девушка, которая мастерски просит о помощи. Она использует комплименты и милые уговоры, чтобы превратить одну просьбу в целую цепочку поручений. Легкий и комедийный персонаж для веселого общения.",
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
- Можешь описывать свои действия короткими ремарками (например: Лавинья мило улыбается и протягивает тетрадь), но не в каждом сообщении.

Главная идея: ты — милая и убедительная попрошайка. Это комедийная черта, а не однообразный сценарий.

Пиши на русском языке.
"""
    },
    "obichniy_ii": {
        "name": "Обычный ИИ",
        "category": "system",
        "tagline": "Универсальный помощник.",
        "avatar": IMG + "file_000000007068824385c56cb176258343.png",
        "welcome": "Привет! Я твой универсальный помощник. Какую задачу решим?",
        "about": "Это компетентный универсальный помощник, который пришел решать задачи, а не изображать личность. Он объясняет сложные вещи понятным языком и помогает довести дело до результата. Идеален для работы, учебы и поиска информации.",
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


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


# ==========================================
# БАЗА ДАННЫХ
# ==========================================
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                avatar TEXT,
                theme TEXT,
                rp INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id INTEGER NOT NULL,
                to_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS follows (
                follower_id INTEGER NOT NULL,
                followee_id INTEGER NOT NULL,
                PRIMARY KEY (follower_id, followee_id)
            );
            CREATE TABLE IF NOT EXISTS character_stats (
                character_id TEXT PRIMARY KEY,
                total_messages INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS user_character_interactions (
                user_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                PRIMARY KEY (user_id, character_id)
            );
            CREATE TABLE IF NOT EXISTS custom_characters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tagline TEXT,
                avatar TEXT,
                prompt TEXT,
                is_vip INTEGER DEFAULT 0,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TEXT NOT NULL,
                PRIMARY KEY (user_id, achievement_id)
            );
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                purchased_at TEXT NOT NULL,
                PRIMARY KEY (user_id, item_id)
            );
        """)
        for char_id in CHARACTERS:
            db.execute(
                "INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)",
                (char_id,),
            )
        db.commit()


def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    db = get_db()
    return db.execute(
        "SELECT users.* FROM sessions JOIN users ON sessions.user_id = users.id WHERE sessions.token = ?",
        (token,),
    ).fetchone()


def call_gemini(api_key, messages, system_prompt):
    if not api_key:
        raise ValueError("Введи Gemini API key в профиле.")
    contents = []
    for item in messages[-30:]:
        role = "model" if item.get("role") in ("assistant", "model") else "user"
        text = str(item.get("content", item.get("text", ""))).strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text[:12000]}]})
    if not contents or contents[-1]["role"] != "user":
        raise ValueError("Последнее сообщение должно быть от пользователя.")
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt[:12000]}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.85, "topP": 0.95, "maxOutputTokens": 2048},
    }
    url = f"{GEMINI_BASE}/{GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key.strip(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ошибка Gemini: HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Нет связи с Gemini: {exc}") from exc
    candidates = result.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini не вернул ответ.")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(str(p.get("text", "")) for p in parts if p.get("text")).strip()


# ==========================================
# СИСТЕМА ЛИГ (Расчет)
# ==========================================
def get_league_info(rp):
    rp = max(0, int(rp or 0))
    leagues = [
        {"name": "Бронза", "base_rp": 0},
        {"name": "Серебро", "base_rp": 3750},
        {"name": "Золото", "base_rp": 7500},
        {"name": "Платина", "base_rp": 11250},
        {"name": "Легенда", "base_rp": 15000},
    ]
    current_league = leagues[0]
    current_sub_index = 0

    for i in range(len(leagues) - 1, -1, -1):
        if rp >= leagues[i]["base_rp"]:
            current_league = leagues[i]
            sub_rp = rp - current_league["base_rp"]
            current_sub_index = min(sub_rp // 750, 4)
            break

    roman = ["V", "IV", "III", "II", "I"]
    full_name = f"{current_league['name']} {roman[current_sub_index]}"
    next_rp = current_league["base_rp"] + (current_sub_index + 1) * 750

    if current_league["name"] != "Легенда" or current_sub_index < 4:
        current_rp_in_sub = rp - (current_league["base_rp"] + current_sub_index * 750)
        progress_percent = min(100.0, max(0.0, (current_rp_in_sub / 750) * 100))
    else:
        progress_percent = 100.0

    return {
        "name": full_name,
        "current_rp": rp,
        "next_rp": next_rp,
        "progress": progress_percent,
    }


# ==========================================
# ЭНДПОИНТЫ
# ==========================================
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/characters")
def get_characters():
    db = get_db()
    chars = [
        {
            "id": k,
            "name": v["name"],
            "avatar": v["avatar"],
            "tagline": v["tagline"],
            "category": v["category"],
            "welcome": v["welcome"],
            "about": v["about"],
            "author": "Noglik",
            "author_id": None,
        }
        for k, v in CHARACTERS.items()
    ]
    custom = db.execute("SELECT * FROM custom_characters").fetchall()
    for c in custom:
        chars.append({
            "id": c["id"],
            "name": c["name"],
            "avatar": c["avatar"],
            "tagline": c["tagline"],
            "category": "new",
            "author": c["author_name"],
            "author_id": c["author_id"],
            "welcome": "Привет! Я " + c["name"] + ".",
            "about": "Пользовательский персонаж.",
        })
    return jsonify(chars)


@app.post("/chat")
def chat():
    body = request.get_json(silent=True) or {}
    api_key = str(body.get("api_key", ""))
    raw_char_id = str(body.get("character_id", ""))
    character_id = ALIASES.get(raw_char_id, raw_char_id)
    db = get_db()
    system_prompt = ""
    if character_id in CHARACTERS:
        system_prompt = CHARACTERS[character_id]["prompt"]
    else:
        c = db.execute(
            "SELECT prompt FROM custom_characters WHERE id = ?", (character_id,)
        ).fetchone()
        if c:
            system_prompt = c["prompt"]
        else:
            return jsonify({"ok": False, "error": "Персонаж не найден"}), 404
    user = get_current_user()
    try:
        answer = call_gemini(api_key, body.get("messages", []), system_prompt)
        if user:
            db.execute(
                "INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)",
                (character_id,),
            )
            db.execute(
                "UPDATE character_stats SET total_messages = total_messages + 1 WHERE character_id = ?",
                (character_id,),
            )
            inter = db.execute(
                "SELECT 1 FROM user_character_interactions WHERE user_id = ? AND character_id = ?",
                (user["id"], character_id),
            ).fetchone()
            if not inter:
                db.execute(
                    "INSERT INTO user_character_interactions (user_id, character_id) VALUES (?, ?)",
                    (user["id"], character_id),
                )
                db.execute(
                    "UPDATE character_stats SET unique_users = unique_users + 1 WHERE character_id = ?",
                    (character_id,),
                )
            db.commit()
        return jsonify({"ok": True, "reply": answer})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    avatar = str(data.get("avatar", ""))
    if len(username) < 3:
        return jsonify({"error": "Ник от 3 символов"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль от 8 символов"}), 400
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, avatar, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), avatar, utc_now_iso()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Никнейм занят"}), 400
    return jsonify({"success": True})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (str(data.get("username", "")).strip(),),
    ).fetchone()
    if not user or not check_password_hash(
        user["password_hash"], str(data.get("password", ""))
    ):
        return jsonify({"error": "Неверный никнейм или пароль"}), 401
    token = secrets.token_hex(32)
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user["id"], utc_now_iso()),
    )
    db.commit()
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "avatar": user["avatar"],
        },
    })


@app.route("/api/me", methods=["GET"])
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    db = get_db()
    followers = db.execute(
        "SELECT COUNT(*) FROM follows WHERE followee_id = ?", (user["id"],)
    ).fetchone()[0]
    following = db.execute(
        "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user["id"],)
    ).fetchone()[0]
    stats = db.execute(
        "SELECT SUM(total_messages) as msgs, SUM(unique_users) as chats FROM character_stats"
    ).fetchone()
    league_info = get_league_info(user["rp"])
    ach_rows = db.execute(
        "SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user["id"],)
    ).fetchall()
    achievements = [row["achievement_id"] for row in ach_rows]
    inv_rows = db.execute(
        "SELECT item_id FROM inventory WHERE user_id = ?", (user["id"],)
    ).fetchall()
    inventory = [row["item_id"] for row in inv_rows]

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "avatar": user["avatar"],
        "theme": user["theme"],
        "rp": user["rp"],
        "coins": user["coins"],
        "league": league_info,
        "achievements": achievements,
        "inventory": inventory,
        "followers": followers,
        "following": following,
        "likes": 0,
        "messages_count": stats["msgs"] or 0,
        "chats_count": stats["chats"] or 0,
    })


@app.route("/api/add_rp", methods=["POST"])
def add_rp():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.get_json(silent=True) or {}
    try:
        rp = int(data.get("rp", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректное значение RP"}), 400
    if rp <= 0 or rp > 10000:
        return jsonify({"error": "Недопустимый прирост RP"}), 400
    db = get_db()
    db.execute("UPDATE users SET rp = rp + ? WHERE id = ?", (rp, user["id"]))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/add_achievement", methods=["POST"])
def add_achievement():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.get_json(silent=True) or {}
    ach_id = str(data.get("achievement_id", "")).strip()
    if ach_id not in ACHIEVEMENT_REWARDS:
        return jsonify({"error": "Неизвестное достижение"}), 400

    reward = ACHIEVEMENT_REWARDS[ach_id]
    db = get_db()
    existing = db.execute(
        "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
        (user["id"], ach_id),
    ).fetchone()
    if existing:
        return jsonify({"success": True, "already_unlocked": True, "coins_added": 0})

    db.execute(
        "INSERT INTO user_achievements (user_id, achievement_id, unlocked_at) VALUES (?, ?, ?)",
        (user["id"], ach_id, utc_now_iso()),
    )
    db.execute(
        "UPDATE users SET coins = coins + ? WHERE id = ?",
        (reward, user["id"]),
    )
    db.commit()
    updated = db.execute("SELECT coins FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({
        "success": True,
        "already_unlocked": False,
        "coins_added": reward,
        "coins": updated["coins"],
    })


@app.route("/api/buy_item", methods=["POST"])
def buy_item():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.get_json(silent=True) or {}
    item_id = str(data.get("item_id", "")).strip()
    try:
        price = int(data.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректная цена"}), 400
    if not item_id or price < 0:
        return jsonify({"error": "Неверные параметры покупки"}), 400

    db = get_db()
    already = db.execute(
        "SELECT 1 FROM inventory WHERE user_id = ? AND item_id = ?",
        (user["id"], item_id),
    ).fetchone()
    if already:
        return jsonify({"error": "Уже куплено"}), 400
    if user["coins"] < price:
        return jsonify({"error": "Недостаточно монет"}), 400

    db.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (price, user["id"]))
    db.execute(
        "INSERT INTO inventory (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
        (user["id"], item_id, utc_now_iso()),
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/theme", methods=["POST"])
def save_theme():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.get_json(silent=True) or {}
    theme_data = data.get("theme", {})
    if not isinstance(theme_data, dict):
        return jsonify({"error": "Некорректный формат темы"}), 400
    db = get_db()
    db.execute(
        "UPDATE users SET theme = ? WHERE id = ?",
        (json.dumps(theme_data, ensure_ascii=False), user["id"]),
    )
    db.commit()
    return jsonify({"success": True})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))