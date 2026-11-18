import ast
import csv
from fractions import Fraction
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

# --- CSS to keep keypad buttons aligned in rows on both mobile and desktop ---
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
        padding: 0.45rem 0.2rem !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- State Initialization ---
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

# --- Safe Mathematical Expression Evaluator ---
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
        raise ValueError("Square root of a negative number is undefined in real numbers.")
    return math.sqrt(x)


def _safe_root(x: float, n: float) -> float:
    if n == 0:
        raise ValueError("0-th root is undefined.")
    if x < 0:
        if float(n).is_integer() and int(n) % 2 == 1:
            return math.copysign(abs(x) ** (1 / n), x)
        raise ValueError("Even root of a negative number is undefined in real numbers.")
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
        raise ValueError("Please enter a mathematical expression first.")

    # Convert √(...) or √number into sqrt(...)
    cleaned = re.sub(r"√\s*\(", "sqrt(", cleaned)
    cleaned = re.sub(r"√\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", cleaned)

    # Convert percentage: 50% -> (50/100), (10+20)% -> ((10+20)/100)
    cleaned = re.sub(r"(\d+(?:\.\d+)?|\))%", r"(\1/100)", cleaned)

    # Implicit multiplication: 2(3+4) -> 2*(3+4), 2sqrt(9) -> 2*sqrt(9), 2Ans -> 2*Ans
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
            raise ValueError(f"Unrecognized symbol '{node.id}'.")
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000:
                    raise ValueError("Exponent is too large (maximum 1000).")
                if left < 0 and not float(right).is_integer():
                    frac = Fraction(right).limit_denominator(1000)
                    if abs(float(frac) - right) < 1e-9 and frac.denominator % 2 == 1:
                        return -((-left) ** (frac.numerator / frac.denominator))
                    raise ValueError("Even root of a negative number is undefined in real numbers.")
            res = OPERATORS[type(node.op)](left, right)
            if isinstance(res, complex):
                raise ValueError("Result is a complex/imaginary number.")
            return res
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in FUNCTIONS_1_ARG and len(node.args) == 1:
                return FUNCTIONS_1_ARG[func_name](_eval(node.args[0]))
            if func_name in FUNCTIONS_2_ARGS and len(node.args) == 2:
                return FUNCTIONS_2_ARGS[func_name](_eval(node.args[0]), _eval(node.args[1]))
        raise ValueError("Invalid mathematical expression syntax. Check your parentheses and operators.")

    tree = ast.parse(cleaned, mode="eval")
    return float(_eval(tree.body))


# --- Keypad Helpers & Callbacks ---
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
    if curr.endswith("^(1/"):
        curr = curr[:-4]
    elif curr.endswith("√("):
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


def calculate_expression():
    expr = get_current_text().strip()
    st.session_state.expression = expr
    if not expr:
        st.session_state.error_msg = "Please enter a calculation first."
        return
    try:
        result = safe_eval(expr)
        result_str = format_number(result)
        st.session_state.last_result = result
        st.session_state.last_expr = expr
        st.session_state.error_msg = ""
        st.session_state.history.insert(
            0,
            {
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Expression": expr,
                "Result": result_str,
            },
        )
    except ZeroDivisionError:
        st.session_state.error_msg = "Error: Division by zero is not allowed."
    except SyntaxError:
        st.session_state.error_msg = "Syntax Error: Make sure all opening '(' and closing ')' parentheses match."
    except Exception as err:
        st.session_state.error_msg = f"Error: {err}"


def use_last_result():
    if st.session_state.last_result is not None:
        st.session_state.expression = format_number(st.session_state.last_result).replace(",", "")
        st.session_state.error_msg = ""
        st.session_state.input_ver += 1


# --- Sidebar: Group Members & Quick Reference ---
with st.sidebar:
    st.header("👥 Group Members")
    st.markdown(
        """
        1. **Ammar Haikal Amin** (`021202600008`)
        2. **Excellent Lennoel Runtuk** (`021202600047`)
        3. **Neysa Mayluya Kesita Sinaga** (`021202600012`)
        """
    )
    st.divider()
    st.subheader("⚡ Quick Syntax Cheat Sheet")
    st.markdown(
        """
        - **Chained Ops:** `12 + 8 × 5 - 4 ÷ 2`
        - **Power:** `2^5` → `32`
        - **Square Root:** `√(144)` → `12`
        - **Custom $n$-th Root:** `27^(1/3)` → `3` or `root(27, 3)` → `3`
        - **Percentage:** `250000 × 15%` → `37,500`
        - **Previous Answer:** `Ans`
        """
    )

# --- Main Calculator Interface ---
st.title("🧮 Smart Web Calculator")
st.caption("Multi-Operation Web Calculator Built with Python & Streamlit")

