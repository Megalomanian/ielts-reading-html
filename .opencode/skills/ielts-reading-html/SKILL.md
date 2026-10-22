---
name: IELTS Reading HTML
description: 把手机拍摄的雅思阅读试卷照片整理成可交互的单文件 HTML：逐字还原文章与题目，生成中文解析并高亮关键词，点击关键词可跳回原文并精确高亮证据句。当用户提到雅思阅读、试卷照片转 HTML、阅读解析、关键词定位原文、IELTS Reading 时使用。
license: MIT
compatibility: Python 3.10+；图片预处理需要 Pillow；HTML 构建只用标准库。
metadata:
  opencode/autoinvoke: true
---

# IELTS Reading HTML

**一句话：照片 → 逐字转录 → `case.json` → 桌面分屏单文件 HTML。左边原文、右边题目与解析；答案默认展开；每题解析前先自动显示「原文回顾」证据句；关键词可点击，跳到左侧原文并精确高亮、闪动。**

## 适用场景

- 用户发来手机拍摄的雅思阅读文章/题目照片，想要一份在电脑上阅读的解析页。
- 用户想要左侧原文、右侧题目，点关键词就能定位原文的交互，而不是静态 PDF/Word。
- 用户想要把一篇或整卷阅读整理成可复习、可打印的 HTML。

不适用：

- 只有模糊到无法辨认的照片，且用户不愿重拍/补文字。
- 要求还原官方排版、图表原图或听力音频。
- 要求代考、作弊或对外发布受版权保护的真题内容。

## 输入与交付

需要向用户确认/获取：

1. 图片路径（一张或多张；可以是文件夹）。
2. 输出目录（不指定就用 `./reading-output/<slug>/`）。
3. 试卷是否附带答案页；如果有，尽量拍进来。
4. 是否需要整卷合并成一个 HTML，还是每篇一个。

交付目录：

```text
<Out>/
  source/          # 用户原图，只读，不修改
  pages/           # 预处理图 + contact-sheet.jpg
  transcript.md    # 逐页逐字转录
  case.json        # 结构化数据（唯一需要编辑的源文件）
  index.html       # 最终交互页
```

`$SkillDir` 指本 `SKILL.md` 所在目录的绝对路径。所有脚本路径都相对于它。

## 工作流（按顺序）

### 0. 建目录、保留原图

```powershell
New-Item -ItemType Directory -Force "$Out\source" | Out-Null
Copy-Item <用户图片或文件夹\*> "$Out\source\" -Recurse
```

不要移动/覆盖用户原图。后面所有处理都基于 `source/` 的副本。

### 1. 预处理照片

```powershell
python -X utf8 "$SkillDir\scripts\prepare_images.py" "$Out\source" --out "$Out\pages" --max-side 2200
```

- 先看 `pages/contact-sheet.jpg`，确认页序、重复页、缺页。
- 再逐页读 `pages/page-*.jpg` 的大图。
- 如果照片本身清晰，也可以直接读原图；但预处理能统一方向、尺寸和对比度，建议做。
- 如果当前模型不能读图，**停下来**，让用户提供文字/OCR；不要根据“雅思真题记忆”编造内容。

### 2. 逐页转录

按 `references/ocr-guide.md` 写 `transcript.md`：

- 页地图（每页包含什么、是否重叠/缺页）。
- 文章逐字转录，保留段落标签 A/B/C 和标题。
- 题目逐字转录，保留题号、选项、题目说明、字数限制。
- 看不清写 `[illegible]` / `[?word]`，不要猜。关键位置看不清就问用户。
- 抄答案页（如果有），单独标记 `## ANSWER KEY`。

这一步是后面所有工作的唯一事实来源。**不要跳过 transcript 直接写 case.json**。

### 3. 组装 `case.json`

按 `references/schema.md` 写。要点：

