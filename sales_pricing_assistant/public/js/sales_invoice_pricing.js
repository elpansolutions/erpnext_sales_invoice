frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Setup
    },
    refresh: function(frm) {
        // Ensure manual ewaybill field is always editable
        frm.set_df_property('ewaybill', 'read_only', 0);
        frm.set_df_property('ewaybill', 'hidden', 0);
        frm.set_df_property('ewaybill', 'reqd', 0);
    },
    custom_remarks: function(frm) {
        if (frm.doc.custom_remarks && (!frm.doc.remarks || frm.doc.remarks === 'No Remarks')) {
            frm.set_value('remarks', frm.doc.custom_remarks);
        }
    }
});


frappe.ui.form.on('Sales Invoice Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code || row.is_free_item || row.__spa_applying || window.__spa_active_dialog) return;

        // Check if item has batch tracking
        frappe.db.get_value('Item', row.item_code, 'has_batch_no', (r) => {
            if (r && !r.has_batch_no) {
                // Not batch-managed: trigger pricing assistant after short delay
                clearTimeout(row.__spa_debounce_timer);
                row.__spa_debounce_timer = setTimeout(() => {
                    if (row.__spa_applying || window.__spa_active_dialog) return;
                    trigger_pricing_assistant(frm, cdt, cdn);
                }, 300);
            }
        });
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

            // Mark applying state so programmatic child row updates do not trigger dialog recursively
            row.__spa_applying = true;
            row.__custom_rate_applied = selected_price;

            // 1. Set Quantity and dedicated Free Qty column (Single-Row Pattern like Purchase Invoice)
            frappe.model.set_value(cdt, cdn, 'qty', selected_qty);
            if (frappe.meta.has_field(cdt, 'custom_billed_qty')) {
                frappe.model.set_value(cdt, cdn, 'custom_billed_qty', selected_qty);
            }
            if (frappe.meta.has_field(cdt, 'custom_free_qty')) {
                frappe.model.set_value(cdt, cdn, 'custom_free_qty', is_free_checked ? free_qty : 0);
            }

            // 2. Set Rates
            frappe.model.set_value(cdt, cdn, 'rate', selected_price);
            frappe.model.set_value(cdt, cdn, 'price_list_rate', selected_price);
            frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);

            // 3. Set Batch and MRP
            if (chosen_batch_name) {
                frappe.model.set_value(cdt, cdn, 'batch_no', chosen_batch_name);
            }
            if (chosen_clean_batch && frappe.meta.has_field(cdt, 'custom_batch_id_all')) {
                frappe.model.set_value(cdt, cdn, 'custom_batch_id_all', chosen_clean_batch);
            }
            if (mrp > 0 && frappe.meta.has_field(cdt, 'custom_mrp')) {
                frappe.model.set_value(cdt, cdn, 'custom_mrp', mrp);
            }

            // 4. Clean up any legacy companion free item lines
            let companion_row = (frm.doc.items || []).find(r => r.is_free_item && (r.__spa_parent_cdn === cdn || (r.item_code === data.item_code && r.batch_no === chosen_batch_name)));
            if (companion_row) {
                frappe.model.clear_doc(companion_row.doctype, companion_row.name);
                frm.doc.items = (frm.doc.items || []).filter(r => r.name !== companion_row.name);
            }

            if (frm && frm.refresh_field) {
                frm.refresh_field('items');
            }

            // Ensure rate persists after ERPNext's background price calculations
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

            window.__spa_active_dialog = false;
            dialog.hide();
            setTimeout(() => {
                row.__spa_applying = false;
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
    dialog.fields_dict.quantity.$input.on('input change', update_validation_status);
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
    setTimeout(update_validation_status, 100);
}
