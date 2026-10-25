
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re
import sys

# ==========================================
# SALES TREND ANALYSIS PROJECT
# ==========================================

folder = Path(__file__).resolve().parent

# Find input files; exclude generated output files
excluded = {
    "monthly_sales.csv",
    "customer_analysis.csv",
    "sales_pivot_table.csv",
    "sales_cleaned.csv",
}

files = [
    *folder.glob("*.xlsx"),
    *folder.glob("*.xls"),
    *folder.glob("*.csv"),
]

files = [
    f for f in files
    if f.name.lower() not in excluded
    and not f.name.startswith("~$")
]

if not files:
    print("ERROR: Dataset nahi mili!")
    print("CSV ya Excel file project folder mein rakho.")
    sys.exit(1)

# Prefer the expected input filename when available
file = next(
    (f for f in files if f.name.lower() == "sales data.csv"),
    files[0]
)

print("Dataset found:", file.name)

# Load dataset
try:
    if file.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(file)
    else:
        try:
            df = pd.read_csv(file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin1")
except Exception as exc:
    print("Dataset read error:", exc)
    sys.exit(1)

if df.empty:
    print("ERROR: Dataset empty hai.")
    sys.exit(1)

# Normalize column names for matching
def normalize(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())

df.columns = [str(c).strip() for c in df.columns]

print("\nOriginal columns:")
print(df.columns.tolist())

normalized = {normalize(c): c for c in df.columns}

# Match common names used by sales datasets
aliases = {
    "InvoiceNo": [
        "invoiceno", "invoice", "invoicenumber",
        "ordernumber", "transactionid"
    ],
    "Description": [
        "description", "product", "productname",
        "item", "itemname"
    ],
    "Quantity": [
        "quantity", "qty", "units", "unitssold"
    ],
    "InvoiceDate": [
        "invoicedate", "orderdate", "date",
        "salesdate", "transactiondate"
    ],
    "UnitPrice": [
        "unitprice", "price", "unitcost",
        "sellingprice", "priceperunit"
    ],
    "CustomerID": [
        "customerid", "customernumber",
        "customer", "clientid"
    ],
}

rename = {}

for standard, options in aliases.items():
    for option in options:
        if option in normalized:
            rename[normalized[option]] = standard
            break

df = df.rename(columns=rename)

# Support datasets where total sales/revenue is already provided
revenue_aliases = [
    "revenue", "sales", "totalsales",
    "totalrevenue", "salesamount", "amount"
]

revenue_column = next(
    (normalized[x] for x in revenue_aliases if x in normalized),
    None
)

if "Revenue" not in df.columns and revenue_column:
    df["Revenue"] = pd.to_numeric(
        df[revenue_column], errors="coerce"
    )

# If quantity and price exist, calculate revenue from them
if "Quantity" in df.columns and "UnitPrice" in df.columns:
    df["Quantity"] = pd.to_numeric(
        df["Quantity"], errors="coerce"
    )
    df["UnitPrice"] = pd.to_numeric(
        df["UnitPrice"], errors="coerce"
    )
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]

# Identify the date column if not already mapped
if "InvoiceDate" not in df.columns:
    date_candidates = [
        c for c in df.columns
        if any(word in normalize(c) for word in
               ["date", "datetime", "timestamp"])
    ]
    if date_candidates:
        df = df.rename(
            columns={date_candidates[0]: "InvoiceDate"}
        )

# Identify product column if not already mapped
if "Description" not in df.columns:
    product_candidates = [
        c for c in df.columns
        if any(word in normalize(c) for word in
               ["productname", "product", "itemname"])
    ]
    if product_candidates:
        df = df.rename(
            columns={product_candidates[0]: "Description"}
        )

# Validate minimum columns
if "InvoiceDate" not in df.columns:
    print("\nERROR: Date column identify nahi hui.")
    print("Available columns:", df.columns.tolist())
    print("Date/OrderDate/SalesDate jaisa column chahiye.")
    sys.exit(1)

if "Revenue" not in df.columns:
    print("\nERROR: Revenue calculate nahi ho paaya.")
    print("Quantity + UnitPrice, ya Sales/Revenue column chahiye.")
    print("Available columns:", df.columns.tolist())
    sys.exit(1)

# Prepare data
df = df.drop_duplicates().copy()

df["InvoiceDate"] = pd.to_datetime(
    df["InvoiceDate"], errors="coerce"
)
df["Revenue"] = pd.to_numeric(
    df["Revenue"], errors="coerce"
)

if "Quantity" in df.columns:
    df["Quantity"] = pd.to_numeric(
        df["Quantity"], errors="coerce"
    )
else:
    df["Quantity"] = 1

if "InvoiceNo" not in df.columns:
    df["InvoiceNo"] = df.index.astype(str)

if "Description" not in df.columns:
    df["Description"] = "Unknown Product"

if "CustomerID" not in df.columns:
    df["CustomerID"] = pd.NA

df = df.dropna(subset=["InvoiceDate", "Revenue"]).copy()

# Remove invalid revenue and cancelled invoices where applicable
if "UnitPrice" in df.columns:
    df = df[df["UnitPrice"] > 0]

