# the fight

主页最上面看起来像一段普通的 profile README。它不是。

`fight-light.svg` / `fight-dark.svg` 是 31 秒的动画 SVG（纯 SMIL，没有 JavaScript），
GitHub 会把它当图片原样渲染。每个词都是独立的 `<text>`，宽度用 `textLength` 写死，
所以打斗可以踢、劈、踩在单个词上，而版面在任何操作系统上都一致。

```bash
pip install pillow
python fight/make_fight.py     # -> fight-light.svg + fight-dark.svg
```

## 改文案

`make_fight.py` 顶部的 `H1_TEXT` 和 `PARAS` 就是全部文字。但注意：
打斗是按词点名的，改文案时要一起改下面这三行，否则会 `KeyError`：

```python
_kicked = word(3, "called")                                  # 被飞踢、炸成字母的词
RD      = word(3, "Pupil.")                                  # 裂开的词（洞在这里，眼珠从这里蹦出来）
S1, S2, S3 = word(3, "bridge"), word(2, "Chinese."), word(1, "README,")   # 被刀劈成两半的三个词
```

- 第 0 行是 `~~Dear~~ ~~Diary~~`（删除线），第 1、2、3 行是正文。
- `word(行号, 词)` 里的行号就是 `PARAS` 的下标，词要**一字不差**（去掉 `**` 和 `~~` 之后）。
- 换行会改变版面宽度，但 `textLength` 会兜底，不会跑版。

## 字体

宽度是用 Pillow 量出来的（量完写死进 `textLength`）。`_font()` 会自动按平台找：
Linux 的 Liberation / Windows 的 Segoe UI / macOS 的 Helvetica。换字体只会让词的
格子宽一点点，不影响动画。

## 分镜（31 秒）

| 秒 | 发生什么 |
|---|---|
| 0.9 | 裂纹从 "Pupil." 炸开，页面发抖 |
| 1.7 | 碎裂，洞开了 |
| 1.9 | Red 从洞里爬出来，叉腰 |
| 3.9 | Red 飞踢 "called" |
| 4.5 | Ink 从天而降，指 |
| 4.8 | Red 拔刀 |
| 5.3 | Ink 瞬移到背后，戳两下 |
| 6.7 | 挥砍 / 后仰躲 |
| 7.1 | 追着劈开 "bridge," "Chinese." "README," |
| 10.5 | "Pupil." 里蹦出一只眼球，咬腿，被踢飞 |
| 12.7 | 结印，三个分身 |
| 14.1 | 激光横扫 |
| 16.9 | 飞吻、爱心、蓄力 |
| 19.6 | 超级一拳 |
| 21.0 | 像素方块墙、被埋、镐子挖出来 |
| 24.0 | 领域展开 · 无量空处 |
| 25.4 | 虚空吞页，然后自愈 |
| 28.1 | 收进掌心，干净的一页 |

## 署名

整套打斗动画改编自 **[@bulletchicken](https://github.com/bulletchicken/bulletchicken)** 的
`fight/make_fight.py`（原版作者 Jeremy，仓库没有附许可证）。这里只换了文案、字体加载方式，
并把原来那只泰迪熊换成了从 "Pupil." 里蹦出来的眼球。原版是他的作品，喜欢就去给他点星。
