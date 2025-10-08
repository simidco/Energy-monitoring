import streamlit as st
import importlib.util
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from persiantools.jdatetime import JalaliDate
import os
import io
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
import numpy as np
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib import colors
import io
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io
from reportlab.platypus import Image  # اضافه برای تصویر
from sklearn.ensemble import IsolationForest
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pulp import LpProblem, LpMinimize, LpVariable, LpStatus, value
import statsmodels.api as sm
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from pulp import *
# بررسی کتابخانه‌ها
required_libraries = [
    "streamlit", "pandas", "plotly", "matplotlib", "seaborn",
    "sklearn", "persiantools", "reportlab", "xlsxwriter", "pulp", "statsmodels", "prophet"
]

def check_libraries():
    missing = []
    for lib in required_libraries:
        if importlib.util.find_spec(lib) is None:
            missing.append(lib)
    if missing:
        st.error(f"⚠️ کتابخانه‌های زیر نصب نیستند: {', '.join(missing)}\nلطفاً آن‌ها را با دستور زیر نصب کنید:\n`pip install {' '.join(missing)}`")
        st.stop()

check_libraries()

st.set_page_config(page_title="داشبورد پایش برق کنسانتره", layout="wide")

# ----------- پس‌زمینه و فونت -----------
page_bg_img = '''
<style>
.stApp {
    background-image: url("https://images.unsplash.com/photo-1581093588401-1ebdd1b6b47d?ixlib=rb-4.0.3&auto=format&fit=crop&w=1470&q=80");
    background-size: cover;
    background-attachment: fixed;
    background-color: rgba(0, 0, 0, 0.5);
    color: white;
    font-family: Tahoma, Vazir, sans-serif;
    font-size: 16px;
}
</style>
'''
st.markdown(page_bg_img, unsafe_allow_html=True)

# ----------- بارگذاری لوگو -----------
st.sidebar.subheader("🏷️ بارگذاری لوگو شرکت")
uploaded_logo = st.sidebar.file_uploader("آپلود لوگو (PNG/JPG)", type=["png", "jpg", "jpeg"])
if uploaded_logo:
    try:
        st.sidebar.image(uploaded_logo, width=150)
    except Exception as e:
        st.sidebar.error(f"خطا در بارگذاری لوگو: {e}")

# ----------- بارگذاری و پردازش اکسل -----------
def load_excel(file):
    log_messages = []  # لیست برای ذخیره پیام‌ها

    try:
        xls = pd.ExcelFile(file)
        log_messages.append(f"📌 فایل اکسل با {len(xls.sheet_names)} شیت بارگذاری شد: {xls.sheet_names}")
    except Exception as e:
        log_messages.append(f"⚠️ خطا در خواندن فایل اکسل: {e}")
        return pd.DataFrame(), log_messages

    dfs = []
    for sheet in xls.sheet_names:
        df_sheet = pd.read_excel(file, sheet_name=sheet, header=None)
        df_sheet = df_sheet.dropna(axis=1, how="all")
        log_messages.append(f"📊 شیت {sheet} با {df_sheet.shape[0]} ردیف و {df_sheet.shape[1]} ستون بارگذاری شد.")

        header_row = None
        for i, row in df_sheet.iterrows():
            row_str = row.astype(str)
            if row_str.str.contains(r'^\d{4}/\d{2}/\d{2}$', na=False).any() or pd.to_datetime(row_str, errors="coerce").notna().any():
                header_row = i - 1
                break
        if header_row is None:
            log_messages.append(f"⚠️ شیت {sheet} فاقد هدر معتبر است و نادیده گرفته شد.")
            continue

        raw_headers = df_sheet.iloc[header_row].fillna("بدون عنوان")
        seen, unique_headers = {}, []
        for col in raw_headers:
            if col not in seen:
                seen[col] = 0
                unique_headers.append(col)
            else:
                seen[col] += 1
                unique_headers.append(f"{col}_{seen[col]}")

        df_data = df_sheet[header_row + 1:].copy()
        df_data.columns = unique_headers
        df_data = df_data.rename(columns={df_data.columns[0]: "تاریخ"})
        log_messages.append(f"📋 ستون‌های شیت {sheet}: {list(df_data.columns)}")

        # بررسی و تبدیل تاریخ
        df_data["تاریخ"] = df_data["تاریخ"].astype(str)
        if df_data["تاریخ"].str.contains(r'^\d{4}/\d{2}/\d{2}$', na=False).any():
            def parse_jalali_date(date_str):
                try:
                    year, month, day = map(int, date_str.split('/'))
                    return JalaliDate(year, month, day).to_gregorian()
                except:
                    return pd.NaT
            df_data["تاریخ"] = df_data["تاریخ"].apply(parse_jalali_date)
            log_messages.append(f"📅 تاریخ‌های شیت {sheet} به‌عنوان تاریخ شمسی پردازش شدند.")
        else:
            df_data["تاریخ"] = pd.to_datetime(df_data["تاریخ"], errors="coerce")

        df_data = df_data.dropna(subset=["تاریخ"])
        if df_data.empty:
            log_messages.append(f"⚠️ شیت {sheet} پس از حذف تاریخ‌های نامعتبر خالی است.")
            continue

        df_data["تاریخ شمسی"] = df_data["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m/%d') if pd.notnull(x) else "")
        for col in df_data.columns:
            if col not in ["تاریخ", "تاریخ شمسی"]:
                df_data[col] = pd.to_numeric(df_data[col], errors="coerce")
        df_data["کارخانه"] = sheet
        dfs.append(df_data)

    if not dfs:
        log_messages.append("⚠️ هیچ داده معتبری از شیت‌ها بارگذاری نشد.")
        return pd.DataFrame(), log_messages

    df = pd.concat(dfs, ignore_index=True)
    log_messages.append(f"📊 DataFrame نهایی با {df.shape[0]} ردیف و {df.shape[1]} ستون ایجاد شد.")
    return df, log_messages

# ----------- دریافت داده با کش -----------
@st.cache_data
def get_data(file):
    with st.spinner("⏳ در حال بارگذاری داده‌ها..."):
        return load_excel(file)

# ----------- بارگذاری فایل Excel -----------
default_excel_path = "نمونه_کنسانتره.xlsx"
uploaded_file = st.file_uploader("📂 لطفاً فایل اکسل کنسانتره را بارگذاری کنید", type=["xlsx"])
if uploaded_file is None:
    if os.path.exists(default_excel_path):
        uploaded_file = default_excel_path
        st.info("📌 از فایل پیش‌فرض استفاده شده است: نمونه_کنسانتره.xlsx")
    else:
        st.warning("⚠️ فایل اکسل بارگذاری نشده و فایل پیش‌فرض هم موجود نیست.")
        st.stop()

df, logs = get_data(uploaded_file)

# نمایش لاگ‌ها فقط در Expander
with st.expander("🔍 گزارش بارگذاری فایل"):
    for msg in logs:
        st.info(msg)

# اگر داده خالی بود متوقف کن
if df.empty:
    st.error("⚠️ هیچ داده‌ای از فایل اکسل بارگذاری نشد. لطفاً فایل اکسل را بررسی کنید.")
    st.stop()

# ----------- فیلتر کارخانه و تاریخ -----------
factories = df["کارخانه"].unique().tolist()
st.sidebar.header("🏭 انتخاب کارخانه")
select_all = st.sidebar.button("انتخاب همه")
if select_all:
    selected_factories = factories
else:
    selected_factories = st.sidebar.multiselect("انتخاب کارخانه (کارخانه‌ها)", factories, default=factories)
if not selected_factories:
    st.warning("⚠️ لطفاً حداقل یک کارخانه انتخاب کنید.")
    st.stop()
filtered_df = df[df["کارخانه"].isin(selected_factories)]

st.sidebar.header("🎯 فیلتر بازه زمانی")
min_date, max_date = filtered_df["تاریخ"].min(), filtered_df["تاریخ"].max()
start_date, end_date = st.sidebar.date_input("بازه زمانی", [min_date, max_date])

# نمایش تاریخ شمسی در زیر تقویم
st.sidebar.markdown(f"**تاریخ شمسی شروع:** {JalaliDate(start_date).strftime('%Y/%m/%d')}")
st.sidebar.markdown(f"**تاریخ شمسی پایان:** {JalaliDate(end_date).strftime('%Y/%m/%d')}")

# ... (بخش‌های قبلی: فیلتر کارخانه و تاریخ)

mask = (filtered_df["تاریخ"] >= pd.to_datetime(start_date)) & (filtered_df["تاریخ"] <= pd.to_datetime(end_date))
filtered_df = filtered_df.loc[mask]
if filtered_df.empty:
    st.warning("⚠️ هیچ داده‌ای برای بازه زمانی انتخاب‌شده یافت نشد.")
    st.stop()

# 👈 تابع monte_carlo_simulation رو اینجا اضافه کن (قبل از تب‌ها)
@st.cache_data
def monte_carlo_simulation(base_consumption, scenarios, n_sim=1000, change_factor=20):
    """
    شبیه‌سازی مونت‌کارلو با فاکتور تغییر متغیر.
    """
    results = []
    low_bound = 1 - change_factor / 100
    high_bound = 1 + change_factor / 100
    for _ in range(n_sim):
        sim = base_consumption * np.random.uniform(low_bound, high_bound, len(scenarios))
        results.append(sim)
    return pd.DataFrame(results, columns=scenarios)

# دیکشنری ترجمه برای fallback انگلیسی (گسترش‌یافته) - به صورت جهانی تعریف شد
translations = {
    "میانگین مصرف تجهیزات": "Average Equipment Consumption",
    "تجهیز": "Equipment",
    "میانگین مصرف": "Avg Consumption",
    "روند مصرف": "Consumption Trend",
    "ماه شمسی": "Jalali Month",
    "مجموع": "Total",
    "میانگین": "Average",
    "ماه": "Month",
    "روز": "Day",
    "مصرف": "Consumption",
    "تاریخ": "Date",
    "پیش‌بینی": "Forecast",
    "KPI": "KPI",
    "مجموع مصرف": "Total Consumption",
    "میانگین مصرف": "Average Consumption",
    "بیشترین مصرف": "Max Consumption",
    "درصد تغییر": "Percent Change",
    "MAE": "MAE",
    "RMSE": "RMSE",
    "مدل": "Model",
    "R²": "R²",
    "p-value": "p-value",
    "UCL": "UCL",
    "LCL": "LCL",
    "ناهنجاری‌ها": "Anomalies",
    "CO2": "CO2",
    "انتشار CO2": "CO2 Emissions",
    "هزینه": "Cost",
    "مصرف اوج": "Peak Consumption",
    "مصرف خارج اوج": "Off-Peak Consumption",
    "کل": "Total",
    "نمودار مصرف ماهیانه": "Monthly Consumption Chart",
    "Heatmap مصرف تجهیزات": "Equipment Consumption Heatmap",
    "گزارش تجهیزات": "Equipment Report",
    "پیش‌بینی مصرف تجهیزات": "Equipment Consumption Forecast",
    "KPI پیشرفته": "Advanced KPI",
    "تحلیل روند تغییرات": "Trend Change Analysis",
    "جدول خطاها": "Error Table",
    "تحلیل دیتا": "Data Analysis",
    "تشخیص ناهنجاری‌ها": "Anomaly Detection",
    "گزارش زیست‌محیطی": "Environmental Report",
    "مقایسه با استانداردهای صنعتی": "Comparison with Industry Standards",
    "تحلیل هزینه و بودجه": "Cost and Budget Analysis",
    "داشبورد تعاملی زنده": "Live Interactive Dashboard",
    "گزارش سفارشی": "Custom Report",
    "شبیه‌سازی سناریوها": "Scenario Simulation",
    "بهینه‌سازی LP": "LP Optimization",
    "بهینه‌سازی NLP": "NLP Optimization",
    # 👈 اگر عناوین دیگه‌ای داری، اضافه کن
}

# ----------- Tab ها -----------
tab1, tab2, tab3, tab4, tab5, tab6, tab7,tab8,tab9,tab10,tab11,tab12,tab13,tab14,tab15,tab16,tab17,tab18 = st.tabs([
    "KPI & مقایسه", "روند مصرف", "ماهانه", "Heatmap", 
    "جدول & خروجی", "پیش‌بینی", "KPI پیشرفته","📊 تحلیل روند تغییرات","پیش‌بینی مصرف تجهیزات با Machine Learning","تحلیل دیتا","🚨 تشخیص ناهنجاری‌ها و هشدارها","🌍 گزارش زیست‌محیطی و پایداری","🏭 مقایسه با استانداردهای صنعتی","💰 تحلیل هزینه و بودجه","📱 داشبورد تعاملی زنده","📧 گزارش‌های سفارشی و ایمیل","🎲 شبیه‌سازی سناریوها","⚙️ بهینه‌سازی (LP/NLP)",
])

# ... (بقیه کد بدون تغییر)

# استخراج ستون‌های عددی (تجهیزات)
columns = filtered_df.select_dtypes(include="number").columns.tolist()
columns = [c for c in columns if c not in ["کارخانه", "تاریخ", "تاریخ شمسی"]]

if not columns:
    st.warning("⚠️ ستون عددی برای نمایش وجود ندارد و برخی بخش‌ها غیرفعال می‌شوند.")

# فونت پیش‌فرض برای PDF: B Nazanin
fonts = {
    "Vazir": r"C:\path\to\Vazir.ttf",  # 👈 دانلود و مسیر رو تنظیم کن (جایگزین B Nazanin)
    "BNazanin": r"D:\BNazanin.ttf"     # نگه دار به‌عنوان fallback
}
available_fonts = [name for name, path in fonts.items() if os.path.exists(path)]
font_name = "Vazir" if "Vazir" in available_fonts else ("BNazanin" if "BNazanin" in available_fonts else "Helvetica")

# تابع generate_pdf ساده‌شده (بدون پردازش elements):
def generate_pdf(title, elements, buffer, pagesize=A4):
    doc = SimpleDocTemplate(buffer, pagesize=pagesize)
    styles = getSampleStyleSheet()
    
    # دیکشنری ترجمه برای fallback انگلیسی (گسترش‌یافته) - حالا جهانی است، اما برای سازگاری نگه داشته شد
    global translations
    
    use_persian = available_fonts and font_name != "Helvetica"
    if use_persian:
        try:
            pdfmetrics.registerFont(TTFont(font_name, fonts[font_name]))
            title_style = ParagraphStyle('Title', fontName=font_name, fontSize=18, alignment=1,  # 👈 alignment=1 برای RIGHT (RTL)
                                         spaceAfter=30, spaceBefore=20)
            normal_style = ParagraphStyle('Normal', fontName=font_name, fontSize=12, alignment=1)  # RTL
            
            # RTL reshape عنوان
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                title = get_display(arabic_reshaper.reshape(title))
            except ImportError:
                st.warning("برای RTL بهتر، arabic-reshaper و python-bidi رو نصب کن.")
                pass  # بدون reshape
        except Exception as e:
            st.warning(f"فونت فارسی خطا داد ({e}). به انگلیسی سوئیچ.")
            use_persian = False
            title = translations.get(title, title)  # ترجمه عنوان
    else:
        title_style = styles['Title']
        title = translations.get(title, title)  # ترجمه عنوان
    
    elements.insert(0, Paragraph(title, title_style))
    doc.build(elements)
    buffer.seek(0)

with tab1:
    st.subheader("📌 مقایسه میانگین مصرف چند تجهیز")
    
    selected_columns = st.multiselect("🔌 انتخاب تجهیزات:", columns)
    
    if selected_columns:
        mean_values = filtered_df[selected_columns].mean().reset_index()
        mean_values.columns = ["تجهیز", "میانگین مصرف"]
        mean_values["میانگین مصرف"] = mean_values["میانگین مصرف"].round(2)  # 👈 فرمت اعداد
        
        chart_height = max(400, len(selected_columns) * 50)
        
        y_max = mean_values["میانگین مصرف"].max()
        y_range = [0, y_max * 1.1]
        
        fig_bar = go.Figure(data=[
            go.Bar(
                x=mean_values["تجهیز"],
                y=mean_values["میانگین مصرف"],
                text=mean_values["میانگین مصرف"].round(2),
                textposition="outside",
                textfont=dict(family="Tahoma, Arial, sans-serif", size=14, color="black"),
                marker_color='blue'
            )
        ])
        
        fig_bar.update_layout(
            title_text="میانگین مصرف تجهیزات",
            title_font=dict(family="Tahoma, Arial, sans-serif", size=20, color="black"),
            xaxis=dict(
                title_text="تجهیز",
                tickangle=-45 if len(selected_columns) > 3 else 0,
                title_font=dict(family="Tahoma, Arial, sans-serif", size=16, color="black"),
                tickfont=dict(family="Tahoma, Arial, sans-serif", size=14, color="black")
            ),
            yaxis=dict(
                title_text="میانگین مصرف",
                title_font=dict(family="Tahoma, Arial, sans-serif", size=16, color="black"),
                tickfont=dict(family="Tahoma, Arial, sans-serif", size=14, color="black"),
                range=y_range
            ),
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            plot_bgcolor='white',  # 👈 سفید برای جلوگیری از حاشیه مشکی در PNG
            paper_bgcolor='white',
            height=chart_height
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.dataframe(
            mean_values.style
                .format({"میانگین مصرف": "{:.2f}"})
                .background_gradient(cmap="Blues", subset=["میانگین مصرف"])
        )

        # خروجی PDF برای Tab1 (بهبودیافته: ترجمه و reshape قبل از Table)
        if st.button("⬇️ دانلود PDF Tab1"):
            buffer = io.BytesIO()
            elements = []
            
            data = [mean_values.columns.tolist()] + mean_values.values.tolist()
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                "تجهیز": "Equipment",
                "میانگین مصرف": "Avg Consumption",
            }
            use_persian = available_fonts and font_name != "Helvetica"
            if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 2:
                data[0][0] = translations_local.get(data[0][0], data[0][0])
                data[0][1] = translations_local.get(data[0][1], data[0][1])
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    for row in data:
                        for i, cell in enumerate(row):
                            if isinstance(cell, str):
                                row[i] = get_display(arabic_reshaper.reshape(cell))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            elements.append(table)
            
            # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
            img_buf = io.BytesIO()
            fig_bar.write_image(img_buf, format='png', width=800, height=chart_height, scale=2)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=500, height=chart_height // 2))
            
            title = "میانگین مصرف تجهیزات"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = buffer.getvalue()
            st.download_button(
                label="دانلود PDF",
                data=pdf_data,
                file_name="tab1.pdf",
                mime="application/pdf"
            )
            
            # چک فونت
            if not available_fonts:
                st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab2: روند مصرف -----------
with tab2:
    st.subheader("📈 روند مصرف تجهیزات")
    selected_multi = st.multiselect("🧠 انتخاب تجهیز(ها):", columns, default=[columns[0]] if columns else [])
    
    time_granularity = st.radio("⏱️ بازه زمانی نمایش:", ["روزانه", "ماهانه", "سالیانه"])
    
    if selected_multi:
        df_plot = filtered_df.copy()
        
        if time_granularity == "روزانه":
            df_plot["تاریخ نمایش"] = df_plot["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m/%d'))
        elif time_granularity == "ماهانه":
            df_plot["تاریخ نمایش"] = df_plot["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
            df_plot = df_plot.groupby("تاریخ نمایش")[selected_multi].sum().reset_index()
        elif time_granularity == "سالیانه":
            df_plot["تاریخ نمایش"] = df_plot["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y'))
            df_plot = df_plot.groupby("تاریخ نمایش")[selected_multi].sum().reset_index()
        
        fig_line = px.line(
            df_plot,
            x="تاریخ نمایش",
            y=selected_multi,
            title="📈 روند مصرف برق",
            template="plotly_white",
            markers=True
        )
        fig_line.update_layout(xaxis_title="تاریخ شمسی", yaxis_title="مصرف (MWh)")
        st.plotly_chart(fig_line, use_container_width=True)

        # خروجی PDF برای Tab2
        if st.button("⬇️ دانلود PDF Tab2"):
            buffer = io.BytesIO()
            elements = []
            
            # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
            img_buf = io.BytesIO()
            fig_line.write_image(img_buf, format='png', width=800, height=400, scale=2)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=500, height=300))
            
            title = "روند مصرف تجهیزات"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = buffer.getvalue()
            st.download_button(
                label="دانلود PDF",
                data=pdf_data,
                file_name="tab2.pdf",
                mime="application/pdf"
            )
            
            # چک فونت
            if not available_fonts:
                st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab3: ماهانه -----------
with tab3:
    st.subheader("📆 نمودار مصرف ماهیانه")
    
    filtered_df["ماه شمسی"] = filtered_df["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
    
    if columns:
        monthly_column = st.selectbox("📌 انتخاب تجهیز:", columns)
        
        # گروه‌بندی و مرتب‌سازی
        monthly_df = filtered_df.groupby("ماه شمسی")[monthly_column].sum().reset_index()
        monthly_df = monthly_df.sort_values("ماه شمسی").reset_index(drop=True)  # ریست ایندکس
        
        y_values = monthly_df[monthly_column].tolist()
        x_values = monthly_df["ماه شمسی"].tolist()
        
        # پیدا کردن بیشترین و کمترین (با ایندکس درست)
        idx_max = monthly_df[monthly_column].idxmax()
        idx_min = monthly_df[monthly_column].idxmin()
        
        # 👈 تغییر: colors رو به bar_colors تغییر دادم
        bar_colors = []  # 👈 نام جدید: bar_colors
        for i in range(len(y_values)):
            if i == idx_max:
                bar_colors.append("green")
            elif i == idx_min:
                bar_colors.append("red")
            else:
                bar_colors.append("blue")
        
        # ایجاد نمودار
        fig_month = go.Figure(
            data=[go.Bar(
                x=x_values,
                y=y_values,
                text=[f"{v:.2f}" for v in y_values],
                textposition="outside",
                marker_color=bar_colors  # 👈 استفاده از bar_colors
            )]
        )
        
        fig_month.update_layout(
            title=f"📊 مصرف ماهیانه {monthly_column}",
            xaxis_title="ماه شمسی",
            yaxis_title="مقدار مصرف",
            template="plotly_white",
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig_month, use_container_width=True)

        # خروجی PDF برای Tab3 (بهبودیافته)
        if st.button("⬇️ دانلود PDF Tab3"):
            buffer = io.BytesIO()
            elements = []
            
            data = [monthly_df.columns.tolist()] + monthly_df.values.tolist()
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                "ماه شمسی": "Jalali Month",
                monthly_column: "Consumption"
            }
            use_persian = available_fonts and font_name != "Helvetica"
            if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 2:
                data[0][0] = translations_local.get(data[0][0], data[0][0])
                data[0][1] = translations_local.get(data[0][1], data[0][1])
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    for row in data:
                        for i, cell in enumerate(row):
                            if isinstance(cell, str):
                                row[i] = get_display(arabic_reshaper.reshape(cell))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            elements.append(table)
            
            # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
            img_buf = io.BytesIO()
            fig_month.write_image(img_buf, format='png', width=800, height=400, scale=2)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=500, height=300))
            
            title = "نمودار مصرف ماهیانه"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = buffer.getvalue()
            st.download_button(
                label="دانلود PDF",
                data=pdf_data,
                file_name="tab3.pdf",
                mime="application/pdf"
            )
            
            # چک فونت
            if not available_fonts:
                st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab4: Heatmap -----------
