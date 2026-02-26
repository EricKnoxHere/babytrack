"""Dashboard - Charts and past reports."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from ui import api_client as api


def render():
    """Render the dashboard page."""
    
    baby = st.session_state.get("selected_baby")
    if not baby:
        st.error("No baby selected")
        return
    
    st.title(f"📊 Dashboard – {baby['name']}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # Time period selector
    # ──────────────────────────────────────────────────────────────────────────
    
    col_period, col_end = st.columns([2, 1])
    
    with col_period:
        period_opts = {
            "7 days": 7,
            "14 days": 14,
            "30 days": 30,
            "90 days": 90,
            "All time": None,
        }
        selected_period = st.selectbox("Period", list(period_opts.keys()), key="dash_period")
        days = period_opts[selected_period]
    
    with col_end:
        end_date = st.date_input("Up to", value=date.today(), key="dash_end_date")
    
    if days:
        start_date = end_date - timedelta(days=days - 1)
    else:
        start_date = date(2020, 1, 1)
    
    # ──────────────────────────────────────────────────────────────────────────
    # Load data
    # ──────────────────────────────────────────────────────────────────────────
    
    try:
        feedings = api.get_feedings(baby["id"], start=start_date, end=end_date)
        weights = api.get_weights(baby["id"])
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return
    
    if not feedings:
        st.info("No feedings recorded for this period.")
        return
    
    # Metrics
    total_ml = sum(f["quantity_ml"] for f in feedings)
    avg_per_day = total_ml / days if days else (total_ml / len(set(f["fed_at"][:10] for f in feedings)))
    avg_per_feeding = total_ml / len(feedings)
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Total volume", f"{total_ml} ml")
    m_col2.metric("Daily average", f"{avg_per_day:.0f} ml")
    m_col3.metric("Per feeding", f"{avg_per_feeding:.0f} ml")
    m_col4.metric("Feedings", len(feedings))
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Charts
    # ──────────────────────────────────────────────────────────────────────────
    
    # Aggregate by day
    from collections import defaultdict
    daily = defaultdict(lambda: {"total_ml": 0, "count": 0})
    for f in feedings:
        day = f["fed_at"][:10]
        daily[day]["total_ml"] += f["quantity_ml"]
        daily[day]["count"] += 1
    
    day_range = [
        (start_date + timedelta(days=i)).isoformat()
        for i in range((end_date - start_date).days + 1)
    ]
    
    vol_data = [daily[d]["total_ml"] for d in day_range]
    count_data = [daily[d]["count"] for d in day_range]
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_vol = go.Figure(data=[
            go.Bar(
                x=day_range,
                y=vol_data,
                marker_color="#3b82f6",
                text=vol_data,
                textposition="outside",
                name="Volume (ml)",
            )
        ])
        fig_vol.update_layout(
            title="Volume per day",
            xaxis_title="Date",
            yaxis_title="ml",
            height=400,
            showlegend=False,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig_vol, use_container_width=True)
    
    with col_chart2:
        fig_count = go.Figure(data=[
            go.Bar(
                x=day_range,
                y=count_data,
                marker_color="#10b981",
                text=count_data,
                textposition="outside",
                name="Feedings",
            )
        ])
        fig_count.update_layout(
            title="Feedings per day",
            xaxis_title="Date",
            yaxis_title="Count",
            height=400,
            showlegend=False,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig_count, use_container_width=True)
    
    # Feeding type breakdown
    type_counts = {
        "🍼 Bottle": sum(1 for f in feedings if f["feeding_type"] == "bottle"),
        "🤱 Breastfeeding": sum(1 for f in feedings if f["feeding_type"] == "breastfeeding"),
    }
    
    fig_pie = go.Figure(data=[
        go.Pie(
            labels=list(type_counts.keys()),
            values=list(type_counts.values()),
            marker_colors=["#3b82f6", "#f59e0b"],
        )
    ])
    fig_pie.update_layout(
        title="Feeding types",
        height=400,
        margin=dict(t=50, b=30),
    )
    
    col_pie, col_recent = st.columns([1, 1.2])
    
    with col_pie:
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_recent:
        st.subheader("📋 Recent feedings")
        recent = sorted(feedings, key=lambda x: x["fed_at"], reverse=True)[:8]
        for f in recent:
            time_str = datetime.fromisoformat(f["fed_at"]).strftime("%d/%m %H:%M")
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            st.markdown(f"{icon} `{time_str}` **{f['quantity_ml']}ml**")
            if f.get("notes"):
                st.caption(f"_{f['notes']}_")
    
    # Weight curve
    st.divider()
    st.subheader("⚖️ Growth curve")
    
    if weights:
        w_dates = [datetime.fromisoformat(w["measured_at"]).strftime("%d/%m") for w in weights]
        w_values = [w["weight_g"] for w in weights]
        
        fig_growth = go.Figure(data=[
            go.Scatter(
                x=w_dates,
                y=w_values,
                mode="lines+markers",
                line=dict(color="#3b82f6", width=3),
                marker=dict(size=8),
            )
        ])
        fig_growth.update_layout(
            title="Weight over time",
            xaxis_title="Date",
            yaxis_title="Weight (g)",
            height=400,
            showlegend=False,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig_growth, use_container_width=True)
        
        if len(weights) >= 2:
            gain = weights[-1]["weight_g"] - weights[0]["weight_g"]
            st.info(f"📈 Total gain: **+{gain}g** ({weights[0]['weight_g']}g → {weights[-1]['weight_g']}g)")
    else:
        st.info("No weight measurements yet. Log them in Home.")
    
    # ──────────────────────────────────────────────────────────────────────────
    # Past AI reports
    # ──────────────────────────────────────────────────────────────────────────
    
    st.divider()
    st.subheader("🤖 Past AI analyses")
    
    try:
        reports = api.list_analysis_history(baby["id"], limit=10)
    except Exception:
        reports = []
    
    if not reports:
        st.info("No analyses saved yet. Go to the Chat page to create one.")
    else:
        for report in reports:
            created = datetime.fromisoformat(report["created_at"])
            badge = "🕐" if report.get("is_partial") else "✅"
            label = f"{badge} {report['period_label']} · {created.strftime('%d/%m %H:%M')}"
            
            with st.expander(label):
                try:
                    full = api.get_analysis_report(baby["id"], report["id"])
                    st.markdown(full["analysis"])
                    if full.get("sources"):
                        st.caption("📚 Sources: " + ", ".join(s["source"] for s in full["sources"]))
                except Exception as e:
                    st.error(f"Could not load: {e}")
                
                if st.button("🗑️", key=f"del_report_{report['id']}", help="Delete"):
                    try:
                        api.delete_analysis_report(baby["id"], report["id"])
                        st.rerun()
                    except Exception:
                        pass
