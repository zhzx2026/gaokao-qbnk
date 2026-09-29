PY ?= python3
QBNK := $(PY) -m tools.qbnk.cli

.PHONY: help pipeline validate stats dedup index report verify clean

help:
	@echo "make pipeline   # validate → stats → dedup → index → report"
	@echo "make validate   # 校验题目与试卷（--fix-hash 需手动加）"
	@echo "make stats      # 概览统计"
	@echo "make dedup      # 查重"
	@echo "make index      # 生成 data/index/*.json"
	@echo "make report     # 生成 reports/*.md"
	@echo "make verify     # 复核所有出处链接（需联网）"

pipeline: validate stats dedup index report

validate:
	$(QBNK) validate

stats:
	$(QBNK) stats

dedup:
	$(QBNK) dedup

index:
	$(QBNK) index

report:
	$(QBNK) report

verify:
	$(QBNK) verify-sources

check-staging:
	$(QBNK) check-staging

collect:
	bash scripts/collect.sh

clean:
	rm -rf data/index reports
