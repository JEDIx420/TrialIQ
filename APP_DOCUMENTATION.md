# TrialIQ Application Documentation

This document provides a comprehensive overview of the TrialIQ Streamlit application, its architecture, logic, and dependencies.

## 1. Core Purpose

TrialIQ is a web-based platform designed to help potential candidates determine their eligibility for various clinical trials. It provides a user-friendly, multi-language interface for users to answer screening questions and receive a list of suitable trials. It also includes a password-protected administrative dashboard for monitoring application usage and participant demographics.

## 2. Application Logic & User Flow

The application is a single-page Streamlit app contained entirely within `trialiq.py`. The user experience is managed by a session state variable `st.session_state.step`, which guides the user through a series of sequential steps:

1.  **Welcome:** The initial landing page that introduces the application.
2.  **Consent:** A mandatory step where the user must agree to the terms before proceeding.
3.  **Personal Info:** The user provides basic demographic information (age, gender, location).
4.  **Q&A:** The user answers a series of medical and lifestyle questions. The questions are dynamically generated based on the requirements of the available clinical trials.
5.  **Review:** The user can review and confirm their answers before submission.
6.  **Results:** The application processes the user's answers and displays a list of clinical trials for which they are potentially eligible. Each result includes a brief description of the trial.
7.  **Admin Dashboard:** Accessible via a password entered in the sidebar. This dashboard provides analytics on the collected data.

## 3. Key Features

### Admin Dashboard
- **Password Protected:** Access is restricted via a password check.
- **KPIs:** Displays key metrics such as Total Participants, Average Age, and Gender Distribution.
- **Participant Map:** A Plotly Scatter-geo map visualizes the geographic distribution of participants.
- **Data Filtering:** Admins can filter the displayed data by date range, gender, and age.
- **Raw Data View:** A table displaying the raw, anonymized participant data.

### Multilingual Support
- A centralized dictionary `UI_TEXT` holds all user-facing strings.
- The `translate()` function retrieves the appropriate string based on the language selected by the user in the sidebar.
- Supported languages are managed in the `LANGUAGES` dictionary.

### Data Handling
- **Database:** The application uses Python's built-in `sqlite3` for data storage. The database is created in-memory and is therefore ephemeral; it resets each time the application restarts.
- **Data Injection:** A function `inject_synthetic_data()` can be toggled to populate the database with realistic-looking fake data for demonstration purposes.
- **Context Manager:** All database interactions are safely handled using a `get_db_connection` context manager to ensure connections are properly opened and closed.

## 4. Deployment on Cloudera Machine Learning (CML)

The application is designed to run as a single file in a CML Application environment where shell scripts cannot be the primary entry point.

- **`launch.py`:** This script acts as the entry point. It reads the CML-provided `$PORT` environment variable and uses Python's `subprocess` module to execute the main Streamlit command (`streamlit run trialiq.py`) with the necessary parameters for the CML environment.
- **To Deploy:** In CML, create a new Application, specify `launch.py` as the script to run, and CML will handle the rest.

## 5. Project Dependencies

The application relies on the following Python libraries. The script includes a dependency check and installation block to ensure these are available in the runtime environment.

- `streamlit`: The core web application framework.
- `pandas`: Used for data manipulation and analysis, particularly in the admin dashboard.
- `plotly`: Powers the interactive charts and the participant map in the admin dashboard.
- `babel`: Used for locale-aware formatting, specifically for displaying month names in the admin dashboard date filter.
- `google-generativeai`: Integrated for the translation functionality.
- `faker`: Used to generate synthetic data for the demonstration mode.