- `passages[].paragraphs[]`：一段一个对象，`id` 用 A/B/C（无标签用 p1/p2）。
- `questionGroups[]`：按试卷的 `Questions 1–6` 等分组；共享选项放题组 `options`，MCQ 选项放每题 `options`。
- 题号保留原编号，不要重排。
- `meta.answerSource`：有官方答案页用 `official`，自己推导用 `derived`，两者都有用 `mixed`。

### 4. 写答案与解析

按 `references/analysis-guide.md`：

1. 先自己从原文推导答案；有官方答案页时再核对。
2. 每题写 1–4 个关键词；关键词必须是定位词、同义替换或限定词，不要选全文高频词。
3. 每个关键词在 `analysis` 里用 `{{term}}` 标记。**每个 keyword 都必须出现在解析中**，否则构建失败。
4. `anchor.quote` 从 `case.json` 的段落正文**逐字复制**，一句或一个从句，不要整段。
5. 页面会在「解析」前自动生成「原文回顾」：把本题所有 `anchor.quote` 去重后按段落标签列出。因此 `analysis` 不必再整句抄原文，直接写“上面回顾的 X 段原句里……”，再解释同义替换/矛盾/缺失即可。
6. 判断题要区分“矛盾”（FALSE）和“没信息”（NOT GIVEN）；NOT GIVEN 要指出缺的具体条件。
7. 填空题答案必须符合字数限制和语法；证据句要包含答案词。
8. 不确定的题设 `confidence: "medium"` 或 `"low"`，不要装确定。

### 5. 校验

```powershell
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" --check
```

- 必须 0 个 ERROR。
- 逐条看 WARN：题号不连续、引文重复、证据句过长、低置信等。
- 引文找不到时，构建器会打印原文相近位置，甚至告诉你该句实际在哪个段落。按提示修 `paraId`/`quote`。

### 6. 生成 HTML

```powershell
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" -o "$Out\index.html"
```

生成的是自包含单文件：CSS/JS 内联，不依赖网络，可直接发给用户或用 `file://` 打开。

### 7. 浏览器验收（不能省）

至少检查：

- 页面能打开，文章/题目/答案数量与试卷一致；桌面宽度下左侧原文、右侧题目分屏显示。
- 答案与解析默认全部展开；每题解析前有「原文回顾」块，引文与 `anchor.quote` 一致。
- 顶部按钮能“收起全部”，再“展开全部”。
- 随便点 3 个不同题组的关键词：左侧原文滚动到证据句、精确高亮 `quote`、有明显闪动/跳动，右下出现“返回解析”。
- 点「原文回顾」里的“定位原文”：同样能跳转/高亮。
- 点“返回解析”：回到刚才的题目，答案与解析仍展开。
- 答案速查的题号能跳到对应题目。
- 打印预览：解析全部显示，没有把导航/按钮印进去。
- 浏览器 console 没有 JS 报错。

浏览器工具不能打开 `file://` 时，起一个本地静态服务：

```powershell
python -X utf8 -m http.server 8765 --bind 127.0.0.1
```

然后打开 `http://127.0.0.1:8765/<相对路径>/index.html`。

没有浏览器工具时，明确告诉用户“已通过构建校验，但未做浏览器交互验收”，不要假装点过。

### 8. 交付

给用户：

- `index.html` 的路径（主交付物）。
- `case.json` / `transcript.md` 的路径（便于后续修正）。
- 统计：几篇、几题、几个关键词、几个 WARN。
- 页面默认状态：桌面分屏、答案与解析全部展开、每题有「原文回顾」。
- 答案来源说明：官方 / 推导 / 混合；如果是推导，提醒仅供学习。
- 如果做了浏览器验收，说明验收了什么；如果没做，说明没做。

## 铁律

