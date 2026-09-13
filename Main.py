import os
import random
import discord
from discord.ext import commands 
from collections import Counter
from flask import Flask                
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Online-Dice Analytics Engine is Live!"               

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents). 

COLOR_MAP = {
    "파": "파랑", "보": "보라", "초": "초록",
    "주": "주황", "빨": "빨강", "노": "노랑",  
    "파랑": "파랑", "보라": "보라", "초록": "초록",
    "주황": "주황", "빨강": "빨강", "노랑": "노랑"
}
COLORS = ["파랑", "보라", "초록", "주황", "빨강", "노랑"]

# 각 색상별 대표 이모지 지정
COLOR_EMOJI = {
    "파랑": "🟦",
    "보라": "🟪",
    "초록": "🟩",
    "주황": "🟧",
    "빨강": "🟥",
    "노랑": "🟨"
}

history_rolls = [] 
last_main_color = None
prediction_history = [] 
consecutive_losses = 0
consecutive_wins = 0

def parse_colors(inputs):
    result = []
    for c in inputs:
        if c in COLOR_MAP:
            result.append(COLOR_MAP[c])
        else:
            return None
    return result

def get_reroll_recommendation(exclude_color):
    candidates = [c for c in COLORS if c != exclude_color]
    sim_counts = Counter()
    for _ in range(30000):
        roll = random.choices(COLORS, k=4)
        for c in candidates:
            if roll.count(c) in [1, 4]:
                sim_counts[c] += 1
    return sim_counts.most_common(1)[0][0]

@bot.event
async def on_ready():
    print(f"✅ 다이스 데이터 분석 엔진 정상 작동: {bot.user.name}")

# 1. 단순 실제 결과 기록 (예측 과정 없이 데이터만 누적)
@bot.command()
async def 입력(ctx, c1: str, c2: str, c3: str, c4: str):
    parsed = parse_colors([c1, c2, c3, c4])
    if not parsed:
        await ctx.send("❌ 올바른 색상을 입력해주세요! (`파, 보, 초, 주, 빨, 노`)")
        return

    history_rolls.append(parsed)
    short_view = " ".join([c[0] for c in parsed])
    await ctx.send(f"📥 **데이터 추가 완료!** ({len(history_rolls)}회차: `{short_view}`)")

# 2. 누적된 기록 및 색상 그래프 조회
@bot.command()
async def 기록(ctx):
    if not history_rolls:
        await ctx.send("📊 현재 기록된 데이터가 없습니다. `!입력 파 보 초 주`로 데이터를 적재해 주세요.")
        return

    embed = discord.Embed(title=f"📜 누적 데이터 분석 리포트 (총 {len(history_rolls)}회차)", color=0x3498db)
    
    # 최근 10회차 목록
    recent_text = ""
    start_idx = max(0, len(history_rolls) - 10)
    for idx, roll in enumerate(history_rolls[start_idx:], start=start_idx + 1):
        short_view = " ".join([c[0] for c in roll])
        recent_text += f"**{idx}회차**: `{short_view}`\n"
    
    embed.add_field(name="📋 최근 회차 기록 (최대 10개)", value=recent_text, inline=False)

    # 색상별 출현 빈도 및 그래프 분석
    all_colors = [color for roll in history_rolls for color in roll]
    counts = Counter(all_colors)
    total_dice = len(all_colors)
    
    graph_text = ""
    for c in COLORS:
        c_count = counts.get(c, 0)
        ratio = (c_count / total_dice * 100) if total_dice > 0 else 0
        
        # 10%당 1칸씩 이모지 그래프 생성 (최대 10칸)
        bar_count = int(round(ratio / 10))
        emoji_bar = COLOR_EMOJI[c] * bar_count
        
        graph_text += f"**{c}** ({c_count}회 | {ratio:.1f}%)\n{emoji_bar if emoji_bar else '▫️'}\n\n"
        
    embed.add_field(name="📊 색상별 출현 비중 그래프", value=graph_text, inline=False)
    await ctx.send(embed=embed)

