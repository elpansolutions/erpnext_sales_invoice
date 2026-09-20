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
}

def setup_custom_fields():
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
