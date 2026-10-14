import streamlit as st

st.markdown("""
<style>
.formula-container {
    background-color: #EAEAEA;
    border-radius: 8px;
    padding: 15px;
    color: #333333;
}
.formula-container .katex {
    color: #333333 !important;
}
</style>
""", unsafe_allow_html=True)

latex_formula = r"Imposto = V \times T_{base}"

st.markdown("<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>Fórmula Base:</div>", unsafe_allow_html=True)
st.latex(latex_formula)
