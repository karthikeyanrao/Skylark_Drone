Set-Location $PSScriptRoot
python -m pip install -r requirements.txt -q
python -m streamlit run app.py
