# MeatShop — Product Selection UX, Multi-Item Receipts & Issues, and Invoice Search (Corrected Implementation Plan)

> [!IMPORTANT]
> **Planning & Alignment Phase:** No application code, database files, or migrations have been modified in this turn. This corrected plan details the exact architectural semantics, data migration safeguards, robust idempotency controls, and acceptance criteria required prior to execution.

---

## 1. Verified System State & Baseline

- **Current Database & Strict Isolation**: SQLite 3 located at `BASE_DIR / 'db.sqlite3'` is used exclusively for local development, alongside isolated test databases created dynamically by Django's test runner (`:memory:` / test runner temporary db). The production database (`C:\MeatShop\data\db.sqlite3` on Windows) is strictly isolated and will **never** be reset, modified, or accessed during development, testing, or migration dry-runs.
- **Verified Test Baseline**: Exactly **87 passing tests** confirmed by recent test execution (`Ran 87 tests in 1.549s OK`, zero system check issues via `manage.py check`).
- **Core Ledger Invariant**: `StockMovement` (ledger table) is the **sole source of truth** for all inventory stock balances (`get_product_stock_balance`). No inventory queries sum `GoodsReceipt` or `GoodsReceiptItem` directly.

---

## 2. GoodsReceipt Legacy-Field Semantics & Authoritative Weight / Tare Source

### A. Authoritative Source Definition
- **New Multi-Item Receipts**:
  - `GoodsReceiptItem` records are the **sole authoritative source** for product-level weights (`gross_weight_kg`, `total_tare_weight_kg`, `net_weight_kg`), package counts, and line-specific condition remarks.
  - The parent `GoodsReceipt` stores document-level header aggregates: `total_gross_weight_kg` and `total_net_weight_kg`, which strictly equal the sum of child `GoodsReceiptItem` rows.
  - Legacy parent fields (`product`, `gross_weight_kg`, `total_tare_weight_kg`, `net_weight_kg`) are made nullable (`null=True, blank=True`) and are omitted/left null for new multi-item receipts.
- **Historical Single-Item Receipts**:
  - Existing records retain their historical values in `GoodsReceipt.product`, `gross_weight_kg`, `total_tare_weight_kg`, and `net_weight_kg`.

### B. Authoritative Aggregate Resolution Properties on `GoodsReceipt`
```python
from decimal import Decimal
from django.db.models import Sum

@property
def aggregate_gross_weight(self) -> Decimal:
    """Returns the authoritative gross weight across child items or legacy parent field."""
    if self.total_gross_weight_kg is not None:
        return self.total_gross_weight_kg
    if self.items.exists():
        return self.items.aggregate(total=Sum('gross_weight_kg'))['total'] or Decimal('0.000')
    return self.gross_weight_kg or Decimal('0.000')

@property
def aggregate_tare_weight(self) -> Decimal:
    """
    Authoritative tare calculation:
    For receipts with GoodsReceiptItem rows, calculate aggregate tare from the sum
    of item-level total_tare_weight_kg values.
    Use legacy parent fields only when no child item rows exist.
    """
    if self.items.exists():
        return self.items.aggregate(total=Sum('total_tare_weight_kg'))['total'] or Decimal('0.000')
    if self.total_tare_weight_kg is not None:
        return self.total_tare_weight_kg
    if self.gross_weight_kg is not None and self.net_weight_kg is not None:
        return self.gross_weight_kg - self.net_weight_kg
    return Decimal('0.000')

@property
def aggregate_net_weight(self) -> Decimal:
    """Returns the authoritative net weight across child items or legacy parent field."""
    if self.total_net_weight_kg is not None:
        return self.total_net_weight_kg
    if self.items.exists():
        return self.items.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')
    return self.net_weight_kg or Decimal('0.000')

@property
def items_count(self) -> int:
    count = self.items.count()
    if count > 0:
        return count
    return 1 if self.product_id else 0

@property
def primary_product_name(self) -> str:
    first_item = self.items.select_related('product').first()
    if first_item and first_item.product:
        return first_item.product.name
    if self.product:
        return self.product.name
    return "ثبت اولیه بدون کالا / ناقص"
```

