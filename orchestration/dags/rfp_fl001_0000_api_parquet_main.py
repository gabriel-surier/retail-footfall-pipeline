"""
@File    :   rfp_fl001_0000_api_parquet_main.py
@Time    :   2026-09-02
@Author  :   Gabriel SURIER
@Purpose :  Create the Airflow DAG to orchestrate rfp workflows
"""

from datetime import timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

import pendulum

default_args = {
    "owner": "gabriel",
    "depends_on_past": False,
    "email": [""],
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="rfp_fl001_0000_api_parquet_main",
    default_args=default_args,
    description="retail footfall pipeline workflow # 01",
    start_date=pendulum.datetime(2026, 9, 2),
    schedule="0 8 * * *",
    catchup=False,
    tags=["rfp"],
) as dag:
    first_task = BashOperator(
        task_id="rfp_fl001_0100_api_csv_extract_data",
        bash_command="python -m etl.rfp_fl001_0100_api_csv_extract_data",
    )

    second_task = BashOperator(
        task_id="rfp_fl001_0100_api_csv_extract_data",
        bash_command="python -m etl.rfp_fl001_0100_api_csv_extract_data",
    )
    first_task >> second_task  # pylint: disable=pointless-statement
