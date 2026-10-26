// Copyright (c) 2026, QL and contributors
// License: MIT. See LICENSE

const VARIABLE_MOH_FIELDS = [
	'biaya_kerusakan_bahan',
	'biaya_analisa',
	'jasa_pengujian_analisa',
	'biaya_pengolahan_limbah',
	'biaya_impor',
	'biaya_ekspedisi'
];

const FIXED_MOH_FIELDS = [
	'biaya_pegawai_tak_langsung',
	'biaya_keamanan',
	'biaya_rumah_tangga',
	'biaya_pabrik_lainnya',
	'biaya_penyusutan_bangunan',
	'biaya_penyusutan_mesin',
	'biaya_penyusutan_inventaris_kantor',
	'biaya_perlengkapan_dan_atk',
	'biaya_fotocopy_dan_cetakan',
	'biaya_listrik_dan_air',
	'biaya_asuransi',
	'biaya_perjalanan_dinas',
	'biaya_entertainment',
	'biaya_training',
	'biaya_pemeliharaan_bangunan_mesin_inventaris',
	'biaya_pemeliharaan_kendaraan',
	'jasa_pemeliharaan_bangunan_mesin_inventaris',
	'jasa_pemeliharaan_kendaraan',
	'biaya_rnd',
	'biaya_sewa_tabung_peralatan',
	'biaya_sewa_kendaraan'
];

function calculate_moh_totals(frm) {
	let tot_var = 0.0;
	VARIABLE_MOH_FIELDS.forEach(f => {
		tot_var += flt(frm.doc[f] || 0.0);
	});

	let tot_fixed = 0.0;
	FIXED_MOH_FIELDS.forEach(f => {
		tot_fixed += flt(frm.doc[f] || 0.0);
	});

	frm.set_value('total_variable_moh', flt(tot_var, 2));
	frm.set_value('total_fixed_moh', flt(tot_fixed, 2));
	frm.set_value('total', flt(tot_var + tot_fixed, 2));
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
		calculate_moh_totals(frm);
	},
	validate: function(frm) {
		snap_period_date(frm);
		calculate_moh_totals(frm);
	},
	period_date: function(frm) {
		snap_period_date(frm);
	}
};

VARIABLE_MOH_FIELDS.concat(FIXED_MOH_FIELDS).forEach(f => {
	form_handlers[f] = function(frm) {
		calculate_moh_totals(frm);
	};
});

frappe.ui.form.on('Manufacturing Overhead', form_handlers);
