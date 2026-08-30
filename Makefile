.PHONY: beta-preview-check format-benchmark-check foundation-check acquisition-check acquisition-inspect m1-structural-check monitor-check normalization-check operations-check pipeline-test pipeline-validate refresh-rehearsal-check release-bundle-check repository-check service-test service-check sicily-release-check storage-check web-check

PIPELINE_PYTHON ?= pipeline/.venv/bin/python

foundation-check: pipeline-test pipeline-validate web-check

format-benchmark-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_format_benchmark.py
	$(PIPELINE_PYTHON) -m thermal_drought.format_benchmark

m1-structural-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_structural_validation.py
	$(PIPELINE_PYTHON) -m thermal_drought.structural_validation

release-bundle-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_release_bundle.py
	$(PIPELINE_PYTHON) -m thermal_drought.release_bundle build

operations-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_operations.py pipeline/tests/test_runtime.py pipeline/tests/test_release_bundle.py
	$(PIPELINE_PYTHON) -m thermal_drought.operations

monitor-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_monitor.py

refresh-rehearsal-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_refresh.py
	$(PIPELINE_PYTHON) -m thermal_drought.refresh rehearse

acquisition-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_acquisition.py
	$(PIPELINE_PYTHON) -m thermal_drought.acquire status

acquisition-inspect:
	$(PIPELINE_PYTHON) -m thermal_drought.acquire inspect

normalization-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_aggregation.py pipeline/tests/test_normalization.py
	$(PIPELINE_PYTHON) -m thermal_drought.normalize --report pipeline/reports/sicily-release-v1.json

service-test:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_aggregation.py pipeline/tests/test_classification.py pipeline/tests/test_service.py

service-check: service-test pipeline-validate
	$(PIPELINE_PYTHON) -m thermal_drought.api --check

sicily-release-check: acquisition-inspect normalization-check service-check

storage-check:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests/test_storage.py
	$(PIPELINE_PYTHON) -m thermal_drought.storage validate
	$(PIPELINE_PYTHON) -m thermal_drought.storage status
	$(PIPELINE_PYTHON) -m thermal_drought.storage preflight --years 2

pipeline-test:
	$(PIPELINE_PYTHON) -m pytest pipeline/tests

pipeline-validate:
	$(PIPELINE_PYTHON) -m thermal_drought.contracts validate config/variables

repository-check:
	$(PIPELINE_PYTHON) -m thermal_drought.repository_audit

beta-preview-check:
	cd web && npm run build
	$(PIPELINE_PYTHON) -m thermal_drought.preview --check --manifest-output output/m1-beta-preview/manifest.json

web-check:
	cd web && npm run check
