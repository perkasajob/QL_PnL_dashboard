import frappe

@frappe.whitelist()
def extract_sales_team_data(raw_text):
    """
    Extracts sales person name, ID, and territory from a multiline string.    
    """
    if not raw_text:
        return []

    extracted_data = []
    
    # Split the raw text into individual lines and remove empty lines
    lines = [line.strip() for line in str(raw_text).strip().split('\n') if line.strip()]
    
    for line in lines:
        if ' / ' not in line:
            continue
            
        # 1. Split the string into the left side (Name & ID) and right side (Territory)
        name_id_part, territory_part = line.split(' / ', 1)
        
        # 2. Extract Name and ID using the '#' separator
        if '#' in name_id_part:
            name, sp_id = name_id_part.split('#', 1)
        else:
            name = name_id_part
            sp_id = ""
            
        # 3. Clean the Territory by stripping '(', '_QL2', and '_QUANTUM'
        territory = territory_part.split('(')[0].strip()
        if '_QL2' in territory:
            territory = territory.split('_QL2')[0].strip()
        if '_QUANTUM' in territory:
            territory = territory.split('_QUANTUM')[0].strip()

        # 4. Extract Sales Tier from parenthesized code (e.g. LPG_DM_QUANTUM -> DM, MDN_REP_QUANTUM -> MR)
        tier = ""
        if '(' in territory_part and ')' in territory_part:
            inside_paren = territory_part.split('(')[-1].split(')')[0].strip()
            parts = inside_paren.split('_')
            if len(parts) >= 3:
                raw_tier = parts[1].strip().upper()
            elif len(parts) == 2:
                raw_tier = parts[0].strip().upper()
            else:
                raw_tier = inside_paren.strip().upper()

            # Mapping: REP is MR
            if raw_tier == "REP":
                tier = "MR"
            else:
                tier = raw_tier
            
        extracted_data.append({
            "sales_person_name": name.strip(),
            "sales_person_id": sp_id.strip(),
            "territory": territory.strip(),
            "tier": tier
        })
        
    return extracted_data


def extract_territory_from_mr(mr_text):
    """
    Extracts territory/sales person code from MR string.
    Example: 'DAVIT PURBA #2120337 / SUMUT1.2.1_QL2 (MDN_REP_QUANTUM)' -> 'SUMUT1.2.1_QL2'
    """
    if not mr_text:
        return ""
    if " / " in mr_text:
        _, territory_part = mr_text.split(" / ", 1)
        return territory_part.split("(")[0].strip()
    return mr_text.strip()


