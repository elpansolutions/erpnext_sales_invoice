import json
import frappe
from frappe import _
from frappe.utils import flt, cstr, cint
from erpnext.controllers.sales_and_purchase_return import make_return_doc


def validate_sales_invoice_delivery_note(doc, method=None):
	"""
	Validates Sales Invoice when items are linked to a Delivery Note:
	1. Ensures update_stock is 0 if items come from a Delivery Note.
	2. Automatically cleans up zero/negative quantity rows.
	3. Automatically splits any excess quantity above the Delivery Note quantity into
	   an extra item row (unlinked to DN) so ERPNext does not raise an over-billing error,
	   and the excess can be delivered via an automatic Delivery Note on submit.
	"""
	if doc.is_return or not doc.get("items"):
		return

	has_dn_linked = any(item.delivery_note for item in doc.items)
	if not has_dn_linked:
		return

	# If update_stock is ticked, uncheck it because stock was already deducted by DN
	# and settlement will handle return and extra stock movements automatically.
	if cint(doc.update_stock) == 1:
		doc.update_stock = 0
		frappe.msgprint(
			_(
				"Note: 'Update Stock' was unchecked because this invoice is linked to Delivery Note(s). "
				"Stock returns for unkept items and deliveries for extra items will be handled automatically upon submission."
			),
			indicator="orange",
			alert=True,
		)

	# Clean up zero-qty rows and split excess quantities
	cleaned_items = []
	items_added = []

	for row in doc.items:
		qty = flt(row.qty)
		if qty <= 0:
			continue  # Exclude row with 0 or negative qty; will be treated as fully returned

		if row.delivery_note and row.dn_detail:
			dn_item = frappe.db.get_value("Delivery Note Item", row.dn_detail, ["qty", "batch_no", "item_code"], as_dict=True)
			if dn_item:
				# If item_code or batch was changed from the original delivered item
				is_item_changed = dn_item.item_code and row.item_code and row.item_code != dn_item.item_code
				is_batch_changed = dn_item.batch_no and row.batch_no and row.batch_no != dn_item.batch_no
				if is_item_changed or is_batch_changed:
					row.dn_detail = None
					row.sales_order = None
					row.so_detail = None
					cleaned_items.append(row)
					continue

				# Check original DN item quantity
				dn_qty = flt(dn_item.qty)
				if qty > dn_qty:
					excess_qty = qty - dn_qty
					# Cap this row at delivered qty
					row.qty = dn_qty
					row.stock_qty = dn_qty * flt(row.conversion_factor or 1.0)
					row.amount = flt(row.qty) * flt(row.rate or 0.0)
					row.base_amount = flt(row.qty) * flt(row.base_rate or row.rate or 0.0)
					cleaned_items.append(row)

					# Create extra row for excess
					excess_row = frappe.copy_doc(row)
					excess_row.name = None
					excess_row.qty = excess_qty
					excess_row.stock_qty = flt(excess_qty) * flt(row.conversion_factor or 1.0)
					excess_row.amount = flt(excess_qty) * flt(row.rate or 0.0)
					excess_row.base_amount = flt(excess_qty) * flt(row.base_rate or row.rate or 0.0)
					excess_row.delivery_note = None
					excess_row.dn_detail = None
					excess_row.sales_order = None
					excess_row.so_detail = None
					if hasattr(excess_row, "custom_free_qty"):
						excess_row.custom_free_qty = 0
					items_added.append(excess_row)
					continue

		cleaned_items.append(row)

	if items_added:
		cleaned_items.extend(items_added)
		for idx, it in enumerate(cleaned_items):
			it.idx = idx + 1
		frappe.msgprint(
			_(
				"Quantities exceeding the original Delivery Note were automatically split into extra item rows. "
				"These extra items will be delivered automatically upon submission."
			),
			indicator="blue",
			alert=True,
		)

	doc.items = cleaned_items


