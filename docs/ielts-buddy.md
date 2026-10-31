# IELTS Buddy 使用说明

本仓库集成了两个互补的雅思工具链：

| 工具 | 作用 | 位置 |
| --- | --- | --- |
| `ielts-reading-html` | 把**试卷照片**变成可交互复盘 HTML（离线、单文件） | `.opencode/skills/ielts-reading-html/` |
| IELTS Buddy Skills（10 个） | 把**线上练习记录/题库/词汇/口语素材**接进对话 | `.agents/skills/` |

来源：https://github.com/Jobo16/ielts-buddy （MIT），当前版本 `0.17.2`，commit `dd83c28`。

## 一、已安装内容

`.agents/skills/` 下 10 个 skill：

| Skill | 用途 |
| --- | --- |
| `ielts-study-plan` | 学习计划、精确课程/题组任务、提醒、学习路径、学习事件 |
| `ielts-practice` | 考场记录、预测候选题、题库目录、浏览器练习 session 与已提交结果 |
| `ielts-writing-review` | 写作提交的不可变版本与结构化批改结果 |
| `ielts-speaking-coach` | 口语素材的读写与练习入口 |
| `ielts-reading-review` | 已提交阅读练习的结果与按需材料 |
| `ielts-listening-review` | 已提交听力练习的结果与按需材料 |
| `ielts-vocabulary-coach` | 词汇数据的读取、维护、导入导出、记录 |
| `ielts-mock-review` | 模考试卷目录与已产生活动数据 |
| `ielts-buddy-question-research` | 后台题库权限下的只读题库接口（普通账号不可用） |
| `ielts-buddy-skills-updater` | 从固定 OSS 源检查/更新本机 skills |

配套脚本（仓库根目录）：

```text
scripts/
├── ielts_buddy_api.py          # 唯一的 API 客户端（bind / me / capabilities / call）
├── update_skills.py            # 从 OSS 固定源更新 .agents/skills
├── learning_store.py           # 本地学习记录
├── simple_docx.py              # 无依赖 DOCX 生成
├── skill-taxonomy.json         # 能力编码表（reading.evidence-location 等）
└── workflows/                  # 各 workflow 的 DOCX 生成/校验脚本
```

已验证：

- 10 个 skill 与上游仓库逐字节一致；
- 30 个 Python 脚本全部可编译；
- 公开接口 `ielts_prediction_search_hits` 可免 Token 直接调用成功；
- 个人接口在未绑定时正确返回 `401 40101`（不是故障，是还没绑定账号）。

## 二、三个层次，别混用

这是这套东西最容易踩的坑：

1. **Skills**（`.agents/skills/*/SKILL.md`）只描述「有哪些接口、能取什么数据、不能做什么」，**不定义教学法**。
2. **Workflows**（`scripts/workflows/`、上游 `workflows/`）是**可选推荐用法**，不安装也能用，装 skill 也不会自动启用。
3. **Scripts** 是真正执行的东西。

所以「用 `$ielts-reading-review` 帮我复盘」这种说法在上游是有效的调用方式，但在这套 skill 里它只会告诉你接口怎么调 —— 真正的复盘动作由我（agent）按你的目标来编排。

## 三、绑定账号（唯一需要你手动做的一步）

不绑定只能查公开数据（考场记录、预测候选、备考资讯）。绑定后才能读你自己的练习记录、词汇、计划。

```powershell
cd C:\dev\projects\ielts-skill
python scripts\ielts_buddy_api.py bind
```

终端会打印一条形如
`https://work.ieltsbuddy.igopx.cn/agent/bind?binding=...`
的链接。**在浏览器打开、登录、点确认**，脚本会自动轮询并在成功后把凭据写到：

```text
C:\Users\<你>\.config\ielts-buddy\agent-token
```

绑定链接有效期约 10 分钟，过期就重跑一次 `bind`。

验证连接：

```powershell
python scripts\ielts_buddy_api.py capabilities
```

返回 42 项能力即成功。若报 `40101`，说明没绑定或凭据已失效；`40301` 说明该账号没有对应 scope。

> Token 只用于数据接口，**不能**用来替你做题或交卷；浏览器登录态也不能拿来当 Token。不要把它贴进聊天记录或提交到仓库。

## 四、日常怎么用

