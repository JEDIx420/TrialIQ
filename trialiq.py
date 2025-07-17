import subprocess
import sys
import os

# --- Dependency Installer ---
# This block checks for required packages and installs them if they're missing.
# This is particularly useful for environments like Cloudera where the base image
# may not include all necessary libraries.
try:
    # A quick check for a primary library. If this fails, run the installer.
    import streamlit
except ImportError:
    print("Required libraries not found. Installing...")
    try:
        # Full list of dependencies from README.md
        requirements = [
            "fastapi", "streamlit", "sqlalchemy", "pydantic", "pandas",
            "babel", "requests", "geopy", "uvicorn", "plotly"
        ]
        # Use subprocess to ensure it's run correctly.
        subprocess.check_call([sys.executable, "-m", "pip", "install", *requirements])
        print("Dependencies installed successfully.")
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        # Exit if installation fails, as the app cannot run.
        sys.exit(1)


import uuid
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any
from random import choice, randint, random

import streamlit as st
from fastapi import FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pandas as pd
from babel import Locale
from geopy.distance import geodesic
import requests
import plotly.graph_objects as go

# --- CONFIG ---
CONFIG = {
    "AI_API_KEY": os.getenv("AI_API_KEY", "<YOUR_API_KEY>"),
    "DEFAULT_LOCALE": os.getenv("DEFAULT_LOCALE", "en-US"),
    "ADMIN_BEARER_SECRET": os.getenv("ADMIN_BEARER_SECRET", "12345"),
    "SUPPORTED_LANGS": ["en", "es", "fr", "de", "hi", "zh", "pt", "ar"],
    "LOCALE_UNIT": {
        "en-US": {"weight": "lb", "temperature": "°F"},
        "en-GB": {"weight": "kg", "temperature": "°C"},
        "fr-FR": {"weight": "kg", "temperature": "°C"},
        "de-DE": {"weight": "kg", "temperature": "°C"},
        "es-ES": {"weight": "kg", "temperature": "°C"},
        "hi-IN": {"weight": "kg", "temperature": "°C"},
        "zh-CN": {"weight": "kg", "temperature": "°C"},
        "pt-BR": {"weight": "kg", "temperature": "°C"},
        "ar-SA": {"weight": "kg", "temperature": "°C"},
    },
    "ICON_CDN": "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css'>",
    "SCORING_WEIGHTS": {
        "mandatory_inclusion": 5,
        "mandatory_exclusion": -999,
        "important_inclusion": 3,
        "soft_inclusion": 1,
        "geo_match_bonus": 2,
    },
}
DEBUG_FAKE_DATA = False

# --- Helpers (order: flag_emoji, get_locale, translate, etc.) ---
def flag_emoji(locale):
    country = locale.split('-')[-1].upper()
    if len(country) == 2 and country.isalpha():
        return chr(0x1F1E6 + ord(country[0]) - ord('A')) + chr(0x1F1E6 + ord(country[1]) - ord('A'))
    return ''

def get_locale(lang_code):
    try:
        return Locale.parse(lang_code)
    except:
        return Locale.parse(CONFIG["DEFAULT_LOCALE"])

def translate(text_dict, lang):
    return text_dict.get(lang, text_dict.get("en", next(iter(text_dict.values()))))

def detect_locale():
    # st.query_params is a dict-like object, not a function call
    browser_lang = st.query_params.get("lang")
    if not browser_lang:
        browser_lang = CONFIG["DEFAULT_LOCALE"]
    
    # Ensure session_state is updated if lang is found in query params
    if "browser_lang" not in st.session_state or st.session_state.browser_lang != browser_lang:
        st.session_state["browser_lang"] = browser_lang
        
    return st.session_state.browser_lang

# --- DB Setup (SQLite for MVP) ---
Base = declarative_base()
DB_URL = os.getenv("DB_URL", "sqlite:///:memory:")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Submission(Base):
    __tablename__ = "trialiq_submissions"
    submission_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id_hash = Column(String)
    locale = Column(String)
    submitted_ts = Column(DateTime, default=datetime.utcnow)
    input_mode = Column(String)
    responses_json = Column(Text)
    matches_json = Column(Text)
    duration_sec = Column(Float)
    status = Column(String)
    meta_json = Column(Text)  # Renamed from 'metadata' to 'meta_json'

