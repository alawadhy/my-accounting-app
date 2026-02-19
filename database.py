import pandas as pd
import requests
import hashlib
import streamlit as st
import io
import json
from datetime import datetime
from supabase import create_client 

# استيراد أدوات التقارير
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 1. إعدادات الاتصال الآمنة (باستخدام Secrets) ---
# سيبحث Streamlit عن هذه القيم في إعدادات المنصة وليس في الكود
try:
    URL = st.secrets["supabase"]["SUPABASE_URL"]
    KEY = st.secrets["supabase"]["SUPABASE_KEY"]
except KeyError:
    st.error("⚠️ لم يتم العثور على مفاتيح الاتصال. تأكد من ضبط Secrets في Streamlit Cloud.")
    st.stop()

# الهيدرز الخاصة بـ Requests
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# إنشاء اتصال supabase الرسمي
# نضمن أن الرابط ينتهي بالشكل الصحيح لمكتبة السحاب
supabase_url = URL.replace("/rest/v1", "") if "/rest/v1" in URL else URL
supabase = create_client(supabase_url, KEY)

def check_system_health():
    try:
        # فحص وجود الجداول الأساسية
        acc_check = supabase.table("accounts").select("*", count="exact").limit(1).execute()
        jou_check = supabase.table("journal").select("*", count="exact").limit(1).execute()
        
        info = {
            "accounts_columns": ["id", "acc_name", "category", "current_balance"], # مثال
            "journal_columns": ["id", "jv_date", "acc_name", "total_amount"] # مثال
        }
        return True, info
    except Exception as e:
        return False, str(e)

# --- 2. التحقق من الدخول وحقوق المستخدم ---
def verify_user(username, password):
    try:
        # تشفير كلمة المرور المدخلة لمطابقتها مع المخزن
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        
        response = supabase.table("users").select("*").eq("username", username.lower()).execute()
        
        if response.data:
            user = response.data[0]
            # مطابقة الهاش المشفر فقط
            if user['password'] == input_hash:
                return True, {
                    "username": user['username'],
                    "full_name": user.get('full_name', user['username']),
                    "role": user['role'],
                    "can_delete": user.get('can_delete_entry', 0),
                    "can_reports": user.get('can_view_reports', 0),
                    "can_settings": user.get('can_edit_settings', 0),
                    "can_users": user.get('can_manage_users', 0)
                }
        return False, None
    except Exception as e:
        return False, None

# --- 3. إدارة المستخدمين (جلب، إضافة، حذف) ---

def get_all_users():
    """جلب المستخدمين باستخدام مكتبة Supabase"""
    try:
        response = supabase.table("users").select("*").execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching users: {e}")
        return pd.DataFrame()

def add_new_user(username, full_name, password, role, can_delete, can_reports, can_settings, can_users):
    try:
        # تشفير كلمة المرور فوراً قبل إرسالها (لضمان التنظيم)
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        
        payload = {
            "username": username,
            "full_name": full_name,
            "password": hashed_pw, # سيخزن الرمز الطويل المشر
            "role": role,
            "can_delete_entry": int(can_delete),
            "can_view_reports": int(can_reports),
            "can_edit_settings": int(can_settings),
            "can_manage_users": int(can_users)
        }
        
        response = supabase.table("users").insert(payload).execute()
        return True, "تم الحفظ بنجاح"
    except Exception as e:
        return False, str(e)

def delete_user(username):
    """حذف مستخدم نهائياً من قاعدة البيانات"""
    try:
        response = requests.delete(f"{URL}/users?username=eq.{username}", headers=HEADERS)
        if response.status_code in [200, 204]:
            return True, f"تم حذف المستخدم {username} بنجاح."
        return False, f"فشل الحذف، استجابة السيرفر: {response.status_code}"
    except Exception as e:
        return False, str(e)

# --- 4. العمليات المحاسبية والبيانات العامة ---

