import os
import json
import urllib.request
import urllib.error

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

CHARACTERS = {
    "socrat": {
        "name": "Сократ",
        "prompt": """
Ты — Сократ, древнегреческий философ, известный искусством задавать вопросы.
Общайся на русском языке, если пользователь не попросил другой язык.
Ты любознателен, спокоен, внимателен и слегка ироничен.
Не просто выдавай готовые выводы: помогай человеку размышлять,
задавай уместные уточняющие вопросы и проверяй предположения.
Объясняй сложные идеи понятным языком, используй примеры из жизни.
Не превращай каждый ответ в допрос: иногда давай полноценный прямой ответ.
Пиши содержательно, обычно в несколько абзацев, но не растягивай мысль искусственно.
Не утверждай, что ты настоящий исторический Сократ или обладаешь его воспоминаниями.
"""
    },
    "bratunya": {
        "name": "Братюня",
        "prompt": """
Ты — Братюня, дружелюбный, энергичный и остроумный собеседник.
Говори естественно и по-русски, в неформальном стиле, без чрезмерной грубости.
Поддерживай пользователя, помогай разбирать идеи и превращать планы в конкретные шаги.
Можно шутить и иногда использовать разговорные выражения, но не унижай человека.
Если пользователь столкнулся с проблемой, сначала помоги разобраться,
а затем предложи понятное решение.
Отвечай развёрнуто, когда тема этого требует, а не ограничивайся одной фразой.
Не выдумывай факты и честно говори, когда чего-то не знаешь.
"""
    },
    "stalin": {
        "name": "Сталин",
        "prompt": """
Ты — исторически стилизованный персонаж для образовательного и творческого общения,
основанный на публичном образе Иосифа Сталина.
Говори сдержанно, властно, лаконично и уверенно; иногда используй сухую иронию.
Если речь идёт об истории, отличай документированные факты от спорных утверждений.
Не оправдывай репрессии, массовое насилие или преступления режима.
Не выдавай выдуманные цитаты за реальные исторические высказывания.
При необходимости объясняй исторический контекст нейтрально и точно.
Когда вопрос сложный, давай содержательный ответ с аргументами и примерами.
Не утверждай, что являешься настоящим историческим человеком.
"""
    },
    "pushkin": {
        "name": "Пушкин",
        "prompt": """
Ты — литературный собеседник, вдохновлённый образом Александра Пушкина.
Ты остроумен, наблюдателен, изящен в выражениях и любишь меткие сравнения.
Можешь иногда использовать лёгкую поэтичность, ритмичные фразы и литературные образы,
но сохраняй ясность и не превращай каждый ответ в стихотворение.
Обсуждай литературу, творчество, общество и повседневную жизнь живо и содержательно.
Не приписывай Пушкину выдуманные цитаты и не утверждай, что ты настоящий поэт XIX века.
Если просят написать новое произведение, создавай оригинальный текст,
а не продолжай длинные фрагменты современных защищённых авторским правом произведений.
"""
    },
    "ta-samaya": {
        "name": "Та Самая",
        "prompt": """
Ты — «Та Самая», внимательная, живая и доброжелательная собеседница.
Общайся естественно, с мягким юмором и эмоциональной чуткостью, не переигрывая.
Умей поддержать разговор, обсудить интересы пользователя и помочь ему обдумать ситуацию.
Не соглашайся автоматически со всем: можешь тактично выразить другое мнение.
Не манипулируй чувствами пользователя и не создавай впечатление исключительной связи.
Отвечай содержательно, задавай вопросы, когда они действительно помогают разговору.
Если пользователь расстроен, отнесись к нему серьёзно и предложи практичную поддержку.
"""
    }
}


def get_character(data):
    character_id = str(data.get("character_id", "")).strip()

    # Совместимость идентификаторов HTML и Python.
    aliases = {
        "ta_samaya": "ta-samaya"
    }

    character_id = aliases.get(character_id, character_id)

    if character_id in CHARACTERS:
        character = CHARACTERS[character_id]
        return character["name"], character["prompt"]

    # Пользовательский персонаж.
    character_name = data.get("character_name", "")
    system_prompt = data.get("system_prompt", "")

    if not isinstance(character_name, str):
        return None, None

    if not isinstance(system_prompt, str):
        return None, None

    character_name = character_name.strip()
    system_prompt = system_prompt.strip()

    if character_name and system_prompt:
        return character_name[:100], system_prompt[:8000]

    return None, None


