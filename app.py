# app.py
# Smart AI Refrigerator: Automatic Grocery Detection and Reordering
# Run: streamlit run app.py

from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st


# =============================================================================
# MOCK DATA
# =============================================================================

INITIAL_INVENTORY = [
    {"item": "Milk", "category": "Dairy", "quantity": 2, "unit": "pack", "min_stock": 2, "reorder_qty": 4, "essential": True, "expiry_date": date.today() + timedelta(days=2)},
    {"item": "Curd", "category": "Dairy", "quantity": 3, "unit": "cup", "min_stock": 1, "reorder_qty": 3, "essential": True, "expiry_date": date.today() + timedelta(days=4)},
    {"item": "Paneer", "category": "Dairy", "quantity": 1, "unit": "pack", "min_stock": 1, "reorder_qty": 2, "essential": False, "expiry_date": date.today() + timedelta(days=5)},
    {"item": "Tomato", "category": "Vegetable", "quantity": 4, "unit": "pcs", "min_stock": 3, "reorder_qty": 6, "essential": True, "expiry_date": date.today() + timedelta(days=3)},
    {"item": "Potato", "category": "Vegetable", "quantity": 8, "unit": "pcs", "min_stock": 3, "reorder_qty": 5, "essential": True, "expiry_date": date.today() + timedelta(days=8)},
    {"item": "Spinach", "category": "Vegetable", "quantity": 1, "unit": "bunch", "min_stock": 2, "reorder_qty": 3, "essential": True, "expiry_date": date.today() + timedelta(days=1)},
    {"item": "Apple", "category": "Fruit", "quantity": 5, "unit": "pcs", "min_stock": 2, "reorder_qty": 4, "essential": False, "expiry_date": date.today() + timedelta(days=6)},
    {"item": "Banana", "category": "Fruit", "quantity": 3, "unit": "pcs", "min_stock": 2, "reorder_qty": 5, "essential": True, "expiry_date": date.today() + timedelta(days=2)},
    {"item": "Pasta", "category": "Packed", "quantity": 4, "unit": "pack", "min_stock": 1, "reorder_qty": 3, "essential": False, "expiry_date": date.today() + timedelta(days=90)},
    {"item": "Juice", "category": "Packed", "quantity": 2, "unit": "bottle", "min_stock": 2, "reorder_qty": 4, "essential": False, "expiry_date": date.today() + timedelta(days=30)},
]


class MockGroceryPlatform:
    """Replace this class with a real grocery-platform adapter later."""

    name = "FreshCart"

    def place_order(self, item: str, quantity: int, order_type: str) -> dict:
        return {
            "order_id": f"FC-{random.randint(10000, 99999)}",
            "item": item,
            "quantity": quantity,
            "type": order_type,
            "status": "Placed",
            "created_at": datetime.now(),
            "platform": self.name,
        }


# =============================================================================
# LOGIC
# =============================================================================

def initialize_state() -> None:
    if "inventory" not in st.session_state:
        st.session_state.inventory = pd.DataFrame(INITIAL_INVENTORY)
    if "orders" not in st.session_state:
        st.session_state.orders = []
    if "auto_reorder" not in st.session_state:
        st.session_state.auto_reorder = True
    if "last_low_items" not in st.session_state:
        st.session_state.last_low_items = set()
    if "pending_order" not in st.session_state:
        st.session_state.pending_order = None
    if "last_simulation" not in st.session_state:
        st.session_state.last_simulation = time.time()
    if "platform" not in st.session_state:
        st.session_state.platform = MockGroceryPlatform()


def item_status(row: pd.Series) -> str:
    days = (row["expiry_date"] - date.today()).days
    if row["quantity"] <= row["min_stock"]:
        return "Low"
    if days < 0:
        return "Expired"
    if days <= 3:
        return "Expiring"
    return "Fresh"


def refresh_order_statuses() -> None:
    """Advance mock delivery statuses based on elapsed wall-clock time."""
    now = datetime.now()
    for order in st.session_state.orders:
        elapsed = (now - order["created_at"]).total_seconds()
        if elapsed >= 35:
            order["status"] = "Delivered"
        elif elapsed >= 12:
            order["status"] = "Out for delivery"