def db_fetch(query, params=None):
    # تعريف الأعمدة القياسية لضمان ثبات الواجهة
    STD_COLUMNS = {
        "accounts": ["id", "acc_name", "name", "current_balance", "category", "opening_balance"],
        "journal": ["id", "date", "jv_date", "acc_name", "total_amount", "debit", "credit", "op_type", "description", "ref_no"]
    }
    
    table_name = "accounts"
    
    try:
        # 1. استخراج اسم الجدول
        clean_query = query.strip().upper()
        if "FROM " in clean_query:
            table_name = clean_query.split("FROM ")[1].split(" ")[0].lower().strip()
        else:
            table_name = query.strip().lower()

        # 2. جلب البيانات
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data) if response.data else pd.DataFrame()

        # 3. معالجة البيانات (حتى وهي موجودة في القاعدة)
        if not df.empty:
            # --- حل مشكلة التاريخ (ArrowTypeError) ---
            for col in df.columns:
                # تحويل أي عمود يحتوي على كلمة تاريخ إلى نص ليعرضه Streamlit بلا مشاكل
                if 'date' in col.lower() or 'التاريخ' in col or 'jv_date' in col:
                    df[col] = df[col].astype(str)
                
                # تحويل القيم الفارغة في مبالغ المدين والدائن إلى أصفار بدلاً من None
                if col in ['debit', 'credit', 'current_balance', 'total_amount', 'opening_balance']:
                    df[col] = df[col].fillna(0)

            # توحيد مسميات الأعمدة
            if "acc_name" in df.columns and "name" not in df.columns:
                df["name"] = df["acc_name"]
            
            if table_name == "journal":
                if "date" in df.columns and "jv_date" not in df.columns:
                    df["jv_date"] = df["date"]
                elif "jv_date" in df.columns and "date" not in df.columns:
                    df["date"] = df["jv_date"]
        else:
            # 4. إذا كان الجدول فارغاً
            df = pd.DataFrame(columns=STD_COLUMNS.get(table_name, ["id"]))

        return df

    except Exception as e:
        print(f"❌ خطأ حرج في جلب بيانات {table_name}: {e}")
        return pd.DataFrame(columns=STD_COLUMNS.get(table_name, ["id"]))

