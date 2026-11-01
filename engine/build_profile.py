# -*- coding: utf-8 -*-
"""📡 主页引擎：拉取实时 GitHub 数据，重绘全部数据卡并重建 README。
在 GitHub Actions 中由 GITHUB_TOKEN 驱动；本地运行需 export GITHUB_TOKEN=xxx
"""
import json, os, urllib.request, urllib.parse, datetime, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 仓库根目录：不管从哪儿调用都对

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

FORTUNES = ["宜 push，忌 force push。", "今天的 bug，是明天面试的素材。",
            "node_modules 删了又装，人生也是如此。", "适合在深夜重构代码，后果自负。",
            "你的 PR 会被 approve，但请先写测试。", "小心：node_modules 会越删越多。",
            "今日不宜 merge，宜摸鱼整理仓库。", "灵感余额 99%，请放心挥霍。",
            "咖啡与代码，缺一不可。", "git blame 之前，先学会原谅自己。",
            "显卡一响，黄金万两。", "改一行，修一天，也是修行。"]

def status_card():
    bars = [("🤖 AI 依赖度", 87, "#8b5cf6"), ("🏛 古迹工程进度", 100, "#f59e0b"),
            ("☕ 咖啡库存", 34, "#f97316"), ("💡 灵感余量", 99, "#22d3ee")]
    s = svg_open(520, 210) + dot_title(24, "🎛 实时状态", "#f97316")
    y = 64
    for label, val, color in bars:
        s += (f'  <text x="24" y="{y+12}" font-family="Segoe UI,sans-serif" font-size="12" fill="#e6edf3">{label}</text>\n'
              f'  <text x="496" y="{y+12}" text-anchor="end" font-family="Segoe UI,sans-serif" font-size="12" font-weight="700" fill="{color}">{val}%</text>\n'
              f'  <rect x="24" y="{y+18}" width="472" height="12" rx="6" fill="#21262d"/>\n'
              f'  <rect x="24" y="{y+18}" width="{472*val/100:.0f}" height="12" rx="6" fill="{color}"/>\n')
        if val < 100:
            s += (f'  <rect x="24" y="{y+18}" width="26" height="12" rx="6" fill="#ffffff" opacity="0.22">\n'
                  f'    <animateTransform attributeName="transform" type="translate" values="0,0;{472*val/100-26:.0f},0" dur="2.4s" repeatCount="indefinite"/>\n'
                  f'  </rect>\n')
        y += 36
    s += '  <text x="260" y="202" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="11" fill="#8b949e">以上数据由 AI 严肃编造，请勿当真</text>\n'
    return s + "</svg>\n"

def fortune_card():
    today = datetime.date.today()
    rng = random.Random(today.toordinal())
    star_n = rng.choice([3, 4, 4, 5])
    star_str = "★" * star_n + "☆" * (5 - star_n)
    text = rng.choice(FORTUNES)
    s = svg_open(420, 190) + dot_title(24, f"🔮 今日签 · {today.strftime('%m月%d日')}", "#c026d3")
    s += f'  <text x="210" y="92" text-anchor="middle" font-size="26" fill="#fbbf24">{star_str}</text>\n'
    s += f'  <text x="210" y="132" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="15" fill="#e6edf3">{text}</text>\n'
    s += f'  <text x="210" y="172" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="11" fill="#8b949e">签文由 AI 大数据（认真编的）生成 · 每日 0 点刷新</text>\n'
    return s + "</svg>\n"

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

    (ROOT / "assets").mkdir(exist_ok=True)
    open(ROOT / "assets/stats-card.svg", "w", encoding="utf-8").write(stats_card(repos["totalCount"], stars, followers, contrib, cur, best))
    open(ROOT / "assets/langs-card.svg", "w", encoding="utf-8").write(langs_card(lb))
    open(ROOT / "assets/achievements.svg", "w", encoding="utf-8").write(achievements_card(repos["totalCount"], stars, len(lb)))
    if latest:
        open(ROOT / "assets/latest-card.svg", "w", encoding="utf-8").write(
            latest_card(latest["name"], "", hours, contrib, cur))
    open(ROOT / "assets/status-card.svg", "w", encoding="utf-8").write(status_card())
    open(ROOT / "assets/fortune-card.svg", "w", encoding="utf-8").write(fortune_card())

    # 头图 hero/hero-*.svg 和这里无关：它不含实时数字，只在改文案时由 hero/make_hero.py 重新生成。
    # 这里只负责把实时数字填进模板，所以 README 的正文可以放心手写。
    star_of = {n["name"]: n["stargazerCount"] for n in nodes}
    fields = {
        "@@REPOS@@": str(repos["totalCount"]),
        "@@STARS@@": str(stars),
        "@@CONTRIB@@": str(contrib),
        "@@STREAK@@": str(cur),
        "@@BEST@@": str(best),
        "@@FOLLOWERS@@": str(followers),
        "@@VB@@": str(star_of.get("vision-bridge", 0)),
        "@@HERITAGE@@": str(star_of.get("blender-heritage-scenes", 0)),
        "@@LOOP@@": "24",
    }
    template = open(ROOT / "engine/README.template.md", encoding="utf-8").read()
    readme = template
    for k, v in fields.items():
        readme = readme.replace(k, v)
    left = [k for k in fields if k in readme]
    assert not left, f"模板里还有没填的占位符: {left}"
    open(ROOT / "README.md", "w", encoding="utf-8").write(readme)
    print(f"generated: repos={repos['totalCount']} stars={stars} contrib={contrib} streak={cur}")

if __name__ == "__main__":
    main()
