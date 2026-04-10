@echo off
cd /d "%~dp0"

python -m pip install streamlit pandas pdfplumber plotly==5.22.0 kaleido==0.2.1 reportlab matplotlib openai

python -m streamlit run app.py

pause