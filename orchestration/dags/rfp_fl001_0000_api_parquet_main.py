"""
@File    :   rfp_fl001_0000_api_parquet_main.py
@Time    :   2026-09-02
@Author  :   Gabriel SURIER
@Purpose :   Create the Airflow DAG to orchestrate rfp workflows
"""

import logging
import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import Variable

logger = logging.getLogger(__name__)

ETL_IMAGE = "retail-footfall-etl:latest"
ETL_NETWORK = "airflow-net"

# Key -> default. Resolution order: Airflow Variable, then .env, then default
VARIABLE_KEYS = {
    "DATA_LOAD_MOD": "DELTA",
    "DATA_LOAD_INIT_DATE": "2026-01-01",
    "MINIO_ROOT_PASSWORD": "",
}

default_args = {
    "owner": "gabriel.surier",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def resolve(key: str) -> tuple[str, str]:
    """Resolve a key from Airflow Variable, then environment, then default.

    Called at runtime only (task execution or template rendering), so a
    variable created at any time is picked up on the next run.

    Args:
        key: Name of the variable to resolve, must be in VARIABLE_KEYS.

    Returns:
        A tuple (value, source), source being "airflow_variable", "env"
        or "default".
    """
    value = Variable.get(key, default=None)
    if value is not None:
        return value, "airflow_variable"
    value = os.getenv(key)
    if value is not None:
        return value, "env"
    return VARIABLE_KEYS[key], "default"


def resolve_value(key: str) -> str:
    """Return only the resolved value, for use in Jinja templates."""
    return resolve(key)[0]


def log_and_resolve_variables() -> None:
    """Log each resolved variable with its source.

    Values from Airflow Variables or defaults are logged (masked by
    Airflow when the key name is sensitive). Any value coming from the
    environment (.env) is hidden and triggers a warning.
    """
    for key in VARIABLE_KEYS:
        value, source = resolve(key)
        if source == "env":
            logger.warning("%s loaded from .env (value hidden)", key)
        else:
            logger.info("%s=%s (source=%s)", key, value, source)


with DAG(
    dag_id="rfp_fl001_0000_api_parquet_main",
    default_args=default_args,
    description="retail footfall pipeline workflow # 01",
    start_date=pendulum.datetime(2026, 9, 2, tz="Europe/Paris"),
    schedule="0 8 * * *",
    catchup=False,
    tags={"rfp", "demo"},
    user_defined_macros={"resolve_value": resolve_value},
) as dag:

    log_variables = PythonOperator(
        task_id="log_and_resolve_variables",
        python_callable=log_and_resolve_variables,
    )

    first_task = DockerOperator(
        task_id="rfp_fl001_0100_api_csv_extract_data",
        image=ETL_IMAGE,
        docker_url="unix://var/run/docker.sock",
        network_mode=ETL_NETWORK,
        command="python -m etl.rfp_fl001_0100_api_csv_extract_data",
        environment={
            "AIRFLOW_CTX_DAG_RUN_ID": "{{ run_id }}",
            "AIRFLOW_CTX_EXECUTION_DATE": "{{ ts }}",
            "DATA_LOAD_MOD": "{{ resolve_value('DATA_LOAD_MOD') }}",
            "DATA_LOAD_INIT_DATE": "{{ resolve_value('DATA_LOAD_INIT_DATE') }}",
            "MINIO_ROOT_PASSWORD": "{{ resolve_value('MINIO_ROOT_PASSWORD') }}",
        },
        auto_remove="success",
        mount_tmp_dir=False,
    )

    second_task = DockerOperator(
        task_id="rfp_fl001_0200_csv_parquet_data_prep",
        image=ETL_IMAGE,
        docker_url="unix://var/run/docker.sock",
        network_mode=ETL_NETWORK,
        command="python -m etl.rfp_fl001_0200_csv_parquet_data_prep",
        environment={
            "AIRFLOW_CTX_DAG_RUN_ID": "{{ run_id }}",
            "AIRFLOW_CTX_EXECUTION_DATE": "{{ ts }}",
        },
        auto_remove="success",
        mount_tmp_dir=False,
    )

    log_variables >> first_task >> second_task  # pylint: disable=pointless-statement
