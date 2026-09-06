# Flight Management System (Admin API)

A high-performance, asynchronous backend service built with **FastAPI**, **SQLAlchemy 2.0 (Async)**, and **PostgreSQL** for managing flight inventories, physical seat maps, and administrative auditing.

---

## Tech Stack

* **Framework:** FastAPI (Python)
* **Database & ORM:** PostgreSQL, SQLAlchemy (AsyncEngine with asyncpg)
* **Validation:** Pydantic v2
* **Server:** Uvicorn (ASGI)

---

## Project Structure

```text
Flight_Management_System/
├── app/
│   ├── api/v1/         # FastAPI endpoints (admin_flights.py)
│   ├── core/           # Database session & security/RBAC
│   ├── models/         # SQLAlchemy models (Flight, Seat, AuditLog, Base)
│   ├── schemas/        # Pydantic validation models
│   └── services/       # Business logic helpers (seat mapping, auditing)
├── venv/               # Python virtual environment
├── main.py             # Application entry point
└── requirements.txt    # Project dependencies
