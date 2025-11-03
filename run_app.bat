@echo off
echo Installing required packages...
pip install -r requirements.txt

echo.
echo Starting Streamlit application...
streamlit run app.py