def settle_delivery_note_before_submit(doc, method=None):
	"""
	Runs in before_submit of Sales Invoice:
	1. For each linked Delivery Note:
	   Calculates items/quantities that were NOT kept (delivered - already_returned - billed).
	   Creates and submits a Return Delivery Note (is_return = 1) for the difference.
	   This returns returned items (e.g. 450 out of 500) back to inventory immediately!
	2. For extra items (items without delivery_note):
	   Creates and submits a new Delivery Note for the extra items so stock is deducted.
	   Links the Sales Invoice extra item rows to the new Delivery Note.
	3. Records the created document names in custom fields for audit and cancellation.
	"""
	if doc.is_return or not doc.get("items"):
		return

	# Collect all unique linked delivery notes
	linked_dns = list(dict.fromkeys(item.delivery_note for item in doc.items if item.delivery_note))
	if not linked_dns:
		return

	auto_return_notes = []
	auto_delivery_notes = []

	# 1. Process Returns for each linked Delivery Note
	for dn_name in linked_dns:
		if not frappe.db.exists("Delivery Note", dn_name):
			continue

		dn = frappe.get_doc("Delivery Note", dn_name)
		return_items_to_add = []

		for dni in dn.items:
			delivered_qty = flt(dni.qty)
			if delivered_qty <= 0:
				continue

			# Calculate already returned qty against this DN item
			already_returned_res = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(ABS(dni.qty)), 0)
				FROM `tabDelivery Note Item` dni
				INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
				WHERE dn.docstatus = 1 AND dn.is_return = 1 AND dni.dn_detail = %s
				""",
				dni.name,
			)
			already_returned = flt(already_returned_res[0][0]) if already_returned_res else 0.0

			# Calculate already billed qty in other submitted invoices
			already_billed_res = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(qty), 0)
				FROM `tabSales Invoice Item`
				WHERE docstatus = 1 AND parent != %s AND dn_detail = %s
				""",
				(doc.name, dni.name),
			)
			already_billed = flt(already_billed_res[0][0]) if already_billed_res else 0.0

			# Calculate currently billed qty in this invoice
			current_billed = sum(
				flt(item.qty)
				for item in doc.items
				if item.dn_detail == dni.name and item.delivery_note == dn_name
			)

			# Net quantity that needs to be returned to stock
			qty_to_return = delivered_qty - (already_returned + already_billed + current_billed)

			if qty_to_return > 0.0001:
				return_items_to_add.append((dni, qty_to_return))

		if return_items_to_add:
			return_map = {dni.name: ret_qty for dni, ret_qty in return_items_to_add}
			ret_dn = make_return_doc("Delivery Note", dn_name)
			ret_dn.__init__(ret_dn.as_dict())

			valid_ret_items = []
			for row in ret_dn.items:
				if row.dn_detail in return_map:
					ret_qty = return_map[row.dn_detail]
					row.qty = -flt(ret_qty)
					row.stock_qty = -flt(ret_qty) * flt(row.conversion_factor or 1.0)
					row.amount = -flt(ret_qty) * flt(row.rate or 0.0)
					row.base_amount = -flt(ret_qty) * flt(row.base_rate or row.rate or 0.0)
					if hasattr(row, "custom_free_qty") and flt(row.custom_free_qty) != 0:
						free_ratio = abs(flt(row.custom_free_qty)) / flt(row.qty) if flt(row.qty) != 0 else 0
						row.custom_free_qty = -abs(flt(ret_qty * free_ratio))
					valid_ret_items.append(row)

			ret_dn.items = valid_ret_items
			ret_dn.posting_date = doc.posting_date
			ret_dn.posting_time = doc.posting_time
			ret_dn.remarks = (
				f"Auto-settlement: Return of unkept items from {dn_name} against Sales Invoice {doc.name}"
			)
			ret_dn.flags.ignore_permissions = True
			ret_dn.insert()
			ret_dn.submit()

			auto_return_notes.append(ret_dn.name)
			doc.add_comment(
				"Comment",
				f"Auto-created and submitted Return Delivery Note <a href='/app/delivery-note/{ret_dn.name}'><b>{ret_dn.name}</b></a> for {len(return_items_to_add)} unkept item(s). Stock has been returned to inventory.",
			)

	# 2. Process Extra Items (items without delivery_note or without dn_detail)
	extra_items = [
		item
		for item in doc.items
		if (not item.delivery_note or not item.dn_detail)
		and flt(item.qty) > 0
		and frappe.get_cached_value("Item", item.item_code, "is_stock_item")
	]

	if extra_items:
		extra_dn = frappe.new_doc("Delivery Note")
		extra_dn.customer = doc.customer
		extra_dn.company = doc.company
		extra_dn.posting_date = doc.posting_date
		extra_dn.posting_time = doc.posting_time
		extra_dn.set_warehouse = doc.set_warehouse or extra_items[0].warehouse
		extra_dn.remarks = (
			f"Auto-settlement: Extra items delivered with Sales Invoice {doc.name}"
		)

		extra_row_map = []
		for item in extra_items:
			dni = extra_dn.append("items", {})
			dni.item_code = item.item_code
			dni.item_name = item.item_name
			dni.description = item.description
			dni.qty = item.qty
			dni.rate = item.rate
			dni.warehouse = item.warehouse or extra_dn.set_warehouse
			dni.batch_no = item.batch_no
			dni.serial_no = item.serial_no
			dni.uom = item.uom
			dni.stock_uom = item.stock_uom
			dni.conversion_factor = item.conversion_factor or 1.0
			if hasattr(item, "custom_batch_id_all") and item.custom_batch_id_all:
				dni.custom_batch_id_all = item.custom_batch_id_all
			if hasattr(item, "custom_free_qty") and item.custom_free_qty:
				dni.custom_free_qty = item.custom_free_qty
			extra_row_map.append((item, dni))

		extra_dn.flags.ignore_permissions = True
		extra_dn.insert()
		extra_dn.submit()

		auto_delivery_notes.append(extra_dn.name)

		# Link the extra items in this Sales Invoice to the new Delivery Note!
		for inv_item, dn_item in extra_row_map:
			inv_item.delivery_note = extra_dn.name
			inv_item.dn_detail = dn_item.name

		doc.add_comment(
			"Comment",
			f"Auto-created and submitted Delivery Note <a href='/app/delivery-note/{extra_dn.name}'><b>{extra_dn.name}</b></a> for extra items. Stock has been deducted from inventory.",
		)

	# 3. Store references in doc fields
	if auto_return_notes:
		doc.custom_auto_return_notes = json.dumps(auto_return_notes)
	if auto_delivery_notes:
		doc.custom_auto_delivery_notes = json.dumps(auto_delivery_notes)
	if auto_return_notes or auto_delivery_notes:
		doc.custom_dn_settlement_status = "Settled"


