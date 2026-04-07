# OffBoarding

[![CI](https://github.com/ruwad-io/slack-offboarding/actions/workflows/ci.yml/badge.svg)](https://github.com/ruwad-io/slack-offboarding/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-purple.svg)](https://python.org)

> Clean up your Slack messages before you leave. Your messages, your choice.

OffBoarding is an open-source tool that lets you bulk-delete your Slack DMs and channel messages. Built for employees who want to leave a workspace cleanly, with privacy in mind.

**No data is ever stored or sent anywhere.** The CLI runs entirely on your machine. The web dashboard processes everything in-memory. The code is fully open source.

---

## Why?

Slack doesn't let you bulk-delete messages. When you leave a company, all your DMs stay behind — visible to workspace admins who can export them at any time. OffBoarding gives you a way to clean up before you go.

## Two ways to use it

| | CLI | Web Dashboard |
|---|---|---|
| **Best for** | Developers, power users | Non-technical users |
| **Setup** | `pip install` + paste token | Deploy to Railway + Sign in with Slack |
| **Privacy** | Runs 100% on your machine | Self-hosted, you control the server |
| **Features** | Interactive TUI, progress bars | Point-and-click UI |

---

## CLI

### Install

```bash
pip install slack-offboarding
```

Or from source:

```bash
git clone https://github.com/ruwad-io/slack-offboarding.git
cd slack-offboarding
pip install -e .
```

### Setup

```bash
offboarding login
```

This will guide you through creating a Slack App and getting your token. You'll need to:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Add the required OAuth scopes (the CLI tells you exactly which ones)
3. Install the app to your workspace
4. Paste the token

Your token is stored locally at `~/.config/offboarding/config` with `600` permissions.

### Usage

```bash
# See what you're working with
offboarding scan

# Interactive cleanup — pick conversations to clean
offboarding clean

# Clean all DMs at once
offboarding clean --all

# Simulate first (recommended)
offboarding clean --all --dry-run

# Nuclear option — wipe everything
offboarding nuke

# Check your connection
offboarding status

# Remove your saved token
offboarding logout
```

### Commands

| Command | Description |
|---|---|
| `offboarding login` | Setup wizard — guides you through getting a Slack token |
| `offboarding scan` | Scan all DMs and show a table with message counts |
| `offboarding clean` | Interactive cleanup — select which conversations to delete |
| `offboarding clean --all` | Delete messages in all DM conversations |
| `offboarding clean --dry-run` | Simulate without actually deleting |
| `offboarding nuke` | Delete everything — requires typing "DELETE EVERYTHING" |
| `offboarding status` | Show current auth status and user info |
| `offboarding logout` | Remove saved Slack token |

---

## Web Dashboard

For a point-and-click experience, deploy the web dashboard:

```bash
git clone https://github.com/ruwad-io/slack-offboarding.git
cd slack-offboarding
pip install -e .

cp .env.example .env
# Edit .env with your Slack App credentials

python run.py
```

Deploy to Railway, Render, or Fly.io for HTTPS (required by Slack OAuth).

### Railway (one-click)

1. Connect this repo in your Railway dashboard
2. Add environment variables: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SECRET_KEY`, `APP_URL`
3. Deploy — Railway detects the `railway.toml` automatically

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/conversations` | List DMs with message counts |
| GET | `/api/preview/<id>` | Preview messages to delete |
| POST | `/api/delete/<id>` | Delete messages in one conversation |
| POST | `/api/delete-all` | Delete all DMs |
| GET | `/health` | Health check |

All POST endpoints accept `{ "dry_run": true }` for simulation.

---

## FAQ

**Can I delete other people's messages?**
No. Slack's API only allows you to delete your own messages.

**Will the other person know I deleted my messages?**
The messages will disappear from the conversation, but Slack doesn't notify them.

**Does the other person still see their own messages?**
Yes. Only your messages are removed.

**Can my workspace admin recover deleted messages?**
No. Once deleted via the API, messages are permanently gone.

**Is this allowed by Slack's terms of service?**
Yes. You're using Slack's official API to delete your own messages.

**How long does it take?**
Slack rate-limits deletions to about 50 per minute. A conversation with 1,000 messages takes about 20 minutes.

---

## Project Structure

```
slack-offboarding/
├── src/
│   ├── cli.py              # Rich CLI (click + rich)
│   ├── app.py              # Flask web app
│   ├── config.py           # Configuration
│   ├── routes/
│   │   ├── auth.py         # OAuth login/callback
│   │   └── main.py         # Dashboard & API
│   └── services/
│       └── slack_cleaner.py  # Core Slack API logic
├── templates/              # HTML templates
├── static/                 # CSS & JS
├── tests/                  # Tests
├── slack-app-manifest.yml  # Slack App manifest
├── railway.toml            # Railway deployment config
├── Dockerfile              # Docker build
└── pyproject.toml          # Python project config
```

## Contributing

PRs welcome! Please open an issue first to discuss what you'd like to change.

```bash
git clone https://github.com/ruwad-io/slack-offboarding.git
cd slack-offboarding
pip install -e ".[dev]"
pytest
ruff check src/
```

## License

MIT — see [LICENSE](LICENSE)

## Built by

[Ruwad](https://github.com/ruwad-io) — Open source tools for a better developer experience.
