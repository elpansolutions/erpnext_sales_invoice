import frappe
from frappe import _

@frappe.whitelist()
def get_pricing_details(customer, item_code, batch_no=None, company=None):
    """
    Returns:
    1. history: Last 5 sales prices for customer and item_code
    2. purchase_rate: Purchase price for item/batch
    3. mrp: MRP for item/batch
    4. minimum_selling_price: Minimum selling price for item
    5. item_meta: Item details
    """
    if not customer or not item_code:
        return {}

    # 1. Fetch Item Master info
    item_doc = frappe.get_cached_value("Item", item_code, 
        ["item_name", "stock_uom", "standard_rate", "valuation_rate", "last_purchase_rate", "has_batch_no"], 
        as_dict=True
    ) or {}

    min_selling_price = 0.0
    if frappe.db.has_column("Item", "minimum_selling_price"):
        min_selling_price = frappe.db.get_value("Item", item_code, "minimum_selling_price") or 0.0

    # 2. Fetch Last 5 Sales Invoices for this customer & item
    history_query = """
        SELECT 
            si.name AS voucher_no,
            si.posting_date,
            sii.batch_no,
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

    # 3. Batch Details (MRP, Expiry, etc.)
    batch_mrp = 0.0
    batch_expiry = None
    if batch_no:
        batch_fields = ["name", "expiry_date"]
        if frappe.db.has_column("Batch", "custom_custom_mrp"):
            batch_fields.append("custom_custom_mrp")
        
        batch_data = frappe.db.get_value("Batch", batch_no, batch_fields, as_dict=True)
        if batch_data:
            batch_mrp = batch_data.get("custom_custom_mrp") or 0.0
            batch_expiry = batch_data.get("expiry_date")

    # 4. Purchase Price for Item & Batch
    purchase_rate = 0.0
    purchase_invoice_mrp = 0.0
    purchase_voucher = None

    if batch_no:
        # Search purchase invoice item by item_code and batch_no
        pi_match = frappe.db.sql("""
            SELECT pii.rate, pii.custom_mrp, pi.name AS voucher_no, pi.posting_date
            FROM `tabPurchase Invoice Item` pii
            INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
            WHERE pi.docstatus = 1
              AND pii.item_code = %(item_code)s
              AND (pii.batch_no = %(batch_no)s OR pii.custom_batch_number = %(batch_no)s)
            ORDER BY pi.posting_date DESC, pi.creation DESC
            LIMIT 1
        """, {"item_code": item_code, "batch_no": batch_no}, as_dict=True)

        if pi_match:
            purchase_rate = pi_match[0].rate or 0.0
            purchase_invoice_mrp = pi_match[0].custom_mrp or 0.0
            purchase_voucher = pi_match[0].voucher_no

    # If purchase rate not found for batch, fallback to latest purchase invoice for the item
    if not purchase_rate:
        latest_pi = frappe.db.sql("""
            SELECT pii.rate, pii.custom_mrp, pi.name AS voucher_no, pi.posting_date
            FROM `tabPurchase Invoice Item` pii
            INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
            WHERE pi.docstatus = 1
              AND pii.item_code = %(item_code)s
            ORDER BY pi.posting_date DESC, pi.creation DESC
            LIMIT 1
        """, {"item_code": item_code}, as_dict=True)

        if latest_pi:
            purchase_rate = latest_pi[0].rate or 0.0
            if not purchase_invoice_mrp:
                purchase_invoice_mrp = latest_pi[0].custom_mrp or 0.0
            if not purchase_voucher:
                purchase_voucher = latest_pi[0].voucher_no

    # If still not found, fallback to Item Master's last purchase rate or valuation rate
    if not purchase_rate:
        purchase_rate = item_doc.get("last_purchase_rate") or item_doc.get("valuation_rate") or 0.0

    # Final MRP resolution: Batch.custom_custom_mrp > Purchase Invoice Item.custom_mrp > 0
    final_mrp = batch_mrp or purchase_invoice_mrp or 0.0

    return {
        "item_code": item_code,
        "item_name": item_doc.get("item_name") or item_code,
        "stock_uom": item_doc.get("stock_uom") or "Nos",
        "has_batch_no": item_doc.get("has_batch_no") or 0,
        "batch_no": batch_no,
        "batch_expiry": str(batch_expiry) if batch_expiry else "",
        "mrp": float(final_mrp),
        "purchase_rate": float(purchase_rate),
        "purchase_voucher": purchase_voucher,
        "minimum_selling_price": float(min_selling_price),
        "standard_rate": float(item_doc.get("standard_rate") or 0.0),
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

