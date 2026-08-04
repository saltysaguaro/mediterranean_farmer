.PHONY: foundation-check acquisition-check acquisition-inspect normalization-check pipeline-test pipeline-validate service-test service-check storage-check web-check

PIPELINE_PYTHON ?= pipeline/.venv/bin/python

foundation-check: pipeline-test pipeline-validate web-check

acquisition-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_acquisition.py
	$(PIPELINE_PYTHON) -m thermal_drought.acquire status

acquisition-inspect:
	$(PIPELINE_PYTHON) -m thermal_drought.acquire inspect

normalization-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_aggregation.py pipeline/tests/test_normalization.py
	$(PIPELINE_PYTHON) -m thermal_drought.normalize --report pipeline/reports/night-3-normalization.json

service-test:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_aggregation.py pipeline/tests/test_classification.py pipeline/tests/test_service.py

service-check: service-test pipeline-validate
	$(PIPELINE_PYTHON) -m thermal_drought.api --check

storage-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_storage.py
	$(PIPELINE_PYTHON) -m thermal_drought.storage validate
	$(PIPELINE_PYTHON) -m thermal_drought.storage status
	$(PIPELINE_PYTHON) -m thermal_drought.storage preflight --years 1

pipeline-test:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests

pipeline-validate:
	$(PIPELINE_PYTHON) -m thermal_drought.contracts validate config/variables

web-check:
	cd web && npm run check