with st.container(border=True):
    st.text_input(
        "Calculation Display (type directly or use the keypad below):",
        value=st.session_state.expression,
        key=f"input_{st.session_state.input_ver}",
        on_change=sync_from_typing,
        placeholder="Example: (125000 × 20%) + 27^(1/3) + √(81)",
    )

    # Display Result or Error Message
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
    elif st.session_state.last_result is not None:
        col_res, col_ans = st.columns([2.5, 1.2], vertical_alignment="center")
        with col_res:
            st.metric(
                label=f"Result: {st.session_state.last_expr}",
                value=format_number(st.session_state.last_result),
            )
        with col_ans:
            st.button(
                "Use Result",
                on_click=use_last_result,
                use_container_width=True,
                help="Insert the last result into the display for further calculation",
            )

    st.divider()

    # Top Function Row: Parentheses, Power, Square Root, Custom Root, Percentage
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    f1.button("(", on_click=append_token, args=("(",), use_container_width=True, help="Open parenthesis")
    f2.button(")", on_click=append_token, args=(")",), use_container_width=True, help="Close parenthesis")
    f3.button("^", on_click=append_token, args=("^",), use_container_width=True, help="Power / Exponent (e.g., 2^5)")
    f4.button("√", on_click=append_token, args=("√(",), use_container_width=True, help="Square root: √(x)")
    f5.button("ⁿ√", on_click=append_token, args=("^(1/",), use_container_width=True, help="Custom n-th root: type base number first, press ⁿ√ to insert ^(1/, enter n, then close with )")
    f6.button("%", on_click=append_token, args=("%",), use_container_width=True, help="Percentage (divides by 100)")

    # Main Number & Operator Keypad
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
    r4[2].button("Ans", on_click=append_token, args=("Ans",), use_container_width=True, help="Insert previous answer")
    r4[3].button("+", on_click=append_token, args=("+",), use_container_width=True)

    # Control Row: All Clear, Backspace, Equals
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.button("AC", on_click=clear_all, use_container_width=True, help="Clear all input and current result")
    c2.button("⌫", on_click=backspace_token, use_container_width=True, help="Delete last character")
    c3.button("=", type="primary", on_click=calculate_expression, use_container_width=True, help="Calculate result")

# --- Detailed User Guide in English ---
with st.expander("📘 User Guide: How to Use & Parentheses Rules", expanded=True):
    st.markdown(
        """
        ### 1. Unlimited Multi-Step Calculations
        You are not limited to two numbers. Enter as many numbers and operations as needed—the calculator automatically follows standard **PEMDAS / BODMAS** order of operations (Parentheses → Exponents/Roots → Multiplication/Division → Addition/Subtraction).
        * **Example:** `12 + 8 × 5 - 4 ÷ 2` → evaluates as `12 + 40 - 2 = 50`.

        ---

        ### 2. How to Use Powers (`^`), Square Roots (`√`), and Custom Roots (`ⁿ√`)
        * **Powers / Exponents (`^`):** Press `^` to raise a number to any power.
          * *Example:* `2^5` = `32`
        * **Square Root ($\sqrt{x}$):** Press **`√`** (which inserts `√(`), enter the number, and close with **`)`**.
          * *Example:* `√(144)` = `12`
        * **Custom $n$-th Root ($\sqrt[n]{x}$) — Adjustable Root Degree:**
          Since an $n$-th root is mathematically equal to a fractional exponent $\\left(x^{1/n}\\right)$, you can calculate **any root degree** (cube root, 4th root, 5th root, etc.) in two ways:
          1. **Using the `ⁿ√` button (Recommended):**
             * First, enter the base number (e.g., `27`).
             * Next, press **`ⁿ√`** — this automatically types **`^(1/`** onto the screen.
             * Enter the root degree (e.g., `3` for cube root), then press **`)`** to close the fraction.
             * Screen shows **`27^(1/3)`** → press **`=`** → Result: **`3`**.
             * *More examples:* `16^(1/4)` = `2` (4th root of 16), `32^(1/5)` = `2` (5th root of 32), `8^(2/3)` = `4`.
          2. **Using the `root(x, n)` function:**
             * Type `root(number, degree)` directly in the input bar.
             * *Example:* `root(27, 3)` = `3`

        ---

        ### 3. Important Rules for Parentheses `( )` — Avoid Common Mistakes!
        Parentheses control which part of your expression is calculated first. Always follow these rules:

        1. **ALWAYS put parentheses around fractional exponents (custom roots):**
           * ✅ **Correct:** `27^(1/3)` → calculates $27^{(1/3)} = 3$
           * ❌ **Wrong:** `27^1/3` → without parentheses, the calculator computes $(27^1) \\div 3 = 9$!
        2. **Enclose expressions inside a root if there is an operation inside:**
           * ✅ **Correct:** `√(9 + 16)` → calculates $\\sqrt{25} = 5$
           * ❌ **Wrong:** `√(9) + 16` → calculates $3 + 16 = 19$
        3. **Group additions or subtractions before multiplying, dividing, or raising to a power:**
           * ✅ **Correct:** `(10 + 20) ÷ 5` → calculates $30 \\div 5 = 6$
           * ❌ **Wrong:** `10 + 20 ÷ 5` → calculates $10 + 4 = 14$
        4. **Wrap negative numbers in parentheses when raising to a power:**
           * ✅ **Correct:** `(-3)^2` → calculates $(-3) \\times (-3) = 9$
           * ❌ **Wrong:** `-3^2` → calculates $-(3^2) = -9$
        5. **Match every opening `(` with a closing `)`:** An unclosed parenthesis will trigger a syntax error.

        ---

        ### 4. Percentages (`%`), `Ans`, and Controls
        * **Percentage (`%`):** Automatically converts a number into hundredths (`x / 100`).
          * *Example:* `250000 × 15%` = `37,500`
        * **Continue Calculating (`Ans` / `Use Result`):** Press **`Ans`** to insert your previous result into a new expression (e.g., `Ans × 2`), or click **`Use Result`** to load it directly into the display.
        * **`AC` vs `⌫`:** **`AC`** resets the entire display and clears the current result box; **`⌫`** deletes only the last character/symbol.
        """
    )

# --- Calculation History ---
if st.session_state.history:
    st.subheader("📜 Calculation History")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["Time", "Expression", "Result"])
    writer.writeheader()
    writer.writerows(st.session_state.history)

    dl_col, clr_col = st.columns(2)
    with dl_col:
        st.download_button(
            "📥 Download History (CSV)",
            data=csv_buffer.getvalue(),
            file_name="calculator_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with clr_col:
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history = []
            st.session_state.last_result = None
            st.session_state.last_expr = ""
            st.rerun()
