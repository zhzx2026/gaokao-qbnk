# gaokao-qbnk · 高考题库

一个**可溯源**的高考题库：把公开的高考真题 / 模拟题 / 同步题收进来，每条题目都强制带出处，
来源查不到的一律不许进库——也就是**不要野题**。

> 当前状态（2026-09-29）：骨架 + 工具链 + 首批真实数据已就绪，收录仍在推进中，详见 [roadmap](docs/roadmap.md)。

## 一、现在库里有什么

| 层级 | 内容 | 数量 | 说明 |
| --- | --- | --- | --- |
| 题目 | **历年高考作文题**（2021-2026，全国卷/新高考/北京/上海/天津） | **37 条** | 6 条已双源核验（`verified`），31 条单一来源（`single_source`）待交叉验证 |
| 试卷 | 上述作文题所属试卷 | 33 份 | 含卷别、考试类型、收录题目 id |
| 试卷档案索引 | 数学、物理历年真题原卷 PDF 清单（1952-2026，来自 deekur/gaokaomath、gaokaophysics） | **1213 份** | 只登记年份/卷别/适用地区/文件路径/sha256，**不复制大文件**，题目正文待 OCR 或人工录入 |
| 隔离区 | 古诗文默写候选（来源：GitHub Reciter，社区整理） | 472 条 | T4 来源，标记 `rejected`，**未核对不得使用**，用来演示"野题闸门" |

覆盖度明细见自动生成报告： [`reports/coverage.md`](reports/coverage.md)（学科×年份矩阵、来源等级分布、缺口清单）、
[`reports/provenance.md`](reports/provenance.md)（每一条题目的出处 URL）。

## 二、为什么"不要野题"

每条记录必须能回答三个问题：**谁发的？在哪？什么时候抓的？** 规则写在 [`docs/sources.md`](docs/sources.md)：

- 来源分 **T1-T4**：T1 命题机构官方（教育部教育考试院、各省考试院）；T2 官方授权媒体（中国教育在线等）；
  T3 大型教育媒体/开放数据集；T4 社区/UGC/文库/公众号/AI 生成。
- **T4 与无 URL 的记录禁止直接进入 `data/questions/`**，先进 `data/quarantine/`，核验后升级。
- `verified` 必须有 ≥2 个**互相独立**的出处（同一篇稿子的不同转载站不算）。
- 冲突内容标 `conflict` 隔离待裁决，不猜、不改、不糊弄。

`qbnk validate` 会把这些规则变成硬检查（见下表），CI 里跑不过就不能合。

| 规则 | 拦截内容 |
| --- | --- |
| `E-SRC-UNKNOWN` | `source_id` 没在 `sources/registry.json` 登记 |
| `E-SRC-HOST` | `source.url` 的域名与登记表不符（防伪造链接） |
| `E-SRC-T4` | T4 来源直接进了正式库 |
| `E-SRC-NOURL` | 没有可核验的出处链接（野题） |
| `E-VERIFY-EVIDENCE` | 声称 `verified` 却拿不出第二个来源 |
| `E-NO-ANSWER` | 客观题没有标准答案 |
| `E-DUP-ID` / `E-DUP-NO` | 重复 id、同一卷内重复题号 |
| `W-HASH-MISMATCH` | 正文被改动但 `content_hash` 没更新 |

## 三、目录结构

```
schema/                     数据规范（JSON Schema）
  question.schema.json      题目记录
  paper.schema.json         试卷记录
sources/
  registry.json             来源登记表（等级/覆盖/许可/抓取策略）
  adapters/                 采集适配器（见下）
data/
  questions/*.jsonl         正式题库（已过校验）
  papers/*.jsonl            试卷层：已收录 + 外部原卷档案索引
  staging/                  适配器产出，**待人工复核**后才可入库
  quarantine/               隔离区（T4 / 冲突 / 待裁决）
  index/                    自动生成的索引（按学科/年份/卷别/题型）
reports/                    自动生成的覆盖度与溯源报告
tools/qbnk/                 工具链（校验/查重/索引/报告/来源复核）
docs/                       规范与流程说明
```

## 四、快速开始

```bash
git clone https://github.com/zhzx2026/gaokao-qbnk.git && cd gaokao-qbnk
pip install -r requirements.txt          # 可选：装 jsonschema 后校验更严格

python3 -m tools.qbnk.cli validate --fix-hash   # 校验 + 补全内容哈希
python3 -m tools.qbnk.cli stats                 # 概览统计
python3 -m tools.qbnk.cli dedup                 # 查重（精确 + 近似）
python3 -m tools.qbnk.cli index                 # 生成 data/index/*.json
python3 -m tools.qbnk.cli report                # 生成 reports/*.md
python3 -m tools.qbnk.cli verify-sources        # 复核所有出处链接是否还活着（需联网）
python3 -m tools.qbnk.cli check-staging         # 检查 data/staging/ 适配器产出是否可复核
python3 -m tools.qbnk.cli viz                   # 生成可视化看板 site/index.html（自包含，双击即可打开）
```

