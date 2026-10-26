# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, getdate

VARIABLE_SALES_FIELDS = [
	"biaya_komisi_penjualan",
	"biaya_pendistribusian_produk",
	"biaya_ekspedisi",
]

FIXED_OPERATING_NON_SALARY_FIELDS = [
	"biaya_rumah_tangga",
	"biaya_perjalanan_dinas",
	"biaya_entertainment",
	"biaya_perlengkapan_dan_atk",
	"biaya_fotocopy_dan_cetakan",
	"biaya_listrik_dan_air",
	"biaya_pemeliharaan_kendaraan",
	"jasa_pemeliharaan_kendaraan",
	"biaya_telepon_dan_internet",
	"biaya_penyusutan_kendaraan",
	"biaya_penyusutan_inventaris_kantor",
]


class SalesOperationalCost(Document):
	def autoname(self):
		if not self.period_date or not self.territory:
			frappe.throw(_("Period Date and Territory are required for naming."))
		snap_date = get_first_day(self.period_date)
		self.period_date = snap_date
		d = getdate(snap_date)
		self.name = f"SOC-{self.territory}-{d.strftime('%Y')}-{d.strftime('%m')}"

	def validate(self):
		# 1. Snap period_date to the 1st of the month
		if self.period_date:
			self.period_date = get_first_day(self.period_date)

		# 2. Enforce uniqueness: Only 1 record per period_date + territory + sales_person
		self.validate_uniqueness()

		# 3. Calculate summary totals
		self.calculate_totals()

	def validate_uniqueness(self):
		filters = {
			"period_date": self.period_date,
			"territory": self.territory,
			"sales_person": self.sales_person,
			"docstatus": ["<", 2],
		}
		if self.name:
			filters["name"] = ["!=", self.name]

		existing = frappe.db.get_value("Sales Operational Cost", filters, "name")
		if existing:
			frappe.throw(
				_("Sales Operational Cost for period {0}, territory {1}, and sales person {2} already exists ({3}).").format(
					frappe.bold(str(self.period_date)),
					frappe.bold(self.territory),
					frappe.bold(self.sales_person),
					frappe.bold(existing),
				),
				frappe.DuplicateEntryError,
			)

	def calculate_totals(self):
		tot_var_sales = sum(flt(self.get(f) or 0.0) for f in VARIABLE_SALES_FIELDS)
		salary = flt(self.biaya_gaji or 0.0)
		commission = flt(self.biaya_komisi_penjualan or 0.0)
		tot_fixed_op = sum(flt(self.get(f) or 0.0) for f in FIXED_OPERATING_NON_SALARY_FIELDS)

		self.total_variable_sales_cost = flt(tot_var_sales, 2)
		self.total_employee_cost = flt(salary + commission, 2)
		self.total_fixed_operating_cost = flt(tot_fixed_op, 2)
		self.total = flt(tot_var_sales + salary + tot_fixed_op, 2)
