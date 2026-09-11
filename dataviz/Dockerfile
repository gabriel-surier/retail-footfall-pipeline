ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# setup requirements packages
COPY dataviz/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# setup project modules
COPY .env_docker ./.env
COPY pyproject.toml ./pyproject.toml
COPY dataviz/streamlit_app.py ./streamlit_app.py
COPY src/__init__.py ./src/__init__.py
COPY src/rfp_config.py ./src/rfp_config.py

# No pip install -e . here: avoids pyproject.toml's etl dependency
ENV PYTHONPATH=/app

# Streamlit default port, no override needed
EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]