# ----------- Tab4: Heatmap -----------
with tab4:
    st.subheader("🔥 Heatmap مصرف تجهیزات با محدوده رنگ قابل تنظیم")
    if columns:
        heat_col = st.selectbox("📌 انتخاب تجهیز برای Heatmap:", columns)
        view_mode = st.radio("🔄 حالت نمایش:", ["روزانه", "ماهانه ماتریسی"])

        df_hm = filtered_df.dropna(subset=[heat_col])
        
        if not df_hm.empty:
            df_hm["ماه"] = df_hm["تاریخ"].dt.to_period("M")
            df_hm["روز"] = df_hm["تاریخ"].dt.day

            default_min = df_hm[heat_col].min()
            default_max = df_hm[heat_col].max()
            st.sidebar.markdown("🎨 تنظیم حداقل و حداکثر رنگ هیت‌مپ")
            user_min, user_max = st.sidebar.slider(
                "محدوده رنگ (Min و Max):",
                float(default_min), float(default_max),
                (float(default_min), float(default_max))
            )

            colorscale = [
                [0.0, 'lightblue'],
                [0.5, 'yellow'],
                [1.0, 'red']
            ]

            # متغیر fig را در ابتدای شرط تعریف کنید تا خطای NameError در PDF نگیرید
            fig = None

            if view_mode == "روزانه":
                pivot_day = df_hm.pivot_table(index="روز", columns="ماه", values=heat_col, aggfunc="mean")
                if not pivot_day.empty:
                    pivot_display = pivot_day.copy()
                    pivot_display.index = pivot_display.index.astype(str)
                    pivot_display.columns = pivot_display.columns.astype(str)

                    fig = go.Figure(data=go.Heatmap(
                        z=pivot_display.values,
                        x=pivot_display.columns,
                        y=pivot_display.index,
                        colorscale=colorscale,
                        zmin=user_min,
                        zmax=user_max,
                        colorbar=dict(title=heat_col),
                        hovertemplate='روز %{y}<br>ماه %{x}<br>مصرف: %{z:.2f}<extra></extra>',
                        # 👈 اضافه کردن بوردر و تفکیک سلول‌ها
                        xgap=1,  # فاصله افقی بین سلول‌ها (ایجاد خط سفید برای بوردر)
                        ygap=1,  # فاصله عمودی بین سلول‌ها
                        # برای بوردر تیره‌تر، می‌توان colorscale را با خطوط سفارشی ترکیب کرد، اما xgap/ygap ساده‌ترین راه است
                    ))

                    fig.update_layout(
                        title=f"Heatmap روزانه - {heat_col}",
                        xaxis=dict(tickangle=-45, automargin=True),
                        yaxis=dict(autorange='reversed', automargin=True),
                        height=max(400, 20*len(pivot_display.index)),
                        width=max(700, 50*len(pivot_display.columns)),
                        # 👈 اضافه کردن بوردر کلی به نمودار
                        plot_bgcolor='white',
                        paper_bgcolor='lightgray',  # بوردر خارجی خاکستری روشن
                        margin=dict(l=50, r=50, t=50, b=50),  # حاشیه برای جداسازی
                        # برای بوردر سلول‌ها، می‌توان از annotations یا shapes استفاده کرد، اما xgap کافی است
                    )
                    st.plotly_chart(fig, use_container_width=True)

            elif view_mode == "ماهانه ماتریسی":
                months = sorted(df_hm["ماه"].unique())
                matrix_data = pd.DataFrame()
                for m in months:
                    month_data = df_hm[df_hm["ماه"]==m].set_index("روز")[heat_col]
                    matrix_data[m] = month_data

                pivot_month = matrix_data.fillna(0)
                pivot_month_display = pivot_month.copy()
                pivot_month_display.index = pivot_month_display.index.astype(str)
                pivot_month_display.columns = pivot_month_display.columns.astype(str)

                fig = go.Figure(data=go.Heatmap(
                    z=pivot_month_display.values,
                    x=pivot_month_display.columns,
                    y=pivot_month_display.index,
                    colorscale=colorscale,
                    zmin=user_min,
                    zmax=user_max,
                    colorbar=dict(title=heat_col),
                    hovertemplate='روز %{y}<br>ماه %{x}<br>مصرف: %{z:.2f}<extra></extra>',
                    # 👈 اضافه کردن بوردر و تفکیک سلول‌ها
                    xgap=1,  # فاصله افقی
                    ygap=1,  # فاصله عمودی
                ))

                fig.update_layout(
                    title=f"Heatmap ماهانه ماتریسی - {heat_col}",
                    xaxis=dict(tickangle=-45, automargin=True),
                    yaxis=dict(autorange='reversed', automargin=True),
                    height=max(400, 20*len(pivot_month_display.index)),
                    width=max(700, 50*len(pivot_month_display.columns)),
                    # 👈 بوردر کلی
                    plot_bgcolor='white',
                    paper_bgcolor='lightgray',
                    margin=dict(l=50, r=50, t=50, b=50),
                )
                st.plotly_chart(fig, use_container_width=True)

            # 👈 چک کردن fig قبل از PDF
            if fig is not None:
                st.markdown("📋 **جدول داده‌های خلاصه شده**")
                monthly_summary = df_hm.groupby("ماه")[heat_col].agg(['sum','mean']).round(2)
                monthly_summary = monthly_summary.rename(columns={'sum':'مجموع', 'mean':'میانگین'})
                st.dataframe(monthly_summary, use_container_width=True)

                # خروجی PDF برای Tab4
                if st.button("⬇️ دانلود PDF Tab4"):
                    buffer = io.BytesIO()
                    elements = []
                    
                    # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                    img_buf = io.BytesIO()
                    fig.write_image(img_buf, format='png', width=800, height=fig.layout.height, scale=2)
                    img_buf.seek(0)
                    elements.append(Image(img_buf, width=500, height=fig.layout.height // 2))
                    
                    data = [monthly_summary.columns.tolist()] + monthly_summary.values.tolist()
                    
                    # ترجمه هدرها اگر انگلیسی
                    translations_local = {
                        "ماه": "Month",
                        "مجموع": "Total",
                        "میانگین": "Average"
                    }
                    use_persian = available_fonts and font_name != "Helvetica"
                    if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 2:
                        data[0][0] = translations_local.get(data[0][0], data[0][0])
                        data[0][1] = translations_local.get(data[0][1], data[0][1])
                        data[0][2] = translations_local.get(data[0][2], data[0][2])
                    
                    # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                    if use_persian:
                        try:
                            import arabic_reshaper
                            from bidi.algorithm import get_display
                            for row in data:
                                for i, cell in enumerate(row):
                                    if isinstance(cell, str):
                                        row[i] = get_display(arabic_reshaper.reshape(cell))
                        except ImportError:
                            st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                    
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                        ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                        ('ALIGN', (0,0), (-1,-1), 'CENTER')
                    ]))
                    elements.append(table)
                    
                    title = "Heatmap مصرف تجهیزات"
                    if not use_persian:
                        title = translations.get(title, title)
                    generate_pdf(title, elements, buffer)
                    
                    # 👈 دانلود با getvalue() برای اطمینان
                    pdf_data = buffer.getvalue()
                    st.download_button(
                        label="دانلود PDF",
                        data=pdf_data,
                        file_name="tab4.pdf",
                        mime="application/pdf"
                    )
                    
                    # چک فونت
                    if not available_fonts:
                        st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
            else:
                st.warning("⚠️ نمودار Heatmap تولید نشد؛ داده‌ها را بررسی کنید.")
        else:
            st.warning("⚠️ داده کافی برای نمایش هیت‌مپ وجود ندارد.")