def advanced_search_journal(query):
    try:
        # البحث في اسم الحساب أو رقم المرجع أو البيان
        res = supabase.table("journal").select("*").or_(f"acc_name.ilike.%{query}%,ref_no.ilike.%{query}%,description.ilike.%{query}%").order("id", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def generate_acc_code(category):
    prefix_map = {
        "مورد": "SUP", "عميل": "CUS", "صندوق/كاش": "CSH",
        "بنك": "BNK", "فرع": "BRN", "مصروفات": "EXP", "إيرادات أخرى": "REV"
    }
    prefix = prefix_map.get(category, "ACC")
    year = 2026 # السنة الحالية
    
    try:
        # نبحث عن آخر حساب تم تسجيله يبدأ بنفس الكود
        res = supabase.table("accounts").select("acc_code").like("acc_code", f"{prefix}{year}-%").order("acc_code", desc=True).limit(1).execute()
        
        if res.data:
            last_code = res.data[0]['acc_code']
            # نأخذ الرقم الأخير ونزيده 1
            last_num = int(last_code.split('-')[-1])
            return f"{prefix}{year}-{str(last_num + 1).zfill(4)}"
        else:
            return f"{prefix}{year}-0001"
    except:
        return f"{prefix}{year}-0001"

def process_full_transaction(acc_name, offset_acc, op_type, amount, use_tax, description, ref_no, date_str, posted_by, due_date=None):
    """
    النسخة الاحترافية: تدعم الحساب التلقائي لتاريخ الاستحقاق للعمليات الآجلة
    لضمان ظهورها في تقارير الديون والالتزامات.
    """
    try:
        amount = float(amount)
        tax = (amount * 0.15) if use_tax else 0
        total = amount + tax
        
        # 1. تحديد المدين والدائن
        is_revenue = any(x in op_type for x in ["بيع", "قبض", "إيراد"])
        deb, crd = (0, total) if is_revenue else (total, 0)

        # 2. منطق ذكي لتاريخ الاستحقاق: 
        # إذا كانت العملية "آجلة" ولم يتم إدخال تاريخ استحقاق، نقوم بإضافة 30 يوم تلقائياً
        final_due_date = due_date
        if "آجل" in op_type and not due_date:
            from datetime import datetime, timedelta
            current_date = datetime.strptime(date_str, '%Y-%m-%d')
            final_due_date = (current_date + timedelta(days=30)).strftime('%Y-%m-%d')

        payload = {
            "date": date_str,
            "acc_name": acc_name,
            "offset_acc": offset_acc,
            "op_type": op_type,
            "description": description,
            "ref_no": ref_no,
            "base_amount": amount,
            "tax_amount": tax,
            "total_amount": total,
            "debit": deb,
            "credit": crd,
            "posted_by": posted_by,
            "due_date": final_due_date  # القيمة المحسنة
        }
        
        res = supabase.table("journal").insert(payload).execute()
        
        if res.data:
            update_account_balance(acc_name, deb, crd)
            update_account_balance(offset_acc, crd, deb)
            return True, "✅ تم ترحيل القيد بنجاح"
        
        return False, "❌ فشل في حفظ البيانات"
    except Exception as e:
        return False, f"❌ خطأ تقني: {str(e)}"

def get_supplier_due_amounts():
    """جلب فواتير المشتريات الآجلة مع تنظيف البيانات"""
    df = db_fetch("journal") 
    if df.empty or 'op_type' not in df.columns:
        return pd.DataFrame()

    # تصفية المشتريات الآجلة فقط
    due_df = df[df['op_type'].str.contains('شراء آجل', na=False)].copy()
    
    if due_df.empty:
        return pd.DataFrame()

    # معالجة التواريخ بحذر
    due_df['jv_date'] = pd.to_datetime(due_df['jv_date']).dt.date
    # إذا لم يوجد تاريخ استحقاق، نفترض 30 يوماً
    due_df['due_date'] = pd.to_datetime(due_df.get('due_date', None)).fillna(
        pd.to_datetime(due_df['jv_date']) + pd.Timedelta(days=30)
    ).dt.date
    
    # حساب الأيام المتبقية
    today = datetime.now().date()
    due_df['days_left'] = due_df['due_date'].apply(lambda x: (x - today).days)
    
    return due_df[['acc_name', 'jv_date', 'due_date', 'total_amount', 'days_left']]
    
def log_event(user, action, details):
    try:
        payload = {
            "user_name": str(user),
            "action": str(action),
            "details": str(details) 
            # حذفنا السطر الخاص بالـ timestamp لنترك القاعدة تسجله تلقائياً
        }
        # محاولة الإرسال
        supabase.table("audit_log").insert(payload).execute()
    except Exception as e:
        # قمنا بتغيير البرينت ليعطيك سبب الخطأ الحقيقي بدلاً من رسالة عامة
        print(f"⚠️ تنبيه: فشل التسجيل في audit_log. السبب: {e}")

def update_account_balance(acc_name, debit_change=0, credit_change=0):
    """
    النسخة الاحترافية: تعيد احتساب الرصيد من واقع حركات القيد لضمان الدقة المطلقة
    وتجنب أخطاء التراكم اليدوي.
    """
    try:
        # 1. جلب الرصيد الافتتاحي من جدول الحسابات
        acc_res = supabase.table("accounts").select("opening_balance").eq("acc_name", acc_name).execute()
        opening_bal = float(acc_res.data[0].get('opening_balance', 0)) if acc_res.data else 0.0
        
        # 2. جلب مجموع الحركات المدينة والدائنة من جدول القيود لهذا الحساب
        journal_res = supabase.table("journal").select("debit, credit").eq("acc_name", acc_name).execute()
        
        total_debit = sum(float(row.get('debit', 0)) for row in journal_res.data)
        total_credit = sum(float(row.get('credit', 0)) for row in journal_res.data)
        
        # 3. المعادلة المحاسبية الذهبية
        # الرصيد الحالي = الرصيد الافتتاحي + (إجمالي المدين - إجمالي الدائن)
        new_balance = opening_bal + (total_debit - total_credit)
        
        # 4. تحديث الرصيد النهائي في جدول الحسابات
        supabase.table("accounts").update({"current_balance": new_balance}).eq("acc_name", acc_name).execute()
        
        return True
    except Exception as e:
        print(f"❌ خطأ في تحديث رصيد الحساب {acc_name}: {e}")
        return False

def get_statement(acc_name, from_date, to_date):
    """
    النسخة الاحترافية الكاملة:
    1. تحسب الرصيد المنقول (قبل تاريخ البداية).
    2. ترتب القيود بالثانية عبر المعرف ID لضبط العمليات المتكررة في نفس اليوم.
    """
    try:
        # 1. جلب الرصيد المنقول (ما قبل فترة البحث)
        # نستخدم الدالة الموجودة مسبقاً في ملفك get_opening_balance_logic
        opening_bal = get_opening_balance_logic(acc_name, from_date)
        
        # 2. جلب الحركات من Supabase مع ترتيب مزدوج (التاريخ ثم ID)
        res = supabase.table("journal")\
            .select("*")\
            .eq("acc_name", acc_name)\
            .gte("date", from_date)\
            .lte("date", to_date)\
            .order("date", desc=False)\
            .order("id", desc=False)\
            .execute()
            
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
        
        # 3. إنشاء سطر الرصيد المنقول يدوياً ليظهر في أعلى الجدول
        opening_row = pd.DataFrame([{
            'date': pd.to_datetime(from_date),
            'ref_no': '---',
            'description': 'رصيد منقول من فترة سابقة',
            'debit': 0.0,
            'credit': 0.0,
            'balance': opening_bal
        }])

        if not df.empty:
            # تحويل التواريخ والترتيب
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(by=['date', 'id'], ascending=[True, True])
            
            # 4. حساب الرصيد التراكمي انطلاقاً من الرصيد المنقول
            # الرصيد الجديد = الرصيد المنقول + (مجموع المدين - مجموع الدائن)
            df['balance'] = opening_bal + (df['debit'] - df['credit']).cumsum()
            
            # دمج سطر الرصيد المنقول مع بقية الحركات
            df = pd.concat([opening_row, df], ignore_index=True)
        else:
            # إذا لم توجد حركات في الفترة، يظهر الرصيد المنقول فقط
            df = opening_row

        # تنسيق التاريخ للعرض
        df['date_display'] = df['date'].dt.strftime('%Y-%m-%d')
        
        return df
    except Exception as e:
        print(f"❌ خطأ في دالة كشف الحساب المحدثة: {e}")
        return pd.DataFrame()

def init_db():
    """دالة لتهيئة قاعدة البيانات (غير مطلوبة في Supabase)"""
    pass

def generate_jv_ref(op_type):
    prefix = "INV" if "بيع" in op_type else "VCH"
    return f"{prefix}-{datetime.now().strftime('%y%m%d%H%M')}"

def get_recent_transactions(limit=20):
    try:
        res = requests.get(f"{URL}/journal?order=id.desc&limit={limit}", headers=HEADERS)
        return pd.DataFrame(res.json()) if res.status_code == 200 else pd.DataFrame()
    except:
        return pd.DataFrame()

def delete_journal_entry(entry_id, user_role, user_name):
    # التحقق من الصلاحية
    if user_role.lower() not in ["administrator", "admin"]:
        return False, "🚫 عذراً، لا تملك صلاحية الحذف"
        
    try:
        # قبل الحذف، يجب عكس أثر القيد على الأرصدة (اختياري لكنه ممارسة محاسبية سليمة)
        res = supabase.table("journal").delete().eq("id", entry_id).execute()
        if res.data:
            log_event(user_name, "حذف قيد", f"تم حذف القيد رقم {entry_id}")
            return True, "✅ تم حذف القيد بنجاح"
        return False, "❌ لم يتم العثور على القيد"
    except Exception as e:
        return False, str(e)

def db_write(table_name, data=None, action="INSERT", row_id=None):
    try:
        if action == "INSERT":
            res = supabase.table(table_name).insert(data).execute()
        elif action == "UPDATE":
            res = supabase.table(table_name).update(data).eq("id", row_id).execute()
        elif action == "DELETE":
            res = supabase.table(table_name).delete().eq("id", row_id).execute()
        return (True, "تمت العملية بنجاح") if res.data else (False, "فشلت العملية")
    except Exception as e:
        return False, str(e)

def update_account(acc_id, account_data):
    try:
        res = supabase.table("accounts").update(account_data).eq("id", acc_id).execute()
        return (True, "✅ تم التحديث") if res.data else (False, "❌ فشل")
    except Exception as e:
        return False, str(e)
def update_record(table, column_name, value, update_data):
    """تحديث سجل موجود بالسحاب"""
    try:
        supabase.table(table).update(update_data).eq(column_name, value).execute()
        return True, "تم التحديث بنجاح ✅"
    except Exception as e:
        return False, f"خطأ في التحديث: {str(e)}"

    
def backup_system():
    try:
        # 1. جلب البيانات من جدول القيود
        df = db_fetch("journal") 
        if df.empty: return None
        
        # 2. تحويل البيانات لـ JSON لرفعها للسحاب
        json_data = df.to_json(orient='records')
        
        # 3. الرفع للسحاب
        entry = {
            "backup_date": datetime.now().strftime("%Y-%m-%d"),
            "data_json": json_data
        }
        supabase.table("system_backups").insert(entry).execute()
        
        # 4. إنشاء ملف CSV محلي (هذا ما ينتظره كود Streamlit الخاص بك)
        file_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        return file_path # سيعود المسار لـ Streamlit لكي يفتحه
    except Exception as e:
        print(f"Backup Error: {e}")
        return None

def get_backup_files():
    import glob
    return glob.glob("backup_*.csv")

def update_journal_entry(entry_id, new_acc, new_amt, new_desc, op_type):
    """تعديل بيانات قيد مالي موجود مسبقاً"""
    try:
        # 1. تجهيز الأرقام
        amount = float(new_amt)
        tax = amount * 0.15 
        total = amount + tax

        # 2. تحديد المنطق المحاسبي
        is_revenue = any(x in op_type for x in ["بيع", "قبض", "إيراد"])
        deb, crd = (0, total) if is_revenue else (total, 0)

        # 3. القاموس المحدث (Payload)
        payload = {
            "acc_name": new_acc,
            "base_amount": amount,
            "tax_amount": tax,
            "total_amount": total,
            "description": new_desc, # تم استخدام الاسم الكامل كما ظهر في الفحص
            "debit": deb,
            "credit": crd
        }
        
        # 4. التنفيذ في Supabase
        res = supabase.table("journal").update(payload).eq("id", entry_id).execute()
        
        if res.data:
            return True, "✅ تم تحديث بيانات القيد بنجاح"
        return False, "❌ لم يتم العثور على القيد المطلوب"
    except Exception as e:
        return False, f"❌ خطأ أثناء التعديل: {str(e)}"
    

def update_account(acc_id, account_data):
    """تعديل حساب - بناءً على خطأ الصورة image_6eda80"""
    try:
        res = supabase.table("accounts").update(account_data).eq("id", acc_id).execute()
        return (True, "✅ تم تحديث الحساب") if res.data else (False, "❌ فشل التحديث")
    except Exception as e:
        return False, str(e)
    
def get_detailed_debts():
    """تحليل احترافي للديون المستحقة للموردين"""
    df = db_fetch("journal")
    if df.empty or 'op_type' not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    # 1. تصفية المشتريات الآجلة فقط
    due_df = df[df['op_type'].str.contains('شراء آجل', na=False)].copy()
    if due_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 2. معالجة التواريخ
    today = datetime.now().date()
    due_df['due_date'] = pd.to_datetime(due_df.get('due_date', None)).fillna(
        pd.to_datetime(due_df['jv_date']) + pd.Timedelta(days=30)
    ).dt.date

    # 3. حساب التأخير بالأيام
    due_df['days_diff'] = due_df['due_date'].apply(lambda x: (today - x).days)

    # الفئة أ: مستحقون حالياً (تاريخ اليوم تجاوز تاريخ الاستحقاق)
    urgent = due_df[due_df['days_diff'] >= 0].copy()
    
    # الفئة ب: خطر جداً (تجاوزوا شهر كامل من تاريخ الاستحقاق)
    critical = urgent[urgent['days_diff'] > 30].copy()

    return urgent, critical

def create_pdf_report(df, account_name, start_date, end_date):
    """النسخة المحدثة: تمنع خروج النص من الجداول وترتب البيانات بدقة"""
    try:
        buffer = io.BytesIO()
        # إنشاء الوثيقة مع هوامش (Margins)
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        # تسجيل الخط العربي
        pdfmetrics.registerFont(TTFont('ArabicFont', 'arial.ttf'))
        
        # إعداد نمط النص العربي مع خاصية التفاف النص (Word Wrap)
        styles = getSampleStyleSheet()
        style_ar = styles['Normal']
        style_ar.fontName = 'ArabicFont'
        style_ar.fontSize = 10
        style_ar.alignment = 1  # سنتر
        style_ar.wordWrap = 'CJK' # تفعيل الالتفاف لمنع خروج النص

        # 1. العنوان
        elements.append(Paragraph(f"<b>تقرير كشف حساب تفصيلي</b>", style_ar))
        elements.append(Paragraph(f"اسم الحساب: {account_name}", style_ar))
        elements.append(Paragraph(f"الفترة من {start_date} إلى {end_date}", style_ar))
        elements.append(Spacer(1, 20)) # مسافة فارغة

        # 2. تجهيز بيانات الجدول
        # نضع العناوين أولاً
        table_data = [["التاريخ", "المرجع", "البيان", "مدين", "دائن", "الرصيد"]]
        
        for _, row in df.iterrows():
            table_data.append([
                str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date']),
                str(row.get('ref_no', '')),
                Paragraph(str(row.get('description', '') or row.get('op_type', '')), style_ar), # هنا سر الحل
                f"{row.get('debit', 0):,.2f}",
                f"{row.get('credit', 0):,.2f}",
                f"{row.get('balance', 0):,.2f}"
            ])

        # 3. تحديد عرض الأعمدة (مجموع عرض A4 المتاح هو 530 تقريباً)
        # وسعنا عمود البيان (180) ليأخذ راحته في الكتابة
        column_widths = [75, 85, 180, 60, 60, 70]
        
        pdf_table = Table(table_data, colWidths=column_widths)

        # 4. تنسيق شكل الجدول
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D47A1")), # لون الترويسة أزرق غامق
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black), # رسم خطوط الشبكة
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # توسيط النص عمودياً
        ])
        pdf_table.setStyle(style)

        elements.append(pdf_table)

        # 5. التذييل (الرصيد النهائي)
        final_bal = df['balance'].iloc[-1] if not df.empty else 0
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"الرصيد النهائي المستحق: {abs(final_bal):,.2f} ريال", style_ar))
        
        # بناء الـ PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        print(f"PDF Error: {str(e)}")
        return None

