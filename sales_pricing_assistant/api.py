import frappe
from frappe import _
from frappe.utils import getdate, format_date, flt


def fix_serial_no_status_on_submit(doc, method=None):
    """
    On Sales Invoice / Delivery Note submit: mark serial numbers referenced
    in the items as 'Delivered' in tabSerial No if they're still 'Active'.
    This corrects cases where ERPNext's bundle-based stock update skips the
    tabSerial No.status field update.
    """
    if doc.is_return:
        return

    serials_to_deliver = set()
    for item in (doc.items or []):
        sn = (item.serial_no or '').strip()
        if sn:
            serials_to_deliver.add(sn)

    if not serials_to_deliver:
        return

    for sn in serials_to_deliver:
        try:
            sn_doc = frappe.db.get_value("Serial No", sn, ["name", "status"], as_dict=True)
            if sn_doc and sn_doc.get("status") not in ("Delivered", "Consumed", "Expired"):
                frappe.db.set_value("Serial No", sn, "status", "Delivered")
        except Exception:
            pass


def fix_serial_no_status_on_cancel(doc, method=None):
    """
    On Sales Invoice / Delivery Note cancel: restore serial numbers back to 'Active'
    so they can be resold.
    """
    for item in (doc.items or []):
        sn = (item.serial_no or '').strip()
        if sn:
            try:
                sn_doc = frappe.db.get_value("Serial No", sn, ["name", "status"], as_dict=True)
                if sn_doc and sn_doc.get("status") == "Delivered":
                    frappe.db.set_value("Serial No", sn, "status", "Active")
            except Exception:
                pass

def get_saved_sales_invoice_qty(item_code, batch_no=None, warehouse=None, exclude_invoice=None, exclude_doctype=None):
    """
    Returns total quantity of an item/batch reserved in saved (draft, docstatus=0)
    Sales Invoices and Delivery Notes (excluding returns and optionally excluding a given document).
    Includes both billed qty and custom_free_qty.
    """
    if not item_code:
        return 0.0

    total_reserved = 0.0

    # 1. Draft Sales Invoices
    si_conditions = [
        "si.docstatus = 0",
        "si.is_return = 0",
        "sii.item_code = %(item_code)s"
    ]
    si_params = {"item_code": item_code}

    if exclude_invoice and (not exclude_doctype or exclude_doctype == "Sales Invoice"):
        si_conditions.append("si.name != %(exclude_invoice)s")
        si_params["exclude_invoice"] = exclude_invoice

    if batch_no:
        si_conditions.append("(sii.batch_no = %(batch_no)s OR sii.custom_batch_id_all = %(batch_no)s)")
        si_params["batch_no"] = batch_no

    if warehouse:
        si_conditions.append("sii.warehouse = %(warehouse)s")
        si_params["warehouse"] = warehouse

    si_query = f"""
        SELECT 
            SUM(
                (COALESCE(sii.qty, 0) + COALESCE(sii.custom_free_qty, 0)) 
                * COALESCE(sii.conversion_factor, 1.0)
            ) AS reserved_qty
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
        WHERE {" AND ".join(si_conditions)}
    """
    res_si = frappe.db.sql(si_query, si_params, as_dict=True)
    if res_si and res_si[0].reserved_qty:
        total_reserved += flt(res_si[0].reserved_qty)

    # 2. Draft Delivery Notes
    dn_conditions = [
        "dn.docstatus = 0",
        "dn.is_return = 0",
        "dni.item_code = %(item_code)s"
    ]
    dn_params = {"item_code": item_code}

    if exclude_invoice and (not exclude_doctype or exclude_doctype == "Delivery Note"):
        dn_conditions.append("dn.name != %(exclude_invoice)s")
        dn_params["exclude_invoice"] = exclude_invoice

    if batch_no:
        dn_conditions.append("(dni.batch_no = %(batch_no)s OR dni.custom_batch_id_all = %(batch_no)s)")
        dn_params["batch_no"] = batch_no

    if warehouse:
        dn_conditions.append("dni.warehouse = %(warehouse)s")
        dn_params["warehouse"] = warehouse

    dn_query = f"""
        SELECT 
            SUM(
                (COALESCE(dni.qty, 0) + COALESCE(dni.custom_free_qty, 0)) 
                * COALESCE(dni.conversion_factor, 1.0)
            ) AS reserved_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
        WHERE {" AND ".join(dn_conditions)}
    """
    res_dn = frappe.db.sql(dn_query, dn_params, as_dict=True)
    if res_dn and res_dn[0].reserved_qty:
        total_reserved += flt(res_dn[0].reserved_qty)

    return total_reserved


