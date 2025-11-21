# Copyright (c) 2015, Frappe Technologies Pvt. Ltd.
# MIT License
# Modified to include custom_sub_group (Customer.custom_sub_group) aggregation
# and produce Customer Group -> Sub Group rows with period buckets.
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, add_days
from dateutil.relativedelta import relativedelta
from datetime import datetime

def execute(filters=None):
    if not filters:
        filters = {}

    # default required filters similar to standard report
    if not filters.get("company"):
        # do not force company, but standard report required company; leave optional
        pass

    # validate dates and period
    validate_filters(filters)

    # build period list
    period_list = get_period_date_ranges(filters.get("period", "Monthly"),
                                         filters["from_date"],
                                         filters["to_date"])

    # dynamic columns based on periods
    columns = get_columns(period_list)

    # aggregate data in a single SQL query per (customer_group, custom_sub_group)
    agg_rows = get_aggregated_rows(filters, period_list)

    # transform aggregated rows into hierarchical data:
    # top-level: customer_group rows; children: custom_sub_group rows
    data = build_hierarchical_rows(agg_rows, period_list)

    # chart data (same shape as original)
    chart = get_chart_data(filters, columns, data, period_list)

    return columns, data, None, chart


# -------------------------
# Validation & helpers
# -------------------------
def validate_filters(filters):
    if "from_date" not in filters or "to_date" not in filters:
        frappe.throw(_("Please select From Date and To Date"))

    if getdate(filters["to_date"]) < getdate(filters["from_date"]):
        frappe.throw(_("To Date must be greater than From Date"))

    if "period" in filters and filters["period"] not in ["Monthly", "Quarterly", "Half Yearly", "Yearly"]:
        frappe.throw(_("Period must be one of Monthly, Quarterly, Half Yearly or Yearly"))


def get_period_date_ranges(period, from_date, to_date):
    """Return list of periods with keys/labels and date ranges.
       period: Monthly / Quarterly / Half Yearly / Yearly
    """
    from_date, to_date = getdate(from_date), getdate(to_date)

    increments = {
        "Monthly": 1,
        "Quarterly": 3,
        "Half Yearly": 6,
        "Yearly": 12
    }

    step = increments.get(period, 1)
    periods = []
    start = from_date

    while start <= to_date:
        end = add_months(start, step) - relativedelta(days=1)
        if end > to_date:
            end = to_date

        key = start.strftime("%b_%Y")  # e.g., Apr_2025
        label = start.strftime("%b %Y") # e.g., Apr 2025
        periods.append({
            "key": key,
            "label": label,
            "from_date": start,
            "to_date": end
        })

        start = add_months(start, step)

    return periods

def add_months(d, months):
    return d + relativedelta(months=months)


# -------------------------
# Columns
# -------------------------
def get_columns(period_list):
    cols = [
        {"label": _("Customer Group"), "fieldname": "customer_group", "width": 200},
        {"label": _("Sub Group"), "fieldname": "custom_sub_group", "width": 180},
    ]

    for p in period_list:
        cols.append({
            "label": p["label"],
            "fieldname": p["key"],
            "fieldtype": "Float",
            "width": 120
        })

    cols.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "width": 140})
    # note: if you want to show more columns (Customer, Item, Territory) you can add them

    return cols


