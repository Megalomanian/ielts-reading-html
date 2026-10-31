# IELTS Writing 范文库（单文件 HTML）

按题型组织的雅思写作题目 + 原创高分范文 + 逐段解析，产物是一个可以直接双击打开、也能打印成 PDF 的 `index.html`。

## 先看东西

```text
writing-output/index.html
```

- 左侧目录：Task 1 八种图表 / Task 2 五种提问方式，滚动时自动高亮当前篇
- 顶部筛选：全部 / Task 1 / Task 2 / 单个题型
- 每篇左栏是「题目 + 图表 + 范文」，右栏是「评分维度 / 结构拆解 / 词汇 / 语法 / 考官视角 / 常见踩坑」
- 点右栏解析里的绿色关键词 → 左栏范文精确高亮对应那半句
- 顶部「隐藏段意」关掉逐段中文注解，只看纯英文范文
- 每篇「复制范文」可直接贴进写作软件
- 末尾「句式工具箱」：72 条按功能分组的可替换句式骨架（开头 / 概述 / 趋势 / 比较 / 让步 / 收尾），每条附一句「别这么写」，可一键复制框架

## 内容构成

| 题型 | 篇数 | 数据来源（真实考场回忆） |
| --- | --- | --- |
| 折线图 / 柱状图 / 饼图 / 表格 / 地图 / 流程图 / 组合图 / 静态比较 | 8 | 2026-10 前后的机考回忆 |
| 观点类 / 双边讨论 / 利弊类 / 问题解决 / 两问类 | 5 | 2026-09 ~ 10 的机考回忆 |

- 题目：来自 IELTS Buddy 公开「写作考场回忆」接口，共 3,743 条记录 / 411 个考试日（2024-01-06 ~ 2026-10-30）。
- 范文：**全部为本页原创撰写**，不搬运任何机构范文，按 Band 7.5 的评分标准写。
- 图表：考场回忆只描述图形，图里的数字是按回忆复原的**示意数据**，用于练结构，不保证与原卷一致，页面里每张图都标了这句。

## 目录

```text
writing-output/
├── index.html            # 生成物，不要手改
├── template.html         # 页面骨架（CSS / JS 内联）
├── build.py              # 校验 + 渲染
├── SPEC.md               # 内容 JSON 的字段规格
├── content/
│   ├── meta.json         # 标题、导读、筛选、附录文案
│   ├── patterns.json     # 句式工具箱（72 条可替换框架）
│   ├── stats.json        # 抓取统计（脚本生成）
│   ├── task1-*.json      # 8 个 Task 1 case
│   └── task2-*.json      # 5 个 Task 2 case
└── data/
    └── writing-recalls.json   # 原始考场回忆（1.5 MB，留作溯源）
```

## 改内容 / 重新生成

只改 `content/*.json`，然后：

```powershell
# 校验（quote 必须逐字出现在范文里，{{关键词}} 必须有对应条目）
python -X utf8 writing-output\build.py --check

# 生成
python -X utf8 writing-output\build.py
```

校验不通过会直接列出错误并且**不生成 HTML**，不会产出坏链接。字段说明见 `SPEC.md`。

句式工具箱在 `content/patterns.json`，用 `[[ ]]` 标出可替换位（构建时会渲染成底线下划）。校验规则：每个 group 必须有 `id` / `task` / `title`，每条必须有 `frame` 与 `zh`；`[[ ]]` 必须配对，没有可替换位会提示「可能是背死的整句」。

## 刷新考场回忆数据

```powershell
python -X utf8 scripts\fetch_writing_recalls.py
python -X utf8 scripts\fetch_writing_recalls.py --skip-data   # 只更新 stats.json
```

接口是公开的，不需要绑定账号。是否绑定都能跑；有 Token 时会顺带带上。抓完会同时更新 `content/stats.json` 和 `data/writing-recalls.json`。

## 边界

- 考场回忆本身可能有记忆偏差，题目表述不保证与原卷逐字一致。
- 图表数字是示意数据，不能当官方数据引用。
- 范文是教学示范，不是标准答案；同一道题可以有很多种 7.5 分写法，页面里给的是其中一种，重点是「这一段承担什么功能」。
- 题目版权归原命题方，本页仅供个人学习，请勿商用或二次分发。
