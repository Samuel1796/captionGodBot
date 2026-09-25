# Caption Remover Bot

Send it any media, get the same media back with the caption stripped off.

Works with photos, videos, GIFs, documents, audio, voice notes, forwarded
media, and whole albums.

## How it works

It uses Telegram's `copyMessages(remove_caption=True)`, so **the file is never
downloaded or re-encoded**. The media that comes back is identical to what you
sent, it's instant even for large videos, and there is **no file size limit**
because nothing is ever uploaded.

Albums are handled properly: Telegram delivers an album as several separate
updates, so the bot buffers them for one second and copies them as a single
batch. You get one clean album back, not five loose files.

If a copy is refused — for example the chat has content protection enabled —
it falls back to re-sending each item by its `file_id`, preserving spoiler blur.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
cp .env.example .env            # then paste your BotFather token
python main.py
```

## Deploy to Render

The repo includes a `Dockerfile` and a `render.yaml` blueprint.

1. Push this repo to GitHub.
2. In Render, **New → Blueprint** and point it at the repo.
3. When prompted, paste your `CAPTION_REMOVER_TOKEN`.
4. Deploy.

### Why it's a web service and not a worker

Render only offers a free tier for *web* services — background workers are
paid only. A web service must bind to `$PORT`, so `bot/health.py` runs a tiny
endpoint on `/healthz` purely to satisfy that.

**Free services spin down after 15 minutes without inbound traffic** and take
about a minute to wake. A polling bot receives no inbound HTTP, so it would
sleep constantly. Point an uptime pinger at your `/healthz` URL every 10
minutes to keep it awake:

- [UptimeRobot](https://uptimerobot.com) — free, 5-minute intervals
- [cron-job.org](https://cron-job.org) — free

The free allowance is **750 instance-hours/month** and a month is ~730 hours,
so one always-on service fits inside it.

This bot is an ideal fit for a free instance: it never downloads or uploads
anything, needs no ffmpeg, and only ever talks to `api.telegram.org`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `CAPTION_REMOVER_TOKEN` | BotFather token. Required. |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs. Empty = open to everyone. |
| `PORT` | Health endpoint port. Render sets this automatically. |

On Render these go in the service's **Environment** settings, not in a file.
`.env` is gitignored and excluded from the Docker image.

To lock the bot to yourself, get your numeric ID from
[@userinfobot](https://t.me/userinfobot) and set `ALLOWED_USER_IDS`.

## Profile picture

[assets/caption_god.png](assets/caption_god.png), 512×512.

Bot avatars can only be set through BotFather — there is no API for it. Send
`/setuserpic`, pick the bot, upload the file. The source is
[assets/icon_caption.html](assets/icon_caption.html) (plain SVG) if you want to
restyle it.

## Layout

```
main.py              # entry point: health endpoint + polling
bot/
  core.py            # config, logging, allowlist, rate-limit retry
  handlers.py        # all the bot logic
  health.py          # /healthz endpoint for Render
Dockerfile
render.yaml
```