def get_purchase_and_landed_cost(item_code, batch_name=None, clean_batch_id=None, item_last_purchase_rate=0.0, item_valuation_rate=0.0):
    """
    Calculates:
    1. Latest Purchase Price (Rate) and voucher no for the batch/item.
    2. Weighted Average Landed Price (Net price after discount) across multiple purchases of this specific batch (or item if not batched).
    3. Purchase count, discount percentage, and helpful subtitle for UI display.
    """
    conditions = ["pii.item_code = %(item_code)s"]
    values = {"item_code": item_code}

    if batch_name or clean_batch_id:
        conditions.append("(pii.batch_no = %(batch_name)s OR pii.custom_batch_number = %(clean_id)s OR pii.custom_batch_id_all = %(clean_id)s)")
        values["batch_name"] = batch_name or ""
        values["clean_id"] = clean_batch_id or batch_name or ""

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            pii.name, pii.parent AS voucher_no, pi.posting_date, pii.qty, pii.rate,
            pii.net_rate, pii.net_amount, pii.amount, pii.custom_item_net_amount,
            pii.custom_item_discount_percentage, pii.custom_item_discount_amount,
            pii.discount_percentage, pii.discount_amount, pii.custom_mrp, pi.docstatus
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
        WHERE pi.docstatus = 1 AND {where_clause}
        ORDER BY pi.posting_date DESC, pi.creation DESC
    """
    pi_rows = frappe.db.sql(query, values, as_dict=True)
    if not pi_rows:
        query_draft = query.replace("pi.docstatus = 1", "pi.docstatus IN (0, 1)")
        pi_rows = frappe.db.sql(query_draft, values, as_dict=True)

    latest_purchase_rate = 0.0
    latest_voucher = None
    latest_mrp = 0.0
    latest_disc_pct = 0.0
    total_net_amount = 0.0
    total_qty = 0.0
    purchase_count = len(pi_rows)

    for idx, pii in enumerate(pi_rows):
        row_qty = flt(pii.get("qty") or 0.0)
        row_rate = flt(pii.get("rate") or 0.0)
        row_gross = flt(pii.get("amount") or (row_rate * row_qty))

        row_net = 0.0
        if flt(pii.get("custom_item_net_amount") or 0.0) > 0:
            row_net = flt(pii.get("custom_item_net_amount"))
        elif flt(pii.get("net_amount") or 0.0) > 0:
            row_net = flt(pii.get("net_amount"))
        elif flt(pii.get("net_rate") or 0.0) > 0 and row_qty > 0:
            row_net = flt(pii.get("net_rate")) * row_qty
        else:
            disc = 0.0
            if flt(pii.get("custom_item_discount_amount") or 0.0) > 0:
                disc += flt(pii.get("custom_item_discount_amount"))
            if flt(pii.get("custom_item_discount_percentage") or 0.0) > 0:
                disc += row_gross * (flt(pii.get("custom_item_discount_percentage")) / 100.0)
            if flt(pii.get("discount_amount") or 0.0) > 0:
                disc += flt(pii.get("discount_amount"))
            if flt(pii.get("discount_percentage") or 0.0) > 0:
                disc += row_gross * (flt(pii.get("discount_percentage")) / 100.0)
            row_net = max(0.0, row_gross - disc)

        if row_qty > 0 and row_net > 0:
            total_net_amount += row_net
            total_qty += row_qty

        if idx == 0:
            latest_purchase_rate = row_rate
            latest_voucher = pii.get("voucher_no")
            if pii.get("custom_mrp"):
                latest_mrp = flt(pii.get("custom_mrp"))
            if flt(pii.get("custom_item_discount_percentage") or 0.0) > 0:
                latest_disc_pct = flt(pii.get("custom_item_discount_percentage"))
            elif flt(pii.get("discount_percentage") or 0.0) > 0:
                latest_disc_pct = flt(pii.get("discount_percentage"))
            elif row_gross > 0 and row_net < row_gross:
                latest_disc_pct = round(((row_gross - row_net) / row_gross) * 100.0, 1)

    if total_qty > 0:
        weighted_avg_landed = round(total_net_amount / total_qty, 2)
    else:
        weighted_avg_landed = 0.0

    if latest_purchase_rate <= 0:
        latest_purchase_rate = item_last_purchase_rate or item_valuation_rate

    if weighted_avg_landed <= 0:
        weighted_avg_landed = item_valuation_rate or latest_purchase_rate

    subtitle = ""
    if purchase_count > 1:
        subtitle = f"{purchase_count} purchases (Weighted Avg)"
    elif purchase_count == 1:
        if latest_disc_pct > 0:
            subtitle = f"-{latest_disc_pct:g}% discount"
        else:
            subtitle = "Net landed cost"
    elif item_valuation_rate > 0:
        subtitle = "Item Valuation Rate"

    return {
        "purchase_rate": latest_purchase_rate,
        "purchase_voucher": latest_voucher,
        "landed_price": weighted_avg_landed,
        "purchase_count": purchase_count,
        "latest_discount_pct": latest_disc_pct,
        "landed_subtitle": subtitle,
        "custom_mrp": latest_mrp
    }


@frappe.whitelist()
def get_pricing_details(customer, item_code, batch_no=None, company=None, warehouse=None, exclude_invoice=None):
    """
    Returns:
    1. history: Last 5 sales prices for customer and item_code
    2. purchase_rate: Purchase price for item/batch
    3. landed_price: Weighted average landed price across purchases of batch/item
    4. mrp: MRP for item/batch
    5. minimum_selling_price: Minimum selling price for item
    6. batches: List of all active batches with stock, MRP, clean batch IDs, and landed prices
    7. item_meta: Item details
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
    batch_mrp_col = "custom_custom_mrp" if frappe.db.has_column("Batch", "custom_custom_mrp") else ("custom_mrp" if frappe.db.has_column("Batch", "custom_mrp") else None)
    history = frappe.db.sql(history_query, {"customer": customer, "item_code": item_code}, as_dict=True)
    for h in history:
        if h.get("batch_no") and not h.get("custom_batch_id_all"):
            h["custom_batch_id_all"] = frappe.db.get_value("Batch", h["batch_no"], "custom_batch_id_all") or h["batch_no"]
        
        # Determine MRP
        h_mrp = flt(h.get("custom_mrp") or 0.0)
        if h_mrp <= 0 and h.get("batch_no") and batch_mrp_col:
            h_mrp = flt(frappe.db.get_value("Batch", h["batch_no"], batch_mrp_col) or 0.0)
        if h_mrp <= 0 and item_doc.get("custom_mrp"):
            h_mrp = flt(item_doc.get("custom_mrp") or 0.0)
        h["mrp"] = h_mrp
        h["custom_mrp"] = h_mrp

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
    item_valuation_rate = flt(item_doc.get("valuation_rate") or 0.0)

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

        # Calculate Purchase Price & Weighted Average Landed Cost for this batch
        cost_info = get_purchase_and_landed_cost(
            item_code=item_code,
            batch_name=b.name,
            clean_batch_id=clean_batch_id,
            item_last_purchase_rate=item_last_purchase_rate,
            item_valuation_rate=item_valuation_rate
        )

        if mrp <= 0 and cost_info.get("custom_mrp"):
            mrp = flt(cost_info.get("custom_mrp"))

        is_expired = bool(expiry_date and getdate(expiry_date) < today_date)

        avail_qty = flt(b.batch_qty)
        if warehouse:
            try:
                from erpnext.stock.doctype.batch.batch import get_batch_qty
                w_qty = get_batch_qty(batch_no=b.name, warehouse=warehouse, item_code=item_code)
                if w_qty is not None:
                    avail_qty = flt(w_qty)
            except Exception:
                pass

        # Deduct quantities in saved (draft) Sales Invoices for this batch
        draft_si_qty = get_saved_sales_invoice_qty(item_code, batch_no=b.name, warehouse=warehouse, exclude_invoice=exclude_invoice)
        avail_qty = max(0.0, avail_qty - draft_si_qty)

        batches.append({
            "name": b.name,
            "batch_id": clean_batch_id,
            "custom_batch_id_all": clean_batch_id,
            "expiry_date": expiry_str,
            "expiry_formatted": expiry_formatted,
            "is_expired": is_expired,
            "mrp": mrp,
            "minimum_selling_price": b_min_price,
            "batch_qty": avail_qty,
            "purchase_rate": cost_info["purchase_rate"],
            "purchase_voucher": cost_info["purchase_voucher"],
            "landed_price": cost_info["landed_price"],
            "purchase_count": cost_info["purchase_count"],
            "latest_discount_pct": cost_info["latest_discount_pct"],
            "landed_subtitle": cost_info["landed_subtitle"]
        })

    # Non-batched item cost fallback
    non_batch_cost = get_purchase_and_landed_cost(
        item_code=item_code,
        item_last_purchase_rate=item_last_purchase_rate,
        item_valuation_rate=item_valuation_rate
    )

    # Select active batch details
    selected_batch = None
    if batch_no:
        selected_batch = next((b for b in batches if b["name"] == batch_no or b["batch_id"] == batch_no or b["custom_batch_id_all"] == batch_no), None)
    
    if not selected_batch and batches:
        # Default to first available batch
        selected_batch = next((b for b in batches if not b["is_expired"] and b["batch_qty"] > 0), batches[0])

    final_batch_no = selected_batch["name"] if selected_batch else (batch_no or "")
    final_batch_id = selected_batch["custom_batch_id_all"] if selected_batch else (batch_no or "")
    final_batch_qty = selected_batch["batch_qty"] if selected_batch else 0.0
    final_mrp = selected_batch["mrp"] if selected_batch else 0.0
    final_purchase_rate = selected_batch["purchase_rate"] if selected_batch else non_batch_cost["purchase_rate"]
    final_purchase_voucher = selected_batch["purchase_voucher"] if selected_batch else non_batch_cost["purchase_voucher"]
    final_landed_price = selected_batch["landed_price"] if selected_batch else non_batch_cost["landed_price"]
    final_purchase_count = selected_batch["purchase_count"] if selected_batch else non_batch_cost["purchase_count"]
    final_discount_pct = selected_batch["latest_discount_pct"] if selected_batch else non_batch_cost["latest_discount_pct"]
    final_landed_subtitle = selected_batch["landed_subtitle"] if selected_batch else non_batch_cost["landed_subtitle"]
    final_min_price = selected_batch["minimum_selling_price"] if selected_batch else min_selling_price
    final_expiry = selected_batch["expiry_formatted"] if selected_batch else ""

    # 4. Fetch Available Serial Numbers for this Item
    has_serial_tracking = bool(item_doc.get("has_serial_no"))

    # Find serial numbers already consumed in submitted Sales Invoices or Delivery Notes
    # (catches cases where tabSerial No.status was not updated correctly)
    already_used_serials = set(r[0] for r in frappe.db.sql("""
        SELECT DISTINCT sbbe.serial_no
        FROM `tabSerial and Batch Entry` sbbe
        JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbbe.parent
        WHERE sbb.item_code = %(item_code)s
          AND sbbe.qty < 0
          AND sbb.docstatus = 1
          AND sbb.voucher_type IN ('Sales Invoice', 'Delivery Note')
    """, {"item_code": item_code}))

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

    # Exclude serials that are actually sold (via bundle) even if status not updated
    serial_records = [s for s in serial_records if s["name"] not in already_used_serials]

    # Filter serial numbers to the active batch if item has batches
    if final_batch_no:
        serial_numbers = [s["name"] for s in serial_records if s.get("batch_no") == final_batch_no]
    else:
        serial_numbers = [s["name"] for s in serial_records]

    if serial_records:
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
        "batch_qty": float(final_batch_qty),
        "mrp": float(final_mrp),
        "purchase_rate": float(final_purchase_rate),
        "purchase_voucher": final_purchase_voucher,
        "landed_price": float(final_landed_price),
        "purchase_count": int(final_purchase_count),
        "latest_discount_pct": float(final_discount_pct),
        "landed_subtitle": final_landed_subtitle,
        "minimum_selling_price": float(final_min_price),
        "standard_rate": float(item_doc.get("standard_rate") or 0.0),
        "batches": batches,
        "history": history
    }


