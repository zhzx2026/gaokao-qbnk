# 溯源报告

> 自动生成（qbnk report）· 2026-09-29

## 已使用来源

| source_id | Tier | 题量 | 来源名称 | 主页 |
|---|---|---|---|---|
| gh-gaokaomath | T3 | 777 | GitHub deekur/gaokaomath：历年高考数学真题原卷（1952-2026） | https://github.com/deekur/gaokaomath |
| gh-gaokaophysics | T3 | 436 | GitHub deekur/gaokaophysics：历年高考物理真题原卷（1952-2026） | https://github.com/deekur/gaokaophysics |
| dxsbb-zuowen | T3 | 66 | 大学生必备网·历年高考作文题目汇总（分卷别） | https://www.dxsbb.com/news/list_457.html |
| eol-gkzx | T2 | 4 | 中国教育在线·转载教育部教育考试院试题解析 | https://www.eol.cn/kaoshi/gaokao/gkzx/ |

## 未使用（登记待采集）

| source_id | Tier | 状态 | 适配器 | 备注 |
|---|---|---|---|---|
| neea-zhongguokaoshi | T1 | planned | — | 每年 6 月发布全国卷试题评析与部分答案（语文/数学/英语），是最高等级依据。 |
| eol-gaokao | T2 | planned | sources/adapters/eol_zhenti.py | 栏目化发布当年真题与答案解析；沙箱网络受限时适配器需在可联网环境运行。 |
| bjd-news | T2 | active | — | 2026 年高考语文全国卷作文命题思路报告全文转载。 |
| bendibao-zuowen | T3 | active | — | 2026 年五套卷作文题交叉验证用。 |
| sina-edu | T3 | active | — | 转载教育部教育考试院 2026 年作文试题解析，作为第三方佐证。 |
| gh-papers-index | T4 | planned | — | 用于生成「应采集试卷清单 / 覆盖率矩阵」，不直接作为题目来源。 |
| gh-reciter | T4 | planned | sources/adapters/reciter_moxie.py | 默写篇目为公共领域古诗文，但「考频/真题出处」标注为社区整理，入库前须逐条核对真题原卷，否则按 T4 处理。 |
| zxxk | T3 | blocked | — | 仅可人工摘录已获授权内容并标注来源；不提供自动抓取适配器。 |
| jyeoo | T3 | blocked | — | 同学科网。可作为答案核对线索，不作正文来源。 |
| huaue-zuowen | T4 | blocked | — | 覆盖年份最全（含 1951-2011），但抓取不稳定、缺出处；仅用于补录线索，须与 T1-T3 核对后才可入库。 |
| baike-zuowen | T4 | planned | — | 只作交叉验证与线索，不作唯一来源。 |

## 全部题目出处清单

| id | 卷别 | 题型 | Tier | 校验 | 来源 URL |
|---|---|---|---|---|---|
| q-2021-yw-beijing-001 | 2021 北京卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2021-yw-shanghai-001 | 2021 上海卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/99991.html |
| q-2021-yw-tianjin-001 | 2021 天津卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116376.html |
| q-2022-yw-beijing-001 | 2022 北京卷 | 微写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2022-yw-beijing-002 | 2022 北京卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2022-yw-quanguojia-001 | 2022 全国甲卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2022-yw-quanguoyi-001 | 2022 全国乙卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2022-yw-shanghai-001 | 2022 上海卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/99991.html |
| q-2022-yw-tianjin-001 | 2022 天津卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116376.html |
| q-2022-yw-xingaokao1-001 | 2022 新高考I卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2022-yw-xingaokao2-001 | 2022 新高考II卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2023-yw-beijing-001 | 2023 北京卷 | 微写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2023-yw-beijing-002 | 2023 北京卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2023-yw-quanguojia-001 | 2023 全国甲卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2023-yw-quanguoyi-001 | 2023 全国乙卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2023-yw-shanghai-001 | 2023 上海卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/99991.html |
| q-2023-yw-tianjin-001 | 2023 天津卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116376.html |
| q-2023-yw-xinkebiao1-001 | 2023 新课标I卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2023-yw-xinkebiao2-001 | 2023 新课标II卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2024-yw-beijing-001 | 2024 北京卷 | 微写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2024-yw-beijing-002 | 2024 北京卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2024-yw-quanguojia-001 | 2024 全国甲卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2024-yw-shanghai-001 | 2024 上海卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/99991.html |
| q-2024-yw-tianjin-001 | 2024 天津卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116376.html |
| q-2024-yw-xinkebiao1-001 | 2024 新课标I卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2024-yw-xinkebiao2-001 | 2024 新课标II卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2025-yw-beijing-001 | 2025 北京卷 | 微写作 | T3 | single_source | https://www.dxsbb.com/news/116375.html |
| q-2025-yw-quanguo1-001 | 2025 全国一卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2025-yw-quanguo2-001 | 2025 全国二卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/136500.html |
| q-2025-yw-shanghai-001 | 2025 上海卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/99991.html |
| q-2025-yw-tianjin-001 | 2025 天津卷 | 写作 | T3 | single_source | https://www.dxsbb.com/news/116376.html |
| q-2026-yw-beijing-001 | 2026 北京卷 | 微写作 | T3 | verified | https://www.dxsbb.com/news/116375.html |
| q-2026-yw-beijing-002 | 2026 北京卷 | 写作 | T3 | verified | https://www.dxsbb.com/news/116375.html |
| q-2026-yw-quanguo1-001 | 2026 全国I卷 | 写作 | T2 | verified | https://www.eol.cn/kaoshi/gaokao/gkzx/202606/t20260607_2742041.shtml |
| q-2026-yw-quanguo2-001 | 2026 全国II卷 | 写作 | T2 | verified | https://www.eol.cn/kaoshi/gaokao/gkzx/202606/t20260607_2742041.shtml |
| q-2026-yw-shanghai-001 | 2026 上海卷 | 写作 | T3 | verified | https://www.dxsbb.com/news/99991.html |
| q-2026-yw-tianjin-001 | 2026 天津卷 | 写作 | T3 | verified | https://www.dxsbb.com/news/116376.html |
