import streamlit as st
import pandas as pd
import plotly.express as px
import database
import os
from datetime import datetime
from fpdf import FPDF, XPos, YPos
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- 1. إعدادات الصفحة (يجب أن تكون أول أمر بعد الـ Imports) ---
st.set_page_config(
    page_title="نظام المحاسب الذكي PRO 2026", 
    layout="wide", 
    page_icon="⚖️",
    initial_sidebar_state="expanded"
)
# --- تهيئة حالة الجلسة مباشرة بعد كل الـ Imports ---
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'role' not in st.session_state:
    st.session_state.role = "User" 
if 'full_name' not in st.session_state:
    st.session_state.full_name = ""

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stMetric {
        background: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border-right: 12px solid #1e3a8a;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
    }
    
    .main {
        background-color: #f1f5f9;
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: bold;
        height: 3em;
        background-color: #1e3a8a;
        color: white;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #2563eb;
        transform: translateY(-2px);
    }
    
    .edit-mode {
        background-color: #fffaf0;
        border: 2px dashed #f97316;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 25px;
    }

    .header-style {
        background-color: #1e3a8a;
        color: white;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 5px;
        font-weight: bold;
    }

    /* تحسين شكل الجداول والجوال */
    .stDataFrame { border-radius: 10px; }
    div[data-testid="stExpander"] { border-radius: 10px !important; }
    </style>