# -------------------------
# Aggregation SQL
# -------------------------
def get_aggregated_rows(filters, period_list):
    """
    Aggregates amounts (or qty) per Customer Group and per custom_sub_group for the given period ranges.

    Returns list of dicts:
    [
      {
        "customer_group": "Distributor",
        "custom_sub_group": "Branch",
        "period_col1": 12345.0,
        "period_col2": 0.0,
        ...
        "total": 12345.0
      }, ...
    ]
    """

    # determine whether to aggregate amount or qty
    value_quantity = filters.get("value_quantity", "Value")
    value_expr = "si_item.amount" if value_quantity == "Value" else "si_item.qty"

    # build period SUM(CASE ...) expressions
    period_sql_parts = []
    for i, p in enumerate(period_list):
        col = frappe.db.escape(p["key"])  # use as column name
        # safe param placeholders will be added separately
        period_sql_parts.append(
            "SUM(CASE WHEN si.posting_date BETWEEN %(p_from_{i})s AND %(p_to_{i})s THEN {val} ELSE 0 END) AS `{col}`"
            .format(i=i, val=value_expr, col=p["key"])
        )

    period_sql = ",\n            ".join(period_sql_parts)

    # base conditions
    conditions = ["si.docstatus = 1"]
    params = {}

    # add posting date overall range to limit rows scanned
    conditions.append("si.posting_date BETWEEN %(from_date)s AND %(to_date)s")
    params["from_date"] = filters["from_date"]
    params["to_date"] = filters["to_date"]

    if filters.get("company"):
        conditions.append("si.company = %(company)s")
        params["company"] = filters["company"]

    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        params["customer"] = filters["customer"]

    if filters.get("customer_group"):
        # customer_group is a field on Customer (c.customer_group)
        conditions.append("c.customer_group = %(customer_group)s")
        params["customer_group"] = filters["customer_group"]

    if filters.get("custom_sub_group"):
        # custom_sub_group is a custom field on Customer
        conditions.append("c.custom_sub_group = %(custom_sub_group)s")
        params["custom_sub_group"] = filters["custom_sub_group"]

    if filters.get("territory"):
        conditions.append("c.territory = %(territory)s")
        params["territory"] = filters["territory"]

    if filters.get("item_group"):
        conditions.append("i.item_group = %(item_group)s")
        params["item_group"] = filters["item_group"]

    if filters.get("item"):
        conditions.append("si_item.item_code = %(item)s")
        params["item"] = filters["item"]

    if filters.get("brand"):
        conditions.append("i.brand = %(brand)s")
        params["brand"] = filters["brand"]

    where_clause = " AND ".join(conditions)

    # Attach period params (p_from_0, p_to_0, etc.)
    for i, p in enumerate(period_list):
        params[f"p_from_{i}"] = p["from_date"]
        params[f"p_to_{i}"] = p["to_date"]

    # final SQL:
    # group by customer_group and custom_sub_group (customer.custom_sub_group)
    sql = f"""
        SELECT
            c.customer_group AS customer_group,
            c.custom_sub_group AS custom_sub_group,
            {period_sql},
            -- total across periods (also derived client-side if you prefer)
            SUM({value_expr}) AS total
        FROM
            `tabSales Invoice Item` si_item
            JOIN `tabSales Invoice` si ON si.name = si_item.parent
            JOIN `tabCustomer` c ON si.customer = c.name
            LEFT JOIN `tabItem` i ON si_item.item_code = i.name
        WHERE
            {where_clause}
        GROUP BY
            c.customer_group, c.custom_sub_group
        ORDER BY
            c.customer_group, c.custom_sub_group
    """

    # run query
    rows = frappe.db.sql(sql, params, as_dict=True)

    # ensure numeric 0.0 instead of None
    for r in rows:
        for p in period_list:
            if r.get(p["key"]) is None:
                r[p["key"]] = 0.0
        if r.get("total") is None:
            r["total"] = 0.0

    return rows


# -------------------------
# Build hierarchical rows
# -------------------------
def build_hierarchical_rows(agg_rows, period_list):
    """
    Convert aggregated rows into a list of rows suitable for reporting:
    - top row per customer_group (indent = 0)
    - child row per custom_sub_group (indent = 1)
    """

    data = []
    # build nested dict: {customer_group: {subgroup: row_dict, ...}, ...}
    nested = {}
    for r in agg_rows:
        cg = r.get("customer_group") or _("Undefined")
        sg = r.get("custom_sub_group") or _("(No Sub Group)")

        nested.setdefault(cg, {})
        # copy period values and total
        nested[cg].setdefault(sg, {})
        nested[cg][sg]["periods"] = {p["key"]: r.get(p["key"], 0.0) for p in period_list}
        nested[cg][sg]["total"] = r.get("total", 0.0)

    # Now assemble rows as list
    for cg, subgroups in nested.items():
        # group total = sum of subgroup totals
        group_total = sum(sg_data["total"] for sg_data in subgroups.values())
        group_row = {
            "customer_group": cg,
            "custom_sub_group": "",
            "total": group_total,
            "indent": 0  # 0 -> top-level
        }
        # add aggregated period values at group level (sum of subgroups)
        for p_key in (list(next(iter(subgroups.values()))["periods"].keys()) if subgroups else []):
            group_row[p_key] = sum(sg_data["periods"].get(p_key, 0.0) for sg_data in subgroups.values())

        data.append(group_row)

        # child rows
        for sg, sg_data in subgroups.items():
            row = {
                "customer_group": "",
                "custom_sub_group": sg,
                "total": sg_data["total"],
                "indent": 1  # 1 -> subgroup row
            }
            for p_key, p_val in sg_data["periods"].items():
                row[p_key] = p_val
            data.append(row)

    return data


# -------------------------
# Chart data (simple aggregated bar)
# -------------------------
def get_chart_data(filters, columns, data, period_list):
    # period fieldnames:
    period_cols = [p["key"] for p in period_list]

    totals = []
    for col in period_cols:
        # sum across rows (both group and subgroup rows contain numbers; it's fine)
        val = sum(row.get(col, 0.0) or 0.0 for row in data)
        totals.append(val)

    labels = [p["label"] for p in period_list]

    return {
        "data": {
            "labels": labels,
            "datasets": [{
                "name": _("Sales"),
                "values": totals
            }]
        },
        "type": "bar"
    }