def place_order(item: str, quantity: int, order_type: str) -> None:
    order = st.session_state.platform.place_order(item, quantity, order_type)
    st.session_state.orders.insert(0, order)
    idx = st.session_state.inventory.index[
        st.session_state.inventory["item"] == item
    ]
    if len(idx):
        st.session_state.inventory.loc[idx[0], "quantity"] += quantity
    st.toast(f"{item}: order placed on FreshCart", icon="🛒")


def check_auto_reorder() -> None:
    """Automatically order essential items; queue non-essential items for approval."""
    inventory = st.session_state.inventory
    for idx, row in inventory.iterrows():
        if row["quantity"] > row["min_stock"]:
            continue
        item = row["item"]
        already_pending = (
            st.session_state.pending_order is not None
            and st.session_state.pending_order["item"] == item
        )
        already_ordered = any(
            o["item"] == item and (datetime.now() - o["created_at"]).total_seconds() < 60
            for o in st.session_state.orders
        )
        if already_pending or already_ordered:
            continue

        if bool(row["essential"]) and st.session_state.auto_reorder:
            place_order(item, int(row["reorder_qty"]), "Auto")
        elif st.session_state.pending_order is None:
            st.session_state.pending_order = {
                "item": item,
                "quantity": int(row["reorder_qty"]),
                "reason": "Essential item with Auto-Reorder OFF" if row["essential"] else "Non-essential item",
            }


def simulate_consumption() -> None:
    """Small mock consumption changes; called by the live inventory fragment."""
    now = time.time()
    if now - st.session_state.last_simulation < 4:
        return
    st.session_state.last_simulation = now
    inv = st.session_state.inventory
    eligible = inv.index[inv["quantity"] > 0].tolist()
    if eligible and random.random() < 0.65:
        idx = random.choice(eligible)
        inv.loc[idx, "quantity"] = max(0, int(inv.loc[idx, "quantity"]) - 1)


def mock_scan_expiry(uploaded_file) -> date:
    """Mock OCR: return a plausible future expiry date without external services."""
    return date.today() + timedelta(days=random.randint(7, 180))


def status_color(status: str) -> str:
    return {
        "Fresh": "#dcfce7",
        "Expiring": "#fef3c7",
        "Low": "#fee2e2",
        "Expired": "#fecaca",
    }.get(status, "#f3f4f6")


# =============================================================================
# UI
# =============================================================================

