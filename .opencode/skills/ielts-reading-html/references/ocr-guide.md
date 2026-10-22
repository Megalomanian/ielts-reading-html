# 手机试卷照片的整理与转录

目标不是“看得懂”，而是**逐字还原**。雅思阅读的答案经常依赖一个限定词、一个数字或一个否定词；转录时改一个词，解析就会错。

## 1. 拍摄与选图

理想照片：

- 页面完整，四角都在画面内，边缘留一点桌面。
- 正对页面，尽量少透视变形；不要斜着拍。
- 光线均匀，避开顶灯反光和手机阴影。
- 对焦清晰，文字边缘不糊。
- 一页一张；跨页题组宁可多拍一张重叠页。
- 包含页码、题号、段落标签和页眉的 Passage 编号。

如果用户已经拍好，不要要求重拍，除非关键区域确实不可读。先尝试预处理。

## 2. 预处理

```powershell
python -X utf8 "$SkillDir\scripts\prepare_images.py" "$Out\source" --out "$Out\pages" --max-side 2200
```

脚本会：

- 按 EXIF 自动旋转；
- 缩放到长边不超过 2200 px；
- 轻微自动对比度；
- 输出 `pages/page-001.jpg` 等；
- 生成 `pages/contact-sheet.jpg`，带页码和原文件名。

先看 `contact-sheet.jpg` 确定页序、重复页和缺页，再逐页读大图。

如果 Pillow 未安装：

```powershell
python -m pip install Pillow
```

HEIC 需要系统解码器或先转成 JPEG；脚本报错时让用户导出 JPEG。

## 3. 页序与页地图

在 `transcript.md` 顶部写页地图：

```markdown
| 页 | 内容 | 备注 |
|---|---|---|
| 1 | Reading Passage 1 标题 + A–C 段 | 清晰 |
| 2 | D–F 段 + Questions 1–6 | 与第 1 页底部重叠 |
| 3 | Questions 7–13 + 答案页 | 答案页在右下角 |
```

处理：

- 相邻照片有重叠时，只保留一份正文。
- 同一页拍了两张，选更清晰的那张。
- 页序乱了，按页码/题号重排；不要按文件修改时间猜。
- 缺页时先问用户要，不要用“常见真题内容”补全。

## 4. 转录格式

建议：

```markdown
# Transcript

## PAGE 1

### READING PASSAGE 1

**Title: The Return of the Nightingale**

**A** Every spring, ...

**B** In the 1950s, ...

### QUESTIONS 1–6

**Questions 1–4**
Do the following statements agree...
1. Nightingales are easier to hear than to see.
2. ...
```

规则：

1. **逐字复制**：不改写、不简化、不“纠正”原文语法。
2. **保留段落标签**：A、B、C…… 以及标题、副标题、斜体说明。
3. **保留题号和选项标签**：1–13、A–D、i–x。
4. **保留题目说明**：TRUE/FALSE/NOT GIVEN 的写法、字数限制（NO MORE THAN TWO WORDS）、是否“one answer only”。
5. **处理换行**：
   - 段落内被排版折断的行合并成一行；
   - 真正的段落边界保留；
   - 行尾连字符只有在明确是断词时才合并，如 `environ-` + `ment` → `environment`；如果是复合词（`well-known`）保留。
6. **数字与字母**：`1`/`I`、`0`/`O`、`5`/`S` 用上下文判断；题号通常是阿拉伯数字。
7. **标点**：保留原标点；英文弯引号 `’` `“` `”` 与直引号不要混。构建器的引文匹配是精确的，大小写和标点都必须一致。
8. **看不清**：写 `[illegible]` 或 `[?word]`，并在页末列出；不要猜一个看起来合理的词。关键位置（题干、答案句）看不清时，停下来问用户。
9. **答案页**：如果试卷附带答案，单独抄成 `## ANSWER KEY`，注明页码；它会影响 `meta.answerSource`。

## 5. 从转录到 `case.json`

- 文章：每个原始段落一个 `paragraphs[]` 对象。`id` 用段落标签（A/B/C）；没有标签时用 `p1`、`p2`。
- 题组：按试卷的 `Questions 1–6`、`Questions 7–13` 分组，不要按题型强行重排。
- 题号：保留原题号，不要重新编号。
- 共享选项：Matching Headings / Features 的选项放在题组 `options`；MCQ 的选项放在每题 `options`。
- 说明文字：放题组 `instructions`，保留换行。
- 复杂版式：table / diagram / flowchart 如果无法用纯文本还原，按阅读顺序把单元格/标签写成题干，并在 `meta.note` 说明“版式已线性化”。不要伪造表格结构。

## 6. 转录自检

在写解析前，至少做一遍：

- 文章段落数是否与照片一致？
- 每段首尾句是否完整？
- 题号是否从第一题连续到最后一题？有没有漏题？
- 每组题的说明是否完整？字数限制是否抄对？
- 选项数量是否与照片一致（A–D 还是 A–E）？
- 有没有把 `NOT GIVEN` 抄成 `NO`，或把 `TRUE` 抄成 `T`？
- 页与页重叠处是否重复了一段/一题？
- 是否有 `[illegible]`？关键位置是否已解决？

## 7. 多篇/整卷

- 一次处理一篇，避免上下文过长。
- 每篇完成后先 `--check`，再处理下一篇。
- 整卷可以合并进一个 `case.json` 的 `passages` / `questionGroups`；也可以每篇一个 HTML。若合并，保持 `passageId` 与文章 id 对应，题号全局唯一。
- 整卷建议在页脚注明“按篇整理，非官方排版”。

## 8. 版权

用户拍摄的试卷通常受版权保护。生成物仅供个人学习；不要把 HTML 公开发布或用于商业用途。页脚已包含版权提示，不要删除。
