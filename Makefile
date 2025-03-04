

check:
	poetry run pre-commit run -a


test-llm-investigate:
	poetry run pytest tests/llm/test_investigate.py -n 6 -vv
