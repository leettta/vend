import os
import discord
from discord.ext import commands
from config import DISCORD_BOT_TOKEN, BOT_PREFIX, UPLOAD_FOLDER
from bot.views import MainVendingView, create_main_embed
from services.charge_service import ChargeService
from services.log_service import set_bot_instance

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    bot.add_view(MainVendingView())
    set_bot_instance(bot)
    print(f"[Discord Bot] Logged in as: {bot.user.name} ({bot.user.id})")
    print(f"[Discord Bot] Ready to serve vending operations.")

@bot.command(name="자판기")
@commands.has_permissions(administrator=True)
async def cmd_setup_vending(ctx: commands.Context):
    embed = create_main_embed()
    view = MainVendingView()
    await ctx.send(embed=embed, view=view)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel) and message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                ext = os.path.splitext(attachment.filename)[1]
                safe_filename = f"receipt_{message.author.id}_{int(discord.utils.utcnow().timestamp())}{ext}"
                save_path = os.path.join(UPLOAD_FOLDER, safe_filename)

                await attachment.save(save_path)

                req_no = ChargeService.attach_receipt_image(message.author.id, safe_filename)
                if req_no:
                    async for msg in message.channel.history(limit=15):
                        if msg.author == bot.user and msg.embeds:
                            if msg.embeds[0].title == "💳 충전 신청 접수 및 입금 안내":
                                try:
                                    await msg.delete()
                                except Exception:
                                    pass

                    embed = discord.Embed(
                        title="📸 영수증 등록 완료",
                        description=f"신청 번호 **{req_no}**의 영수증이 성공적으로 등록되었습니다.\n보안을 위해 이전 계좌 정보는 삭제되었습니다.\n\n**관리자 확인 후 잔액이 지급될 때까지 잠시만 승인을 기다려주세요.**",
                        color=0x57F287
                    )
                    await message.channel.send(embed=embed)
                    return
                else:
                    embed = discord.Embed(
                        title="⚠️ 대기 중인 충전 신청 없음",
                        description="현재 대기 중인 충전 신청 내역이 없습니다.\n서버의 자판기 패널에서 [충전] 버튼을 먼저 눌러 신청해주세요.",
                        color=0xED4245
                    )
                    await message.channel.send(embed=embed)
                    return

    await bot.process_commands(message)

def run_discord_bot():
    if not DISCORD_BOT_TOKEN:
        print("[Error] DISCORD_BOT_TOKEN is missing in .env file!")
        return
    bot.run(DISCORD_BOT_TOKEN)