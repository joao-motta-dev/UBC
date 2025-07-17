FROM apache/airflow:2.7.1-python3.10

# Instala dependências de sistema necessárias
USER root

RUN apt-get update && \
    apt-get install -y netcat curl && \
    apt-get clean

# Volta para usuário airflow
USER airflow

# Instala pacotes Python necessários para a DAG
RUN pip install --no-cache-dir \
    pandas \
    scikit-learn \
    openpyxl \
    requests