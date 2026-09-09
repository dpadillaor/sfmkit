# Developer shortcuts. The pipeline itself lives in the CLI: `sfmkit run`.
CONFIG ?= configs/valencia_all9.yaml
RUN    ?= runs/$(notdir $(basename $(CONFIG)))

.PHONY: help run test lint typecheck check clean-run

help:
	@echo "make run     CONFIG=configs/<name>.yaml   run the whole pipeline"
	@echo "make test                                 test suite (no dataset needed)"
	@echo "make lint                                 ruff + import contracts"
	@echo "make check                                lint + test"
	@echo ""
	@echo "individual stages: sfmkit <stage> --config ... --out ..."
	@echo "                   sfmkit run --help"

run:
	sfmkit run --config $(CONFIG) --out $(RUN)

test:
	pytest -q

lint:
	ruff check src tests
	lint-imports

check: lint test

clean-run:
	rm -rf $(RUN)