st.set_page_config(
    page_title="Smart AI Refrigerator",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
initialize_state()
refresh_order_statuses()

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1250px;}
    [data-testid="stMetric"] {background: #f8fafc; border: 1px solid #e2e8f0;
        padding: 14px 16px; border-radius: 14px;}
    .status-pill {padding: 4px 10px; border-radius: 20px; font-size: 0.82rem;
        font-weight: 600; display: inline-block;}
    div[data-testid="stTabs"] button {font-weight: 600;}
    @media (max-width: 640px) {
        .block-container {padding-left: 0.8rem; padding-right: 0.8rem;}
        h1 {font-size: 1.65rem !important;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
header_left, header_mid, header_right = st.columns([5, 1.4, 2])
with header_left:
    st.title("🧊 Smart AI Refrigerator")
    st.caption("Automatic Grocery Detection and Reordering")
with header_mid:
    st.markdown("### 🟢 Online")
    st.caption("Fridge status")
with header_right:
    st.session_state.auto_reorder = st.toggle(
        "Auto-Reorder", value=st.session_state.auto_reorder, key="auto_reorder_toggle"
    )
    st.caption("Master switch — can be turned off anytime")

st.divider()

# Summary cards
inventory = st.session_state.inventory.copy()
inventory["status"] = inventory.apply(item_status, axis=1)
low_count = int((inventory["quantity"] <= inventory["min_stock"]).sum())
expiring_count = int(
    inventory["expiry_date"].apply(lambda d: 0 <= (d - date.today()).days <= 3).sum()
)
week_ago = datetime.now() - timedelta(days=7)
weekly_orders = sum(o["created_at"] >= week_ago for o in st.session_state.orders)

st.subheader("Overview")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total items", len(inventory))
m2.metric("Low stock", low_count, delta=None)
m3.metric("Expiring soon", expiring_count, help="Expiry date is within the next 3 days")
m4.metric("Auto-orders this week", sum(
    o["type"] == "Auto" and o["created_at"] >= week_ago
    for o in st.session_state.orders
))

# Live inventory
st.subheader("📦 Live Inventory")
search_col, category_col = st.columns([2, 1])
with search_col:
    search_text = st.text_input("Search inventory", placeholder="Search by item name...")
with category_col:
    category_filter = st.selectbox(
        "Category", ["All", "Dairy", "Vegetable", "Fruit", "Packed"]
    )

@st.fragment(run_every="5s")
def live_inventory_panel():
    simulate_consumption()
    check_auto_reorder()
    current = st.session_state.inventory.copy()
    current["status"] = current.apply(item_status, axis=1)
    # Toast only when an item newly enters low-stock state.
    current_low = set(current.loc[current["quantity"] <= current["min_stock"], "item"])
    newly_low = current_low - st.session_state.last_low_items
    for item in newly_low:
        st.toast(f"{item} is running low", icon="⚠️")
    st.session_state.last_low_items = current_low

    shown = current.copy()
    if search_text:
        shown = shown[shown["item"].str.contains(search_text, case=False, na=False)]
    if category_filter != "All":
        shown = shown[shown["category"] == category_filter]
    shown["days_left"] = shown["expiry_date"].apply(lambda d: (d - date.today()).days)
    shown = shown.rename(columns={
        "item": "Item", "category": "Category", "quantity": "Quantity",
        "unit": "Unit", "status": "Status", "days_left": "Days left",
    })
    display_cols = ["Item", "Category", "Quantity", "Unit", "Status", "Days left"]
    styled = shown[display_cols].style.map(
        lambda value: f"background-color: {status_color(str(value))}; font-weight: 600;"
        if value in ["Fresh", "Expiring", "Low", "Expired"] else "",
        subset=["Status"],
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Inventory consumption is simulated every few seconds. Quantities may change automatically.")

live_inventory_panel()

# Low stock alerts
st.subheader("🚨 Low Stock Alerts")
low_items = st.session_state.inventory[
    st.session_state.inventory["quantity"] <= st.session_state.inventory["min_stock"]
]
if low_items.empty:
    st.success("All items are above their minimum stock levels.")
else:
    for _, row in low_items.iterrows():
        a, b, c = st.columns([3, 2, 1])
        a.markdown(f"**{row['item']}**  ·  {row['category']}")
        b.caption(f"{int(row['quantity'])} {row['unit']} left · threshold {int(row['min_stock'])}")
        if c.button("Reorder now", key=f"manual_{row['item']}"):
            place_order(row["item"], int(row["reorder_qty"]), "Manual")
            st.rerun()

# Non-essential / auto-off confirmation prompt
if st.session_state.pending_order:
    pending = st.session_state.pending_order
    st.warning(
        f"Order approval needed: **{pending['item']}** — "
        f"{pending['quantity']} units. {pending['reason']}."
    )
    yes, no = st.columns(2)
    if yes.button("Confirm order", type="primary", key="confirm_pending"):
        place_order(pending["item"], pending["quantity"], "Manual")
        st.session_state.pending_order = None
        st.rerun()
    if no.button("Cancel", key="cancel_pending"):
        st.session_state.pending_order = None
        st.info("Pending order cancelled.")

# Expiry tracking
st.subheader("🗓️ Expiry Tracking")
packed_tab, fresh_tab = st.tabs(["Packed items · Scan expiry", "Vegetables & fruits"])
with packed_tab:
    st.write("Upload a package photo or use your camera. The OCR step is mocked for this demo.")
    packed_names = st.session_state.inventory.loc[
        st.session_state.inventory["category"] == "Packed", "item"
    ].tolist()
    if packed_names:
        selected_packed = st.selectbox("Packed item", packed_names, key="packed_select")
        camera_file = st.camera_input("Take a package photo", key="expiry_camera")
        uploaded_file = st.file_uploader(
            "Or upload a package image", type=["png", "jpg", "jpeg"], key="expiry_upload"
        )
        if st.button("Scan Expiry", key="scan_expiry"):
            if camera_file is None and uploaded_file is None:
                st.info("Add a photo first. The mock scanner will then estimate an expiry date.")
            else:
                detected_date = mock_scan_expiry(camera_file or uploaded_file)
                item_idx = st.session_state.inventory.index[
                    st.session_state.inventory["item"] == selected_packed
                ][0]
                st.session_state.inventory.loc[item_idx, "expiry_date"] = detected_date
                st.success(f"Mock OCR detected expiry date: {detected_date:%d %b %Y}")
    else:
        st.info("No packed items are currently in inventory.")

with fresh_tab:
    with st.form("fresh_expiry_form"):
        fresh_names = st.session_state.inventory.loc[
            st.session_state.inventory["category"].isin(["Vegetable", "Fruit"]), "item"
        ].tolist()
        chosen_fresh = st.selectbox("Item", fresh_names if fresh_names else ["Tomato"])
        fresh_days = st.number_input("Stays fresh for (days)", min_value=1, max_value=60, value=5)
        submitted = st.form_submit_button("Calculate expiry")
    if submitted:
        calculated = date.today() + timedelta(days=int(fresh_days))
        if chosen_fresh in st.session_state.inventory["item"].values:
            idx = st.session_state.inventory.index[
                st.session_state.inventory["item"] == chosen_fresh
            ][0]
            st.session_state.inventory.loc[idx, "expiry_date"] = calculated
        days_left = (calculated - date.today()).days
        st.success(f"{chosen_fresh} expiry date: {calculated:%d %b %Y} · {days_left} days left")
        st.progress(min(1.0, days_left / 30), text=f"{days_left} days remaining")

# Auto-reorder settings
st.subheader("⚙️ Auto-Reorder Settings")
st.caption("Edit essential status, minimum stock and reorder quantity. Essential items reorder without confirmation when Auto-Reorder is ON.")
editable_cols = ["item", "category", "quantity", "essential", "min_stock", "reorder_qty"]
edited = st.data_editor(
    st.session_state.inventory[editable_cols],
    use_container_width=True,
    hide_index=True,
    disabled=["item", "category", "quantity"],
    column_config={
        "essential": st.column_config.CheckboxColumn("Essential"),
        "min_stock": st.column_config.NumberColumn("Min stock", min_value=0, step=1),
        "reorder_qty": st.column_config.NumberColumn("Reorder quantity", min_value=1, step=1),
    },
    key="settings_editor",
)
if st.button("Save reorder settings"):
    for col in ["essential", "min_stock", "reorder_qty"]:
        st.session_state.inventory[col] = edited[col].values
    st.success("Reorder settings saved.")
    check_auto_reorder()
    st.rerun()

# Orders section
st.subheader("🛒 Orders")
st.markdown(f"**Connected grocery platform:** {st.session_state.platform.name}")
refresh_order_statuses()
if st.session_state.orders:
    latest = st.session_state.orders[0]
    status_icon = {"Placed": "🟡", "Out for delivery": "🚚", "Delivered": "🟢"}
    st.info(
        f"{status_icon.get(latest['status'], '📦')} Latest order **{latest['order_id']}** — "
        f"{latest['item']} × {latest['quantity']} · **{latest['status']}**"
    )
    order_df = pd.DataFrame(st.session_state.orders)
    order_df["created_at"] = order_df["created_at"].dt.strftime("%d %b %Y, %I:%M:%S %p")
    order_df = order_df.rename(columns={
        "order_id": "Order ID", "item": "Item", "quantity": "Quantity",
        "type": "Type", "status": "Status", "created_at": "Ordered at",
        "platform": "Platform",
    })
    st.dataframe(
        order_df[["Order ID", "Item", "Quantity", "Type", "Status", "Ordered at", "Platform"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("No orders yet. Low-stock items will appear here when reordered.")

# Simple inventory mix chart
with st.expander("View inventory breakdown"):
    chart_data = st.session_state.inventory.groupby("category", as_index=False)["quantity"].sum()
    fig = px.pie(chart_data, names="category", values="quantity", hole=0.55,
                 title="Current stock by category")
    fig.update_layout(margin=dict(t=45, b=10, l=10, r=10), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Demo only · Mock inventory, simulated consumption, mock OCR and FreshCart orders. No external API calls.")
