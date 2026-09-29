# 采集 → 入库流程

```
 ┌─ 线索 ─┐    ┌── 适配器/人工 ──┐    ┌── staging ──┐    ┌── 人工复核 ──┐    ┌── 正式库 ──┐
 │ 来源发现 │───►│ 抽取 + 写溯源块 │───►│ data/staging │───►│ 比对第二来源 │───►│ data/      │
 └────────┘    └───────────────┘    └────────────┘    └──────┬───────┘    │ questions/ │
                                                            │            └─────┬──────┘
                                                       冲突/无源 ──► quarantine ◄────┘
                                                                                 ▲
                                                              T4 来源 ───────────┘
```

## 1. 发现线索

- 优先顺序：T1（考试院）→ T2（中国教育在线等授权媒体）→ T3（大型教育媒体/开放数据集）→ T4（仅作线索）。
- 新增来源先在 `sources/registry.json` 登记：等级、覆盖（学科/年份/地区）、抓取策略、许可、适配器。

## 2. 抽取

- 有适配器的跑适配器；没有的走人工录入（人工录入同样要写完整的 `source` 块）。
- 适配器**只输出到 `data/staging/`**，绝不直接写进 `data/questions/`。
- 抽取时保留原文，不做"顺手修正"；发现异样写进 `notes`，不要静默改数据。

## 3. 人工复核（不可跳过）

1. 与第二个**独立来源**逐字比对题干、选项、答案；
2. 一致 → `verification.status = verified`，把第二个来源写进 `source.evidence[]`；
3. 只有一个来源 → `single_source`（可用，但导出与展示时必须标注）；
4. 两个版本冲突 → `conflict`，进 `data/quarantine/`，人工裁决后再回库；
5. T4 来源、AI 生成、网盘/文库链接、无法核验的 → 一律进 `data/quarantine/`，状态 `rejected`。

## 4. 入库

```bash
mv data/staging/xxx.jsonl data/questions/xxx.jsonl
python3 -m tools.qbnk.cli validate --fix-hash
python3 -m tools.qbnk.cli dedup
python3 -m tools.qbnk.cli index && python3 -m tools.qbnk.cli report
```

## 5. 持续维护

- `qbnk verify-sources` 定期复核所有出处链接；源站删稿的记录降级为 `single_source` 并在 `notes` 说明，
  找不到任何存档的移入隔离区。
- `content_hash` 是正文指纹：正文被改动而哈希没更新会触发 `W-HASH-MISMATCH`，防止"悄悄改题"。
- CI（`.github/workflows/qbnk.yml`）在每次 PR 跑 validate + dedup，红就不合。

## 6. 沙箱/离线环境提示

在受限网络（如本仓库的开发沙箱）里，bash 出网可能被限制，此时：

- **能跑**：基于本地克隆的适配器（gaokaomath / gaokaophysics / Reciter）、全部校验与报告命令；
- **跑不了**：需要抓取网页的适配器（dxsbb / eol）会明确报 `抓取失败 …（本适配器需联网环境运行）`，
  换到能联网的机器或 CI 上执行即可，产出物格式完全一致。
