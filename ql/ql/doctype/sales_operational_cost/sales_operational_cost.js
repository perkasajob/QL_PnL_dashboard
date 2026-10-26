// Copyright (c) 2026, QL and contributors
// License: MIT. See LICENSE

const VARIABLE_SALES_FIELDS = [
	'biaya_komisi_penjualan',
	'biaya_pendistribusian_produk',
	'biaya_ekspedisi'
];

const FIXED_OPERATING_NON_SALARY_FIELDS = [
	'biaya_rumah_tangga',
	'biaya_perjalanan_dinas',
	'biaya_entertainment',
	'biaya_perlengkapan_dan_atk',
	'biaya_fotocopy_dan_cetakan',
	'biaya_listrik_dan_air',
	'biaya_pemeliharaan_kendaraan',
	'jasa_pemeliharaan_kendaraan',
	'biaya_telepon_dan_internet',
	'biaya_penyusutan_kendaraan',
	'biaya_penyusutan_inventaris_kantor'
];

function calculate_soc_totals(frm) {
	let tot_var_sales = 0.0;
	VARIABLE_SALES_FIELDS.forEach(f => {
		tot_var_sales += flt(frm.doc[f] || 0.0);
	});

	let salary = flt(frm.doc.biaya_gaji || 0.0);
	let commission = flt(frm.doc.biaya_komisi_penjualan || 0.0);

	let tot_fixed_op = 0.0;
	FIXED_OPERATING_NON_SALARY_FIELDS.forEach(f => {
		tot_fixed_op += flt(frm.doc[f] || 0.0);
	});

	frm.set_value('total_variable_sales_cost', flt(tot_var_sales, 2));
	frm.set_value('total_employee_cost', flt(salary + commission, 2));
	frm.set_value('total_fixed_operating_cost', flt(tot_fixed_op, 2));
	frm.set_value('total', flt(tot_var_sales + salary + tot_fixed_op, 2));
}

function snap_period_date(frm) {
	if (frm.doc.period_date) {
		let parts = frm.doc.period_date.split('-');
		if (parts.length === 3) {
			let snapped = `${parts[0]}-${parts[1]}-01`;
			if (frm.doc.period_date !== snapped) {
				frm.set_value('period_date', snapped);
			}
		}
	}
}

const form_handlers = {
	refresh: function(frm) {
		calculate_soc_totals(frm);
	},
	validate: function(frm) {
		snap_period_date(frm);
		calculate_soc_totals(frm);
	},
	period_date: function(frm) {
		snap_period_date(frm);
	},
	biaya_gaji: function(frm) {
		calculate_soc_totals(frm);
	}
};

VARIABLE_SALES_FIELDS.concat(FIXED_OPERATING_NON_SALARY_FIELDS).forEach(f => {
	form_handlers[f] = function(frm) {
		calculate_soc_totals(frm);
	};
});

frappe.ui.form.on('Sales Operational Cost', form_handlers);