def settle_delivery_note_on_submit(doc, method=None):
	"""
	Runs in on_submit of Sales Invoice:
	Recalculates billing status and percentages for all linked Delivery Notes
	so they cleanly reach 100% (Completed).
	"""
	if doc.is_return or not doc.get("items"):
		return

	linked_dns = list(dict.fromkeys(item.delivery_note for item in doc.items if item.delivery_note))
	for dn_name in linked_dns:
		if frappe.db.exists("Delivery Note", dn_name):
			try:
				dn = frappe.get_doc("Delivery Note", dn_name)
				dn.update_billing_status()
			except Exception:
				pass


def settle_delivery_note_on_cancel(doc, method=None):
	"""
	Runs in on_cancel of Sales Invoice:
	Cancels all auto-created Return Delivery Notes and Extra Delivery Notes
	so stock movements are completely and accurately reversed.
	"""
	if doc.is_return:
		return

	# 1. Cancel Auto Return Delivery Notes
	return_notes = []
	if getattr(doc, "custom_auto_return_notes", None):
		try:
			return_notes = json.loads(doc.custom_auto_return_notes)
		except Exception:
			return_notes = [n.strip() for n in doc.custom_auto_return_notes.split(",") if n.strip()]

	for ret_name in return_notes:
		if frappe.db.exists("Delivery Note", ret_name):
			status = frappe.db.get_value("Delivery Note", ret_name, "docstatus")
			if status == 1:
				ret_doc = frappe.get_doc("Delivery Note", ret_name)
				ret_doc.flags.ignore_permissions = True
				ret_doc.cancel()
				doc.add_comment(
					"Comment",
					f"Cancelled auto-created Return Delivery Note <b>{ret_name}</b> upon cancellation of this invoice.",
				)

	# 2. Cancel Auto Extra Delivery Notes
	extra_notes = []
	if getattr(doc, "custom_auto_delivery_notes", None):
		try:
			extra_notes = json.loads(doc.custom_auto_delivery_notes)
		except Exception:
			extra_notes = [n.strip() for n in doc.custom_auto_delivery_notes.split(",") if n.strip()]

	for extra_name in extra_notes:
		if frappe.db.exists("Delivery Note", extra_name):
			status = frappe.db.get_value("Delivery Note", extra_name, "docstatus")
			if status == 1:
				extra_doc = frappe.get_doc("Delivery Note", extra_name)
				extra_doc.flags.ignore_permissions = True
				extra_doc.cancel()
				doc.add_comment(
					"Comment",
					f"Cancelled auto-created Extra Delivery Note <b>{extra_name}</b> upon cancellation of this invoice.",
				)