if "InvoiceNo" in df.columns:
    df = df[
        ~df["InvoiceNo"].astype(str).str.startswith("C")
    ]

if df.empty:
    print("ERROR: Cleaning ke baad valid sales records nahi bache.")
    sys.exit(1)

# Feature engineering
df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)
df["Year"] = df["InvoiceDate"].dt.year
df["Month"] = df["InvoiceDate"].dt.month
df["DayOfWeek"] = df["InvoiceDate"].dt.day_name()

# ==========================================
# 1. MONTHLY SALES TREND
# ==========================================

monthly = df.groupby("YearMonth")["Revenue"].sum()
monthly.to_csv(folder / "monthly_sales.csv")

plt.figure(figsize=(12, 5))
monthly.plot(marker="o")
plt.title("Monthly Revenue Trend")
plt.xlabel("Month")
plt.ylabel("Revenue")
plt.xticks(rotation=45)
plt.grid(alpha=0.25)
plt.tight_layout()
plt.savefig(folder / "monthly_sales_trend.png", dpi=150)
plt.close()

# ==========================================
# 2. TOP 10 PRODUCTS
# ==========================================

top_products = (
    df.groupby("Description")["Revenue"]
    .sum()
    .nlargest(10)
    .sort_values()
)

top_products.to_csv(folder / "top_products.csv")

plt.figure(figsize=(10, 6))
top_products.plot(kind="barh")
plt.title("Top 10 Products by Revenue")
plt.xlabel("Revenue")
plt.tight_layout()
plt.savefig(folder / "top_products.png", dpi=150)
plt.close()

# ==========================================
# 3. CUSTOMER ANALYSIS
# ==========================================

customer_data = df.dropna(subset=["CustomerID"]).copy()

customer = customer_data.groupby("CustomerID").agg(
    Total_Spent=("Revenue", "sum"),
    Total_Orders=("InvoiceNo", "nunique"),
    Total_Quantity=("Quantity", "sum")
).sort_values("Total_Spent", ascending=False)

customer.to_csv(folder / "customer_analysis.csv")

# ==========================================
# 4. YEAR-MONTH HEATMAP
# ==========================================

pivot = pd.pivot_table(
    df,
    index="Year",
    columns="Month",
    values="Revenue",
    aggfunc="sum",
    fill_value=0
)

pivot.to_csv(folder / "sales_pivot_table.csv")

plt.figure(figsize=(12, 5))
plt.imshow(pivot, aspect="auto")
plt.title("Monthly Revenue Heatmap")
plt.xlabel("Month")
plt.ylabel("Year")
plt.xticks(
    range(len(pivot.columns)),
    pivot.columns
)
plt.yticks(
    range(len(pivot.index)),
    pivot.index
)
plt.colorbar(label="Revenue")
plt.tight_layout()
plt.savefig(folder / "sales_pivot_heatmap.png", dpi=150)
plt.close()

# ==========================================
# 5. SAVE CLEANED DATASET
# ==========================================

df.to_csv(folder / "sales_cleaned.csv", index=False)

# ==========================================
# 6. BUSINESS RECOMMENDATIONS
# ==========================================

best_month = monthly.idxmax()
best_revenue = monthly.max()
top_product = top_products.idxmax()

top_customer = (
    customer["Total_Spent"].idxmax()
    if not customer.empty
    else "Customer ID unavailable"
)

total_revenue = df["Revenue"].sum()
unique_customers = df["CustomerID"].nunique()
total_orders = df["InvoiceNo"].nunique()

recommendations = f"""
SALES TREND ANALYSIS REPORT
===========================

Dataset: {file.name}
Valid records: {len(df)}
Total revenue: {total_revenue:.2f}
Unique customers: {unique_customers}
Total orders/transactions: {total_orders}

Best sales month: {best_month}
Revenue in best month: {best_revenue:.2f}
Top product by revenue: {top_product}
Highest-spending customer: {top_customer}

BUSINESS RECOMMENDATIONS
------------------------
1. Monitor high-revenue products and plan inventory accordingly.
2. Study promotions and events during the best-performing month.
3. Consider loyalty offers for repeat and high-spending customers.
4. Investigate weaker sales periods before planning discounts.
5. Use monthly sales trends to improve business forecasting.

Note: Recommendations are based on the available dataset.
"""

(folder / "business_recommendations.txt").write_text(
    recommendations, encoding="utf-8"
)

# ==========================================
# FINAL SUMMARY
# ==========================================

print("\n" + "=" * 45)
print("PROJECT COMPLETED SUCCESSFULLY!")
print("=" * 45)
print(f"Dataset: {file.name}")
print(f"Valid records: {len(df)}")
print(f"Total Revenue: {total_revenue:.2f}")
print(f"Unique Customers: {unique_customers}")
print(f"Best Month: {best_month}")
print(f"Top Product: {top_product}")

print("\nFiles saved in:", folder)
print("- monthly_sales_trend.png")
print("- top_products.png")
print("- sales_pivot_heatmap.png")
print("- monthly_sales.csv")
print("- top_products.csv")
print("- customer_analysis.csv")
print("- sales_pivot_table.csv")
print("- sales_cleaned.csv")
print("- business_recommendations.txt")
