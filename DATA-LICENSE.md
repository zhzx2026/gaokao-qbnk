# 数据许可与免责说明

## 1. 数据的性质

- `data/` 下的**试题正文**来自命题机构与各发布方的公开内容（教育部教育考试院、省级教育考试院、
  中国教育在线等权威媒体，以及标注了出处的整理稿）。
- **高考试题的著作权归命题机构所有**。本仓库不以任何方式主张对试题内容的所有权。

## 2. 使用范围

- 本仓库以**学习研究、教学参考、命题研究**为目的收录，并在每条记录中标注：`source_id`、
  发布机构、原文 URL、发布日期、采集日期（`fetched_at`）。
- 请勿用于商业分发、付费题库、培训机构的商业性再分发。若需商业使用，请自行取得权利人授权。
- 引用时请保留出处，格式建议：
  `题目来源：<source.name>，<source.url>（采集于 <source.fetched_at>）`。

## 3. 来源等级与可信度

数据按 T1-T4 分级（[docs/sources.md](docs/sources.md)），并且每条记录都有 `verification.status`：

| 状态 | 含义 | 使用建议 |
| --- | --- | --- |
| `verified` | ≥2 个独立来源一致 | 可放心使用 |
| `single_source` | 仅有单一来源 | 可用，但重要场景（如命题研究、对外发布）请先复核 |
| `conflict` | 来源互相矛盾 | **不要使用**，等待人工裁决 |
| `rejected` | 未核验/来源不合格 | **禁止使用**（本仓库全部放在 `data/quarantine/`） |

## 4. 删除与更正

- 权利人或发现错误的读者请提 issue 或 PR（说明题目 id 与问题），我们会在 48 小时内处理。
- 题目正文被更正时必须同步更新 `content_hash`（`qbnk validate --fix-hash`），保证改动可追溯。

## 5. 免责

本仓库提供的数据**按"现状"提供**，不对准确性、完整性、适用性作任何担保。
使用者应自行核验关键内容；因使用本仓库数据造成的任何后果，由使用者自行承担。

## 5. 试卷 PDF（`pdf/`）的许可

`pdf/` 下由 CI 用 XeLaTeX 编译出来的试卷 PDF 是**改编作品**，各文件末尾都写明了来源和许可：

| 类型 | 上游 | 许可 |
| --- | --- | --- |
| 数学整卷重排（`typeset`） | [DxAThing/Gaokao-Math-Problems-Compilation](https://github.com/DxAThing/Gaokao-Math-Problems-Compilation) → [deekur/gaokaomath](https://github.com/deekur/gaokaomath) | **CC BY-SA 4.0**（须署名并以相同方式共享）；题源 CC BY 4.0 |
| 其它学科节选卷（`excerpt`） | [OpenLMLab/GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)、本库作文题 | Apache-2.0（数据整理） |
| 物理原卷套版（`archive`） | [deekur/gaokaophysics](https://github.com/deekur/gaokaophysics) | CC BY 4.0 |

无论哪种，**试题本身的著作权仍归命题机构**；PDF 里的 OCR 整理数据（`excerpt`）尚未逐题二次校对，请以原卷为准。
