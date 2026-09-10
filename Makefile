# Developer shortcuts. The pipeline itself lives in the CLI: `sfmkit run`.
CONFIG ?= configs/valencia/9cameras.yaml
DEVICE ?= cpu
# The package that test, lint and check work on, in its own environment.
PKG    ?= sfmkit
RUN    ?= runs/$(notdir $(patsubst %/,%,$(dir $(CONFIG))))/$(notdir $(basename $(CONFIG)))

.PHONY: help run view test lint env image check clean-run

help:
	@echo "make run     CONFIG=configs/<dataset>/<config>.yaml   run the whole pipeline"
	@echo "make view                                 the viewer on runs/, at http://127.0.0.1:8000"
	@echo "make test   [PKG=sfmkit|viewer]           test suite (no dataset needed)"
	@echo "make lint   [PKG=sfmkit|viewer]           ruff + import contracts"
	@echo "make check  [PKG=sfmkit|viewer]           lint + test"
	@echo "make env                                  .env with your UID/GID, for docker compose"
	@echo "make image  [DEVICE=cpu]                   docker image sfmkit:$(DEVICE), stamped with the commit"
	@echo ""
	@echo "individual stages: sfmkit <stage> --config ..."
	@echo "                   sfmkit run --help"

run:
	sfmkit run --config $(CONFIG)

view:
	sfmview --runs runs

test:
	cd packages/$(PKG) && pytest -q

lint:
	ruff check .
	cd packages/$(PKG) && lint-imports

env:
	@printf 'UID=%s\nGID=%s\n' "$$(id -u)" "$$(id -g)" > .env
	@cat .env

image:
	GIT_COMMIT=$(shell git rev-parse HEAD) docker compose build $(if $(filter gpu,$(DEVICE)),cli-gpu,cli)

check: lint test

clean-run:
	rm -rf $(RUN)