### C. Elimination of Double-Counting
- Stock calculations query exclusively `StockMovement` (`direction=IN`).
- Receipt detail templates check `{% if receipt.items.exists %}` to iterate over `receipt.items.all`. If no child items exist (un-migrated or legacy record), it renders the single parent row. Under no circumstances are parent weights and child rows summed together.

---

## 3. Safe Legacy Receipt Data Migration (0004 & 0005)

### A. Schema Migration (`0004_goods_receipt_multi_item.py`)
1. Create model `GoodsReceiptItem`:
   - `id` (AutoField)
   - `goods_receipt` (`ForeignKey(GoodsReceipt, on_delete=CASCADE, related_name='items')`)
   - `product` (`ForeignKey(Product, on_delete=PROTECT, related_name='receipt_items')`)
   - `gross_weight_kg` (`DecimalField(max_digits=10, decimal_places=3)`)
   - `total_tare_weight_kg` (`DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'))`)
   - `net_weight_kg` (`DecimalField(max_digits=10, decimal_places=3)`)
   - `package_count` (`PositiveIntegerField(null=True, blank=True)`)
   - `condition_notes` (`CharField(max_length=256, blank=True)`)
   - `remarks` (`CharField(max_length=256, blank=True)`)
2. Alter `GoodsReceipt`:
   - Add `total_gross_weight_kg` (`DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)`)
   - Add `total_net_weight_kg` (`DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)`)
   - Alter `product`, `gross_weight_kg`, `total_tare_weight_kg`, `net_weight_kg` to `null=True, blank=True`.
3. Alter `WeighingTareRow`:
   - Add `goods_receipt_item` (`ForeignKey(GoodsReceiptItem, on_delete=CASCADE, null=True, blank=True, related_name='tare_rows')`)
4. Alter `InvoiceItem`:
   - Add `source_receipt_item` (`ForeignKey(GoodsReceiptItem, on_delete=SET_NULL, null=True, blank=True, related_name='invoice_items')`)

### B. Safe Data Migration (`0005_backfill_goods_receipt_items.py`)
1. **Clear Distinction: Incomplete vs. Valid Zero-Weight Records**:
   - **Incomplete Historical Receipts**: Records where `product_id is None` or `gross_weight_kg is None` or `net_weight_kg is None`. These are draft or aborted records.
     - **Action**: Skipped by the backfill. They are **never deleted**. No fictitious `Product`, weight, or movement is created.
     - **Visibility & Safety**: They remain fully visible in list and detail views (`receipt.primary_product_name` returns `"ثبت اولیه بدون کالا / ناقص"`). Invoicing services and reporting safely bypass incomplete records without throwing errors.
   - **Valid Historical Records (including zero-weight test/calibration records)**: Records where `product_id is not None` and weights are explicitly specified (even if `0.000 kg`).
     - **Action**: Backfilled into 1 `GoodsReceiptItem`:
       - `goods_receipt = receipt`
       - `product = receipt.product`
       - `gross_weight_kg = receipt.gross_weight_kg`
       - `total_tare_weight_kg = receipt.total_tare_weight_kg or Decimal('0.000')`
       - `net_weight_kg = receipt.net_weight_kg`
       - `package_count = receipt.package_count`
       - `condition_notes = receipt.condition_notes or ""`
       - `remarks = receipt.remarks or ""`
     - Link tare rows: Update all `WeighingTareRow.objects.filter(goods_receipt=receipt)` to point `goods_receipt_item = item`.
     - Update parent totals: `total_gross_weight_kg = receipt.gross_weight_kg`, `total_net_weight_kg = receipt.net_weight_kg`.
2. **Zero Stock Movement Invariant**:
   - This migration creates **zero** `StockMovement` records. Existing movements created when historical receipts were originally finalized remain untouched.
