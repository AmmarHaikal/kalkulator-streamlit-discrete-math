import ast
import csv
import io
import math
import operator as op
from datetime import datetime
import streamlit as st

# Konfigurasi halaman
st.set_page_config(
    page_title="Smart Web Calculator",
    page_icon="🧮",
    layout="centered",
)

# --- Inisialisasi State ---
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_expr" not in st.session_state:
    st.session_state.last_expr = ""
if "angka1_input" not in st.session_state:
    st.session_state.angka1_input = 0.0
if "angka2_input" not in st.session_state:
    st.session_state.angka2_input = 0.0


# --- Fungsi Evaluasi Ekspresi Matematika Aman (Tanpa eval) ---
OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": lambda x: math.sin(math.radians(x)),
    "cos": lambda x: math.cos(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "log": math.log10,
}


def safe_eval(expr: str) -> float:
    cleaned = (
        expr.replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
        .replace(",", ".")
        .strip()
    )
    if not cleaned:
        raise ValueError("Ekspresi masih kosong.")

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Pangkat terlalu besar (maksimal 1000).")
            return OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in FUNCTIONS and len(node.args) == 1:
                return FUNCTIONS[func_name](_eval(node.args[0]))
        raise ValueError("Gunakan hanya angka, operator (+, -, *, /, ^, %), dan kurung.")

    tree = ast.parse(cleaned, mode="eval")
    return float(_eval(tree.body))


def format_number(val: float) -> str:
    if val == 0:
        return "0"
    return f"{val:,.8g}"


def simpan_riwayat(mode: str, ekspresi: str, hasil: float):
    hasil_str = format_number(hasil)
    st.session_state.last_result = hasil
    st.session_state.last_expr = f"{ekspresi} = {hasil_str}"
    st.session_state.history.insert(
        0,
        {
            "Waktu": datetime.now().strftime("%H:%M:%S"),
            "Mode": mode,
            "Perhitungan": ekspresi,
            "Hasil": hasil_str,
        },
    )


def gunakan_hasil_ke_angka1():
    if st.session_state.last_result is not None:
        st.session_state.angka1_input = float(st.session_state.last_result)


# --- Sidebar Informasi Kelompok ---
with st.sidebar:
    st.header("👥 Informasi Kelompok")
    st.markdown(
        """
        **Anggota Kelompok:**
        1. Ammar Haikal Amin (021202600008)
        2. Excellent Lennoel Runtuk (021202600047)
        3. Neysa Mayluya Kesita Sinaga (021202600012)
        """
    )
    st.divider()
    st.subheader("💡 Fitur Aplikasi")
    st.markdown(
        """
        - **Kalkulator Standar:** Operasi dasar & hitung berantai otomatis.
        - **Ekspresi Cepat:** Mendukung tanda kurung `()`, pangkat `^`, dan fungsi `sqrt()`, `sin()`, `cos()`, `log()`.
        - **Ekspor CSV:** Riwayat hitungan dapat diunduh langsung.
        """
    )

# --- Header Utama ---
st.title("🧮 Smart Web Calculator")
st.caption("Aplikasi Kalkulator Berbasis Python & Streamlit")

# --- Tab Mode Kalkulator ---
tab_standar, tab_ekspresi = st.tabs(["🔢 Kalkulator Standar", "⚡ Mode Ekspresi Cepat"])

with tab_standar:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            angka1 = st.number_input("Angka Pertama", step=1.0, key="angka1_input")
        with col2:
            angka2 = st.number_input("Angka Kedua", step=1.0, key="angka2_input")

        operasi = st.segmented_control(
            "Pilih Operasi",
            options=["➕ Tambah", "➖ Kurang", "✖️ Kali", "➗ Bagi", "🔼 Pangkat", "📐 Sisa Bagi"],
            default="➕ Tambah",
        )

        if st.button("Hitung Hasil", type="primary", use_container_width=True):
            if operasi is None:
                st.warning("Silakan pilih salah satu operasi matematika terlebih dahulu.")
            else:
                hasil = None
                simbol = ""
                if operasi == "➕ Tambah":
                    hasil, simbol = angka1 + angka2, "+"
                elif operasi == "➖ Kurang":
                    hasil, simbol = angka1 - angka2, "-"
                elif operasi == "✖️ Kali":
                    hasil, simbol = angka1 * angka2, "×"
                elif operasi == "➗ Bagi":
                    if angka2 == 0:
                        st.error("Error: Pembagian dengan angka 0 tidak diperbolehkan.")
                    else:
                        hasil, simbol = angka1 / angka2, "÷"
                elif operasi == "🔼 Pangkat":
                    if abs(angka2) > 1000:
                        st.error("Error: Pangkat terlalu besar (maksimal 1000).")
                    else:
                        hasil, simbol = angka1 ** angka2, "^"
                elif operasi == "📐 Sisa Bagi":
                    if angka2 == 0:
                        st.error("Error: Modulus dengan angka 0 tidak diperbolehkan.")
                    else:
                        hasil, simbol = angka1 % angka2, "%"

                if hasil is not None:
                    ekspresi = f"{format_number(angka1)} {simbol} {format_number(angka2)}"
                    simpan_riwayat("Standar", ekspresi, hasil)
                    st.toast("Perhitungan berhasil!", icon="✅")

with tab_ekspresi:
    with st.container(border=True):
        rumus = st.text_input(
            "Ketik Ekspresi Matematika",
            placeholder="Contoh: (250000 * 0.15) + sqrt(144)",
        )
        if st.button("Evaluasi Rumus", type="primary", use_container_width=True):
            try:
                hasil_expr = safe_eval(rumus)
                simpan_riwayat("Ekspresi", rumus, hasil_expr)
                st.toast("Rumus berhasil dihitung!", icon="⚡")
            except ZeroDivisionError:
                st.error("Error: Terdapat pembagian dengan angka 0 pada rumus.")
            except Exception as err:
                st.error(f"Error: {err}")

# --- Kartu Tampilan Hasil Utama ---
if st.session_state.last_result is not None:
    with st.container(border=True):
        col_res, col_btn = st.columns([2, 1], vertical_alignment="center")
        with col_res:
            st.metric(
                label=f"Hasil Terakhir ({st.session_state.last_expr})",
                value=format_number(st.session_state.last_result),
            )
        with col_btn:
            st.button(
                "🔄 Lanjut Hitung",
                help="Masukkan hasil ini ke Angka Pertama untuk hitungan berikutnya",
                on_click=gunakan_hasil_ke_angka1,
                use_container_width=True,
            )

# --- Tabel Riwayat & Ekspor CSV ---
if st.session_state.history:
    st.divider()
    st.subheader("📜 Riwayat Perhitungan")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

    # Siapkan file CSV di memori untuk tombol download
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer, fieldnames=["Waktu", "Mode", "Perhitungan", "Hasil"]
    )
    writer.writeheader()
    writer.writerows(st.session_state.history)

    col_dl, col_clr = st.columns(2)
    with col_dl:
        st.download_button(
            label="📥 Download Riwayat (CSV)",
            data=csv_buffer.getvalue(),
            file_name="riwayat_kalkulator.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_clr:
        if st.button("🗑️ Hapus Riwayat", use_container_width=True):
            st.session_state.history = []
            st.session_state.last_result = None
            st.session_state.last_expr = ""
            st.rerun()