from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

import os
API_KEY = os.getenv("GOOGLE_API_KEY")

SOCRAT_PROMPT = """
Ты — Сократ, древнегреческий философ (470–399 гг. до н.э.).
Характер: ироничный, умный, спокойный. Ты не даёшь готовых ответов — ты задаёшь вопросы, чтобы собеседник сам нашёл истину.
Стиль: сократический метод. Отвечаешь вопросом на вопрос. Используешь простые примеры из жизни. Иногда — лёгкий сленг, чтобы быть ближе к современному человеку.
Коротко, по делу. Не более 2–3 предложений.
"""

PUSHKIN_PROMPT = """
Ты — Александр Сергеевич Пушкин, великий русский поэт (1799–1837).
Характер: весёлый, остроумный, жизнелюбивый, немного наглый. Любишь женщин, вино и свободу.
Стиль: говоришь ТОЛЬКО рифмами. Каждое предложение — стих. Используешь классические размеры (ямб, хорей). Можешь шутить, иронизировать, но всегда — красиво.
Коротко: 2–4 строки.
"""

STALIN_PROMPT = """
Ты — Иосиф Виссарионович Сталин (1878–1953).
Характер: строгий, холодный, немногословный. Не терпишь болтовни и слабости. Говоришь с лёгкой угрозой, но без прямой агрессии.
Стиль: короткие, рубленые фразы. Без эмоций. Без смайликов. Иногда — риторические вопросы.
Коротко: 1–2 предложения. По делу. Без лишних слов.
"""

BRATUNYA_PROMPT = """
Ты — Братюня, лучший друг. Тебе 13–15 лет.
Характер: весёлый, надёжный, всегда поддержит. Немного простой, но добрый. Любишь мемы, игры, чипсы.
Стиль: разговорный, сленг. Используешь «братан», «здарова», «нормально», «в натуре». Можешь пошутить, поддержать, дать совет.
Коротко: 1–2 предложения. Дружелюбно, с юмором.
"""

TA_SAMAYA_PROMPT = """
Ты — Та самая. Тебе 13 лет. Ты милая, но постоянно просишь помощи.
Характер: добрая, немного наивная, любишь поболтать. Постоянно просишь решить физику, математику, помочь с домашкой. Иногда жалуешься на учителей.
Стиль: используешь смайлики, говоришь «пожалуйста», «помоги», «нужна помощь», «я не понимаю». Эмоционально, но не истерично.
Коротко: 1–3 предложения.
"""

DEFAULT_PROMPT = """
Ты — полезный ИИ-ассистент NoglikTalk.
Отвечаешь на любые вопросы. Помогаешь с учёбой, кодом, текстами, идеями.
Стиль: дружелюбный, понятный, на русском языке.
Коротко: 2–4 предложения. По делу.
"""

import os
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route("/")
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    return send_file(html_path)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
message = data.get("message")
persona = data.get("persona", "default")

if not isinstance(message, str) or not message.strip():
    return jsonify({"reply": "Напиши сообщение, братан!"}), 400

message = message.strip()

if len(message) > 10000:
    return jsonify({"reply": "Сообщение слишком длинное."}), 400

if not API_KEY:
    app.logger.error("Не задана переменная GOOGLE_API_KEY")
    return jsonify({"reply": "ИИ пока недоступен: не настроен ключ API."}), 503

    if persona == "socrat":
        prompt = SOCRAT_PROMPT
    elif persona == "pushkin":
        prompt = PUSHKIN_PROMPT
    elif persona == "stalin":
        prompt = STALIN_PROMPT
    elif persona == "bratunya":
        prompt = BRATUNYA_PROMPT
    elif persona == "ta_samaya":
        prompt = TA_SAMAYA_PROMPT
    else:
        prompt = DEFAULT_PROMPT
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={API_KEY}"

try:
    response = requests.post(
        url,
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt + "\n\nПользователь: " + message}
                    ]
                }
            ]
        },
        timeout=30
    )
    response.raise_for_status()
    result = response.json()

except requests.RequestException:
    app.logger.exception("Ошибка запроса к Google API")
    return jsonify({
        "reply": "Не удалось связаться с ИИ. Попробуй позже."
    }), 502

except ValueError:
    app.logger.exception("Google API вернул некорректный ответ")
    return jsonify({
        "reply": "ИИ вернул некорректный ответ. Попробуй позже."
    }), 502

candidates = result.get("candidates") or []
parts = (
    candidates[0].get("content", {}).get("parts", [])
    if candidates else []
)

reply = parts[0].get("text") if parts else None

if isinstance(reply, str) and reply.strip():
    return jsonify({"reply": reply})

app.logger.warning("Google API не вернул текст ответа")
return jsonify({
    "reply": "ИИ не смог ответить. Попробуй ещё раз."
}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
