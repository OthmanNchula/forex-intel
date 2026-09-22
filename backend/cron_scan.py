"""
Standalone entrypoint for a Railway Cron Job.

Runs ONE signal-scan cycle and exits — it does not start the web
server or the in-process background loop. This is what guarantees
signal scanning happens on schedule, independent of whether the main
web service is idle/asleep: Railway spins up a fresh container for
this command on its own schedule, runs it to completion, then tears
it down.

Deploy as a separate "Cron Job" service in the same Railway project,
pointed at this same repo/image, with the same environment variables
as the web service (DATABASE_URL, ANTHROPIC_API_KEY, TWELVE_DATA_API_KEY,
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, UPSTASH_REDIS_REST_URL,
UPSTASH_REDIS_REST_TOKEN, etc). Suggested schedule: every 15 minutes,
e.g. "*/15 * * * *".

Start command in Railway: python cron_scan.py
"""
import asyncio

from app.services.auto_signal_engine import run_signal_scan_cycle


async def main():
    print("[CronScan] Starting scheduled scan cycle...")
    result = await run_signal_scan_cycle()
    print(f"[CronScan] Done: {result}")


if __name__ == "__main__":
    asyncio.run(main())