""", unsafe_allow_html=True)

if not st.session_state.get('auth', False):
    st.markdown("<h2 style='text-align: center;'>🔑 دخول النظام</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_in = st.text_input("👤 اسم المستخدم")
        pwd_in = st.text_input("🔑 كلمة المرور", type="password")
        
        # التعديل هنا: استخدام width='stretch' بدلاً من use_container_width
        if st.button("تسجيل الدخول", width='stretch'):
            u_clean = user_in.strip().lower()
            
            # استدعاء الدالة من database.py
            is_valid, user_data = database.verify_user(u_clean, pwd_in)
            
            if is_valid:
                st.session_state.auth = True
                st.session_state.user = user_data # تخزين القاموس كاملاً للرجوع إليه
                
                # استخدام .get() يمنع KeyError الذي ظهر لك في الصورة image_5e802a
                st.session_state.user_name = user_data.get('username')
                st.session_state.role = user_data.get('role')
                st.session_state.full_name = user_data.get('full_name')
                
                # جلب الصلاحيات بأمان
                st.session_state.can_delete = user_data.get('can_delete', 0)
                st.session_state.can_reports = user_data.get('can_reports', 0)
                st.session_state.can_settings = user_data.get('can_settings', 0)
                st.session_state.can_users = user_data.get('can_users', 0)
                
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    # أضف هذا السطر هنا لمنع تشغيل باقي الملف قبل تسجيل الدخول
    st.stop() 

# --- الآن هنا يبدأ كود لوحة التحكم والقائمة الجانبية ---
st.sidebar.title("لوحة التحكم")

def create_pdf_report(df, acc_name, start_date, end_date):
    pdf = FPDF()
    pdf.add_page()
    
    # إعدادات الخط والوقت
    from datetime import datetime
    report_gen_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        pdf.add_font('ArabicFont', '', 'arial.ttf', uni=True)
        pdf.set_font('ArabicFont', size=10)
    except: return None

    def fix_ar(text):
        from bidi.algorithm import get_display
        from arabic_reshaper import reshape
        return get_display(reshape(str(text)))

    # 1. ترويسة علوية تفصيلية
    pdf.set_font('ArabicFont', size=16)
    pdf.cell(190, 10, fix_ar(f"تقرير كشف حساب تفصيلي"), ln=True, align='C')
    pdf.set_font('ArabicFont', size=10)
    pdf.cell(95, 8, fix_ar(f"تاريخ الاستخراج: {report_gen_date}"), align='R')
    pdf.cell(95, 8, fix_ar(f"اسم الحساب: {acc_name}"), ln=True, align='L')
    pdf.cell(190, 8, fix_ar(f"الفترة الزمنية: من {start_date} إلى {end_date}"), ln=True, align='C')
    pdf.line(10, 35, 200, 35) # خط جمالي
    pdf.ln(5)

    # 2. رسم الجدول بتنسيق احترافي
    col_widths = [25, 25, 25, 55, 20, 20, 20]
    headers = ["التاريخ", "المرجع", "البيان", "مدين", "دائن", "الرصيد", "الاستحقاق"]
    
    pdf.set_fill_color(52, 73, 94) # لون كحلي للهيدر
    pdf.set_text_color(255, 255, 255)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, fix_ar(header), border=1, align='C', fill=True)
    pdf.ln()

    # بيانات الجدول
    pdf.set_text_color(0, 0, 0)
    for _, row in df.iterrows():
        for i, item in enumerate(row):
            val = f"{item:,.2f}" if isinstance(item, (int, float)) else str(item)
            pdf.cell(col_widths[i], 8, fix_ar(val), border=1, align='C')
        pdf.ln()

    # 3. التذييل والتحليل المالي (لنا / علينا)
    pdf.ln(5)
    final_bal = float(df.iloc[-1, -1])
    status = "لنا مبلغ" if final_bal > 0 else "علينا مبلغ"
    summary = f"الرصيد النهائي المستحق {status}: {abs(final_bal):,.2f} ريال"
    
    pdf.set_font('ArabicFont', size=12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(190, 12, fix_ar(summary), border=1, ln=True, align='C', fill=True)
    
    return bytes(pdf.output())

# --- 3. إدارة حالة الجلسة (Session State) المحدثة ---
# تم تحديث القيم الافتراضية لتتوافق مع نظام التحقق الجديد
states = {
    'edit_id': None,
    'temp_name': "",
    'temp_vat': "",
    'temp_phone': "",
    'temp_cat': "--- اختر التصنيف ---",  # القيمة الجديدة لمنع الإضافة العشوائية
    'temp_limit': 0.0,                   # تصفير حد الائتمان افتراضياً
    'temp_open': 0.0,
    'temp_addr': "",
    'auth': False
}

for key, value in states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# إضافة مفتاح إضافي للتحقق من تغيير التصنيف (اختياري لكنه مفيد)
if 'old_cat' not in st.session_state:
    st.session_state.old_cat = ""

# --- 5. القائمة الجانبية (Sidebar) المحدثة والذكية ---
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>🏢 لوحة التحكم PRO</h2>", unsafe_allow_html=True)
    
    # استخراج بيانات المستخدم الحالي بأمان
    user_data = st.session_state.get('user', {})
    
    # جلب الصلاحيات من داخل قاموس user
    current_role = str(user_data.get('role', 'user')).lower()
    p_reports = int(user_data.get('can_reports', 0))
    p_settings = int(user_data.get('can_settings', 0))
    p_users = int(user_data.get('can_users', 0))

    # بناء قائمة الخيارات بناءً على الصلاحيات
    menu = ["🏠 الرئيسية", "📂 دليل الحسابات", "📝 القيود اليومية", "🔍 كشف الحساب"]
    
    # 1. صلاحيات التقارير
    if current_role in ["admin", "administrator", "adminstrator"] or p_reports == 1:
        menu.append("📊 تحليل المبيعات")
        menu.append("🧾 التقارير الضريبية")

    # 2. صلاحيات الإعدادات
    if current_role in ["admin", "administrator", "adminstrator"] or p_settings == 1:
        menu.append("⚙️ الإعدادات")

    # 3. صلاحية إدارة المستخدمين (أضفنا adminstrator بسبب الخطأ الإملائي في جدولك)
    if current_role in ["administrator", "adminstrator"] or p_users == 1:
        menu.append("👥 إدارة المستخدمين")

    # أداة الاختيار
    choice = st.selectbox("انتقل إلى:", menu)
    
    st.divider()

    # عرض معلومات المستخدم في مربع واحد أنيق
    st.markdown(f"""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px;'>
        <p style='margin:0; color: #333; text-align:right;'>👤 <b>المستخدم:</b> {st.session_state.get('full_name', 'None')}</p>
        <p style='margin:0; color: #007bff; text-align:right;'>🔑 <b>الصلاحية:</b> {current_role.capitalize()}</p>
        <p style='margin:0; color: #666; text-align:right; font-size: 12px;'>📅 {datetime.now().strftime('%Y-%m-%d')}</p>
    </div>
    """, unsafe_allow_html=True)

    # زر تسجيل خروج واحد نهائي
    if st.sidebar.button("🚪 تسجيل الخروج"):
        with st.spinner("جاري تأمين البيانات وعمل نسخة احتياطية..."):
            database.auto_smart_backup() # النسخ التلقائي الذكي
        st.session_state.clear()
        st.rerun()
# تأكد أن هذه الأسطر تبدأ من أول السطر تماماً بدون أي فراغ جهة اليسار
if choice == "🏠 الرئيسية":
    st.title("📈 الملخص المالي اللحظي")
    
    try:
        all_accounts = database.db_fetch("accounts") 
        
        if not all_accounts.empty:
            # التأكد من تحويل القيم لأرقام
            all_accounts['current_balance'] = pd.to_numeric(all_accounts['current_balance'], errors='coerce').fillna(0)
            
            # تجميع البيانات
            summary = all_accounts.groupby('category')['current_balance'].sum()

            def get_bal(cat_list):
                return summary[summary.index.isin(cat_list)].sum()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📦 ديون الموردين", f"{abs(get_bal(['مورد', 'موردين'])):,.2f} ريال")
            m2.metric("👥 مستحقات العملاء", f"{get_bal(['عميل', 'عملاء']):,.2f} ريال")
            m3.metric("💰 السيولة النقدية", f"{get_bal(['صندوق', 'كاش', 'نقدية', 'بنك']):,.2f} ريال")
            m4.metric("📉 إجمالي المصروفات", f"{abs(get_bal(['مصروفات', 'مصاريف'])):,.2f} ريال")
        
        st.divider()

        df_journal = database.db_fetch("journal")
        if not df_journal.empty:
            df_journal['date'] = pd.to_datetime(df_journal['date']).dt.date
            df_journal['total_amount'] = pd.to_numeric(df_journal['total_amount'], errors='coerce').fillna(0)
            
            df_chart = df_journal.groupby('date')['total_amount'].sum().reset_index().tail(10)
            fig = px.line(df_chart, x='date', y='total_amount', title="📊 حجم التداول اليومي", markers=True)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("ℹ️ لا توجد حركات مسجلة حالياً لعرضها.")

        # --- الجزء الجديد: تنبيهات الموردين المستحقين ---
        st.markdown("### 🔔 تنبيهات إدارة الموردين")
        urgent_debts, critical_debts = database.get_detailed_debts()

        col_msg1, col_msg2 = st.columns(2)

        with col_msg1:
            st.markdown("#### 🗓️ مستحقات حان موعدها")
            if not urgent_debts.empty:
                # تجميع المبالغ حسب المورد لتجنب التكرار
                sum_urgent = urgent_debts.groupby('acc_name')['total_amount'].sum().reset_index()
                for _, row in sum_urgent.iterrows():
                    st.warning(f"⚠️ **{row['acc_name']}**: مبلغ **{row['total_amount']:,.2f}** ريال")
            else:
                st.success("✅ جميع التزاماتك المجدولة تحت السيطرة.")

        with col_msg2:
            st.markdown("#### 🚨 ديون متأخرة (> 30 يوم)")
            if not critical_debts.empty:
                sum_crit = critical_debts.groupby('acc_name')['total_amount'].sum().reset_index()
                for _, row in sum_crit.iterrows():
                    # تنسيق بارز للديون المتأخرة جداً
                    st.error(f"🚩 **{row['acc_name']}**: متأخر بمبلغ **{row['total_amount']:,.2f}** ريال")
            else:
                st.info("👍 لا توجد مديونيات متأخرة لأكثر من شهر.")
            
    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة البيانات: {e}")

# --- نهاية القائمة الجانبية وبداية الأقسام الوظيفية ---
# 2. دليل الحسابات المطور - النسخة الكاملة الشاملة 2026
elif choice == "📂 دليل الحسابات":
    st.title("📂 إدارة دليل الحسابات الذكي")

    if st.session_state.edit_id:
        st.markdown('<div style="background-color: #fff3cd; padding: 20px; border-radius: 15px; border-right: 10px solid #ffa000;">', unsafe_allow_html=True)
        st.subheader(f"📝 تعديل بيانات الحساب")
    else:
        st.subheader("➕ إضافة حساب جديد")

    with st.form("account_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("اسم الحساب / الشركة *", value=st.session_state.temp_name)
        cat_list = ["--- اختر التصنيف ---", "عميل", "مورد", "صندوق", "بنك", "مصروفات", "فرع", "إيرادات أخرى"]
        current_cat_idx = cat_list.index(st.session_state.temp_cat) if st.session_state.temp_cat in cat_list else 0
        cat = c2.selectbox("نوع الحساب (التصنيف) *", cat_list, index=current_cat_idx)
        is_taxable = c3.toggle("هل الحساب خاضع للضريبة؟", value=True if st.session_state.temp_vat else False)

        st.divider()

        c4, c5, c6 = st.columns(3)
        default_bal_type = "علينا (دائن)" if cat == "مورد" else "لنا (مدين)"
        bal_type = c4.selectbox("حالة الرصيد الافتتاحي", ["لنا (مدين)", "علينا (دائن)"], 
                                index=0 if default_bal_type == "لنا (مدين)" else 1)
        open_bal_raw = c5.number_input("قيمة الرصيد الافتتاحي", value=abs(float(st.session_state.temp_open)), min_value=0.0)
        open_bal = open_bal_raw if bal_type == "لنا (مدين)" else -open_bal_raw
        limit = c6.number_input("حد الائتمان (سقف المديونية)", value=float(st.session_state.temp_limit), step=100.0)

        st.divider()

        c7, c8, c9 = st.columns(3)
        vat = c7.text_input("الرقم الضريبي", value=st.session_state.temp_vat)
        phone = c8.text_input("رقم الجوال", value=st.session_state.temp_phone)
        addr = c9.text_input("العنوان الجغرافي", value=st.session_state.temp_addr)

        btn_txt = "💾 حفظ التعديلات" if st.session_state.edit_id else "✅ إضافة الحساب"
        
        if st.form_submit_button(btn_txt):
            if not name or cat == "--- اختر التصنيف ---":
                st.error("❌ يرجى إدخال البيانات المطلوبة")
            else:
                account_data = {
                    "acc_name": name, "category": cat, "tax_number": vat,
                    "credit_limit": float(limit), "opening_balance": float(open_bal),
                    "current_balance": float(open_bal), "phone": phone, "address": addr, "is_active": True
                }

                try:
                    if st.session_state.edit_id:
                        # حل مشكلة التعديل: نستخدم مكتبة supabase مباشرة
                        from database import supabase
                        supabase.table("accounts").update(account_data).eq("id", st.session_state.edit_id).execute()
                        st.success("✅ تم التعديل بنجاح")
                    else:
                        account_data["acc_code"] = database.generate_acc_code(cat)
                        database.db_write("accounts", account_data)
                        st.success("✅ تم إضافة الحساب بنجاح")
                    
                    # تصفير البيانات
                    st.session_state.edit_id = None
                    for k in ['temp_name', 'temp_vat', 'temp_phone', 'temp_addr']: st.session_state[k] = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ حدث خطأ: {e}")

    st.divider()
    st.subheader("📋 قائمة الحسابات المسجلة")
    acc_df = database.db_fetch("accounts")
    
    if not acc_df.empty:
        h = st.columns([1, 1.8, 1, 0.9, 0.9, 0.9, 0.6, 1.2])
        titles = ["الكود", "الاسم", "التصنيف", "الافتتاحي", "الائتمان", "الرصيد", "حالة", "إدارة"]
        for col, title in zip(h, titles): col.markdown(f"**{title}**")

        for _, row in acc_df.iterrows():
            r = st.columns([1, 1.8, 1, 0.9, 0.9, 0.9, 0.6, 1.2])
            r[0].write(f"`{row['acc_code']}`")
            r[1].write(row['acc_name'])
            r[2].info(row['category'])
            r[3].write(f"{row['opening_balance']:,.0f}")
            r[4].write(f"{row['credit_limit']:,.0f}")
            cur = row['current_balance']
            r[5].markdown(f":{'green' if cur >= 0 else 'red'}[{abs(cur):,.0f}]")
            r[6].write("🟢" if row['is_active'] else "🔴")
            
            with r[7]:
                c_edit, c_del = st.columns(2)
                if c_edit.button("📝", key=f"e_{row['id']}"):
                    st.session_state.edit_id = row['id']
                    st.session_state.temp_name = row['acc_name']
                    st.session_state.temp_cat = row['category']
                    st.session_state.temp_open = row['opening_balance']
                    st.session_state.temp_limit = row['credit_limit']
                    st.session_state.temp_vat = row.get('tax_number', '')
                    st.session_state.temp_phone = row.get('phone', '')
                    st.session_state.temp_addr = row.get('address', '')
                    st.rerun()
                
                if c_del.button("🗑️", key=f"d_{row['id']}"):
                    # حل مشكلة الحذف: نستخدم مكتبة supabase مباشرة لتجنب نقص الوسائط (data)
                    from database import supabase
                    supabase.table("accounts").delete().eq("id", row['id']).execute()
                    st.success("✅ تم الحذف")
                    st.rerun()
            st.divider()
    else:
        st.info("لا توجد حسابات مسجلة حالياً.")

elif choice == "📅 متابعة المستحقات":
    st.title("📅 جدول أعمار الديون ومستحقات الموردين")
    
    # استدعاء الدالة التي أنشأناها في الخطوة السابقة
    due_data = database.get_supplier_due_amounts()
    
    if not due_data.empty:
        # عرض ملخص سريع باستخدام بطاقات (Metrics)
        total_due = due_data['total_amount'].sum()
        overdue = due_data[due_data['days_left'] < 0]['total_amount'].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("إجمالي المستحقات القادمة", f"{total_due:,.2f} ريال")
        c2.metric("مبالغ تجاوزت موعدها", f"{overdue:,.2f} ريال", delta_color="inverse")

        # تنسيق الجدول للعرض
        display_df = due_data.copy()
        display_df.columns = ['اسم المورد', 'تاريخ الفاتورة', 'تاريخ الاستحقاق', 'المبلغ', 'الأيام المتبقية']
        
        # إضافة تلوين احترافي: أحمر للمتأخر، أصفر للقريب
        def highlight_due(val):
            color = 'white'
            if val < 0: color = '#ffcccc' # متأخر
            elif val <= 7: color = '#ffffcc' # يستحق خلال أسبوع
            return f'background-color: {color}'

        st.dataframe(display_df.style.applymap(highlight_due, subset=['الأيام المتبقية']), width="stretch")
    else:
        st.info("✅ لا توجد فواتير مشتريات آجلة مستحقة حالياً.")
        
# 3. تسجيل القيود اليومية المطور (نظام التوازن التلقائي والبحث والحذف)
elif choice == "📝 القيود اليومية":
    st.title("📝 تسجيل العمليات المالية")
    
    # جلب الحسابات النشطة من قاعدة البيانات
    accounts_db = database.db_fetch("SELECT name, category FROM accounts WHERE is_active=1")
    
    if accounts_db.empty:
        st.error("❌ يرجى إضافة حسابات أولاً من دليل الحسابات")
    else:
        # --- الجزء الأول: نموذج إدخال القيد (الفورم) ---
        with st.form("journal_entry", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            acc_name = c1.selectbox("الحساب الرئيسي (الطرف الأول)", accounts_db['name'].tolist())
            # قائمة العمليات كاملة لضمان عدم فقدان أي نوع
            op_list = ["بيع آجل", "شراء آجل", "سند قبض", "سند صرف", "بيع كاش", "شراء كاش", "مرتجع مبيعات", "مرتجع مشتريات", "مصروفات عامة"]
            op_type = c2.selectbox("نوع العملية", op_list)
            date_op = c3.date_input("تاريخ العملية", datetime.now())
            
            c4, c5, c6 = st.columns(3)
            amount = c4.number_input("المبلغ (قبل الضريبة)", min_value=0.0, step=1.0)
            has_vat = c5.checkbox("إضافة ضريبة 15%", value=False)
            ref_no = c6.text_input("رقم المرجع / الفاتورة", value=database.generate_jv_ref(op_type))
            
            # --- ميزة تاريخ الاستحقاق المدمجة ---
            due_date_val = None
            if "آجل" in op_type:
                # يظهر فقط في البيع/الشراء الآجل
                due_date_val = st.date_input("📅 موعد استحقاق السداد", 
                                            value=date_op + pd.Timedelta(days=30)).isoformat()
            
            note = st.text_input("شرح القيد (البيان)", placeholder="مثلاً: سداد فاتورة توريد رقم 50")
            
            st.markdown("---")
            cash_box = database.db_fetch("SELECT name FROM accounts WHERE category IN ('صندوق/كاش', 'بنك')")
            
            offset_acc = None
            if not cash_box.empty:
                offset_acc = st.selectbox("حدد حساب الدفع/القبض (الصندوق أو البنك):", cash_box['name'].tolist())
            else:
                st.warning("⚠️ لا يوجد حساب صندوق أو بنك مسجل!")
            
            submit = st.form_submit_button("🚀 ترحيل القيد الآن")
            
            if submit:
                if amount <= 0:
                    st.error("⚠️ يرجى إدخال مبلغ صحيح")
                elif not offset_acc:
                    st.error("⚠️ لا يمكن الترحيل بدون تحديد حساب (صندوق أو بنك)")
                else:
                    success, msg = database.process_full_transaction(
                        acc_name=acc_name, 
                        offset_acc=offset_acc, 
                        op_type=op_type, 
                        amount=amount, 
                        use_tax=has_vat, 
                        description=note, 
                        ref_no=ref_no, 
                        date_str=date_op.isoformat(),
                        posted_by=st.session_state.get('user_name', 'System'),
                        due_date=due_date_val # التمرير السليم للسحاب
                    )
                    
                    if success:
                        # تسجيل الحدث في سجل الرقابة
                        database.log_event(st.session_state.get('user_name', 'System'), 
                                        "إضافة قيد", f"تم إضافة {op_type} برقم {ref_no}")
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        # --- الجزء الثاني: سجل العمليات المطور (مصحح) ---
        st.write("##") 
        st.markdown("---")
        st.subheader("📑 سجل العمليات المطور")

        search_query = st.text_input("🔍 ابحث برقم المرجع أو اسم الحساب:", placeholder="اكتب هنا...")

        if search_query:
            recent_data = database.advanced_search_journal(search_query)
        else:
            recent_data = database.get_recent_transactions(30)

        if not recent_data.empty:
            for index, row in recent_data.iterrows():
                # استخدام .get() لتجنب خطأ KeyError
                ref = row.get('ref_no', 'N/A')
                acc = row.get('acc_name', 'Unknown')
                amt = row.get('total_amount', 0.0)
                
                with st.expander(f"📄 {row.get('op_type', 'عملية')} | {acc} | مبلغ: {amt:,.2f} | مرجع: {ref}"):
                    col_info, col_action = st.columns([4, 1])
                    
                    with col_info:
                        st.write(f"**البيان:** {row.get('description', '-')}")
                        # معالجة حقل المستخدم والتاريخ بأمان
                        st.write(f"**التاريخ:** {row.get('date', '-')} | **بواسطة:** {row.get('posted_by', 'Admin')}")
                                                    
                    with col_action:
                        # تحديث خاصية العرض إلى width='stretch'
                        if st.button("🗑️ حذف", key=f"del_{row['id']}_{index}", width='stretch'):
                            success, msg = database.delete_journal_entry(row['id'], st.session_state.role, st.session_state.user_name)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

                        # زر التعديل الجديد
                        if st.button("✏️ تعديل", key=f"edit_{row['id']}_{index}", width='stretch'):
                            st.session_state[f"edit_mode_{row['id']}"] = True

                    # --- منطق ظهور نافذة التعديل ---
                    if st.session_state.get(f"edit_mode_{row['id']}", False):
                        with st.form(f"form_edit_{row['id']}"):
                            st.write(f"### 🛠️ تعديل القيد رقم: {row['id']}")
                            new_acc = st.selectbox("تغيير الحساب", accounts_db['name'].tolist(), index=accounts_db['name'].tolist().index(row['acc_name']))
                            new_amt = st.number_input("المبلغ الجديد", value=float(row['total_amount']))
                            new_desc = st.text_input("البيان الجديد", value=row['description'])
                            
                            c_save, c_cancel = st.columns(2)
                            if c_save.form_submit_button("💾 حفظ التعديلات"):
                                success, msg = database.update_journal_entry(row['id'], new_acc, new_amt, new_desc, row['op_type'])
                                if success:
                                    st.success(msg)
                                    del st.session_state[f"edit_mode_{row['id']}"]
                                    st.rerun()
                                else: st.error(msg)
                            
                            if c_cancel.form_submit_button("✖️ إلغاء"):
                                del st.session_state[f"edit_mode_{row['id']}"]
                                st.rerun()
                    
    

        else:
            st.info("ℹ️ لا توجد عمليات مسجلة حالياً أو مطابقة للبحث.")

# 4. مركز كشف الحساب الاحترافي (النسخة المتكاملة: فلاتر + رصيد منقول + طباعة مضمونة)
elif choice == "🔍 كشف الحساب":
    st.title("🔍 مركز مراجعة كشوفات الحساب الذكية")
    
    # صف أدوات التحكم العلوي
    with st.container():
        c1, c2, c3 = st.columns([2, 1, 1])
        # ملاحظة: تأكد أن db_fetch ترجع DataFrame
        acc_list_df = database.db_fetch("accounts") 
        
        if acc_list_df.empty:
            st.warning("⚠️ لا توجد حسابات مسجلة حالياً.")
            selected_acc = None
        else:
            selected_acc = c1.selectbox("🎯 اختر الحساب للمراجعة:", acc_list_df['name'].tolist())
            start_date = c2.date_input("من تاريخ", value=datetime(2026, 1, 1))
            end_date = c3.date_input("إلى تاريخ", value=datetime.now())

    if selected_acc:
        # 1. جلب البيانات وحساب الرصيد المنقول
        orig_opening_bal = acc_list_df[acc_list_df['name'] == selected_acc]['opening_balance'].values[0]
        
        all_j = database.db_fetch("journal")
        
        if not all_j.empty:
            # تحويل التاريخ لصيغة صحيحة (Date Object) للمقارنة مع date_input
            all_j['jv_date'] = pd.to_datetime(all_j['jv_date']).dt.date
            
            # حساب ما قبل الفترة
            pre_df = all_j[(all_j['acc_name'] == selected_acc) & (all_j['jv_date'] < start_date)]
            pre_deb = pd.to_numeric(pre_df['debit'], errors='coerce').sum()
            pre_crd = pd.to_numeric(pre_df['credit'], errors='coerce').sum()
            carried_forward_bal = orig_opening_bal + (pre_deb - pre_crd)
            
            # جلب حركات الفترة الحالية
            data = all_j[(all_j['acc_name'] == selected_acc) & 
                         (all_j['jv_date'] >= start_date) & 
                         (all_j['jv_date'] <= end_date)].sort_values(by=['jv_date', 'id'])
        else:
            carried_forward_bal = orig_opening_bal
            data = pd.DataFrame()

        # --- استكمال بقية كودك (الفلاتر، عرض الجدول، الرصيد التراكمي) من هنا ---
        # (بقية الكود الخاص بـ df_filtered و final_df الذي أرسلته سابقاً)


        # --- 3. أزرار الفلترة ---
        st.write("---")
        f1, f2, f3, f4 = st.columns(4)
        if f1.button("🌐 عرض الكل", width='stretch'): st.session_state.filter = "all"
        if f2.button("💵 كاش فقط", width='stretch'): st.session_state.filter = "cash"
        if f3.button("📝 آجل فقط", width='stretch'): st.session_state.filter = "credit"
        if f4.button("🚫 استبعاد الكاش", width='stretch'): st.session_state.filter = "non_cash"
        
        current_filter = st.session_state.get('filter', 'all')
        
        # تطبيق الفلترة
        df_filtered = data.copy()
        if not df_filtered.empty:
            if current_filter == "cash":
                df_filtered = df_filtered[df_filtered['op_type'].str.contains("كاش|سند", na=False)]
            elif current_filter == "credit":
                df_filtered = df_filtered[df_filtered['op_type'].str.contains("آجل", na=False)]
            elif current_filter == "non_cash":
                df_filtered = df_filtered[~df_filtered['op_type'].str.contains("كاش|سند", na=False)]

        # --- 4. معالجة سطر الرصيد المنقول ودمجه ---
        opening_row = pd.DataFrame([{
            'jv_date': start_date.isoformat(),
            'ref_no': '---',
            'op_type': 'رصيد منقول',
            'description': 'رصيد ما قبل تاريخ البداية',
            'debit': 0.0,
            'credit': 0.0,
            'الرصيد التراكمي': carried_forward_bal
        }])

        if not df_filtered.empty:
            df_filtered['debit'] = pd.to_numeric(df_filtered['debit'], errors='coerce').fillna(0.0)
            df_filtered['credit'] = pd.to_numeric(df_filtered['credit'], errors='coerce').fillna(0.0)
            df_filtered['الرصيد التراكمي'] = carried_forward_bal + (df_filtered['debit'] - df_filtered['credit']).cumsum()
            final_df = pd.concat([opening_row, df_filtered], ignore_index=True)
        else:
            final_df = opening_row

        # --- 5. ملخص الحساب (Metrics) ---
        total_deb = df_filtered['debit'].sum() if not df_filtered.empty else 0
        total_crd = df_filtered['credit'].sum() if not df_filtered.empty else 0
        final_balance = final_df['الرصيد التراكمي'].iloc[-1]
        
        st.markdown(f"### 📊 ملخص حركات: {selected_acc} ({current_filter})")
        st.info(f"💾 الرصيد المنقول من فترات سابقة: {carried_forward_bal:,.2f} ريال")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("📥 إجمالي مدين (الفترة)", f"{total_deb:,.2f} ريال")
        k2.metric("📤 إجمالي دائن (الفترة)", f"{total_crd:,.2f} ريال")
        bal_label = "لنا (مدين)" if final_balance >= 0 else "علينا (دائن)"
        k3.metric("⚖️ الرصيد الختامي", f"{abs(final_balance):,.2f} ريال", 
                  delta=bal_label, delta_color="normal" if final_balance >= 0 else "inverse")

        # --- 6. عرض الجدول النهائي وتنسيقه ---
        display_df = final_df[['jv_date', 'ref_no', 'op_type', 'description', 'debit', 'credit', 'الرصيد التراكمي']].copy()
        display_df.columns = ['التاريخ', 'المرجع', 'العملية', 'البيان', '(+) مدين', '(-) دائن', 'الرصيد التراكمي']
        
        st.dataframe(
            display_df.style.format({'(+) مدين': '{:,.2f}', '(-) دائن': '{:,.2f}', 'الرصيد التراكمي': '{:,.2f}'}), 
            width='stretch', hide_index=True
        )

        # --- قسم التصدير والطباعة المحدث ---
        st.markdown("---")
        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            csv = final_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تصدير ككشف Excel", data=csv, 
                            file_name=f"Statement_{selected_acc}.csv", 
                            width='stretch') 

        # --- قسم التصدير والطباعة النهائي ---
        st.markdown("---")
        
        if st.button("🖨️ إصدار كشف حساب PDF", width='stretch'):
            try:
                # 1. استدعاء الدالة وتمرير البيانات المعروضة حالياً
                pdf_data = create_pdf_report(display_df, selected_acc, start_date, end_date)
                
                # 2. التأكد من نجاح عملية التوليد
                if pdf_data:
                    st.download_button(
                        label="⬇️ اضغط هنا لتحميل ملف PDF",
                        data=pdf_data,
                        file_name=f"Statement_{selected_acc}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        width='stretch'
                    )
                    st.success("✅ تم تجهيز الملف بنجاح، يمكنك التحميل الآن.")
                else:
                    st.error("❌ فشل إنشاء ملف PDF. تأكد من وجود الخط arial.ttf")
                    
            except Exception as e:
                st.error(f"⚠️ حدث خطأ تقني: {str(e)}")
            
# --- صفحة إدارة المستخدمين المتكاملة ---
if choice == "👥 إدارة المستخدمين":
    st.title("👥 إدارة مستخدمي النظام والصلاحيات")
    st.divider()

    # 1. قسم إضافة مستخدم جديد
    with st.expander("➕ إضافة مستخدم جديد للنظام", expanded=True):
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_un = st.text_input("اسم المستخدم (بالإنجليزي - بدون مسافات)")
                new_fn = st.text_input("الاسم الكامل (يظهر في التقارير)")
            with col2:
                new_pw = st.text_input("كلمة المرور", type="password")
                # الرتب بالأسماء البرمجية الموحدة
                new_role = st.selectbox("الصلاحية الأساسية", ["administrator", "admin", "user"])
            
            st.write("---")
            st.write("🔒 **تحديد صلاحيات الوصول الدقيقة (سيتم ضبطها تلقائياً حسب الرتبة ويمكنك التعديل):**")
            
            # منطق توزيع الصلاحيات التلقائي بناءً على اختيار الرتبة
            d_delete, d_reports, d_settings, d_users = False, True, False, False

            if new_role == "administrator":
                d_delete, d_reports, d_settings, d_users = True, True, True, True
            elif new_role == "admin":
                d_delete, d_reports, d_settings, d_users = True, True, True, False
            elif new_role == "user":
                d_delete, d_reports, d_settings, d_users = False, True, False, False

            c1, c2, c3, c4 = st.columns(4) 
            p_delete = c1.checkbox("🗑️ حذف القيود", value=d_delete)
            p_reports = c2.checkbox("📊 عرض التقارير", value=d_reports)
            p_settings = c3.checkbox("⚙️ دخول الإعدادات", value=d_settings)
            p_users = c4.checkbox("👥 إدارة الموظفين", value=d_users)

            submit_user = st.form_submit_button("حفظ المستخدم الجديد", width='stretch')
            
            if submit_user:
                # التأكد من عدم ترك الحقول الأساسية فارغة لضمان التنظيم
                if new_un.strip() and new_pw.strip() and new_fn.strip():
                    
                    # استدعاء الدالة مع مراعاة الترتيب الصحيح للمتغيرات
                    # 1.Username, 2.Full Name, 3.Password, 4.Role, ثم الصلاحيات
                    success, msg = database.add_new_user(
                        new_un.strip().lower(), # اسم المستخدم
                        new_fn.strip(),         # الاسم الكامل (الذي كان يظهر NULL)
                        new_pw,                 # كلمة المرور (سيتم تشفيرها في database.py)
                        new_role,               # الرتبة
                        p_delete,               # حذف القيود
                        p_reports,              # عرض التقارير
                        p_settings,             # دخول الإعدادات
                        p_users                 # إدارة الموظفين
                    )
                    
                    if success:
                        st.success(f"✅ تم إضافة {new_fn} بنجاح كـ {new_role}")
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("⚠️ يرجى كتابة اسم المستخدم، الاسم الكامل، وكلمة المرور.")

    # 2. عرض جدول المستخدمين الحاليين
    st.subheader("📋 المستخدمين الحاليين")
    users_df = database.get_all_users()

    if not users_df.empty:
        # تحسين مسميات الأعمدة للعرض فقط
        display_df = users_df.copy()
        if 'password' in display_df.columns:
            display_df = display_df.drop(columns=['password']) # إخفاء كلمة المرور للأمان

        display_df = display_df.rename(columns={
            'username': 'اسم المستخدم',
            'full_name': 'الاسم الكامل',
            'role': 'الرتبة',
            'can_delete_entry': 'صلاحية الحذف',
            'can_view_reports': 'رؤية التقارير',
            'can_edit_settings': 'تعديل الإعدادات',
            'can_manage_users': 'إدارة الموظفين'
        })
        
        st.dataframe(display_df, width="stretch", hide_index=True)
        
        # 3. قسم الحذف (محمي)
        st.divider()

        # التحقق من الصلاحية للدخول لقسم الحذف
        # نتحقق من الرتبة administrator أو الصلاحية المباشرة
        if st.session_state.get('role') == "administrator" or st.session_state.get('can_users', 0) == 1:
            st.subheader("🗑️ حذف مستخدم")
            
            all_users = users_df['username'].tolist()
            current_logged_in = st.session_state.get('user_name', '')
            
            # القائمة الآمنة: استثناء المستخدم الحالي وحساب admin الرئيسي
            safe_list = [u for u in all_users if u != current_logged_in and u != "admin"]
            
            if safe_list:
                user_to_del = st.selectbox("اختر المستخدم المراد حذفه", safe_list)
                
                if st.button("تأكيد الحذف النهائي", type="primary", width="stretch"):
                    success, msg = database.delete_user(user_to_del)
                    if success:
                        st.success(f"✅ تم حذف المستخدم {user_to_del} بنجاح")
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("ℹ️ لا توجد حسابات أخرى متاحة للحذف.")
        else:
            st.warning("🔒 قسم الحذف متاح فقط للمدير العام (Administrator).")

# 1. تحليل البيانات (الكود الخاص بك)

if choice == "📊 تحليل المبيعات":
    st.title("📊 مركز تحليل البيانات المالية")
    tab1, tab2, tab3 = st.tabs(["💰 المبيعات", "🛒 المشتريات", "📈 المصاريف"])
    
    # جلب البيانات باستخدام استعلام SQL صحيح
    # نستخدم TRY لضمان عدم توقف البرنامج إذا كان الجدول فارغاً
    try:
        all_data = database.db_fetch("SELECT * FROM journal")
    except:
        all_data = pd.DataFrame()

    with tab1:
        if not all_data.empty and 'op_type' in all_data.columns:
            # فلترة عمليات البيع (سواء كاش أو آجل)
            sales = all_data[all_data['op_type'].str.contains('بيع', na=False)]
            if not sales.empty:
                fig_s = px.pie(sales, values='total_amount', names='op_type', 
                               hole=0.5, title="توزيع المبيعات (نقدي/آجل)")
                st.plotly_chart(fig_s, width="stretch")
            else:
                st.info("ℹ️ لا توجد عمليات بيع مسجلة حتى الآن.")
        else:
            st.warning("⚠️ لا توجد بيانات في سجل العمليات حالياً.")

    with tab2:
        if not all_data.empty:
            purchases = all_data[all_data['op_type'].str.contains('شراء', na=False)]
            if not purchases.empty:
                # رسم بياني بالأعمدة للمشتريات حسب التاريخ
                fig_p = px.bar(purchases, x='jv_date', y='total_amount', 
                               color='op_type', title="تحليل المشتريات الزمني")
                st.plotly_chart(fig_p, width="stretch")
            else:
                st.info("ℹ️ لا توجد عمليات شراء مسجلة.")

    with tab3:
        if not all_data.empty:
            expenses = all_data[all_data['op_type'].str.contains('مصروفات', na=False)]
            if not expenses.empty:
                # تحليل المصروفات حسب اسم الحساب (كهرباء، إيجار، إلخ)
                fig_ex = px.bar(expenses, x='acc_name', y='total_amount', 
                                title="تحليل المصروفات حسب الحساب")
                st.plotly_chart(fig_ex, width="stretch")
            else:
                st.info("ℹ️ لا توجد مصروفات مسجلة.")


# 7. الإعدادات
elif choice == "⚙️ الإعدادات":
    st.title("⚙️ صيانة وإعدادات النظام")
    
    # تحويل القيم لنصوص صغيرة لضمان المطابقة التامة مهما كانت حالة الأحرف
    current_user = str(st.session_state.get('username', '')).lower()
    current_role = str(st.session_state.get('role', '')).lower()
    
    # التحقق من الصلاحية: مسموح فقط لاسم المستخدم administrator أو من يحمل صلاحية Administrator
    is_admin = (current_user == "administrator" or current_role == "administrator")

    col_s1, col_s2 = st.columns(2)
    
    # --- العمود الأول: النسخ الاحتياطي (متاح للجميع أو حسب رغبتك) ---
    with col_s1:
        st.subheader("📦 النسخ الاحتياطي")
        st.info("سيتم تصدير سجل القيود الحالي إلى ملف CSV")
        
        cloud_backups = database.get_cloud_backups()

        if st.button("🔄 تنفيذ نسخة احتياطية الآن"):
            with st.spinner("جاري تأمين البيانات ورفعها للسحاب..."):
                # الدالة الآن تقوم بالرفع للسحاب + إنشاء ملف CSV محلي
                path = database.backup_system()
                
                if path:
                    try:
                        # 1. قراءة الملف للتحميل
                        with open(path, "rb") as f:
                            file_data = f.read()
                        
                        # 2. عرض زر تحميل الملف المادي
                        st.download_button(
                            label="💾 تحميل ملف CSV للكمبيوتر",
                            data=file_data,
                            file_name=path,
                            mime="text/csv"
                        )
                        
                        st.success("✅ تم الحفظ سحابياً وتجهيز ملف التحميل")
                        
                        # 3. إظهار زر لتحديث القائمة اليسرى
                        if st.button("🔄 تحديث قائمة النسخ السحابية"):
                            st.rerun()

                    except Exception as e:
                        st.error(f"خطأ في معالجة الملف: {e}")
                else:
                    st.error("❌ فشل إنشاء النسخة الاحتياطية (تأكد من اتصال الإنترنت)")

    # --- العمود الثاني: الاستعادة والصيانة (محصور للمبرمج/الأدمين) ---
    with col_s2:
        st.subheader("⏪ استعادة ذكية من السحاب")
        if is_admin:
            cloud_list = database.get_cloud_backups()
            if cloud_list:
                # تحويل القائمة لقاموس يسهل الاختيار منه
                options = {f"نسخة يوم {b['backup_date']} - (توقيت: {b['created_at']})": b['id'] for b in cloud_list}
                selected = st.selectbox("اختر النسخة المراد العودة إليها:", list(options.keys()))
                
                if st.button("🚀 تأكيد الاستعادة السحابية"):
                    with st.spinner("جاري استبدال البيانات..."):
                        success, msg = database.restore_from_smart_backup(options[selected])
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.info("لا توجد نسخ سحابية محفوظة بعد.")
            
            # قسم صيانة البيانات
            st.markdown("---")
            st.subheader("🧹 صيانة البيانات")
            st.info("استخدم هذا الزر إذا لاحظت عدم دقة في الأرصدة الظاهرة")
            if st.button("🔄 إعادة حساب أرصدة الحسابات"):
                with st.spinner("جاري تدقيق الحسابات..."):
                    success, msg = database.recalculate_all_balances()
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            # هذه الرسالة لن تظهر لك بعد الآن إذا دخلت بحساب administrator
            st.error(f"🚫 عذراً {st.session_state.get('username')}، صلاحية الاستعادة محصورة للمبرمج فقط.")

    # --- فحص جودة الاتصال (أسفل الصفحة) ---
    st.markdown("---")
    if st.button("🔍 فحص جودة الاتصال وتطابق البيانات"):
        with st.spinner("جاري فحص السحاب..."):
            success, info = database.check_system_health()
            if success:
                st.success("✅ اتصال Supabase سليم!")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**أعمدة جدول الحسابات:**")
                    st.json(info['accounts_columns'])
                with col2:
                    st.write("**أعمدة جدول القيود:**")
                    st.json(info['journal_columns'])
            else:
                st.error(f"❌ فشل الفحص: {info}")

 # ... باقي كود سجل المراقبة (Audit Log) كما هو
    st.divider()
    st.subheader("🕵️ سجل العمليات الأخير (Audit Log)")
    audit_data = database.db_fetch("SELECT * FROM audit_log ORDER BY id DESC LIMIT 20")

    st.table(audit_data)