# ----------- Tab5: خروجی PDF (داره، تغییر فونت) -----------
with tab5:
    st.subheader("📝 خروجی PDF گزارش تجهیزات")

    uploaded_file_tab5 = st.file_uploader("آپلود فایل اکسل برای ایجاد PDF", type=['xlsx'], key="tab5_uploader")
    if uploaded_file_tab5:
        df_tab5 = pd.read_excel(uploaded_file_tab5, sheet_name=0)

        buffer = io.BytesIO()
        elements = []

        styles = getSampleStyleSheet()
        use_persian = available_fonts and font_name != "Helvetica"
        if use_persian:
            try:
                pdfmetrics.registerFont(TTFont(font_name, fonts[font_name]))
                title_style = ParagraphStyle('Title', fontName=font_name, fontSize=18, alignment=1)
                normal_style = ParagraphStyle('Normal', fontName=font_name, fontSize=12, alignment=1)
            except Exception as e:
                st.warning(f"فونت فارسی خطا داد ({e}). به انگلیسی سوئیچ.")
                use_persian = False
        else:
            title_style = styles['Title']
            normal_style = styles['Normal']
        
        title = Paragraph("گزارش تجهیزات", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))

        data = [df_tab5.columns.tolist()] + df_tab5.values.tolist()

        # ترجمه هدرها اگر انگلیسی
        translations_local = {
            "تجهیز": "Equipment",
            # Add more as needed
        }
        if not use_persian and data and isinstance(data[0], list):
            for i, header in enumerate(data[0]):
                data[0][i] = translations_local.get(header, header)
        
        # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
        if use_persian:
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                for row in data:
                    for i, cell in enumerate(row):
                        if isinstance(cell, str):
                            row[i] = get_display(arabic_reshaper.reshape(cell))
            except ImportError:
                st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        elements.append(table)

        title_str = "گزارش تجهیزات"
        if not use_persian:
            title_str = translations.get(title_str, title_str)
        generate_pdf(title_str, elements, buffer)

        # 👈 دانلود با getvalue() برای اطمینان
        pdf_data = buffer.getvalue()
        st.download_button(
            label="⬇️ دانلود PDF",
            data=pdf_data,
            file_name="گزارش_تجهیزات.pdf",
            mime="application/pdf"
        )
        
        # چک فونت
        if not available_fonts:
            st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab6: پیش‌بینی -----------
with tab6:
    st.subheader("🔮 پیش‌بینی مصرف تجهیزات")
    if columns:
        forecast_col = st.selectbox("📌 انتخاب تجهیز برای پیش‌بینی:", columns)
        
        time_granularity_pred = st.radio("⏱️ بازه زمانی نمایش:", ["روزانه", "ماهانه", "سالیانه"], key="pred_radio")
        
        df_pred = filtered_df.dropna(subset=[forecast_col]).copy()
        if len(df_pred) > 1:
            df_pred["روز"] = (df_pred["تاریخ"] - df_pred["تاریخ"].min()).dt.days
            X = df_pred[["روز"]].values
            y = df_pred[forecast_col].values
            model = LinearRegression().fit(X, y)
            
            future_days = np.arange(X.max()+1, X.max()+31).reshape(-1,1)
            future_pred = model.predict(future_days)
            future_dates = pd.date_range(df_pred["تاریخ"].max()+pd.Timedelta(days=1), periods=30)
            
            if time_granularity_pred == "روزانه":
                df_pred["تاریخ نمایش"] = df_pred["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m/%d'))
                future_dates_sh = [JalaliDate(d).strftime('%Y/%m/%d') for d in future_dates]
            elif time_granularity_pred == "ماهانه":
                df_pred["تاریخ نمایش"] = df_pred["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
                df_pred = df_pred.groupby("تاریخ نمایش")[forecast_col].sum().reset_index()
                future_dates_sh = [JalaliDate(d).strftime('%Y/%m') for d in future_dates]
            elif time_granularity_pred == "سالیانه":
                df_pred["تاریخ نمایش"] = df_pred["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y'))
                df_pred = df_pred.groupby("تاریخ نمایش")[forecast_col].sum().reset_index()
                future_dates_sh = [JalaliDate(d).strftime('%Y') for d in future_dates]
            
            fig_forecast = go.Figure()
            fig_forecast.add_trace(go.Scatter(
                x=df_pred["تاریخ نمایش"],
                y=df_pred[forecast_col],
                mode="lines+markers",
                name="داده واقعی"
            ))
            fig_forecast.add_trace(go.Scatter(
                x=future_dates_sh,
                y=future_pred,
                mode="lines+markers",
                name="پیش‌بینی"
            ))
            fig_forecast.update_layout(
                title="پیش‌بینی مصرف برق",
                xaxis_title="تاریخ شمسی",
                yaxis_title="مصرف (MWh)",
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig_forecast, use_container_width=True)

            # خروجی PDF برای Tab6
            if st.button("⬇️ دانلود PDF Tab6"):
                buffer = io.BytesIO()
                elements = []
                
                data = [df_pred.columns.tolist()] + df_pred.values.tolist()
                
                # ترجمه هدرها اگر انگلیسی
                translations_local = {
                    "تاریخ نمایش": "Display Date",
                    forecast_col: "Consumption"
                }
                use_persian = available_fonts and font_name != "Helvetica"
                if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 2:
                    data[0][0] = translations_local.get(data[0][0], data[0][0])
                    data[0][1] = translations_local.get(data[0][1], data[0][1])
                
                # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                if use_persian:
                    try:
                        import arabic_reshaper
                        from bidi.algorithm import get_display
                        for row in data:
                            for i, cell in enumerate(row):
                                if isinstance(cell, str):
                                    row[i] = get_display(arabic_reshaper.reshape(cell))
                    except ImportError:
                        st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                    ('ALIGN', (0,0), (-1,-1), 'CENTER')
                ]))
                elements.append(table)
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf = io.BytesIO()
                fig_forecast.write_image(img_buf, format='png', width=800, height=400, scale=2)
                img_buf.seek(0)
                elements.append(Image(img_buf, width=500, height=300))
                
                title = "پیش‌بینی مصرف تجهیزات"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab6.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab7: KPI پیشرفته -----------
with tab7:
    st.markdown("## ✨ شاخص‌های کلیدی عملکرد (KPI پیشرفته)")

    kpi_columns = st.multiselect(
        "📌 انتخاب تجهیزات برای KPI:", 
        columns, 
        default=columns[:3] if columns else []
    )

    if kpi_columns:
        st.markdown("### 🔹 کارت‌های KPI")
        kpis = []
        for col in kpi_columns:
            total = filtered_df[col].sum()
            avg = filtered_df[col].mean()
            max_val = filtered_df[col].max()
            kpis.append((col, total, avg, max_val))

        for col_name, total, avg, max_val in kpis:
            st.markdown(f"#### تجهیزات: {col_name}")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(f"🔌 مجموع مصرف", f"{total:,.0f} MWh")
            with c2:
                st.metric(f"📊 میانگین مصرف", f"{avg:,.2f} MWh")
            with c3:
                st.metric(f"🚀 بیشترین مصرف", f"{max_val:,.0f} MWh")
            st.markdown("---")

        st.markdown("### 📏 مصرف متوسط بر اساس بازه زمانی")
        period_option = st.radio("⏱️ انتخاب بازه:", ["روزانه", "ماهانه", "سالیانه"], horizontal=True)

        df_avg = filtered_df.copy()
        if period_option == "روزانه":
            df_avg["تاریخ نمایش"] = df_avg["تاریخ"]
        elif period_option == "ماهانه":
            df_avg["تاریخ نمایش"] = df_avg["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
        else:
            df_avg["تاریخ نمایش"] = df_avg["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y'))

        df_avg_grouped = df_avg.groupby("تاریخ نمایش")[kpi_columns].mean().reset_index()
        fig_avg = px.line(
            df_avg_grouped,
            x="تاریخ نمایش",
            y=kpi_columns,
            markers=True,
            title=f"📊 مصرف متوسط {period_option}",
            template="plotly_white"
        )
        fig_avg.update_layout(
            xaxis_title="تاریخ شمسی",
            yaxis_title="مصرف متوسط (MWh)",
            legend_title="تجهیزات"
        )
        st.plotly_chart(fig_avg, use_container_width=True)

        # خروجی PDF برای Tab7
        if st.button("⬇️ دانلود PDF Tab7"):
            buffer = io.BytesIO()
            elements = []
            
            kpi_data = [['تجهیز', 'مجموع', 'میانگین', 'بیشترین']]
            for col_name, total, avg, max_val in kpis:
                kpi_data.append([col_name, f"{total:,.0f}", f"{avg:,.2f}", f"{max_val:,.0f}"])
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                "تجهیز": "Equipment",
                "مجموع": "Total",
                "میانگین": "Average",
                "بیشترین": "Max"
            }
            use_persian = available_fonts and font_name != "Helvetica"
            if not use_persian and kpi_data and isinstance(kpi_data[0], list) and len(kpi_data[0]) >= 4:
                kpi_data[0][0] = translations_local.get(kpi_data[0][0], kpi_data[0][0])
                kpi_data[0][1] = translations_local.get(kpi_data[0][1], kpi_data[0][1])
                kpi_data[0][2] = translations_local.get(kpi_data[0][2], kpi_data[0][2])
                kpi_data[0][3] = translations_local.get(kpi_data[0][3], kpi_data[0][3])
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    for row in kpi_data:
                        for i, cell in enumerate(row):
                            if isinstance(cell, str):
                                row[i] = get_display(arabic_reshaper.reshape(cell))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            table = Table(kpi_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            elements.append(table)
            
            # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
            img_buf = io.BytesIO()
            fig_avg.write_image(img_buf, format='png', width=800, height=400, scale=2)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=500, height=300))
            
            title = "KPI پیشرفته"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = buffer.getvalue()
            st.download_button(
                label="دانلود PDF",
                data=pdf_data,
                file_name="tab7.pdf",
                mime="application/pdf"
            )
            
            # چک فونت
            if not available_fonts:
                st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
    else:
        st.warning("⚠️ هیچ تجهیزی برای KPI انتخاب نشده است.")

