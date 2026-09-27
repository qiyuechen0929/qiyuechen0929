# -*- coding: utf-8 -*-
"""📡 主页引擎：拉取实时 GitHub 数据，重绘全部数据卡并重建 README。
在 GitHub Actions 中由 GITHUB_TOKEN 驱动；本地运行需 export GITHUB_TOKEN=xxx
"""
import json, os, urllib.request, datetime, random

TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGIN = "qiyuechen0929"

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    if "errors" in d:
        raise RuntimeError(d["errors"])
    return d["data"]

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      totalCommitContributions
      contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date } } }
    }
    followers{totalCount}
    repositories(ownerAffiliations:OWNER, first:100, isFork:false){
      totalCount
      nodes{ name stargazerCount pushedAt primaryLanguage{name}
             languages(first:50){ edges{ size node{ name } } } }
    }
  }
}
"""

# ---------- SVG 工具 ----------
def svg_open(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <rect width="{w}" height="{h}" rx="14" fill="#0d1117" stroke="#30363d"/>\n')

def dot_title(x, title, color="#8b5cf6"):
    return (f'  <circle cx="{x+4}" cy="36" r="4" fill="{color}"/>\n'
            f'  <text x="{x+18}" y="41" font-family="Segoe UI,sans-serif" font-size="17" '
            f'font-weight="700" fill="#c9d1d9">{title}</text>\n')

LCOLOR = {"Python": "#3572A5", "JavaScript": "#f1e05a", "HTML": "#e34c26",
          "C": "#8a8a8a", "Kotlin": "#A97BFF", "PowerShell": "#4f8ef7",
          "C++": "#f34b7d", "TypeScript": "#3178c6", "Shell": "#89e051",
          "Batchfile": "#C1F12E", "CSS": "#663399", "Dockerfile": "#384d54"}

def stats_card(repos, stars, followers, contrib, cur, best):
    s = svg_open(420, 190) + dot_title(24, "📊 GitHub 战报")
    metrics = [(24, 68, "🗂", "公开仓库", str(repos)),
               (228, 68, "⭐", "收获 Star", str(stars)),
               (24, 126, "👥", "关注者", str(followers)),
               (228, 126, "💻", "年度贡献", str(contrib))]
    for x, y, em, label, val in metrics:
        s += (f'  <text x="{x}" y="{y}" font-size="16">{em}</text>\n'
              f'  <text x="{x+28}" y="{y}" font-family="Segoe UI,sans-serif" font-size="12" fill="#8b949e">{label}</text>\n'
              f'  <text x="{x+28}" y="{y+30}" font-family="Segoe UI,sans-serif" font-size="26" font-weight="700" fill="#e6edf3">{val}</text>\n')
    s += (f'  <text x="210" y="178" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="12" '
          f'fill="#8b949e">🔥 连续提交 {cur} 天 · 最长 {best} 天 · 建号于 2026.07</text>\n</svg>\n')
    return s

def langs_card(lb):
    top = sorted(lb.items(), key=lambda x: -x[1])[:8]
    total = sum(v for _, v in top) or 1
    maxpct = top[0][1] / total * 100 if top else 1
    s = svg_open(420, 190) + dot_title(24, "🗣 语言占比", "#58a6ff")
    y = 62
    for name, size in top:
        pct = size / total * 100
        w = max(14, 250 * pct / maxpct)
        color = LCOLOR.get(name, "#8b949e")
        s += (f'  <text x="24" y="{y+9}" font-family="Segoe UI,sans-serif" font-size="12" fill="#e6edf3">{name}</text>\n'
              f'  <rect x="112" y="{y}" width="{w:.0f}" height="10" rx="5" fill="{color}"/>\n'
              f'  <text x="396" y="{y+9}" text-anchor="end" font-family="Segoe UI,sans-serif" font-size="11" fill="#8b949e">{pct:.1f}%</text>\n')
        y += 15.5
    return s + "</svg>\n"

def achievements_card(repos, stars, nlangs):
    s = svg_open(860, 150)
    ach = [("🚀", str(repos), "公开仓库"), ("⭐", str(stars), "收获 Star"),
           ("👁", "7", "旗舰项目星数"), ("🏛", "2", "复刻中国古迹"), ("🌈", str(nlangs), "编程语言")]
    x = 25
    for em, val, label in ach:
        s += (f'  <rect x="{x}" y="16" width="160" height="118" rx="12" fill="#161b22" stroke="#30363d"/>\n'
              f'  <text x="{x+80}" y="52" text-anchor="middle" font-size="32">{em}</text>\n'
              f'  <text x="{x+80}" y="88" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="24" font-weight="700" fill="#e6edf3">{val}</text>\n'
              f'  <text x="{x+80}" y="114" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="13" fill="#8b949e">{label}</text>\n')
        x += 169
    return s + "</svg>\n"

def latest_card(latest_name, latest_url, hours_ago, contrib, cur):
    if hours_ago < 24:
        t = f"{max(1, int(hours_ago))} 小时前"
    else:
        t = f"{int(hours_ago // 24)} 天前"
    s = svg_open(860, 130) + dot_title(24, "📡 最近在做什么", "#f97316")
    s += (f'  <text x="24" y="78" font-family="Segoe UI,sans-serif" font-size="20" fill="#e6edf3">🛠 {latest_name}</text>\n'
          f'  <text x="24" y="108" font-family="Segoe UI,sans-serif" font-size="13" fill="#8b949e">'
          f'最后推动于 {t} · 本年贡献 {contrib} 次 · 当前连续 {cur} 天</text>\n</svg>\n')
    return s

def typing_url(lines):
    def q(s): return urllib.parse.quote(s, safe="")
    base = ("https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24"
            "&pause=1100&color=8B5CF6&center=true&vCenter=true&random=false&width=720&lines=")
    return base + ";".join(q(l) for l in lines)

TEMPLATE = """<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient:0x4f46e5,0x9333ea,0xec4899&height=210&section=header&text=ChenQiyue%20%E9%99%88%E5%90%AF%E7%B2%A4&fontSize=40&fontAlignY=32&desc=%E5%AD%A6%E7%94%9F%E5%BC%80%E5%8F%91%E8%80%85%20%C2%B7%20AI%20%E5%B7%A5%E5%85%B7%E6%8E%A2%E7%B4%A2%E8%80%85&descAlignY=55&descSize=17&animation=fadeIn" width="100%"/>

