import streamlit as st
from database import db_write, db_fetch
from datetime import datetime

def show():
    st.header("👥 إدارة الحسابات (موردين، عملاء، صناديق)")
    
    tab1, tab2 = st.tabs(["➕ إضافة حساب جديد", "📋 قائمة الحسابات الحالية"])
    
    with tab1:
        with st.form("acc_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم الحساب (المحل أو الشخص)")
            cat = col2.selectbox("التصنيف", ["مورد", "عميل", "صندوق/كاش", "فرع", "بنك"])
            
            col3, col4 = st.columns(2)
            phone = col3.text_input("رقم التواصل")
            op_bal = col4.number_input("الرصيد الافتتاحي (لك + / عليك -)", value=0.0)
            
            if st.form_submit_button("حفظ الحساب"):
                if name:
                    success, err = db_write(
                        "INSERT INTO accounts (name, category, phone, opening_balance, current_balance, created_at) VALUES (?,?,?,?,?,?)",
                        (name, cat, phone, op_bal, op_bal, datetime.now().strftime("%Y-%m-%d"))
                    )
                    if success: 
                        st.success(f"تم تسجيل {name} بنجاح كـ {cat}")
                        st.rerun()
                    else: st.error(f"خطأ: {err}")

    with tab2:
        df = db_fetch("SELECT name, category, phone, current_balance FROM accounts")
        if not df.empty:
            # تلوين الأرصدة (أحمر للديون، أخضر للمبالغ المتوفرة)
            st.dataframe(df.style.format(subset=['current_balance'], formatter="{:.2f}")
                         .applymap(lambda x: 'color: red' if x < 0 else 'color: green', subset=['current_balance']), 
                         use_container_width=True)