frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Setup hooks
    }
});

frappe.ui.form.on('Sales Invoice Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code) return;

        // Check if item has batch tracking
        frappe.db.get_value('Item', row.item_code, 'has_batch_no', (r) => {
            if (r && !r.has_batch_no) {
                // Not batch-managed: trigger pricing assistant after a short delay so ERPNext finishes fetching standard item details
                setTimeout(() => {
                    trigger_pricing_assistant(frm, cdt, cdn);
                }, 600);
            }
        });
    },

    batch_no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code || !row.batch_no) return;

        // Batch-managed: trigger when batch is selected
        setTimeout(() => {
            trigger_pricing_assistant(frm, cdt, cdn);
        }, 500);
    }
});

function trigger_pricing_assistant(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code) return;

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
                show_pricing_dialog(frm, cdt, cdn, r.message);
            }
        }
    });
}

function show_pricing_dialog(frm, cdt, cdn, data) {
    let row = locals[cdt][cdn];
    let currency = frm.doc.currency || '₹';
    let current_rate = flt(row.rate) || flt(data.standard_rate) || 0.0;
    let min_price = flt(data.minimum_selling_price) || 0.0;
    let purchase_rate = flt(data.purchase_rate) || 0.0;
    let mrp = flt(data.mrp) || 0.0;

    // Default price recommendation:
    let default_price = current_rate;
    if (!default_price || default_price === 0) {
        if (purchase_rate > 0) {
            default_price = Math.round(purchase_rate * 1.1 * 100) / 100;
        } else if (mrp > 0) {
            default_price = mrp;
        }
    }

    let dialog = new frappe.ui.Dialog({
        title: __('Pricing Assistant — {0}', [data.item_name || data.item_code]),
        size: 'large',
        fields: [
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
                description: __('Calculate price from Purchase Invoice Rate')
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
                fieldname: 'final_price',
                label: __('Final Selling Price (' + currency + ')'),
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
                fieldname: 'validation_msg_html',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: __('Apply Price'),
        primary_action: function(values) {
            let selected_price = flt(values.final_price);
            let override = values.override_min_price;

            if (min_price > 0 && selected_price < min_price && !override) {
                frappe.msgprint({
                    title: __('Price Below Minimum'),
                    indicator: 'red',
                    message: __('The selected price ({0} {1}) is below the Minimum Selling Price ({0} {2}).<br><br>Please check <strong>"Override Minimum Selling Price"</strong> to authorize this price.', [currency, format_currency(selected_price, currency), format_currency(min_price, currency)])
                });
                return;
            }

            // Apply to row
            frappe.model.set_value(cdt, cdn, 'rate', selected_price);
            frappe.model.set_value(cdt, cdn, 'price_list_rate', selected_price);
            if (mrp > 0 && frappe.meta.has_field(cdt, 'custom_mrp')) {
                frappe.model.set_value(cdt, cdn, 'custom_mrp', mrp);
            }
            
            frappe.show_alert({
                message: __('Applied Price: {0} {1} for Item {2}', [currency, format_currency(selected_price, currency), data.item_code]),
                indicator: 'green'
            }, 3);

            dialog.hide();
        },
        secondary_action_label: __('Cancel / Ignore (Esc)'),
        secondary_action: function() {
            dialog.hide();
        }
    });

    // Metric Summary Cards
    let metric_cards_html = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 12px;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; text-align: center;">
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Selected Batch</div>
                <div style="font-size: 15px; font-weight: 700; color: #1e293b; margin-top: 4px;">${frappe.utils.escape_html(data.batch_no || 'None')}</div>
                ${data.batch_expiry ? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">Exp: ${frappe.utils.escape_html(data.batch_expiry)}</div>` : ''}
            </div>

            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 14px; text-align: center;">
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #166534; letter-spacing: 0.5px;">Batch MRP</div>
                <div style="font-size: 16px; font-weight: 700; color: #15803d; margin-top: 4px;">${currency} ${format_currency(mrp, currency)}</div>
            </div>

            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 14px; text-align: center;">
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #1e40af; letter-spacing: 0.5px;">Purchase Price</div>
                <div style="font-size: 16px; font-weight: 700; color: #2563eb; margin-top: 4px;">${currency} ${format_currency(purchase_rate, currency)}</div>
                ${data.purchase_voucher ? `<div style="font-size: 10px; color: #3b82f6; margin-top: 2px;">${frappe.utils.escape_html(data.purchase_voucher)}</div>` : ''}
            </div>

            <div style="background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 10px 14px; text-align: center;">
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #9a3412; letter-spacing: 0.5px;">Min Selling Price</div>
                <div style="font-size: 16px; font-weight: 700; color: #ea580c; margin-top: 4px;">${currency} ${format_currency(min_price, currency)}</div>
            </div>
        </div>
    `;
    dialog.fields_dict.info_html.$wrapper.html(metric_cards_html);

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
            history_table_html += `
                <tr>
                    <td style="padding: 7px 10px; font-weight: 600; color: #64748b;">${index + 1}</td>
                    <td style="padding: 7px 10px;"><a href="/app/sales-invoice/${frappe.utils.escape_html(h.voucher_no)}" target="_blank" style="font-weight: 500;">${frappe.utils.escape_html(h.voucher_no)}</a></td>
                    <td style="padding: 7px 10px; color: #475569;">${frappe.datetime.str_to_user(h.posting_date)}</td>
                    <td style="padding: 7px 10px; color: #475569;">${frappe.utils.escape_html(h.batch_no || '-')}</td>
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

    // Validation Status Updater
    function update_validation_status() {
        let current_final_price = flt(dialog.get_value('final_price'));
        let is_override = dialog.get_value('override_min_price');
        let $msg_wrapper = dialog.fields_dict.validation_msg_html.$wrapper;
        let $override_field = dialog.fields_dict.override_min_price.$wrapper;

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
                dialog.get_primary_btn().prop('disabled', true).addClass('btn-secondary').removeClass('btn-primary');
            } else {
                $msg_wrapper.html(`
                    <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 8px 12px; margin-top: 10px; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 15px;">ℹ️</span>
                        <div style="font-size: 12px; color: #92400e; font-weight: 500;">
                            Minimum Selling Price override active. Price can now be applied.
                        </div>
                    </div>
                `);
                dialog.get_primary_btn().prop('disabled', false).addClass('btn-primary').removeClass('btn-secondary');
            }
        } else {
            $msg_wrapper.html('');
            $override_field.hide();
            dialog.get_primary_btn().prop('disabled', false).addClass('btn-primary').removeClass('btn-secondary');
        }
    }

    // Bind inputs
    dialog.fields_dict.margin_type.$input.on('change', calculate_margin_price);
    dialog.fields_dict.margin_value.$input.on('input change', calculate_margin_price);
    dialog.fields_dict.final_price.$input.on('input change', update_validation_status);
    dialog.fields_dict.override_min_price.$input.on('change', update_validation_status);

    dialog.show();
    update_validation_status();
}