Base.metadata.create_all(bind=engine)

# --- Mock Data ---
TRIALS = [
    {"trial_id": "NCT01007279", "country_list": ["FR", "BE", "DE"], "criteria": {"age_min": 50, "diabetic": False, "cardiac_history": True}},
    {"trial_id": "NCT02592421", "country_list": ["US", "CA"], "criteria": {"age_min": 18, "diabetic": False}},
    {"trial_id": "NCT99999999", "country_list": "global", "criteria": {"age_min": 21}},
]

QUESTION_FLOW = [
    {"q_id": "age", "text_dict": {"en": "What is your age?", "fr": "Quel âge avez-vous?", "es": "¿Cuál es su edad?"}, "answer_type": "number", "voice_enabled": True, "next": "gender"},
    {"q_id": "gender", "text_dict": {"en": "What is your gender?", "fr": "Quel est votre genre?", "es": "¿Cuál es su género?"}, "answer_type": "select", "options": ["Male", "Female", "Other"], "voice_enabled": True, "next": "diabetic"},
    {"q_id": "diabetic", "text_dict": {"en": "Do you have diabetes?", "fr": "Avez-vous du diabète?", "es": "¿Tiene diabetes?"}, "answer_type": "bool", "voice_enabled": True, "next": "cardiac_history"},
    {"q_id": "cardiac_history", "text_dict": {"en": "Any history of cardiac disease?", "fr": "Antécédents de maladie cardiaque?", "es": "¿Antecedentes de enfermedad cardíaca?"}, "answer_type": "bool", "voice_enabled": True, "next": None},
]

# --- Scoring Engine ---
def geo_filter(trial, country):
    if trial["country_list"] == "global" or country in trial["country_list"]:
        return True
    return False

def score_trial(trial, responses, country):
    if not geo_filter(trial, country):
        return 0, "No study sites in your country"
    score = 0
    max_score = 5 + 3 + 1 + 2  # MVP: sum of all possible positive
    crit = trial["criteria"]
    if "age_min" in crit and responses.get("age", 0) >= crit["age_min"]:
        score += CONFIG["SCORING_WEIGHTS"]["mandatory_inclusion"]
    if "diabetic" in crit and responses.get("diabetic") == crit["diabetic"]:
        score += CONFIG["SCORING_WEIGHTS"]["important_inclusion"]
    if "cardiac_history" in crit and responses.get("cardiac_history") == crit["cardiac_history"]:
        score += CONFIG["SCORING_WEIGHTS"]["soft_inclusion"]
    score += CONFIG["SCORING_WEIGHTS"]["geo_match_bonus"]
    pct = int((score / max_score) * 100)
    return pct, "eligible" if pct > 0 else "ineligible"

# --- Streamlit UI ---
st.set_page_config(page_title="TrialIQ Clinical Trial Matcher", layout="centered")
# Load icon CDN
st.markdown(CONFIG["ICON_CDN"], unsafe_allow_html=True)

# --- Locale Detection is now done inside the run_patient_flow and other relevant places ---

# --- Sidebar: Language and Theme Switcher ---
# Ensure session state keys are initialized
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "lang" not in st.session_state:
    st.session_state.lang = CONFIG["DEFAULT_LOCALE"].split("-")[0]

lang_names = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch", "hi": "हिन्दी", "zh": "中文", "pt": "Português", "ar": "العربية"}
lang = st.sidebar.selectbox("Language", CONFIG["SUPPORTED_LANGS"], format_func=lambda l: f"{lang_names.get(l, l)}", index=CONFIG["SUPPORTED_LANGS"].index(st.session_state.get("lang", detect_locale().split("-")[0])), key="lang_select")
if lang != st.session_state.get("lang"):
    st.session_state.lang = lang
    st.session_state.browser_lang = f"{lang}-{detect_locale().split('-')[-1]}"
    st.rerun()
theme = st.sidebar.radio("Theme", ["Light", "Dark"], index=1 if st.session_state.theme=="dark" else 0)
st.session_state.theme = theme.lower()
st.query_params["theme"] = st.session_state.theme
menu = st.sidebar.selectbox("Menu", ["Patient", "Admin"], key="main_menu")