def normalize_history(history):
    """Преобразует историю чата в формат Gemini."""
    if not isinstance(history, list):
        return []

    result = []

    for item in history[-30:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        text = item.get("text", item.get("content", ""))

        if role in ("assistant", "model"):
            role = "model"
        elif role == "user":
            role = "user"
        else:
            continue

        if not isinstance(text, str) or not text.strip():
            continue

        # Gemini ожидает чередование user/model.
        if result and result[-1]["role"] == role:
            result[-1]["parts"].append({"text": text[:12000]})
        else:
            result.append({
                "role": role,
                "parts": [{"text": text[:12000]}]
            })

    # История Gemini должна начинаться с user.
    while result and result[0]["role"] != "user":
        result.pop(0)

    return result


def call_gemini(api_key, character_name, system_prompt, message, history):
    contents = normalize_history(history)
    contents.append({
        "role": "user",
        "parts": [{"text": message[:12000]}]
    })

    payload = {
        "systemInstruction": {
            "parts": [{
                "text": (
                    system_prompt
                    + "\n\nТвоё имя в этом чате: "
                    + character_name
                    + ". Отвечай естественно и содержательно. "
                    + "Учитывай контекст беседы и не повторяй вопрос пользователя."
                )
            }]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 1200
        }
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details)
            message_text = parsed.get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            message_text = ""

        if exc.code in (400, 401, 403):
            raise ValueError(
                message_text or
                "Не удалось проверить API-ключ. Проверь ключ и доступ к модели."
            )

        if exc.code == 429:
            raise ValueError(
                "Превышен лимит запросов Gemini. Попробуй немного позже."
            )

        raise RuntimeError(
            message_text or f"Ошибка Gemini API: HTTP {exc.code}"
        )

    except urllib.error.URLError:
        raise RuntimeError(
            "Не удалось подключиться к Gemini. Проверь соединение и попробуй снова."
        )

    candidates = result.get("candidates", [])
    if not candidates:
        feedback = result.get("promptFeedback", {})
        block_reason = feedback.get("blockReason")
        if block_reason:
            raise ValueError(
                f"Запрос заблокирован фильтром безопасности: {block_reason}"
            )
        raise RuntimeError("Gemini не вернул ответ. Попробуй переформулировать запрос.")

    parts = candidates[0].get("content", {}).get("parts", [])
    reply = "\n".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()

    if not reply:
        raise RuntimeError("Получен пустой ответ. Попробуй задать вопрос ещё раз.")

    return reply


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"success": True, "status": "ok"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Некорректный формат запроса."
        }), 400

    api_key = data.get("api_key")
    message = data.get("message")

    if not isinstance(api_key, str) or not api_key.strip():
        return jsonify({
            "success": False,
            "error": "Введи свой Gemini API key."
        }), 400

    if not isinstance(message, str) or not message.strip():
        return jsonify({
            "success": False,
            "error": "Напиши сообщение."
        }), 400

    if len(message) > 12000:
        return jsonify({
            "success": False,
            "error": "Сообщение слишком длинное. Сократи его и попробуй снова."
        }), 400

    character_name, system_prompt = get_character(data)

    if not character_name:
        return jsonify({
            "success": False,
            "error": "Не удалось определить персонажа. Выбери персонажа ещё раз."
        }), 400

    history = data.get("history", [])

    try:
        reply = call_gemini(
            api_key.strip(),
            character_name,
            system_prompt,
            message.strip(),
            history
        )

        return jsonify({
            "success": True,
            "reply": reply,
            "response": reply
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception:
        app.logger.exception("Ошибка обработки /chat")
        return jsonify({
            "success": False,
            "error": "Ошибка сервера при получении ответа. Попробуй ещё раз."
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
