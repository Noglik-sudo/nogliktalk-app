import os, re, sqlite3, secrets, json
import urllib.request, urllib.error
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_VERSION = "1.182"
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "socium.db")
IMG = "https://raw.githubusercontent.com/Noglik-sudo/nogliktalk-images/main/"
DEFAULT_AVATAR = IMG + "file_000000007068824385c56cb176258343.png"
ALLOWED_CHAR_CLASSES = {"personal", "game", "book", "movie"}

PROVIDERS = {
    "gemini": ("Gemini", "https://generativelanguage.googleapis.com/v1beta/models", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    "deepseek": ("DeepSeek", "https://api.deepseek.com/chat/completions", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
    "groq": ("Groq", "https://api.groq.com/openai/v1/chat/completions", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions", os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")),
}

ACHIEVEMENT_REWARDS = {
    "msg_1": 3, "msg_100": 1, "msg_250": 2, "msg_500": 5, "msg_1000": 10,
    "forest_win": 6, "forest_try": 2, "subs_1": 3, "subs_10": 6, "subs_50": 12,
    "char_1": 3, "char_5": 6, "char_10": 9, "char_25": 12, "char_50": 25,
    "game_1": 5, "game_3": 10, "game_5": 15, "game_10": 20, "game_20": 35,
    "streak_3": 10, "streak_7": 100, "streak_14": 150, "streak_30": 300,
    "likes_1": 7, "likes_5": 14, "likes_25": 25, "likes_100": 60,
    "rp_500": 15, "rp_2500": 40,
}

CHARACTERS = {
    "socrat": {
        "name": "Сократ", "category": "system", "char_class": "",
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
        "name": "Братюня", "category": "popular", "char_class": "",
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
        "name": "Сталин", "category": "popular", "char_class": "",
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
        "name": "Пушкин", "category": "popular", "char_class": "",
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
        "name": "Лавинья", "category": "popular", "char_class": "",
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
        "name": "Обычный ИИ", "category": "system", "char_class": "",
        "tagline": "Универсальный помощник.",
        "avatar": DEFAULT_AVATAR,
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

utc_now = lambda: datetime.now(timezone.utc).isoformat()
body_json = lambda: request.get_json(silent=True) or {}

def sanitize_api_key(key):
    s = key.strip() if isinstance(key, str) else ""
    return s if 8 <= len(s) <= 256 and not re.search(r"[\s\r\n]", s) else ""

def scrub_secrets(text, *secrets_to_hide):
    out = str(text or "")
    for s in secrets_to_hide:
        if s:
            out = out.replace(s, "[REDACTED]")
    return re.sub(r"(key=|Bearer\s+)([A-Za-z0-9_\-\.]{8,})", r"\1[REDACTED]", out)

def get_db():
    if "_database" not in g:
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row
    return g._database

@app.teardown_appcontext
def close_connection(exc):
    db = g.pop("_database", None)
    if db:
        db.close()

def count_rows(db, sql, params=()):
    return db.execute(sql, params).fetchone()[0]

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, avatar TEXT, theme TEXT, rp INTEGER DEFAULT 0, coins INTEGER DEFAULT 0, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS follows (follower_id INTEGER NOT NULL, followee_id INTEGER NOT NULL, PRIMARY KEY (follower_id, followee_id));
            CREATE TABLE IF NOT EXISTS character_stats (character_id TEXT PRIMARY KEY, total_messages INTEGER DEFAULT 0, unique_users INTEGER DEFAULT 0, likes_count INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS user_character_interactions (user_id INTEGER NOT NULL, character_id TEXT NOT NULL, PRIMARY KEY (user_id, character_id));
            CREATE TABLE IF NOT EXISTS custom_characters (id TEXT PRIMARY KEY, name TEXT NOT NULL, tagline TEXT, welcome TEXT, about TEXT, avatar TEXT, prompt TEXT, char_class TEXT DEFAULT 'personal', is_vip INTEGER DEFAULT 0, author_id INTEGER NOT NULL, author_name TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS user_achievements (user_id INTEGER NOT NULL, achievement_id TEXT NOT NULL, unlocked_at TEXT NOT NULL, PRIMARY KEY (user_id, achievement_id));
            CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER NOT NULL, item_id TEXT NOT NULL, purchased_at TEXT NOT NULL, PRIMARY KEY (user_id, item_id));
        """)
        cols = {r["name"] for r in db.execute("PRAGMA table_info(custom_characters)").fetchall()}
        for col, ddl in [("char_class", "TEXT DEFAULT 'personal'"), ("welcome", "TEXT"), ("about", "TEXT")]:
            if col not in cols:
                db.execute(f"ALTER TABLE custom_characters ADD COLUMN {col} {ddl}")
        db.executemany("INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)", [(cid,) for cid in CHARACTERS])
        db.commit()

def get_current_user():
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    return get_db().execute("SELECT users.* FROM sessions JOIN users ON sessions.user_id = users.id WHERE sessions.token = ?", (token,)).fetchone() if token else None

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Не авторизован"}), 401
        return fn(user, *args, **kwargs)
    return wrapper

def call_ai(provider, api_key, messages, system_prompt):
    label, base_url, model = PROVIDERS[provider]
    clean_key = sanitize_api_key(api_key)
    if not clean_key:
        raise ValueError(f"Укажи корректный {label} API-ключ в профиле.")

    msgs = [
        ("model" if provider == "gemini" else "assistant" if m.get("role") in ("assistant", "model") else "user",
         str(m.get("content", m.get("text", ""))).strip()[:12000])
        for m in messages[-30:]
    ]
    msgs = [(r, t) for r, t in msgs if t]
    if not msgs or msgs[-1][0] != "user":
        raise ValueError("Последнее сообщение должно быть от пользователя.")

    if provider == "gemini":
        url = f"{base_url}/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": clean_key}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt[:12000]}]},
            "contents": [{"role": r, "parts": [{"text": t}]} for r, t in msgs],
            "generationConfig": {"temperature": 0.85, "topP": 0.95, "maxOutputTokens": 2048},
        }
    else:
        url = base_url
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {clean_key}"}
        if provider == "openrouter":
            headers.update({"HTTP-Referer": "https://nogliktalk.local", "X-Title": "NoglikTalk"})
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt[:12000]}] + [{"role": r, "content": t} for r, t in msgs],
            "temperature": 0.85,
            "max_tokens": 2048,
        }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(scrub_secrets(f"Ошибка {label}: HTTP {e.code}", clean_key)) from None
    except Exception as e:
        raise RuntimeError(scrub_secrets(f"Нет связи с {label}: {e}", clean_key)) from None

    if provider == "gemini":
        cands = res.get("candidates") or []
        if not cands:
            raise RuntimeError("Gemini не вернул ответ.")
        return "\n".join(str(p.get("text", "")) for p in cands[0].get("content", {}).get("parts", []) if p.get("text")).strip()

    choices = res.get("choices") or []
    content = str((choices[0].get("message") or {}).get("content", "")).strip() if choices else ""
    if not content:
        raise RuntimeError(f"{label} вернул пустой ответ.")
    return content

def get_league_info(rp):
    rp = max(0, int(rp or 0))
    names = ["Бронза", "Серебро", "Золото", "Платина", "Легенда"]
    roman = ["V", "IV", "III", "II", "I"]
    tier = min(rp // 3750, 4)
    base_rp = tier * 3750
    sub = min((rp - base_rp) // 750, 4)
    sub_base = base_rp + sub * 750
    progress = 100.0 if (tier == 4 and sub == 4) else min(100.0, max(0.0, ((rp - sub_base) / 750) * 100))
    return {"name": f"{names[tier]} {roman[sub]}", "current_rp": rp, "next_rp": sub_base + 750, "progress": progress}

def serialize_custom_char(c):
    return {
        "id": c["id"],
        "name": c["name"],
        "avatar": c["avatar"] or DEFAULT_AVATAR,
        "tagline": c["tagline"] or "Пользовательский персонаж",
        "category": "new",
        "char_class": c["char_class"] or "personal",
        "author": c["author_name"],
        "author_id": c["author_id"],
        "welcome": (c["welcome"] or "").strip() or f"Привет! Я {c['name']}.",
        "about": (c["about"] or "").strip() or (c["tagline"] or "Пользовательский персонаж."),
    }

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/api/characters")
def get_characters():
    user = get_current_user()
    uid = user["id"] if user else None
    chars = [{"id": k, "author": "Noglik", "author_id": None, **{f: v.get(f, "") for f in ("name", "avatar", "tagline", "category", "char_class", "welcome", "about")}} for k, v in CHARACTERS.items()]
    rows = get_db().execute("SELECT * FROM custom_characters ORDER BY created_at DESC").fetchall()
    chars.extend(serialize_custom_char(c) for c in rows if (c["char_class"] or "personal") != "personal" or c["author_id"] == uid)
    return jsonify(chars)

@app.post("/chat")
def chat():
    body = body_json()
    raw_keys = {
        "gemini": str(body.get("api_key", "")),
        "deepseek": str(body.get("deepseek_key", "")),
        "groq": str(body.get("groq_key", "")),
        "openrouter": str(body.get("openrouter_key", "")),
    }
    clean_keys = {k: sanitize_api_key(v) for k, v in raw_keys.items()}
    raw_cid = str(body.get("character_id", ""))
    cid = ALIASES.get(raw_cid, raw_cid)
    db, user = get_db(), get_current_user()

    if cid in CHARACTERS:
        system_prompt = CHARACTERS[cid]["prompt"]
    else:
        c = db.execute("SELECT prompt, char_class, author_id FROM custom_characters WHERE id = ?", (cid,)).fetchone()
        if not c:
            return jsonify({"ok": False, "error": "Персонаж не найден"}), 404
        if (c["char_class"] or "") == "personal" and (not user or c["author_id"] != user["id"]):
            return jsonify({"ok": False, "error": "Доступ к личному персонажу запрещён"}), 403
        system_prompt = c["prompt"]

    provider = str(body.get("provider", "gemini")).strip().lower()
    provider = provider if provider in PROVIDERS else "gemini"

    try:
        answer = call_ai(provider, clean_keys[provider], body.get("messages", []), system_prompt)
        rp_added, total_rp, league_info = 0, None, None
        if user:
            rp_added = 5
            db.execute("UPDATE users SET rp = rp + 5 WHERE id = ?", (user["id"],))
            db.execute("INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)", (cid,))
            db.execute("UPDATE character_stats SET total_messages = total_messages + 1 WHERE character_id = ?", (cid,))
            if not db.execute("SELECT 1 FROM user_character_interactions WHERE user_id = ? AND character_id = ?", (user["id"], cid)).fetchone():
                db.execute("INSERT INTO user_character_interactions (user_id, character_id) VALUES (?, ?)", (user["id"], cid))
                db.execute("UPDATE character_stats SET unique_users = unique_users + 1 WHERE character_id = ?", (cid,))
            db.commit()
            total_rp = db.execute("SELECT rp FROM users WHERE id = ?", (user["id"],)).fetchone()["rp"]
            league_info = get_league_info(total_rp)
        return jsonify({"ok": True, "reply": answer, "rp_added": rp_added, "rp": total_rp, "league": league_info})
    except Exception as exc:
        return jsonify({"ok": False, "error": scrub_secrets(str(exc), *raw_keys.values(), *clean_keys.values())}), 400

@app.post("/api/register")
def register():
    data = body_json()
    username, password, avatar = str(data.get("username", "")).strip(), str(data.get("password", "")), str(data.get("avatar", ""))
    if not (2 <= len(username) <= 32):
        return jsonify({"error": "Ник от 2 до 32 символов"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль от 8 символов"}), 400
    if len(avatar) > 1_500_000:
        return jsonify({"error": "Слишком большой размер аватарки"}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password_hash, avatar, created_at) VALUES (?, ?, ?, ?)",
                   (username, generate_password_hash(password), avatar, utc_now()))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Никнейм занят"}), 400
    return jsonify({"success": True})

@app.post("/api/login")
def login():
    data = body_json()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (str(data.get("username", "")).strip(),)).fetchone()
    if not user or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
        return jsonify({"error": "Неверный никнейм или пароль"}), 401
    token = secrets.token_hex(32)
    db.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], utc_now()))
    db.commit()
    return jsonify({"token": token, "user": {"id": user["id"], "username": user["username"], "avatar": user["avatar"]}})

@app.get("/api/me")
@auth_required
def get_me(user):
    db, uid = get_db(), user["id"]
    return jsonify({
        "id": uid, "username": user["username"], "avatar": user["avatar"], "theme": user["theme"],
        "rp": user["rp"], "coins": user["coins"], "league": get_league_info(user["rp"]),
        "achievements": [r["achievement_id"] for r in db.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (uid,))],
        "inventory": [r["item_id"] for r in db.execute("SELECT item_id FROM inventory WHERE user_id = ?", (uid,))],
        "followers": count_rows(db, "SELECT COUNT(*) FROM follows WHERE followee_id = ?", (uid,)),
        "following": count_rows(db, "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (uid,)),
        "likes": 0,
        "messages_count": count_rows(db, "SELECT COUNT(*) FROM messages WHERE from_id = ?", (uid,)) + count_rows(db, "SELECT COUNT(*) FROM user_character_interactions WHERE user_id = ?", (uid,)),
    })

@app.post("/api/profile/update")
@auth_required
def update_profile(user):
    data, db = body_json(), get_db()
    next_name, next_avatar = user["username"], user["avatar"]
    if "username" in data:
        cand = str(data.get("username", "")).strip()
        if not (2 <= len(cand) <= 32):
            return jsonify({"error": "Имя должно быть от 2 до 32 символов"}), 400
        if db.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (cand, user["id"])).fetchone():
            return jsonify({"error": "Этот никнейм уже занят"}), 400
        next_name = cand
    if "avatar" in data:
        cand_av = str(data.get("avatar", "")).strip()
        if len(cand_av) > 1_500_000:
            return jsonify({"error": "Слишком большой размер аватарки"}), 400
        next_avatar = cand_av

    db.execute("UPDATE users SET username = ?, avatar = ? WHERE id = ?", (next_name, next_avatar, user["id"]))
    if next_name != user["username"]:
        db.execute("UPDATE custom_characters SET author_name = ? WHERE author_id = ?", (next_name, user["id"]))
    db.commit()
    return jsonify({"success": True, "username": next_name, "avatar": next_avatar})

@app.post("/api/follow")
@auth_required
def toggle_follow(user):
    try:
        target_id = int(body_json().get("user_id", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректный ID пользователя"}), 400
    if target_id <= 0 or target_id == user["id"]:
        return jsonify({"error": "Нельзя подписаться на себя"}), 400

    db = get_db()
    if not db.execute("SELECT 1 FROM users WHERE id = ?", (target_id,)).fetchone():
        return jsonify({"error": "Пользователь не найден"}), 404

    exists = db.execute("SELECT 1 FROM follows WHERE follower_id = ? AND followee_id = ?", (user["id"], target_id)).fetchone()
    if exists:
        db.execute("DELETE FROM follows WHERE follower_id = ? AND followee_id = ?", (user["id"], target_id))
    else:
        db.execute("INSERT INTO follows (follower_id, followee_id) VALUES (?, ?)", (user["id"], target_id))
    db.commit()
    return jsonify({
        "success": True,
        "followed": not exists,
        "following_count": count_rows(db, "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user["id"],)),
        "followers_count": count_rows(db, "SELECT COUNT(*) FROM follows WHERE followee_id = ?", (target_id,)),
    })

@app.get("/api/users/search")
def search_users():
    q = str(request.args.get("q", "")).strip()
    db = get_db()
    sql = "SELECT id, username, avatar, rp FROM users " + ("WHERE username LIKE ? " if q else "") + "ORDER BY rp DESC LIMIT 30"
    rows = db.execute(sql, (f"%{q}%",) if q else ()).fetchall()
    return jsonify([{"id": r["id"], "username": r["username"], "avatar": r["avatar"] or "", "rp": r["rp"] or 0} for r in rows])

@app.get("/api/users/<int:target_id>")
def get_user_profile(target_id):
    db, cur = get_db(), get_current_user()
    target = db.execute("SELECT id, username, avatar, rp FROM users WHERE id = ?", (target_id,)).fetchone()
    if not target:
        return jsonify({"error": "Пользователь не найден"}), 404
    cur_id = cur["id"] if cur else None
    char_rows = db.execute("SELECT * FROM custom_characters WHERE author_id = ? ORDER BY created_at DESC", (target_id,)).fetchall()
    created = [{k: v for k, v in serialize_custom_char(c).items() if k not in ("category", "author")}
               for c in char_rows if (c["char_class"] or "personal") != "personal" or c["author_id"] == cur_id]
    return jsonify({
        "id": target["id"], "username": target["username"], "avatar": target["avatar"] or "", "rp": target["rp"] or 0,
        "following": count_rows(db, "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (target_id,)),
        "followers": count_rows(db, "SELECT COUNT(*) FROM follows WHERE followee_id = ?", (target_id,)),
        "messages_count": count_rows(db, "SELECT COUNT(*) FROM messages WHERE from_id = ?", (target_id,)),
        "created_characters": created,
    })

@app.get("/api/direct/<int:peer_id>")
@auth_required
def get_direct_messages(user, peer_id):
    if peer_id == user["id"]:
        return jsonify({"error": "Нельзя открыть переписку с самим собой"}), 400
    db = get_db()
    peer = db.execute("SELECT id, username FROM users WHERE id = ?", (peer_id,)).fetchone()
    if not peer:
        return jsonify({"error": "Пользователь не найден"}), 404
    rows = db.execute("SELECT id, from_id, text, created_at FROM messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY id ASC LIMIT 100",
                      (user["id"], peer_id, peer_id, user["id"])).fetchall()
    return jsonify([{
        "id": r["id"], "text": r["text"], "from_me": r["from_id"] == user["id"],
        "sender": user["username"] if r["from_id"] == user["id"] else peer["username"],
        "peer_name": peer["username"], "created_at": r["created_at"],
    } for r in rows])

@app.post("/api/direct/<int:peer_id>")
@auth_required
def send_direct_message(user, peer_id):
    if peer_id == user["id"]:
        return jsonify({"error": "Нельзя написать самому себе"}), 400
    text = str(body_json().get("text", "")).strip()
    if not text or len(text) > 4000:
        return jsonify({"error": "Сообщение должно быть от 1 до 4000 символов"}), 400
    db = get_db()
    peer = db.execute("SELECT id, username FROM users WHERE id = ?", (peer_id,)).fetchone()
    if not peer:
        return jsonify({"error": "Пользователь не найден"}), 404
    now = utc_now()
    cur = db.execute("INSERT INTO messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)", (user["id"], peer_id, text, now))
    db.execute("UPDATE users SET rp = rp + 5 WHERE id = ?", (user["id"],))
    db.commit()
    return jsonify({"success": True, "rp_added": 5, "message": {"id": cur.lastrowid, "text": text, "from_me": True, "sender": user["username"], "peer_name": peer["username"], "created_at": now}})

@app.post("/api/add_rp")
@auth_required
def add_rp(user):
    try:
        rp = int(body_json().get("rp", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректное значение RP"}), 400
    if not (0 < rp <= 10000):
        return jsonify({"error": "Недопустимый прирост RP"}), 400
    db = get_db()
    db.execute("UPDATE users SET rp = rp + ? WHERE id = ?", (rp, user["id"]))
    db.commit()
    return jsonify({"success": True})

@app.post("/api/add_achievement")
@auth_required
def add_achievement(user):
    ach_id = str(body_json().get("achievement_id", "")).strip()
    if ach_id not in ACHIEVEMENT_REWARDS:
        return jsonify({"error": "Неизвестное достижение"}), 400
    db = get_db()
    if db.execute("SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user["id"], ach_id)).fetchone():
        return jsonify({"success": True, "already_unlocked": True, "coins_added": 0, "coins": user["coins"]})
    reward = ACHIEVEMENT_REWARDS[ach_id]
    db.execute("INSERT INTO user_achievements (user_id, achievement_id, unlocked_at) VALUES (?, ?, ?)", (user["id"], ach_id, utc_now()))
    db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (reward, user["id"]))
    db.commit()
    return jsonify({"success": True, "already_unlocked": False, "coins_added": reward, "coins": user["coins"] + reward})

@app.post("/api/buy_item")
@auth_required
def buy_item(user):
    data = body_json()
    item_id = str(data.get("item_id", "")).strip()
    try:
        price = int(data.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректная цена"}), 400
    if not item_id or price < 0:
        return jsonify({"error": "Неверные параметры покупки"}), 400
    db = get_db()
    if db.execute("SELECT 1 FROM inventory WHERE user_id = ? AND item_id = ?", (user["id"], item_id)).fetchone():
        return jsonify({"error": "Уже куплено"}), 400
    if user["coins"] < price:
        return jsonify({"error": "Недостаточно монет"}), 400
    db.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (price, user["id"]))
    db.execute("INSERT INTO inventory (user_id, item_id, purchased_at) VALUES (?, ?, ?)", (user["id"], item_id, utc_now()))
    db.commit()
    return jsonify({"success": True, "coins": user["coins"] - price})

@app.post("/api/theme")
@auth_required
def save_theme(user):
    theme_data = body_json().get("theme", {})
    if not isinstance(theme_data, dict):
        return jsonify({"error": "Некорректный формат темы"}), 400
    serialized = json.dumps(theme_data, ensure_ascii=False)
    if len(serialized) > 32768:
        return jsonify({"error": "Слишком большие данные темы"}), 400
    db = get_db()
    db.execute("UPDATE users SET theme = ? WHERE id = ?", (serialized, user["id"]))
    db.commit()
    return jsonify({"success": True})

@app.post("/api/characters/create")
@auth_required
def create_character(user):
    data = body_json()
    f = {k: str(data.get(k, "")).strip() for k in ("name", "tagline", "welcome", "personality", "behavior", "relation", "style", "slang", "phrases", "avatar")}
    char_class = str(data.get("char_class", "personal")).strip().lower()
    char_class = char_class if char_class in ALLOWED_CHAR_CLASSES else "personal"
    avatar = f["avatar"] or DEFAULT_AVATAR

    if len(avatar) > 1_500_000:
        return jsonify({"error": "Слишком большой размер аватарки"}), 400
    if not f["name"] or not f["personality"]:
        return jsonify({"error": "Укажи имя и характер персонажа"}), 400

    labels = [("tagline", "Кратко о тебе"), ("personality", "Характер"), ("behavior", "Поведение"),
              ("relation", "Отношение к собеседнику"), ("style", "Стиль общения"), ("slang", "Любимые словечки"), ("phrases", "Характерные фразы")]
    prompt = "\n".join([f"Ты — {f['name']}."] + [f"{lbl}: {f[k]}" for k, lbl in labels if f[k]] + ["Отвечай на русском языке, сохраняя образ."])

    cid = f"custom_{secrets.token_hex(6)}"
    tagline = f["tagline"] or "Пользовательский персонаж"
    welcome = f["welcome"] or f"Привет! Я {f['name']}."
    db = get_db()
    db.execute(
        "INSERT INTO custom_characters (id, name, tagline, welcome, about, avatar, prompt, char_class, is_vip, author_id, author_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (cid, f["name"], tagline, welcome, f["personality"], avatar, prompt, char_class, user["id"], user["username"], utc_now()),
    )
    db.execute("INSERT OR IGNORE INTO character_stats (character_id) VALUES (?)", (cid,))
    db.execute("UPDATE users SET rp = rp + 50 WHERE id = ?", (user["id"],))
    db.commit()

    return jsonify({"success": True, "character": {
        "id": cid, "name": f["name"], "char_class": char_class, "tagline": tagline, "avatar": avatar,
        "welcome": welcome, "about": f["personality"], "category": "new", "author": user["username"], "author_id": user["id"],
    }})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))