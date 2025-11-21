frappe.query_reports["Most Selling Report Stock"] = {
    "filters": [
        {
            "fieldname": "limit",
            "label": __("Limit"),
            "fieldtype": "Select",
            "default": "100",
            "options": "\n50\n100\n200\n500"
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "sort_by",
            "label": __("Sort By"),
            "fieldtype": "Select",
            "options": "\nQuantity\nAmount",
            "default": "Amount"
        }
    ]
};
