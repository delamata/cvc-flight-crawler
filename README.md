# ✈ CVC Flight Price Crawler

> Monitor automatizado de tarifas aéreas — CVC Viagens  
> Stack: **Python 3.11 · Playwright · FastAPI · SQLite/PostgreSQL · GitHub Actions**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![Playwright](https://img.shields.io/badge/Playwright-1.44-orange?logo=playwright)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📁 Estrutura

```
cvc-flight-crawler/
├── crawler/          # Lógica de scraping (Playwright + BeautifulSoup)
├── api/              # FastAPI — endpoints REST
├── scheduler/        # APScheduler — execução periódica
├── dashboard/        # Front-end HTML do feed
├── tests/            # Testes automatizados
└── .github/workflows # CI/CD + cron job
```

---

## 🚀 Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/cvc-flight-crawler.git
cd cvc-flight-crawler

# 2. Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt
playwright install chromium

# 4. Configure o .env
cp .env.example .env
# Edite o .env com suas configurações

# 5. Inicie a API + scheduler
python scheduler/job.py
```

## 🐳 Docker

```bash
docker-compose up --build
```

## 🌐 Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /feed | Lista tarifas com filtros |
| GET | /feed/latest | Últimas 50 tarifas coletadas |
| GET | /health | Status da API |

## ⚠️ Configuração dos Seletores

Após clonar, valide os seletores CSS em `crawler/parser.py` contra o HTML real do site.  
Consulte o guia em `docs/ajuste-seletores.md`.

## 📄 Licença

MIT © CVC Viagens — Uso interno
