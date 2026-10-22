# `case.json` 数据结构

`case.json` 是唯一需要手写的结构化文件。`scripts/build.py` 会校验它，再渲染成 `index.html`。不要直接改 HTML。

完整可运行示例：`examples/demo-case.json`。

## 最小示例

```json
{
  "schemaVersion": 1,
  "meta": {
    "title": "The Return of the Nightingale",
    "subtitle": "IELTS Academic Reading",
    "exam": "IELTS Academic Reading",
    "source": "用户拍摄的试卷",
    "answerSource": "derived",
    "timeLimit": 20,
    "createdAt": "2026-10-22"
  },
  "passages": [
    {
      "id": "p1",
      "number": 1,
      "title": "The Return of the Nightingale",
      "intro": "You should spend about 20 minutes on Questions 1–2.",
      "paragraphs": [
        {
          "id": "A",
          "label": "A",
          "text": "Nightingales are shy birds, and they are far more often heard than seen."
        }
      ]
    }
  ],
  "questionGroups": [
    {
      "id": "g1",
      "passageId": "p1",
      "range": "Questions 1–1",
      "type": "true_false_not_given",
      "instructions": "Do the following statements agree with the information given in Reading Passage 1?",
      "questions": [
        {
          "number": 1,
          "stem": "Nightingales are easier to hear than to see.",
          "answer": "TRUE",
          "analysis": "题干说夜莺更容易被听到。A 段 {{more often heard than seen}} 与题干一致，因此答案是 TRUE。",
          "keywords": [
            {
              "term": "more often heard than seen",
              "anchor": {
                "paraId": "A",
                "quote": "they are far more often heard than seen"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## 顶层字段

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `schemaVersion` | 是 | `1` | 固定为 `1`。 |
| `meta` | 是 | object | 页面标题、来源、答案来源等。 |
| `passages` | 是 | array | 至少一篇阅读文章。 |
| `questionGroups` | 是 | array | 至少一组题目。 |

## `meta`

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 页面主标题，通常用文章标题。 |
| `subtitle` | 否 | 副标题，如 `IELTS Academic Reading · Test 1 Passage 1`。 |
| `exam` | 否 | 默认 `IELTS Reading`。 |
| `source` | 否 | 来源说明，如“用户拍摄的 Cambridge 19 Test 1”。只放简短描述。 |
| `answerSource` | 否 | `official` / `derived` / `mixed`，默认 `derived`。有官方答案页时用 `official`；自己推导用 `derived`；两者都有用 `mixed`。 |
| `timeLimit` | 否 | 建议分钟数，整数。 |
| `createdAt` | 否 | `YYYY-MM-DD`；不填则用构建当天。 |
| `note` | 否 | 页脚备注，如“答案由模型推导，仅供学习”。 |
| `slug` | 否 | 仅用于你自己组织输出目录，构建器不依赖它。 |

## `passages[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 文章内部 id，唯一，如 `p1`。题组用它关联文章。 |
| `number` | 是 | 文章序号，如 `1`。显示为 Reading Passage 1。 |
| `title` | 是 | 文章标题；没有标题时留空并接受警告。 |
| `intro` | 否 | 标题下的说明，如 “You should spend about 20 minutes...”。 |
| `paragraphs` | 是 | 至少一段。 |

### `passages[].paragraphs[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 段落内部 id，在同一篇内唯一。**关键词的 `paraId` 指向它**，不是 `label`。建议直接使用 `A`、`B`、`C`。 |
| `label` | 否 | 显示在段落左侧的标签，如 `A`。原文没有标签就留空。 |
| `text` | 是 | 段落正文，逐字转录。构建时会折叠多余空白。 |

> `paraId` 与 `label` 可以相同（推荐），但概念不同。`paraId` 是程序定位用的；`label` 只负责显示。

## `questionGroups[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 题组内部 id，唯一，如 `g1`。 |
| `passageId` | 是* | 所属文章 id。只有一篇时省略会默认第一篇；多篇时建议始终写。 |
| `range` | 否 | 显示用范围，如 `Questions 1–6`。省略时按题号自动生成。 |
| `type` | 是 | 题组题型，见下方“题型取值”。 |
| `instructions` | 否 | 题目说明。支持换行；构建时每行渲染成一段。 |
| `options` | 否 | **共享选项**，如 Matching Headings 的 i–x 标题列表。每项 `{label, text}`。共享选项里不能写关键词标记。 |
| `questions` | 是 | 至少一道题。 |

## `questions[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `number` | 是 | 题号，整数，全局唯一。 |
| `type` | 否 | 单题题型；不填则继承题组 `type`。 |
| `stem` | 是 | 题干。支持 `{{关键词}}` 标记。 |
| `options` | 否 | 本题选项，如 MCQ 的 A–D。每项 `{label, text}`。支持关键词标记。 |
| `answer` | 是 | 答案字符串，或字符串数组（数组会用 ` / ` 连接）。 |
| `answerText` | 否 | 答案的补充说明。若答案是选项字母，构建器会自动从选项补全，一般不用手写。 |
| `analysis` | 是 | 中文解析。**必须包含至少一个 `{{关键词}}` 标记**，且每个需定位的关键词都要在这里出现。 |
| `keywords` | 是 | 1–6 个；建议 1–4 个。每个关键词必须在 `analysis` 里被标记。 |
| `trap` | 否 | 易错点，支持 `{{关键词}}` 标记。 |
| `vocab` | 否 | 生词数组，每项 `{word, meaning}`。 |
| `confidence` | 否 | `high` / `medium` / `low`，默认 `high`。低置信会在页面显示提示；答案不确定时不要装确定。 |

### 选项对象

```json
{"label": "B", "text": "because low engine noise covers their lower notes"}
```

- `label` 必填；Matching Headings 可用 `i`、`ii`、`iii`。
- 题组共享选项不要写 `{{...}}`；本题选项可以。
- 同一组/同一题的标签不能重复。

## `keywords[]` 与 `{{标记}}`

```json
{
  "term": "more often heard than seen",
  "anchor": {
    "paraId": "A",
    "quote": "they are far more often heard than seen",
    "occurrence": 1
  }
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `term` | 是 | 关键词本身，也是解析里的标记名。同一题内唯一。建议短，如 `amateur recordists`、`6 decibels louder`。 |
| `anchor.paraId` | 是 | 段落 `id`（通常是 `A`、`B`），不是段落标签文本，也不是段落序号。 |
| `anchor.quote` | 是 | **必须逐字出现在该段正文中的证据句/短语**。构建时按折叠空白后的文本做精确子串匹配。建议一句或一个从句，不要整段。 |
| `anchor.occurrence` | 否 | 同一引文在段落中出现多次时，定位第几次。默认 `1`。 |

在题干、解析、易错点、本题选项中写 `{{term}}`，构建器会把它渲染成可点击按钮。**每个 `keywords[].term` 都必须在 `analysis` 中出现至少一次**；否则校验失败。`trap` / `stem` / `options` 里的标记是额外的，不替代解析中的标记。

### 标记规则

- 正确：`定位到 A 段 {{more often heard than seen}}。`
- 错误：`定位到 A 段 {{more often heard than seen}。`（括号不完整）
- 错误：`{{amateur recordists}}` 但 `keywords` 里写的是 `amateur recordist`（拼写必须一致）
- 标记内容会被折叠空白；不要在 `term` 里写 `{{` 或 `}}`。

### 原文回顾（自动生成）

构建器会把同一题所有 `keywords[].anchor.quote` 去重，按 `paraId` 的段落标签显示在「解析」上方，形成「原文回顾」块；每条引文旁有“定位原文”按钮。**不需要额外字段**。

这也是为什么 `anchor.quote` 要选完整证据句，而不是只选一个答案词：它同时承担“回顾原文”和“定位高亮”两个职责。解析正文可以直接说“上面回顾的 X 段原句里……”，不必重复整句。

### 定位是怎么发生的

构建器把每个关键词渲染成带 `data-para` / `data-quote` 的按钮。点击时，浏览器在对应段落文本中查找 `quote`，用 `<mark>` 包住它并滚动到视口中央。因此：

- `quote` 必须与段落正文完全一致（大小写、标点、弯引号、连字符都要一致）。
- 如果找不到，构建阶段就会失败，不会把坏链接带到 HTML 里。
- 同一句被多个关键词使用时没问题；每个按钮各自定位。

## 答案字段规则

- 判断题 `true_false_not_given`：只接受 `TRUE` / `FALSE` / `NOT GIVEN`；`T`、`F`、`NG` 会被自动规范化。
- 判断题 `yes_no_not_given`：只接受 `YES` / `NO` / `NOT GIVEN`；`Y`、`N`、`NG` 会被自动规范化。
- MCQ：填字母，如 `B`；构建器会用选项文本补全答案说明。
- Matching：填选项标签，如 `iv`；若题组有共享选项，构建器会补全标题文本。
- Completion / Short answer：填原文中的词或数字；答案要符合字数限制和语法。
- 多答案：用数组或 `A / C` 字符串。

## 题型取值

| `type` | 显示 |
|---|---|
| `true_false_not_given` | 判断题 · TRUE / FALSE / NOT GIVEN |
| `yes_no_not_given` | 判断题 · YES / NO / NOT GIVEN |
| `multiple_choice` | 选择题 |
| `matching_headings` | 段落标题匹配 |
| `matching_information` | 信息匹配 |
| `matching_features` | 特征匹配 |
| `matching_sentence_endings` | 句子结尾匹配 |
| `summary_completion` | 摘要填空 |
| `sentence_completion` | 句子填空 |
| `note_completion` | 笔记填空 |
| `table_completion` | 表格填空 |
| `flowchart_completion` | 流程图填空 |
| `short_answer` | 简答题 |
| `diagram_labeling` | 图示标注 |

别名（`tfng`、`mcq`、`headings` 等）会被自动转换；未知题型会保留原样并给出警告。

## 构建器的硬校验（ERROR）

- `schemaVersion` 不是 `1`。
- 没有文章、没有题组、题组没有题。
- passage id / 段落 id / group id / 题号重复。
- 题号不是整数或 <= 0。
- 题干、解析、答案为空。
- 判断题答案不在允许集合。
- 关键词为空、`term` 为空、同一题关键词重复。
- `anchor.paraId` 不存在。
- `anchor.quote` 不是段落正文的精确子串。
- `occurrence` 超出引文出现次数。
- 解析里没有 `{{...}}` 标记。
- 某个 keyword 没有出现在解析的标记中。
- 标记里的 term 没有对应 keyword。
- 标记括号不完整。
- 题组共享选项里出现 `{{...}}`。

## 常见修复

1. **引文找不到**：从 `case.json` 的 `passages[].paragraphs[].text` 里复制，不要从 `transcript.md` 或记忆里复制。检查弯引号 `’` 与直引号 `'`、连字符 `-` 与 en dash `–`。构建器会打印相近原文和“该句实际在哪个段落”的提示。
2. **关键词没出现在解析**：把解析里的普通词改成 `{{term}}`，或删除该 keyword。
3. **共享选项报标记错误**：把关键词移到题干/解析里；共享选项只放纯文本。
4. **题号不连续**：构建器只警告，不阻止；但雅思题号通常连续，优先补全或确认是否漏拍。