@frappe.whitelist()
def validate_batch_stock(item_code, batch_no, qty, warehouse=None, exclude_invoice=None):
    """Checks if requested qty is available in the batch after deducting saved draft invoices."""
    qty = flt(qty)
    avail_qty = 0.0
    if warehouse:
        try:
            from erpnext.stock.doctype.batch.batch import get_batch_qty
            w_qty = get_batch_qty(batch_no=batch_no, warehouse=warehouse, item_code=item_code)
            if w_qty is not None:
                avail_qty = flt(w_qty)
        except Exception:
            pass
    if avail_qty == 0.0:
        avail_qty = flt(frappe.db.get_value("Batch", batch_no, "batch_qty") or 0.0)

    draft_si_qty = get_saved_sales_invoice_qty(item_code, batch_no=batch_no, warehouse=warehouse, exclude_invoice=exclude_invoice)
    avail_qty = max(0.0, avail_qty - draft_si_qty)
    
    clean_batch = frappe.db.get_value("Batch", batch_no, "custom_batch_id_all") or batch_no
    return {
        "is_available": (qty <= avail_qty),
        "available_qty": avail_qty,
        "requested_qty": qty,
        "clean_batch": clean_batch
    }


def configure_ewaybill_field():
    """Ensure Sales Invoice and Delivery Note ewaybill and transporter_name fields are editable and visible."""
    try:
        from frappe.custom.doctype.property_setter.property_setter import make_property_setter

        # 1. Sales Invoice - ewaybill
        if frappe.db.exists("Custom Field", "Sales Invoice-ewaybill"):
            cf = frappe.get_doc("Custom Field", "Sales Invoice-ewaybill")
            cf.read_only = 0
            cf.depends_on = ""
            cf.allow_on_submit = 1
            cf.save(ignore_permissions=True)

        # 2. Sales Invoice - transporter_name
        if frappe.db.exists("Custom Field", "Sales Invoice-transporter_name"):
            cf = frappe.get_doc("Custom Field", "Sales Invoice-transporter_name")
            cf.read_only = 0
            cf.read_only_depends_on = ""
            cf.allow_on_submit = 1
            cf.save(ignore_permissions=True)

        # 3. Delivery Note - ewaybill
        if frappe.db.exists("Custom Field", "Delivery Note-ewaybill"):
            cf = frappe.get_doc("Custom Field", "Delivery Note-ewaybill")
            cf.read_only = 0
            cf.depends_on = ""
            cf.allow_on_submit = 1
            cf.save(ignore_permissions=True)

        # 4. Delivery Note & other doctypes - transporter_name
        for dt in ["Sales Invoice", "Delivery Note", "Purchase Invoice", "Stock Entry", "Subcontracting Receipt"]:
            cf_name = f"{dt}-transporter_name"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.db.set_value(
                    "Custom Field",
                    cf_name,
                    {
                        "read_only": 0,
                        "read_only_depends_on": "",
                        "allow_on_submit": 1,
                    },
                    update_modified=False,
                )

            # Delete any read_only_depends_on Property Setter that locks transporter_name when doc.ewaybill is set
            frappe.db.delete(
                "Property Setter",
                {
                    "doc_type": dt,
                    "field_name": "transporter_name",
                    "property": "read_only_depends_on",
                },
            )

            # Ensure read_only=0 and allow_on_submit=1 via Property Setter (especially for standard DocFields like in Delivery Note)
            try:
                make_property_setter(dt, "transporter_name", "read_only", 0, "Check", validate_fields_for_doctype=False)
                make_property_setter(dt, "transporter_name", "allow_on_submit", 1, "Check", validate_fields_for_doctype=False)
            except Exception:
                pass

            frappe.clear_cache(doctype=dt)

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="Failed to configure ewaybill/transporter custom fields", message=str(e))


