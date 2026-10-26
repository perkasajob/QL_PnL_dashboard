# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, getdate

VARIABLE_MOH_FIELDS = [
	"biaya_kerusakan_bahan",
	"biaya_analisa",
	"jasa_pengujian_analisa",
	"biaya_pengolahan_limbah",
	"biaya_impor",
	"biaya_ekspedisi",
]

FIXED_MOH_FIELDS = [
	"biaya_pegawai_tak_langsung",
	"biaya_keamanan",
	"biaya_rumah_tangga",
	"biaya_pabrik_lainnya",
	"biaya_penyusutan_bangunan",
	"biaya_penyusutan_mesin",
	"biaya_penyusutan_inventaris_kantor",
	"biaya_perlengkapan_dan_atk",
	"biaya_fotocopy_dan_cetakan",
	"biaya_listrik_dan_air",
	"biaya_asuransi",
	"biaya_perjalanan_dinas",
	"biaya_entertainment",
	"biaya_training",
	"biaya_pemeliharaan_bangunan_mesin_inventaris",
	"biaya_pemeliharaan_kendaraan",
	"jasa_pemeliharaan_bangunan_mesin_inventaris",
	"jasa_pemeliharaan_kendaraan",
	"biaya_rnd",
	"biaya_sewa_tabung_peralatan",
	"biaya_sewa_kendaraan",
]


class ManufacturingOverhead(Document):
	def autoname(self):
		if not self.period_date:
			frappe.throw(_("Period Date is required for naming."))
		snap_date = get_first_day(self.period_date)
		self.period_date = snap_date
		d = getdate(snap_date)
		self.name = f"MOH-{d.strftime('%Y')}-{d.strftime('%m')}"

	def validate(self):
		# 1. Snap period_date to the 1st of the month
		if self.period_date:
			self.period_date = get_first_day(self.period_date)

		# 2. Enforce uniqueness: Only 1 active/submitted record per period_date + company
		self.validate_uniqueness()

		# 3. Calculate summary totals
		self.calculate_totals()

	def validate_uniqueness(self):
		filters = {
			"company": self.company,
			"period_date": self.period_date,
			"docstatus": ["<", 2],
		}
		if self.name:
			filters["name"] = ["!=", self.name]

		existing = frappe.db.get_value("Manufacturing Overhead", filters, "name")
		if existing:
			frappe.throw(
				_("Manufacturing Overhead for company {0} and period {1} already exists ({2}).").format(
					frappe.bold(self.company),
					frappe.bold(str(self.period_date)),
					frappe.bold(existing),
				),
				frappe.DuplicateEntryError,
			)

	def calculate_totals(self):
		tot_var = sum(flt(self.get(f) or 0.0) for f in VARIABLE_MOH_FIELDS)
		tot_fixed = sum(flt(self.get(f) or 0.0) for f in FIXED_MOH_FIELDS)

		self.total_variable_moh = flt(tot_var, 2)
		self.total_fixed_moh = flt(tot_fixed, 2)
		self.total = flt(tot_var + tot_fixed, 2)
