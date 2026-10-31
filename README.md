# IELTS Reading HTML

把手机拍摄的雅思阅读试卷照片整理成一份**可交互的单文件 HTML**：

- 桌面分屏：左边原文，右边题目与解析；
- 文章与题目逐字还原；
- 每题生成中文解析，**答案与解析默认展开**；
- 解析前自动生成「原文回顾」：直接引用该题的证据句，先读原文再看解析；
- 解析里的关键词是可点击按钮；
- 点击关键词会跳到左侧原文、**精确高亮证据句并闪动/跳动**；
- 可以点“返回解析”回到刚才的题目；
- 支持打印 / 导出 PDF。

这是一个 OpenCode skill，skill ID 为 `ielts-reading-html`。

## 先看效果

在线示例（GitHub Pages，`main` 分支更新后自动部署）：

```text
落地页       https://megalomanian.github.io/ielts-reading-html/
写作范文库   https://megalomanian.github.io/ielts-reading-html/writing/
口语素材库   https://megalomanian.github.io/ielts-reading-html/speaking/
阅读示例     https://megalomanian.github.io/ielts-reading-html/reading/
```

也可以直接用浏览器打开本地文件：

```text
.opencode/skills/ielts-reading-html/examples/demo.html
```

这是用原创演示文章生成的示例，不是真题。点解析里的绿色关键词试试。

GitHub Pages 由 `.github/workflows/pages.yml` 在 `main` 分支更新时自动部署。

## 怎么用

在 OpenCode 里直接说：

```text
用 ielts-reading-html 把这个雅思阅读试卷生成 HTML：
C:\path\to\IMG_001.jpg
C:\path\to\IMG_002.jpg
输出到 C:\path\to\output
```

或者显式加载 skill：

```text
@ielts-reading-html 帮我整理这组雅思阅读照片，生成可点击关键词定位原文的 HTML。
```

如果你把图片直接拖进对话，也可以让 agent 自己找路径。

## 工作流

```text
照片
  → source/（保留原图）
  → pages/（EXIF 旋转、缩放、contact sheet）
  → transcript.md（逐页逐字转录）
  → case.json（文章 / 题目 / 答案 / 解析 / 关键词锚点）
  → build.py 校验
  → index.html
  → 浏览器验收
```

核心原则：**只改 `case.json`，不手改 HTML**。HTML 是生成物，改完 JSON 重新构建。

## 目录

```text
.opencode/skills/ielts-reading-html/
├── SKILL.md                     # skill 主说明
├── assets/template.html         # 页面模板（CSS/JS 内联）
├── scripts/
│   ├── build.py                 # 校验 + 渲染
│   └── prepare_images.py        # 图片预处理 + contact sheet
├── references/
│   ├── schema.md                # case.json 字段、标记语法、报错解释
│   ├── ocr-guide.md             # 拍摄、页序、逐字转录
│   └── analysis-guide.md        # 各题型解析写法、关键词规则
└── examples/
    ├── demo-case.json           # 原创演示数据
    └── demo.html                # 生成结果
```

## 手动命令

```powershell
# 1. 预处理照片（需要 Pillow）
python -X utf8 .opencode\skills\ielts-reading-html\scripts\prepare_images.py `
  C:\path\to\photos --out C:\path\to\output\pages --max-side 2200

# 2. 校验 case.json
python -X utf8 .opencode\skills\ielts-reading-html\scripts\build.py `
  C:\path\to\output\case.json --check

# 3. 生成 HTML
python -X utf8 .opencode\skills\ielts-reading-html\scripts\build.py `
  C:\path\to\output\case.json -o C:\path\to\output\index.html

# 4. 重建演示
python -X utf8 .opencode\skills\ielts-reading-html\scripts\build.py `
  .opencode\skills\ielts-reading-html\examples\demo-case.json `
  -o .opencode\skills\ielts-reading-html\examples\demo.html
```

构建器只依赖 Python 标准库；图片预处理依赖 Pillow（`python -m pip install Pillow`）。

## 关键词定位是怎么做的

每个关键词在 `case.json` 里长这样：

```json
{
  "term": "amateur recordists",
  "anchor": {
    "paraId": "B",
    "quote": "In the 1950s, amateur recordists began noticing that nightingales in busy urban parks sang differently from those in quiet countryside."
  }
}
```

解析里写 `{{amateur recordists}}`，构建器会把它渲染成按钮，并带上段落 id 和精确引文。点击时浏览器在该段落文本中查找 `quote`，用 `<mark>` 包住并滚动到视口中央。因此：

- `quote` 必须逐字出现在段落正文里（构建时会校验）；
- 找不到会直接报错，不会生成坏链接；
- 同一句可以被多个关键词复用；
- 一句话太长可以只截取关键从句，但必须仍能支持答案。

## 页面交互

- **原文回顾**：每题答案下方先显示证据句（按 `keywords[].anchor` 自动生成），可点“定位原文”去左侧高亮。
- **点击关键词**：左侧原文滚动到证据句，精确高亮并闪动，段落轻微跳动；右下出现“返回解析”。
- **返回解析**：回到触发定位的题目，答案与解析保持展开。
- **展开 / 收起全部解析**：顶部按钮；默认全部展开。
- **答案速查**：页底折叠表，点题号跳到对应题目。
- **打印 / PDF**：打印样式会显示所有解析并隐藏导航。

## 安装到其他项目 / 全局

当前 skill 在项目内：

```text
<repo>/.opencode/skills/ielts-reading-html/
```

如果想让所有项目都能用，复制到全局：

```powershell
Copy-Item -Recurse `
  .opencode\skills\ielts-reading-html `
  "$env:USERPROFILE\.config\opencode\skills\ielts-reading-html"
```

OpenCode 会自动发现 `~/.config/opencode/skills/<id>/SKILL.md`。

## 配套：IELTS Buddy Skills

本仓库同时集成了 [Jobo16/ielts-buddy](https://github.com/Jobo16/ielts-buddy) 的 10 个 Agent Skills（`.agents/skills/`）与配套脚本（`scripts/`），用于读取 IELTS Buddy 线上练习记录、题库、词汇和口语素材。

安装、账号绑定与使用方式见 **[docs/ielts-buddy.md](docs/ielts-buddy.md)**。

分工：**纸质/截图试卷**走上面的 `ielts-reading-html` 生成单文件 HTML；**线上刷题记录**走 IELTS Buddy 接口复盘。

## 写作范文库

`writing-output/` 里是另一份独立产物：按题型组织的雅思写作题目 + 原创 7.5 分范文 + 逐段解析，同样是一个单文件 HTML。

- 题目来自 IELTS Buddy 公开的「写作考场回忆」接口（3,743 条 / 411 个考试日）
- 覆盖 Task 1 八种图表 + Task 2 五种提问方式，共 13 篇
- 每篇四栏拆解：评分维度 / 结构拆解 / 词汇与语法 / 考官视角与踩坑
- 点解析关键词可在范文里精确高亮对应句子

详见 **[writing-output/README.md](writing-output/README.md)**。

## 边界

- 照片模糊/缺页时，skill 会要求补拍，不会用“雅思真题记忆”补内容。
- 表格、流程图、图示会被线性化，复杂版式无法 100% 还原。
- 答案若来自模型推导，会在页面标注；有官方答案页时以官方为准。
- 原文与题目版权归原作者/出版方所有，生成物仅供个人学习，请勿公开传播或商用。
- 写作范文库里的图表数字是按考场回忆复原的示意数据，不是官方数据；范文是教学示范，不是标准答案。

## 许可

代码与模板 MIT。用户上传的试卷文本、题目与图片版权归原权利人。