@frappe.whitelist()
def sync_sales_from_salesdivisi2(from_date=None, to_date=None, commit_batch_size=100):
    """
    Synchronizes Sales DocType from is_salesdivisi2 table from ISQ db.
    Filters by the last 1 month of tanggal_faktur (by default), inserts new records, and updates existing records if any values have changed.    
    Examples cmd:
    # Default (runs for the last 1 month):
    # bench --site ms.quantumlaboratoris.com execute ql.tools.ql_tools.sync_sales_from_salesdivisi2
    # Custom date range:
    # bench --site ms.quantumlaboratoris.com execute ql.tools.ql_tools.sync_sales_from_salesdivisi2 --kwargs "{'from_date': '2026-09-01', 'to_date': '2026-09-07'}"
    """
    from frappe.utils import add_months, today, getdate, flt, cint

    if not from_date:
        from_date = str(add_months(today(), -1))
    else:
        from_date = str(getdate(from_date))

    if to_date:
        to_date = str(getdate(to_date))

    # 1. Fetch source rows from is_salesdivisi2
    sql_conditions = ["tanggal_faktur >= %(from_date)s"]
    params = {"from_date": from_date}

    if to_date:
        sql_conditions.append("tanggal_faktur <= %(to_date)s")
        params["to_date"] = to_date

    where_clause = " AND ".join(sql_conditions)

    source_query = f"""
        SELECT 
            tahun, bulan, comid, disid, distributor, outid, outlet, alamat,
            tanggal_faktur, nomor_faktur, proid, product, quantity, bonus,
            hna, value, diskon, hna2, value_net, nama_group, disc_p,
            disc_distributor, disc_spektakuler, mrid, mr, spvid, spv,
            dmid, dm, amid, am, smid, sm, gsmid, gsm, off_mr, off_spv,
            off_dm, off_am, sp_sales, tanggalinput, dplId
        FROM is_salesdivisi2
        WHERE {where_clause}
    """

    source_rows = frappe.db.sql(source_query, params, as_dict=True)
    if not source_rows:
        return {
            "status": "success",
            "message": f"No records found in is_salesdivisi2 for tanggal_faktur >= {from_date}",
            "from_date": from_date,
            "to_date": to_date,
            "total_source": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }

    # Sort in Python to ensure deterministic processing order
    source_rows.sort(
        key=lambda r: (
            str(r.get("tanggal_faktur") or ""),
            str(r.get("nomor_faktur") or ""),
            cint(r.get("proid")),
        )
    )

    # 2. Build in-memory lookup caches for fast lookup
    # Customer caches
    customer_records = frappe.db.sql("""
        SELECT name, custom_comid, custom_outid
        FROM `tabCustomer`
        WHERE custom_outid IS NOT NULL AND custom_outid != 0
    """, as_dict=True)
    customer_comid_outid_map = {}
    customer_outid_map = {}
    for c in customer_records:
        cid = str(c.custom_comid).strip() if c.custom_comid else ""
        oid = cint(c.custom_outid)
        customer_comid_outid_map[(cid, oid)] = c.name
        if oid not in customer_outid_map:
            customer_outid_map[oid] = c.name

    # Branch Distributor cache
    branches = frappe.db.sql("""
        SELECT name, custom_sales_partner, custom_address
        FROM `tabBranch Distributor`
    """, as_dict=True)
    branch_map = {
        b.name: (b.custom_sales_partner or "", b.custom_address or "")
        for b in branches
    }

    # Item Name cache
    items = frappe.db.sql("SELECT name, item_name FROM `tabItem`", as_dict=True)
    item_map = {str(item.name): item.item_name for item in items}

    # 3. Fetch existing Sales records in target date range
    existing_sales_sql = f"""
        SELECT 
            s.name,
            s.custom_customers_purchase_order,
            s.custom_customers_purchase_order_date,
            s.custom_gsv,
            s.custom_diskon,
            s.custom_nsv1,
            s.custom_customer,
            s.custom_divisi,
            s.custom_sales_person,
            s.custom_sales_partner,
            s.custom_branch_distributor,
            s.custom_mr,
            s.custom_spv,
            s.custom_dm,
            s.custom_am,
            s.custom_sm,
            s.custom_gsm,
            si.name as item_row_name,
            si.custom_item,
            si.custom_item_name,
            si.custom_quantity,
            si.custom_hna,
            si.custom_amount
        FROM `tabSales` s
        JOIN `tabSales Item` si ON si.parent = s.name
        WHERE s.custom_customers_purchase_order_date >= %(from_date)s
    """
    if to_date:
        existing_sales_sql += " AND s.custom_customers_purchase_order_date <= %(to_date)s"

    existing_sales_rows = frappe.db.sql(existing_sales_sql, params, as_dict=True)

    # Group existing sales by key: (po_number, po_date, item_code) -> list of existing entries
    existing_sales_dict = {}
    for ex in existing_sales_rows:
        po_no = str(ex.custom_customers_purchase_order or "").strip()
        po_date = str(ex.custom_customers_purchase_order_date or "").strip()
        item_code = str(ex.custom_item or "").strip()
        k = (po_no, po_date, item_code)
        if k not in existing_sales_dict:
            existing_sales_dict[k] = []
        existing_sales_dict[k].append(ex)

    matched_sales_item_row_names = set()

    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    commit_batch = cint(commit_batch_size) or 100

    # 4. Iterate over source rows and insert / update
    for idx, row in enumerate(source_rows, start=1):
        try:
            nomor_faktur = str(row.get("nomor_faktur") or "").strip()
            tanggal_faktur = str(row.get("tanggal_faktur") or "").strip()
            proid = str(row.get("proid") or "").strip()
            k = (nomor_faktur, tanggal_faktur, proid)

            # Determine customer
            comid_str = str(row.get("comid") or "").strip()
            outid_int = cint(row.get("outid"))
            customer_name = customer_comid_outid_map.get((comid_str, outid_int))
            if not customer_name:
                customer_name = customer_outid_map.get(outid_int)
            if not customer_name:
                customer_name = f"{comid_str}-{outid_int} {row.get('outlet') or ''}".strip()

            # Determine partner and branch distributor
            distributor = str(row.get("distributor") or "").strip()
            if distributor in branch_map:
                sales_partner, branch_distributor = branch_map[distributor]
            else:
                sales_partner = distributor.split("-")[0] if "-" in distributor else distributor
                branch_distributor = distributor

            # Determine territory / sales person from MR
            sales_person = extract_territory_from_mr(row.get("mr"))

            # Determine item name
            raw_product = str(row.get("product") or "").strip()
            clean_product = raw_product.replace("(Q) ", "").strip()
            item_name = item_map.get(proid) or clean_product

            # Numeric values
            qty = flt(row.get("quantity"))
            hna = flt(row.get("hna"))
            val = flt(row.get("value"))
            diskon = flt(row.get("diskon"))
            val_net = flt(row.get("value_net"))
            is_return = 1 if (qty < 0 or val < 0) else 0

            divisi = str(row.get("nama_group") or "").strip()
            tahun = str(row.get("tahun") or "")
            bulan = str(row.get("bulan") or "")

            mr_val = row.get("mr") or ""
            spv_val = row.get("spv") or ""
            dm_val = row.get("dm") or ""
            am_val = row.get("am") or ""
            sm_val = row.get("sm") or ""
            gsm_val = row.get("gsm") or None

            # Check if matching existing doc exists
            candidate_list = existing_sales_dict.get(k, [])
            matched_candidate = None
            for cand in candidate_list:
                if cand.item_row_name not in matched_sales_item_row_names:
                    matched_candidate = cand
                    break

            if matched_candidate:
                matched_sales_item_row_names.add(matched_candidate.item_row_name)

                # Check if update is needed
                differs = (
                    abs(flt(matched_candidate.custom_gsv) - val) > 0.001
                    or abs(flt(matched_candidate.custom_diskon) - diskon) > 0.001
                    or abs(flt(matched_candidate.custom_nsv1) - val_net) > 0.001
                    or abs(flt(matched_candidate.custom_quantity) - qty) > 0.001
                    or abs(flt(matched_candidate.custom_hna) - hna) > 0.001
                    or (matched_candidate.custom_customer or "") != customer_name
                    or (matched_candidate.custom_sales_person or "") != sales_person
                    or (matched_candidate.custom_sales_partner or "") != sales_partner
                    or (matched_candidate.custom_branch_distributor or "") != branch_distributor
                    or (matched_candidate.custom_divisi or "") != divisi
                    or (matched_candidate.custom_mr or "") != mr_val
                    or (matched_candidate.custom_spv or "") != spv_val
                    or (matched_candidate.custom_dm or "") != dm_val
                    or (matched_candidate.custom_am or "") != am_val
                    or (matched_candidate.custom_sm or "") != sm_val
                    or (matched_candidate.custom_gsm or "") != (gsm_val or "")
                )

                if differs:
                    sales_doc = frappe.get_doc("Sales", matched_candidate.name)
                    sales_doc.custom_customer = customer_name
                    sales_doc.custom_divisi = divisi
                    sales_doc.custom_sales_partner = sales_partner
                    sales_doc.custom_branch_distributor = branch_distributor
                    sales_doc.custom_sales_person = sales_person
                    sales_doc.custom_gsv = val
                    sales_doc.custom_diskon = diskon
                    sales_doc.custom_nsv1 = val_net
                    sales_doc.custom_is_return_credit_note = is_return
                    sales_doc.custom_mr = mr_val
                    sales_doc.custom_spv = spv_val
                    sales_doc.custom_dm = dm_val
                    sales_doc.custom_am = am_val
                    sales_doc.custom_sm = sm_val
                    sales_doc.custom_gsm = gsm_val

                    if sales_doc.custom_items:
                        item_row = sales_doc.custom_items[0]
                        item_row.custom_quantity = qty
                        item_row.custom_hna = hna
                        item_row.custom_amount = val
                        item_row.custom_item_name = item_name

                    sales_doc.flags.ignore_permissions = True
                    sales_doc.flags.ignore_links = True
                    sales_doc.flags.ignore_mandatory = True
                    sales_doc.save()
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # Insert new Sales Doc
                sales_doc = frappe.get_doc({
                    "doctype": "Sales",
                    "naming_series": "SALES-.YYYY.-",
                    "custom_tahun": tahun,
                    "custom_bulan": bulan,
                    "custom_customer": customer_name,
                    "custom_divisi": divisi,
                    "custom_sales_partner": sales_partner,
                    "custom_branch_distributor": branch_distributor,
                    "custom_customers_purchase_order": nomor_faktur,
                    "custom_customers_purchase_order_date": tanggal_faktur,
                    "custom_gsv": val,
                    "custom_diskon": diskon,
                    "custom_nsv1": val_net,
                    "custom_faktur": 0.0,
                    "custom_is_return_credit_note": is_return,
                    "custom_sales_person": sales_person,
                    "custom_mr": mr_val,
                    "custom_spv": spv_val,
                    "custom_dm": dm_val,
                    "custom_am": am_val,
                    "custom_sm": sm_val,
                    "custom_gsm": gsm_val,
                    "custom_items": [
                        {
                            "doctype": "Sales Item",
                            "custom_item": proid,
                            "custom_item_name": item_name,
                            "custom_quantity": qty,
                            "custom_hna": hna,
                            "custom_amount": val
                        }
                    ]
                })
                sales_doc.flags.ignore_permissions = True
                sales_doc.flags.ignore_links = True
                sales_doc.flags.ignore_mandatory = True
                sales_doc.insert()
                inserted_count += 1

            if idx % commit_batch == 0:
                frappe.db.commit()

        except Exception as e:
            error_count += 1
            frappe.log_error(
                title=f"Error syncing Sales row {row.get('nomor_faktur')} - {row.get('proid')}",
                message=frappe.get_traceback()
            )

    frappe.db.commit()

    result = {
        "status": "success",
        "from_date": str(from_date),
        "to_date": str(to_date) if to_date else None,
        "total_source": len(source_rows),
        "inserted": inserted_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": error_count
    }
    frappe.logger("sales_sync").info(f"Sales synchronization completed: {result}")
    return result


    