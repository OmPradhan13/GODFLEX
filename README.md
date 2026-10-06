# GODFLEX

Production-oriented persistence, API quota protection, and Telegram human-in-the-loop approval.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` in `.env`.

## Run

Terminal 1 — Telegram approval bot:

```bash
python telegram_hitl.py
```

Terminal 2 — GODFLEX CLI:

```bash
python main.py
```

Or Streamlit:

```bash
streamlit run app.py
```

## Behavior

- SQLite state is stored in `data/godflex.db`.
- Chat history and plans survive restarts.
- Task metadata/status survives restarts.
- A running Python worker cannot be resumed after a process crash because Python callables are not serializable; such tasks are restored as `waiting_approval` and require a worker to be reattached.
- Gemini `generate_content` calls made through `GODFLEXRuntime` are limited to 1,500/day with a persistent minimum 4-second interval.
- On quota exhaustion, no further Gemini request is sent and `Quota Exceeded` is logged.
- Approval-required tasks send Telegram inline Approve/Reject buttons and wait for the decision.
- Keep exactly one Telegram polling process running for the bot token.
