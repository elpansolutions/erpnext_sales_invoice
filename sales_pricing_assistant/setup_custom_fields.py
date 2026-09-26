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
    ],
    "Sales Invoice": [
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "customer_name",
            "description": "Doctor name for reference and prescription billing",
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_patient_name",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
        },
        {
            "fieldname": "custom_remarks",
            "label": "Remarks",
            "fieldtype": "Small Text",
            "insert_after": "custom_goodwill_message",
            "description": "Invoice-specific remarks or notes",
        },
    ],
    "Sales Order": [
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "customer_name",
            "description": "Doctor name for reference and prescription billing",
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_patient_name",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
        },
        {
            "fieldname": "custom_remarks",
            "label": "Remarks",
            "fieldtype": "Small Text",
            "insert_after": "custom_goodwill_message",
            "description": "Order-specific remarks or notes",
        },
    ],
    "Delivery Note": [
        {
            "fieldname": "custom_doctor_name",
            "label": "Doctor Name",
            "fieldtype": "Data",
            "insert_after": "customer_name",
            "description": "Doctor name for reference and prescription billing",
        },
        {
            "fieldname": "custom_patient_name",
            "label": "Patient Name",
            "fieldtype": "Data",
            "insert_after": "custom_doctor_name",
            "description": "Patient name for reference and prescription billing",
        },
        {
            "fieldname": "custom_goodwill_message",
            "label": "Goodwill Message",
            "fieldtype": "Small Text",
            "insert_after": "custom_patient_name",
            "description": "Customer greeting or goodwill note (e.g. Wishing you good health)",
        },
        {
            "fieldname": "custom_remarks",
            "label": "Remarks",
            "fieldtype": "Small Text",
            "insert_after": "custom_goodwill_message",
            "description": "Delivery-specific remarks or notes",
        },
    ],
}

def sync_print_formats():
    import os
    template_path = os.path.join(os.path.dirname(__file__), "templates", "print_formats", "print_v4.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        for pf_name in ["v4 gst", "v5"]:
            if frappe.db.exists("Print Format", pf_name):
                frappe.db.set_value("Print Format", pf_name, "html", html_content)
                frappe.db.commit()

def setup_custom_fields():
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    sync_print_formats()

