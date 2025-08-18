# Oraculum – Wysocki Indicator MVP

## Avvio rapido
### Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

### Frontend
cd frontend
npm install
npm run dev

### Endpoints
GET /api/v1/health
GET /api/v1/wi?tickers=APP&tickers=NVDA
GET /api/v1/wi/backtest?tickers=APP&rank_date=2024-01-15&to=2024-06-15
