// Exact same JS as ERPNext standard Selling → Sales Analytics
// Only report name changed

frappe.query_reports["Sales Analaytic - Custom report"] = {
    filters: [
        {
            fieldname: "company",	
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "group_by",
            label: __("Group By"),
            fieldtype: "Select",
            options: ["Customer", "Customer Group", "Item", "Item Group", "Territory"],
            default: "Customer Group",
            reqd: 1
        },
        {
            fieldname: "value_quantity",
            label: __("Value / Quantity"),
            fieldtype: "Select",
            options: ["Value", "Quantity"],
            default: "Value",
            reqd: 1
        },
        {
            fieldname: "period",
            label: __("Period"),
            fieldtype: "Select",
            options: ["Monthly", "Quarterly", "Half Yearly", "Yearly"],
            default: "Monthly",
            reqd: 1
        }
    ]
};