绑定后直接说人话即可，我会自己去调接口。下面是高频场景。

### 1. 「我最近练得怎么样？」

```text
看看我这两周的练习记录，哪个题型掉得最多
```

对应能力：`ielts_footprints_list`（统计走服务端 `summary/dailyCounts`）、`ielts_practice_recent_activity`、`ielts_review_read_snapshot`。

注意：不会从「10 题对 7 题」去推算雅思分数，那是错的。

### 2. 「这道阅读题我为什么错」

```text
复盘我上次那道阅读，把错题的原文证据句找出来
```

对应：`ielts_review_read_snapshot`（拿作答 + 答案 key）+ 本地证据定位。上游推荐的产出是一份 **Reading Evidence Map .docx**：

```powershell
python scripts\workflows\reading-review\create_reading_evidence_map_docx.py plan.json
python scripts\workflows\reading-review\validate_reading_evidence_map_docx.py out.docx
```

### 3. 「明天考什么题材」

```text
最近考场回忆里出现最多的阅读话题是哪些
```

对应：`ielts_prediction_search_hits`（免 Token）。要点：结果是「考场记录 + `candidates` 候选」两层，`matchScore` 只是匹配值，**不是**确认命中；要展示全部候选，不能只取第一条。三个月前的记录不再做题库匹配，返回空候选是正常的。

### 4. 刷题本身

Agent **不代做、不代交**。流程是：

1. 我告诉你练哪篇（`ielts_practice_search_parts` 给 `partId` 和做题入口）；
2. 你在浏览器刷题中心手动开始、作答、交卷；
3. 我再读权威记录做复盘。

Token 和网页登录态是两套东西，不能互相替代。

### 5. 写作 / 口语 / 词汇

- 写作：你在浏览器提交，我读 `ielts_writing_read_practice` 拿不可变版本 + 批改结果，不代提交、不触发正式批改。
- 口语：`ielts_speaking_materials_*` 管素材（可写），陪练本身在本地对话里做。
- 词汇：`ielts_vocabulary_*` 支持增删改查和导入导出。

### 6. 学习计划与提醒

`ielts_study_todos_create` 可以带 `date` / `time`（Asia/Shanghai），能关联具体题组（`question_part`）、模考卷（`mock_paper`）、课程章节（`course_section`）、精听素材（`listening_dictation`）；微信提醒默认关闭。

## 五、和 `ielts-reading-html` 怎么配合

两者不冲突，正好接成一条链：

```text
线上刷题（IELTS Buddy 浏览器）
   → Agent 读记录、定位证据（ielts-*-review + scripts/）
   → 需要成稿：Docx 复盘表
   → 需要随身复习：把纸质/截图试卷走 ielts-reading-html 生成单文件 HTML
```

也就是说：**电子记录走 IELTS Buddy 接口，纸质或截图试卷走 `ielts-reading-html`**。

## 六、更新

```powershell
python scripts\update_skills.py check   --target .agents\skills
python scripts\update_skills.py update  --target .agents\skills
```

`--target` 必须带上，否则脚本会按「脚本在 `<root>/scripts/`」的默认布局去找 `<root>/<skill>/SKILL.md`，在 `scripts/` 存放方式下会报错。

更新会校验项目名、版本、commit、ZIP 大小、SHA-256、路径越界和 skills 清单，失败保留原版本。注意它在**当前仓库层**会拒绝执行（检测到 `.git` 就判定为维护者仓库）—— 这里用 `--target .agents\skills` 绕开的是默认布局，不改变这个安全语义，实际替换的只是 `.agents/skills` 这 10 个目录加版本标记。

也可以在任意目录用官方 CLI：

```powershell
npx skills@latest add Jobo16/ielts-buddy --skill '*' --project --yes
```

## 七、边界（照抄上游，别越界）

- 不替你做正式练习、不代交卷、不触发正式批改。
- 不从部分题目正确率推算 IELTS 分数。
- `coverage.complete` / `sourceTruncated` 表示「列明范围完整」，不等于全站数据；不完整时不许说「查全了」。
- 题库来源只认 `origin.questionBank/sourceBook/sourceTest/sourceUnit`，不从标题猜。
- 后台题库接口只对**拥有后台题库权限**的账号开放，普通账号拿不到。
- 这些是学习辅助，不替代教师判断和官方评分。
