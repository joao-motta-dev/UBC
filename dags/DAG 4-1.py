import os
import json
import requests
import pandas as pd
from datetime import date, datetime
from sklearn.cluster import KMeans
from airflow import DAG
from airflow.operators.python import PythonOperator

# Caminhos e variáveis
caminho = os.getenv("AIRFLOW_DADOS_PATH", "/opt/airflow/dados")
arquivo_csv = os.path.join(caminho, "aluno.csv")
arquivo_saida = os.path.join(caminho, "arquivo_saida.xlsx")
SOLR_URL = os.getenv("SOLR_URL", "http://localhost:8983/solr/alunos")
CSV_URL = "https://raw.githubusercontent.com/Uniao-brasileira-dos-Compositores/desafio-engenheiro-dados_airflow/main/aluno.csv"

# Etapa 1: Baixar CSV do GitHub
def etapa_1():
    os.makedirs(caminho, exist_ok=True)
    response = requests.get(CSV_URL)
    response.raise_for_status()
    with open(arquivo_csv, "wb") as f:
        f.write(response.content)

# Etapa 2: Processar CSV com Pandas e salvar Excel
def etapa_2():
    df_raw = pd.read_csv(arquivo_csv)

    df_raw['Data de Nascimento'] = pd.to_datetime(df_raw["Data de Nascimento"])
    df_raw['Idade Correta'] = (pd.to_datetime(date.today()) - df_raw["Data de Nascimento"]).dt.days // 365
    df_raw = df_raw.drop("Idade", axis=1)
    df_raw["Ano de Nascimento"] = df_raw["Data de Nascimento"].dt.year

    df_raw = df_raw.rename(columns={
        "Nome da Mãe": "Nome da Mae",
        "Nota Média": "Nota Media",
        "Série": "Serie",
        "Idade Correta": "Idade",
        "Endereço": "Endereco"
    })

    df_raw["Rua"] = df_raw["Endereco"].str.extract(r"\s(\S+)\s")

    sobrenome_pai = df_raw["Nome do Pai"].str.split(" ").str[-1]
    sobrenome_mae = df_raw["Nome da Mae"].str.split(" ").str[-1]
    cond = sobrenome_pai == sobrenome_mae
    df_raw["Nome Completo"] = (df_raw["Nome"] + " " + sobrenome_pai).where(cond)
    df_raw = df_raw.drop(columns=["Nome do Pai", "Nome da Mae"])

    # Clustering com ML
    valor = df_raw[["Nota Media"]]
    kmeans = KMeans(n_clusters=3, random_state=42)
    df_raw["Status Geral"] = kmeans.fit_predict(valor)
    df_raw["Status Geral"] = df_raw["Status Geral"].replace({
        0: "ótimo",
        1: "regular",
        2: "bom"
    })

    ordem = ["Nome Completo", "Nome", "Serie", "Idade", "Ano de Nascimento",
             "Data de Nascimento", "Endereco", "Rua", "Nota Media", "Status Geral"]
    df_final = df_raw[ordem]

    df_final.to_excel(arquivo_saida, index=False)

# Etapa 3: Enviar dados tratados ao Solr em CSV
def etapa_3():
    if not os.path.exists(arquivo_saida):
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_saida}")

    df_final = pd.read_excel(arquivo_saida)

    # Limpar colunas vazias e linhas com nulos
    df_final = df_final.dropna(axis=1, how='all')
    df_final = df_final.dropna()
    if df_final.empty:
        raise ValueError("DataFrame está vazio após limpeza. Nada a enviar ao Solr.")

    # Formatar 'Data de Nascimento' para ISO com hora zero
    if 'Data de Nascimento' in df_final.columns:
        df_final['Data de Nascimento'] = pd.to_datetime(df_final['Data de Nascimento']).dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Adicionar coluna 'id' (necessário no Solr)
    df_final['id'] = df_final.index.astype(str)

    # Converter para CSV
    csv_data = df_final.to_csv(index=False)

    headers = {"Content-Type": "text/csv"}
    params = {"commit": "true"}

    response = requests.post(f"{SOLR_URL}/update/csv", headers=headers, params=params, data=csv_data)
    response.raise_for_status()

# DAG
default_args = {
    'start_date': datetime(2025, 7, 15),
}

with DAG(
    dag_id='Projeto_Joao_Motta',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
    tags=['João Motta', 'csv', 'pandas', 'machine learning', 'solr'],
) as dag:

    task_etapa_1 = PythonOperator(
        task_id='etapa_1',
        python_callable=etapa_1,
    )

    task_etapa_2 = PythonOperator(
        task_id='etapa_2',
        python_callable=etapa_2,
    )

    task_etapa_3 = PythonOperator(
        task_id='etapa_3',
        python_callable=etapa_3,
    )

    task_etapa_1 >> task_etapa_2 >> task_etapa_3