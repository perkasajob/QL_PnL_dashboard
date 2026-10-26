import frappe
import requests
from frappe.utils import flt, get_first_day, get_last_day, today


# https://qsdev.quantumlaboratoris.com/api/method/ql.tasks.sync_items.sync_manufacturing_costs

@frappe.whitelist(allow_guest=True)
def sync_manufacturing_costs(from_date=None, to_date=None):
    if not from_date or not to_date:
        from_date = get_first_day(today())
        to_date = get_last_day(today())

    qs_url = frappe.conf.get("qs_costing_api_url") or "https://qs.quantum-laboratories.com/api/method/ql.api.get_item_costs"
    api_key = frappe.conf.get("qs_api_key") 
    api_secret = frappe.conf.get("qs_api_secret")

    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Accept": "application/json"
    }
    
    params = {
        "from_date": from_date,
        "to_date": to_date
    }

    try:
        response = requests.get(qs_url, headers=headers, params=params, timeout=30)
        # If remote server fails on date params (e.g. unknown column 'jc.employee_rate' in Job Card query), fallback without params
        if response.status_code != 200:
            fallback = requests.get(qs_url, headers=headers, timeout=30)
            if fallback.status_code == 200:
                response = fallback
        response.raise_for_status()
        data = response.json().get("message", [])
    except requests.exceptions.RequestException as e:
        frappe.log_error(title="qs Cost API Sync Failed", message=str(e))
        return f"Sync failed: {str(e)}"

    synced_count = 0

    for item in data:
        existing_fact = frappe.db.exists("Manufacturing Cost", {
            "item_code": item.get("item_code"),
            "period_start_date": from_date,
            "period_end_date": to_date
        })

        if existing_fact:
            doc = frappe.get_doc("Manufacturing Cost", existing_fact)
            doc.statutory_valuation_rate = flt(item.get("statutory_valuation_rate"))
            doc.variable_cogs_per_piece = flt(item.get("variable_cogs_per_piece"))
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({
                "doctype": "Manufacturing Cost",
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "product_id": item.get("product_id"),
                "apl_item_code": item.get("apl_item_code"),
                "statutory_valuation_rate": flt(item.get("statutory_valuation_rate")),
                "variable_cogs_per_piece": flt(item.get("variable_cogs_per_piece")),
                "period_start_date": from_date,
                "period_end_date": to_date
            })
            doc.insert(ignore_permissions=True)
        
        synced_count += 1

    frappe.db.commit()
    return f"Successfully synced {synced_count} dual-metric cost records from qs."