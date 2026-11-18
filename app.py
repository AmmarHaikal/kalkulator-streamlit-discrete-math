import ast
import csv
import io
import math
import operator as op
import re
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="Smart Web Calculator",
    page_icon="🧮",
    layout="centered",
)

# --- CSS agar grid tombol tetap rapi sejajar di HP maupun Laptop ---
st.markdown(
    """
    <style>
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
    }
    div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
    div.stButton > button {
        white-space: nowrap !important;
        padding: 0.45rem 0.25rem !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Inisialisasi State ---
if "expression" not in st.session_state:
    st.session_state.expression = ""
if "input_ver" not in st.session_state:
    st.session_state.input_ver = 0
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_expr" not in st.session_state:
    st.session_state.last_expr = ""
if "error_msg" not in st.session_state:
    st.session_state.error_msg = ""
if "history" not in st.session_state:
    st.session_state.history = []

# --- Evaluasi Ekspresi Matematika Aman ---
OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.FloorDiv: op.floordiv,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _safe_sqrt(x: float) -> float:
    if x < 0:
        raise ValueError("Akar kuadrat dari bilangan negatif tidak terdefinisi.")
    return math.sqrt(x)


def _safe_root(x: float, n: float) -> float:
    if n == 0:
        raise ValueError("Akar ke-0 tidak terdefinisi.")
    if x < 0:
        if float(n).is_integer() and int(n) % 2 == 1:
            return math.copysign(abs(x) ** (1 / n), x)
        raise ValueError("Akar genap dari bilangan negatif tidak terdefinisi.")
    return x ** (1 / n)


FUNCTIONS_1_ARG = {
    "sqrt": _safe_sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "abs": abs,
    "round": round,
}

FUNCTIONS_2_ARGS = {
    "root": _safe_root,
    "mod": op.mod,
}


def format_number(val: float) -> str:
    if abs(val) < 1e-12:
        return "0"
    return f"{val:,.10g}"


def safe_eval(raw_expr: str) -> float:
    cleaned = (
        raw_expr.replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
        .replace(",", ".")
        .strip()
    )
    if not cleaned:
        raise ValueError("Masukkan angka atau operasi perhitungan terlebih dahulu.")

    # Ubah simbol √angka atau √(...) menjadi sqrt(...)
    cleaned = re.sub(r"√\s*\(", "sqrt(", cleaned)
    cleaned = re.sub(r"√\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", cleaned)

    # Ubah persen: 50% -> (50/100), (10+20)% -> ((10+20)/100)
    cleaned = re.sub(r"(\d+(?:\.\d+)?|\))%", r"(\1/100)", cleaned)

    # Perkalian implisit: 2(3+4) -> 2*(3+4), 2sqrt(9) -> 2*sqrt(9), 2Ans -> 2*Ans
    cleaned = re.sub(r"(\d)\s*\(", r"\1*(", cleaned)
    cleaned = re.sub(r"\)\s*(\d)", r")*\1", cleaned)
    cleaned = re.sub(r"\)\s*\(", r")*(", cleaned)
    cleaned = re.sub(
        r"(\d)\s*(sqrt|cbrt|root|abs|round|mod|ans)\b",
        r"\1*\2",
        cleaned,
        flags=re.IGNORECASE,
    )

    constants = {
        "ans": float(st.session_state.last_result) if st.session_state.last_result is not None else 0.0,
    }

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            name_lower = node.id.lower()
            if name_lower in constants:
                return constants[name_lower]
            raise ValueError(f"Simbol '{node.id}' tidak dikenali.")
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Pangkat terlalu besar (maksimal 1000).")
            res = OPERATORS[type(node.op)](left, right)
            if isinstance(res, complex):
                raise ValueError("Hasil berupa bilangan imajiner (akar genap dari bilangan negatif).")
            return res
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in FUNCTIONS_1_ARG and len(node.args) == 1:
                return FUNCTIONS_1_ARG[func_name](_eval(node.args[0]))
            if func_name in FUNCTIONS_2_ARGS and len(node.args) == 2:
                return FUNCTIONS_2_ARGS[func_name](_eval(node.args[0]), _eval(node.args[1]))
        raise ValueError("Format ekspresi matematika tidak valid.")

    tree = ast.parse(cleaned, mode="eval")
    return float(_eval(tree.body))


# --- Helper & Callback Tombol ---
def get_current_text() -> str:
    widget_key = f"input_{st.session_state.input_ver}"
    return st.session_state.get(widget_key, st.session_state.expression)


def sync_from_typing():
    st.session_state.expression = get_current_text()


def append_token(token: str):
    curr = get_current_text()
    st.session_state.expression = curr + token
    st.session_state.error_msg = ""
    st.session_state.input_ver += 1


def backspace_token():
    curr = get_current_text()
    if curr.endswith("√("):
        curr = curr[:-2]
    elif curr.lower().endswith("ans"):
        curr = curr[:-3]
    else:
        curr = curr[:-1]
    st.session_state.expression = curr
    st.session_state.error_msg = ""
    st.session_state.input_ver += 1


def clear_all():
    st.session_state.expression = ""
    st.session_state.last_result = None
    st.session_state.last_expr = ""
    st.session_state.error_msg = ""
    st.session_state.input_ver += 1


def hitung_ekspresi():
    ekspresi = get_current_text().strip()
    st.session_state.expression = ekspresi
    if not ekspresi:
        st.session_state.error_msg = "Silakan masukkan perhitungan terlebih dahulu."
        return
    try:
        hasil = safe_eval(ekspresi)
        hasil_str = format_number(hasil)
        st.session_state.last_result = hasil
        st.session_state.last_expr = ekspresi
        st.session_state.error_msg = ""
        st.session_state.history.insert(
            0,
            {
                "Waktu": datetime.now().strftime("%H:%M:%S"),
                "Ekspresi": ekspresi,
                "Hasil": hasil_str,
            },
        )
    except ZeroDivisionError:
        st.session_state.error_msg = "Error: Pembagian dengan angka 0 tidak diperbolehkan."
    except SyntaxError:
        st.session_state.error_msg = "Error: Penulisan tanda kurung atau operator belum lengkap."
    except Exception as err:
        st.session_state.error_msg = f"Error: {err}"


def lanjut_dengan_hasil():
    if st.session_state.last_result is not None:
        st.session_state.expression = format_number(st.session_state.last_result).replace(",", "")
        st.session_state.error_msg = ""
        st.session_state.input_ver += 1


# --- Sidebar Info Kelompok ---
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
    st.subheader("📖 Panduan Singkat")
    st.markdown(
        """
        - **Banyak Angka:** Bebas gabung operasi, misal `12+8*5-4/2`
        - **Pangkat & Akar:** Gunakan `^` (misal `2^5`, `16^(1/2)`, `27^(1/3)`), simbol `√(144)`, atau `root(27, 3)`
        - **Persen:** Ketik langsung dengan `%`, misalnya `250000*15%`
        - **Hitung Lanjutan:** Gunakan `Ans` atau tombol **Gunakan Hasil**
        """
    )

# --- Tampilan Utama Kalkulator ---
st.title("🧮 Smart Web Calculator")
st.caption("Kalkulator Multi-Operasi Berbasis Python & Streamlit")

with st.container(border=True):
    st.text_input(
        "Layar Perhitungan (bisa ketik langsung atau klik tombol di bawah):",
        value=st.session_state.expression,
        key=f"input_{st.session_state.input_ver}",
        on_change=sync_from_typing,
        placeholder="Contoh: (125000*20%) + 16^(1/2) + √(81)",
    )

    # Tampilan Hasil atau Error
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
    elif st.session_state.last_result is not None:
        col_res, col_ans = st.columns([2.5, 1.2], vertical_alignment="center")
        with col_res:
            st.metric(
                label=f"Hasil: {st.session_state.last_expr}",
                value=format_number(st.session_state.last_result),
            )
        with col_ans:
            st.button(
                "Pakai Hasil",
                on_click=lanjut_dengan_hasil,
                use_container_width=True,
                help="Masukkan hasil ini ke layar untuk hitungan lanjutan",
            )

    st.divider()

    # Baris Fungsi Tambahan (Pangkat, Akar, Persen, Kurung)
    f1, f2, f3, f4, f5 = st.columns(5)
    f1.button("(", on_click=append_token, args=("(",), use_container_width=True)
    f2.button(")", on_click=append_token, args=(")",), use_container_width=True)
    f3.button("xʸ (^)", on_click=append_token, args=("^",), use_container_width=True)
    f4.button("√", on_click=append_token, args=("√(",), use_container_width=True)
    f5.button("%", on_click=append_token, args=("%",), use_container_width=True)

    # Keypad Angka & Operator Utama (tanpa spasi berlebih)
    r1 = st.columns(4)
    r1[0].button("7", on_click=append_token, args=("7",), use_container_width=True)
    r1[1].button("8", on_click=append_token, args=("8",), use_container_width=True)
    r1[2].button("9", on_click=append_token, args=("9",), use_container_width=True)
    r1[3].button("÷", on_click=append_token, args=("÷",), use_container_width=True)

    r2 = st.columns(4)
    r2[0].button("4", on_click=append_token, args=("4",), use_container_width=True)
    r2[1].button("5", on_click=append_token, args=("5",), use_container_width=True)
    r2[2].button("6", on_click=append_token, args=("6",), use_container_width=True)
    r2[3].button("×", on_click=append_token, args=("×",), use_container_width=True)

    r3 = st.columns(4)
    r3[0].button("1", on_click=append_token, args=("1",), use_container_width=True)
    r3[1].button("2", on_click=append_token, args=("2",), use_container_width=True)
    r3[2].button("3", on_click=append_token, args=("3",), use_container_width=True)
    r3[3].button("-", on_click=append_token, args=("-",), use_container_width=True)

    r4 = st.columns(4)
    r4[0].button("0", on_click=append_token, args=("0",), use_container_width=True)
    r4[1].button(".", on_click=append_token, args=(".",), use_container_width=True)
    r4[2].button("Ans", on_click=append_token, args=("Ans",), use_container_width=True)
    r4[3].button("+", on_click=append_token, args=("+",), use_container_width=True)

    # Baris Kontrol (AC, Backspace, Hitung)
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.button("AC", on_click=clear_all, use_container_width=True)
    c2.button("⌫", on_click=backspace_token, use_container_width=True)
    c3.button("=", type="primary", on_click=hitung_ekspresi, use_container_width=True)

# --- Riwayat Perhitungan ---
if st.session_state.history:
    st.subheader("📜 Riwayat Perhitungan")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["Waktu", "Ekspresi", "Hasil"])
    writer.writeheader()
    writer.writerows(st.session_state.history)

    dl_col, clr_col = st.columns(2)
    with dl_col:
        st.download_button(
            "📥 Download CSV",
            data=csv_buffer.getvalue(),
            file_name="riwayat_kalkulator.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with clr_col:
        if st.button("🗑️ Hapus Riwayat", use_container_width=True):
            st.session_state.history = []
            st.session_state.last_result = None
            st.session_state.last_expr = ""
            st.rerun()