3. **Reversibility & Rollback Limitations**:
   - The reverse migration disassociates `WeighingTareRow.goods_receipt_item = None` and removes `GoodsReceiptItem` records that were created for legacy single-item receipts.
   - **Documented Rollback Limitation**: If new multi-item receipts are created in production *after* applying migration 0005, rolling back migration 0005 cannot collapse multi-item receipts into the legacy single-item `GoodsReceipt.product` field without data loss. Reversing is intended only for emergency staging rollback before multi-item operational data is committed.

---

## 4. Atomic Multi-Item Finalization & Robust Idempotency Handling

### A. Atomic Finalization (`sales/services.py`)
Both `finalize_goods_receipt` and `finalize_goods_issue` execute within a single `@transaction.atomic` block:
1. Validate all lines upfront:
   - Verify every line has a valid, active `Product`.
   - Verify $gross\_weight > 0$ and $gross\_weight \ge total\_tare\_weight$ for every line ($net\_weight \ge 0$).
   - For Goods Issue: Sum requested net weights across duplicate products and verify against available `StockMovement` balance.
2. If any validation fails (e.g., insufficient stock on line 3 of 4, or negative net weight on line 2):
   - Raise domain exception (`InsufficientStockError` or `InvalidTareWeightError`).
   - The database transaction rolls back completely. Zero parent documents, zero child items, zero tare rows, and zero `StockMovement` entries are persisted.
3. On success:
   - Create parent document (`GoodsReceipt` / `GoodsIssue`) with calculated aggregate totals.
   - Create child items (`GoodsReceiptItem` / `GoodsIssueItem`).
   - Create child `WeighingTareRow` records linked directly to each item.
   - Post exactly one `StockMovement` per line item (`IN` for receipts, `OUT` for issues) with `reference_document_number = doc.document_number`.

### B. Robust Idempotency Error Handling (No Reliance on Error String Parsing)
To ensure reliable idempotency across all database backends (SQLite, PostgreSQL, Cloud SQL) without fragile exception string parsing:
```python
def finalize_goods_receipt(..., idempotency_key: str | None = None) -> GoodsReceipt:
    if idempotency_key:
        existing = GoodsReceipt.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    try:
        with transaction.atomic():
            # Create receipt, items, tare rows, and stock movements
            receipt = GoodsReceipt.objects.create(
                ...,
                idempotency_key=idempotency_key,
            )
            ...
            return receipt
    except IntegrityError:
        # Do NOT parse exception text. Check directly whether a committed document
        # with this EXACT idempotency_key exists in the database.
        if idempotency_key:
            committed_doc = GoodsReceipt.objects.filter(idempotency_key=idempotency_key).first()
            if committed_doc:
                # Successfully committed by a concurrent racing transaction
                return committed_doc
        # If no committed document with this key exists, it is an unrelated integrity violation
        # (e.g. check constraint, invalid foreign key, or failed transaction) -> re-raise!
        raise
```
This guarantees:
1. No false positive duplicate returns for failed or rolled-back transactions.
2. Re-raising of all unrelated foreign key, check constraint, or null-constraint errors.

---

## 5. Independent Product IDs per Line & Product Selection Correctness

### A. Problem Resolution & Independent Line Isolation
- **The Problem**: Using a single shared `selected_product_id` across dynamic rows causes cross-contamination where searching or filtering one line mutates another line.
- **The Architecture**: Every line in Goods Receipt, Goods Issue, and Invoice maintains its own **strictly independent** product ID state and form submission input.

### B. Goods Receipt & Goods Issue Active Line Isolation
1. **Active Line Weighing Section**:
   - Contains its own hidden field `<input type="hidden" id="active-line-product-id" name="active_product_id">`.
   - Contains its own `#selected-product-card`:
     - Displays Selected Cut Name (bold typography), SKU/Code badge (`[کد: B-101]`), Category badge (`(گوشت گوساله)`), Current Stock (for Issues), and `«تغییر / حذف کالا»` button.
   - Live Search Input (`#product-search`) and Category Filter Pills (`.cat-btn`) filter only the results dropdown list without deselecting or altering the active card.