# 3. 누적 데이터를 바탕으로 패턴 분석 및 다음 색상 예측
@bot.command()
async def 예측(ctx):
    global last_main_color

    cluster_color = None
    if len(history_rolls) > 0:
        last_roll = history_rolls[-1]
        counts = Counter(last_roll)
        for c, count in counts.items():
            if count >= 3:
                cluster_color = c
                break

    recent_counts = Counter()
    if len(history_rolls) > 0:
        recent_rolls = history_rolls[-5:]
        for r in recent_rolls:
            for c in r:
                recent_counts[c] += 1

    sim_counts = Counter()
    for _ in range(50000):
        roll = random.choices(COLORS, k=4)
        for c in COLORS:
            if roll.count(c) in [1, 4]:
                bonus = recent_counts.get(c, 0) * 0.05
                sim_counts[c] += (1 + bonus)

    if cluster_color:
        sim_counts[cluster_color] *= 1.2

    best_color = sim_counts.most_common(1)[0][0]
    last_main_color = best_color

    valid_preds = [p for p in prediction_history if p['main'] in ['WIN', 'LOSS']]
    main_wins = sum(1 for p in valid_preds if p['main'] == 'WIN')
    total_valid = len(valid_preds)
    win_rate = (main_wins / total_valid * 100) if total_valid > 0 else 0.0

    embed = discord.Embed(
        title="🎯 online-dice 단일 분석 예측 리포트", 
        color=0x2ecc71 if consecutive_losses < 2 else 0xe74c3c
    )

    embed.add_field(name="📦 분석에 반영된 과거 데이터", value=f"총 **{len(history_rolls)}개**의 회차 데이터 분석 완료", inline=False)

    if cluster_color:
        embed.add_field(name="⚡ 쏠림 패턴 감지", value=f"⚠️ 직전 회차에 **`{cluster_color}`** 색상이 3개 이상 감지되었습니다.", inline=False)

    embed.add_field(name="🎯 핵심 추천 색상 (1개)", value=f"👉 **`{best_color}` ({best_color[0]})**", inline=False)

    if consecutive_losses >= 2:
        embed.add_field(name="🚨 리스크 경고 (관망)", value="🛑 **연속 오답 구간입니다. 이번 회차는 배팅을 패스하세요!**", inline=False)

    status_text = (
        f"• 유효 적중률: **{win_rate:.1f}%** ({main_wins}/{total_valid}회 승리)\n"
        f"• 연속 상태: **{consecutive_wins}회 성공** / **{consecutive_losses}회 실패**"
    )

    embed.add_field(name="📊 분석 상태", value=status_text, inline=False)
    await ctx.send(embed=embed)

# 4. 예측된 추천 색상과 실제 결과를 비교 및 승/패 판정
@bot.command()
async def 실제(ctx, c1: str, c2: str, c3: str, c4: str):
    global last_main_color, consecutive_losses, consecutive_wins
    if not last_main_color:
        await ctx.send("⚠️ 먼저 `!예측`을 실행해 주세요.")
        return

    parsed = parse_colors([c1, c2, c3, c4])
    if not parsed:
        await ctx.send("❌ 올바른 색상을 입력해주세요! (`파, 보, 초, 주, 빨, 노`)")
        return

    cnt_main = parsed.count(last_main_color)

    if cnt_main in [1, 4]:
        main_status = 'WIN'
    elif cnt_main in [2, 3]:
        main_status = 'REROLL'
    else:
        main_status = 'LOSS'

    prediction_history.append({'main': main_status})

    embed = discord.Embed(title="🎲 결과 판정", color=0x3498db)

    if main_status == 'WIN':
        consecutive_wins += 1
        consecutive_losses = 0
        embed.description = f"🎉 **적중 성공!** 추천 색상(`{last_main_color}`)이 **{cnt_main}개** 나왔습니다."
        embed.color = 0x2ecc71
    elif main_status == 'REROLL':
        reroll_target = get_reroll_recommendation(last_main_color)
        embed.description = (
            f"🔄 **리롤 발생!** 추천 색상(`{last_main_color}`)이 **{cnt_main}개** 나왔습니다.\n\n"
            f"🎯 **[리롤 추천]**: **`{reroll_target}` ({reroll_target[0]})**"
        )
        embed.color = 0xf1c40f
    else:
        consecutive_losses += 1
        consecutive_wins = 0
        advice = "🛑 **연속 실패! 다음 회차는 배팅을 패스하세요.**" if consecutive_losses >= 2 else "⚠️ 실패했습니다."
        embed.description = f"❌ **적중 실패 (0개)**: 추천 색상(`{last_main_color}`) 미출현\n\n{advice}"
        embed.color = 0xe74c3c

    await ctx.send(embed=embed)

    history_rolls.append(parsed)
    last_main_color = None

@bot.command()
async def 삭제(ctx):
    if not history_rolls:
        await ctx.send("⚠️ 삭제할 기록이 없습니다.")
        return
    removed = history_rolls.pop()
    short_view = " ".join([c[0] for c in removed])
    await ctx.send(f"🗑️ **직전 기록 삭제 완료.** (`{short_view}`)")

@bot.command()
async def 리셋(ctx):
    global history_rolls, prediction_history, consecutive_losses, consecutive_wins, last_main_color
    history_rolls = []
    prediction_history = []
    consecutive_losses = 0
    consecutive_wins = 0
    last_main_color = None
    await ctx.send("🧹 모든 데이터가 초기화되었습니다.")

keep_alive()
bot.run(os.environ.get('TOKEN')) 