@frappe.whitelist()
def validate_link_and_fetch(
    doctype: str,
    docname: str,
    fields_to_fetch: list[str] | str | None = None,
    query: str | None = None,
    filters: dict | list | str | None = None,
    **search_args,
):
    import frappe.client
    resolved_docname = docname
    if doctype == "Batch" and docname:
        parsed_filters = filters
        if isinstance(filters, str):
            try:
                import json
                parsed_filters = json.loads(filters)
            except Exception:
                parsed_filters = {}
        elif not isinstance(filters, dict):
            parsed_filters = {}

        item_code = parsed_filters.get("item_code") if parsed_filters else None

        batch_item = frappe.db.get_value("Batch", docname, "item") if frappe.db.exists("Batch", docname) else None
        
        # If the docname does not exist, or does not belong to the requested item_code:
        if not batch_item or (item_code and batch_item != item_code):
            found_name = None
            if item_code:
                found_name = frappe.db.get_value("Batch", {"item": item_code, "custom_batch_id_all": docname, "disabled": 0}, "name")
                if not found_name:
                    found_name = frappe.db.get_value("Batch", {"item": item_code, "batch_id": docname, "disabled": 0}, "name")

            if not found_name and item_code:
                # Prefix match for this item
                prefix_match = frappe.db.sql("""
                    SELECT name FROM `tabBatch`
                    WHERE item = %(item)s AND disabled = 0
                      AND (custom_batch_id_all LIKE %(txt)s OR batch_id LIKE %(txt)s OR name LIKE %(txt)s)
                    ORDER BY creation DESC LIMIT 1
                """, {"item": item_code, "txt": f"{docname}%"}, as_dict=True)
                if prefix_match:
                    found_name = prefix_match[0].name

            if not found_name:
                found_name = frappe.db.get_value("Batch", {"custom_batch_id_all": docname, "disabled": 0}, "name")
            if not found_name:
                found_name = frappe.db.get_value("Batch", {"batch_id": docname, "disabled": 0}, "name")

            if not found_name:
                try:
                    from frappe.desk.search import search_widget
                    s_args = dict(search_args)
                    s_args.update(
                        as_dict=False,
                        page_length=10,
                        txt=docname,
                        for_link_validation=True,
                    )
                    search_res = frappe.call(
                        search_widget,
                        doctype=doctype,
                        query=query,
                        filters=filters,
                        **s_args,
                    )
                    if search_res:
                        for item in search_res:
                            if len(item) > 1 and str(item[1]).strip().lower() == str(docname).strip().lower():
                                found_name = item[0]
                                break
                        if not found_name and len(search_res) > 0:
                            found_name = search_res[0][0]
                except Exception:
                    pass

            if found_name:
                resolved_docname = found_name

    return frappe.client.validate_link_and_fetch(
        doctype=doctype,
        docname=resolved_docname,
        fields_to_fetch=fields_to_fetch,
        query=query,
        filters=filters,
        **search_args
    )



