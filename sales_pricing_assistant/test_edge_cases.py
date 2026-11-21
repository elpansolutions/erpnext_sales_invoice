import sys
sys.path.insert(0, '/home/frappe/frappe-bench/apps/sales_pricing_assistant')
import frappe
from frappe.utils import flt
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from erpnext.stock.utils import get_stock_balance

def get_stock(item_code, warehouse="Stores - RRS"):
    return flt(get_stock_balance(item_code, warehouse))

def run_tests():
    print("=" * 60)
    print("STARTING DELIVERY NOTE SETTLEMENT (APPROACH 3) EDGE CASES TEST SUITE")
    print("=" * 60)
    
    customer = "Zydus Wellness"
    warehouse = "Stores - RRS"
    company = "RRSurgica"

    # Ensure test items have plenty of stock before running tests
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Receipt"
    se.company = company
    for code in ["TEST-DN-A", "TEST-DN-B", "TEST-DN-C", "TEST-DN-EXTRA"]:
        se.append("items", {
            "item_code": code,
            "t_warehouse": warehouse,
            "qty": 2000.0,
            "basic_rate": 100.0
        })
    se.insert(ignore_permissions=True)
    se.submit()

    # =========================================================================
    # TEST 1: Send 500 items, customer keeps 50, returns 450
    # =========================================================================
    print("\n--- TEST 1: Partial Return (Send 500, keep 50, return 450) ---")
    stock_before = get_stock("TEST-DN-A", warehouse)
    print(f"Stock before DN: {stock_before}")

    # 1. Create & submit Delivery Note for 500 items
    dn = frappe.new_doc("Delivery Note")
    dn.customer = customer
    dn.company = company
    dn.append("items", {
        "item_code": "TEST-DN-A",
        "qty": 500.0,
        "rate": 100.0,
        "warehouse": warehouse
    })
    dn.insert(ignore_permissions=True)
    dn.submit()
    print(f"Created & Submitted Delivery Note: {dn.name} (Delivered 500)")
    
    stock_after_dn = get_stock("TEST-DN-A", warehouse)
    print(f"Stock after DN: {stock_after_dn} (Expected: {stock_before - 500})")
    assert stock_after_dn == stock_before - 500, "Stock deduction failed on DN"

    # 2. Create Sales Invoice from Delivery Note
    si = make_sales_invoice(dn.name)
    assert len(si.items) == 1
    # Customer only took 50!
    si.items[0].qty = 50.0
    si.insert(ignore_permissions=True)
    si.submit()
    print(f"Submitted Sales Invoice: {si.name} with Qty: 50.0")

    # 3. Check settlement results
    si.reload()
    dn.reload()
    print(f"SI Settlement Status: {si.custom_dn_settlement_status}")
    print(f"Auto Return Notes: {si.custom_auto_return_notes}")
    
    stock_after_settlement = get_stock("TEST-DN-A", warehouse)
    print(f"Stock after SI submit: {stock_after_settlement}")
    # Net delivered should be exactly 50, so stock should be stock_before - 50!
    expected_stock = stock_before - 50.0
    print(f"Expected stock: {expected_stock}, Actual stock: {stock_after_settlement}")
    assert stock_after_settlement == expected_stock, f"Expected {expected_stock}, got {stock_after_settlement}"

    # Check that original DN is completed / fully billed against net delivered
    print(f"Delivery Note status: {dn.status}, per_billed: {dn.per_billed}%")
    assert dn.status in ["Completed", "Closed"], f"Delivery Note status is {dn.status}"
    print(">>> TEST 1 PASSED! 450 items successfully returned to stock, net 50 billed, DN completed.")

    # =========================================================================
    # TEST 2: Send 2 items, customer returns 1 item completely (user deletes row)
    # =========================================================================
    print("\n--- TEST 2: Full Item Return (Send Item A 100, Item B 200; keep 20 of A, delete B) ---")
    stock_A_before = get_stock("TEST-DN-A", warehouse)
    stock_B_before = get_stock("TEST-DN-B", warehouse)

    dn2 = frappe.new_doc("Delivery Note")
    dn2.customer = customer
    dn2.company = company
    dn2.append("items", {
        "item_code": "TEST-DN-A",
        "qty": 100.0,
        "rate": 100.0,
        "warehouse": warehouse
    })
    dn2.append("items", {
        "item_code": "TEST-DN-B",
        "qty": 200.0,
        "rate": 150.0,
        "warehouse": warehouse
    })
    dn2.insert(ignore_permissions=True)
    dn2.submit()
    print(f"Created & Submitted Delivery Note: {dn2.name} (A: 100, B: 200)")

    si2 = make_sales_invoice(dn2.name)
    # Customer kept 20 of Item A
    si2.items[0].qty = 20.0
    # Customer returned ALL 200 of Item B -> user deletes Item B row from Sales Invoice
    si2.items.pop(1)
    assert len(si2.items) == 1, "Expected only Item A in SI"
    si2.insert(ignore_permissions=True)
    si2.submit()
    print(f"Submitted Sales Invoice: {si2.name} with only Item A (20.0)")

    stock_A_after = get_stock("TEST-DN-A", warehouse)
    stock_B_after = get_stock("TEST-DN-B", warehouse)
    print(f"Item A stock: {stock_A_after} (Expected: {stock_A_before - 20})")
    print(f"Item B stock: {stock_B_after} (Expected: {stock_B_before} - fully returned!)")
    assert stock_A_after == stock_A_before - 20, "Item A stock incorrect"
    assert stock_B_after == stock_B_before, "Item B stock should be 100% returned!"

    dn2.reload()
    print(f"DN2 status: {dn2.status}, per_billed: {dn2.per_billed}%")
    assert dn2.status in ["Completed", "Closed"], f"DN2 status is {dn2.status}"
    print(">>> TEST 2 PASSED! Deleted line Item B was 100% returned to inventory automatically.")

    # =========================================================================
    # TEST 3: Returns + Extra items added to Sales Invoice
    # =========================================================================
    print("\n--- TEST 3: Returns + Extra Items Added ---")
    stock_A_before = get_stock("TEST-DN-A", warehouse)
    stock_extra_before = get_stock("TEST-DN-EXTRA", warehouse)

    dn3 = frappe.new_doc("Delivery Note")
    dn3.customer = customer
    dn3.company = company
    dn3.append("items", {
        "item_code": "TEST-DN-A",
        "qty": 300.0,
        "rate": 100.0,
        "warehouse": warehouse
    })
    dn3.insert(ignore_permissions=True)
    dn3.submit()
    print(f"Created & Submitted Delivery Note: {dn3.name} (A: 300)")

    si3 = make_sales_invoice(dn3.name)
    # Customer kept 50 of Item A (returns 250)
    si3.items[0].qty = 50.0
    # Customer also took 15 of TEST-DN-EXTRA (extra item not on DN)
    si3.append("items", {
        "item_code": "TEST-DN-EXTRA",
        "qty": 15.0,
        "rate": 200.0,
        "warehouse": warehouse
    })
    si3.insert(ignore_permissions=True)
    si3.submit()
    print(f"Submitted Sales Invoice: {si3.name} with Item A (50) and Extra Item (15)")

    si3.reload()
    print(f"Auto Return Notes: {si3.custom_auto_return_notes}")
    print(f"Auto Delivery Notes: {si3.custom_auto_delivery_notes}")

    stock_A_after = get_stock("TEST-DN-A", warehouse)
    stock_extra_after = get_stock("TEST-DN-EXTRA", warehouse)
    print(f"Item A stock: {stock_A_after} (Expected: {stock_A_before - 50})")
    print(f"Extra Item stock: {stock_extra_after} (Expected: {stock_extra_before - 15})")
    assert stock_A_after == stock_A_before - 50, "Item A stock incorrect"
    assert stock_extra_after == stock_extra_before - 15, "Extra item stock should be deducted by auto DN!"

    # Verify that the extra item in SI is now linked to the auto Delivery Note
    extra_row = [r for r in si3.items if r.item_code == "TEST-DN-EXTRA"][0]
    print(f"Extra row linked Delivery Note: {extra_row.delivery_note}, dn_detail: {extra_row.dn_detail}")
    assert extra_row.delivery_note is not None, "Extra row should be linked to auto Delivery Note"
    print(">>> TEST 3 PASSED! 250 of Item A returned, 15 of Extra Item deducted and linked.")

    # =========================================================================
    # TEST 4: Excess quantity on an existing item (Delivered 50, customer took 65)
    # =========================================================================
    print("\n--- TEST 4: Excess Qty on Existing Item (Delivered 50, Takes 65) ---")
    stock_C_before = get_stock("TEST-DN-C", warehouse)

    dn4 = frappe.new_doc("Delivery Note")
    dn4.customer = customer
    dn4.company = company
    dn4.append("items", {
        "item_code": "TEST-DN-C",
        "qty": 50.0,
        "rate": 120.0,
        "warehouse": warehouse
    })
    dn4.insert(ignore_permissions=True)
    dn4.submit()
    print(f"Created & Submitted Delivery Note: {dn4.name} (C: 50)")

    si4 = make_sales_invoice(dn4.name)
    # Customer took 65! (15 more than delivered)
    si4.items[0].qty = 65.0
    si4.insert(ignore_permissions=True)
    print(f"Sales Invoice saved! Item count after auto-split: {len(si4.items)}")
    for it in si4.items:
        print(f" - {it.item_code}: Qty {it.qty}, DN: {it.delivery_note}")
    assert len(si4.items) == 2, "Row should have been split into 50 (DN) and 15 (Extra)"
    assert si4.items[0].qty == 50.0 and si4.items[0].delivery_note == dn4.name
    assert si4.items[1].qty == 15.0 and si4.items[1].delivery_note is None

    si4.submit()
    print(f"Sales Invoice {si4.name} submitted without any overbilling error!")

    stock_C_after = get_stock("TEST-DN-C", warehouse)
    print(f"Item C stock: {stock_C_after} (Expected: {stock_C_before - 65})")
    assert stock_C_after == stock_C_before - 65, "Total 65 should be deducted (50 via DN4 + 15 via auto DN)!"
    print(">>> TEST 4 PASSED! Excess qty split cleanly, no overbilling error, extra 15 delivered.")

    # =========================================================================
    # TEST 5: Cancel Sales Invoice (Verifying Clean Rollback of Returns and Extras)
    # =========================================================================
    print("\n--- TEST 5: Cancellation Rollback ---")
    si3.reload()
    stock_A_before_cancel = get_stock("TEST-DN-A", warehouse)
    stock_extra_before_cancel = get_stock("TEST-DN-EXTRA", warehouse)

    si3.cancel()
    print(f"Cancelled Sales Invoice: {si3.name}")

    stock_A_after_cancel = get_stock("TEST-DN-A", warehouse)
    stock_extra_after_cancel = get_stock("TEST-DN-EXTRA", warehouse)
    print(f"Item A stock after cancel: {stock_A_after_cancel} (Expected: {stock_A_before_cancel - 250})")
    print(f"Extra Item stock after cancel: {stock_extra_after_cancel} (Expected: {stock_extra_before_cancel + 15})")
    assert stock_A_after_cancel == stock_A_before_cancel - 250, "Return DN should be cancelled (stock reversed)!"
    assert stock_extra_after_cancel == stock_extra_before_cancel + 15, "Extra DN should be cancelled (stock restored)!"
    print(">>> TEST 5 PASSED! Clean cancellation and full stock reversal.")

    # =========================================================================
    # TEST 6: Exact match (send 50, keep 50, no returns, no extras)
    # =========================================================================
    print("\n--- TEST 6: Exact Match (Send 50, keep 50) ---")
    dn6 = frappe.new_doc("Delivery Note")
    dn6.customer = customer
    dn6.company = company
    dn6.append("items", {
        "item_code": "TEST-DN-A",
        "qty": 50.0,
        "rate": 100.0,
        "warehouse": warehouse
    })
    dn6.insert(ignore_permissions=True)
    dn6.submit()

    si6 = make_sales_invoice(dn6.name)
    si6.insert(ignore_permissions=True)
    si6.submit()

    si6.reload()
    print(f"SI6 auto return notes: {si6.custom_auto_return_notes}")
    print(f"SI6 auto delivery notes: {si6.custom_auto_delivery_notes}")
    assert not si6.custom_auto_return_notes, "No return notes should be created for exact match"
    assert not si6.custom_auto_delivery_notes, "No extra delivery notes should be created for exact match"
    print(">>> TEST 6 PASSED! Exact match works cleanly with standard ERPNext flow.")

    # =========================================================================
    # TEST 7: Batch Swapping & Pricing Update (Change Batch B1 -> B2 and Rate 150 -> 180)
    # =========================================================================
    print("\n--- TEST 7: Batch Swapping & Pricing Update ---")
    b1 = "5678-003"
    b2 = "789456"
    stock_b1_before = flt(frappe.db.get_value("Batch", b1, "batch_qty") or 0.0)
    stock_b2_before = flt(frappe.db.get_value("Batch", b2, "batch_qty") or 0.0)
    print(f"Before DN: B1 ({b1}) = {stock_b1_before}, B2 ({b2}) = {stock_b2_before}")

    dn7 = frappe.new_doc("Delivery Note")
    dn7.customer = customer
    dn7.company = company
    dn7.append("items", {
        "item_code": "003",
        "qty": 2.0,
        "rate": 150.0,
        "warehouse": warehouse,
        "batch_no": b1
    })
    dn7.insert(ignore_permissions=True)
    dn7.submit()
    print(f"DN7 submitted with Batch {b1} (Rate 150.0): {dn7.name}")

    stock_b1_after_dn = flt(frappe.db.get_value("Batch", b1, "batch_qty") or 0.0)
    assert stock_b1_after_dn == stock_b1_before - 2.0, "Batch B1 should be deducted on DN7"

    si7 = make_sales_invoice(dn7.name)
    # Customer swapped to Batch B2, and price negotiated to 180 (higher rate!)
    si7.items[0].batch_no = b2
    si7.items[0].rate = 180.0
    si7.calculate_taxes_and_totals()
    si7.insert(ignore_permissions=True)
    si7.submit()
    print(f"Submitted SI7: {si7.name} with new Batch {b2} and higher Rate 180.0!")

    si7.reload()
    print(f"SI7 Auto Return Notes: {si7.custom_auto_return_notes}")
    print(f"SI7 Auto Delivery Notes: {si7.custom_auto_delivery_notes}")

    stock_b1_final = flt(frappe.db.get_value("Batch", b1, "batch_qty") or 0.0)
    stock_b2_final = flt(frappe.db.get_value("Batch", b2, "batch_qty") or 0.0)
    print(f"Final stock: B1 ({b1}) = {stock_b1_final} (Expected: {stock_b1_before} - restored!)")
    print(f"Final stock: B2 ({b2}) = {stock_b2_final} (Expected: {stock_b2_before - 2.0} - deducted!)")
    assert stock_b1_final == stock_b1_before, "Batch B1 should be returned to inventory!"
    assert stock_b2_final == stock_b2_before - 2.0, "Batch B2 should be deducted via auto Delivery Note!"
    print(">>> TEST 7 PASSED! Batch swapped cleanly: B1 restored, B2 deducted, higher rate 180 accepted.")

    print("\n" + "=" * 60)
    print("ALL 7 EDGE CASES PASSED THOROUGHLY AND SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    frappe.init(site="site1.local")
    frappe.connect()
    frappe.flags.in_test = True
    run_tests()
    frappe.db.commit()
