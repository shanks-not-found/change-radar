.PHONY: install test eval backend frontend run-demo

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest tests

eval:
	cd backend && python eval/run_eval.py
	cd backend && python eval/groundedness_check.py

run-demo:
	@echo "Starting StackSignal Backend and Frontend..."
	@echo "Visit http://localhost:5173 to access the dashboard."
