import streamlit as st
from database import db_write, db_fetch, generate_jv_ref, get_accounting_logic
from datetime import datetime

def show_journal_page():
    st.header("📑 تسجيل العمليات والمحاسب الآلي")
    
    acc_df = db_fetch("SELECT name, category FROM accounts WHERE is_active=1")
    if acc_df.empty:
        st.warning("⚠️ يرجى إضافة حسابات أولاً.")
        return

    acc_list = acc_df['name'].tolist()

    with st.form("smart_trans_form"):
        c1, c2, c3 = st.columns(3)
        acc_name = c1.selectbox("اختر الحساب (الطرف الثاني)", acc_list)
        op_type = c2.selectbox("نوع العملية", 
            ["بيع آجل", "شراء آجل", "سند قبض", "سند صرف", "بيع كاش", "شراء كاش", "مرتجع"])
        date = c3.date_input("تاريخ العملية", datetime.now())

        c4, c5, c6 = st.columns(3)
        amount = c4.number_input("المبلغ الأساسي", min_value=0.0, step=0.1)
        use_tax = c5.checkbox("إضافة ضريبة 15%", value=True)
        auto_ref = generate_jv_ref(op_type)
        ref_no = c6.text_input("رقم المرجع (توليد آلي)", value=auto_ref)

        desc = st.text_input("البيان / شرح العملية المختصر")
        
        offset_acc = None
        if "سند" in op_type or "كاش" in op_type:
            cash_accs = db_fetch("SELECT name FROM accounts WHERE category IN ('صندوق/كاش', 'بنك')")
            if not cash_accs.empty:
                offset_acc = st.selectbox("الصندوق / البنك المتأثر", cash_accs['name'].tolist())

        if st.form_submit_button("ترحيل العملية إلى النظام 🚀"):
            if amount <= 0:
                st.error("❌ لا يمكن تسجيل عملية بمبلغ صفر!")
            else:
                # استدعاء الدالة الموحدة من ملف database.py
                success, message = process_full_transaction(
                    acc_name=acc_name,
                    offset_acc=offset_acc,
                    op_type=op_type,
                    base_amount=amount,
                    use_tax=use_tax,
                    description=desc,
                    ref_no=ref_no,
                    date_str=str(date)
                )
                
                if success:
                    st.success(message)
                    st.balloons()
                else:
                    st.error(message)