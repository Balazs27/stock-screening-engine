FROM astrocrpublic.azurecr.io/runtime:3.1-9

# Ensure project root is on PYTHONPATH so Airflow can import src/
ENV PYTHONPATH="/usr/local/airflow"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# (Optional, but recommended) Copy dbt project for future dbt DAGs
COPY dbt_project dbt_project

# Pre-fetch dbt packages (safe even if you don't use dbt DAGs yet)
RUN cd dbt_project && dbt deps || true
