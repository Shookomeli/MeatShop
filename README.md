# MeatShop — Local Weighing, Inventory & Invoice Management System

سیستم مدیریت توزین، انبارداری و صدور فاکتور فروشگاه گوشت و مرغ با فریم‌ورک جنگو و رابط کاربری فارسی

---

## 1. Overview & Architecture

MeatShop is a desktop/local operational system designed for a local Persian meat and chicken retail and wholesale shop. The application runs locally with Django, SQLite, and server-rendered templates.

### Key Architecture Components
- **Framework**: Django 5.2+ on Python 3.10+ / 3.13.
- **Database**: SQLite (strictly separated between development and production).
- **Scale Package**: Plain Python package (`scale/`) kept outside `INSTALLED_APPS` with a clean `ScaleInterface`.
- **Localization**: Native Persian (`fa-ir`) layout (`dir="rtl"`) with `Asia/Tehran` time zone.

---

## 2. Configuration & Environment Variables

Environment settings are configured via `.env` (derived from `.env.example`).

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | *(insecure dev key)* | Cryptographic signing key. Must be a strong unique string in production. |
| `DEBUG` | `True` | Set to `False` in production. |
| `SCALE_MODE` | `mock` | Scale integration mode: `mock` (development) or `keli_xk3118t1` (hardware). |
| `CURRENCY_DISPLAY_UNIT` | `TOMAN` | Presentation unit: `TOMAN` or `RIAL`. Affects display only; all stored values are Rial. |
| `DATABASE_PATH` | *(none)* | Custom absolute path to SQLite file (e.g. `C:\MeatShop\data\db.sqlite3` in production). |

---

## 3. Database Separation & Migration Rules

### Strict Separation Policy
- **Development Database**: `BASE_DIR / 'db.sqlite3'` (local repository directory).
- **Production Database**: Configured via `DATABASE_PATH`, default target `C:\MeatShop\data\db.sqlite3`.

> [!CRITICAL]
> **Safety Invariant**: Never copy the developer's `db.sqlite3` over the customer's production database!
> Database schema changes must be applied strictly through Django's migration engine:
> ```bash
> python manage.py migrate
> ```
> Always back up the production database before applying migrations.

---

## 4. Currency Standard (The Rial Rule)

- **Storage Invariant**: Every monetary database field (`price_per_unit_rial`, `total_price_rial`, `line_total_rial`, etc.) stores whole-number **Rial** values as positive integers.
- **Conversion Rule**: `1 Toman = 10 Rial`.
- **Presentation Layer**: When `CURRENCY_DISPLAY_UNIT=TOMAN`, values are displayed in Toman (`amount_rial // 10`) with Persian formatting. When `CURRENCY_DISPLAY_UNIT=RIAL`, values are displayed in Rial.
- **No Floating-Point Financials**: Avoid binary float calculations; use integer Rial or `Decimal` throughout calculation pipelines.

---

## 5. Product Data Import Policy

- **Development Only**: The initial product catalogue import command (`python manage.py seed_catalogue`) is an explicit, development-only operation.
- **No Auto-Import in Production**: The system will **never** automatically seed or overwrite products in an active production database.
- **Idempotency**: Import operations use idempotent lookups (`get_or_create`) and preserve any previously modified user prices.

---

## 6. Development Workflow

```bash
# 1. Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows

# 2. Run system checks
python manage.py check

# 3. Apply migrations
python manage.py migrate

# 4. Run test suite
pytest

# 5. Start development server
python manage.py runserver 0.0.0.0:3000
```