# ----------- Tab8: تحلیل روند تغییرات -----------
with tab8:
    st.subheader("📈 تغییرات درصدی نسبت به دوره قبلی")

    selected_col = st.selectbox("🔌 انتخاب تجهیز:", columns)

    period_type = st.radio("⏱️ بازه زمانی:", ["روزانه", "ماهانه", "سالیانه"])

    if selected_col:
        df_change = filtered_df.copy()

        if period_type == "روزانه":
            df_change["period"] = df_change["تاریخ"].dt.to_period("D").dt.to_timestamp()
        elif period_type == "ماهانه":
            df_change["period"] = df_change["تاریخ"].dt.to_period("M").dt.to_timestamp(how="end")
        elif period_type == "سالیانه":
            df_change["period"] = df_change["تاریخ"].dt.to_period("Y").dt.to_timestamp()

        df_change = df_change.groupby("period")[selected_col].sum().reset_index()

        df_change["تاریخ نمایش"] = df_change["period"].apply(
            lambda x: JalaliDate(pd.to_datetime(x)).strftime('%Y/%m/%d')
        )

        df_change["درصد تغییر"] = df_change[selected_col].pct_change() * 100

        df_change.replace([np.inf, -np.inf], np.nan, inplace=True)

        df_change["درصد تغییر"] = df_change["درصد تغییر"].fillna(0).astype(float)

        if not df_change.empty:
            st.markdown("📋 **جدول تغییرات درصدی**")
            st.dataframe(
                df_change[["تاریخ نمایش", selected_col, "درصد تغییر"]].round(2),
                use_container_width=True
            )

            fig_line = px.line(
                df_change,
                x="تاریخ نمایش",
                y="درصد تغییر",
                title=f"📈 تغییرات درصدی {selected_col} ({period_type})",
                markers=True,
                template="plotly_white"
            )
            fig_line.update_layout(yaxis_title="درصد تغییر (%)", xaxis_title="تاریخ")
            st.plotly_chart(fig_line, use_container_width=True)

            measures = ["relative"] * len(df_change)
            measures[-1] = "total"

            y_values = df_change["درصد تغییر"].tolist()
            x_values = df_change["تاریخ نمایش"].tolist()

            fig_wf = go.Figure(go.Waterfall(
                name="درصد تغییر",
                orientation="v",
                measure=measures,
                x=x_values,
                y=y_values,
                decreasing=dict(marker=dict(color="red")),
                increasing=dict(marker=dict(color="green")),
                totals=dict(marker=dict(color="blue")),
                text=[f"{v:.2f}%" for v in y_values],
                textposition="outside",
            ))

            fig_wf.update_layout(
                title=f"💧 نمودار Waterfall تغییرات درصدی {selected_col} ({period_type})",
                yaxis_title="درصد تغییر (%)",
                xaxis_title="تاریخ"
            )
            st.plotly_chart(fig_wf, use_container_width=True)

            idx_max = df_change["درصد تغییر"].idxmax()
            idx_min = df_change["درصد تغییر"].idxmin()
            max_increase = df_change.loc[idx_max]
            max_decrease = df_change.loc[idx_min]
            st.markdown(
                f"**نتیجه‌گیری:**\n\n"
                f"🔺 بیشترین افزایش مصرف **{selected_col}**: "
                f"**{max_increase['درصد تغییر']:.2f}%** در دوره **{max_increase['تاریخ نمایش']}**\n\n"
                f"🔻 بیشترین کاهش مصرف **{selected_col}**: "
                f"**{max_decrease['درصد تغییر']:.2f}%** در دوره **{max_decrease['تاریخ نمایش']}**"
            )

            # خروجی PDF برای Tab8
            if st.button("⬇️ دانلود PDF Tab8"):
                buffer = io.BytesIO()
                elements = []
                
                data = [df_change[["تاریخ نمایش", selected_col, "درصد تغییر"]].columns.tolist()] + df_change[["تاریخ نمایش", selected_col, "درصد تغییر"]].round(2).values.tolist()
                
                # ترجمه هدرها اگر انگلیسی
                translations_local = {
                    "تاریخ نمایش": "Display Date",
                    selected_col: "Consumption",
                    "درصد تغییر": "Percent Change"
                }
                use_persian = available_fonts and font_name != "Helvetica"
                if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 3:
                    data[0][0] = translations_local.get(data[0][0], data[0][0])
                    data[0][1] = translations_local.get(data[0][1], data[0][1])
                    data[0][2] = translations_local.get(data[0][2], data[0][2])
                
                # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                if use_persian:
                    try:
                        import arabic_reshaper
                        from bidi.algorithm import get_display
                        for row in data:
                            for i, cell in enumerate(row):
                                if isinstance(cell, str):
                                    row[i] = get_display(arabic_reshaper.reshape(cell))
                    except ImportError:
                        st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                    ('ALIGN', (0,0), (-1,-1), 'CENTER')
                ]))
                elements.append(table)
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf1 = io.BytesIO()
                fig_line.write_image(img_buf1, format='png', width=800, height=400, scale=2)
                img_buf1.seek(0)
                elements.append(Image(img_buf1, width=500, height=300))
                
                img_buf2 = io.BytesIO()
                fig_wf.write_image(img_buf2, format='png', width=800, height=400, scale=2)
                img_buf2.seek(0)
                elements.append(Image(img_buf2, width=500, height=300))
                
                title = "تحلیل روند تغییرات"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab8.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
        else:
            st.warning("📭 داده کافی برای رسم نمودار وجود ندارد.")

# ----------- Tab9: پیش‌بینی ML -----------
with tab9:
    st.subheader("🤖 پیش‌بینی مصرف تجهیزات با Machine Learning")

    selected_cols = st.multiselect("🔌 انتخاب تجهیزات (ML):", columns, key="ml_multiselect")

    if selected_cols:
        start_date = st.date_input("📅 شروع بازه (ML)", value=filtered_df['تاریخ'].min(), key="ml_start_date")
        end_date = st.date_input("📅 پایان بازه (ML)", value=filtered_df['تاریخ'].max(), key="ml_end_date")

        df_ml = filtered_df[(filtered_df['تاریخ'] >= pd.to_datetime(start_date)) &
                            (filtered_df['تاریخ'] <= pd.to_datetime(end_date))].copy()

        error_table = []

        for col in selected_cols:
            st.markdown(f"### 🔹 پیش‌بینی {col}")

            ts = df_ml[['تاریخ', col]].rename(columns={'تاریخ': 'ds', col: 'y'}).dropna()
            ts['ds'] = pd.to_datetime(ts['ds'])
            ts = ts.sort_values('ds').reset_index(drop=True)

            if len(ts) < 4:
                st.warning(f"داده برای {col} کافی نیست (حداقل 4 رکورد لازم است).")
                continue

            train_size = int(len(ts) * 0.8)
            if train_size < 1:
                train_size = len(ts) - 1
            train_df = ts.iloc[:train_size].copy().reset_index(drop=True)
            test_df = ts.iloc[train_size:].copy().reset_index(drop=True)

            preds_prophet_test = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])
            preds_arima_test = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])
            preds_exp_test = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])
            df_pred_future_prophet = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])
            df_pred_future_arima = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])
            df_pred_future_exp = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])

            try:
                from prophet import Prophet
                m = Prophet(daily_seasonality=True)
                m.fit(train_df)

                future_test = test_df[['ds']].copy()
                forecast_test = m.predict(future_test)
                preds_prophet_test = forecast_test[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(
                    columns={'yhat': 'Predicted', 'yhat_lower': 'Lower', 'yhat_upper': 'Upper'}
                )

                merged_p = test_df.merge(preds_prophet_test, on='ds', how='left')
                valid_p = merged_p.dropna(subset=['y', 'Predicted'])
                mae_prophet = valid_p['y'].sub(valid_p['Predicted']).abs().mean() if len(valid_p) > 0 else float('nan')
                rmse_prophet = ((valid_p['y'] - valid_p['Predicted'])**2).mean()**0.5 if len(valid_p) > 0 else float('nan')
            except Exception as e:
                mae_prophet = rmse_prophet = float('nan')
                st.error(f"⚠️ خطا در اجرای Prophet برای {col}: {e}")

            try:
                from statsmodels.tsa.arima.model import ARIMA
                ts_arima_train = train_df.set_index('ds')['y']
                arima_model = ARIMA(ts_arima_train, order=(1,1,1))
                arima_fit = arima_model.fit()

                if len(test_df) > 0:
                    forecast_test_a = arima_fit.get_forecast(steps=len(test_df))
                    conf_int = forecast_test_a.conf_int(alpha=0.05)
                    preds_arima_test = pd.DataFrame({
                        'ds': test_df['ds'].values,
                        'Predicted': forecast_test_a.predicted_mean.values,
                        'Lower': conf_int.iloc[:, 0].values,
                        'Upper': conf_int.iloc[:, 1].values
                    })

                    merged_a = test_df.merge(preds_arima_test, on='ds', how='left')
                    valid_a = merged_a.dropna(subset=['y', 'Predicted'])
                    mae_arima = valid_a['y'].sub(valid_a['Predicted']).abs().mean() if len(valid_a) > 0 else float('nan')
                    rmse_arima = ((valid_a['y'] - valid_a['Predicted'])**2).mean()**0.5 if len(valid_a) > 0 else float('nan')
                else:
                    mae_arima = rmse_arima = float('nan')
            except Exception as e:
                mae_arima = rmse_arima = float('nan')
                st.error(f"⚠️ خطا در اجرای ARIMA برای {col}: {e}")

            try:
                from statsmodels.tsa.holtwinters import ExponentialSmoothing
                ts_exp_train = train_df.set_index('ds')['y']
                exp_model = ExponentialSmoothing(ts_exp_train, trend='add', seasonal=None, damped_trend=True)
                exp_fit = exp_model.fit()

                if len(test_df) > 0:
                    forecast_test_e = exp_fit.forecast(steps=len(test_df))
                    std_err = np.std(exp_fit.resid)
                    preds_exp_test = pd.DataFrame({
                        'ds': test_df['ds'].values,
                        'Predicted': forecast_test_e.values,
                        'Lower': forecast_test_e.values - 1.96 * std_err,
                        'Upper': forecast_test_e.values + 1.96 * std_err
                    })

                    merged_e = test_df.merge(preds_exp_test, on='ds', how='left')
                    valid_e = merged_e.dropna(subset=['y', 'Predicted'])
                    mae_exp = valid_e['y'].sub(valid_e['Predicted']).abs().mean() if len(valid_e) > 0 else float('nan')
                    rmse_exp = ((valid_e['y'] - valid_e['Predicted'])**2).mean()**0.5 if len(valid_e) > 0 else float('nan')
                else:
                    mae_exp = rmse_exp = float('nan')
            except Exception as e:
                mae_exp = rmse_exp = float('nan')
                st.error(f"⚠️ خطا در اجرای Exponential Smoothing برای {col}: {e}")

            error_table.append([col, 'Prophet', round(mae_prophet, 2) if not pd.isna(mae_prophet) else None,
                                round(rmse_prophet, 2) if not pd.isna(rmse_prophet) else None])
            error_table.append([col, 'ARIMA', round(mae_arima, 2) if not pd.isna(mae_arima) else None,
                                round(rmse_arima, 2) if not pd.isna(rmse_arima) else None])
            error_table.append([col, 'ExponentialSmoothing', round(mae_exp, 2) if not pd.isna(mae_exp) else None,
                                round(rmse_exp, 2) if not pd.isna(rmse_exp) else None])

            rmse_candidates = {}
            if not pd.isna(rmse_prophet):
                rmse_candidates['Prophet'] = rmse_prophet
            if not pd.isna(rmse_arima):
                rmse_candidates['ARIMA'] = rmse_arima
            if not pd.isna(rmse_exp):
                rmse_candidates['ExponentialSmoothing'] = rmse_exp

            if rmse_candidates:
                best_model = min(rmse_candidates, key=rmse_candidates.get)
                best_rmse = rmse_candidates[best_model]
            else:
                best_model = None
                best_rmse = None

            try:
                m_full = Prophet(daily_seasonality=True)
                m_full.fit(ts)
                future_full = m_full.make_future_dataframe(periods=30)
                forecast_full = m_full.predict(future_full)
                df_pred_future_prophet = forecast_full[forecast_full['ds'] > ts['ds'].max()][['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(
                    columns={'yhat': 'Predicted', 'yhat_lower': 'Lower', 'yhat_upper': 'Upper'}
                )
            except Exception:
                df_pred_future_prophet = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])

            try:
                ts_arima_full = ts.set_index('ds')['y']
                arima_full = ARIMA(ts_arima_full, order=(1,1,1))
                arima_full_fit = arima_full.fit()
                forecast_future_a = arima_full_fit.get_forecast(steps=30)
                conf_int_future = forecast_future_a.conf_int(alpha=0.05)
                df_pred_future_arima = pd.DataFrame({
                    'ds': pd.date_range(ts_arima_full.index[-1] + pd.Timedelta(days=1), periods=30),
                    'Predicted': forecast_future_a.predicted_mean.values,
                    'Lower': conf_int_future.iloc[:, 0].values,
                    'Upper': conf_int_future.iloc[:, 1].values
                })
            except Exception:
                df_pred_future_arima = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])

            try:
                ts_exp_full = ts.set_index('ds')['y']
                exp_full = ExponentialSmoothing(ts_exp_full, trend='add', seasonal=None, damped_trend=True)
                exp_full_fit = exp_full.fit()
                forecast_future_e = exp_full_fit.forecast(steps=30)
                std_err_full = np.std(exp_full_fit.resid)
                df_pred_future_exp = pd.DataFrame({
                    'ds': pd.date_range(ts_exp_full.index[-1] + pd.Timedelta(days=1), periods=30),
                    'Predicted': forecast_future_e.values,
                    'Lower': forecast_future_e.values - 1.96 * std_err_full,
                    'Upper': forecast_future_e.values + 1.96 * std_err_full
                })
            except Exception:
                df_pred_future_exp = pd.DataFrame(columns=['ds', 'Predicted', 'Lower', 'Upper'])

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ts['ds'], y=ts['y'], mode='lines+markers', name='Actual', line=dict(color='blue')))

            if not preds_prophet_test.empty:
                fig.add_trace(go.Scatter(x=preds_prophet_test['ds'], y=preds_prophet_test['Predicted'],
                                         mode='lines+markers', name='Prophet (Test)', line=dict(color='green')))
                fig.add_trace(go.Scatter(x=preds_prophet_test['ds'], y=preds_prophet_test['Lower'],
                                         mode='lines', name='Prophet Lower CI', line=dict(color='green', dash='dash')))
                fig.add_trace(go.Scatter(x=preds_prophet_test['ds'], y=preds_prophet_test['Upper'],
                                         mode='lines', name='Prophet Upper CI', line=dict(color='green', dash='dash'), fill='tonexty'))

            if not preds_arima_test.empty:
                fig.add_trace(go.Scatter(x=preds_arima_test['ds'], y=preds_arima_test['Predicted'],
                                         mode='lines+markers', name='ARIMA (Test)', line=dict(color='orange')))
                fig.add_trace(go.Scatter(x=preds_arima_test['ds'], y=preds_arima_test['Lower'],
                                         mode='lines', name='ARIMA Lower CI', line=dict(color='orange', dash='dash')))
                fig.add_trace(go.Scatter(x=preds_arima_test['ds'], y=preds_arima_test['Upper'],
                                         mode='lines', name='ARIMA Upper CI', line=dict(color='orange', dash='dash'), fill='tonexty'))

            if not preds_exp_test.empty:
                fig.add_trace(go.Scatter(x=preds_exp_test['ds'], y=preds_exp_test['Predicted'],
                                         mode='lines+markers', name='Exp Smoothing (Test)', line=dict(color='purple')))
                fig.add_trace(go.Scatter(x=preds_exp_test['ds'], y=preds_exp_test['Lower'],
                                         mode='lines', name='Exp Lower CI', line=dict(color='purple', dash='dash')))
                fig.add_trace(go.Scatter(x=preds_exp_test['ds'], y=preds_exp_test['Upper'],
                                         mode='lines', name='Exp Upper CI', line=dict(color='purple', dash='dash'), fill='tonexty'))

            if best_model == 'Prophet' and not df_pred_future_prophet.empty:
                fig.add_trace(go.Scatter(x=df_pred_future_prophet['ds'], y=df_pred_future_prophet['Predicted'],
                                         mode='lines+markers', name='Best (Future) - Prophet', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_prophet['ds'], y=df_pred_future_prophet['Lower'],
                                         mode='lines', name='Prophet Future Lower CI', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_prophet['ds'], y=df_pred_future_prophet['Upper'],
                                         mode='lines', name='Prophet Future Upper CI', line=dict(color='red', dash='dash'), fill='tonexty'))
            elif best_model == 'ARIMA' and not df_pred_future_arima.empty:
                fig.add_trace(go.Scatter(x=df_pred_future_arima['ds'], y=df_pred_future_arima['Predicted'],
                                         mode='lines+markers', name='Best (Future) - ARIMA', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_arima['ds'], y=df_pred_future_arima['Lower'],
                                         mode='lines', name='ARIMA Future Lower CI', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_arima['ds'], y=df_pred_future_arima['Upper'],
                                         mode='lines', name='ARIMA Future Upper CI', line=dict(color='red', dash='dash'), fill='tonexty'))
            elif best_model == 'ExponentialSmoothing' and not df_pred_future_exp.empty:
                fig.add_trace(go.Scatter(x=df_pred_future_exp['ds'], y=df_pred_future_exp['Predicted'],
                                         mode='lines+markers', name='Best (Future) - Exp', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_exp['ds'], y=df_pred_future_exp['Lower'],
                                         mode='lines', name='Exp Future Lower CI', line=dict(color='red', dash='dash')))
                fig.add_trace(go.Scatter(x=df_pred_future_exp['ds'], y=df_pred_future_exp['Upper'],
                                         mode='lines', name='Exp Future Upper CI', line=dict(color='red', dash='dash'), fill='tonexty'))

            fig.update_layout(
                title=f"📈 Actual vs Predicted برای {col}",
                xaxis_title="تاریخ",
                yaxis_title="مقدار مصرف",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True, key=f"ml_chart_{col}")

            if best_model is not None:
                st.success(f"💡 بهترین مدل برای {col}: {best_model} (RMSE = {best_rmse:.2f})")
            else:
                st.info(f"⚠️ برای {col} مدل برتر قابل تعیین نیست (خطا یا دادهٔ ناکافی).")

            # خروجی PDF برای Tab9 (برای هر تجهیز)
            if st.button(f"⬇️ دانلود PDF برای {col}"):
                buffer = io.BytesIO()
                elements = []
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf = io.BytesIO()
                fig.write_image(img_buf, format='png', width=800, height=400, scale=2)
                img_buf.seek(0)
                elements.append(Image(img_buf, width=500, height=300))
                
                title = f"پیش‌بینی {col}"
                if not use_persian:
                    title = translations.get("پیش‌بینی", "Forecast") + f" {col}"
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name=f"tab9_{col}.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

        if error_table:
            st.markdown("### 📊 جدول خطاها برای همه تجهیزات")
            error_df = pd.DataFrame(error_table, columns=['تجهیز', 'مدل', 'MAE', 'RMSE'])
            st.dataframe(error_df.style.format({'MAE': '{:.2f}', 'RMSE': '{:.2f}'}))

            # خروجی PDF برای جدول خطاها
            if st.button("⬇️ دانلود PDF جدول خطاها Tab9"):
                buffer = io.BytesIO()
                elements = []
                
                data = [error_df.columns.tolist()] + error_df.values.tolist()
                
                # ترجمه هدرها اگر انگلیسی
                translations_local = {
                    "تجهیز": "Equipment",
                    "مدل": "Model",
                    "MAE": "MAE",
                    "RMSE": "RMSE"
                }
                use_persian = available_fonts and font_name != "Helvetica"
                if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 4:
                    data[0][0] = translations_local.get(data[0][0], data[0][0])
                    data[0][1] = translations_local.get(data[0][1], data[0][1])
                    data[0][2] = translations_local.get(data[0][2], data[0][2])
                    data[0][3] = translations_local.get(data[0][3], data[0][3])
                
                # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                if use_persian:
                    try:
                        import arabic_reshaper
                        from bidi.algorithm import get_display
                        for row in data:
                            for i, cell in enumerate(row):
                                if isinstance(cell, str):
                                    row[i] = get_display(arabic_reshaper.reshape(cell))
                    except ImportError:
                        st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                    ('ALIGN', (0,0), (-1,-1), 'CENTER')
                ]))
                elements.append(table)
                
                title = "جدول خطاها"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab9_errors.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab10: تحلیل دیتا -----------
