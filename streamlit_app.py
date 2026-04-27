
import pandas as pd

def load_bom(file) -> pd.DataFrame:
    """Load a BoM file from CSV or Excel."""
    filename = file.name.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(file)
    elif filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    else:
        raise ValueError(f"Unsupported file type: {file.name}")


def compare_boms(
    df_old: pd.DataFrame,
    df_new: pd.DataFrame,
    part_number_col: str,
    compare_cols: list
) -> dict:
    """
    Compare two BoMs and return a dict of DataFrames representing differences.

    Returns:
        {
            "added":    parts in new but not in old,
            "removed":  parts in old but not in new,
            "modified": parts present in both but with changed field values
        }
    """
    df_old = df_old.copy()
    df_new = df_new.copy()

    # Ensure the key column is a string for safe merging
    df_old[part_number_col] = df_old[part_number_col].astype(str).str.strip()
    df_new[part_number_col] = df_new[part_number_col].astype(str).str.strip()

    old_parts = set(df_old[part_number_col])
    new_parts = set(df_new[part_number_col])

    added_parts   = new_parts - old_parts
    removed_parts = old_parts - new_parts
    common_parts  = old_parts & new_parts

    added_df   = df_new[df_new[part_number_col].isin(added_parts)].copy()
    removed_df = df_old[df_old[part_number_col].isin(removed_parts)].copy()

    # --- Find modified parts ---
    old_common = df_old[df_old[part_number_col].isin(common_parts)].set_index(part_number_col)
    new_common = df_new[df_new[part_number_col].isin(common_parts)].set_index(part_number_col)

    # Only compare columns that exist in both DataFrames
    valid_cols = [c for c in compare_cols if c in old_common.columns and c in new_common.columns]

    modified_rows = []
    for part in common_parts:
        if part not in old_common.index or part not in new_common.index:
            continue
        old_row = old_common.loc[part, valid_cols]
        new_row = new_common.loc[part, valid_cols]

        diffs = old_row != new_row
        if diffs.any():
            for col in valid_cols:
                if old_row[col] != new_row[col]:
                    modified_rows.append({
                        part_number_col: part,
                        "Field":         col,
                        "Old Value":     old_row[col],
                        "New Value":     new_row[col],
                    })

    modified_df = pd.DataFrame(modified_rows)

    return {
        "added":    added_df.reset_index(drop=True),
        "removed":  removed_df.reset_index(drop=True),
        "modified": modified_df.reset_index(drop=True),
    }


# ============================================================
# app.py
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="BoM Validator",
    page_icon="🔩",
    layout="wide"
)

st.title("🔩 Bill of Materials Validator")
st.markdown("Upload your two BoM files below, configure the comparison settings, then head to the **Report** page.")

st.divider()

# --- File Upload ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 BoM — Baseline (Old)")
    bom_old_file = st.file_uploader(
        "Upload your baseline BoM",
        type=["csv", "xlsx", "xls"],
        key="bom_old"
    )

with col2:
    st.subheader("📄 BoM — Current (New)")
    bom_new_file = st.file_uploader(
        "Upload your current BoM",
        type=["csv", "xlsx", "xls"],
        key="bom_new"
    )

# --- Preview & Configuration ---
if bom_old_file and bom_new_file:
    from utils.bom_compare import load_bom

    try:
        df_old = load_bom(bom_old_file)
        df_new = load_bom(bom_new_file)

        # Store in session state for use on report page
        st.session_state["df_old"] = df_old
        st.session_state["df_new"] = df_new

        st.divider()
        st.subheader("⚙️ Configuration")

        # Let user pick the Part Number column
        all_columns = list(df_old.columns)

        part_col = st.selectbox(
            "Select the **Part Number** column (used as the unique key):",
            options=all_columns,
            index=0
        )

        # Let user choose which columns to compare
        compare_cols = st.multiselect(
            "Select **columns to compare** for changes:",
            options=[c for c in all_columns if c != part_col],
            default=[c for c in all_columns if c != part_col]
        )

        st.session_state["part_col"]     = part_col
        st.session_state["compare_cols"] = compare_cols

        st.divider()

        # --- Previews ---
        with st.expander("👁️ Preview — Baseline BoM", expanded=False):
            st.dataframe(df_old, use_container_width=True)

        with st.expander("👁️ Preview — Current BoM", expanded=False):
            st.dataframe(df_new, use_container_width=True)

        st.success("✅ Both files loaded. Navigate to the **Report** page to see the comparison.")

    except Exception as e:
        st.error(f"❌ Error loading files: {e}")

else:
    st.info("Please upload both BoM files to continue.")


# ============================================================
# pages/2_Report.py
# ============================================================

import streamlit as st
import pandas as pd
from utils.bom_compare import compare_boms

st.set_page_config(
    page_title="BoM Report",
    page_icon="📊",
    layout="wide"
)

st.title("📊 BoM Comparison Report")

# --- Guard: Check session state ---
required_keys = ["df_old", "df_new", "part_col", "compare_cols"]
if not all(k in st.session_state for k in required_keys):
    st.warning("⚠️ No data found. Please upload your BoM files on the **Home** page first.")
    st.stop()

df_old       = st.session_state["df_old"]
df_new       = st.session_state["df_new"]
part_col     = st.session_state["part_col"]
compare_cols = st.session_state["compare_cols"]

# --- Run Comparison ---
results = compare_boms(df_old, df_new, part_col, compare_cols)

added_df    = results["added"]
removed_df  = results["removed"]
modified_df = results["modified"]

# --- Summary Metrics ---
st.subheader("📈 Summary")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Parts (Old)", len(df_old))
m2.metric("Total Parts (New)", len(df_new))
m3.metric("Parts Added",       len(added_df),   delta=f"+{len(added_df)}")
m4.metric("Parts Removed",     len(removed_df), delta=f"-{len(removed_df)}", delta_color="inverse")

st.divider()

# --- Added Parts ---
st.subheader("✅ Parts Added")
if not added_df.empty:
    st.dataframe(added_df, use_container_width=True)
else:
    st.info("No parts were added.")

st.divider()

# --- Removed Parts ---
st.subheader("❌ Parts Removed")
if not removed_df.empty:
    st.dataframe(removed_df, use_container_width=True)
else:
    st.info("No parts were removed.")

st.divider()

# --- Modified Parts ---
st.subheader(f"✏️ Parts Modified ({len(modified_df)} changes)")
if not modified_df.empty:
    st.dataframe(
        modified_df.style.applymap(
            lambda _: "background-color: #fff3cd",
            subset=["Old Value", "New Value"]
        ),
        use_container_width=True
    )
else:
    st.info("No field-level changes detected.")

st.divider()

# --- Export ---
st.subheader("📥 Export Report")

@st.cache_data
def to_excel(added, removed, modified):
    """Bundle all diff sheets into a single Excel file."""
    from io import BytesIO
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        added.to_excel(writer,    sheet_name="Added",    index=False)
        removed.to_excel(writer,  sheet_name="Removed",  index=False)
        modified.to_excel(writer, sheet_name="Modified", index=False)
    return buf.getvalue()

excel_data = to_excel(added_df, removed_df, modified_df)

st.download_button(
    label="⬇️ Download Full Report (.xlsx)",
    data=excel_data,
    file_name="bom_comparison_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
