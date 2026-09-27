import frappe
from frappe import _
from frappe.utils import getdate, format_date, flt

@frappe.whitelist()
def get_pricing_details(customer, item_code, batch_no=None, company=None):
    """
    Returns:
    1. history: Last 5 sales prices for customer and item_code
    2. purchase_rate: Purchase price for item/batch
    3. mrp: MRP for item/batch
    4. minimum_selling_price: Minimum selling price for item
    5. batches: List of all active batches with stock, MRP, and clean batch IDs
    6. item_meta: Item details
    """
    if not customer or not item_code:
        return {}

    # 1. Fetch Item Master info
    item_doc = frappe.get_cached_value("Item", item_code, 
        ["item_name", "stock_uom", "standard_rate", "valuation_rate", "last_purchase_rate", "has_batch_no", "has_serial_no"], 
        as_dict=True
    ) or {}

    min_selling_price = 0.0
    if frappe.db.has_column("Item", "minimum_selling_price"):
        min_selling_price = flt(frappe.db.get_value("Item", item_code, "minimum_selling_price")) or 0.0

    # 2. Fetch Last 5 Sales Invoices for this customer & item
    history_query = """
        SELECT 
            si.name AS voucher_no,
            si.posting_date,
            sii.batch_no,
            sii.custom_batch_id_all,
            sii.qty,
            sii.uom,
            sii.rate,
            sii.base_rate,
            sii.custom_mrp
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.customer = %(customer)s
          AND sii.item_code = %(item_code)s
        ORDER BY si.posting_date DESC, si.creation DESC
        LIMIT 5
    """
    history = frappe.db.sql(history_query, {"customer": customer, "item_code": item_code}, as_dict=True)
    for h in history:
        if h.get("batch_no") and not h.get("custom_batch_id_all"):
            h["custom_batch_id_all"] = frappe.db.get_value("Batch", h["batch_no"], "custom_batch_id_all") or h["batch_no"]

    # 3. Fetch All Active Batches for this Item
    batches = []
    has_batch_tracking = bool(item_doc.get("has_batch_no"))
    
    batch_records = frappe.db.sql("""
        SELECT 
            b.name,
            b.batch_id,
            b.custom_batch_id_all,
            b.expiry_date,
            b.batch_qty,
            b.disabled
        FROM `tabBatch` b
        WHERE b.item = %(item_code)s AND b.disabled = 0
        ORDER BY b.creation DESC
    """, {"item_code": item_code}, as_dict=True)

    today_date = getdate()
    batch_mrp_col = "custom_custom_mrp" if frappe.db.has_column("Batch", "custom_custom_mrp") else ("custom_mrp" if frappe.db.has_column("Batch", "custom_mrp") else None)
    batch_min_col = "custom_minimum_selling_price" if frappe.db.has_column("Batch", "custom_minimum_selling_price") else ("minimum_selling_price" if frappe.db.has_column("Batch", "minimum_selling_price") else None)

    item_last_purchase_rate = flt(item_doc.get("last_purchase_rate") or item_doc.get("valuation_rate") or 0.0)

    for b in batch_records:
        clean_batch_id = b.get("custom_batch_id_all") or b.batch_id or b.name
        expiry_date = b.expiry_date
        expiry_str = str(expiry_date) if expiry_date else ""
        expiry_formatted = format_date(expiry_date) if expiry_date else ""

        # Batch MRP
        mrp = 0.0
        if batch_mrp_col:
            mrp = flt(frappe.db.get_value("Batch", b.name, batch_mrp_col)) or 0.0

        # Batch Min Selling Price
        b_min_price = min_selling_price
        if batch_min_col:
            val = flt(frappe.db.get_value("Batch", b.name, batch_min_col))
            if val > 0:
                b_min_price = val

        # Search last Purchase Invoice Item for this specific batch
        purchase_rate = 0.0
        purchase_voucher = None
        pi_match = frappe.db.sql("""
            SELECT pii.rate, pii.custom_mrp, pi.name AS voucher_no, pi.posting_date
            FROM `tabPurchase Invoice Item` pii
            INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
            WHERE pi.docstatus = 1
              AND pii.item_code = %(item_code)s
              AND (pii.batch_no = %(batch_no)s OR pii.custom_batch_number = %(clean_batch_id)s OR pii.custom_batch_id_all = %(clean_batch_id)s)
            ORDER BY pi.posting_date DESC, pi.creation DESC
            LIMIT 1
        """, {"item_code": item_code, "batch_no": b.name, "clean_batch_id": clean_batch_id}, as_dict=True)

        if pi_match:
            purchase_rate = flt(pi_match[0].rate)
            purchase_voucher = pi_match[0].voucher_no
            if mrp <= 0 and pi_match[0].get("custom_mrp"):
                mrp = flt(pi_match[0].custom_mrp)

        if purchase_rate <= 0:
            purchase_rate = item_last_purchase_rate

        is_expired = bool(expiry_date and getdate(expiry_date) < today_date)

        batches.append({
            "name": b.name,
            "batch_id": clean_batch_id,
            "custom_batch_id_all": clean_batch_id,
            "expiry_date": expiry_str,
            "expiry_formatted": expiry_formatted,
            "is_expired": is_expired,
            "mrp": mrp,
            "minimum_selling_price": b_min_price,
            "batch_qty": flt(b.batch_qty),
            "purchase_rate": purchase_rate,
            "purchase_voucher": purchase_voucher
        })

    # Select active batch details
    selected_batch = None
    if batch_no:
        selected_batch = next((b for b in batches if b["name"] == batch_no or b["batch_id"] == batch_no or b["custom_batch_id_all"] == batch_no), None)
    
    if not selected_batch and batches:
        # Default to first available batch
        selected_batch = next((b for b in batches if not b["is_expired"] and b["batch_qty"] > 0), batches[0])

    final_batch_no = selected_batch["name"] if selected_batch else (batch_no or "")
    final_batch_id = selected_batch["custom_batch_id_all"] if selected_batch else (batch_no or "")
    final_mrp = selected_batch["mrp"] if selected_batch else 0.0
    final_purchase_rate = selected_batch["purchase_rate"] if selected_batch else item_last_purchase_rate
    final_purchase_voucher = selected_batch["purchase_voucher"] if selected_batch else None
    final_min_price = selected_batch["minimum_selling_price"] if selected_batch else min_selling_price
    final_expiry = selected_batch["expiry_formatted"] if selected_batch else ""

    # 4. Fetch Available Serial Numbers for this Item
    has_serial_tracking = bool(item_doc.get("has_serial_no"))
    serial_records = frappe.db.sql("""
        SELECT 
            name,
            serial_no,
            batch_no,
            warehouse,
            status
        FROM `tabSerial No`
        WHERE item_code = %(item_code)s
          AND (status NOT IN ('Delivered', 'Consumed', 'Expired', 'Inactive') OR status IS NULL OR status = '')
        ORDER BY creation ASC, name ASC
    """, {"item_code": item_code}, as_dict=True)

    serial_numbers = [s["name"] for s in serial_records]
    if serial_numbers:
        has_serial_tracking = True

    return {
        "item_code": item_code,
        "item_name": item_doc.get("item_name") or item_code,
        "stock_uom": item_doc.get("stock_uom") or "Nos",
        "has_batch_no": has_batch_tracking or (len(batches) > 0),
        "has_serial_no": has_serial_tracking,
        "serial_numbers": serial_numbers,
        "serial_records": serial_records,
        "batch_no": final_batch_no,
        "batch_id": final_batch_id,
        "custom_batch_id_all": final_batch_id,
        "batch_expiry": final_expiry,
        "mrp": float(final_mrp),
        "purchase_rate": float(final_purchase_rate),
        "purchase_voucher": final_purchase_voucher,
        "minimum_selling_price": float(final_min_price),
        "standard_rate": float(item_doc.get("standard_rate") or 0.0),
        "batches": batches,
        "history": history
    }


def configure_ewaybill_field():
    """Ensure Sales Invoice ewaybill field is editable and visible for manual entry."""
    try:
        if frappe.db.exists("Custom Field", "Sales Invoice-ewaybill"):
            cf = frappe.get_doc("Custom Field", "Sales Invoice-ewaybill")
            cf.read_only = 0
            cf.depends_on = ""
            cf.allow_on_submit = 1
            cf.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.clear_cache(doctype="Sales Invoice")
    except Exception as e:
        frappe.log_error(title="Failed to configure ewaybill custom field", message=str(e))

