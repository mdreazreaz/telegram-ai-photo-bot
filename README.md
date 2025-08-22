# Telegram AI Photo Bot (Bangla/English)
A Telegram bot that generates AI images from user scripts (Bangla or English). 
- `/start` → welcomes the user **in English by name**, then **asks for script in Bangla**.
- Generates a new image for a given script.
- Press **ENTIRE** or **GO** to get a **fresh, different** image each time.
- Each generated image shows a small **⬇️ Download** button (links to the image file on Telegram).
- Previously generated image or error **auto-vanishes** when a new command is executed.
- Errors are shown in **Bangla** if the user's script is in Bangla; otherwise in **English**, including the reason.
- Works with **OpenAI Images API** by default.

## Local Setup
1. Create a Telegram bot with **@BotFather** and copy the token.
2. Get an **OpenAI API key**.
3. Copy `.env.example` to `.env` and fill in values.
4. Create a virtual environment and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
5. Run:
   ```bash
   python app.py
   ```

## Environment Variables
Create a `.env` file with:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

## Railway Deployment (Step-by-step)
**Prereqs:** GitHub account, Railway account.

1. **Create a new GitHub repo** and push this project.
2. In **Railway**:
   - Click **New Project → Deploy from GitHub Repo**.
   - Select your repo.
3. After Railway connects, go to **Variables** and add:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
4. Railway detects Python automatically. If it asks for a start command, set:
   ```
   python app.py
   ```
   (If you use the provided `Dockerfile`, you don't need to set a start command.)
5. Click **Deploy**. Watch the logs until you see `Bot started...`.
6. Open Telegram and send `/start` to your bot.

### Notes
- This bot uses **long polling**, so no webhook is required.
- If you redeploy, the last messages are not persisted; sessions are in memory.
- To force fresh images on **ENTIRE/GO**, the bot appends an invisible variation token per click.

## Render or Other Platforms
- This repo is portable; it also includes a `Dockerfile`. Most PaaS platforms can deploy it directly.

## License
MIT
