// Copyright (c) 2026, QL and contributors
// For license information, please see license.txt

frappe.ui.form.on('Secondary Distribution', {
	refresh: function(frm) {
		frm.add_custom_button(__('Calculate Within-City Optimization'), function() {
			frm.trigger('calculate_within_city_optimization');
		}).addClass('btn-primary');
	},

	primary_distribution: function(frm) {
		if (frm.doc.primary_distribution) {
			frappe.db.get_doc('Primary Distribution', frm.doc.primary_distribution)
				.then(function(pd) {
					frm.set_value('destination', pd.destination);
					frm.set_value('intercity_cost', pd.best_total_cost);
					frm.set_value('intercity_vendor', pd.best_vendor);
					frm.set_value('intercity_fleet_mix', pd.best_fleet_mix);
					if (!frm.doc.package_count) {
						frm.set_value('package_count', pd.package_count);
					}
					if (!frm.doc.unit_count_in_package) {
						frm.set_value('unit_count_in_package', pd.unit_count_in_package || 1);
					}
					frm.set_value('distributor_warehouse', pd.destination + ' Distribution Center');
					frm.trigger('calculate_total_cost');

					if (frm.doc.outlet && frm.doc.package_count) {
						frm.trigger('calculate_within_city_optimization');
					}
				});
		}
	},

	handling_and_labor_cost: function(frm) {
		frm.trigger('calculate_total_cost');
	},

	within_city_transport_cost: function(frm) {
		frm.trigger('calculate_total_cost');
	},

	distance_km: function(frm) {
		if (frm.doc.package_count && frm.doc.package_count > 0) {
			frm.trigger('calculate_within_city_optimization');
		}
	},

	package_count: function(frm) {
		if (frm.doc.package_count && frm.doc.package_count > 0) {
			frm.trigger('calculate_within_city_optimization');
		}
	},

	calculate_total_cost: function(frm) {
		let intercity = flt(frm.doc.intercity_cost);
		let handling = flt(frm.doc.handling_and_labor_cost);
		let within_city = flt(frm.doc.within_city_transport_cost);

		let total = intercity + handling + within_city;
		frm.set_value('total_cost', total);

		let total_units = (cint(frm.doc.package_count) || 1) * (cint(frm.doc.unit_count_in_package) || 1);
		if (total_units > 0) {
			frm.set_value('total_cost_per_unit', Math.round((total / total_units) * 100) / 100);
		}
	},

	calculate_within_city_optimization: function(frm) {
		if (!frm.doc.primary_distribution) {
			frappe.msgprint(__('Please select a Primary Distribution record first.'));
			return;
		}
		if (!frm.doc.package_count || frm.doc.package_count <= 0) {
			frappe.msgprint(__('Package Count must be greater than 0.'));
			return;
		}

		frappe.call({
			method: 'ql.tools.fleet_optimizer.calculate_within_city_optimization',
			args: {
				package_count: frm.doc.package_count,
				distance_km: frm.doc.distance_km || 15,
				unit_count_in_package: frm.doc.unit_count_in_package || 1
			},
			freeze: true,
			freeze_message: __('Optimizing within-the-city delivery fleet...'),
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.clear_table('within_city_optimization_results');
					r.message.forEach(function(item) {
						let row = frm.add_child('within_city_optimization_results');
						row.vehicle_mode = item.vehicle_mode;
						row.fleet_mix = item.fleet_mix;
						row.cost = item.cost;
						row.cost_per_unit = item.cost_per_unit;
						row.capacity = item.capacity;
						row.remaining_capacity = item.remaining_capacity;
						row.is_recommended = item.is_recommended;
					});
					frm.refresh_field('within_city_optimization_results');

					let best = r.message[0];
					frm.set_value('within_city_transport_cost', best.cost);
					frm.set_value('within_city_fleet_mix', best.fleet_mix);
					frm.set_value('status', 'Calculated');

					frm.trigger('calculate_total_cost');

					frappe.show_alert({
						message: __('Within-city optimization complete! Recommended: {0} ({1})', [best.fleet_mix, format_currency(best.cost)]),
						indicator: 'green'
					});
				} else {
					frappe.msgprint(__('No viable within-city delivery configuration found.'));
				}
			}
		});
	}
});
