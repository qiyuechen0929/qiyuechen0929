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
打斗是按词点名的，改文案时要一起改下面这行，否则会 `KeyError`：

```python
_kicked = word(3, "called")                                   # 被飞踢、炸成字母的词
RD      = word(3, "Pupil.")                                   # 裂开的词（洞在这里，眼珠从这里蹦出来）
S1, S2, S3 = word(3, "bridge"), word(2, "Chinese."), word(1, "README,")   # 被劈成两半的三个词
```

- 第 0 行是 `~~Dear~~ ~~Diary~~`（删除线），第 1、2、3 行是正文。
- `word(行号, 词)` 里的行号就是 `PARAS` 的下标，词要**一字不差**（去掉 `**` 和 `~~` 之后）。
- 换行会改变版面宽度，但 `textLength` 会兜底，不会跑版。第 4 行结尾的词决定那个洞开在哪里，
  想让洞偏右就把第 4 行写长一点。

## 字体

宽度是用 Pillow 量出来的（量完写死进 `textLength`）。`_font()` 会自动按平台找：
Linux 的 Liberation / Windows 的 Segoe UI / macOS 的 Helvetica。换字体只会让词的
格子宽一点点，不影响动画。

## 分镜（31 秒）

| 秒 | 发生什么 |
|---|---|
| 0.7 | 鼠标指针滑进来，点了一下 "Pupil." —— 页面是被点裂的 |
| 0.9 | 裂纹三个波次炸开，页面发抖 |
| 1.7 | 碎裂，洞开了 |
| 1.9 | Red 从洞里爬出来，叉腰 |
| 3.9 | Red 飞踢 "called"，字母散开 |
| 4.5 | Ink 从天而降，指 |
| 4.8 | Red 拔刀 —— 拔出来的是一根巨大的文本光标 |
| 5.3 | Ink 瞬移到背后，戳两下 |
| 6.7 | 挥砍 / 后仰躲 |
| 7.1 | 追着劈开 "bridge"、"Chinese."、"README,"，每一刀弹出 SyntaxError |
| 10.5 | "Pupil." 里蹦出一只眼球，咬腿，被踢飞 |
| 12.7 | 结印，三个分身 |
| 14.1 | 激光横扫 |
| 16.9 | 飞吻、爱心、蓄力 |
| 19.6 | 超级一拳 |
| 21.0 | 像素方块墙、被埋、镐子挖出来 |
| 25.9 | Ink 轻声说了一句 `$ rm -rf ./*` |
| 26.4 | 领域展开，虚空吞页 |
| 27.4 | 虚空里弹出终端：`$ git restore .` |
| 28.1 | 页面自愈，干净如初 |

## 隐藏彩蛋

- 开场那只鼠标是真的会点下去（有波纹），不是装饰。
- 刀是一根 I-beam 文本光标（`katana_parts()` 里改的几何），不是武士刀。
- 每个被劈开的词下面都会浮出一条红色波浪线 + `SyntaxError: unexpected token`。
- 领域展开的台词是终端命令 `$ rm -rf ./*`，页面靠 `$ git restore .` 长回来。

## 怎么定格看某一帧

```html
<script>
  const s = document.querySelector('svg');
  s.pauseAnimations();
  s.setCurrentTime(9.46);   // 第二刀劈中 "Chinese." 的瞬间
</script>
```

`--virtual-time-budget` 那个截图法时间会飘，`setCurrentTime` 才是确定的那一帧。
