# 数据规范（schema 1.0）

正式规范文件：[`schema/question.schema.json`](../schema/question.schema.json)、[`schema/paper.schema.json`](../schema/paper.schema.json)。
本文说明设计取舍与填写约定。存储格式统一为 **JSONL**（一行一条，便于 git diff 与增量合并）。

## 1. 题目记录（question）

### 必填最小集

```json
{
  "id": "q-2026-yw-quanguo1-001",
  "schema_version": "1.0",
  "subject": "语文",
  "stage": "高考",
  "exam_type": "真题",
  "year": 2026,
  "type": "写作",
  "stem": "题干（材料题含材料全文）",
  "source": { "source_id": "eol-gkzx", "name": "…", "url": "https://…", "tier": "T2", "fetched_at": "2026-09-29" },
  "verification": { "status": "verified" }
}
```

### 字段约定

| 字段 | 约定 |
| --- | --- |
| `id` | `q-<年份>-<学科码>-<卷别slug>-<序号>`，用 `qbnk new-id` 生成；必须稳定，不得随时间变化 |
| `subject` | 语文/数学/英语/物理/化学/生物/政治/历史/地理/技术/综合/其他 |
| `stage` | 高考（真题）· 高三/高二/高一（模拟、同步、期中期末）· 其他 |
| `exam_type` | 真题 / 模拟 / 联考 / 期中 / 期末 / 月考 / 学业水平 / 竞赛 / 教材习题 / 其他 |
| `type` | 单选/多选/判断/填空/解答/计算/证明/实验/写作/微写作/翻译/完形/阅读/语用/古诗文默写/材料分析/开放性/选做/其他 |
| `region` / `paper` | 省级行政区或"全国"；卷别如 `全国I卷`、`新课标II卷`、`北京卷` |
| `stem` | 题干原文。材料题把材料全文放进 `materials[]`，`stem` 只留设问 |
| `options` / `answer` | 客观题必填 `answer`（单选字符串、多选字符串数组），否则 `E-NO-ANSWER` |
| `answer_text` | 主观题参考答案/评分说明；引用官方评分细则时需在 `source` 注明 |
| `analysis` | 解析，**必须来自 `source` 或 `evidence` 列出的权威出处**，不许自己写 |
| `difficulty` | 1-5；**没有可靠依据就留 null**，禁止凭感觉填 |
| `score` | 该题分值，未知留 null |
| `question_no` | 原卷题号；缺失时不参与同卷去重比对 |
| `source` | 见下节 |
| `verification` | `verified` / `single_source` / `conflict` / `rejected` |
| `content_hash` | `sha1:` + 归一化正文的哈希，由 `qbnk validate --fix-hash` 维护 |
| `year` | 0 表示年份未知，**仅隔离区记录允许** |

### source（溯源块）

```json
"source": {
  "source_id": "dxsbb-zuowen",     // 必须在 sources/registry.json 登记
  "name": "历年全国卷高考作文题目汇总（含2022-2026年）",
  "publisher": "大学生必备网",
  "url": "https://www.dxsbb.com/news/136500.html",
  "tier": "T3",
  "published_at": "2026-06-15",
  "fetched_at": "2026-09-29",
  "license": "教育类站点整理稿，转载需署名",
  "evidence": [
    { "url": "https://m.qz.bendibao.com/edu/38017.shtm", "tier": "T3", "checked_at": "2026-09-29", "note": "题干全文一致" }
  ]
}
```

- `url` 主机必须与登记表里该来源的主机一致（校验规则 `E-SRC-HOST`）。
- `evidence` 里的每个 URL 都是**不同主体**的独立出处；同稿转载不算。

## 2. 试卷记录（paper）

试卷是题目的归属单位，题目通过 `paper_id` 指回试卷，试卷用 `question_ids[]` 列出已录入题目（有序）。

- 只登记原卷档案、题目尚未录入时：`question_ids: []` + `artifact{kind,url,local_path,sha256}`，
  并在 `verification.notes` 写明"仅登记原卷档案位置，题目正文尚未录入"。
  覆盖度报告会区分"已录入题目的试卷"与"仅档案索引"。
- `structure[]` 描述大题结构（板块/题型/题量/分值），有官方结构说明时填写。

## 3. 目录约定

| 目录 | 含义 | 是否校验 |
| --- | --- | --- |
| `data/questions/` | 正式题库 | 是（CI 强制） |
| `data/papers/` | 试卷层（含外部档案索引） | 是 |
| `data/staging/` | 适配器产出、待人工复核 | 否 |
| `data/quarantine/` | T4 / 冲突 / 待裁决 | 否（移入正式库时必须先改状态） |

## 4. 版本与演进

- `schema_version` 目前是 `1.0`；破坏性变更必须同时提供迁移脚本并保留旧字段兼容一个版本周期。
- 新增枚举值（如新科目、新题型）需同步更新：schema、`tools/qbnk/core.py` 的常量、`docs/schema.md`。