def get_opening_balance_logic(acc_name, start_date):
    """حساب الرصيد الذي يسبق تاريخ البحث المختار"""
    try:
        # جلب الرصيد الأساسي عند التأسيس
        acc_data = supabase.table("accounts").select("opening_balance").eq("acc_name", acc_name).execute()
        initial_bal = float(acc_data.data[0]['opening_balance']) if acc_data.data else 0.0
        
        # جلب كافة الحركات قبل تاريخ البداية
        pre_entries = supabase.table("journal").select("debit, credit").eq("acc_name", acc_name).lt("date", start_date).execute()
        
        if pre_entries.data:
            sum_debit = sum(float(item['debit']) for item in pre_entries.data)
            sum_credit = sum(float(item['credit']) for item in pre_entries.data)
            return initial_bal + (sum_debit - sum_credit)
        
        return initial_bal
    except:
        return 0.0
    
def restore_backup_to_supabase(uploaded_file):
    """استرجاع القيود من ملف CSV إلى قاعدة بيانات السحاب"""
    try:
        # قراءة البيانات
        df = pd.read_csv(uploaded_file)
        
        # تحويل الأعمدة لتناسب القاعدة (حذف id ليتولد تلقائياً)
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
            
        data_to_restore = df.to_dict(orient='records')
        
        # إرسال البيانات للسحاب
        res = supabase.table("journal").insert(data_to_restore).execute()
        
        return True, f"✅ تم استرجاع {len(res.data)} قيد بنجاح"
    except Exception as e:
        return False, f"❌ خطأ أثناء الاسترجاع: {str(e)}"
    
