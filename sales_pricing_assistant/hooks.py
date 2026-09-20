app_name = "sales_pricing_assistant"
app_title = "Sales Pricing Assistant"
app_publisher = "Custom"
app_description = "Sales Invoice Pricing Assistant with Batch-wise Purchase Price, MRP, and Margin Controls"
app_email = "admin@example.com"
app_license = "mit"

# Includes in <head>
# ------------------
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_pricing.js"
}

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", ["Item-minimum_selling_price"]]
        ]
    }
]

after_install = "sales_pricing_assistant.setup_custom_fields.setup_custom_fields"
after_migrate = [
    "sales_pricing_assistant.setup_custom_fields.setup_custom_fields",
    "sales_pricing_assistant.api.configure_ewaybill_field"
]

