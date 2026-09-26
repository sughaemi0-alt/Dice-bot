import os
import asyncio
import math
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands

# -------------------------------------------------------------
# 1. Render 웹서버 및 UptimeRobot 24시간 유지 설정 (Flask)
# -------------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# -------------------------------------------------------------
# 2. 디스코드 봇 설정 & 전용 서버 제한 설정
# -------------------------------------------------------------
ALLOWED_SERVER_ID = 1476547550885711894

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 전역 변수
history_rolls = []
prediction_history = []
consecutive_losses = 0
consecutive_wins = 0
last_main_color = None
is_maintenance_mode = False  # 점검 모드 상태 플래그

ALL_COLORS = ['초록', '파랑', '노랑', '보라', '주황', '빨강']

@bot.event
async def on_ready():
    print(f'✅ 로그인 완료: {bot.user.name} (ID: {bot.user.id})')
    for guild in bot.guilds:
        if guild.id != ALLOWED_SERVER_ID:
            print(f"🚫 허가되지 않은 서버({guild.name}) 감지 -> 탈퇴 처리")
            await guild.leave()

@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_SERVER_ID:
        print(f"🚫 허가되지 않은 서버({guild.name}) 접속 차단 및 탈퇴.")
        await guild.leave()

# 점검 모드 전역 확인 (명령어 실행 전 차단)
@bot.before_invoke
async def check_maintenance(ctx):
    if ctx.command.name in ['start', 'stop']:
        return
    
    if is_maintenance_mode:
        await ctx.send("🛠️ **Bot usage is temporarily suspended for system maintenance.**")
        raise commands.CommandError("Maintenance mode enabled.")

# -------------------------------------------------------------
# 3. 관리자 전용 점검 명령어 (start / stop)
# -------------------------------------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def stop(ctx):
    global is_maintenance_mode
    is_maintenance_mode = True
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="🛠️ Maintenance Mode"))
    await ctx.send("🚨 **Bot usage is temporarily suspended for system maintenance.**")

@bot.command()
@commands.has_permissions(administrator=True)
async def start(ctx):
    global is_maintenance_mode
    is_maintenance_mode = False
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(name="🎲 다이스 분석 중"))
    await ctx.send("✅ **The bot is back to normal operation and ready to process commands.**")

@start.error
@stop.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⚠️ You do not have administrator permissions to use this command.")

# -------------------------------------------------------------
# 4. 정밀 확률 통계 분석 알고리즘
# -------------------------------------------------------------
def parse_colors(colors_list):
    color_map = {
        '초': '초록', '파': '파랑', '노': '노랑', '보': '보라', '주': '주황', '빨': '빨강',
        '초록': '초록', '파랑': '파랑', '노랑': '노랑', '보라': '보라', '주황': '주황', '빨강': '빨강'
    }
    parsed = []
    for c in colors_list:
        clean_c = c.strip()
        if clean_c in color_map:
            parsed.append(color_map[clean_c])
    return parsed

def calculate_advanced_prediction():
    """
    최근 트렌드 가중치 + 미출현(지연) 가중치 + 직전 연달아 나온 패턴 밸런싱 알고리즘
    """
    if not history_rolls:
        return None, 0, 0

    total_turns = len(history_rolls)
    color_scores = {color: 0.0 for color in ALL_COLORS}
    last_seen = {color: 999 for color in ALL_COLORS}  # 몇 회차 동안 안 나왔는지

    # 1. 최근 회차 가중치 점수 산출 (최근일수록 높은 가중치)
    for idx, roll in enumerate(history_rolls):
        recency_weight = math.pow(1.15, idx)  # 최근 회차일수록 exponencial 가중치
        for color in roll:
            if color in color_scores:
                color_scores[color] += recency_weight

    # 2. 미출현 회차(Gap) 계산
    for idx, roll in enumerate(reversed(history_rolls)):
        for color in ALL_COLORS:
            if color in roll and last_seen[color] == 999:
                last_seen[color] = idx

    # 3. 미출현 지연 보정 및 과도한 빈도 밸런싱
    for color in ALL_COLORS:
        gap = last_seen[color]
        if gap >= 3:
            color_scores[color] += (gap * 1.5)  # 3회차 이상 안 나온 색상 보정 점수 부여
        
        # 직전 회차에 2개 이상 몰려서 나왔다면 꺾일 확률 보정
        if history_rolls and history_rolls[-1].count(color) >= 2:
            color_scores[color] *= 0.85

    # 점수 정렬
    sorted_scores = sorted(color_scores.items(), key=lambda x: x[1], reverse=True)
    best_color = sorted_scores[0][0]
    top_score = sorted_scores[0][1]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    score_gap = top_score - second_score
    return best_color, score_gap, top_score

