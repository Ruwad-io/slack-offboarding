# OffBoarding

> Clean up your Slack messages before you leave.

OffBoarding is an open-source tool that lets you bulk-delete your Slack DMs and channel messages. Built for employees who want to leave a workspace cleanly, with privacy in mind.

## Features

- **OAuth login** — Sign in with Slack, no tokens to copy/paste
- **Browse conversations** — See all your DMs with message counts
- **Preview before delete** — Check what will be removed
- **Selective or bulk delete** — Pick specific conversations or nuke everything
- **Dry run mode** — Simulate without deleting anything
- **Privacy first** — No data stored on external servers, fully open source

## Quick Start

### 1. Create a Slack App

Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From an app manifest** → paste the contents of `slack-app-manifest.yml`.

Update the redirect URL to match your deployment.

### 2. Install & Run

```bash
# Clone the repo
git clone https://github.com/ruwad-io/slack-offboarding.git
cd slack-offboarding

# Install dependencies
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your Slack App credentials

# Run
python run.py
```

Open [http://localhost:5000](http://localhost:5000) and sign in with Slack.

### 3. Deploy (optional)

```bash
# With gunicorn
gunicorn "src.app:create_app()" -b 0.0.0.0:8000

# Or with Docker (coming soon)
```

## Project Structure

```
slack-offboarding/
├── src/
│   ├── app.py              # Flask app factory
│   ├── config.py           # Configuration
│   ├── routes/
│   │   ├── auth.py         # OAuth login/callback
│   │   └── main.py         # Dashboard & API endpoints
│   └── services/
│       └── slack_cleaner.py  # Core Slack API logic
├── templates/              # HTML templates
├── static/                 # CSS & JS
├── slack-app-manifest.yml  # Slack App manifest
├── pyproject.toml          # Python project config
└── run.py                  # Dev entry point
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/conversations` | List DMs with message counts |
| GET | `/api/preview/<channel_id>` | Preview messages to delete |
| POST | `/api/delete/<channel_id>` | Delete messages in one conversation |
| POST | `/api/delete-all` | Delete all DMs |

All POST endpoints accept `{ "dry_run": true }` for simulation.

## Slack App Directory

To submit to the Slack App Directory:

1. Deploy the app to a public URL (Render, Railway, Fly.io, etc.)
2. Update `slack-app-manifest.yml` with your production URL
3. Go to your app settings → **Manage Distribution** → **Submit to App Directory**
4. Follow Slack's review guidelines

## Limitations

- You can only delete **your own messages**, not other people's
- Slack API rate limits: ~50 deletions per minute
- The other person's copy of the conversation remains

## License

MIT — see [LICENSE](LICENSE)

## Built by

[Ruwad](https://github.com/ruwad) — Open source tools for a better developer experience.
