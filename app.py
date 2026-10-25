
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# =========================================
# PAGE CONFIGURATION
# =========================================
st.set_page_config(
    page_title="Sales Analytics | Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "Sales Data.csv"


# =========================================
# PROFESSIONAL STYLING
# =========================================
st.markdown("""
<style>
    .stApp {
        background-color: #0b1120;
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #263449;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #172238, #111b2e);
        border: 1px solid #293850;
        padding: 19px;
        border-radius: 14px;
    }
    [data-testid="stMetricLabel"] {
        color: #a5b4fc;
    }
    [data-testid="stMetricValue"] {
        color: #f8fafc;
    }
    .dashboard-subtitle {
        color: #9ca3af;
        font-size: 15px;
        margin-top: -10px;
    }
    .section-heading {
        font-size: 21px;
        font-weight: 650;
        margin-top: 18px;
        margin-bottom: 8px;
    }
    div[data-testid="stDownloadButton"] button {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# =========================================
# LOAD DATA
# =========================================
@st.cache_data(show_spinner="Loading sales dataset...")
def load_data(path, modified_time):
    del modified_time

    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    # Normalize names for flexible column matching
    def normalize(name):
        return re.sub(r"[^a-z0-9]", "", str(name).lower())

    original_columns = {
        normalize(c): c for c in df.columns
    }

    aliases = {
        "Order ID": [
            "orderid", "ordernumber", "invoiceno",
            "invoicenumber", "transactionid"
        ],
        "Product": [
            "product", "productname", "description",
            "item", "itemname"
        ],
        "Quantity Ordered": [
            "quantityordered", "quantity", "qty",
            "units", "unitssold"
        ],
        "Price Each": [
            "priceeach", "unitprice", "priceperunit",
            "sellingprice", "unitcost"
        ],
        "Order Date": [
            "orderdate", "invoicedate", "salesdate",
            "transactiondate", "date"
        ],
        "Purchase Address": [
            "purchaseaddress", "shippingaddress",
            "customeraddress", "address"
        ],
        "Sales": [
            "sales", "revenue", "totalsales",
            "totalrevenue", "salesamount", "amount"
        ],
    }

    rename = {}

    for standard_name, candidates in aliases.items():
        for candidate in candidates:
            if candidate in original_columns:
                rename[original_columns[candidate]] = standard_name
                break

    df = df.rename(columns=rename)

    # Remove repeated header rows that sometimes occur in CSV exports
    if "Order Date" in df.columns:
        df = df[
            df["Order Date"].astype(str).str.strip().str.lower()
            != "order date"
        ].copy()

    # Date is essential for time-based analytics
    if "Order Date" not in df.columns:
        raise ValueError(
            "Date column nahi mili. Available columns: "
            + ", ".join(df.columns)
        )

    df["Order Date"] = pd.to_datetime(
        df["Order Date"], errors="coerce"
    )

    # Quantity and price columns
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(
            df["Quantity Ordered"], errors="coerce"
        )
    else:
        df["Quantity Ordered"] = 1

    if "Price Each" in df.columns:
        df["Price Each"] = pd.to_numeric(
            df["Price Each"], errors="coerce"
        )

    # Calculate sales if quantity and price are available
    if "Price Each" in df.columns:
        df["Sales"] = (
            df["Quantity Ordered"] * df["Price Each"]
        )
    elif "Sales" in df.columns:
        df["Sales"] = pd.to_numeric(
            df["Sales"], errors="coerce"
        )
    else:
        raise ValueError(
            "Sales calculate nahi ho paayi. "
            "Quantity + Price, ya Sales/Revenue column chahiye."
        )

    if "Product" not in df.columns:
        df["Product"] = "Unknown Product"

    if "Order ID" not in df.columns:
        df["Order ID"] = [
            f"ROW-{i}" for i in range(len(df))
        ]

    # Keep only usable sales records
    df = df.drop_duplicates()
    df = df.dropna(subset=["Order Date", "Sales"])
    df = df[
        (df["Sales"] > 0)
        & (df["Quantity Ordered"] > 0)
    ].copy()

    # Derived fields
    df["Year"] = df["Order Date"].dt.year
    df["Month"] = df["Order Date"].dt.month
    df["Month Name"] = df["Order Date"].dt.strftime("%b")
    df["Year-Month"] = df["Order Date"].dt.to_period("M").astype(str)
    df["Hour"] = df["Order Date"].dt.hour
    df["Day"] = df["Order Date"].dt.day_name()

    if "Purchase Address" in df.columns:
        # City is estimated from addresses like "Street, City, ST ZIP"
        df["City"] = (
            df["Purchase Address"]
            .fillna("")
            .astype(str)
            .str.split(",")
            .str[-2]
            .str.strip()
        )
        df.loc[df["City"] == "", "City"] = "Unknown"
    else:
        df["City"] = "Not available"

    return df


# =========================================
# FRIENDLY ERROR HANDLING
# =========================================
if not DATA_FILE.exists():
    st.error("Sales Data.csv file nahi mili.")
    st.info(
        "app.py aur Sales Data.csv ko ek hi "
        "Sales_Trend_Analysis folder mein rakho."
    )
    st.stop()

try:
    df = load_data(
        str(DATA_FILE),
        DATA_FILE.stat().st_mtime,
    )
except Exception as error:
    st.error(f"Dataset load karne mein problem: {error}")
    st.stop()

if df.empty:
    st.error("Dataset mein valid sales records nahi mile.")
    st.stop()


# =========================================
# SIDEBAR FILTERS
# =========================================
st.sidebar.markdown("# 📊 Sales Analytics")
st.sidebar.caption("Interactive Business Intelligence")
st.sidebar.divider()

st.sidebar.subheader("Filters")

min_date = df["Order Date"].min().date()
max_date = df["Order Date"].max().date()

date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0] if isinstance(date_range, (tuple, list)) else date_range
    end_date = start_date

products = sorted(
    df["Product"].dropna().astype(str).unique().tolist()
)

selected_products = st.sidebar.multiselect(
    "Products",
    options=products,
    placeholder="All products",
)

cities = sorted(
    df["City"].dropna().astype(str).unique().tolist()
)

selected_cities = st.sidebar.multiselect(
    "Sales locations",
    options=cities,
    placeholder="All locations",
)

st.sidebar.divider()
st.sidebar.caption(f"Source file: {DATA_FILE.name}")
st.sidebar.caption(f"Dataset rows: {len(df):,}")


# =========================================
# APPLY FILTERS
# =========================================
mask = (
    (df["Order Date"].dt.date >= start_date)
    & (df["Order Date"].dt.date <= end_date)
)

if selected_products:
    mask &= df["Product"].astype(str).isin(selected_products)

if selected_cities:
    mask &= df["City"].isin(selected_cities)

filtered = df.loc[mask].copy()

if filtered.empty:
    st.title("📊 Sales Analytics Dashboard")
    st.warning("Selected filters ke liye koi sales record nahi mila.")
    st.info("Date range ya filters change karke dekho.")
    st.stop()


# =========================================
# HEADER
# =========================================
st.title("📊 Sales Trend Analysis")
st.markdown(
    '<p class="dashboard-subtitle">'
    'Real-time interactive exploration of your sales data'
    '</p>',
    unsafe_allow_html=True,
)

st.divider()


# =========================================
# KPI CARDS
# =========================================
total_sales = filtered["Sales"].sum()
total_orders = filtered["Order ID"].nunique()
total_quantity = filtered["Quantity Ordered"].sum()
average_order = total_sales / total_orders if total_orders else 0
total_products = filtered["Product"].nunique()

k1, k2, k3, k4 = st.columns(4)

k1.metric("💰 Total Revenue", f"${total_sales:,.2f}")
k2.metric("🧾 Total Orders", f"{total_orders:,}")
k3.metric("📦 Units Sold", f"{total_quantity:,.0f}")
k4.metric("🛒 Avg. Order Value", f"${average_order:,.2f}")

st.caption(
    f"Showing {len(filtered):,} records across "
    f"{total_products:,} distinct products."
)


# =========================================
# SALES TREND
# =========================================
st.markdown(
    '<div class="section-heading">📈 Revenue Overview</div>',
    unsafe_allow_html=True,
)

monthly = (
    filtered.groupby("Year-Month", as_index=False)["Sales"]
    .sum()
    .sort_values("Year-Month")
)

fig_trend = px.line(
    monthly,
    x="Year-Month",
    y="Sales",
    markers=True,
    template="plotly_dark",
    title="Monthly Revenue Trend",
    labels={"Year-Month": "Month", "Sales": "Revenue ($)"},
)

fig_trend.update_traces(
    line=dict(width=3),
    hovertemplate="%{x}<br>Revenue: $%{y:,.2f}<extra></extra>",
)
fig_trend.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=55, b=10),
)

st.plotly_chart(fig_trend, use_container_width=True)


# =========================================
# PRODUCT PERFORMANCE
# =========================================
left, right = st.columns(2)

with left:
    product_sales = (
        filtered.groupby("Product", as_index=False)["Sales"]
        .sum()
        .nlargest(10, "Sales")
        .sort_values("Sales")
    )

    fig_products = px.bar(
        product_sales,
        x="Sales",
        y="Product",
        orientation="h",
        template="plotly_dark",
        title="Top 10 Products by Revenue",
        labels={"Sales": "Revenue ($)", "Product": ""},
        text="Sales",
    )
    fig_products.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="auto",
    )
    fig_products.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig_products, use_container_width=True)

with right:
    daily = (
        filtered.groupby("Day", as_index=False)["Sales"]
        .sum()
    )

    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]
    daily["Day"] = pd.Categorical(
        daily["Day"], categories=weekday_order, ordered=True
    )
    daily = daily.sort_values("Day")

    fig_days = px.bar(
        daily,
        x="Day",
        y="Sales",
        template="plotly_dark",
        title="Revenue by Day of Week",
        labels={"Sales": "Revenue ($)", "Day": ""},
    )
    fig_days.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig_days, use_container_width=True)



left, right = st.columns(2)

with left:
    hourly = (
        filtered.groupby("Hour", as_index=False)["Sales"]
        .sum()
        .sort_values("Hour")
    )

    fig_hour = px.bar(
        hourly,
        x="Hour",
        y="Sales",
        template="plotly_dark",
        title="Revenue by Hour",
        labels={"Hour": "Hour of Day (0–23)", "Sales": "Revenue ($)"},
    )
    fig_hour.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig_hour, use_container_width=True)

with right:
    city_sales = (
        filtered.groupby("City", as_index=False)["Sales"]
        .sum()
        .nlargest(10, "Sales")
        .sort_values("Sales")
    )

    fig_city = px.bar(
        city_sales,
        x="Sales",
        y="City",
        orientation="h",
        template="plotly_dark",
        title="Top Locations by Revenue",
        labels={"Sales": "Revenue ($)", "City": ""},
    )
    fig_city.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig_city, use_container_width=True)


# =========================================
# MONTH x YEAR HEATMAP
# =========================================
st.markdown(
    '<div class="section-heading">🗓️ Seasonal Sales Patterns</div>',
    unsafe_allow_html=True,
)

heatmap_data = filtered.pivot_table(
    index="Year",
    columns="Month",
    values="Sales",
    aggfunc="sum",
    fill_value=0,
)

if not heatmap_data.empty:
    fig_heatmap = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=[str(c) for c in heatmap_data.columns],
            y=[str(i) for i in heatmap_data.index],
            colorscale="Viridis",
            colorbar=dict(title="Revenue ($)"),
            hovertemplate=(
                "Year: %{y}<br>Month: %{x}"
                "<br>Revenue: $%{z:,.2f}<extra></extra>"
            ),
        )
    )
    fig_heatmap.update_layout(
        title="Revenue by Year and Month",
        xaxis_title="Month",
        yaxis_title="Year",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)


# =========================================
# TOP PRODUCTS TABLE
# =========================================
st.markdown(
    '<div class="section-heading">🏆 Product Performance Table</div>',
    unsafe_allow_html=True,
)

product_table = (
    filtered.groupby("Product")
    .agg(
        Revenue=("Sales", "sum"),
        Units_Sold=("Quantity Ordered", "sum"),
        Orders=("Order ID", "nunique"),
    )
    .sort_values("Revenue", ascending=False)
    .reset_index()
)

product_table["Revenue"] = product_table["Revenue"].round(2)

st.dataframe(
    product_table,
    use_container_width=True,
    hide_index=True,
)


# =========================================
# DOWNLOAD REPORTS
# =========================================
st.markdown(
    '<div class="section-heading">📥 Download Reports</div>',
    unsafe_allow_html=True,
)

d1, d2 = st.columns(2)

with d1:
    st.download_button(
        "⬇ Download Filtered Sales CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales_data.csv",
        mime="text/csv",
        use_container_width=True,
    )

with d2:
    st.download_button(
        "⬇ Download Product Summary CSV",
        data=product_table.to_csv(index=False).encode("utf-8"),
        file_name="product_sales_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )


# =========================================
# BUSINESS INSIGHTS
# =========================================
st.markdown(
    '<div class="section-heading">💡 Business Insights</div>',
    unsafe_allow_html=True,
)

best_month = monthly.loc[monthly["Sales"].idxmax()]
best_product = product_table.iloc[0]

i1, i2 = st.columns(2)

with i1:
    st.info(
        f"**Best revenue month:** {best_month['Year-Month']}  \n"
        f"Revenue: ${best_month['Sales']:,.2f}"
    )

with i2:
    st.info(
        f"**Top product:** {best_product['Product']}  \n"
        f"Revenue: ${best_product['Revenue']:,.2f}"
    )

st.caption(
    "Sales Analytics Dashboard | Built with Python, "
    "Streamlit, Pandas and Plotly"
)
