import streamlit as st

def apply_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        html, body, [class*="css"] { font-family: 'Cairo', sans-serif; direction: rtl; text-align: right; }
        .main { background-color: #f8fafc; }
        .stMetric { background: white; padding: 20px; border-radius: 15px; border-right: 10px solid #1e40af; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%); color: white; border: none; font-weight: 700; transition: 0.3s; }
        .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(30, 64, 175, 0.3); }
        .status-card { padding: 20px; border-radius: 15px; color: white; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)