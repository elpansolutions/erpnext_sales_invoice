frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Setup
    },
    refresh: function(frm) {
        // Ensure manual ewaybill field is always editable
        frm.set_df_property('ewaybill', 'read_only', 0);
        frm.set_df_property('ewaybill', 'hidden', 0);
        frm.set_df_property('ewaybill', 'reqd', 0);

        // Position standard inbuilt remarks right below Goodwill Message on main screen
        setTimeout(() => {
            if (frm.fields_dict.remarks && frm.fields_dict.custom_goodwill_message && frm.fields_dict.custom_goodwill_message.$wrapper) {
                frm.fields_dict.remarks.$wrapper.insertAfter(frm.fields_dict.custom_goodwill_message.$wrapper);
                frm.set_df_property('remarks', 'hidden', 0);
                frm.fields_dict.remarks.$wrapper.show();
            } else if (frm.fields_dict.remarks && frm.fields_dict.custom_patient_name && frm.fields_dict.custom_patient_name.$wrapper) {
                frm.fields_dict.remarks.$wrapper.insertAfter(frm.fields_dict.custom_patient_name.$wrapper);
                frm.set_df_property('remarks', 'hidden', 0);
                frm.fields_dict.remarks.$wrapper.show();
            }
        }, 100);

        // Clear default 'No Remarks' on new invoices so user sees a clean empty input
        if (frm.is_new() && frm.doc.remarks === 'No Remarks') {
            frm.set_value('remarks', '');
        }

        // Add button to sort items table alphabetically by Item Name / Item Code
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Sort Items A-Z'), function() {
                sort_items_alphabetically(frm);
            }, __('Actions'));

            if (frm.fields_dict.items && frm.fields_dict.items.grid) {
                frm.fields_dict.items.grid.add_custom_button(__('Sort Items A-Z'), function() {
                    sort_items_alphabetically(frm);
                }, 'top');
            }
        }
    },
    onload_post_render: function(frm) {
        if (frm.fields_dict.remarks && frm.fields_dict.custom_goodwill_message && frm.fields_dict.custom_goodwill_message.$wrapper) {
            frm.fields_dict.remarks.$wrapper.insertAfter(frm.fields_dict.custom_goodwill_message.$wrapper);
            frm.set_df_property('remarks', 'hidden', 0);
            frm.fields_dict.remarks.$wrapper.show();
        }
    }
});

function sort_items_alphabetically(frm) {
    if (!frm.doc.items || frm.doc.items.length <= 1) {
        frappe.show_alert({
            message: __('Need at least 2 items to sort.'),
            indicator: 'orange'
        }, 3);
        return;
    }

    // Sort items alphabetically by item_name (fallback to item_code)
    frm.doc.items.sort((a, b) => {
        let nameA = (a.item_name || a.item_code || '').trim().toLowerCase();
        let nameB = (b.item_name || b.item_code || '').trim().toLowerCase();
        return nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' });
    });

    // Re-index rows (idx is 1-based in Frappe)
    frm.doc.items.forEach((row, idx) => {
        row.idx = idx + 1;
    });

    // Refresh grid display & mark dirty
    frm.refresh_field('items');
    frm.dirty();

    frappe.show_alert({
        message: __('Items sorted alphabetically (A-Z)'),
        indicator: 'green'
    }, 3);
}



frappe.ui.form.on('Sales Invoice Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code || row.is_free_item || row.__spa_applying || window.__spa_active_dialog) return;

        // Trigger pricing assistant after short delay
        clearTimeout(row.__spa_debounce_timer);
        row.__spa_debounce_timer = setTimeout(() => {
            if (row.__spa_applying || window.__spa_active_dialog) return;
            trigger_pricing_assistant(frm, cdt, cdn);
        }, 300);
    },

    batch_no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code || !row.batch_no || row.is_free_item || row.__spa_applying || window.__spa_active_dialog) return;

        // Batch-managed: trigger when batch is selected
        clearTimeout(row.__spa_debounce_timer);
        row.__spa_debounce_timer = setTimeout(() => {
            if (row.__spa_applying || window.__spa_active_dialog) return;
            trigger_pricing_assistant(frm, cdt, cdn);
        }, 300);
    },

    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code || row.is_free_item) return;

        if (row.__custom_rate_applied) {
            let custom_rate = flt(row.__custom_rate_applied);
            // Protect custom price from being overwritten by ERPNext's async apply_price_list
            setTimeout(() => {
                if (flt(row.rate) !== custom_rate && !row.__spa_applying) {
                    frappe.model.set_value(cdt, cdn, 'rate', custom_rate);
                    frappe.model.set_value(cdt, cdn, 'price_list_rate', custom_rate);
                    frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);
                }
            }, 400);
        }

        if (row.__spa_applying || window.__spa_active_dialog) return;

        if (flt(row.qty) > 0) {
            clearTimeout(row.__spa_debounce_timer);
            row.__spa_debounce_timer = setTimeout(() => {
                if (row.__spa_applying || window.__spa_active_dialog) return;
                trigger_pricing_assistant(frm, cdt, cdn);
            }, 300);
        }
    },

    rate: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row && flt(row.rate) > 0 && !row.is_free_item) {
            // Keep tracked rate in sync if manually typed in grid
            row.__custom_rate_applied = flt(row.rate);
        }
    },

    form_render: function(frm, cdt, cdn) {
        let row = locals[cdt]?.[cdn];
        if (!row) return;

        if (frm.fields_dict.items && frm.fields_dict.items.grid && frm.fields_dict.items.grid.open_grid_row) {
            let grid_row = frm.fields_dict.items.grid.open_grid_row;
            if (grid_row && !grid_row.__spa_btn_added) {
                grid_row.__spa_btn_added = true;
                let btn = $(`<button class="btn btn-xs btn-default" style="margin-top: 6px; margin-bottom: 6px;">
                    <i class="fa fa-tag text-primary"></i> ${__('Sales Pricing Assistant')}
                </button>`);
                btn.on('click', function(e) {
                    e.preventDefault();
                    trigger_pricing_assistant(frm, cdt, cdn);
                });
                grid_row.wrapper.find('.grid-row-header').append(btn);
            }
        }
    }
});