@frappe.whitelist()
def get_dn_settlement_preview(doc):
	"""
	API for the UI preview dialog:
	Calculates and returns a preview of what will be returned to stock
	and what extra items will be delivered when this invoice is submitted.
	"""
	if isinstance(doc, str):
		doc = frappe.get_doc(json.loads(doc))

	linked_dns = list(dict.fromkeys(item.delivery_note for item in doc.get("items", []) if item.delivery_note))
	if not linked_dns:
		return {
			"has_linked_dn": False,
			"message": _("No items are linked to a Delivery Note.")
		}

	items_summary = []
	total_delivered = 0.0
	total_billed = 0.0
	total_returning = 0.0
	total_extra = 0.0

	for dn_name in linked_dns:
		if not frappe.db.exists("Delivery Note", dn_name):
			continue

		dn = frappe.get_doc("Delivery Note", dn_name)
		for dni in dn.items:
			delivered_qty = flt(dni.qty)
			if delivered_qty <= 0:
				continue

			already_returned_res = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(ABS(dni.qty)), 0)
				FROM `tabDelivery Note Item` dni
				INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
				WHERE dn.docstatus = 1 AND dn.is_return = 1 AND dni.dn_detail = %s
				""",
				dni.name,
			)
			already_returned = flt(already_returned_res[0][0]) if already_returned_res else 0.0

			already_billed_res = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(qty), 0)
				FROM `tabSales Invoice Item`
				WHERE docstatus = 1 AND parent != %s AND dn_detail = %s
				""",
				(doc.name or "", dni.name),
			)
			already_billed = flt(already_billed_res[0][0]) if already_billed_res else 0.0

			current_billed = sum(
				flt(item.qty)
				for item in doc.get("items", [])
				if item.dn_detail == dni.name and item.delivery_note == dn_name
			)

			qty_to_return = delivered_qty - (already_returned + already_billed + current_billed)
			qty_to_return = max(0.0, qty_to_return)

			total_delivered += delivered_qty
			total_billed += current_billed
			total_returning += qty_to_return

			items_summary.append({
				"dn_name": dn_name,
				"item_code": dni.item_code,
				"item_name": dni.item_name,
				"batch_no": dni.batch_no or "",
				"warehouse": dni.warehouse,
				"delivered_qty": delivered_qty,
				"billed_qty": current_billed,
				"return_qty": qty_to_return,
				"status": "Kept" if qty_to_return == 0 else ("Partially Kept" if current_billed > 0 else "Fully Returned")
			})

	# Extra items
	extra_items_list = []
	for item in doc.get("items", []):
		if (not item.delivery_note or not item.dn_detail) and flt(item.qty) > 0:
			qty = flt(item.qty)
			total_extra += qty
			total_billed += qty
			extra_items_list.append({
				"item_code": item.item_code,
				"item_name": item.item_name,
				"batch_no": item.batch_no or "",
				"warehouse": item.warehouse or doc.set_warehouse or "",
				"qty": qty,
				"rate": item.rate or 0.0
			})

	return {
		"has_linked_dn": True,
		"delivery_notes": linked_dns,
		"items_summary": items_summary,
		"extra_items": extra_items_list,
		"total_delivered": total_delivered,
		"total_billed": total_billed,
		"total_returning": total_returning,
		"total_extra": total_extra
	}
