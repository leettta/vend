import asyncio
import datetime
import discord
from database.db import get_db
from database.models import LogSetting, SystemLog

# 전역 Discord 봇 인스턴스 참조 (run.py에서 주입)
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

def send_discord_log(log_type: str, title: str, fields: dict, color: int = 0x5865F2):
    """지정된 로그 채널로 Embed를 안전하게 전송합니다."""
    if not bot_instance or not bot_instance.is_ready():
        return

    with get_db() as session:
        setting = session.query(LogSetting).filter_by(log_type=log_type).first()
        if not setting or not setting.enabled or not setting.channel_id:
            return
        target_channel_id = setting.channel_id

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    for k, v in fields.items():
        embed.add_field(name=k, value=str(v), inline=True)
    embed.set_footer(text="자판기 통합 관제 시스템")

    async def _send():
        try:
            channel = bot_instance.get_channel(target_channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[LogService] Failed to send log: {e}")

    asyncio.run_coroutine_threadsafe(_send(), bot_instance.loop)

def record_system_log(log_type: str, message: str, admin_name: str = "System"):
    with get_db() as session:
        log = SystemLog(log_type=log_type, message=message, admin_name=admin_name)
        session.add(log)