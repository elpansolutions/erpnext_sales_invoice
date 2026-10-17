import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
    "Sales Invoice Item": [
        {
            "fieldname": "custom_free_qty",
            "label": "Free Qty",
            "fieldtype": "Float",
            "insert_after": "qty",
            "in_list_view": 1,
            "columns": 1,
            "description": "Free / Scheme units given with this item line",
        },
        {
            "fieldname": "custom_billed_qty",
            "label": "Billed Qty",
            "fieldtype": "Float",
            "insert_after": "custom_free_qty",
            "description": "Sold / billed quantity excluding free units",
        },
        {
            "fieldname": "custom_mrp",
            "label": "MRP",
            "fieldtype": "Currency",
            "insert_after": "batch_no",
            "in_list_view": 1,
            "read_only": 1,
            "columns": 1,
        },
        {
            "fieldname": "custom_expiry",
            "label": "Expiry",
            "fieldtype": "Date",
            "insert_after": "custom_mrp",
            "in_list_view": 1,
            "read_only": 1,
            "columns": 1,
        },
    ],
    "Sales Order Item": [
        {
            "fieldname": "custom_free_qty",
            "label": "Free Qty",
            "fieldtype": "Float",
            "insert_after": "qty",
            "in_list_view": 1,
            "columns": 1,
            "description": "Free / Scheme units given with this item line",
        },
        {
            "fieldname": "custom_billed_qty",
            "label": "Billed Qty",
            "fieldtype": "Float",
            "insert_after": "custom_free_qty",
            "description": "Sold / billed quantity excluding free units",
        },
    ],
    "Delivery Note Item": [
        {
            "fieldname": "custom_free_qty",
            "label": "Free Qty",
            "fieldtype": "Float",
            "insert_after": "qty",
            "in_list_view": 1,
            "columns": 1,
            "description": "Free / Scheme units given with this item line",
        },
        {
            "fieldname": "custom_billed_qty",
            "label": "Billed Qty",
            "fieldtype": "Float",
            "insert_after": "custom_free_qty",
            "description": "Sold / billed quantity excluding free units",
        },
        {
            "fieldname": "custom_mrp",
            "label": "MRP",
            "fieldtype": "Currency",
            "insert_after": "batch_no",
            "in_list_view": 1,
            "read_only": 1,
            "columns": 1,
        },
        {
            "fieldname": "custom_expiry",
            "label": "Expiry",
            "fieldtype": "Date",
            "insert_after": "custom_mrp",
            "in_list_view": 1,
            "read_only": 1,
            "columns": 1,
        },
    ],
    "Sales Invoice": [
        {
            "fieldname": "custom_doctor_patient_section",
            "label": "Doctor, Patient & Reference Notes",
            "fieldtype": "Section Break",
            "insert_after": "other_charges_calculation",
            "collapsible": 1,
            "description": "Optional Doctor, Patient, Goodwill and Remarks details",
        },
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_patient_section",
            "description": "Doctor name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_col_break_notes",
            "fieldtype": "Column Break",
            "insert_after": "custom_patient_name",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_col_break_notes",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
            "allow_on_submit": 1,
        },
    ],
    "Sales Order": [
        {
            "fieldname": "custom_doctor_patient_section",
            "label": "Doctor, Patient & Reference Notes",
            "fieldtype": "Section Break",
            "insert_after": "other_charges_calculation",
            "collapsible": 1,
            "description": "Optional Doctor, Patient, Goodwill and Remarks details",
        },
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_patient_section",
            "description": "Doctor name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_col_break_notes",
            "fieldtype": "Column Break",
            "insert_after": "custom_patient_name",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_col_break_notes",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
            "allow_on_submit": 1,
        },
    ],
    "Delivery Note": [
        {
            "fieldname": "custom_doctor_patient_section",
            "label": "Doctor, Patient & Reference Notes",
            "fieldtype": "Section Break",
            "insert_after": "other_charges_calculation",
            "collapsible": 1,
            "description": "Optional Doctor, Patient, Goodwill and Remarks details",
        },
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_patient_section",
            "description": "Doctor name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_col_break_notes",
            "fieldtype": "Column Break",
            "insert_after": "custom_patient_name",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_col_break_notes",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
            "allow_on_submit": 1,
        },
    ],
}

def remove_legacy_custom_remarks():
    for dt in ["Sales Invoice", "Sales Order", "Delivery Note"]:
        cf_name = f"{dt}-custom_remarks"
        if frappe.db.exists("Custom Field", cf_name):
            frappe.delete_doc("Custom Field", cf_name, force=1, ignore_permissions=True)
            frappe.db.commit()

