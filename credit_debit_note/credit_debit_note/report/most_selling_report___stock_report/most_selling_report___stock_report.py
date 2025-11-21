# top_100_most_selling_item__stock_report.py
# Script Report: Top 100 most selling item - stock report
# Behavior:
#  - If the "limit" filter is empty -> show ALL matching items (no LIMIT clause)
#  - If the "limit" filter contains a number or text containing a number -> use that as LIMIT
#  - Supports item_group filter and sort_by ("Quantity" or "Amount")

import frappe
import re

def execute(filters=None):
    """
    Entry point called by Frappe when the report runs.
    Returns: (columns, data)
    """
    filters = filters or {}
    return get_columns(), get_data(filters)

# ----------------------------------------------
# COLUMNS
# ----------------------------------------------
def get_columns():
    return [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": "Total Sold Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": "Total Sales Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
        {"label": "Current Stock", "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
        {"label": "Safety Stock", "fieldname": "safety_stock", "fieldtype": "Float", "width": 120},
        {"label": "Shortage Qty", "fieldname": "shortage_qty", "fieldtype": "Float", "width": 120}
    ]

# ----------------------------------------------
# DATA
# ----------------------------------------------
def get_data(filters):
    # SORT → Qty or Amount
    sort_by = filters.get("sort_by") or "Quantity"
    order_by_field = "total_amount" if sort_by == "Amount" else "total_qty"

    # LIMIT logic: if limit not provided -> show ALL (no LIMIT clause)
    limit_value = filters.get("limit")
    limit = None

    if limit_value:
        # try to parse integer directly, otherwise extract digits with regex
        try:
            limit = int(limit_value)
        except Exception:
            match = re.search(r"\d+", str(limit_value))
            limit = int(match.group()) if match else None

    # ITEM GROUP FILTER
    ig_condition = ""
    params = {}

    if filters.get("item_group"):
        ig_condition = " AND i.item_group = %(item_group)s "
        params["item_group"] = filters.get("item_group")

    # build LIMIT clause only if limit is an integer
    limit_clause = f"LIMIT {limit}" if isinstance(limit, int) else ""

    # MAIN QUERY
    # Note: order_by_field is controlled by us (either total_amount or total_qty)
    query = f"""
        SELECT
            sii.item_code AS item_code,
            i.item_name AS item_name,
            i.item_group AS item_group,
            SUM(sii.qty) AS total_qty,
            SUM(sii.base_net_amount) AS total_amount,

            COALESCE((SELECT SUM(actual_qty)
                      FROM `tabBin`
                      WHERE item_code = sii.item_code), 0) AS current_stock,

            COALESCE(i.safety_stock, 0) AS safety_stock,

            (COALESCE(i.safety_stock, 0) -
             COALESCE((SELECT SUM(actual_qty)
                       FROM `tabBin`
                       WHERE item_code = sii.item_code), 0)
            ) AS shortage_qty

        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        LEFT JOIN `tabItem` i ON i.name = sii.item_code

        WHERE si.docstatus = 1
        {ig_condition}

        GROUP BY sii.item_code, i.item_name, i.item_group, i.safety_stock

        ORDER BY {order_by_field} DESC
        {limit_clause}
    """

    # Run query with params (item_group if provided)
    return frappe.db.sql(query, params, as_dict=True)
