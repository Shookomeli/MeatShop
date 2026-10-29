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
| `CURRENCY_DISPLAY_UNIT` | `RIAL` | Kept for compatibility. All monetary displays are Rial; Toman is shown only as an approximate hint under price-entry fields. All stored values are Rial. |
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
- **Presentation Layer**: Every monetary display (screens, A5 printouts, lists, reports) shows Rial through one shared formatter (`sales.date_utils.format_rial` / template filters `rial` and `thousands`; `formatRial` in `base.html` for live previews): Persian digits with `,` thousands separators, e.g. `۱۲,۵۰۰,۰۰۰ ریال`. Toman (`amount_rial // 10`) is used only as an approximate hint under price-entry fields. Formatting never changes stored values.
- **No Floating-Point Financials**: Avoid binary float calculations; use integer Rial or `Decimal` throughout calculation pipelines.
- **Invoice Line Calculation** (`sales.services.calculate_line_total_rial`): `line_total_rial = weight_kg × unit_price_rial` (or `quantity × unit_price_rial` for non-kg units), truncated to whole Rial (`ROUND_DOWN`). `Invoice.total_amount_rial` is the sum of its line totals.
- **Weight Precision** (`sales.services.normalize_weight_kg`): invoice weights are normalized to 0.001 kg with `ROUND_HALF_EVEN` (the same rule Django uses when reading a stored `DecimalField`) before being saved and before the line total is computed, so the stored weight and the line total always agree. Weights already at 0.001 precision are unchanged; inputs with more than three decimals are rounded first.

### Stock Movement Rule
Stock changes only through goods receipts, goods issues, processing records and approved reconciliation adjustments. Invoices are financial documents and never create stock movements, including invoices created directly on the invoice form.

### Loss Reporting
The loss report shows two separate metrics:
- **Theoretical movement balance**: incoming minus outgoing movements for the period, excluding reconciliation `ADJUSTMENT` movements.
- **Confirmed physical loss**: the sum of positive discrepancies (shortages) from complete reconciliations with status `APPROVED` or `CLOSED`. Surpluses, exact matches, drafts and calculated-but-unapproved records are not counted.

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

# 4. Run test suite (uses an isolated in-memory test database)
pytest
# or: python manage.py test
# On Windows, set PYTHONUTF8=1 first so Persian command output never fails on a non-UTF-8 console

# 5. Start development server
python manage.py runserver 0.0.0.0:3000
```