2. **Committed Items Table & Dynamic Formset Submission**:
   - When the operator clicks `➕ افزودن کالا به رسید / حواله (Add Product)`:
     - The current product ID, weights, package count, and tare rows are committed to an independent row in the table.
     - Each committed row renders its own isolated hidden inputs:
       - `<input type="hidden" name="items[0][product_id]" value="...">`
       - `<input type="hidden" name="items[0][gross_weight_kg]" value="...">`
       - `<input type="hidden" name="items[0][tare_weights]" value="...">`
     - The active weighing section, tare rows, and `#active-line-product-id` are reset to empty for the next line.
   - Editing or removing row 2 does not affect row 1 or row 3.

### C. Invoice Form Independent Rows
1. In `invoice_form.html`:
   - Each dynamic invoice row `$index` contains its own isolated hidden field:
     `<input type="hidden" name="items[${index}][product_id]" class="line-product-id">`
   - Each row has its own dedicated search/select trigger, displaying its own selected-product card.
   - Adding, filtering, editing, or deleting line $i$ operates strictly on index $i$ and never changes line $j$.
2. **Server-Side Validation**:
   - Server iterates over every line and validates each individual `item['product_id']` against active `Product` models.
   - Any missing or invalid product ID returns an explicit Persian error indicating the exact line (`«کالای ردیف ۲ انتخاب نشده است یا نامعتبر می‌باشد.»`).

---

## 6. Money, Display Conventions & Pricing Integrity

1. **Storage Invariant**:
   - All monetary values are strictly stored and computed as **whole Rial integers** (`PositiveBigIntegerField`).
   - Floats and floating-point math are strictly prohibited for financial fields.
2. **Display Conversion (Rial to Toman)**:
   - Toman display is presentation-only: `rial_amount // 10`.
   - **Remainder Handling**: If a Rial amount is not evenly divisible by 10 (`rial % 10 != 0`):
     - It is displayed with the exact remainder: e.g., `55 Rials` $\rightarrow$ `۵.۵ تومان (۵۵ ریال)`.
3. **Purchase Price Confirmation (Zero Silent Fallback)**:
   - Goods receipts record incoming weight, not financial purchase prices.
   - When generating a purchase invoice from receipts (`invoice_from_source_view`), the system will **never** silently insert current catalog prices as purchase prices.
   - The user must explicitly enter or confirm the agreed unit purchase price in Rials per line before finalization.
4. **Zero Invoicing Stock Movements**:
   - Creating invoices (sales or purchase) generates only commercial accounting records (`Invoice` and `InvoiceItem`). It creates **zero** `StockMovement` entries.

---

## 7. Acceptance Criteria & Exact Test Coverage

### A. Specific Test Suite (`sales/tests.py`)
1. `ProductSelectionFeedbackTestCase`:
   - `test_selected_product_card_sync_with_hidden_field`: selecting updates card and hidden input.
   - `test_filter_and_search_does_not_clear_selected_product`: changing search query keeps selection intact.
   - `test_server_side_validation_rejects_empty_or_invalid_product`: missing product raises validation error.
   - `test_independent_product_ids_across_multiple_lines`: verifies dynamic rows maintain independent product IDs.
2. `MultiItemGoodsReceiptTestCase`:
   - `test_multi_item_goods_receipt_creation_and_stock_movements`: creates 1 receipt with 2 cuts, verifies 2 `GoodsReceiptItem` records and 2 `StockMovement` (IN) records.
   - `test_multi_item_receipt_header_totals_match_line_sums`: header gross/net equals item sums.
   - `test_multi_item_receipt_tare_weight_authoritative_sum`: aggregate tare strictly equals sum of child `total_tare_weight_kg`.
   - `test_multi_item_receipt_gross_tare_net_consistency`: verifies $aggregate\_gross - aggregate\_tare == aggregate\_net$.
   - `test_multi_item_receipt_atomic_rollback_on_invalid_tare`: tare $\ge$ gross on 1 item rolls back entire receipt.
   - `test_receipt_idempotency_prevents_duplicate_stock_and_handles_race`: duplicate key returns existing receipt; simulated concurrent race recovers safely via DB check rather than string parsing.