<div align="center">
  <a href="https://git.io/typing-svg"><img src="@@TYPING@@" alt="Typing SVG"/></a>
</div>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=qiyuechen0929&color=8B5CF6&style=flat-square&label=访客"/>
  <a href="https://github.com/qiyuechen0929?tab=followers"><img src="https://img.shields.io/github/followers/qiyuechen0929?style=flat-square&color=8B5CF6&label=关注者"/></a>
  <img src="https://img.shields.io/badge/%F0%9F%8E%93-%E5%AD%A6%E7%94%9F%E5%BC%80%E5%8F%91%E8%80%85-8B5CF6?style=flat-square"/>
  <img src="https://img.shields.io/badge/%F0%9F%93%A1-%E7%94%B1%E4%B8%BB%E9%A1%B5%E5%BC%95%E6%93%8E%E6%AF%8F6%E5%B0%8F%E6%97%B6%E9%A9%B1%E5%8A%A8-0969da?style=flat-square"/>
</p>

## 👀 关于我

- 🎓 **学生开发者**——仓库是我这两个月的成长记录，现在有 **@@REPOS@@ 个公开仓库 · @@STARS@@ 颗星**
- 👀 代表作：给纯文本 AI 装上"眼睛"的 **Vision Bridge**，让 DeepSeek 们也能看懂截图
- 🏛 最近沉迷于让 AI 在 Blender 里**实时复刻中国古迹**：天坛和佛山祖庙都盖好了
- 🈶 顺手把 Cursor、Claude Desktop 都汉化了——哪里有英文界面，哪里就有我
- ⚡ 相信一件事：**人和 AI 一起做东西，最好玩**

<div align="center">
  <img src="assets/ai-eye.svg" width="520" alt="AI 正在看你"/>
</div>

## 📡 最近动态

<div align="center">
  <img src="assets/latest-card.svg" width="86%" alt="最近动态"/>
</div>

## 🎮 主页游乐场

> 你是一名刚降落在 qiyuechen0929 主页的 AI 探险者。三条支线，各藏一个彩蛋，全部通关可解锁终极答案。

### 🏛️ 支线一 · 古迹工地

亲眼看看 AI 怎么在 Blender 里，用一条条 bpy 代码把天坛和祖庙"长"出来——白天版 + 夜景版 + 相机巡游视频，全开源：