def recalculate_all_balances():
    try:
        # جلب كل الحسابات
        acc_res = supabase.table("accounts").select("acc_name").execute()
        if not acc_res.data: return False, "لا توجد حسابات"
        
        for acc in acc_res.data:
            name = acc['acc_name']
            # جلب حركات هذا الحساب
            j_res = supabase.table("journal").select("debit, credit").eq("acc_name", name).execute()
            
            total_debit = sum(float(row.get('debit', 0)) for row in j_res.data)
            total_credit = sum(float(row.get('credit', 0)) for row in j_res.data)
            new_bal = total_debit - total_credit
            
            # التحديث في جدول الحسابات (تأكد أن العمود اسمه current_balance)
            supabase.table("accounts").update({"current_balance": new_bal}).eq("acc_name", name).execute()
            
        return True, "تم التحديث بنجاح"
    except Exception as e:
        print(f"Error in recalculate: {e}")
        return False, str(e)

def auto_smart_backup():
    """
    النظام الذكي: 
    1. يحفظ نسخة CSV محلياً.
    2. يحفظ نسخة JSON في السحاب.
    3. يحدّث نسخة اليوم إذا تكررت، ويحتفظ بنسخ الأيام السابقة.
    """
    try:
        # جلب البيانات الحالية
        res = supabase.table("journal").select("*").execute()
        current_data = res.data
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # --- الجزء الأول: النسخة السحابية (JSON) ---
        # فحص هل توجد نسخة لليوم؟
        existing = supabase.table("system_backups").select("id").eq("backup_date", today_date).execute()
        
        payload = {
            "backup_date": today_date,
            "data_json": current_data
        }
        
        if existing.data:
            # تحديث نسخة اليوم (لتبقى دائماً عند آخر دقيقة)
            supabase.table("system_backups").update(payload).eq("id", existing.data[0]['id']).execute()
        else:
            # إنشاء نسخة جديدة ليوم جديد
            supabase.table("system_backups").insert(payload).execute()
            
        # --- الجزء الثاني: النسخة المحلية (CSV) ---
        df = pd.DataFrame(current_data)
        filename = f"backup_{today_date}.csv"
        df.to_csv(filename, index=False)
        
        return True
    except Exception as e:
        print(f"Smart Backup Error: {e}")
        return False

