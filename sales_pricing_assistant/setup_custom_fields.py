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
                frappe.db.commit()

def setup_custom_fields():
    remove_legacy_custom_remarks()
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    configure_allow_on_submit_fields()
    sync_print_formats()