1. **原文逐字还原**。不改写、不简化、不“纠正”语法。雅思答案经常依赖一个限定词。
2. **不猜 OCR**。看不清就标记并问；用“雅思常见文章”补内容是严重错误。
3. **每道题至少 1 个 keyword，且必须出现在 `analysis` 的 `{{...}}` 标记里**。
4. **`anchor.quote` 必须逐字出现在对应段落**；构建器会精确校验。
5. **先推导答案，再写解析**。有官方答案页时以官方为准；冲突要标注。
6. **只改 `case.json`，不改 `index.html`**。HTML 是生成物，改完 JSON 重新构建。
7. **不伪造答案确定性**。不确定就降 `confidence`。
8. **保留原图和 transcript**，方便用户指出 OCR 错误后局部修正。
9. **版权**：生成物仅供个人学习；页脚版权提示不要删。
10. **解析前先回顾原文**：页面会在每题解析上方自动显示「原文回顾」证据句；该块由 `anchor.quote` 生成，不要删。解析正文直接接着解释，不要整句重复。

## 文件地图

```text
.opencode/skills/ielts-reading-html/
├── SKILL.md
├── assets/
│   └── template.html          # 页面模板（CSS/JS 内联）
├── scripts/
│   ├── build.py               # 校验 + 渲染 + 统计
│   └── prepare_images.py      # EXIF 旋转、缩放、contact sheet
├── references/
│   ├── schema.md              # case.json 字段与错误说明
│   ├── ocr-guide.md           # 拍摄、页序、逐字转录
│   └── analysis-guide.md      # 各题型解析写法、关键词规则
└── examples/
    ├── demo-case.json         # 原创演示数据
    └── demo.html              # 生成结果，可直接打开
```

## 常用命令

```powershell
# 只校验
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" --check

# 校验 + 生成
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" -o "$Out\index.html"

# 警告也当错误（交付前想更严格时）
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" --check --strict

# 生成后自动打开默认浏览器
python -X utf8 "$SkillDir\scripts\build.py" "$Out\case.json" -o "$Out\index.html" --open
```

## 快速验证模板本身

```powershell
python -X utf8 "$SkillDir\scripts\build.py" "$SkillDir\examples\demo-case.json" -o "$SkillDir\examples\demo.html"
```

打开 `examples/demo.html`，点任意解析里的绿色关键词，应跳到左侧/原文对应句并高亮。

## 处理整卷

- 优先一篇一个 `case.json` + 一个 HTML；这样上下文短、出错好修。
- 如果用户要一个整卷 HTML，把三篇放进同一个 `case.json` 的 `passages`，题组用 `passageId` 关联；题号必须全局唯一。
- 整卷很长时按篇处理，每篇先 `--check`，最后合并。不要一次性在上下文里塞三篇全文再写解析。
- 表格/流程图/图示无法用纯文本还原时，按阅读顺序线性化，并在 `meta.note` 说明。

## 常见故障

| 现象 | 处理 |
|---|---|
| `quote` 找不到 | 从 `case.json` 段落正文复制；检查弯引号、en dash、大小写。构建器会打印相近原文。 |
| 关键词没出现在解析 | 把解析里的词改成 `{{term}}`，或删掉该 keyword。 |
| 共享选项报标记错误 | 共享选项只能纯文本；关键词移到题干/解析。 |
| 窗口太窄，两块挤在一起 | 建议窗口 ≥ 1200px；≤ 860px 会自动改成上下堆叠，不再分屏。 |
| 答案没有默认显示 | 确认没有手工改过 `index.html`；重新构建，构建器默认输出展开状态。 |
| 关键词点了没反应 | 看 console 是否有 JS 错误；确认 `data-para` 指向的段落 id 存在；重新构建。 |
| 打印没有解析 | 浏览器打印时 CSS 会强制展开 `.answer-box`；如果仍没有，检查是否用了旧 HTML。 |
| 图片读不出来 | 跑 `prepare_images.py`；HEIC 先转 JPEG；模糊/缺页让用户补拍。 |

## 不要做

- 不要把 `transcript.md` 里的内容直接当 `quote`（可能已合并换行/改动标点）。
- 不要给每道题塞 8 个关键词；解析会变成高亮噪声。
- 不要把 `NOT GIVEN` 写成 `FALSE` 来“凑答案”。
- 不要删除 `source/` 或 `transcript.md`；用户后续改错需要它们。
- 不要把真题 HTML 公开发布或商用。
