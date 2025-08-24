

check:
	poetry run pre-commit run -a


test-llm-investigate:
	poetry run pytest tests/llm/test_investigate.py -n 6 -vv

test-llm-ask-holmes:
	poetry run pytest tests/llm/test_ask_holmes.py -n 6 -vv

test-without-llm:
	poetry run pytest tests -m "not llm"

# Local development with Skaffold
.PHONY: dev dev-run dev-debug dev-clean

# Start development with hot reload
dev:
	@echo "Starting Holmes with operator (hot reload enabled)..."
	@echo "Ports forwarded: API=9090, Operator=9091"
	skaffold dev

# Deploy once without watching
dev-run:
	@echo "Deploying Holmes with operator..."
	skaffold run

# Debug mode with verbose output
dev-debug:
	@echo "Starting Holmes in debug mode..."
	skaffold dev -v debug

# Clean up everything
dev-clean:
	@echo "Cleaning up..."
	skaffold delete

# Run operator tests
test-operator:
	poetry run pytest tests/test_check_api.py -v

# Build operator image separately
operator-build:
	@echo "Building operator image..."
	docker build -t holmes-operator:latest operator/

# Run operator locally for development
operator-run:
	@echo "Running operator locally..."
	cd operator && HOLMES_API_URL=http://localhost:9090 kopf run -A --standalone main.py