def get_cloud_backups():
    try:
        # هذه الدالة تجلب قائمة النسخ الاحتياطية من الجدول الذي أصلحناه
        response = supabase.table('system_backups').select('*').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"خطأ في جلب البيانات: {e}")
        return []

def restore_from_smart_backup(backup_id):
    """النسخة المحصنة: استعادة البيانات مع ضمان تنظيف الجدول وإعادة الهيكلة"""
    try:
        # 1. التحقق من المعرف
        if not backup_id or str(backup_id) in ["0", "None"]:
            return False, "⚠️ يرجى اختيار نسخة احتياطية من القائمة أولاً"

        # 2. جلب البيانات من السحاب
        res = supabase.table("system_backups").select("data_json").eq("id", int(backup_id)).execute()
        if not res.data: 
            return False, "❌ عذراً، لم يتم العثور على ملف النسخة في السحاب"
        
        raw_data = res.data[0]['data_json']
        records = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

        if not records:
            return False, "⚠️ هذه النسخة الاحتياطية لا تحتوي على أي سجلات"

        # 3. تنظيف البيانات (إزالة الحقول التي تولدها القاعدة تلقائياً)
        # هذا يمنع تعارض المعرفات (Primary Key Conflicts)
        clean_records = []
        for r in records:
            # نحتفظ بكل شيء ما عدا المعرف التسلسلي والوقت التلقائي
            item = {k: v for k, v in r.items() if k not in ['id', 'created_at']}
            clean_records.append(item)

        # 4. الحذف الآمن (Force Clear) 
        # نستخدم gte(id, 0) لأنها أسرع وأضمن في الفلترة لجميع أنواع الجداول
        try:
            supabase.table("journal").delete().gte("id", 0).execute()
        except:
            # إذا كان المعرف ليس رقماً، نستخدم الفلتر النصي كبديل
            supabase.table("journal").delete().neq("acc_name", "NULL_DATA_RESERVED").execute()
        
        # 5. الرفع الذكي على دفعات (Batching)
        # تم تصغير الدفعة لـ 100 لضمان عدم تجاوز حجم الطلب (Request Size Limit)
        chunk_size = 100
        for i in range(0, len(clean_records), chunk_size):
            batch = clean_records[i:i + chunk_size]
            supabase.table("journal").insert(batch).execute()
            
        # 6. تحديث الأرصدة فوراً بعد الاستعادة لضمان مطابقة الأرقام
        recalculate_all_balances() 
        
        return True, f"✅ تم استعادة {len(clean_records)} قيد مالي وتحديث الأرصدة بنجاح"

    except Exception as e:
        error_msg = str(e)
        if "UUID" in error_msg:
            return False, "❌ خطأ في تنسيق المعرفات: يرجى التأكد من تطابق أنواع البيانات في الجداول"

        return False, f"❌ فشلت عملية الاستعادة: {error_msg}"

