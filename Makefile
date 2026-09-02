# Pipeline stages, in order. The order lives here, not in module names.
CONFIG ?= configs/valencia_all9.yaml
RUN    ?= runs/$(notdir $(basename $(CONFIG)))

.PHONY: all match verify reconstruct localize evaluate test lint clean-run help

help:
	@echo "make all CONFIG=configs/<name>.yaml   run the whole pipeline"
	@echo "make test                             run the test suite (no dataset needed)"
	@echo "make lint                             ruff check + format --check"
	@echo ""
	@echo "stages: match -> verify -> reconstruct -> localize -> evaluate"

all: evaluate

match:
	sfmkit match --config $(CONFIG) --out $(RUN)

verify: 
	sfmkit verify --config $(CONFIG) --out $(RUN)

reconstruct:
	sfmkit reconstruct --config $(CONFIG) --out $(RUN)

localize:
	sfmkit localize --config $(CONFIG) --out $(RUN)

evaluate:
	sfmkit evaluate --config $(CONFIG) --out $(RUN)

test:
	pytest -q

lint:
	ruff check src tests && ruff format --check src tests

clean-run:
	rm -rf $(RUN)
