# 内容文件规格（给写作 agent 看）

本目录 `writing-output/content/*.json` 是唯一手改的内容源，`index.html` 由 `build.py` 生成。

## 任务

为指定题型各写 1 个 case，存成一个 JSON 文件，文件名如 `task1-bar.json`：

```json
{ "cases": [ { ... }, { ... } ] }
```

只写你被分配的 case，**不要**读写别人的文件，**不要**跑 `build.py`（并发会互相覆盖）。

## 一个 case 的字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | str | 唯一，如 `t1-bar`、`t2-opinion` |
| `task` | str | `"task1"` 或 `"task2"` |
| `cat` | str | 题型 key（见分配） |
| `catLabel` | str | 中文题型名，如 `柱状图` |
| `catEn` | str | 英文题型名，如 `Bar chart` |
| `catNote` | str | 只有该题型的第一篇需要写：一句话说这类题最容易错在哪 |
| `order` | int | 排序号，按分配给的数字 |
| `title` | str | 中文话题名 |
| `titleEn` | str | 英文副标题（图表的英文标题） |
| `promptEn` | str | 英文题目原文（Task 2 用真实考场回忆里的题目，可补全被截断的部分） |
| `promptZh` | str | 中文说明：任务要求 + 「写之前先想清楚」一句（可用 `<b>`） |
| `chart` | obj/null | 仅 Task 1，见下 |
| `tags` | str[] | 2-3 个 |
| `minutes` | int | Task 1 用 20，Task 2 用 40 |
| `band` | str | `"7.5+"` |
| `exam` | obj | `{"date":"2026-10-28","venue":"..."}`，用分配给你的那条回忆 |
| `essay` | obj[] | 范文段落，见下 |
| `scores` | obj[] | 4 条评分维度 |
| `structure` | obj[] | 逐句/逐段拆解 |
| `lexis` | obj[] | 5-6 条词汇 |
| `grammar` | str[] | 3 条语法点，可用 `<code>` |
| `examiner` | str | 考官视角，一段话，可用 `<strong>` |
| `pitfalls` | str[] | 4 条常见踩坑 |
| `keywords` | obj[] | 5-7 个可定位关键词 |

### essay

```json
"essay": [
  { "text": "The line graph compares ...", "gist": "开头：改写题目，只交代图表身份。" }
]
```

- `text` 是**原创**范文正文，纯文本，不要 markdown。
- Task 1：150–190 词，3–4 段。
- Task 2：265–300 词，4–5 段。
- `gist` 是一句中文段意，说明这段承担什么功能。

### scores

```json
{ "k": "Task Achievement", "v": "7.5", "p": "中文解析，可以嵌 {{关键词}}" }
```

8 项评分维度按任务选：
- Task 1：`Task Achievement`、`Coherence & Cohesion`、`Lexical Resource`、`Grammatical Range`
- Task 2：`Task Response`、`Coherence & Cohesion`、`Lexical Resource`、`Grammatical Range`

### structure

```json
{ "n": "第 2 句", "d": "中文：这句在干什么，为什么这样切。" }
```

6–9 条。`n` 可以是「第 1–2 句」「第 1 段」这种范围。

### lexis

```json
{ "w": "uninterrupted decline", "m": "不间断的下降", "note": "三点都往下走时，比 decreased 精确" }
```

5–6 条，只收**范文里真实出现过**的表达。

### keywords

```json
{
  "term": "uninterrupted decline",
  "para": 1,
  "quote": "whereas Museum C recorded an uninterrupted decline",
  "label": "定位第 B 段"
}
```

硬性规则（构建时会校验，错一条就不生成页面）：
1. `quote` 必须**逐字**出现在 `essay[para].text` 里（大小写、标点都要一致）。
2. `term` 必须出现在 `scores / structure / grammar / examiner / pitfalls / lexis` 的**某处**，写成 `{{term}}` 形式；否则只算提醒，但请照做。
3. `term` 不能重复。
4. `para` 从 0 开始。
5. `label` 用 `定位第 X 段`，X 是段号字母（A/B/C/D/E）。

`{{term}}` 在解析文本里渲染成绿色按钮，点击会滚动到左栏范文并精确高亮 `quote`。所以：
- `quote` 挑**半句到一句**，太长会一次刷掉满屏高亮；
- `term` 是读者想追问的概念，通常是搭配或结构名称，不是单个普通词。

### chart（仅 Task 1）
六种 `kind`，按分配选一种。

```jsonc
// 折线 / 柱状
{ "kind": "line", "caption": "英文图注", "unit": "thousand",
  "categories": ["2000","2010","2020"],
  "series": [ { "name": "Museum A", "values": [500,650,800] } ],
  "note": "数据按考场回忆复原为示意数据，用于练结构，不保证与原卷一致。" }

// 饼图（1-3 个并排）
{ "kind": "pie", "caption": "...", "unit": "%",
  "panels": [ { "title": "1988", "slices": [ {"label":"Hotels","value":40} ] } ],
  "legend": ["Hotels","Camping","Friends","Rented flats"],
  "note": "..." }

// 表格
{ "kind": "table", "caption": "...", "head": ["Country","2009"],
  "rows": [ ["Japan","45,000"] ], "note": "..." }

// 流程
{ "kind": "flow", "caption": "...",
  "steps": [ { "label": "Collection", "detail": "used cans are collected from households" } ],
  "note": "..." }

// 地图（左右两幅，用分区列表替代平面图）
{ "kind": "map", "caption": "...",
  "panes": [ { "title": "1985", "zones": [ {"zone":"North","state":"playing field"} ] } ],
  "note": "..." }
```

数值统一用数字（`values` 里不要带单位字符串）。地图用「区域 + 状态」的列表来表达，读者靠文字读图。

## patterns.json（句式工具箱）

单独一个文件，不进 case。结构：

```jsonc
{
  "kicker": "Sentence bank",
  "headline": "句式工具箱 · 换一道题也还能用的句子",
  "lead": "顶部导读，可用 <strong>",
  "note": "小字说明",
  "groups": [
    {
      "id": "t1-overview",        // 唯一，用于锚点 #pat-t1-overview
      "task": "task1",            // task1 / task2，决定筛选
      "title": "Task 1 · 概述句",
      "sub": "一句话副标题",
      "items": [
        {
          "frame": "Overall, [[X]] rose steadily while [[Y]] declined.",
          "zh": "这句为什么好用，以及怎么填",
          "warn": "最常见的误用是什么"
        }
      ]
    }
  ]
}
```

规则：

- `frame` 用 `[[ ]]` 标出可替换位，构建时渲染成带底线的 slot，复制按钮取到的文本里它们会变成 `___`。
- 每条都要有 `warn`：「别这么写」比「为什么这么写」更值钱，别省略。
- 一个 group 4–7 条；按功能分组（开头 / 概述 / 趋势 / 比较 / 让步 / 收尾），不要按语法点分组。
- 校验：`[[ ]]` 必须配对；一条都没有可替换位的会被提醒（说明它是背死的整句，换题就废）。

## 写作要求

- 范文必须自己写，**不要**复制任何机构的范文；句式要像 7.5 分真实考生写的，不要华丽空洞。
- 中文解析要具体：说清「为什么这样写能拿分」「换成什么写法会掉分」，不要写「用词丰富、逻辑清晰」这种空话。
- 每篇的 `examiner` 要指出这篇**最容易被忽略的一个判断**，而不是复述优点。
- 题目里的考场日期、考场名必须来自分配给你的真实回忆。
- 生成的文件必须是严格 JSON（不要 markdown 代码围栏）。