with tab10:
    st.subheader("🔬 تحلیل دیتا و تعیین متغیرهای تاثیرگذار")

    target_var = st.selectbox("📌 انتخاب متغیر وابسته:", columns)
    predictor_vars = st.multiselect("📌 انتخاب متغیرهای مستقل:", [col for col in columns if col != target_var])

    if target_var and predictor_vars:
        df_selected = df[[target_var] + predictor_vars].dropna()

        if len(df_selected) < 2:
            st.warning("⚠️ داده کافی برای تحلیل وجود ندارد (حداقل ۲ رکورد لازم است).")
        else:
            st.markdown("### 📊 ماتریس همبستگی")
            corr = df_selected.corr()
            fig_corr = px.imshow(
                corr,
                text_auto=True,
                color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1,
                title="ماتریس همبستگی"
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            st.markdown("**💡 تفسیر همبستگی:**")
            for col in predictor_vars:
                r = corr.loc[target_var, col]
                if r > 0.7:
                    strength = "قوی"
                elif r > 0.5:
                    strength = "قابل توجه"
                else:
                    strength = "ضعیف"
                st.write(f"{col}: همبستگی با {target_var} = {r:.2f} → {strength}")

            st.markdown("### 📈 تحلیل رگرسیون")

            st.markdown("#### رگرسیون تک‌متغیره")
            single_results = []
            for col in predictor_vars:
                X = df_selected[[col]].dropna()
                if len(X) < 2:
                    st.warning(f"⚠️ داده برای {col} کافی نیست (حداقل ۲ رکورد).")
                    continue
                X_const = sm.add_constant(X)
                y_temp = df_selected.loc[X.index, target_var]
                if len(y_temp) < 2 or X_const.shape[0] == 0:
                    st.warning(f"⚠️ X_const خالی برای {col}.")
                    continue
                try:
                    model = sm.OLS(y_temp, X_const).fit()
                    r2 = model.rsquared
                    p_val = model.pvalues[col] if col in model.pvalues else np.nan
                    significant = p_val < 0.05 and r2 > 0.75
                    single_results.append({
                        "Variable": col,
                        "R²": r2,
                        "p-value": p_val,
                        "Impactful": "✅" if significant else "❌"
                    })
                except Exception as e:
                    st.warning(f"⚠️ خطا در رگرسیون {col}: {e}")
                    continue
            
            if single_results:
                st.table(pd.DataFrame(single_results))
            else:
                st.info("هیچ رگرسیون موفقی اجرا نشد.")

            if len(predictor_vars) > 1:
                st.markdown("#### رگرسیون چندمتغیره")
                X_multi = df_selected[predictor_vars].dropna()
                if len(X_multi) < 2:
                    st.warning("⚠️ داده برای رگرسیون چندمتغیره کافی نیست.")
                else:
                    X_multi_const = sm.add_constant(X_multi)
                    y_multi = df_selected.loc[X_multi.index, target_var]
                    if len(y_multi) < 2 or X_multi_const.shape[0] == 0:
                        st.warning("⚠️ X_multi_const خالی.")
                    else:
                        try:
                            multi_model = sm.OLS(y_multi, X_multi_const).fit()
                            multi_summary = pd.DataFrame({
                                "Variable": multi_model.params.index[1:],
                                "Coefficient": multi_model.params.values[1:],
                                "p-value": multi_model.pvalues.values[1:],
                                "Significant": ["✅" if p < 0.05 else "❌" for p in multi_model.pvalues.values[1:]]
                            })
                            st.table(multi_summary)
                        except Exception as e:
                            st.warning(f"⚠️ خطا در رگرسیون چندمتغیره: {e}")

            st.markdown("### 📦 نمودار Box Plot و تعیین UCL/LCL")
            for col in predictor_vars + [target_var]:
                Q1 = df_selected[col].quantile(0.25)
                Q3 = df_selected[col].quantile(0.75)
                IQR = Q3 - Q1
                LCL = Q1 - 1.5 * IQR
                UCL = Q3 + 1.5 * IQR

                fig_box = px.box(df_selected, y=col, points="all", title=f"Box Plot: {col}")

                fig_box.add_hline(
                    y=UCL, line_dash="dash", line_color="red",
                    annotation_text=f"UCL = {UCL:.2f}", annotation_position="top right"
                )
                fig_box.add_hline(
                    y=LCL, line_dash="dash", line_color="green",
                    annotation_text=f"LCL = {LCL:.2f}", annotation_position="bottom right"
                )

                st.plotly_chart(fig_box, use_container_width=True)

                outliers = df_selected[(df_selected[col] > UCL) | (df_selected[col] < LCL)][col]
                if not outliers.empty:
                    st.markdown(
                        f"🔎 **تحلیل {col}:**\n"
                        f"- مقدار **UCL** = {UCL:.2f}\n"
                        f"- مقدار **LCL** = {LCL:.2f}\n"
                        f"- تعداد داده‌های خارج از محدوده = {len(outliers)}\n"
                        f"- مقادیر پرت: {list(outliers.values)}"
                    )
                else:
                    st.markdown(
                        f"🔎 **تحلیل {col}:**\n"
                        f"- مقدار **UCL** = {UCL:.2f}\n"
                        f"- مقدار **LCL** = {LCL:.2f}\n"
                        f"- هیچ داده‌ای خارج از محدوده وجود ندارد ✅"
                    )

            # خروجی PDF برای Tab10
            if st.button("⬇️ دانلود PDF Tab10"):
                buffer = io.BytesIO()
                elements = []
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf_corr = io.BytesIO()
                fig_corr.write_image(img_buf_corr, format='png', width=800, height=400, scale=2)
                img_buf_corr.seek(0)
                elements.append(Image(img_buf_corr, width=500, height=300))
                
                # جدول‌های رگرسیون
                if single_results:
                    single_df = pd.DataFrame(single_results)
                    data_single = [single_df.columns.tolist()] + single_df.values.tolist()
                    
                    # ترجمه هدرها اگر انگلیسی
                    translations_local = {
                        "Variable": "Variable",
                        "R²": "R²",
                        "p-value": "p-value",
                        "Impactful": "Impactful"
                    }
                    use_persian = available_fonts and font_name != "Helvetica"
                    if not use_persian and data_single and isinstance(data_single[0], list):
                        for i, header in enumerate(data_single[0]):
                            data_single[0][i] = translations_local.get(header, header)
                    
                    # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                    if use_persian:
                        try:
                            import arabic_reshaper
                            from bidi.algorithm import get_display
                            for row in data_single:
                                for i, cell in enumerate(row):
                                    if isinstance(cell, str):
                                        row[i] = get_display(arabic_reshaper.reshape(cell))
                        except ImportError:
                            st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                    
                    table_single = Table(data_single)
                    table_single.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                        ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                        ('ALIGN', (0,0), (-1,-1), 'CENTER')
                    ]))
                    elements.append(table_single)
                
                if 'multi_summary' in locals():
                    data_multi = [multi_summary.columns.tolist()] + multi_summary.values.tolist()
                    
                    # ترجمه هدرها اگر انگلیسی
                    translations_local = {
                        "Variable": "Variable",
                        "Coefficient": "Coefficient",
                        "p-value": "p-value",
                        "Significant": "Significant"
                    }
                    if not use_persian and data_multi and isinstance(data_multi[0], list):
                        for i, header in enumerate(data_multi[0]):
                            data_multi[0][i] = translations_local.get(header, header)
                    
                    # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                    if use_persian:
                        try:
                            import arabic_reshaper
                            from bidi.algorithm import get_display
                            for row in data_multi:
                                for i, cell in enumerate(row):
                                    if isinstance(cell, str):
                                        row[i] = get_display(arabic_reshaper.reshape(cell))
                        except ImportError:
                            st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                    
                    table_multi = Table(data_multi)
                    table_multi.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                        ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                        ('ALIGN', (0,0), (-1,-1), 'CENTER')
                    ]))
                    elements.append(table_multi)
                
                # Box Plots
                for col in predictor_vars + [target_var]:
                    fig_box_col = px.box(df_selected, y=col, points="all", title=f"Box Plot: {col}")
                    img_buf_box = io.BytesIO()
                    fig_box_col.write_image(img_buf_box, format='png', width=800, height=400, scale=2)
                    img_buf_box.seek(0)
                    elements.append(Image(img_buf_box, width=500, height=300))
                
                title = "تحلیل دیتا"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab10.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
    else:
        st.info("⚠️ لطفاً متغیر وابسته و حداقل یک متغیر مستقل انتخاب کنید تا تحلیل شروع شود.")