function trigger_pricing_assistant(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code || row.is_free_item || row.__spa_applying || window.__spa_active_dialog) return;

    if (!frm.doc.customer) {
        frappe.show_alert({
            message: __('Please select a Customer first to see historical pricing and margins.'),
            indicator: 'orange'
        }, 4);
        return;
    }

    // Call backend API
    frappe.call({
        method: 'sales_pricing_assistant.api.get_pricing_details',
        args: {
            customer: frm.doc.customer,
            item_code: row.item_code,
            batch_no: row.batch_no || null,
            company: frm.doc.company || null
        },
        freeze: false,
        callback: function(r) {
            if (r.message) {
                if (window.__spa_active_dialog) return;
                show_pricing_dialog(frm, cdt, cdn, r.message);
            }
        }
    });
}

function show_pricing_dialog(frm, cdt, cdn, data) {
    let row = locals[cdt][cdn];
    if (!row) return;

    window.__spa_active_dialog = true;
    let currency = frm.doc.currency || '₹';
    let batches = data.batches || [];
    
    // Determine active batch
    let current_batch = null;
    let active_batch_key = row.batch_no || row.custom_batch_id_all || data.batch_no;
    if (active_batch_key && batches.length > 0) {
        current_batch = batches.find(b => b.name === active_batch_key || b.batch_id === active_batch_key || b.custom_batch_id_all === active_batch_key);
    }
    if (!current_batch && batches.length > 0) {
        current_batch = batches.find(b => !b.is_expired && b.batch_qty > 0) || batches[0];
    }

    let current_rate = flt(row.rate) || flt(data.standard_rate) || 0.0;
    let min_price = current_batch ? flt(current_batch.minimum_selling_price) : (flt(data.minimum_selling_price) || 0.0);
    let purchase_rate = current_batch ? flt(current_batch.purchase_rate) : (flt(data.purchase_rate) || 0.0);
    let mrp = current_batch ? flt(current_batch.mrp) : (flt(data.mrp) || 0.0);

    // Initial Free and Billed Quantities from row (Single-Row Column Pattern)
    let initial_free_qty = flt(row.custom_free_qty) || 0;
    let is_free_initially_checked = initial_free_qty > 0;
    let current_qty = flt(row.custom_billed_qty) || flt(row.qty) || 1.0;
    if (current_qty <= 0) current_qty = 1.0;

    // Serial numbers
    let all_serials = data.serial_numbers || [];
    let has_serial_tracking = Boolean(data.has_serial_no || all_serials.length > 0);
    let initial_selected_serials = [];
    if (row.serial_no) {
        initial_selected_serials = (row.serial_no || '').split(/[\n,]/).map(s => s.trim()).filter(Boolean);
    }

    // Default price calculation
    let default_price = current_rate;
    if (!default_price || default_price === 0) {
        if (purchase_rate > 0) {
            default_price = Math.round(purchase_rate * 1.1 * 100) / 100;
        } else if (mrp > 0) {
            default_price = mrp;
        }
    }

    // Build batch dropdown options
    let batch_options = [];
    if (batches.length > 0) {
        batches.forEach(b => {
            let label = `${b.custom_batch_id_all || b.batch_id} — MRP: ${currency} ${format_currency(b.mrp, currency)} | Stock: ${b.batch_qty} ${data.stock_uom}${b.expiry_formatted ? ' | Exp: ' + b.expiry_formatted : ''}${b.is_expired ? ' (EXPIRED)' : ''}`;
            batch_options.push({
                label: label,
                value: b.name
            });
        });
    }

    let fields = [];

    // Batch Selector Dropdown (if batch tracking or batches exist)
    if (batches.length > 0) {
        fields.push({
            fieldname: 'section_batch_select',
            fieldtype: 'Section Break',
            label: __('Batch Selection')
        });
        fields.push({
            fieldname: 'selected_batch_no',
            label: __('Select Batch (Available in Stock)'),
            fieldtype: 'Select',
            options: batch_options,
            default: current_batch ? current_batch.name : (batch_options[0]?.value || ''),
            reqd: 1
        });
    }

    // Serial Number Section
    if (has_serial_tracking) {
        fields.push({
            fieldname: 'section_serial_select',
            fieldtype: 'Section Break',
            label: __('Serial Number Selection')
        });
        fields.push({
            fieldname: 'serial_selection_html',
            fieldtype: 'HTML'
        });
    }

    fields.push(
        {
            fieldname: 'info_html',
            fieldtype: 'HTML'
        },
        {
            fieldname: 'section_history',
            fieldtype: 'Section Break',
            label: __('Last 5 Occasions Prices (Customer: {0})', [frm.doc.customer])
        },
        {
            fieldname: 'history_html',
            fieldtype: 'HTML'
        },
        {
            fieldname: 'section_strategy',
            fieldtype: 'Section Break',
            label: __('Pricing Calculation & Options')
        },
        {
            fieldname: 'margin_type',
            label: __('Margin Type'),
            fieldtype: 'Select',
            options: ['Percentage (%)', 'Flat Amount (' + currency + ')'],
            default: 'Percentage (%)'
        },
        {
            fieldname: 'margin_value',
            label: __('Margin Value'),
            fieldtype: 'Float',
            default: 10.0,
            description: __('Calculate price from Purchase Rate')
        },
        {
            fieldname: 'margin_quick_buttons',
            fieldtype: 'HTML'
        },
        {
            fieldname: 'col_break_1',
            fieldtype: 'Column Break'
        },
        {
            fieldname: 'quantity',
            label: __('Billed Quantity ({0})', [data.stock_uom || 'Nos']),
            fieldtype: 'Float',
            default: current_qty,
            reqd: 1
        },
        {
            fieldname: 'final_price',
            label: __('Final Selling Price ({0})', [currency]),
            fieldtype: 'Currency',
            default: default_price,
            reqd: 1,
            description: min_price > 0 ? __('Minimum Selling Price floor: {0} {1}', [currency, format_currency(min_price, currency)]) : ''
        },
        {
            fieldname: 'override_min_price',
            label: __('Override Minimum Selling Price'),
            fieldtype: 'Check',
            default: 0,
            description: __('Check this box to permit setting price lower than Minimum Selling Price')
        },
        {
            fieldname: 'section_free_scheme',
            fieldtype: 'Section Break',
            label: __('Free Item / Scheme / Replacement (Single-Row Column Pattern)')
        },
        {
            fieldname: 'add_free_item',
            label: __('Add Free Item (Recorded in dedicated Free Qty column)'),
            fieldtype: 'Check',
            default: is_free_initially_checked ? 1 : 0
        },
        {
            fieldname: 'free_quantity',
            label: __('Free Quantity ({0})', [data.stock_uom || 'Nos']),
            fieldtype: 'Float',
            default: initial_free_qty || 1.0,
            depends_on: 'eval:doc.add_free_item == 1'
        },
        {
            fieldname: 'free_scheme_summary_html',
            fieldtype: 'HTML'
        },
        {
            fieldname: 'validation_msg_html',
            fieldtype: 'HTML'
        }
    );

    // Selected serials tracking state
    let selected_serials_set = new Set(initial_selected_serials);

    let dialog = new frappe.ui.Dialog({
        title: __('Pricing Assistant — {0}', [data.item_name || data.item_code]),
        size: 'large',
        fields: fields,
        primary_action_label: __('Apply Price (Enter)'),
        primary_action: function(values) {
            let selected_price = flt(dialog.get_value('final_price'));
            let selected_qty = flt(dialog.get_value('quantity')) || 1.0;
            let is_free_checked = Boolean(dialog.get_value('add_free_item'));
            let free_qty = is_free_checked ? flt(dialog.get_value('free_quantity')) : 0;
            let is_override = Boolean(
                dialog.get_value('override_min_price') || 
                dialog.fields_dict.override_min_price.$input.is(':checked')
            );

            if (min_price > 0 && selected_price < min_price && !is_override) {
                frappe.msgprint({
                    title: __('Price Below Minimum'),
                    indicator: 'red',
                    message: __('The selected price ({0} {1}) is below the Minimum Selling Price ({0} {2}).<br><br>Please check <strong>"Override Minimum Selling Price"</strong> to authorize this price.', [currency, format_currency(selected_price, currency), format_currency(min_price, currency)])
                });
                return;
            }

            if (is_free_checked && free_qty <= 0) {
                frappe.msgprint(__('Please specify a valid Free Quantity greater than 0.'));
                return;
            }

            let chosen_batch_name = dialog.fields_dict.selected_batch_no ? dialog.get_value('selected_batch_no') : (current_batch?.name || data.batch_no || row.batch_no);
            let b = (batches || []).find(item => item.name === chosen_batch_name) || current_batch;
            let chosen_clean_batch = b ? (b.custom_batch_id_all || b.batch_id) : (data.custom_batch_id_all || data.batch_id || chosen_batch_name);

            let selected_serials = Array.from(selected_serials_set);

            // If manual serial text entered and no pills selected
            if (has_serial_tracking && selected_serials.length === 0 && dialog.$wrapper.find('.spa-manual-serial-input').length) {
                let manual_txt = (dialog.$wrapper.find('.spa-manual-serial-input').val() || '').trim();
                if (manual_txt) {
                    selected_serials = manual_txt.split(/[\n,]/).map(s => s.trim()).filter(Boolean);
                }
            }

            // Mark applying state so programmatic child row updates do not trigger dialog recursively
            row.__spa_applying = true;
            row.__custom_rate_applied = selected_price;

            if (selected_serials.length > 0) {
                // Serialized workflow: Create/populate Y rows with Qty 1 and respective serial_no
                let Y = selected_serials.length;

                // 1. Update 1st Row (the active row in place)
                frappe.model.set_value(cdt, cdn, 'qty', 1);
                if (frappe.meta.has_field(cdt, 'custom_billed_qty')) {
                    frappe.model.set_value(cdt, cdn, 'custom_billed_qty', 1);
                }
                if (frappe.meta.has_field(cdt, 'custom_free_qty')) {
                    frappe.model.set_value(cdt, cdn, 'custom_free_qty', is_free_checked ? free_qty : 0);
                }
                frappe.model.set_value(cdt, cdn, 'rate', selected_price);
                frappe.model.set_value(cdt, cdn, 'price_list_rate', selected_price);
                frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);

                if (frappe.meta.has_field(cdt, 'serial_no')) {
                    frappe.model.set_value(cdt, cdn, 'serial_no', selected_serials[0]);
                }
                if (frappe.meta.has_field(cdt, 'use_serial_batch_fields')) {
                    frappe.model.set_value(cdt, cdn, 'use_serial_batch_fields', 1);
                }
                if (chosen_batch_name) {
                    frappe.model.set_value(cdt, cdn, 'batch_no', chosen_batch_name);
                }
                if (chosen_clean_batch && frappe.meta.has_field(cdt, 'custom_batch_id_all')) {
                    frappe.model.set_value(cdt, cdn, 'custom_batch_id_all', chosen_clean_batch);
                }
                if (mrp > 0 && frappe.meta.has_field(cdt, 'custom_mrp')) {
                    frappe.model.set_value(cdt, cdn, 'custom_mrp', mrp);
                }

                // 2. Add remaining (Y - 1) rows with identical price, batch, mrp, and next serial_no
                for (let i = 1; i < Y; i++) {
                    let sn = selected_serials[i];
                    let new_row = frm.add_child('items', {
                        item_code: row.item_code,
                        item_name: row.item_name || data.item_name,
                        description: row.description || '',
                        uom: row.uom || data.stock_uom,
                        stock_uom: row.stock_uom || data.stock_uom,
                        conversion_factor: row.conversion_factor || 1,
                        qty: 1,
                        custom_billed_qty: 1,
                        custom_free_qty: 0,
                        rate: selected_price,
                        price_list_rate: selected_price,
                        discount_percentage: 0,
                        serial_no: sn,
                        use_serial_batch_fields: 1,
                        batch_no: chosen_batch_name || row.batch_no || '',
                        custom_batch_id_all: chosen_clean_batch || row.custom_batch_id_all || '',
                        custom_mrp: mrp || row.custom_mrp || 0,
                        warehouse: row.warehouse || '',
                        income_account: row.income_account || '',
                        expense_account: row.expense_account || '',
                        cost_center: row.cost_center || ''
                    });
                    new_row.__custom_rate_applied = selected_price;
                    new_row.__spa_applying = true;
                }

                // 3. Clean up any companion free rows
                let companion_row = (frm.doc.items || []).find(r => r.is_free_item && (r.__spa_parent_cdn === cdn || (r.item_code === data.item_code && r.batch_no === chosen_batch_name)));
                if (companion_row) {
                    frappe.model.clear_doc(companion_row.doctype, companion_row.name);
                    frm.doc.items = (frm.doc.items || []).filter(r => r.name !== companion_row.name);
                }

                if (frm && frm.refresh_field) {
                    frm.refresh_field('items');
                }

                // Re-apply rates across created rows to protect against ERPNext async handlers
                setTimeout(() => {
                    (frm.doc.items || []).forEach(it => {
                        if (it.item_code === row.item_code && it.__custom_rate_applied) {
                            frappe.model.set_value(it.doctype, it.name, 'rate', it.__custom_rate_applied);
                            frappe.model.set_value(it.doctype, it.name, 'price_list_rate', it.__custom_rate_applied);
                            frappe.model.set_value(it.doctype, it.name, 'discount_percentage', 0);
                        }
                    });
                    frm.refresh_field('items');
                }, 300);

                let alert_msg = `Created ${Y} item rows for Serial Nos: ${selected_serials.join(', ')} — Price: ${currency} ${format_currency(selected_price, currency)} each`;
                frappe.show_alert({
                    message: __(alert_msg),
                    indicator: 'green'
                }, 4);

            } else {
                // Non-serialized or single quantity workflow
                frappe.model.set_value(cdt, cdn, 'qty', selected_qty);
                if (frappe.meta.has_field(cdt, 'custom_billed_qty')) {
                    frappe.model.set_value(cdt, cdn, 'custom_billed_qty', selected_qty);
                }
                if (frappe.meta.has_field(cdt, 'custom_free_qty')) {
                    frappe.model.set_value(cdt, cdn, 'custom_free_qty', is_free_checked ? free_qty : 0);
                }

                frappe.model.set_value(cdt, cdn, 'rate', selected_price);
                frappe.model.set_value(cdt, cdn, 'price_list_rate', selected_price);
                frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);

                if (chosen_batch_name) {
                    frappe.model.set_value(cdt, cdn, 'batch_no', chosen_batch_name);
                }
                if (chosen_clean_batch && frappe.meta.has_field(cdt, 'custom_batch_id_all')) {
                    frappe.model.set_value(cdt, cdn, 'custom_batch_id_all', chosen_clean_batch);
                }
                if (mrp > 0 && frappe.meta.has_field(cdt, 'custom_mrp')) {
                    frappe.model.set_value(cdt, cdn, 'custom_mrp', mrp);
                }

                let companion_row = (frm.doc.items || []).find(r => r.is_free_item && (r.__spa_parent_cdn === cdn || (r.item_code === data.item_code && r.batch_no === chosen_batch_name)));
                if (companion_row) {
                    frappe.model.clear_doc(companion_row.doctype, companion_row.name);
                    frm.doc.items = (frm.doc.items || []).filter(r => r.name !== companion_row.name);
                }

                if (frm && frm.refresh_field) {
                    frm.refresh_field('items');
                }

                setTimeout(() => {
                    frappe.model.set_value(cdt, cdn, 'rate', selected_price);
                    frappe.model.set_value(cdt, cdn, 'price_list_rate', selected_price);
                }, 300);

                let alert_text = `Applied Batch ${chosen_clean_batch || chosen_batch_name || ''} — Price: ${currency} ${format_currency(selected_price, currency)} (Billed: ${selected_qty})`;
                if (is_free_checked && free_qty > 0) {
                    alert_text += ` + ${free_qty} Free`;
                }

                frappe.show_alert({
                    message: __(alert_text),
                    indicator: 'green'
                }, 3);
            }

            window.__spa_active_dialog = false;
            dialog.hide();
            setTimeout(() => {
                row.__spa_applying = false;
                (frm.doc.items || []).forEach(it => {
                    it.__spa_applying = false;
                });
            }, 600);

            // Keyboard Navigation: Focus current row's rate column
            setTimeout(() => {
                let grid = frm.fields_dict.items?.grid;
                if (grid && row) {
                    let grid_row = grid.grid_rows_by_docname[row.name];
                    if (grid_row) {
                        if (typeof grid_row.toggle_editable_row === 'function') {
                            grid_row.toggle_editable_row(true);
                        }
                        let $row_wrapper = grid.wrapper.find(`.grid-row[data-name="${row.name}"]`);
                        if ($row_wrapper.length) {
                            let $target = $row_wrapper.find('input[data-fieldname="rate"], input[data-fieldname="custom_mrp"]').first();
                            if (!$target.length) {
                                $target = $row_wrapper.find('input:visible:enabled').last();
                            }
                            if ($target.length) {
                                $target.focus().select();
                            }
                        }
                    }
                }
            }, 120);
        },
        secondary_action_label: __('Cancel / Ignore (Esc)'),
        secondary_action: function() {
            window.__spa_active_dialog = false;
            if (row) {
                row.__spa_applying = false;
            }
            dialog.hide();
        }
    });

    dialog.on_hide = function() {
        window.__spa_active_dialog = false;
        if (row) {
            setTimeout(() => {
                row.__spa_applying = false;
            }, 300);
        }
    };

    // Serial Number Selector Renderer
    function render_serial_selector() {
        if (!has_serial_tracking || !dialog.fields_dict.serial_selection_html) return;

        let $wrapper = dialog.fields_dict.serial_selection_html.$wrapper;
        let serials_list = data.serial_numbers || [];
        let current_target_qty = flt(dialog.get_value('quantity')) || 1.0;
        let selected_count = selected_serials_set.size;

        if (serials_list.length > 0) {
            let chips_html = serials_list.map(sn => {
                let is_selected = selected_serials_set.has(sn);
                return `
                    <div class="spa-serial-chip ${is_selected ? 'selected' : ''}" data-serial="${frappe.utils.escape_html(sn)}" style="
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        padding: 6px 12px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        user-select: none;
                        transition: all 0.15s ease-in-out;
                        border: 1.5px solid ${is_selected ? '#0284c7' : '#cbd5e1'};
                        background: ${is_selected ? '#e0f2fe' : '#ffffff'};
                        color: ${is_selected ? '#0369a1' : '#475569'};
                        box-shadow: ${is_selected ? '0 1px 3px rgba(2,132,199,0.2)' : 'none'};
                    ">
                        <span style="font-size: 13px; font-weight: bold;">${is_selected ? '✓' : '+'}</span>
                        <span>${frappe.utils.escape_html(sn)}</span>
                    </div>
                `;
            }).join('');

            let html = `
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 12px; font-weight: 700; color: #334155;">Available Serials (${serials_list.length})</span>
                            <span class="badge" style="background: ${selected_count > 0 ? '#0284c7' : '#94a3b8'}; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 12px;">
                                Selected: ${selected_count}
                            </span>
                        </div>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <input type="text" class="form-control input-xs spa-serial-search" placeholder="Filter serials..." style="width: 140px; height: 26px; font-size: 11px; border-radius: 4px;">
                            <button type="button" class="btn btn-xs btn-default btn-autoselect-serials" style="font-size: 11px; height: 26px;">
                                <i class="fa fa-check-circle text-primary"></i> Auto-select First ${current_target_qty > 0 ? Math.round(current_target_qty) : 1}
                            </button>
                            <button type="button" class="btn btn-xs btn-default btn-clear-serials" style="font-size: 11px; height: 26px;">
                                Clear
                            </button>
                        </div>
                    </div>

                    <div class="spa-serials-container" style="display: flex; flex-wrap: wrap; gap: 8px; max-height: 140px; overflow-y: auto; padding: 4px 0;">
                        ${chips_html}
                    </div>

                    <div style="margin-top: 8px; font-size: 11px; color: ${selected_count > 0 ? '#059669' : '#64748b'}; font-weight: 500;">
                        ${selected_count > 0 ? `✓ ${selected_count} serial number(s) selected. Applying will create ${selected_count} row(s) in invoice with Qty 1 each.` : 'ℹ️ Click serial numbers to select. Selecting Y serials will automatically set quantity to Y and create Y invoice rows.'}
                    </div>
                </div>
            `;
            $wrapper.html(html);

            // Bind Chip Clicks
            $wrapper.find('.spa-serial-chip').on('click', function(e) {
                e.preventDefault();
                let sn = $(this).data('serial');
                if (selected_serials_set.has(sn)) {
                    selected_serials_set.delete(sn);
                } else {
                    selected_serials_set.add(sn);
                }
                if (selected_serials_set.size > 0) {
                    dialog.set_value('quantity', selected_serials_set.size);
                }
                render_serial_selector();
                update_validation_status();
            });

            // Bind Search Input
            $wrapper.find('.spa-serial-search').on('input', function() {
                let q = $(this).val().toLowerCase().trim();
                $wrapper.find('.spa-serial-chip').each(function() {
                    let sn = String($(this).data('serial')).toLowerCase();
                    $(this).toggle(sn.includes(q));
                });
            });

            // Bind Auto-select
            $wrapper.find('.btn-autoselect-serials').on('click', function(e) {
                e.preventDefault();
                let target_qty = Math.round(flt(dialog.get_value('quantity'))) || 1;
                selected_serials_set.clear();
                let visible_chips = $wrapper.find('.spa-serial-chip:visible');
                for (let i = 0; i < Math.min(target_qty, visible_chips.length); i++) {
                    selected_serials_set.add($(visible_chips[i]).data('serial'));
                }
                dialog.set_value('quantity', selected_serials_set.size || target_qty);
                render_serial_selector();
                update_validation_status();
            });

            // Bind Clear
            $wrapper.find('.btn-clear-serials').on('click', function(e) {
                e.preventDefault();
                selected_serials_set.clear();
                render_serial_selector();
                update_validation_status();
            });

        } else {
            // Manual entry when no serials exist in database yet
            let manual_val = Array.from(selected_serials_set).join(', ');
            let html = `
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                    <div style="font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 6px;">Enter Serial Numbers (Comma or newline separated):</div>
                    <textarea class="form-control spa-manual-serial-input" rows="2" placeholder="e.g. SN-001, SN-002, SN-003" style="font-size: 12px;">${frappe.utils.escape_html(manual_val)}</textarea>
                    <div style="margin-top: 6px; font-size: 11px; color: #64748b;">
                        Entering Y serial numbers will create Y separate rows with Qty 1 each in the invoice.
                    </div>
                </div>
            `;
            $wrapper.html(html);

            $wrapper.find('.spa-manual-serial-input').on('input', function() {
                let txt = $(this).val().trim();
                let serials = txt ? txt.split(/[\n,]/).map(s => s.trim()).filter(Boolean) : [];
                selected_serials_set = new Set(serials);
                if (serials.length > 0) {
                    dialog.set_value('quantity', serials.length);
                }
                update_validation_status();
            });
        }
    }

    // Dynamic Metric Summary Cards Updater
    function update_metric_cards() {
        let clean_batch_display = current_batch ? (current_batch.custom_batch_id_all || current_batch.batch_id || current_batch.name) : (data.custom_batch_id_all || data.batch_id || data.batch_no || 'None');
        let batch_exp = current_batch ? (current_batch.expiry_formatted || current_batch.expiry_date) : data.batch_expiry;
        let batch_stock = current_batch ? `${current_batch.batch_qty} ${data.stock_uom || 'Nos'}` : '';

        let metric_cards_html = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 12px;">
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; text-align: center;">
                    <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Selected Batch</div>
                    <div style="font-size: 16px; font-weight: 700; color: #1e293b; margin-top: 4px;">${frappe.utils.escape_html(clean_batch_display)}</div>
                    ${batch_exp ? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">Exp: ${frappe.utils.escape_html(batch_exp)}</div>` : ''}
                    ${batch_stock ? `<div style="font-size: 11px; color: #0284c7; font-weight: 600; margin-top: 2px;">Avail Stock: ${frappe.utils.escape_html(batch_stock)}</div>` : ''}
                </div>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 14px; text-align: center;">
                    <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #166534; letter-spacing: 0.5px;">Batch MRP</div>
                    <div style="font-size: 16px; font-weight: 700; color: #15803d; margin-top: 4px;">${currency} ${format_currency(mrp, currency)}</div>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 14px; text-align: center;">
                    <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #1e40af; letter-spacing: 0.5px;">Purchase Price</div>
                    <div style="font-size: 16px; font-weight: 700; color: #2563eb; margin-top: 4px;">${currency} ${format_currency(purchase_rate, currency)}</div>
                    ${(current_batch?.purchase_voucher || data.purchase_voucher) ? `<div style="font-size: 10px; color: #3b82f6; margin-top: 2px;">${frappe.utils.escape_html(current_batch?.purchase_voucher || data.purchase_voucher)}</div>` : ''}
                </div>

                <div style="background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 10px 14px; text-align: center;">
                    <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #9a3412; letter-spacing: 0.5px;">Min Selling Price</div>
                    <div style="font-size: 16px; font-weight: 700; color: #ea580c; margin-top: 4px;">${currency} ${format_currency(min_price, currency)}</div>
                </div>
            </div>
        `;
        dialog.fields_dict.info_html.$wrapper.html(metric_cards_html);
    }

    update_metric_cards();

    // History Table
    let history_table_html = '';
    if (data.history && data.history.length > 0) {
        history_table_html = `
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 12px;">
                <table class="table table-bordered table-hover" style="margin-bottom: 0; font-size: 12px;">
                    <thead style="background: #f8fafc;">
                        <tr>
                            <th style="padding: 8px 10px; width: 40px;">#</th>
                            <th style="padding: 8px 10px;">Invoice No</th>
                            <th style="padding: 8px 10px;">Date</th>
                            <th style="padding: 8px 10px;">Batch</th>
                            <th style="padding: 8px 10px; text-align: right;">Qty</th>
                            <th style="padding: 8px 10px; text-align: right;">Sold Price</th>
                            <th style="padding: 8px 10px; text-align: center; width: 95px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.history.forEach((h, index) => {
            let hist_batch_clean = h.custom_batch_id_all || h.batch_no || '-';
            history_table_html += `
                <tr>
                    <td style="padding: 7px 10px; font-weight: 600; color: #64748b;">${index + 1}</td>
                    <td style="padding: 7px 10px;"><a href="/app/sales-invoice/${frappe.utils.escape_html(h.voucher_no)}" target="_blank" style="font-weight: 500;">${frappe.utils.escape_html(h.voucher_no)}</a></td>
                    <td style="padding: 7px 10px; color: #475569;">${frappe.datetime.str_to_user(h.posting_date)}</td>
                    <td style="padding: 7px 10px; color: #475569;">${frappe.utils.escape_html(hist_batch_clean)}</td>
                    <td style="padding: 7px 10px; text-align: right; color: #475569;">${format_number(h.qty)} ${frappe.utils.escape_html(h.uom || '')}</td>
                    <td style="padding: 7px 10px; text-align: right; font-weight: 700; color: #0f172a;">${currency} ${format_currency(h.rate, currency)}</td>
                    <td style="padding: 5px 10px; text-align: center;">
                        <button type="button" class="btn btn-xs btn-primary btn-pick-price" data-price="${flt(h.rate)}" style="font-size: 11px; padding: 2px 8px;">
                            Use Price
                        </button>
                    </td>
                </tr>
            `;
        });

        history_table_html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        history_table_html = `
            <div style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 14px; text-align: center; color: #64748b; font-size: 13px; margin-bottom: 12px;">
                No prior sales history found for this customer and product.
            </div>
        `;
    }
    dialog.fields_dict.history_html.$wrapper.html(history_table_html);

    // Quick Margin Presets
    let quick_presets_html = `
        <div style="display: flex; gap: 6px; align-items: center; margin-top: 6px; flex-wrap: wrap;">
            <span style="font-size: 11px; color: #64748b; font-weight: 500;">Quick Margin:</span>
            <button type="button" class="btn btn-xs btn-default btn-margin-preset" data-margin="5">5%</button>
            <button type="button" class="btn btn-xs btn-default btn-margin-preset" data-margin="10">10%</button>
            <button type="button" class="btn btn-xs btn-default btn-margin-preset" data-margin="15">15%</button>
            <button type="button" class="btn btn-xs btn-default btn-margin-preset" data-margin="20">20%</button>
            <button type="button" class="btn btn-xs btn-default btn-margin-preset" data-margin="25">25%</button>
        </div>
    `;
    dialog.fields_dict.margin_quick_buttons.$wrapper.html(quick_presets_html);

    // Pick Price Click handler
    dialog.fields_dict.history_html.$wrapper.find('.btn-pick-price').on('click', function(e) {
        e.preventDefault();
        let picked_price = flt($(this).data('price'));
        dialog.set_value('final_price', picked_price);
        update_validation_status();
    });

    // Preset Margin Click handler
    dialog.fields_dict.margin_quick_buttons.$wrapper.find('.btn-margin-preset').on('click', function(e) {
        e.preventDefault();
        let m = flt($(this).data('margin'));
        dialog.set_value('margin_type', 'Percentage (%)');
        dialog.set_value('margin_value', m);
        calculate_margin_price();
    });

    // Calculate Price from Margin
    function calculate_margin_price() {
        let m_type = dialog.get_value('margin_type');
        let m_val = flt(dialog.get_value('margin_value'));
        let calc_price = 0.0;

        if (purchase_rate > 0) {
            if (m_type.includes('Percentage')) {
                calc_price = purchase_rate * (1 + (m_val / 100));
            } else {
                calc_price = purchase_rate + m_val;
            }
            calc_price = Math.round(calc_price * 100) / 100;
            dialog.set_value('final_price', calc_price);
        }
        update_validation_status();
    }

    // Helper to get apply button reliably
    function get_apply_btn() {
        return dialog.$wrapper.find('.modal-footer button').filter(function() {
            return $(this).text().trim().includes('Apply Price') || $(this).hasClass('btn-primary');
        });
    }

    // Free Scheme Summary Updater (Single-Row Column Pattern)
    function update_free_scheme_summary() {
        let is_free_checked = Boolean(dialog.get_value('add_free_item'));
        let $wrapper = dialog.fields_dict.free_scheme_summary_html.$wrapper;
        if (!is_free_checked) {
            $wrapper.html('');
            return;
        }

        let billed_qty = flt(dialog.get_value('quantity')) || 1.0;
        let free_qty = flt(dialog.get_value('free_quantity')) || 0;
        let price = flt(dialog.get_value('final_price')) || 0;
        let total_deducted = billed_qty + free_qty;
        let total_billed_amount = billed_qty * price;

        $wrapper.html(`
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px 12px; margin-top: 10px; font-size: 12px; color: #166534; line-height: 1.4;">
                <strong>Free Scheme Breakdown (Single-Row Column Pattern):</strong><br>
                • Customer Billed: <strong>${billed_qty} ${data.stock_uom || 'Nos'}</strong> @ ${currency} ${format_currency(price, currency)} = <strong>${currency} ${format_currency(total_billed_amount, currency)}</strong><br>
                • Free Quantity Column: <strong>+${free_qty} Free</strong> (Tracked in Free Qty column, standard rate & financials preserved)<br>
                • <strong>Total Warehouse Stock Deducted: ${total_deducted} units</strong>
            </div>
        `);
    }

    // Validation Status Updater
    function update_validation_status() {
        let current_final_price = flt(dialog.get_value('final_price'));
        let is_override = Boolean(
            dialog.get_value('override_min_price') || 
            dialog.fields_dict.override_min_price.$input.is(':checked')
        );
        let $msg_wrapper = dialog.fields_dict.validation_msg_html.$wrapper;
        let $override_field = dialog.fields_dict.override_min_price.$wrapper;
        let $btn = get_apply_btn();

        if (min_price > 0 && current_final_price < min_price) {
            $override_field.show();
            if (!is_override) {
                $msg_wrapper.html(`
                    <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px 12px; margin-top: 10px; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 15px;">⚠️</span>
                        <div style="font-size: 12px; color: #991b1b; font-weight: 500;">
                            Price (${currency} ${format_currency(current_final_price, currency)}) is below Minimum Selling Price (${currency} ${format_currency(min_price, currency)}). Check <strong>Override Minimum Selling Price</strong> below to apply.
                        </div>
                    </div>
                `);
                $btn.prop('disabled', true).css({'opacity': '0.5', 'cursor': 'not-allowed'});
            } else {
                $msg_wrapper.html(`
                    <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 8px 12px; margin-top: 10px; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 15px;">ℹ️</span>
                        <div style="font-size: 12px; color: #92400e; font-weight: 500;">
                            Minimum Selling Price override active. Price can now be applied.
                        </div>
                    </div>
                `);
                $btn.prop('disabled', false).css({'opacity': '1', 'cursor': 'pointer'});
            }
        } else {
            $msg_wrapper.html('');
            $override_field.hide();
            $btn.prop('disabled', false).css({'opacity': '1', 'cursor': 'pointer'});
        }

        update_free_scheme_summary();
    }

    // Dynamic Batch Selection change listener
    if (dialog.fields_dict.selected_batch_no) {
        dialog.fields_dict.selected_batch_no.$input.on('change', function() {
            let chosen_name = dialog.get_value('selected_batch_no');
            let b = (batches || []).find(item => item.name === chosen_name);
            if (b) {
                current_batch = b;
                purchase_rate = flt(b.purchase_rate) || flt(data.standard_rate) || 0.0;
                mrp = flt(b.mrp) || 0.0;
                min_price = flt(b.minimum_selling_price) || flt(data.minimum_selling_price) || 0.0;
                update_metric_cards();
                calculate_margin_price();
                update_validation_status();
            }
        });
    }

    // Bind inputs
    dialog.fields_dict.margin_type.$input.on('change', calculate_margin_price);
    dialog.fields_dict.margin_value.$input.on('input change', calculate_margin_price);
    dialog.fields_dict.final_price.$input.on('input change', update_validation_status);
    dialog.fields_dict.quantity.$input.on('input change', function() {
        update_validation_status();
        render_serial_selector();
    });
    dialog.fields_dict.add_free_item.$input.on('change click', update_validation_status);
    dialog.fields_dict.free_quantity.$input.on('input change', update_validation_status);
    dialog.fields_dict.override_min_price.$input.on('change click input', function() {
        setTimeout(update_validation_status, 50);
    });

    // Support keyboard Enter key to submit dialog
    dialog.$wrapper.find('input').on('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            dialog.get_primary_btn().trigger('click');
        }
    });

    dialog.show();
    render_serial_selector();
    setTimeout(update_validation_status, 100);
}