3. `GoodsReceiptMigrationTestCase`:
   - `test_migration_0005_backfills_items_without_creating_stock_movements`: verifies initial movement count equals post-migration movement count.
   - `test_migration_0005_skips_incomplete_historical_records_safely`: records with `product is None` are skipped without creating fake items.
   - `test_migration_0005_backfills_valid_zero_weight_records`: records with valid product and explicit 0 weight are preserved as items.
   - `test_legacy_and_incomplete_receipt_detail_view_renders_correctly`: historical single-item and incomplete receipts display cleanly without throwing exceptions.
4. `MultiItemGoodsIssueWorkflowTestCase`:
   - `test_goods_issue_add_product_resets_scale_inputs`: verifies fresh reading isolation.
   - `test_goods_issue_aggregate_demand_across_multiple_lines`: 2 lines of same product validated against combined balance.
5. `InvoiceProductSearchAndCalculationTestCase`:
   - `test_invoice_product_search_and_category_filter`: verifies matching cuts by name/code and category.
   - `test_invoice_independent_lines_calculation`: multiple lines calculate line totals and grand total accurately in whole Rials and Tomans.
   - `test_invoice_from_source_traceability`: verifies `source_receipt_item` and `source_issue_item` links without duplicate stock movements.

### B. Summary of Files to Modify / Create
- **Models & Migrations**:
  - `sales/models.py`: add `GoodsReceiptItem`, tare row FK, header aggregates, and compatibility properties.
  - `sales/migrations/0004_goods_receipt_multi_item.py` (Schema migration).
  - `sales/migrations/0005_backfill_goods_receipt_items.py` (Data migration).
- **Services & Views**:
  - `sales/services.py`: multi-item `finalize_goods_receipt`, atomic validation, DB-verified idempotency handler, `generate_invoice_from_source_documents` line updates.
  - `sales/views.py`: `goods_receipt_create_view`, `goods_issue_create_view`, `invoice_create_view`, and detail views.
- **Templates**:
  - `templates/sales/receipt_form.html`: multi-item workflow, selected-product card, active scale isolation, per-row product IDs.
  - `templates/sales/receipt_detail.html`: multi-item table + legacy fallback.
  - `templates/sales/issue_form.html`: selected-product card, prominent Add Product button, field reset, per-row product IDs.
  - `templates/sales/invoice_form.html`: independent searchable product selector per row with category filter pills and dynamic line addition.
- **Tests**:
  - `sales/tests.py`: new test classes covering all acceptance criteria.

---

## 8. Remaining Risks & Mitigation Strategies

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| **Concurrent Idempotency Submissions** | Two simultaneous requests passing initial query check could cause duplicate creation. | Unique constraint on `idempotency_key` triggers rollback. Catch block checks whether a committed document with this key exists in the DB, returning it safely or re-raising if uncommitted/unrelated. |
| **Incomplete Historical Receipts** | Legacy records with missing product or 0 kg might fail validation or corrupt reports. | Migration 0005 explicitly skips incomplete records without fabricating products or weights, and views gracefully handle un-migrated records. |
| **Tare Calculation Inconsistency** | Aggregate tare drifting from child tare totals. | Property on `GoodsReceipt` aggregates tare strictly from `sum(items.total_tare_weight_kg)` when items exist, covered by explicit gross-tare-net consistency tests. |
| **Dynamic Form Line Contamination** | Product selection in one row overwriting another row. | Formset uses indexed field names (`items[0][product_id]`, `items[1][product_id]`) and per-row DOM scopes. |
| **Silent Price Overwrite on Purchase Invoices** | Using catalog price instead of negotiated supplier price. | Service strictly raises `BusinessLogicError` if purchase price is omitted; catalog price is shown only as unconfirmed visual reference. |

---

## 9. Verification & Phase Approval Protocol

- After user approval, all migrations, models, services, templates, and tests will be implemented.
- Verification commands will be executed:
  - `python manage.py check`
  - `python manage.py test`
- Actual console output, passing test count, and runtime will be reported. No verification will be claimed without actual command execution.
- No application code, database migrations, or test edits will take place until the user explicitly responds with approval to proceed.
