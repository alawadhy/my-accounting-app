import streamlit as st
from database import db_write, db_fetch, log_event, auto_backup
from datetime import datetime

def manage_accounts():
    st.subheader("🏛️ الدليل المحاسبي الموحد")
    
    # توزيع الواجهة لسهولة الإدخال
    tab_add, tab_view = st.tabs(["➕ إضافة حساب/جهة", "📋 استعراض الأرصدة"])
    
    with tab_add:
        with st.form("advanced_acc_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم الجهة (محل، مورد، فرع، عميل)")
            cat = col2.selectbox("التصنيف المحاسبي", ["مورد", "عميل", "صندوق/كاش", "بنك", "فرع", "مصروفات تشغيلية"])
            
            col3, col4, col5 = st.columns(3)
            limit = col3.number_input("حد الائتمان (تنبيه المديونية)", min_value=0.0, value=10000.0)
            open_bal = col4.number_input("الرصيد الافتتاحي", value=0.0)
            phone = col5.text_input("رقم التواصل")
            
            note = st.text_area("ملاحظات إضافية عن الحساب")
            
            if st.form_submit_button("اعتماد الحساب في النظام"):
                if name:
                    res, err = db_write(
                        "INSERT INTO accounts (name, category, credit_limit, opening_balance, current_balance, phone) VALUES (?,?,?,?,?,?)",
                        (name, cat, limit, open_bal, open_bal, phone)
                    )
                    if res:
                        log_event("admin", "CREATE_ACC", f"تم إنشاء حساب {name} بفئة {cat}")
                        st.success(f"✅ تم تعريف الحساب '{name}' بنجاح.")
                        st.rerun()
                    else: st.error(f"❌ فشل الحفظ: {err}")

    with tab_view:
        search = st.text_input("🔍 بحث سريع في الحسابات")
        query = "SELECT name, category, current_balance, credit_limit FROM accounts"
        if search:
            query += f" WHERE name LIKE '%{search}%'"
        
        df = db_fetch(query)
        if not df.empty:
            # تلوين احترافي للأرصدة
            st.dataframe(df.style.applymap(lambda x: 'color: red' if isinstance(x, float) and x < 0 else 'color: green', subset=['current_balance']), use_container_width=True)

def record_transaction():
    st.subheader("📑 تسجيل العمليات المالية والقيود")
    
    acc_data = db_fetch("SELECT name, category, current_balance FROM accounts")
    if acc_data.empty:
        return st.warning("⚠️ يجب إضافة حسابات أولاً من قسم 'إدارة الحسابات'")

    acc_list = acc_data['name'].tolist()

    with st.form("mega_transaction_form"):
        c1, c2, c3 = st.columns([2, 1, 1])
        acc = c1.selectbox("الطرف الأول (الحساب المستهدف)", acc_list)
        op = c2.selectbox("نوع العملية", [
            "شراء آجل (مديونية)", "شراء كاش", "سند صرف (تسديد مورد)", 
            "بيع آجل", "سند قبض (تحصيل عميل)", "مرتجع مشتريات", "مصروف عام"
        ])
        amount = c3.number_input("المبلغ (صافي)", min_value=0.01)
        
        c4, c5 = st.columns(2)
        ref = c4.text_input("رقم الفاتورة / المرجع الورقي")
        desc = c5.text_input("شرح العملية (البيان)")
        
        # ميزة اختيار الصندوق في حالة العمليات النقدية
        cash_accounts = acc_data[acc_data['category'].isin(['صندوق/كاش', 'بنك'])]['name'].tolist()
        payment_method = st.selectbox("مصدر النقد (في حال العملية كاش أو سداد)", ["---"] + cash_accounts)

        if st.form_submit_button("ترحيل العملية وتحديث الأرصدة 🚀"):
            debit, credit = 0, 0
            
            # منطق المحاسبة الذكي
            if "شراء" in op or "قبض" in op: credit = amount
            elif "بيع" in op or "صرف" in op or "مصروف" in op: debit = amount
            
            # تسجيل في اليومية
            success, jid = db_write(
                "INSERT INTO journal (date, acc_name, op_type, description, debit, credit, ref_no) VALUES (?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d"), acc, op, desc, debit, credit, ref)
            )
            
            if success:
                # تحديث الحساب الرئيسي
                db_write("UPDATE accounts SET current_balance = current_balance + ? WHERE name = ?", (debit - credit, acc))
                
                # تحديث حساب الصندوق (إذا تم اختياره) لإبقاء الأرصدة دقيقة
                if payment_method != "---":
                    cash_impact = -amount if "شراء" in op or "صرف" in op else amount
                    db_write("UPDATE accounts SET current_balance = current_balance + ? WHERE name = ?", (cash_impact, payment_method))
                
                auto_backup()
                st.success(f"✅ تم الترحيل بنجاح! رقم القيد: {jid}")
                st.rerun()