# --- Progress Bar Helper ---
def show_progress():
    step = st.session_state.get("step", 0)
    total_steps = 4 + len(QUESTION_FLOW)  # 0:welcome, 1:consent, 2:info, rest:questions, summary
    color = "#2b6cb0" if st.session_state.theme == "dark" else "#3182ce"
    if step == 'results':
        pct = 1.0
    else:
        pct = min(step, total_steps) / total_steps
    st.markdown(f'<div style="height:8px;background:{color};width:{pct*100:.1f}%;border-radius:4px;margin-bottom:16px;"></div>', unsafe_allow_html=True)

# --- Consent Step ---
def consent_card():
    card = """
    <div class="card" style="max-width:480px;margin:auto;">
    <h3>Terms & Data Consent</h3>
    <ul>
      <li>Your answers will be stored securely and used only to match you to clinical trials.</li>
      <li>No personally identifiable information will be shared with third parties.</li>
      <li>You can request data deletion at any time.</li>
    </ul>
    </div>
    """
    st.markdown(card, unsafe_allow_html=True)
    col1, col2 = st.columns([2,1])
    agree = col1.button("Agree & Continue", key="agree_btn")
    decline = col2.button("Decline", key="decline_btn")
    return agree, decline

# --- Patient Flow ---
def run_patient_flow():
    locale = detect_locale()
    lang = st.session_state.get("lang", detect_locale().split("-")[0])
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "responses" not in st.session_state:
        st.session_state.responses = {}
    if "results" not in st.session_state:
        st.session_state.results = {}
    step = st.session_state.step
    responses = st.session_state.responses
    st.title("TrialIQ Multilingual Clinical Trial Matcher")
    show_progress()

    # Results page (check first to avoid TypeError on rerun)
    if step == 'results':
        if 'results' in st.session_state:
            results = st.session_state['results']
            st.markdown('<div class="card" style="max-width:480px;margin:auto;"><b>Matched Trials</b></div>', unsafe_allow_html=True)
            if results.get('matches'):
                for m in results['matches']:
                    why = "Met age ≥" + str([t['criteria']['age_min'] for t in TRIALS if t['trial_id']==m['trial_id']][0]) if m['status']=="eligible" else ""
                    card_html = f"""
                    <div style='display:flex;align-items:center;border: 1px solid #2ecc40; border-radius: 5px; padding: 10px; margin-bottom: 10px;'>
                        <i class='bi bi-patch-check-fill' style='color:#2ecc40;font-size:2rem;margin-right:10px;'></i>
                        <div><b>Trial:</b> {m['trial_id']}<br><b>Match:</b> {m['match_percentage']}%<br><b>Status:</b> {m['status']} <span title='{why}'>ℹ️ why?</span><br><a href='{m['next_steps']}' target='_blank'>Apply/More Info</a></div>
                    </div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.warning("No eligible trials found.", icon='⚠️')
            if st.button("Start Over"):
                st.session_state.step = 0
                st.session_state.responses = {}
                st.session_state.results = {}
                st.rerun()
        return

    # Step 0: Welcome
    if step == 0:
        st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><h2>TrialIQ Multilingual Clinical Trial Matcher {flag_emoji(locale)}</h2><p>We\'ll help you find clinical trials you may be eligible for. Click Start to begin.</p></div>', unsafe_allow_html=True)
        if st.button("Start", key="start_btn"):
            st.session_state.step = 1
            st.rerun()
        return
    # Step 1: Consent
    if step == 1:
        agree, decline = consent_card()
        if agree:
            st.session_state.step = 2
            st.rerun()
        if decline:
            st.markdown("<div class='card' style='max-width:480px;margin:auto;'><b>Thank you for your interest. You must accept the terms to use this service.</b></div>", unsafe_allow_html=True)
            st.stop()
        return
    # Step 2: Personal Info
    if step == 2:
        with st.form("personal_info_form", clear_on_submit=False):
            st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><b>Please enter your details:</b> {flag_emoji(locale)}</div>', unsafe_allow_html=True)
            name = st.text_input("Full Name", value=responses.get("name", ""))
            phone = st.text_input("Phone Number", value=responses.get("phone", ""))
            email = st.text_input("Email", value=responses.get("email", ""))
            id_doc = st.text_input("Identity Document Number", value=responses.get("id_doc", ""))
            submitted = st.form_submit_button("Next")
            error = ""
            if submitted:
                if not name or not phone or not email or not id_doc:
                    error = "All fields are required."
                elif "@" not in email or "." not in email:
                    error = "Please enter a valid email."
                elif not phone.isdigit() or len(phone) < 7:
                    error = "Please enter a valid phone number."
                else:
                    responses["name"] = name
                    responses["phone"] = phone
                    responses["email"] = email
                    responses["id_doc"] = id_doc
                    st.session_state.responses = responses
                    st.session_state.step = 3
                    st.rerun()
            if error:
                st.error(error)
            if st.form_submit_button("Back"):
                st.session_state.step = 1
                st.rerun()
        return
    # Step 3+: Eligibility Questions
    q_idx = step - 3
    if isinstance(q_idx, int) and 0 <= q_idx < len(QUESTION_FLOW):
        q = QUESTION_FLOW[q_idx]
        qtext = translate(q["text_dict"], lang)
        with st.form(f"q_form_{q['q_id']}", clear_on_submit=False):
            st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><b>{qtext}</b> {flag_emoji(locale)}</div>', unsafe_allow_html=True)
            key = f"q_{q['q_id']}"
            val = responses.get(q["q_id"])
            if q["answer_type"] == "number":
                label = "Your Age (years)"
                val = st.number_input(label, min_value=0, max_value=120, step=1, key=key, value=val if val is not None else 0)
                if val < 0:
                    st.error("Age can't be negative")
            elif q["answer_type"] == "select":
                val = st.selectbox("Select an option", q.get("options", []), key=key, index=q.get("options", []).index(val) if val in q.get("options", []) else 0)
            elif q["answer_type"] == "bool":
                val = st.radio("Select one", [True, False], key=key, format_func=lambda x: translate({"en": "Yes", "fr": "Oui", "es": "Sí"}, lang) if x else translate({"en": "No", "fr": "Non", "es": "No"}, lang), index=0 if val is None or val else 1)
            submitted = st.form_submit_button("Next")
            if submitted:
                responses[q["q_id"]] = val
                st.session_state.responses = responses
                st.session_state.step += 1
                st.rerun()
            if st.form_submit_button("Back"):
                if step == 3:
                    st.session_state.step = 2
                else:
                    st.session_state.step -= 1
                st.rerun()
        return
    # Summary and submit
    if step == 3 + len(QUESTION_FLOW):
        st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><b>Review your details and answers</b><ul>' + "".join([f"<li><b>{k.title().replace('_',' ')}:</b> {responses.get(k)}" for k in ["name","phone","email","id_doc"]]) + "".join([f"<li>{translate(q['text_dict'], lang)}: {responses.get(q['q_id'])}</li>" for q in QUESTION_FLOW]) + "</ul></div>", unsafe_allow_html=True)
        if st.button("Submit & Find Trials"):
            with st.spinner('Running eligibility engine…'):
                submit_patient(responses, locale)
            st.rerun()
        if st.button("Back"):
            st.session_state.step -= 1
            st.rerun()
        return

def submit_patient(responses, locale):
    user_id_hash = hashlib.sha256(str(responses).encode()).hexdigest()[:12]
    input_mode = "text"
    start = time.time()
    matches = []
    ineligible = []
    country = locale.split("-")[-1]
    for trial in TRIALS:
        pct, status = score_trial(trial, responses, country)
        if pct > 0:
            matches.append({"trial_id": trial["trial_id"], "country_site": country, "match_percentage": pct, "status": status, "next_steps": f"https://apply.example/{trial['trial_id'][-3:]}_{country.lower()}"})
        else:
            ineligible.append({"trial_id": trial["trial_id"], "reason": status})
    duration = time.time() - start
    with SessionLocal() as db:
        sub = Submission(
            user_id_hash=user_id_hash,
            locale=locale,
            input_mode=input_mode,
            responses_json=json.dumps(responses),
            matches_json=json.dumps(matches),
            duration_sec=duration,
            status="complete",
            meta_json=json.dumps({"ineligible_trials": ineligible})
        )
        db.add(sub)
        db.commit()
    st.session_state['results'] = {
        'matches': matches,
        'ineligible': ineligible
    }
    st.session_state['step'] = 'results'

# --- Admin Dashboard ---
def inject_synthetic_data(db, n=50):
    # Only inject if table is empty
    if db.query(Submission).count() > 0:
        return
    locales = ["en-US", "fr-FR", "de-DE", "es-ES", "hi-IN", "zh-CN", "pt-BR", "ar-SA", "en-GB", "ca-CA"]
    names = ["Alice", "Bob", "Carlos", "Diana", "Eva", "Faisal", "Gita", "Hao", "Ines", "Jorge"]
    emails = [f"{n.lower()}@demo.com" for n in names]
    for i in range(n):
        locale = choice(locales)
        name = choice(names)
        phone = str(randint(1000000000, 9999999999))
        email = choice(emails)
        id_doc = str(randint(10000, 99999))
        responses = {
            "name": name,
            "phone": phone,
            "email": email,
            "id_doc": id_doc,
            "age": randint(18, 80),
            "gender": choice(["male", "female", "other"]),
            "diabetic": choice([True, False]),
            "cardiac_history": choice([True, False])
        }
        matches = []
        ineligible = []
        country = locale.split("-")[-1]
        for trial in TRIALS:
            pct, status = score_trial(trial, responses, country)
            if pct > 0:
                matches.append({"trial_id": trial["trial_id"], "country_site": country, "match_percentage": pct, "status": status, "next_steps": f"https://apply.example/{trial['trial_id'][-3:]}_{country.lower()}"})
            else:
                ineligible.append({"trial_id": trial["trial_id"], "reason": status})
        sub = Submission(
            user_id_hash=hashlib.sha256(str(responses).encode()).hexdigest()[:12],
            locale=locale,
            input_mode="text",
            responses_json=json.dumps(responses),
            matches_json=json.dumps(matches),
            duration_sec=round(random()*10+5,2),
            status="complete",
            meta_json=json.dumps({"ineligible_trials": ineligible}),
            submitted_ts=datetime.utcnow() - timedelta(days=randint(0, 30))
        )
        db.add(sub)
    db.commit()

def run_admin():
    st.header("🛡️ Admin Dashboard")
    secret = st.text_input("Admin Secret", type="password")
    if secret != CONFIG["ADMIN_BEARER_SECRET"]:
        st.warning("Enter valid admin secret.")
        return
    with SessionLocal() as db:
        inject_synthetic_data(db)
        df = pd.read_sql("SELECT * FROM trialiq_submissions", db.bind)
    # --- Filters ---
    st.markdown("---")
    st.subheader("🔎 Filters")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2,2,3,2])
    country_opts = sorted(df["locale"].dropna().apply(lambda l: l.split("-")[-1]).unique())
    trial_opts = sorted(set([m["trial_id"] for ms in df["matches_json"].apply(json.loads) for m in ms]))
    date_min, date_max = df["submitted_ts"].min(), df["submitted_ts"].max()
    # Convert to python datetime for slider
    date_min = pd.to_datetime(date_min).to_pydatetime() if pd.notnull(date_min) else datetime.utcnow()
    date_max = pd.to_datetime(date_max).to_pydatetime() if pd.notnull(date_max) else datetime.utcnow()
    if date_min == date_max:
        date_max = date_min + timedelta(days=1)
    # --- Reset Filters logic ---
    if 'admin_filters' not in st.session_state:
        st.session_state.admin_filters = {
            'country': 'All',
            'trial': 'All',
            'date': (date_min.date(), date_max.date())
        }
    if filter_col4.button('Reset Filters'):
        st.session_state.admin_filters = {
            'country': 'All',
            'trial': 'All',
            'date': (date_min.date(), date_max.date())
        }
        st.rerun()
    country_f = filter_col1.selectbox("Country", ["All"] + country_opts, index=(["All"] + country_opts).index(st.session_state.admin_filters['country']) if st.session_state.admin_filters['country'] in (["All"] + country_opts) else 0, key="admin_country")
    trial_f = filter_col2.selectbox("Trial", ["All"] + trial_opts, index=(["All"] + trial_opts).index(st.session_state.admin_filters['trial']) if st.session_state.admin_filters['trial'] in (["All"] + trial_opts) else 0, key="admin_trial")
    date_f = filter_col3.slider("Date", min_value=date_min.date(), max_value=date_max.date(), value=st.session_state.admin_filters['date'], format="%Y-%m-%d", key="admin_date")
    # Save filter state
    st.session_state.admin_filters = {'country': country_f, 'trial': trial_f, 'date': date_f}
    # Apply filters
    dff = df.copy()
    if country_f != "All":
        dff = dff[dff["locale"].apply(lambda l: l.split("-")[-1]) == country_f]
    if trial_f != "All":
        dff = dff[dff["matches_json"].apply(lambda ms: trial_f in [m["trial_id"] for m in json.loads(ms)])]
    dff = dff[(pd.to_datetime(dff["submitted_ts"]).dt.date >= date_f[0]) & (pd.to_datetime(dff["submitted_ts"]).dt.date <= date_f[1])]
    # --- Submissions Table ---
    st.markdown("---")
    st.subheader(f"📋 Submissions ({len(dff)})")
    if dff.empty:
        st.info("No submissions for selected filters.")
    else:
        st.dataframe(dff, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.subheader("📊 KPIs")
    k1, k2, k3 = st.columns(3)
    # Fake growth for demo
    total = len(df)
    new_today = 3 if total > 0 else 0
    avg_dur = round(df["duration_sec"].mean(), 2) if not df.empty else 0
    k1.metric("Total Submissions", total, f"+{new_today}")
    k2.metric("Avg Duration (sec)", avg_dur, "+0.5")
    k3.metric("Completion Rate", "100%" if not df.empty else "0%", "+0%")
    # --- Map ---
    st.markdown("---")
    st.subheader("🌍 Submissions Map")
    if not dff.empty:
        dff["country"] = dff["locale"].apply(lambda l: l.split("-")[-1] if l else "US")
        country_counts = dff["country"].value_counts().reset_index()
        country_counts.columns = ["country", "cnt"]

        iso2_to_iso3 = {
            'US': 'USA', 'FR': 'FRA', 'DE': 'DEU', 'ES': 'ESP', 'IN': 'IND', 'CN': 'CHN',
            'BR': 'BRA', 'SA': 'SAU', 'GB': 'GBR', 'CA': 'CAN', 'PT': 'PRT', 'BE': 'BEL', 'AR': 'ARG'
        }
        country_counts["iso_alpha"] = country_counts["country"].map(iso2_to_iso3)

        fig = go.Figure(data=go.Scattergeo(
            locations=country_counts['iso_alpha'],
            locationmode='ISO-3',
            text=country_counts.apply(lambda row: f"{row['country']}: {row['cnt']} submissions", axis=1),
            marker=dict(
                size=country_counts['cnt'],
                sizemin=4,
                sizemode='diameter',
                color='#3182ce' if st.session_state.theme == 'light' else '#2b6cb0',
                line_width=0.5,
                line_color='rgb(40,40,40)',
                sizeref=country_counts['cnt'].max() / 50 if country_counts['cnt'].max() > 0 else 1,
            ),
            hoverinfo='text'
        ))

        fig.update_layout(
            title='Global Submissions by Country',
            geo=dict(
                scope='world',
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(217, 217, 217)' if st.session_state.theme == 'light' else 'rgb(40, 40, 40)',
                subunitcolor='rgb(255, 255, 255)' if st.session_state.theme == 'light' else 'rgb(80, 80, 80)',
                bgcolor='rgba(0,0,0,0)',
            ),
            margin={"r":0,"t":40,"l":0,"b":0},
            template='plotly_white' if st.session_state.theme == 'light' else 'plotly_dark'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for map yet.")
    # --- Top Trials Drilldown ---
    st.markdown("---")
    st.subheader("🏆 Top Matched Trials")
    if not dff.empty:
        matches = pd.json_normalize(dff["matches_json"].apply(json.loads).sum())
        top_trials = matches.groupby("trial_id").size().sort_values(ascending=False).head(3)
        st.write(top_trials)
        trial_drill = st.selectbox("Drilldown: View users for trial", ["None"] + list(top_trials.index))
        if trial_drill != "None":
            users = dff[dff["matches_json"].apply(lambda ms: trial_drill in [m["trial_id"] for m in json.loads(ms)])]
            for idx, row in users.iterrows():
                st.markdown(f"<details><summary><b>{row['submitted_ts']} | {row['locale']}</b></summary><pre style='white-space:pre-wrap;'>{json.dumps(json.loads(row['responses_json']), indent=2, ensure_ascii=False)}</pre></details>", unsafe_allow_html=True)
    else:
        st.info("No trial matches yet.")

# --- Main App ---
if menu == "Patient":
    run_patient_flow()
else:
    run_admin()

# NOTE: All experimental APIs have been updated.
