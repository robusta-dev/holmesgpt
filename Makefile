

check:
	poetry run pre-commit run -a


test-llm-investigate:
	poetry run pytest tests/llm/test_investigate.py -n 6 -vv

test-llm-ask-holmes:
	poetry run pytest tests/llm/test_ask_holmes.py -n 6 -vv