# ----------- Tab11: تشخیص ناهنجاری‌ها -----------
with tab11:
    st.subheader("🚨 تشخیص ناهنجاری‌ها و هشدارها")

    anomaly_col = st.selectbox("🔌 انتخاب تجهیز برای تحلیل ناهنجاری:", columns, key="anomaly_select")
    
    if anomaly_col:
        df_anomaly = filtered_df[["تاریخ", "تاریخ شمسی", anomaly_col]].dropna().copy()

        if len(df_anomaly) < 2:
            st.warning(f"⚠️ داده کافی برای تحلیل ناهنجاری در {anomaly_col} وجود ندارد (حداقل 2 رکورد لازم است).")
        else:
            X = df_anomaly[[anomaly_col]].values
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            df_anomaly["is_anomaly"] = iso_forest.fit_predict(X)
            df_anomaly["is_anomaly"] = df_anomaly["is_anomaly"] == -1

            Q1 = df_anomaly[anomaly_col].quantile(0.25)
            Q3 = df_anomaly[anomaly_col].quantile(0.75)
            IQR = Q3 - Q1
            LCL = Q1 - 1.5 * IQR
            UCL = Q3 + 1.5 * IQR

            fig_anomaly = go.Figure()
            normal_data = df_anomaly[~df_anomaly["is_anomaly"]]
            fig_anomaly.add_trace(go.Scatter(
                x=normal_data["تاریخ"],
                y=normal_data[anomaly_col],
                mode="markers",
                name="داده‌های نرمال",
                marker=dict(color="blue", size=8)
            ))
            anomaly_data = df_anomaly[df_anomaly["is_anomaly"]]
            if not anomaly_data.empty:
                fig_anomaly.add_trace(go.Scatter(
                    x=anomaly_data["تاریخ"],
                    y=anomaly_data[anomaly_col],
                    mode="markers",
                    name="ناهنجاری‌ها",
                    marker=dict(color="red", size=12, symbol="x")
                ))

            fig_anomaly.add_hline(
                y=UCL, line_dash="dash", line_color="red",
                annotation_text=f"UCL = {UCL:.2f}", annotation_position="top right"
            )
            fig_anomaly.add_hline(
                y=LCL, line_dash="dash", line_color="green",
                annotation_text=f"LCL = {LCL:.2f}", annotation_position="bottom right"
            )

            fig_anomaly.update_layout(
                title=f"📊 تشخیص ناهنجاری‌ها در مصرف {anomaly_col}",
                xaxis_title="تاریخ",
                yaxis_title="مصرف (MWh)",
                template="plotly_white",
                height=500
            )
            st.plotly_chart(fig_anomaly, use_container_width=True)

            if not anomaly_data.empty:
                st.warning(f"⚠️ {len(anomaly_data)} ناهنجاری در مصرف {anomaly_col} شناسایی شد!")
                st.markdown("📋 **جدول ناهنجاری‌ها**")
                anomaly_table = anomaly_data[["تاریخ شمسی", anomaly_col]].rename(
                    columns={anomaly_col: "مصرف (MWh)", "تاریخ شمسی": "تاریخ"}
                )
                anomaly_table["مصرف (MWh)"] = anomaly_table["مصرف (MWh)"].round(2)
                st.dataframe(anomaly_table, use_container_width=True)

                st.markdown("### 🔎 تحلیل ناهنجاری‌ها")
                for idx, row in anomaly_data.iterrows():
                    date_sh = row["تاریخ شمسی"]
                    value = row[anomaly_col]
                    reason = "بیش از حد بالا" if value > UCL else "بیش از حد پایین"
                    st.write(f"- تاریخ: {date_sh} | مصرف: {value:.2f} MWh | دلیل: {reason}")
            else:
                st.success(f"✅ هیچ ناهنجاری در مصرف {anomaly_col} شناسایی نشد.")

            # خروجی PDF برای Tab11
            if st.button("⬇️ دانلود PDF Tab11"):
                buffer = io.BytesIO()
                elements = []
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf = io.BytesIO()
                fig_anomaly.write_image(img_buf, format='png', width=800, height=500, scale=2)
                img_buf.seek(0)
                elements.append(Image(img_buf, width=500, height=300))
                
                if not anomaly_data.empty:
                    data = [anomaly_table.columns.tolist()] + anomaly_table.values.tolist()
                    
                    # ترجمه هدرها اگر انگلیسی
                    translations_local = {
                        "تاریخ": "Date",
                        "مصرف (MWh)": "Consumption (MWh)"
                    }
                    use_persian = available_fonts and font_name != "Helvetica"
                    if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 2:
                        data[0][0] = translations_local.get(data[0][0], data[0][0])
                        data[0][1] = translations_local.get(data[0][1], data[0][1])
                    
                    # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                    if use_persian:
                        try:
                            import arabic_reshaper
                            from bidi.algorithm import get_display
                            for row in data:
                                for i, cell in enumerate(row):
                                    if isinstance(cell, str):
                                        row[i] = get_display(arabic_reshaper.reshape(cell))
                        except ImportError:
                            st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                    
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                        ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                        ('ALIGN', (0,0), (-1,-1), 'CENTER')
                    ]))
                    elements.append(table)
                
                title = "تشخیص ناهنجاری‌ها"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab11.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab12: گزارش زیست‌محیطی (داره، تغییر فونت) -----------
with tab12:
    st.subheader("🌍 گزارش زیست‌محیطی و پایداری")

    env_cols = st.multiselect("🔌 انتخاب تجهیزات برای تحلیل زیست‌محیطی:", 
                              columns, 
                              default=columns[:3] if columns else [],
                              key="env_multiselect")

    if env_cols:
        use_persian = available_fonts and font_name != "Helvetica"
        lang_mode = "fa" if use_persian else "en"

        st.markdown("### ⚙️ تنظیمات")
        co2_factor = st.number_input(
            "فاکتور انتشار CO2 (kg CO2/kWh):",
            min_value=0.0,
            value=0.5,
            step=0.01,
            key="co2_factor"
        )
        reduction_target = st.number_input(
            "هدف کاهش انتشار CO2 (%):",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=1.0,
            key="reduction_target"
        )

        df_env = filtered_df[["تاریخ", "تاریخ شمسی"] + env_cols].copy()
        for col in env_cols:
            df_env[f"CO2_{col}"] = df_env[col] * 1000 * co2_factor

        co2_columns = [f"CO2_{col}" for col in env_cols]
        df_env["CO2_Total"] = df_env[co2_columns].sum(axis=1)

        fig_co2 = px.line(
            df_env,
            x="تاریخ",
            y="CO2_Total",
            title="📈 روند انتشار CO2 کل" if lang_mode=="fa" else "📈 Total CO2 Emissions Trend",
            template="plotly_white",
            markers=True
        )
        fig_co2.update_layout(
            xaxis_title="تاریخ" if lang_mode=="fa" else "Date",
            yaxis_title="انتشار CO2 (kg)" if lang_mode=="fa" else "CO2 Emissions (kg)",
            height=500
        )
        st.plotly_chart(fig_co2, use_container_width=True)

        co2_totals = df_env[co2_columns].sum().reset_index()
        co2_totals.columns = ["تجهیز" if lang_mode=="fa" else "Equipment", "CO2 (kg)"]
        co2_totals["تجهیز" if lang_mode=="fa" else "Equipment"] = co2_totals[
            "تجهیز" if lang_mode=="fa" else "Equipment"
        ].str.replace("CO2_", "")
        fig_pie = px.pie(
            co2_totals,
            names="تجهیز" if lang_mode=="fa" else "Equipment",
            values="CO2 (kg)",
            title="🥧 توزیع انتشار CO2 بین تجهیزات" if lang_mode=="fa" else "🥧 CO2 Emission Distribution by Equipment",
            template="plotly_white"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        total_co2 = df_env["CO2_Total"].sum()
        target_co2 = total_co2 * (1 - reduction_target / 100)
        st.markdown("### 🔎 تحلیل پایداری" if lang_mode=="fa" else "### 🔎 Sustainability Analysis")
        if lang_mode == "fa":
            st.write(f"- **کل انتشار CO2**: {total_co2:,.2f} kg")
            st.write(f"- **هدف کاهش CO2**: {target_co2:,.2f} kg (کاهش {reduction_target}%)")
        else:
            st.write(f"- **Total CO2 Emissions**: {total_co2:,.2f} kg")
            st.write(f"- **Target CO2 Emissions**: {target_co2:,.2f} kg (Reduction {reduction_target}%)")

        if total_co2 > target_co2:
            if lang_mode == "fa":
                st.warning(f"⚠️ انتشار فعلی {total_co2 - target_co2:,.2f} kg بیشتر از هدف است.")
            else:
                st.warning(f"⚠️ Current emissions exceed the target by {total_co2 - target_co2:,.2f} kg.")
        else:
            if lang_mode == "fa":
                st.success("✅ انتشار فعلی در محدوده هدف کاهش است!")
            else:
                st.success("✅ Current emissions are within the reduction target!")

        st.markdown("### 📝 تولید گزارش PDF" if lang_mode=="fa" else "### 📝 Generate PDF Report")
        buffer = io.BytesIO()
        elements = []

        elements.append(Paragraph("گزارش زیست‌محیطی و پایداری" if lang_mode=="fa" else "Environmental & Sustainability Report", ParagraphStyle('Title', alignment=1 if lang_mode=="fa" else 0)))
        elements.append(Spacer(1, 12))

        if lang_mode == "fa":
            summary_data = [
                ["معیار", "مقدار"],
                ["کل انتشار CO2 (kg)", f"{total_co2:,.2f}"],
                ["هدف کاهش CO2 (kg)", f"{target_co2:,.2f}"],
                ["فاکتور انتشار (kg CO2/kWh)", f"{co2_factor:.2f}"],
                ["هدف کاهش (%)", f"{reduction_target:.1f}"]
            ]
        else:
            summary_data = [
                ["Metric", "Value"],
                ["Total CO2 Emissions (kg)", f"{total_co2:,.2f}"],
                ["Target CO2 (kg)", f"{target_co2:,.2f}"],
                ["Emission Factor (kg CO2/kWh)", f"{co2_factor:.2f}"],
                ["Reduction Target (%)", f"{reduction_target:.1f}"]
            ]

        table_summary = Table(summary_data)
        table_summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(Paragraph("خلاصه معیارهای زیست‌محیطی" if lang_mode=="fa" else "Environmental Summary", ParagraphStyle('Normal', alignment=1 if lang_mode=="fa" else 0)))
        elements.append(Spacer(1, 12))
        elements.append(table_summary)

        if lang_mode == "fa":
            equipment_data = [["تجهیز", "انتشار CO2 (kg)"]] + co2_totals.values.tolist()
        else:
            equipment_data = [["Equipment", "CO2 (kg)"]] + co2_totals.values.tolist()

        table_equipment = Table(equipment_data)
        table_equipment.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("توزیع انتشار CO2 بین تجهیزات" if lang_mode=="fa" else "CO2 Distribution by Equipment", ParagraphStyle('Normal', alignment=1 if lang_mode=="fa" else 0)))
        elements.append(Spacer(1, 12))
        elements.append(table_equipment)

        # اضافه کردن نمودارها به PDF
        img_buf_co2 = io.BytesIO()
        import io

# ایجاد بایت‌استریم از تصویر بدون نیاز به Kaleido
        img_buf_co2 = io.BytesIO()
        img_bytes = fig_co2.to_image(format="png", width=800, height=500, scale=2)
        img_buf_co2.write(img_bytes)
        img_buf_co2.seek(0)
        img_buf_co2.seek(0)
        elements.append(Image(img_buf_co2, width=500, height=300))

        img_buf_pie = io.BytesIO()
        fig_pie.write_image(img_buf_pie, format='png', width=800, height=500, scale=2)
        img_buf_pie.seek(0)
        elements.append(Image(img_buf_pie, width=500, height=300))

        title = "گزارش زیست‌محیطی"
        if not use_persian:
            title = translations.get(title, title)
        generate_pdf(title, elements, buffer)

        # 👈 دانلود با getvalue() برای اطمینان
        pdf_data = buffer.getvalue()
        st.download_button(
            label="⬇️ دانلود گزارش زیست‌محیطی (PDF)" if lang_mode=="fa" else "⬇️ Download Environmental Report (PDF)",
            data=pdf_data,
            file_name="گزارش_زیست_محیطی.pdf" if lang_mode=="fa" else "Environmental_Report.pdf",
            mime="application/pdf"
        )
        
        # چک فونت
        if not available_fonts:
            st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab13: مقایسه با استانداردها -----------