async def generate_prediction_report(ctx, is_auto=False):
    global history_rolls, last_main_color, consecutive_losses, consecutive_wins
    
    if len(history_rolls) < 3:
        if not is_auto:
            await ctx.send("⚠️ 정확한 분석을 위해 최소 **3회차 이상**의 데이터가 필요합니다.")
        return

    best_color, score_gap, top_score = calculate_advanced_prediction()
    last_main_color = best_color

    total_valid = consecutive_wins + consecutive_losses
    win_rate = (consecutive_wins / total_valid * 100) if total_valid > 0 else 0.0

    # 확신 타이밍 조건: 점수 차이가 크고 최근 패배가 적을 때
    is_strong_timing = (score_gap >= 3.0 or consecutive_wins >= 2) and (consecutive_losses < 2)

    if is_auto and not is_strong_timing:
        return

    # 가이드 메시지 및 상태 설정
    if consecutive_losses >= 2:
        confidence = "🛑 관망 권장 (위험)"
        guide_msg = "🚨 **연속 오답 구간입니다!** 수렴 주기 조정 중이므로 이번 회차는 배팅하지 말고 패스하세요."
        embed_color = 0xe74c3c
    elif is_strong_timing:
        confidence = "🔥 무조건 추천 (정밀 포착!)"
        guide_msg = f"⚡ **[ {best_color} ]** 출현 패턴 조건이 완벽히 맞물렸습니다! 이번 타이밍 진입을 강추합니다."
        embed_color = 0x2ecc71
    else:
        confidence = "🟢 일반 참고"
        guide_msg = f"👍 현재 통계상 가장 유력한 색상은 **[ {best_color} ]** 입니다."
        embed_color = 0x3498db

    title_prefix = "🚨 [자동 감지] " if is_auto else ""
    embed = discord.Embed(title=f"🎯 {title_prefix}online-dice 정밀 예측 리포트", color=embed_color)
    embed.add_field(name="📦 분석 회차", value=f"총 **{len(history_rolls)}**회차 패턴 분석", inline=True)
    embed.add_field(name="📊 최근 실적", value=f"적중률 **{win_rate:.1f}%** ({consecutive_wins}승/{consecutive_losses}패)", inline=True)
    
    embed.add_field(name="🎯 AI 추천 색상", value=f"👉 `{best_color}`", inline=False)
    embed.add_field(name="🔥 봇의 확신도", value=f"**{confidence}**", inline=False)
    embed.add_field(name="💡 베팅 가이드", value=guide_msg, inline=False)
    
    await ctx.send(embed=embed)

# -------------------------------------------------------------
# 5. 명령어 처리 로직
# -------------------------------------------------------------
@bot.command()
async def 입력(ctx, c1: str, c2: str, c3: str, c4: str):
    global history_rolls
    parsed = parse_colors([c1, c2, c3, c4])
    if len(parsed) != 4:
        await ctx.send("⚠️ 색상 4개를 정확히 입력해 주세요. (예: `!입력 초 파 노 보`)")
        return
    
    history_rolls.append(parsed)
    await ctx.send(f"📊 데이터 추가 완료! ({len(history_rolls)}회차: {' '.join(parsed)})")
    
    await generate_prediction_report(ctx, is_auto=True)

@bot.command()
async def 예측(ctx):
    await generate_prediction_report(ctx, is_auto=False)

@bot.command()
async def 실제(ctx, c1: str, c2: str, c3: str, c4: str):
    global last_main_color, consecutive_losses, consecutive_wins
    if not last_main_color:
        await ctx.send("⚠️ 먼저 `!예측` 또는 자동 예측 알림을 확인해 주세요.")
        return

    parsed = parse_colors([c1, c2, c3, c4])
    if len(parsed) != 4:
        await ctx.send("⚠️ 결과 색상 4개를 입력해 주세요.")
        return

    history_rolls.append(parsed)
    
    if last_main_color in parsed:
        consecutive_wins += 1
        consecutive_losses = 0
        embed = discord.Embed(title="🎉 예측 성공!", description=f"추천 색상 `{last_main_color}`이(가) 출현했습니다.", color=0x2ecc71)
    else:
        consecutive_losses += 1
        consecutive_wins = 0
        advice = "🛑 2연패 진입! 패턴 조정을 위해 다음 회차는 관망(패스)하세요." if consecutive_losses >= 2 else "⚠️ 실패했습니다."
        embed = discord.Embed(title="❌ 예측 실패", description=f"추천 색상 `{last_main_color}` 미출현\n\n{advice}", color=0xe74c3c)

    await ctx.send(embed=embed)

@bot.command()
async def 삭제(ctx):
    global history_rolls
    if not history_rolls:
        await ctx.send("⚠️ 삭제할 기록이 없습니다.")
        return
    removed = history_rolls.pop()
    await ctx.send(f"🗑️ 직전 기록 삭제 완료. ({' '.join(removed)})")

@bot.command()
async def 리셋(ctx):
    global history_rolls, consecutive_losses, consecutive_wins, last_main_color
    history_rolls = []
    consecutive_losses = 0
    consecutive_wins = 0
    last_main_color = None
    await ctx.send("🧹 모든 데이터가 초기화되었습니다.")

keep_alive()
bot.run(os.environ.get('TOKEN'))
