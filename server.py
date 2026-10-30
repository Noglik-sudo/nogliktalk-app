import os
import json
import urllib.request
import urllib.error
import traceback

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
        "name": "Обычный ИИ",
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


def get_character(data):
    character_id = str(data.get("character_id", "")).strip()

    aliases = {
        "ta_samaya": "lavinya",
        "ta-samaya": "lavinya"
    }
    character_id = aliases.get(character_id, character_id)

    if character_id in CHARACTERS:
        character = CHARACTERS[character_id]
        return character["name"], character["prompt"]

    character_name = data.get("character_name", "")
    system_prompt = data.get("system_prompt", "")

    if not isinstance(character_name, str) or not isinstance(system_prompt, str):
        return None, None

    character_name = character_name.strip()
    system_prompt = system_prompt.strip()

    if character_name and system_prompt:
        return character_name[:100], system_prompt[:12000]

    return None, None


def normalize_history(history):
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

        if result and result[-1]["role"] == role:
            result[-1]["parts"].append({"text": text[:12000]})
        else:
            result.append({
                "role": role,
                "parts": [{"text": text[:12000]}]
            })

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
            raise ValueError(message_text or "Не удалось проверить API-ключ. Проверьте правильность ключа.")
        if exc.code == 429:
            raise ValueError("Превышен лимит запросов Gemini. Попробуйте позже.")
        
        print(f"GEMINI API ERROR {exc.code}: {details}")
        raise RuntimeError(message_text or f"Ошибка Gemini API: HTTP {exc.code}")

    except urllib.error.URLError as e:
        print(f"GEMINI URL ERROR: {str(e)}")
        raise RuntimeError("Не удалось подключиться к Gemini. Проверьте интернет-соединение.")

    candidates = result.get("candidates", [])
    if not candidates:
        feedback = result.get("promptFeedback", {})
        block_reason = feedback.get("blockReason")
        if block_reason:
            raise ValueError(f"Запрос заблокирован фильтром безопасности: {block_reason}")
        raise RuntimeError("Gemini не вернул ответ. Попробуйте переформулировать запрос.")

    parts = candidates[0].get("content", {}).get("parts", [])
    reply = "\n".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()

    if not reply:
        raise RuntimeError("Получен пустой ответ от модели. Попробуйте ещё раз.")

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
        return jsonify({"success": False, "error": "Некорректный формат запроса."}), 400

    api_key = data.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip() or api_key.strip() == "TEST":
        api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key.strip():
        return jsonify({"success": False, "error": "Укажите ваш Gemini API key в профиле."}), 400

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "Напишите сообщение."}), 400

    if len(message) > 12000:
        return jsonify({"success": False, "error": "Сообщение слишком длинное."}), 400

    character_name, system_prompt = get_character(data)

    if not character_name:
        return jsonify({"success": False, "error": "Не удалось определить персонажа."}), 400

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
        return jsonify({"success": False, "error": str(exc)}), 400

    except Exception as e:
        print("=== SERVER ERROR ===")
        traceback.print_exc()
        print("====================")
        return jsonify({
            "success": False,
            "error": "Ошибка сервера при обработке запроса."
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