with tab13:
    st.subheader("🏭 مقایسه با استانداردهای صنعتی")
    
    uploaded_std = st.file_uploader("📂 آپلود فایل استاندارد (CSV)", type=["csv"])
    if uploaded_std:
        standards_df = pd.read_csv(uploaded_std)
        st.dataframe(standards_df)
        
        if 'تولید (تن)' not in filtered_df.columns:
            production = st.number_input("📏 مقدار تولید کل (تن):", value=1000.0)
        else:
            production = filtered_df['تولید (تن)'].sum()
        
        selected_col = st.selectbox("🔌 انتخاب تجهیز:", columns)
        
        if selected_col and not standards_df.empty:
            actual_consumption_per_ton = filtered_df[selected_col].sum() / production
            std_value = standards_df[standards_df['تجهیز'] == selected_col]['استاندارد kWh/تن'].iloc[0] if selected_col in standards_df['تجهیز'].values else 0.5
            
            deviation = ((actual_consumption_per_ton - std_value) / std_value) * 100
            
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=deviation,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "انحراف از استاندارد (%)"},
                delta={'reference': 0},
                gauge={
                    'axis': {'range': [-100, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [-100, -20], 'color': "red"},
                        {'range': [-20, 20], 'color': "yellow"},
                        {'range': [20, 100], 'color': "green"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 20
                    }
                }
            ))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
            st.metric("مصرف واقعی (kWh/تن)", f"{actual_consumption_per_ton:.2f}")
            st.metric("استاندارد (kWh/تن)", f"{std_value:.2f}")
            st.info(f"انحراف: {deviation:.1f}% {'(بالاتر از حد مجاز)' if deviation > 20 else '(در محدوده)'}")

            # خروجی PDF برای Tab13
            if st.button("⬇️ دانلود PDF Tab13"):
                buffer = io.BytesIO()
                elements = []
                
                # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                img_buf = io.BytesIO()
                fig_gauge.write_image(img_buf, format='png', width=800, height=400, scale=2)
                img_buf.seek(0)
                elements.append(Image(img_buf, width=500, height=300))
                
                title = "مقایسه با استانداردهای صنعتی"
                if not use_persian:
                    title = translations.get(title, title)
                generate_pdf(title, elements, buffer)
                
                # 👈 دانلود با getvalue() برای اطمینان
                pdf_data = buffer.getvalue()
                st.download_button(
                    label="دانلود PDF",
                    data=pdf_data,
                    file_name="tab13.pdf",
                    mime="application/pdf"
                )
                
                # چک فونت
                if not available_fonts:
                    st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
    else:
        st.info("📌 نمونه CSV: ستون‌های 'تجهیز' و 'استاندارد kWh/تن'")

# ----------- Tab14: تحلیل هزینه -----------
with tab14:
    st.subheader("💰 تحلیل هزینه و بودجه")
    
    rate_peak = st.number_input("💸 نرخ اوج (تومان/kWh):", value=1000.0)
    rate_offpeak = st.number_input("💸 نرخ خارج اوج (تومان/kWh):", value=500.0)
    peak_hours = st.slider("⏰ ساعات اوج روزانه:", 0, 24, 8)
    
    if 'ساعت' in filtered_df.columns:
        peak_consumption = filtered_df[filtered_df['ساعت'] >= peak_hours][columns].sum().sum()
        offpeak_consumption = filtered_df[filtered_df['ساعت'] < peak_hours][columns].sum().sum()
    else:
        total_consumption = filtered_df[columns].sum().sum()
        peak_consumption = total_consumption * (peak_hours / 24)
        offpeak_consumption = total_consumption - peak_consumption
    
    peak_cost = peak_consumption * rate_peak
    offpeak_cost = offpeak_consumption * rate_offpeak
    total_cost = peak_cost + offpeak_cost
    
    cost_df = pd.DataFrame({
        'دوره': ['اوج', 'خارج اوج', 'کل'],
        'مصرف (kWh)': [peak_consumption, offpeak_consumption, total_consumption],
        'هزینه (تومان)': [peak_cost, offpeak_cost, total_cost]
    })
    st.dataframe(cost_df.style.format({'هزینه (تومان)': '{:,.0f}'}))
    
    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(
            label=["مصرف اوج", "مصرف خارج اوج", "کل هزینه"],
            color="blue"
        ),
        link=dict(
            source=[0, 1, 0, 1],
            target=[2, 2, 2, 2],
            value=[peak_cost, offpeak_cost, peak_cost, offpeak_cost]
        )
    )])
    fig_sankey.update_layout(title="جریان هزینه‌ها")
    st.plotly_chart(fig_sankey, use_container_width=True)
    
    budget = st.number_input("🎯 بودجه ماهانه (تومان):", value=total_cost * 1.2)
    st.metric("هزینه کل", f"{total_cost:,.0f} تومان", delta=f"{total_cost - budget:.0f}")

    # خروجی PDF برای Tab14
    if st.button("⬇️ دانلود PDF Tab14"):
        buffer = io.BytesIO()
        elements = []
        
        data = [cost_df.columns.tolist()] + cost_df.values.tolist()
        
        # ترجمه هدرها اگر انگلیسی
        translations_local = {
            "دوره": "Period",
            "مصرف (kWh)": "Consumption (kWh)",
            "هزینه (تومان)": "Cost (Toman)"
        }
        use_persian = available_fonts and font_name != "Helvetica"
        if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 3:
            data[0][0] = translations_local.get(data[0][0], data[0][0])
            data[0][1] = translations_local.get(data[0][1], data[0][1])
            data[0][2] = translations_local.get(data[0][2], data[0][2])
        
        # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
        if use_persian:
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                for row in data:
                    for i, cell in enumerate(row):
                        if isinstance(cell, str):
                            row[i] = get_display(arabic_reshaper.reshape(cell))
            except ImportError:
                st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
            ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        elements.append(table)
        
        # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
        img_buf = io.BytesIO()
        fig_sankey.write_image(img_buf, format='png', width=800, height=400, scale=2)
        img_buf.seek(0)
        elements.append(Image(img_buf, width=500, height=300))
        
        title = "تحلیل هزینه و بودجه"
        if not use_persian:
            title = translations.get(title, title)
        generate_pdf(title, elements, buffer)
        
        # 👈 دانلود با getvalue() برای اطمینان
        pdf_data = buffer.getvalue()
        st.download_button(
            label="دانلود PDF",
            data=pdf_data,
            file_name="tab14.pdf",
            mime="application/pdf"
        )
        
        # چک فونت
        if not available_fonts:
            st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab15: داشبورد تعاملی -----------
with tab15:
    st.subheader("📱 داشبورد تعاملی زنده")
    
    view_selector = st.selectbox("🔄 انتخاب ویو:", ["KPI خلاصه", "روند سریع",])
    
    selected_cols = st.multiselect("🔌 تجهیزات:", columns, default=columns[:3])
    
    if selected_cols:
        if view_selector == "KPI خلاصه":
            col1, col2, col3 = st.columns(3)
            for i, col in enumerate(selected_cols):
                c = [col1, col2, col3][i % 3]
                with c:
                    total = filtered_df[col].sum()
                    st.metric(f"{col}", f"{total:,.0f} MWh")
        
        elif view_selector == "روند سریع":
            df_quick = filtered_df.groupby(filtered_df["تاریخ"].dt.to_period("M"))[selected_cols].sum().reset_index()
            df_quick["ماه"] = df_quick["تاریخ"].dt.strftime('%Y/%m')
            fig_quick = px.line(df_quick, x="ماه", y=selected_cols, title="روند ماهانه")
            st.plotly_chart(fig_quick, use_container_width=True)
    
    st.info("🔄 داشبورد هر ۳۰ ثانیه رفرش می‌شود (در محیط واقعی).")

    # خروجی PDF برای Tab15
    if st.button("⬇️ دانلود PDF Tab15"):
        buffer = io.BytesIO()
        elements = []
        
        if view_selector == "روند سریع":
            # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
            img_buf = io.BytesIO()
            fig_quick.write_image(img_buf, format='png', width=800, height=400, scale=2)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=500, height=300))
        
        title = "داشبورد تعاملی زنده"
        if not use_persian:
            title = translations.get(title, title)
        generate_pdf(title, elements, buffer)
        
        # 👈 دانلود با getvalue() برای اطمینان
        pdf_data = buffer.getvalue()
        st.download_button(
            label="دانلود PDF",
            data=pdf_data,
            file_name="tab15.pdf",
            mime="application/pdf"
        )
        
        # چک فونت
        if not available_fonts:
            st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")

