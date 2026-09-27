# -*- coding: utf-8 -*-
import subprocess, json

def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or r.stderr).strip()
    return r.returncode, out

# ===== 真实数据 =====
d = json.load(open("gh_data.json", encoding="utf-8"))["data"]["user"]
repos = d["repositories"]["totalCount"]
stars = sum(r["stargazerCount"] for r in d["repositories"]["nodes"])
followers = d["followers"]["totalCount"]
contrib = d["contributionsCollection"]["contributionCalendar"]["totalContributions"]
cal = d["contributionsCollection"]["contributionCalendar"]
days = [dd["contributionCount"] for w in cal["weeks"] for dd in w["contributionDays"]]
cur = 0
for c in reversed(days):
    if c > 0: cur += 1
    else: break
best = bc = 0
for c in days:
    bc = bc + 1 if c > 0 else 0
    best = max(best, bc)

lb = {}
for r in d["repositories"]["nodes"]:
    for e in r["languages"]["edges"]:
        lb[e["node"]["name"]] = lb.get(e["node"]["name"], 0) + e["size"]
top = sorted(lb.items(), key=lambda x: -x[1])[:8]
total = sum(lb.values())

LCOLOR = {"Python": "#3572A5", "JavaScript": "#f1e05a", "HTML": "#e34c26",
          "C": "#8a8a8a", "Kotlin": "#A97BFF", "PowerShell": "#4f8ef7",
          "C++": "#f34b7d", "TypeScript": "#3178c6"}

def card_base(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <rect width="{w}" height="{h}" rx="14" fill="#0d1117" stroke="#30363d"/>\n')

# ===== 数据卡 =====
s = card_base(420, 190)
s += '  <circle cx="28" cy="36" r="4" fill="#8b5cf6"/>\n'
s += '  <text x="42" y="41" font-family="Segoe UI,sans-serif" font-size="17" font-weight="700" fill="#c9d1d9">GitHub 战报</text>\n'
metrics = [
    (24, 68, "🗂", "公开仓库", str(repos)),
    (228, 68, "⭐", "收获 Star", str(stars)),
    (24, 126, "👥", "关注者", str(followers)),
    (228, 126, "💻", "年度贡献", str(contrib)),
]
for x, y, emoji, label, val in metrics:
    s += f'  <text x="{x}" y="{y}" font-size="16">{emoji}</text>\n'
    s += f'  <text x="{x+28}" y="{y}" font-family="Segoe UI,sans-serif" font-size="12" fill="#8b949e">{label}</text>\n'
    s += f'  <text x="{x+28}" y="{y+30}" font-family="Segoe UI,sans-serif" font-size="26" font-weight="700" fill="#e6edf3">{val}</text>\n'
s += f'  <text x="210" y="178" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="12" fill="#8b949e">🔥 连续提交 {cur} 天 · 最长 {best} 天 · 建号于 2026.07</text>\n'
s += '</svg>\n'
open("assets/stats-card.svg", "w", encoding="utf-8").write(s)

# ===== 语言卡 =====
maxpct = top[0][1] / total * 100
s = card_base(420, 190)
s += '  <circle cx="28" cy="36" r="4" fill="#58a6ff"/>\n'
s += '  <text x="42" y="41" font-family="Segoe UI,sans-serif" font-size="17" font-weight="700" fill="#c9d1d9">语言占比</text>\n'
y = 62
for name, size in top:
    pct = size / total * 100
    color = LCOLOR.get(name, "#8b949e")
    w = max(14, 250 * pct / maxpct)
    s += f'  <text x="24" y="{y+9}" font-family="Segoe UI,sans-serif" font-size="12" fill="#e6edf3">{name}</text>\n'
    s += f'  <rect x="112" y="{y}" width="{w:.0f}" height="10" rx="5" fill="{color}"/>\n'
    s += f'  <text x="396" y="{y+9}" text-anchor="end" font-family="Segoe UI,sans-serif" font-size="11" fill="#8b949e">{pct:.1f}%</text>\n'
    y += 15.5
s += '</svg>\n'
open("assets/langs-card.svg", "w", encoding="utf-8").write(s)

# ===== 成就墙 =====
s = card_base(860, 150)
ach = [("🚀", str(repos), "公开仓库"), ("⭐", str(stars), "收获 Star"),
       ("👁", "7", "旗舰项目星数"), ("🏛", "2", "复刻中国古迹"), ("🌈", str(len(lb)), "编程语言")]
x = 25
for emoji, val, label in ach:
    s += f'  <rect x="{x}" y="16" width="160" height="118" rx="12" fill="#161b22" stroke="#30363d"/>\n'
    s += f'  <text x="{x+80}" y="52" text-anchor="middle" font-size="32">{emoji}</text>\n'
    s += f'  <text x="{x+80}" y="88" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="24" font-weight="700" fill="#e6edf3">{val}</text>\n'
    s += f'  <text x="{x+80}" y="114" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="13" fill="#8b949e">{label}</text>\n'
    x += 169
s += '</svg>\n'
open("assets/achievements.svg", "w", encoding="utf-8").write(s)

# ===== 更新 README（替换第三方数据卡/奖杯墙区块）=====
md = open("README.md", encoding="utf-8").read()
import re
md = re.sub(r'<div align="center">\s*<img height="165" src="https://github-readme-stats[\s\S]*?</div>',
            '<div align="center">\n  <img src="assets/stats-card.svg" width="49%" alt="GitHub 战报"/>\n  <img src="assets/langs-card.svg" width="49%" alt="语言占比"/>\n</div>', md)
md = re.sub(r'<div align="center">\s*<img src="https://streak-stats[\s\S]*?</div>', '', md)
md = md.replace("## 🏆 奖杯墙", "## 🏆 成就墙（数据实时取自本账号）")
md = re.sub(r'(<## 🏆 成就墙[^>]*>|\n)<div align="center">\s*<img src="https://github-profile-trophy[\s\S]*?</div>',
            r'\1<div align="center">\n  <img src="assets/achievements.svg" width="92%" alt="成就墙"/>\n</div>', md)
open("README.md", "w", encoding="utf-8").write(md)

print("cards generated")
print(run("git", "add", "-A")[1] or "staged")
print(run("git", "commit", "-q", "-m", "📊 用真实 GitHub 数据自绘数据卡/语言卡/成就墙（替换失效的第三方服务）")[1] or "committed")
print(run("git", "push", "-q")[1] or "pushed")
