// Copyright (c) 2026, QL and contributors
// For license information, please see license.txt

frappe.ui.form.on('Transport Calculator', {
	refresh: function(frm) {
		// Custom button on header as well for easy access
		frm.add_custom_button(__('Calculate Optimization'), function() {
			frm.trigger('calculate_optimization');
		}).addClass('btn-primary');
	},

	calculate_optimization: function(frm) {
		if (!frm.doc.destination) {
			frappe.msgprint(__('Please select a Destination first.'));
			return;
		}
		if (!frm.doc.package_count || frm.doc.package_count <= 0) {
			frappe.msgprint(__('Please enter a valid Package Count (greater than 0).'));
			return;
		}

		frappe.call({
			method: 'ql.tools.fleet_optimizer.calculate_logistics_optimization',
			args: {
				destination: frm.doc.destination,
				package_count: frm.doc.package_count,
				unit_count_in_package: frm.doc.unit_count_in_package || 1
			},
			freeze: true,
			freeze_message: __('Calculating optimal fleet allocation...'),
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.clear_table('results');
					r.message.forEach(function(item) {
						let row = frm.add_child('results');
						row.vendor = item.vendor;
						row.fleet_mix = item.fleet_mix;
						row.intercity_total_cost = item.intercity_total_cost;
						row.intercity_cost_per_unit = item.intercity_cost_per_unit;
						row.remaining_package_capacity = item.remaining_package_capacity;
						row.total_capacity = item.total_capacity;
						row.is_recommended = item.is_recommended;
					});
					frm.refresh_field('results');

					// Set recommended fields
					let best = r.message[0];
					frm.set_value('best_vendor', best.vendor);
					frm.set_value('best_fleet_mix', best.fleet_mix);
					frm.set_value('best_total_cost', best.intercity_total_cost);
					frm.set_value('best_cost_per_unit', best.intercity_cost_per_unit);

					frappe.show_alert({
						message: __('Optimization complete! Best vendor: {0} ({1})', [best.vendor, format_currency(best.intercity_total_cost)]),
						indicator: 'green'
					});
				} else {
					frappe.msgprint(__('No available fleet combination found for this destination.'));
				}
			}
		});
	}
});