def configure_allow_on_submit_fields():
    """Ensure doctor, patient, goodwill message, and remarks fields are editable after submission."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    for dt in ["Sales Invoice", "Sales Order", "Delivery Note"]:
        for fn in ["custom_doctor_name", "custom_patient_name", "custom_goodwill_message"]:
            cf_name = f"{dt}-{fn}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.db.set_value("Custom Field", cf_name, "allow_on_submit", 1)

        try:
            make_property_setter(dt, "remarks", "allow_on_submit", 1, "Check", validate_fields_for_doctype=False)
        except Exception as e:
            frappe.log_error(title=f"Failed to set allow_on_submit Property Setter for {dt} remarks", message=str(e))

    frappe.db.commit()
    for dt in ["Sales Invoice", "Sales Order", "Delivery Note"]:
        frappe.clear_cache(doctype=dt)

def sync_print_formats():
    import os
    template_path = os.path.join(os.path.dirname(__file__), "templates", "print_formats", "print_v4.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        for pf_name in ["v4 gst", "v5"]:
            if frappe.db.exists("Print Format", pf_name):
                frappe.db.set_value("Print Format", pf_name, "html", html_content)

    dn_template_path = os.path.join(os.path.dirname(__file__), "templates", "print_formats", "print_v4_delivery_note.html")
    if os.path.exists(dn_template_path):
        with open(dn_template_path, "r", encoding="utf-8") as f:
            dn_html = f.read()
        for pf_name in ["v4 Delivery Note", "Delivery Note v4"]:
            if not frappe.db.exists("Print Format", pf_name):
                pf = frappe.get_doc({
                    "doctype": "Print Format",
                    "name": pf_name,
                    "doc_type": "Delivery Note",
                    "custom_format": 1,
                    "print_format_type": "Jinja",
                    "standard": "No",
                    "html": dn_html
                })
                pf.insert(ignore_permissions=True)
            else:
                frappe.db.set_value("Print Format", pf_name, "html", dn_html)
    frappe.db.commit()


def sync_sales_invoice_client_scripts():
    """Ensure Sales Invoice and Delivery Note client scripts enforce add row guard and qty validation."""
    try:
        import os, json
        fixtures_cs_path = os.path.join(os.path.dirname(__file__), "fixtures", "client_script.json")
        if os.path.exists(fixtures_cs_path):
            with open(fixtures_cs_path, "r", encoding="utf-8") as f:
                scripts_data = json.load(f)

            for item in scripts_data:
                target_dt = item.get("dt")
                target_name = item.get("name")
                target_script = item.get("script")

                existing_name = frappe.db.get_value("Client Script", {"dt": target_dt, "name": target_name}, "name")
                if not existing_name:
                    all_s = frappe.get_all("Client Script", filters={"dt": target_dt}, fields=["name", "script"])
                    for s in all_s:
                        if "validate_all_qty" in (s.script or ""):
                            existing_name = s.name
                            break

                if existing_name:
                    doc = frappe.get_doc("Client Script", existing_name)
                    doc.script = target_script
                    doc.enabled = 1
                    doc.save(ignore_permissions=True)
                else:
                    new_cs = frappe.get_doc({
                        "doctype": "Client Script",
                        "dt": target_dt,
                        "name": target_name,
                        "enabled": 1,
                        "view": "Form",
                        "script": target_script
                    })
                    new_cs.insert(ignore_permissions=True)

                frappe.db.commit()
                frappe.clear_cache(doctype=target_dt)
    except Exception as e:
        frappe.log_error(title="Failed to sync client scripts", message=str(e))

def setup_custom_fields():
    remove_legacy_custom_remarks()
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    # Ensure in_list_view and read_only are set on existing Custom Field records
    for dt in ["Sales Invoice Item", "Delivery Note Item"]:
        for fn in ["custom_mrp", "custom_expiry"]:
            cf_name = f"{dt}-{fn}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.db.set_value("Custom Field", cf_name, "in_list_view", 1)
                frappe.db.set_value("Custom Field", cf_name, "read_only", 1)
                frappe.db.set_value("Custom Field", cf_name, "columns", 1)
        frappe.clear_cache(doctype=dt)
    frappe.db.commit()
    configure_allow_on_submit_fields()
    sync_print_formats()
    sync_sales_invoice_client_scripts()


