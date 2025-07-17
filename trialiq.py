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
    "SUPPORTED_LANGS": ["en", "es", "fr", "de", "hi", "zh", "pt"],
    "LOCALE_UNIT": {
        "en-US": {"weight": "lb", "temperature": "°F"},
        "en-GB": {"weight": "kg", "temperature": "°C"},
        "fr-FR": {"weight": "kg", "temperature": "°C"},
        "de-DE": {"weight": "kg", "temperature": "°C"},
        "es-ES": {"weight": "kg", "temperature": "°C"},
        "hi-IN": {"weight": "kg", "temperature": "°C"},
        "zh-CN": {"weight": "kg", "temperature": "°C"},
        "pt-BR": {"weight": "kg", "temperature": "°C"},
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

# --- UI Text & Translations ---
UI_TEXT = {
    "app_title": {"en": "TrialIQ Multilingual Clinical Trial Matcher", "es": "TrialIQ Buscador Multilingüe de Ensayos Clínicos", "fr": "TrialIQ Chercheur Multilingue d'Essais Cliniques", "de": "TrialIQ Mehrsprachiger klinischer Studien-Matcher", "hi": "ट्रायलआईक्यू बहुभाषी क्लिनिकल परीक्षण मैचर", "zh": "TrialIQ 多语言临床试验匹配器", "pt": "TrialIQ Localizador Multilíngue de Ensaios Clínicos"},
    "welcome_subtitle": {"en": "We'll help you find clinical trials you may be eligible for. Click Start to begin.", "es": "Le ayudaremos a encontrar ensayos clínicos para los que pueda ser elegible. Haga clic en Iniciar para comenzar.", "fr": "Nous vous aiderons à trouver des essais cliniques pour lesquels vous pourriez être éligible. Cliquez sur Démarrer pour commencer.", "de": "Wir helfen Ihnen, klinische Studien zu finden, für die Sie möglicherweise in Frage kommen. Klicken Sie auf Start, um zu beginnen.", "hi": "हम आपको उन क्लिनिकल परीक्षणों को खोजने में मदद करेंगे जिनके लिए आप पात्र हो सकते हैं। शुरू करने के लिए स्टार्ट पर क्लिक करें।", "zh": "我们将帮助您找到您可能有资格参加的临床试验。点击“开始”以开始。", "pt": "Vamos ajudá-lo a encontrar ensaios clínicos para os quais você pode ser elegível. Clique em Iniciar para começar."},
    "start_button": {"en": "Start", "es": "Iniciar", "fr": "Démarrer", "de": "Start", "hi": "शुरू करें", "zh": "开始", "pt": "Iniciar"},
    "next_button": {"en": "Next", "es": "Siguiente", "fr": "Suivant", "de": "Weiter", "hi": "अगला", "zh": "下一步", "pt": "Próximo"},
    "back_button": {"en": "Back", "es": "Atrás", "fr": "Retour", "de": "Zurück", "hi": "वापस", "zh": "返回", "pt": "Voltar"},
    "submit_button": {"en": "Submit & Find Trials", "es": "Enviar y Buscar Ensayos", "fr": "Soumettre et Trouver des Essais", "de": "Senden & Studien finden", "hi": "सबमिट करें और परीक्षण खोजें", "zh": "提交并查找试验", "pt": "Enviar e Encontrar Ensaios"},
    "consent_title": {"en": "Terms & Data Consent", "es": "Términos y Consentimiento de Datos", "fr": "Conditions et Consentement des Données", "de": "Bedingungen & Datenzustimmung", "hi": "शर्तें और डेटा सहमति", "zh": "条款和数据同意", "pt": "Termos e Consentimento de Dados"},
    "consent_item1": {"en": "Your answers will be stored securely and used only to match you to clinical trials.", "es": "Sus respuestas se almacenarán de forma segura y se usarán solo para encontrarle ensayos clínicos.", "fr": "Vos réponses seront stockées en toute sécurité et utilisées uniquement pour vous trouver des essais cliniques.", "de": "Ihre Antworten werden sicher gespeichert und nur dazu verwendet, Sie mit klinischen Studien abzugleichen.", "hi": "आपके उत्तर सुरक्षित रूप से संग्रहीत किए जाएंगे और केवल आपको क्लिनिकल परीक्षणों से मिलाने के लिए उपयोग किए जाएंगे।", "zh": "您的答案将被安全存储，并且仅用于将您与临床试验相匹配。", "pt": "Suas respostas serão armazenadas com segurança e usadas apenas para combiná-lo com ensaios clínicos."},
    "consent_item2": {"en": "No personally identifiable information will be shared with third parties.", "es": "No se compartirá información de identificación personal con terceros.", "fr": "Aucune information personnellement identifiable ne sera partagée avec des tiers.", "de": "Es werden keine personenbezogenen Daten an Dritte weitergegeben.", "hi": "कोई भी व्यक्तिगत रूप से पहचानी जाने वाली जानकारी तीसरे पक्ष के साथ साझा नहीं की जाएगी।", "zh": "任何个人身份信息都不会与第三方共享。", "pt": "Nenhuma informação de identificação pessoal será compartilhada com terceiros."},
    "consent_item3": {"en": "You can request data deletion at any time.", "es": "Puede solicitar la eliminación de sus datos en cualquier momento.", "fr": "Vous pouvez demander la suppression de vos données à tout moment.", "de": "Sie können jederzeit die Löschung Ihrer Daten verlangen.", "hi": "आप किसी भी समय डेटा हटाने का अनुरोध कर सकते हैं।", "zh": "您可以随时请求删除数据。", "pt": "Você pode solicitar a exclusão dos dados a qualquer momento."},
    "agree_button": {"en": "Agree & Continue", "es": "Aceptar y Continuar", "fr": "Accepter et Continuer", "de": "Zustimmen & Fortfahren", "hi": "सहमत हैं और जारी रखें", "zh": "同意并继续", "pt": "Concordar e Continuar"},
    "decline_button": {"en": "Decline", "es": "Rechazar", "fr": "Refuser", "de": "Ablehnen", "hi": "अस्वीकार", "zh": "拒绝", "pt": "Recusar"},
    "decline_message": {"en": "Thank you for your interest. You must accept the terms to use this service.", "es": "Gracias por su interés. Debe aceptar los términos para usar este servicio.", "fr": "Merci de votre intérêt. Vous devez accepter les conditions pour utiliser ce service.", "de": "Danke für Ihr Interesse. Sie müssen die Bedingungen akzeptieren, um diesen Dienst zu nutzen.", "hi": "आपकी रुचि के लिए धन्यवाद। इस सेवा का उपयोग करने के लिए आपको शर्तों को स्वीकार करना होगा।", "zh": "感谢您的关注。您必须接受条款才能使用此服务。", "pt": "Obrigado pelo seu interesse. Você deve aceitar os termos para usar este serviço."},
    "personal_info_title": {"en": "Please enter your details:", "es": "Por favor, ingrese sus detalles:", "fr": "Veuillez saisir vos coordonnées:", "de": "Bitte geben Sie Ihre Daten ein:", "hi": "कृपया अपना विवरण दर्ज करें:", "zh": "请输入您的详细信息：", "pt": "Por favor, insira seus detalhes:"},
    "name_label": {"en": "Full Name", "es": "Nombre Completo", "fr": "Nom Complet", "de": "Vollständiger Name", "hi": "पूरा नाम", "zh": "全名", "pt": "Nome Completo"},
    "phone_label": {"en": "Phone Number", "es": "Número de Teléfono", "fr": "Numéro de Téléphone", "de": "Telefonnummer", "hi": "फ़ोन नंबर", "zh": "电话号码", "pt": "Número de Telefone"},
    "email_label": {"en": "Email", "es": "Correo Electrónico", "fr": "Email", "de": "Email", "hi": "ईमेल", "zh": "电子邮件", "pt": "Email"},
    "id_doc_label": {"en": "Identity Document Number", "es": "Número de Documento de Identidad", "fr": "Numéro du Document d'Identité", "de": "Ausweisnummer", "hi": "पहचान दस्तावेज़ संख्या", "zh": "身份证件号码", "pt": "Número do Documento de Identidade"},
    "summary_title": {"en": "Review your details and answers", "es": "Revise sus detalles y respuestas", "fr": "Vérifiez vos coordonnées et vos réponses", "de": "Überprüfen Sie Ihre Angaben und Antworten", "hi": "अपने विवरण और उत्तरों की समीक्षा करें", "zh": "请核对您的详细信息和答案", "pt": "Revise seus detalhes e respostas"},
    "matched_trials_title": {"en": "Matched Trials", "es": "Ensayos Compatibles", "fr": "Essais Correspondants", "de": "Passende Studien", "hi": "मिलान किए गए परीक्षण", "zh": "匹配的试验", "pt": "Ensaios Correspondentes"},
    "no_trials_found": {"en": "No eligible trials found.", "es": "No se encontraron ensayos elegibles.", "fr": "Aucun essai éligible trouvé.", "de": "Keine passenden Studien gefunden.", "hi": "कोई योग्य परीक्षण नहीं मिला।", "zh": "未找到符合条件的试验。", "pt": "Nenhum ensaio elegível encontrado."},
    "start_over_button": {"en": "Start Over", "es": "Empezar de Nuevo", "fr": "Recommencer", "de": "Von vorne anfangen", "hi": "फिर से शुरू करें", "zh": "重新开始", "pt": "Começar de Novo"},
    "results_trial_label": {"en": "Trial", "es": "Ensayo", "fr": "Essai", "de": "Studie", "hi": "परीक्षण", "zh": "试验", "pt": "Ensaio"},
    "results_match_label": {"en": "Match", "es": "Coincidencia", "fr": "Correspondance", "de": "Übereinstimmung", "hi": "मिलान", "zh": "匹配度", "pt": "Correspondência"},
    "results_status_label": {"en": "Status", "es": "Estado", "fr": "Statut", "de": "Status", "hi": "स्थिति", "zh": "状态", "pt": "Status"},
    "results_next_steps_label": {"en": "Apply/More Info", "es": "Aplicar/Más Info", "fr": "Postuler/Plus d'Infos", "de": "Bewerben/Mehr Infos", "hi": "आवेदन करें/अधिक जानकारी", "zh": "申请/更多信息", "pt": "Aplicar/Mais Informações"},
    "error_all_fields_required": {"en": "All fields are required.", "es": "Todos los campos son obligatorios.", "fr": "Tous les champs sont requis.", "de": "Alle Felder sind erforderlich.", "hi": "सभी फ़ील्ड आवश्यक हैं।", "zh": "所有字段均为必填项。", "pt": "Todos os campos são obrigatórios."},
    "error_invalid_email": {"en": "Please enter a valid email.", "es": "Por favor, ingrese un correo electrónico válido.", "fr": "Veuillez entrer un email valide.", "de": "Bitte geben Sie eine gültige E-Mail-Adresse ein.", "hi": "कृपया एक वैध ईमेल दर्ज करें।", "zh": "请输入有效的电子邮件。", "pt": "Por favor, insira um email válido."},
    "error_invalid_phone": {"en": "Please enter a valid phone number.", "es": "Por favor, ingrese un número de teléfono válido.", "fr": "Veuillez entrer un numéro de téléphone valide.", "de": "Bitte geben Sie eine gültige Telefonnummer ein.", "hi": "कृपया एक वैध फ़ोन नंबर दर्ज करें।", "zh": "请输入有效的电话号码。", "pt": "Por favor, insira um número de telefone válido."},
    "age_label": {"en": "Your Age (years)", "es": "Su Edad (años)", "fr": "Votre Âge (ans)", "de": "Ihr Alter (Jahre)", "hi": "आपकी उम्र (वर्ष)", "zh": "您的年龄（岁）", "pt": "Sua Idade (anos)"},
    "age_error_negative": {"en": "Age can't be negative", "es": "La edad no puede ser negativa", "fr": "L'âge ne peut pas être négatif", "de": "Das Alter kann nicht negativ sein", "hi": "उम्र नकारात्मक नहीं हो सकती", "zh": "年龄不能为负数", "pt": "A idade não pode ser negativa"},
    "select_option_label": {"en": "Select an option", "es": "Seleccione una opción", "fr": "Sélectionnez une option", "de": "Wählen Sie eine Option", "hi": "एक विकल्प चुनें", "zh": "请选择一个选项", "pt": "Selecione uma opção"},
    "radio_yes": {"en": "Yes", "es": "Sí", "fr": "Oui", "de": "Ja", "hi": "हाँ", "zh": "是", "pt": "Sim"},
    "radio_no": {"en": "No", "es": "No", "fr": "Non", "de": "Nein", "hi": "नहीं", "zh": "否", "pt": "Não"},
    "results_why_tooltip": {"en": "Why?", "es": "¿Por qué?", "fr": "Pourquoi?", "de": "Warum?", "hi": "क्यों?", "zh": "为什么？", "pt": "Por quê?"},
    "results_met_age_req": {"en": "Met age requirement", "es": "Cumplió el requisito de edad", "fr": "A satisfait à l'exigence d'âge", "de": "Altersanforderung erfüllt", "hi": "आयु की आवश्यकता पूरी की", "zh": "符合年龄要求", "pt": "Cumpriu o requisito de idade"},
    "radio_select_one": {"en": "Select one", "es": "Seleccione uno", "fr": "Sélectionnez-en un", "de": "Wählen Sie eins aus", "hi": "एक का चयन करें", "zh": "请选择一个", "pt": "Selecione um"},
    "spinner_eligibility": {"en": "Running eligibility engine…", "es": "Ejecutando motor de elegibilidad…", "fr": "Exécution du moteur d'éligibilité…", "de": "Eignungs-Engine wird ausgeführt…", "hi": "पात्रता इंजन चल रहा है...", "zh": "正在运行资格引擎...", "pt": "Executando o mecanismo de elegibilidade…"},
    "not_applicable": {"en": "N/A", "es": "N/D", "fr": "N/A", "de": "N/A", "hi": "लागू नहीं", "zh": "不适用", "pt": "N/A"},
    "admin_dashboard_title": {"en": "🛡️ Admin Dashboard", "es": "🛡️ Panel de Administración", "fr": "🛡️ Tableau de Bord Admin", "de": "🛡️ Admin-Dashboard", "hi": "🛡️ एडमिन डैशबोर्ड", "zh": "🛡️ 管理员仪表板", "pt": "🛡️ Painel do Administrador"},
    "admin_secret_label": {"en": "Admin Secret", "es": "Secreto de Administrador", "fr": "Secret Admin", "de": "Admin-Geheimnis", "hi": "एडमिन सीक्रेट", "zh": "管理员密钥", "pt": "Segredo do Administrador"},
    "admin_secret_warning": {"en": "Enter valid admin secret.", "es": "Ingrese un secreto de administrador válido.", "fr": "Veuillez saisir un secret admin valide.", "de": "Geben Sie ein gültiges Admin-Geheimnis ein.", "hi": "वैध एडमिन सीक्रेट दर्ज करें।", "zh": "请输入有效的管理员密钥。", "pt": "Insira um segredo de administrador válido."},
    "admin_filters_title": {"en": "🔎 Filters", "es": "🔎 Filtros", "fr": "🔎 Filtres", "de": "🔎 Filter", "hi": "🔎 फिल्टर", "zh": "🔎 筛选器", "pt": "🔎 Filtros"},
    "admin_reset_filters_button": {"en": "Reset Filters", "es": "Restablecer Filtros", "fr": "Réinitialiser les Filtres", "de": "Filter zurücksetzen", "hi": "फ़िल्टर रीसेट करें", "zh": "重置筛选器", "pt": "Redefinir Filtros"},
    "admin_country_filter_label": {"en": "Country", "es": "País", "fr": "Pays", "de": "Land", "hi": "देश", "zh": "国家", "pt": "País"},
    "admin_trial_filter_label": {"en": "Trial", "es": "Ensayo", "fr": "Essai", "de": "Studie", "hi": "परीक्षण", "zh": "试验", "pt": "Ensaio"},
    "admin_date_filter_label": {"en": "Date", "es": "Fecha", "fr": "Date", "de": "Datum", "hi": "तारीख", "zh": "日期", "pt": "Data"},
    "admin_submissions_title": {"en": "📋 Submissions", "es": "📋 Envíos", "fr": "📋 Soumissions", "de": "📋 Einreichungen", "hi": "📋 प्रस्तुतियाँ", "zh": "📋 提交记录", "pt": "📋 Submissões"},
    "admin_no_submissions_message": {"en": "No submissions for selected filters.", "es": "No hay envíos para los filtros seleccionados.", "fr": "Aucune soumission pour les filtres sélectionnés.", "de": "Keine Einreichungen für die ausgewählten Filter.", "hi": "चयनित फिल्टर के लिए कोई सबमिशन नहीं है।", "zh": "没有符合所选筛选条件的提交记录。", "pt": "Nenhuma submissão para os filtros selecionados."},
    "admin_kpis_title": {"en": "📊 KPIs", "es": "📊 KPIs", "fr": "📊 Indicateurs Clés", "de": "📊 KPIs", "hi": "📊 KPIs", "zh": "📊 关键绩效指标", "pt": "📊 KPIs"},
    "admin_kpi_total_submissions": {"en": "Total Submissions", "es": "Envíos Totales", "fr": "Soumissions Totales", "de": "Einreichungen Gesamt", "hi": "कुल प्रस्तुतियाँ", "zh": "总提交数", "pt": "Total de Submissões"},
    "admin_kpi_avg_duration": {"en": "Avg Duration (sec)", "es": "Duración Promedio (seg)", "fr": "Durée Moyenne (sec)", "de": "Ø Dauer (sek)", "hi": "औसत अवधि (सेकंड)", "zh": "平均持续时间（秒）", "pt": "Duração Média (seg)"},
    "admin_kpi_completion_rate": {"en": "Completion Rate", "es": "Tasa de Finalización", "fr": "Taux de Complétion", "de": "Abschlussrate", "hi": "पूर्णता दर", "zh": "完成率", "pt": "Taxa de Conclusão"},
    "admin_map_title": {"en": "🌍 Submissions Map", "es": "🌍 Mapa de Envíos", "fr": "🌍 Carte des Soumissions", "de": "🌍 Karte der Einreichungen", "hi": "🌍 सबमिशन का नक्शा", "zh": "🌍 提交地图", "pt": "🌍 Mapa de Submissões"},
    "admin_map_plot_title": {"en": "Global Submissions by Country", "es": "Envíos Globales por País", "fr": "Soumissions Mondiales par Pays", "de": "Globale Einreichungen nach Land", "hi": "देश के अनुसार वैश्विक प्रस्तुतियाँ", "zh": "按国家/地区划分的全球提交记录", "pt": "Submissões Globais por País"},
    "admin_map_hover_text": {"en": "submissions", "es": "envíos", "fr": "soumissions", "de": "einreichungen", "hi": "प्रस्तुतियाँ", "zh": "提交", "pt": "submissões"},
    "admin_map_no_data_message": {"en": "No data for map yet.", "es": "Aún no hay datos para el mapa.", "fr": "Pas encore de données pour la carte.", "de": "Noch keine Daten für die Karte.", "hi": "मानचित्र के लिए अभी तक कोई डेटा नहीं है।", "zh": "尚无地图数据。", "pt": "Ainda não há dados para o mapa."},
    "admin_top_trials_title": {"en": "🏆 Top Matched Trials", "es": "🏆 Principales Ensayos Compatibles", "fr": "🏆 Essais les Mieux Correspondants", "de": "🏆 Top-passende Studien", "hi": "🏆 शीर्ष मिलान वाले परीक्षण", "zh": "🏆 匹配度最高的试验", "pt": "🏆 Principais Ensaios Correspondentes"},
    "admin_top_trials_drilldown_label": {"en": "Drilldown: View users for trial", "es": "Detalle: Ver usuarios por ensayo", "fr": "Détail : Voir les utilisateurs par essai", "de": "Drilldown: Benutzer für Studie anzeigen", "hi": "ड्रिलडाउन: परीक्षण के लिए उपयोगकर्ता देखें", "zh": "深入分析：查看试验的用户", "pt": "Detalhar: Ver usuários por ensaio"},
    "admin_top_trials_no_matches_message": {"en": "No trial matches yet.", "es": "Aún no hay ensayos compatibles.", "fr": "Aucune correspondance d'essai pour le moment.", "de": "Noch keine Studienübereinstimmungen.", "hi": "अभी तक कोई परीक्षण मिलान नहीं हुआ है।", "zh": "尚无试验匹配。", "pt": "Ainda não há correspondências de ensaios."},
}

# --- Helpers (order: get_locale, translate, etc.) ---
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
    {
        "trial_id": "NCT01007279", 
        "country_list": ["FR", "BE", "DE"], 
        "criteria": {"age_min": 50, "diabetic": False, "cardiac_history": True},
        "description_dict": {
            "en": "A study on the effects of a new drug for cardiac patients over 50.",
            "es": "Un estudio sobre los efectos de un nuevo fármaco para pacientes cardíacos mayores de 50 años.",
            "fr": "Une étude sur les effets d'un nouveau médicament pour les patients cardiaques de plus de 50 ans.",
            "de": "Eine Studie über die Auswirkungen eines neuen Medikaments für Herzpatienten über 50.",
            "hi": "50 से अधिक उम्र के हृदय रोगियों के लिए एक नई दवा के प्रभावों पर एक अध्ययन।",
            "zh": "一项关于一种新药对50岁以上心脏病患者影响的研究。",
            "pt": "Um estudo sobre os efeitos de um novo medicamento para pacientes cardíacos com mais de 50 anos."
        }
    },
    {
        "trial_id": "NCT02592421", 
        "country_list": ["US", "CA"], 
        "criteria": {"age_min": 18, "diabetic": False},
        "description_dict": {
            "en": "General wellness study for non-diabetic adults.",
            "es": "Estudio de bienestar general para adultos no diabéticos.",
            "fr": "Étude sur le bien-être général des adultes non diabétiques.",
            "de": "Allgemeine Wellness-Studie für nicht-diabetische Erwachsene.",
            "hi": "गैर-मधुमेह वयस्कों के लिए सामान्य कल्याण अध्ययन।",
            "zh": "针对非糖尿病成年人的一般健康研究。",
            "pt": "Estudo de bem-estar geral para adultos não diabéticos."
        }
    },
    {
        "trial_id": "NCT99999999", 
        "country_list": "global", 
        "criteria": {"age_min": 21},
        "description_dict": {
            "en": "A global study open to all adults aged 21 and over.",
            "es": "Un estudio global abierto a todos los adultos mayores de 21 años.",
            "fr": "Une étude mondiale ouverte à tous les adultes de 21 ans et plus.",
            "de": "Eine globale Studie, die allen Erwachsenen ab 21 Jahren offensteht.",
            "hi": "21 वर्ष और उससे अधिक आयु के सभी वयस्कों के लिए एक वैश्विक अध्ययन।",
            "zh": "一项面向所有21岁及以上成年人的全球性研究。",
            "pt": "Um estudo global aberto a todos os adultos com 21 anos ou mais."
        }
    },
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
# Force dark theme, remove theme switcher
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
st.session_state.theme = "dark"
st.query_params["theme"] = "dark"

if "lang" not in st.session_state:
    st.session_state.lang = CONFIG["DEFAULT_LOCALE"].split("-")[0]

lang_names = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch", "hi": "हिन्दी", "zh": "中文", "pt": "Português"}
# Limit languages to 7
supported_langs = ["en", "es", "fr", "de", "hi", "zh", "pt"]
lang = st.sidebar.selectbox("Language", supported_langs, format_func=lambda l: f"{lang_names.get(l, l)}", index=supported_langs.index(st.session_state.get("lang", detect_locale().split("-")[0])), key="lang_select")
if lang != st.session_state.get("lang"):
    st.session_state.lang = lang
    st.session_state.browser_lang = f"{lang}-{detect_locale().split('-')[-1]}"
    st.rerun()

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
def consent_card(lang):
    card = f"""
    <div class="card" style="max-width:480px;margin:auto;">
    <h3>{translate(UI_TEXT['consent_title'], lang)}</h3>
    <ul>
      <li>{translate(UI_TEXT['consent_item1'], lang)}</li>
      <li>{translate(UI_TEXT['consent_item2'], lang)}</li>
      <li>{translate(UI_TEXT['consent_item3'], lang)}</li>
    </ul>
    </div>
    """
    st.markdown(card, unsafe_allow_html=True)
    col1, col2 = st.columns([2,1])
    agree = col1.button(translate(UI_TEXT['agree_button'], lang), key="agree_btn")
    decline = col2.button(translate(UI_TEXT['decline_button'], lang), key="decline_btn")
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
    st.title(translate(UI_TEXT['app_title'], lang))
    show_progress()

    # Results page (check first to avoid TypeError on rerun)
    if step == 'results':
        if 'results' in st.session_state:
            results = st.session_state['results']
            st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><b>{translate(UI_TEXT["matched_trials_title"], lang)}</b></div>', unsafe_allow_html=True)
            if results.get('matches'):
                for m in results['matches']:
                    why_text = translate(UI_TEXT['results_why_tooltip'], lang)
                    age_req_text = translate(UI_TEXT['results_met_age_req'], lang)
                    why = f"{age_req_text} ≥" + str([t['criteria']['age_min'] for t in TRIALS if t['trial_id']==m['trial_id']][0]) if m['status']=="eligible" else ""
                    
                    # Find trial details to get the description
                    trial_details = next((t for t in TRIALS if t['trial_id'] == m['trial_id']), None)
                    description = ""
                    if trial_details:
                        description = translate(trial_details.get('description_dict', {}), lang)

                    card_html = f"""
                    <div style='border: 1px solid #2ecc40; border-radius: 5px; padding: 10px; margin-bottom: 10px;'>
                        <div style='display:flex;align-items:center;margin-bottom:8px;'>
                            <i class='bi bi-patch-check-fill' style='color:#2ecc40;font-size:1.5rem;margin-right:10px;'></i>
                            <b style='font-size:1.1rem;'>{translate(UI_TEXT['results_trial_label'], lang)}: {m['trial_id']}</b>
                        </div>
                        <p style='margin: 5px 0; font-style:italic;'>{description}</p>
                        <p style='margin: 5px 0;'>
                            <b>{translate(UI_TEXT['results_match_label'], lang)}:</b> {m['match_percentage']}% | 
                            <b>{translate(UI_TEXT['results_status_label'], lang)}:</b> {m['status']} <span title='{why}'>ℹ️ {why_text}</span>
                        </p>
                        <a href='{m['next_steps']}' target='_blank'>{translate(UI_TEXT['results_next_steps_label'], lang)}</a>
                    </div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.warning(translate(UI_TEXT['no_trials_found'], lang), icon='⚠️')
            if st.button(translate(UI_TEXT['start_over_button'], lang)):
                st.session_state.step = 0
                st.session_state.responses = {}
                st.session_state.results = {}
                st.rerun()
        return

    # Step 0: Welcome
    if step == 0:
        st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><h2>{translate(UI_TEXT["app_title"], lang)}</h2><p>{translate(UI_TEXT["welcome_subtitle"], lang)}</p></div>', unsafe_allow_html=True)
        if st.button(translate(UI_TEXT['start_button'], lang), key="start_btn"):
            st.session_state.step = 1
            st.rerun()
        return
    # Step 1: Consent
    if step == 1:
        agree, decline = consent_card(lang)
        if agree:
            st.session_state.step = 2
            st.rerun()
        if decline:
            st.markdown(f"<div class='card' style='max-width:480px;margin:auto;'><b>{translate(UI_TEXT['decline_message'], lang)}</b></div>", unsafe_allow_html=True)
            st.stop()
        return
    # Step 2: Personal Info
    if step == 2:
        with st.form("personal_info_form", clear_on_submit=False):
            st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><h3>{translate(UI_TEXT["personal_info_title"], lang)}</h3></div>', unsafe_allow_html=True)
            name = st.text_input(translate(UI_TEXT['name_label'], lang), value=responses.get("name", ""))
            phone = st.text_input(translate(UI_TEXT['phone_label'], lang), value=responses.get("phone", ""))
            email = st.text_input(translate(UI_TEXT['email_label'], lang), value=responses.get("email", ""))
            id_doc = st.text_input(translate(UI_TEXT['id_doc_label'], lang), value=responses.get("id_doc", ""))
            submitted = st.form_submit_button(translate(UI_TEXT['next_button'], lang))
            error = ""
            if submitted:
                if not name or not phone or not email or not id_doc:
                    error = translate(UI_TEXT['error_all_fields_required'], lang)
                elif "@" not in email or "." not in email:
                    error = translate(UI_TEXT['error_invalid_email'], lang)
                elif not phone.isdigit() or len(phone) < 7:
                    error = translate(UI_TEXT['error_invalid_phone'], lang)
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
            if st.form_submit_button(translate(UI_TEXT['back_button'], lang)):
                st.session_state.step = 1
                st.rerun()
        return
    # Step 3+: Eligibility Questions
    q_idx = step - 3
    if isinstance(q_idx, int) and 0 <= q_idx < len(QUESTION_FLOW):
        q = QUESTION_FLOW[q_idx]
        qtext = translate(q["text_dict"], lang)
        with st.form(f"q_form_{q['q_id']}", clear_on_submit=False):
            st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><b>{qtext}</b></div>', unsafe_allow_html=True)
            key = f"q_{q['q_id']}"
            val = responses.get(q["q_id"])
            if q["answer_type"] == "number":
                label = translate(UI_TEXT['age_label'], lang)
                val = st.number_input(label, min_value=0, max_value=120, step=1, key=key, value=val if val is not None else 0)
                if val < 0:
                    st.error(translate(UI_TEXT['age_error_negative'], lang))
            elif q["answer_type"] == "select":
                val = st.selectbox(translate(UI_TEXT['select_option_label'], lang), q.get("options", []), key=key, index=q.get("options", []).index(val) if val in q.get("options", []) else 0)
            elif q["answer_type"] == "bool":
                val = st.radio(translate(UI_TEXT['radio_select_one'], lang), [True, False], key=key, format_func=lambda x: translate(UI_TEXT['radio_yes'], lang) if x else translate(UI_TEXT['radio_no'], lang), index=0 if val is None or val else 1)
            submitted = st.form_submit_button(translate(UI_TEXT['next_button'], lang))
            if submitted:
                responses[q["q_id"]] = val
                st.session_state.responses = responses
                st.session_state.step += 1
                st.rerun()
            if st.form_submit_button(translate(UI_TEXT['back_button'], lang)):
                if step == 3:
                    st.session_state.step = 2
                else:
                    st.session_state.step -= 1
                st.rerun()
        return
    # Summary and submit
    if step == 3 + len(QUESTION_FLOW):
        st.markdown(f'<div class="card" style="max-width:480px;margin:auto;"><h3>{translate(UI_TEXT["summary_title"], lang)}</h3></div>', unsafe_allow_html=True)
        # Display personal info
        for key in ["name", "phone", "email", "id_doc"]:
            label = translate(UI_TEXT[f'{key}_label'], lang)
            st.write(f"**{label}**: {responses.get(key, translate(UI_TEXT['not_applicable'], lang))}")
        # Display question answers
        for q in QUESTION_FLOW:
            q_text = translate(q['text_dict'], lang)
            st.write(f"**{q_text}**: {responses.get(q['q_id'], translate(UI_TEXT['not_applicable'], lang))}")
        
        col1, col2 = st.columns(2)
        if col1.button(translate(UI_TEXT['submit_button'], lang)):
            with st.spinner(translate(UI_TEXT['spinner_eligibility'], lang)):
                submit_patient(responses, locale)
            st.rerun()
        if col2.button(translate(UI_TEXT['back_button'], lang)):
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

def run_admin(lang):
    st.header(translate(UI_TEXT['admin_dashboard_title'], lang))
    secret = st.text_input(translate(UI_TEXT['admin_secret_label'], lang), type="password")
    if secret != CONFIG["ADMIN_BEARER_SECRET"]:
        st.warning(translate(UI_TEXT['admin_secret_warning'], lang))
        return
    with SessionLocal() as db:
        inject_synthetic_data(db)
        df = pd.read_sql("SELECT * FROM trialiq_submissions", db.bind)
    # --- Filters ---
    st.markdown("---")
    st.subheader(translate(UI_TEXT['admin_filters_title'], lang))
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
    if filter_col4.button(translate(UI_TEXT['admin_reset_filters_button'], lang)):
        st.session_state.admin_filters = {
            'country': 'All',
            'trial': 'All',
            'date': (date_min.date(), date_max.date())
        }
        st.rerun()
    country_f = filter_col1.selectbox(translate(UI_TEXT['admin_country_filter_label'], lang), ["All"] + country_opts, index=(["All"] + country_opts).index(st.session_state.admin_filters['country']) if st.session_state.admin_filters['country'] in (["All"] + country_opts) else 0, key="admin_country")
    trial_f = filter_col2.selectbox(translate(UI_TEXT['admin_trial_filter_label'], lang), ["All"] + trial_opts, index=(["All"] + trial_opts).index(st.session_state.admin_filters['trial']) if st.session_state.admin_filters['trial'] in (["All"] + trial_opts) else 0, key="admin_trial")
    date_f = filter_col3.slider(translate(UI_TEXT['admin_date_filter_label'], lang), min_value=date_min.date(), max_value=date_max.date(), value=st.session_state.admin_filters['date'], format="YYYY-MM-DD", key="admin_date")
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
    st.subheader(f"{translate(UI_TEXT['admin_submissions_title'], lang)} ({len(dff)})")
    if dff.empty:
        st.info(translate(UI_TEXT['admin_no_submissions_message'], lang))
    else:
        st.dataframe(dff, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.subheader(translate(UI_TEXT['admin_kpis_title'], lang))
    k1, k2, k3 = st.columns(3)
    # Fake growth for demo
    total = len(df)
    new_today = 3 if total > 0 else 0
    avg_dur = round(df["duration_sec"].mean(), 2) if not df.empty else 0
    k1.metric(translate(UI_TEXT['admin_kpi_total_submissions'], lang), total, f"+{new_today}")
    k2.metric(translate(UI_TEXT['admin_kpi_avg_duration'], lang), avg_dur, "+0.5")
    k3.metric(translate(UI_TEXT['admin_kpi_completion_rate'], lang), "100%" if not df.empty else "0%", "+0%")
    # --- Map ---
    st.markdown("---")
    st.subheader(translate(UI_TEXT['admin_map_title'], lang))
    if not dff.empty:
        dff["country"] = dff["locale"].apply(lambda l: l.split("-")[-1] if l else "US")
        country_counts = dff["country"].value_counts().reset_index()
        country_counts.columns = ["country", "cnt"]

        iso2_to_iso3 = {
            'US': 'USA', 'FR': 'FRA', 'DE': 'DEU', 'ES': 'ESP', 'IN': 'IND', 'CN': 'CHN',
            'BR': 'BRA', 'SA': 'SAU', 'GB': 'GBR', 'CA': 'CAN', 'PT': 'PRT', 'BE': 'BEL', 'AR': 'ARG'
        }
        country_counts["iso_alpha"] = country_counts["country"].map(iso2_to_iso3)
        hover_text = translate(UI_TEXT['admin_map_hover_text'], lang)
        fig = go.Figure(data=go.Scattergeo(
            locations=country_counts['iso_alpha'],
            locationmode='ISO-3',
            text=country_counts.apply(lambda row: f"{row['country']}: {row['cnt']} {hover_text}", axis=1),
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
            title=translate(UI_TEXT['admin_map_plot_title'], lang),
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
        st.info(translate(UI_TEXT['admin_map_no_data_message'], lang))
    # --- Top Trials Drilldown ---
    st.markdown("---")
    st.subheader(translate(UI_TEXT['admin_top_trials_title'], lang))
    if not dff.empty:
        matches = pd.json_normalize(dff["matches_json"].apply(json.loads).sum())
        top_trials = matches.groupby("trial_id").size().sort_values(ascending=False).head(3)
        st.write(top_trials)
        trial_drill = st.selectbox(translate(UI_TEXT['admin_top_trials_drilldown_label'], lang), ["None"] + list(top_trials.index))
        if trial_drill != "None":
            users = dff[dff["matches_json"].apply(lambda ms: trial_drill in [m["trial_id"] for m in json.loads(ms)])]
            for idx, row in users.iterrows():
                st.markdown(f"<details><summary><b>{row['submitted_ts']} | {row['locale']}</b></summary><pre style='white-space:pre-wrap;'>{json.dumps(json.loads(row['responses_json']), indent=2, ensure_ascii=False)}</pre></details>", unsafe_allow_html=True)
    else:
        st.info(translate(UI_TEXT['admin_top_trials_no_matches_message'], lang))

# --- Main App ---
if menu == "Patient":
    run_patient_flow()
else:
    run_admin(lang)