# ----------- Tab16: گزارش‌های سفارشی (داره، تغییر فونت) -----------
with tab16:
    st.subheader("📱 گزارش‌های سفارشی و واتساپ")
    
    uploaded_font = st.file_uploader("🖋 آپلود فونت فارسی (TTF, مثل BNazanin.ttf)", type=["ttf"])
    font_path_tab16 = None
    if uploaded_font:
        with open("temp_font_tab16.ttf", "wb") as f:
            f.write(uploaded_font.getvalue())
        font_path_tab16 = "temp_font_tab16.ttf"
    else:
        font_path_tab16 = r"D:\BNazanin.ttf"
        if not os.path.exists(font_path_tab16):
            st.warning("⚠️ فونت B Nazanin پیدا نشد.")
    
    include_kpi = st.checkbox("شامل KPI")
    include_trend = st.checkbox("شامل روند")
    selected_cols_report = st.multiselect("تجهیزات:", columns, default=columns[:2])
    
    st.markdown("### 📅 انتخاب بازه زمانی")
    min_date, max_date = filtered_df["تاریخ"].min(), filtered_df["تاریخ"].max()
    start_date, end_date = st.date_input("بازه زمانی", [min_date, max_date], key="report_date_range")
    st.markdown(f"**تاریخ شمسی شروع:** {JalaliDate(start_date).strftime('%Y/%m/%d')}")
    st.markdown(f"**تاریخ شمسی پایان:** {JalaliDate(end_date).strftime('%Y/%m/%d')}")
    
    mask_report = (filtered_df["تاریخ"] >= pd.to_datetime(start_date)) & (filtered_df["تاریخ"] <= pd.to_datetime(end_date))
    filtered_report_df = filtered_df.loc[mask_report].copy()
    
    if filtered_report_df.empty:
        st.warning("⚠️ هیچ داده‌ای برای بازه انتخاب‌شده یافت نشد.")
        st.stop()
    
    granularity = st.selectbox("📊 سطح جزئیات خروجی:", ["روزانه", "ماهانه"], key="granularity")
    
    if st.button("📝 تولید گزارش"):
        if not selected_cols_report:
            st.error("⚠️ حداقل یک تجهیز انتخاب کنید!")
            st.stop()
        
        buffer = io.BytesIO()
        elements = []
        
        use_persian = available_fonts and font_name != "Helvetica"
        if font_path_tab16 and os.path.exists(font_path_tab16):
            try:
                pdfmetrics.registerFont(TTFont("BNazanin", font_path_tab16))
                title_style = ParagraphStyle(
                    name='TitleRTL',
                    parent=getSampleStyleSheet()['Title'],
                    fontName="BNazanin",
                    fontSize=18,
                    alignment=1
                )
                normal_style = ParagraphStyle(
                    name='RTLStyle',
                    parent=getSampleStyleSheet()['Normal'],
                    fontName="BNazanin",
                    fontSize=12,
                    leading=14,
                    alignment=1,
                    spaceAfter=12
                )
                st.success("✅ فونت B Nazanin ثبت شد.")
            except Exception as e:
                st.error(f"⚠️ خطا در فونت: {e}")
                title_style = getSampleStyleSheet()['Title']
                normal_style = getSampleStyleSheet()['Normal']
        else:
            title_style = getSampleStyleSheet()['Title']
            normal_style = getSampleStyleSheet()['Normal']
        
        title_text = f"گزارش سفارشی پایش برق ({JalaliDate(start_date).strftime('%Y/%m/%d')} تا {JalaliDate(end_date).strftime('%Y/%m/%d')})"
        elements.append(Paragraph(title_text, title_style))
        elements.append(Spacer(1, 12))
        
        if include_kpi:
            elements.append(Paragraph("جدول KPI", normal_style))
            if granularity == "روزانه":
                kpi_summary = filtered_report_df[selected_cols_report].sum()
                kpi_data = [['تجهیز', 'مجموع بازه']] + [[col, f"{kpi_summary[col]:.2f}"] for col in selected_cols_report]
            else:
                filtered_report_df["ماه شمسی"] = filtered_report_df["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
                kpi_monthly = filtered_report_df.groupby("ماه شمسی")[selected_cols_report].sum()
                kpi_data = [['تجهیز', 'مجموع بازه']] + [[col, f"{kpi_monthly[col].sum():.2f}"] for col in selected_cols_report]
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                "تجهیز": "Equipment",
                "مجموع بازه": "Total Period"
            }
            if not use_persian and kpi_data and isinstance(kpi_data[0], list):
                kpi_data[0][0] = translations_local.get(kpi_data[0][0], kpi_data[0][0])
                kpi_data[0][1] = translations_local.get(kpi_data[0][1], kpi_data[0][1])
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    for row in kpi_data:
                        for i, cell in enumerate(row):
                            if isinstance(cell, str):
                                row[i] = get_display(arabic_reshaper.reshape(cell))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            table = Table(kpi_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
                ('GRID', (0,0), (-1,-1), 1, colors.darkblue),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))
        
        if include_trend:
            elements.append(Paragraph(f"نمودار روند مصرف ({granularity})", normal_style))
            
            df_trend = filtered_report_df.copy()
            if granularity == "روزانه":
                df_trend["تاریخ نمایش"] = df_trend["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m/%d'))
                df_trend = df_trend.groupby("تاریخ نمایش")[selected_cols_report].mean().reset_index()
            else:
                df_trend["تاریخ نمایش"] = df_trend["تاریخ"].map(lambda x: JalaliDate(x).strftime('%Y/%m'))
                df_trend = df_trend.groupby("تاریخ نمایش")[selected_cols_report].mean().reset_index()
            
            if not df_trend.empty:
                fig_trend = px.line(
                    df_trend, 
                    x="تاریخ نمایش", 
                    y=selected_cols_report, 
                    title=f"روند مصرف ({granularity})",
                    color_discrete_sequence=px.colors.qualitative.Set1
                )
                fig_trend.update_layout(
                    xaxis_title="تاریخ شمسی", 
                    yaxis_title="میانگین مصرف (MWh)", 
                    plot_bgcolor='white', 
                    paper_bgcolor='white'
                )
                
                st.plotly_chart(fig_trend, use_container_width=True)
                
                img_buffer = io.BytesIO()
                fig_trend.write_image(img_buffer, format='png', width=500, height=300, scale=2)
                img_buffer.seek(0)
                
                img = Image(img_buffer, width=500, height=300)
                elements.append(img)
                elements.append(Spacer(1, 12))
        
        title = "گزارش سفارشی"
        if not use_persian:
            title = translations.get(title, title)
        generate_pdf(title, elements, buffer)
        
        # 👈 دانلود با getvalue() برای اطمینان
        pdf_data = buffer.getvalue()
        st.download_button("⬇️ دانلود PDF", pdf_data, "گزارش_سفارشی.pdf", "application/pdf")
        
        if uploaded_font:
            os.remove("temp_font_tab16.ttf")
    
    if st.checkbox("📱 ارسال به واتساپ"):
        phone_number = st.text_input("📞 شماره واتساپ (با +، مثل +989123456789):")
        message = st.text_area("💬 متن پیام (PDF رو دستی آپلود کن):")
        
        if st.button("ارسال به واتساپ"):
            if not phone_number or not message:
                st.error("⚠️ شماره و متن رو وارد کن!")
                st.stop()
            
            import pywhatkit as pwk
            pwk.sendwhatmsg_instantly(phone_number, message)
            st.success("✅ پیام به واتساپ ارسال شد! (PDF رو دانلود و دستی ضمیمه کن.)")
            st.download_button("📎 دانلود PDF برای واتساپ", pdf_data, "گزارش.pdf", "application/pdf")

# ----------- Tab17: شبیه‌سازی سناریوها (داره، تغییر فونت) -----------
with tab17:
    st.subheader("🎲 شبیه‌سازی سناریوها")
    
    selected_scen = st.multiselect("🔮 سناریوها (تجهیزات):", columns, default=columns[:3])
    
    if selected_scen:
        base_means = filtered_df[selected_scen].mean()
        
        change_factor = st.slider("📈 فاکتور تغییر (±%):", 0, 50, 20)
        n_simulations = st.slider("🔄 تعداد شبیه‌سازی:", 100, 5000, 1000)
        
        sim_df = monte_carlo_simulation(base_means.values, selected_scen, n_simulations, change_factor)
        
        for col in selected_scen:
            fig_hist = px.histogram(sim_df, x=col, title=f"توزیع شبیه‌سازی {col} (±{change_factor}%)",
                                    color_discrete_sequence=['blue'])
            st.plotly_chart(fig_hist, use_container_width=True)
        
        summary = sim_df.describe().round(2)
        st.dataframe(summary)
        
        st.info(f"💡 میانگین شبیه‌سازی کل: {sim_df.mean().mean():.2f} MWh (تغییر ±{change_factor}%)")
        
        st.markdown("### 📝 تولید PDF گزارش شبیه‌سازی")
        
        uploaded_font_sim = st.file_uploader("🖋 آپلود فونت فارسی (TTF, مثل BNazanin.ttf)", type=["ttf"], key="sim_font")
        font_path_sim = None
        if uploaded_font_sim:
            with open("temp_sim_font.ttf", "wb") as f:
                f.write(uploaded_font_sim.getvalue())
            font_path_sim = "temp_sim_font.ttf"
        else:
            font_path_sim = r"D:\BNazanin.ttf"
            if not os.path.exists(font_path_sim):
                st.warning("⚠️ فونت B Nazanin پیدا نشد.")
        
        if st.button("تولید PDF", key="sim_pdf"):
            pdf_buffer = io.BytesIO()
            elements = []
            
            use_persian = available_fonts and font_name != "Helvetica"
            if font_path_sim and os.path.exists(font_path_sim):
                try:
                    pdfmetrics.registerFont(TTFont("BNazanin", font_path_sim))
                    title_style = ParagraphStyle(
                        name='TitleRTL',
                        parent=getSampleStyleSheet()['Title'],
                        fontName="BNazanin",
                        fontSize=18,
                        alignment=1
                    )
                    normal_style = ParagraphStyle(
                        name='RTLStyle',
                        parent=getSampleStyleSheet()['Normal'],
                        fontName="BNazanin",
                        fontSize=12,
                        leading=14,
                        alignment=1,
                        spaceAfter=12
                    )
                except Exception as e:
                    st.error(f"⚠️ خطا در فونت: {e}")
                    title_style = getSampleStyleSheet()['Title']
                    normal_style = getSampleStyleSheet()['Normal']
            else:
                title_style = getSampleStyleSheet()['Title']
                normal_style = getSampleStyleSheet()['Normal']
            
            title_text = f"گزارش شبیه‌سازی مونت‌کارلو (±{change_factor}%) - {n_simulations} تکرار"
            elements.append(Paragraph(title_text, title_style))
            elements.append(Spacer(1, 12))
            
            elements.append(Paragraph("جدول آمار توصیفی", normal_style))
            summary_list = summary.reset_index().values.tolist()
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                # Add summary columns translations if needed
            }
            if not use_persian and summary_list and isinstance(summary_list[0], list):
                # Apply translations to headers
                pass  # Implement as needed
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    for row in summary_list:
                        for i, cell in enumerate(row):
                            if isinstance(cell, str):
                                row[i] = get_display(arabic_reshaper.reshape(cell))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            table = Table(summary_list)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
                ('GRID', (0,0), (-1,-1), 1, colors.darkblue),
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))
            
            for col in selected_scen:
                fig_hist_pdf = px.histogram(sim_df, x=col, title=f"توزیع {col}",
                                            color_discrete_sequence=['blue'])
                fig_hist_pdf.update_layout(plot_bgcolor='white', paper_bgcolor='white')
                
                img_buffer = io.BytesIO()
                fig_hist_pdf.write_image(img_buffer, format='png', width=500, height=300, scale=2)
                img_buffer.seek(0)
                img = Image(img_buffer, width=500, height=300)
                elements.append(Paragraph(f"هیستوگرام {col}", normal_style))
                elements.append(img)
                elements.append(Spacer(1, 12))
            
            title = "شبیه‌سازی سناریوها"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, pdf_buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = pdf_buffer.getvalue()
            st.download_button("⬇️ دانلود PDF شبیه‌سازی", pdf_data, "شبیه_سازی_مونت_کارلو.pdf", "application/pdf")
            
            if uploaded_font_sim:
                os.remove("temp_sim_font.ttf")

# ----------- Tab18: بهینه‌سازی -----------
with tab18:
    st.subheader("⚙️ بهینه‌سازی (LP/NLP)")
    
    opt_type = st.selectbox("نوع بهینه‌سازی:", ["خطی (LP)", "غیرخطی (NLP)"])
    
    if opt_type == "خطی (LP)":
        st.markdown("### مثال LP: حداقل هزینه مصرف تجهیزات")
        
        selected_equip = st.multiselect("تجهیزات:", columns)
        if selected_equip:
            costs = {col: st.number_input(f"هزینه {col} (تومان/MWh):", value=1000.0, key=f"cost_{col}") for col in selected_equip}
            
            min_total = st.number_input("حداقل مجموع مصرف (MWh):", value=100.0)
            max_per_equip = st.number_input("حداکثر هر تجهیز (MWh):", value=50.0)
            
            if st.button("حل LP"):
                prob = LpProblem("بهینه_مصرف_برق", LpMinimize)
                
                vars_dict = {col: LpVariable(col, lowBound=0, upBound=max_per_equip) for col in selected_equip}
                
                prob += sum(costs[col] * vars_dict[col] for col in selected_equip)
                
                prob += sum(vars_dict[col] for col in selected_equip) >= min_total
                
                prob.solve()
                
                if LpStatus[prob.status] == "Optimal":
                    results = {col: value(vars_dict[col]) for col in selected_equip}
                    total_cost = value(prob.objective)
                    
                    res_df = pd.DataFrame(list(results.items()), columns=["تجهیز", "مصرف بهینه (MWh)"])
                    res_df["هزینه (تومان)"] = [costs[col] * results[col] for col in selected_equip]
                    st.dataframe(res_df)
                    
                    st.metric("هزینه کل بهینه", f"{total_cost:.0f} تومان")
                    
                    fig = px.bar(res_df, x="تجهیز", y="مصرف بهینه (MWh)", title="تخصیص بهینه")
                    st.plotly_chart(fig, use_container_width=True)

                    # خروجی PDF برای Tab18 LP
                    if st.button("⬇️ دانلود PDF LP Tab18"):
                        buffer = io.BytesIO()
                        elements = []
                        
                        data = [res_df.columns.tolist()] + res_df.values.tolist()
                        
                        # ترجمه هدرها اگر انگلیسی
                        translations_local = {
                            "تجهیز": "Equipment",
                            "مصرف بهینه (MWh)": "Optimized Consumption (MWh)",
                            "هزینه (تومان)": "Cost (Toman)"
                        }
                        use_persian = available_fonts and font_name != "Helvetica"
                        if not use_persian and data and isinstance(data[0], list) and len(data[0]) >= 3:
                            data[0][0] = translations_local.get(data[0][0], data[0][0])
                            data[0][1] = translations_local.get(data[0][1], data[0][1])
                            data[0][2] = translations_local.get(data[0][2], data[0][2])
                        
                        # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
                        if use_persian:
                            try:
                                import arabic_reshaper
                                from bidi.algorithm import get_display
                                for row in data:
                                    for i, cell in enumerate(row):
                                        if isinstance(cell, str):
                                            row[i] = get_display(arabic_reshaper.reshape(cell))
                            except ImportError:
                                st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
                        
                        table = Table(data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),  # پس‌زمینه عنوان
                            ('TEXTCOLOR', (0,0), (-1,0), colors.black),       # متن عنوان
                            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),  # 👈 grid کم‌رنگ (نه مشکی)
                            ('ALIGN', (0,0), (-1,-1), 'CENTER')
                        ]))
                        elements.append(table)
                        
                        # تولید تصویر با کیفیت بهتر (نیاز به kaleido: pip install kaleido)
                        img_buf = io.BytesIO()
                        fig.write_image(img_buf, format='png', width=800, height=400, scale=2)
                        img_buf.seek(0)
                        elements.append(Image(img_buf, width=500, height=300))
                        
                        title = "بهینه‌سازی LP"
                        if not use_persian:
                            title = translations.get(title, title)
                        generate_pdf(title, elements, buffer)
                        
                        # 👈 دانلود با getvalue() برای اطمینان
                        pdf_data = buffer.getvalue()
                        st.download_button(
                            label="دانلود PDF",
                            data=pdf_data,
                            file_name="tab18_lp.pdf",
                            mime="application/pdf"
                        )
                        
                        # چک فونت
                        if not available_fonts:
                            st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")
                else:
                    st.error("راه‌حل بهینه پیدا نشد!")
    
    else:
        st.markdown("### مثال NLP: بهینه‌سازی غیرخطی (scipy)")
        from scipy.optimize import minimize
        
        def objective(x):
            return x[0]**2 + x[1]**2
        
        constraints = ({'type': 'eq', 'fun': lambda x: x[0] + x[1] - 10})
        bounds = [(0, None), (0, None)]
        
        res = minimize(objective, [1, 1], method='SLSQP', bounds=bounds, constraints=constraints)
        
        st.write(f"نتایج NLP: x={res.x[0]:.2f}, y={res.x[1]:.2f}, مقدار هدف={res.fun:.2f}")

        # خروجی PDF برای Tab18 NLP
        if st.button("⬇️ دانلود PDF NLP Tab18"):
            buffer = io.BytesIO()
            elements = []
            
            # ترجمه هدرها اگر انگلیسی
            translations_local = {
                # For text
            }
            use_persian = available_fonts and font_name != "Helvetica"
            text = f"نتایج NLP: x={res.x[0]:.2f}, y={res.x[1]:.2f}, مقدار هدف={res.fun:.2f}"
            if not use_persian:
                text = "NLP Results: x={:.2f}, y={:.2f}, objective={:.2f}".format(res.x[0], res.x[1], res.fun)
            
            # Reshape متن‌ها برای RTL اگر فارسی (فقط رشته‌ها)
            if use_persian:
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    text = get_display(arabic_reshaper.reshape(text))
                except ImportError:
                    st.warning("برای RTL در جدول، arabic-reshaper و python-bidi رو نصب کن.")
            
            elements.append(Paragraph(text, ParagraphStyle('Normal', alignment=1 if use_persian else 0)))
            
            title = "بهینه‌سازی NLP"
            if not use_persian:
                title = translations.get(title, title)
            generate_pdf(title, elements, buffer)
            
            # 👈 دانلود با getvalue() برای اطمینان
            pdf_data = buffer.getvalue()
            st.download_button(
                label="دانلود PDF",
                data=pdf_data,
                file_name="tab18_nlp.pdf",
                mime="application/pdf"
            )
            
            # چک فونت
            if not available_fonts:
                st.warning("⚠️ فونت فارسی پیدا نشد. PDF به انگلیسی تولید شد.")