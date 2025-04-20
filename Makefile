.PHONY: test coverage clean run lint

# Run the application
run:
	python app.py

# Run tests
test:
	python -m pytest

# Run tests with coverage
coverage:
	python -m pytest --cov=app --cov-report=term-missing
	python -m pytest --cov=app --cov-report=html

# Clean up pyc files and cache
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ build/ dist/

# Install dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
dev-install:
	pip install -r requirements.txt
	pip install pytest pytest-cov flake8 black

# Run linting
lint:
	flake8 app.py test_app.py

# Format code
format:
	black app.py test_app.py
