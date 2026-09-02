"""
@File    :   rfp_fl001_0000_api_parquet_main.py
@Time    :   2026-09-02
@Author  :   Gabriel SURIER
@Purpose :   Create the Airflow DAG to orchestrate rfp workflows
"""

from datetime import timedelta

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

import pendulum

ETL_IMAGE = "retail-footfall-etl:latest"
ETL_NETWORK = "rfp-net"

default_args = {
    "owner": "gabriel",
    "depends_on_past": False,
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
    first_task = DockerOperator(
        task_id="rfp_fl001_0100_api_csv_extract_data",
        image=ETL_IMAGE,
        docker_url="unix://var/run/docker.sock",
        network_mode=ETL_NETWORK,
        command="python -m etl.rfp_fl001_0100_api_csv_extract_data",
        auto_remove="success",
        mount_tmp_dir=False,
    )

    second_task = DockerOperator(
        task_id="rfp_fl001_0200_csv_parquet_data_prep",
        image=ETL_IMAGE,
        docker_url="unix://var/run/docker.sock",
        network_mode=ETL_NETWORK,
        command="python -m etl.rfp_fl001_0200_csv_parquet_data_prep",
        auto_remove="success",
        mount_tmp_dir=False,
    )

    first_task >> second_task  # pylint: disable=pointless-statement