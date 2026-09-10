# Developer shortcuts. The pipeline itself lives in the CLI: `sfmkit run`.
CONFIG ?= configs/valencia/all9.yaml
RUN    ?= runs/$(notdir $(patsubst %/,%,$(dir $(CONFIG))))/$(notdir $(basename $(CONFIG)))

.PHONY: help run test lint image check clean-run

help:
	@echo "make run     CONFIG=configs/<dataset>/<config>.yaml   run the whole pipeline"
	@echo "make test                                 test suite (no dataset needed)"
	@echo "make lint                                 ruff + import contracts"
	@echo "make check                                lint + test"
	@echo "make image                                docker image, tagged with the commit"
	@echo ""
	@echo "individual stages: sfmkit <stage> --config ..."
	@echo "                   sfmkit run --help"

run:
	sfmkit run --config $(CONFIG)

test:
	pytest -q

lint:
	ruff check src tests
	lint-imports

image:
	GIT_COMMIT=$(shell git rev-parse HEAD) docker compose build

check: lint test

clean-run:
	rm -rf $(RUN)
