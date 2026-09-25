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

### Webhook vs polling

The bot picks its mode automatically from `RENDER_EXTERNAL_URL`, which Render
sets on every web service. No configuration needed.

| Where | Mode | Why |
| --- | --- | --- |
| Render | Webhook | Telegram POSTs each update to the service |
| Local | Long polling | No public URL needed |

This matters more than it looks. Render only wakes a sleeping free instance on
**inbound** traffic. Polling is *outbound*, so a sleeping polling bot can never
be woken by someone messaging it - the message just sits in Telegram's queue
until something else happens to wake the service. A webhook is an inbound POST,
so **the message itself wakes the bot**.

Nothing is lost either way: `drop_pending_updates` is `False`, so anything
queued while the instance was asleep is delivered on wake rather than
discarded. The first message after a sleep waits about a minute while the
container starts, and the bot replies explaining the delay before handling it.

The webhook path and its secret token are derived from a SHA-256 of the bot
token, so both are unguessable and stable across restarts with nothing extra to
configure. Telegram echoes the secret back in a header, so forged POSTs are
rejected.

### Do you still need an uptime pinger?

Optional now, and there is a real trade-off:

- **Without a pinger** the service sleeps when idle and wakes on demand. The
  first message after a sleep waits ~1 minute. Uses very few instance hours.
- **With a pinger** ([UptimeRobot](https://uptimerobot.com) or
  [cron-job.org](https://cron-job.org) hitting `/healthz` every 5 minutes) it
  never sleeps and every message is instant. Uses ~730 hours a month.

The free allowance is **750 instance-hours per month across the whole
workspace**, and a month is ~730 hours. So a pinger can keep **only one**
service awake all month. If you run both bots on free instances, either ping
neither, or ping just one - pinging both exhausts the allowance around the
halfway mark and suspends everything until the next month.

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
main.py              # entry point: webhook when deployed, polling locally
bot/
  core.py            # config, logging, allowlist, rate-limit retry
  handlers.py        # all the bot logic
  health.py          # /healthz endpoint for Render
Dockerfile
render.yaml
```
