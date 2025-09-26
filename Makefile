

##@ Checks
check: poetry
	${POETRY} run pre-commit run -a

test-llm-investigate: poetry
	${POETRY} run pytest tests/llm/test_investigate.py -n 6 -vv

test-llm-ask-holmes: poetry
	${POETRY} run pytest tests/llm/test_ask_holmes.py -n 6 -vv

test-without-llm: poetry
	${POETRY} run pytest tests -m "not llm"

##@ Docs
docs: poetry
	${POETRY} run mkdocs serve --dev-addr=127.0.0.1:7000

docs-build: poetry
	${POETRY} run mkdocs build

docs-strict: poetry
	${POETRY} run mkdocs serve --dev-addr=127.0.0.1:7000 --strict

##@ Dependencies

deps-install: poetry
	${POETRY} install

deps-lock: poetry
	${POETRY} lock

##@ Tools

POETRY = $(shell pwd)/bin/poetry
POETRY_VERSION = 1.8.5

.PHONY: poetry
poetry:  ## Download poetry locally if necessary.
	@if [ ! -f $(POETRY) ] || ! $(POETRY) --version | grep -q "$(POETRY_VERSION)"; then \
		echo "Installing poetry $(POETRY_VERSION)"; \
		curl -sSL https://install.python-poetry.org | POETRY_HOME=$(shell pwd) python3 - --version $(POETRY_VERSION); \
	fi
