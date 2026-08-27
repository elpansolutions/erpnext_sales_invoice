# ERPNext Sales Invoice Pricing Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Frappe Framework](https://img.shields.io/badge/Frappe-v14%20%7C%20v15%20%7C%20v16-orange.svg)](https://frappeframework.com)
[![ERPNext](https://img.shields.io/badge/ERPNext-Compatible-green.svg)](https://erpnext.com)

**Sales Pricing Assistant** (`erpnext_sales_invoice` / `sales_pricing_assistant`) is a custom Frappe / ERPNext application that enhances the Sales Invoice workflow. It displays an interactive pricing intelligence popup whenever a Customer, Item, and Batch are selected, helping sales teams make fast, profitable, and compliant pricing decisions.

---

## 🚀 Key Features

1. **Automatic Modal Trigger**:
   - Pops up seamlessly in the Sales Invoice form as soon as an Item and **Batch** are selected for a Customer (or upon Item selection for non-batch items).

2. **Batch-Specific Purchase Price & MRP**:
   - **Batch MRP**: Automatically fetched from the Batch master (`custom_custom_mrp`) or Purchase Invoice item (`custom_mrp`).
   - **Purchase Price**: Dynamically fetched from the latest submitted Purchase Invoice for that specific item and batch (with fallback to Item's last purchase rate / valuation rate).

3. **Past 5 Sales Prices to Customer**:
   - Shows the last 5 invoices where this product was sold to the selected customer.
   - Includes Invoice Number, Posting Date, Batch Number, Quantity, and Historical Rate.
   - Features a **1-click "Use Price"** button on each row to instantly populate the selling price.

4. **Live Margin Calculator**:
   - Calculate selling price based on purchase price using either:
     - **Percentage Margin (`%`)**
     - **Flat Amount Margin (`₹` / Currency)**
   - Quick one-click preset buttons (`+5%`, `+10%`, `+15%`, `+20%`, `+25%`).

5. **Minimum Selling Price Protection & Override**:
   - Reads the item's configured **Minimum Selling Price** floor.
   - If the chosen price falls below the minimum selling price:
     - Displays a prominent warning banner.
     - Disables the **Apply Price** button.
     - Requires an explicit **"Override Minimum Selling Price"** checkbox confirmation to authorize sub-floor rates.

6. **Seamless ERPNext Flow & Escape Support**:
   - Applying updates `rate`, `price_list_rate`, and `custom_mrp`, triggering standard ERPNext tax and total recalculations.
   - Pressing **Escape (`Esc`)** or clicking **Cancel** dismisses the popup immediately with zero modification, preserving ERPNext's standard flow.

---

## 📋 Requirements & Prerequisites

- **Frappe Framework**: Version 14, 15, or 16
- **ERPNext**: Version 14, 15, or 16
- **Python**: `>= 3.10`
- **Node.js**: `>= 18`

---

## 🛠️ Installation Steps

### Step 1: Fetch the App
Run from your `frappe-bench` directory:
```bash
bench get-app https://github.com/elpansolutions/erpnext_sales_invoice.git
```
*(Or if using the local app folder: `bench get-app sales_pricing_assistant`)*

### Step 2: Install App on Your Site
Replace `site1.local` with your site name:
```bash
bench --site site1.local install-app sales_pricing_assistant
```

### Step 3: Run Database Migrations
Ensures custom fields (such as `minimum_selling_price` on `Item`) are properly synced:
```bash
bench --site site1.local migrate
```

### Step 4: Build Assets & Clear Cache
```bash
bench --site site1.local clear-cache
```

---

## ⚙️ Configuration & Usage

1. **Setting Minimum Selling Price**:
   - Go to **Stock > Item** > open an item.
   - In the **Pricing** section, set the **Minimum Selling Price** field.
   - Save the item.

2. **Creating a Sales Invoice**:
   - Navigate to **Accounting > Sales Invoice > New**.
   - Select the **Customer**.
   - In the **Items** child table, choose an **Item Code**.
   - Select the **Batch No** (for batch-tracked items).
   - The **Pricing Assistant** popup will appear automatically with batch MRP, purchase rate, prior customer prices, and margin controls.
   - Pick an old price, apply a margin, or enter a custom rate, then click **Apply Price**.
   - To bypass without changing, press **Escape (`Esc`)** or click **Cancel**.

---

## 📁 Repository Structure

```text
sales_pricing_assistant/
├── LICENSE
├── pyproject.toml
├── README.md
└── sales_pricing_assistant/
    ├── __init__.py
    ├── hooks.py
    ├── api.py                     # Backend API for pricing, batch, and historical queries
    ├── modules.txt
    ├── fixtures/
    │   └── custom_field.json      # Custom field fixture for Item.minimum_selling_price
    └── public/
        └── js/
            └── sales_invoice_pricing.js  # Client script with interactive modal & validations
```

---

## 📄 License
MIT License. Created by [Elpan Solutions](https://github.com/elpansolutions).
