# Developer shortcuts. The pipeline itself lives in the CLI: `sfmkit run`.
CONFIG ?= configs/valencia/cpu.yaml
DEVICE ?= cpu
# The package that test, lint and check work on, in its own environment.
PKG    ?= sfmkit
RUN    ?= runs/$(notdir $(patsubst %/,%,$(dir $(CONFIG))))/$(notdir $(basename $(CONFIG)))
# Where images are published. OWNER is the GitHub account the packages hang off.
REGISTRY ?= ghcr.io
OWNER    ?= dpadillaor
COMMIT   := $(shell git rev-parse HEAD)

.PHONY: help run view test lint env image push check clean-run

help:
	@echo "make run     CONFIG=configs/<dataset>/<config>.yaml   run the whole pipeline"
	@echo "make view                                 the viewer on runs/, at http://127.0.0.1:8000"
	@echo "make test   [PKG=sfmkit|viewer]           test suite (no dataset needed)"
	@echo "make lint   [PKG=sfmkit|viewer]           ruff + import contracts"
	@echo "make check  [PKG=sfmkit|viewer]           lint + test"
	@echo "make env                                  .env with your UID/GID, for docker compose"
	@echo "make image  [DEVICE=cpu]                   docker image sfmkit:$(DEVICE), stamped with the commit"
	@echo "make push   [DEVICE=gpu]                   publish it to $(REGISTRY)/$(OWNER), commit and all"
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
	GIT_COMMIT=$(COMMIT) docker compose build $(if $(filter gpu,$(DEVICE)),cli-gpu,cli)

# Publishing by hand, for the GPU image: CI cannot build it (CUDA PyTorch and
# COLMAP's CUDA build do not fit a hosted runner's disk), so it is built where
# there is a GPU. What CI would have given it is added here instead: it refuses
# to publish from a dirty tree, and the commit goes in as a label as well as an
# environment variable, so `docker inspect` says which code is inside.
#
# Once: docker login $(REGISTRY) -u <you>, with a token that can write packages.
push: image
	@test -z "$$(git status --porcelain)" || \
		{ echo "the working tree is dirty: commit first, so the image names real code"; exit 1; }
	docker tag sfmkit:$(DEVICE) $(REGISTRY)/$(OWNER)/sfmkit:$(DEVICE)
	docker tag sfmkit:$(DEVICE) $(REGISTRY)/$(OWNER)/sfmkit:$(DEVICE)-$(shell git rev-parse --short HEAD)
	docker push $(REGISTRY)/$(OWNER)/sfmkit:$(DEVICE)
	docker push $(REGISTRY)/$(OWNER)/sfmkit:$(DEVICE)-$(shell git rev-parse --short HEAD)
	@echo "published $(REGISTRY)/$(OWNER)/sfmkit:$(DEVICE) from $(COMMIT)"

check: lint test

clean-run:
	rm -rf $(RUN)
