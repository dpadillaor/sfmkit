# Developer shortcuts. The pipeline itself lives in the CLI: `sfmkit run`.
CONFIG ?= configs/valencia/9cameras.yaml
DEVICE ?= cpu
RUN    ?= runs/$(notdir $(patsubst %/,%,$(dir $(CONFIG))))/$(notdir $(basename $(CONFIG)))

.PHONY: help run test lint env image check clean-run

help:
	@echo "make run     CONFIG=configs/<dataset>/<config>.yaml   run the whole pipeline"
	@echo "make test                                 test suite (no dataset needed)"
	@echo "make lint                                 ruff + import contracts"
	@echo "make check                                lint + test"
	@echo "make env                                  .env with your UID/GID, for docker compose"
	@echo "make image  [DEVICE=cpu]                   docker image sfmkit:$(DEVICE), stamped with the commit"
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

env:
	@printf 'UID=%s\nGID=%s\n' "$$(id -u)" "$$(id -g)" > .env
	@cat .env

image:
	GIT_COMMIT=$(shell git rev-parse HEAD) docker compose build $(if $(filter gpu,$(DEVICE)),cli-gpu,cli)

check: lint test

clean-run:
	rm -rf $(RUN)