一条命令跑完：`make pipeline`（等价于 validate → stats → dedup → index → report）。

可视化看板：`make serve` 后打开 <http://localhost:8000>（或直接打开 `site/index.html`）——覆盖度热力图、来源/核验分布、作文题浏览、试卷档案检索、来源登记与"野题闸门"。修改数据后重新运行 `make viz` 刷新。

## 五、采集适配器

适配器产出**一律先落到 `data/staging/`**，人工复核后才可移进 `data/questions/`；
所有适配器遵守 robots.txt、单域名 ≥1s 限速，不绕登录、不碰付费内容（[抓取礼仪](docs/sources.md#4-抓取礼仪适配器必须遵守)）。

| 适配器 | 来源 | 需要网络 | 输出 |
| --- | --- | --- | --- |
| `sources/adapters/gaokaomath_papers.py` | deekur/gaokaomath（数学原卷 PDF，1952-2026） | 否（本地克隆） | `data/papers/archive_math.jsonl` |
| `sources/adapters/gaokaophysics_papers.py` | deekur/gaokaophysics（物理原卷 PDF） | 否（本地克隆） | `data/papers/archive_physics.jsonl` |
| `sources/adapters/dxsbb_zuowen.py` | 大学生必备网历年作文汇总（T3） | 是 | `data/staging/zuowen_dxsbb.jsonl` |
| `sources/adapters/eol_zhenti.py` | 中国教育在线真题栏目（T2） | 是 | `data/staging/eol_zhenti.jsonl` |
| `sources/adapters/reciter_moxie.py` | GitHub Reciter 默写题库（T4） | 否（本地克隆） | `data/quarantine/reciter_moxie.jsonl` |

例：把数学原卷档案变成试卷索引（1213 份里的 777 份来自这里）

```bash
git clone --depth 1 https://github.com/deekur/gaokaomath.git /tmp/gaokaomath
python3 sources/adapters/gaokaomath_papers.py --repo /tmp/gaokaomath \
  --out data/papers/archive_math.jsonl
python3 -m tools.qbnk.cli validate
```

## 六、用 GitHub Actions 跑采集（不用自己开机器）

需要联网的采集全部放在 Actions 上，跑完自动开 PR 等人复核，`data/questions/` 永远只进人工看过的题。

| Workflow | 触发时机 | 做什么 |
| --- | --- | --- |
| [`collect.yml`](.github/workflows/collect.yml) | 高考季 **6/7–6/12 每天** + 平时**每周日**；可手动 | 跑 dxsbb / eol 适配器 → `data/staging/` → `check-staging` → 开 PR（label `collect`） |
| [`qbnk.yml`](.github/workflows/qbnk.yml) | 每次 push / PR | `validate --strict` + `dedup` + 重建索引与报告，生成物不一致直接报红 |
| [`sources-health.yml`](.github/workflows/sources-health.yml) | **每月 1 号**；可手动 | 复核全部出处链接；失效的开 issue（label `source-dead-link`），报告提交回仓库 |

手动跑一次采集：Actions → **collect** → `Run workflow` → 选 `adapters`（all / dxsbb / eol）→ 勾 `open_pr`。

几个实现上的注意点（踩过的坑已经写进 workflow）：

- 采集分支形如 `collect/20260929-0317`，PR 的 base 是仓库默认分支；
- `GITHUB_TOKEN` 建的 PR 默认不会触发其它 workflow，所以 collect 末尾会显式
  `gh workflow run qbnk.yml --ref <branch>`，让校验真的在 PR 上跑一遍；
- 采集失败（源站限流/改版/robots 禁止）不算 job 失败，只在 job summary 里提示，避免误报报警；
- 链接失效 ≠ 立刻删题：先补 web archive 等存档链接写进 `source.evidence[]`，补不上再降级或移入隔离区。

## 七、怎么加一道题

1. 先确认来源等级：官方/权威媒体 → 可用；社区/文库 → 进隔离区等核验。
2. 抄一条 `data/questions/zuowen.jsonl` 里的记录改，或在 `sources/registry.json` 登记新来源后新建分片。
3. `python3 -m tools.qbnk.cli new-id --year 2026 --subject 数学 --paper 全国I卷 --seq 1` 生成合规 id。
4. `python3 -m tools.qbnk.cli validate --fix-hash` 跑绿了，再提 PR（CI 会自动再跑一遍）。

字段含义见 [`docs/schema.md`](docs/schema.md)，完整流程见 [`docs/pipeline.md`](docs/pipeline.md)。

## 八、许可与责任

- **代码、schema、适配器**：MIT，见 [LICENSE](LICENSE)。
- **数据**：试题著作权归命题机构，本库以学习研究/教学参考为目的收录并逐条标注出处，
  见 [DATA-LICENSE.md](DATA-LICENSE.md)。权利人不希望被收录的，提 issue/PR，48 小时内删除。
- 已知的数据问题登记在 [`docs/known-issues.md`](docs/known-issues.md)。
