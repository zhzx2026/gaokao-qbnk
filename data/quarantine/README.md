# 隔离区（quarantine）

这里放**不能直接用**的东西：`qbnk validate` 不检查本目录，但**这些记录一旦被移进 `data/questions/`
就会校验失败**（`E-SRC-T4` / `E-REJECTED`），这就是"野题闸门"。

## 什么进这里

1. **T4 来源**（社区/UGC/文库/公众号/AI 生成）抽出来的候选题；
2. **与权威版本冲突**（`conflict`）、等人工裁决的记录；
3. 出处链接失效且找不到存档、来源无法核验的记录。

## 怎么出这里

1. 找到 T1-T3 的独立来源逐条核对题干、选项、答案；
2. 补齐 `year` / `region` / `paper` 等元数据（缺年份时用 0 占位，出区前必须补上真实年份）；
3. `verification.status` 改为 `single_source`（单源）或 `verified`（≥2 个独立来源 + 写进 `source.evidence[]`）；
4. 移动到 `data/questions/` 并运行 `python3 -m tools.qbnk.cli validate --fix-hash`。

## 当前内容

| 文件 | 来源 | 条数 | 状态 |
| --- | --- | --- | --- |
| `reciter_moxie.jsonl` | GitHub Binkic/Reciter 古诗文默写题库（MIT，但内容源自社区收集与百科） | 472 | `rejected`（T4，未核对真题出处） |