👉 [blender-heritage-scenes](https://github.com/qiyuechen0929/blender-heritage-scenes)

**🎁 彩蛋**：下面这幅天坛夜景是**会动的**——星星会闪、流星会划过、祈年殿的窗灯在忽明忽暗（刷新页面看流星）。

### 👁️ 支线二 · AI 实验室

上面那只一直在扫描你的眼睛，出生证明在这里：[Vision Bridge](https://github.com/qiyuechen0929/vision-bridge)（7★）。
它还学会了多通道视觉降级方案：[Codex 视觉桥全攻略](https://github.com/qiyuechen0929/Common-solutions-to-fix-missing-vision-when-integrating-DeepSeek-into-Codex)。

### 🕹️ 支线三 · 街机机台

五台纯前端游戏，全部单文件、下载即玩：

| 机台 | 玩法 |
|---|---|
| [MagnetRush · 磁能狂飙](https://github.com/qiyuechen0929/MagnetRush) | 三技能 + 16 种装备 + AI 语音 |
| [GestureRacer · 手势竞速](https://github.com/qiyuechen0929/GestureRacer) | 双手手势开车，拳头是油门 |
| [GestureTree · 手势圣诞树](https://github.com/qiyuechen0929/GestureTree) | 手势切换四种照片展示模式 |
| [GestureOrbit · 全向卡牌环](https://github.com/qiyuechen0929/GestureOrbit) | 手掌就是全向摇杆 |
| [TriChessInn · 三棋小馆](https://github.com/qiyuechen0929/TriChessInn) | 象棋围棋五子棋，水墨风 AI 对弈 |

<div align="center"><sub>通关终极答案：<b>人和 AI 一起做东西，最好玩。</b></sub></div>

## 📊 GitHub 数据

<div align="center">
  <img src="assets/stats-card.svg" width="49%" alt="GitHub 战报"/>
  <img src="assets/langs-card.svg" width="49%" alt="语言占比"/>
</div>

## 🏆 成就墙

<div align="center">
  <img src="assets/achievements.svg" width="92%" alt="成就墙"/>
</div>

## 🐍 贡献贪吃蛇

<picture>
  <source media="(prefers-color-scheme: dark)" src="https://raw.githubusercontent.com/qiyuechen0929/qiyuechen0929/output/github-contribution-grid-snake-dark.svg"/>
  <img src="https://raw.githubusercontent.com/qiyuechen0929/qiyuechen0929/output/github-contribution-grid-snake.svg" width="100%"/>
</picture>

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient:0xec4899,0x9333ea,0x4f46e5&height=130&section=footer" width="100%"/>

<div align="center">
  <b>人和 AI 一起做东西，最好玩。</b><br/>
  <sub>由 📡 主页引擎每 6 小时自动驱动 · 用 ZCode(GLM) + Blender 5.0 建成</sub>
</div>
"""

def main():
    data = gql(QUERY, {"login": LOGIN})["user"]
    cal = data["contributionsCollection"]["contributionCalendar"]
    contrib = cal["totalContributions"]
    days = [dd["contributionCount"] for w in cal["weeks"] for dd in w["contributionDays"]]
    cur = 0
    for c in reversed(days):
        if c > 0: cur += 1
        else: break
    best = bc = 0
    for c in days:
        bc = bc + 1 if c > 0 else 0
        best = max(best, bc)
    repos = data["repositories"]
    nodes = repos["nodes"]
    stars = sum(n["stargazerCount"] for n in nodes)
    followers = data["followers"]["totalCount"]
    lb = {}
    for n in nodes:
        for e in n["languages"]["edges"]:
            lb[e["node"]["name"]] = lb.get(e["node"]["name"], 0) + e["size"]
    latest = max((n for n in nodes if n["name"] != LOGIN), key=lambda n: n["pushedAt"], default=None)
    pushed = datetime.datetime.fromisoformat(latest["pushedAt"].replace("Z", "+00:00")) if latest else None
    hours = (datetime.datetime.now(datetime.timezone.utc) - pushed).total_seconds() / 3600 if pushed else 999

    os.makedirs("assets", exist_ok=True)
    open("assets/stats-card.svg", "w", encoding="utf-8").write(stats_card(repos["totalCount"], stars, followers, contrib, cur, best))
    open("assets/langs-card.svg", "w", encoding="utf-8").write(langs_card(lb))
    open("assets/achievements.svg", "w", encoding="utf-8").write(achievements_card(repos["totalCount"], stars, len(lb)))
    if latest:
        open("assets/latest-card.svg", "w", encoding="utf-8").write(
            latest_card(latest["name"], "", hours, contrib, cur))

    lines = ["你好，我是陈启粤 👋",
             f"学生开发者 · 仓库 {repos['totalCount']} · Star {stars}",
             "给 AI 装上\"眼睛\" · 让工具说中文",
             f"年度贡献 {contrib} 次 · 正在盖天坛 🏛️",
             "相信人和 AI 一起做东西，最好玩"]
    readme = TEMPLATE.replace("@@TYPING@@", typing_url(lines))
    readme = readme.replace("@@REPOS@@", str(repos["totalCount"])).replace("@@STARS@@", str(stars))
    open("README.md", "w", encoding="utf-8").write(readme)
    print(f"generated: repos={repos['totalCount']} stars={stars} contrib={contrib} streak={cur}")

if __name__ == "__main__":
    main()
