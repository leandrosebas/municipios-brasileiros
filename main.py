import pyodbc
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import date
import locale

# Define o locale para pt_BR para formatação de moeda
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    locale.setlocale(locale.LC_ALL, '')

@st.cache_resource
def get_conexao():
    # Acessando as credenciais de forma segura através dos segredos do Streamlit
    conexao_dados = (
        "Driver=" + st.secrets["conexao_banco_dados"]["Driver"] + ";"
        "Server=" + st.secrets["conexao_banco_dados"]["Server"] + ";"
        "Database=" + st.secrets["conexao_banco_dados"]["Database"] + ";"
        "UID=" + st.secrets["conexao_banco_dados"]["UID"] + ";"
        "PWD=" + st.secrets["conexao_banco_dados"]["PWD"]
    )
    return pyodbc.connect(conexao_dados)

def formatar_moeda(valor):
    try:
        return locale.currency(valor, grouping=True, symbol=True)
    except:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data(ttl=10)
def carregar_dados():
    with get_conexao() as conexao:
        query = """
            SELECT Emissao, VENDEDOR, ValorNF
            FROM dbo.v_faturamento_produto
        """
        return pd.read_sql(query, conexao)

@st.cache_data(ttl=10)
def carregar_devolucoes():
    with get_conexao() as conexao:
        query = """
            SELECT 
                [QUANTIDADE],
                [VALOR_TOTAL],
                [NF],
                [EMISSAO_NFD],
                [COD_VENDEDOR],
                [NOME_VENDEDOR]
            FROM dbo.v_devolucoes
        """
        df = pd.read_sql(query, conexao)
    df['EMISSAO_NFD'] = pd.to_datetime(df['EMISSAO_NFD'], errors='coerce')
    return df

def main():
    st.set_page_config(page_title="Informações de Faturamento do Dia", layout="wide")
    hoje = date.today()

    st.title(f"Informações de Faturamento do Dia ({hoje.strftime('%d/%m/%Y')} - {hoje.strftime('%A')})")
    
    st_autorefresh(interval=10000, key="datarefresh")

    # --- Faturamento e Devoluções do dia ---
    df_vendas = carregar_dados()
    df_vendas['Emissao'] = pd.to_datetime(df_vendas['Emissao'])
    vendas_hoje = df_vendas[df_vendas['Emissao'].dt.date == hoje]

    df_devolucoes = carregar_devolucoes()
    devolucoes_hoje = df_devolucoes[df_devolucoes['EMISSAO_NFD'].dt.date == hoje]

    total_vendas = vendas_hoje['ValorNF'].sum()
    total_devolucoes = devolucoes_hoje['VALOR_TOTAL'].sum()
    faturamento_liquido = total_vendas - total_devolucoes

    # --- Cartões no topo ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Receita", formatar_moeda(total_vendas))
    col2.metric("Devolução", formatar_moeda(total_devolucoes))
    col3.metric("Faturamento Líquido", formatar_moeda(faturamento_liquido))

    # --- Receita, Devolução e Faturamento por Vendedor ---
    vendas_vendedor = (
        vendas_hoje.groupby('VENDEDOR', as_index=False)['ValorNF']
        .sum()
        .rename(columns={'ValorNF': 'Receita'})
    )
    devolucao_vendedor = (
        devolucoes_hoje.groupby('NOME_VENDEDOR', as_index=False)['VALOR_TOTAL']
        .sum()
        .rename(columns={'VALOR_TOTAL': 'Devolução'})
    )

    df_vendedor = pd.merge(
        vendas_vendedor, devolucao_vendedor,
        left_on='VENDEDOR', right_on='NOME_VENDEDOR', how='outer'
    ).fillna(0)
    df_vendedor['Faturamento'] = df_vendedor['Receita'] - df_vendedor['Devolução']
    df_vendedor = df_vendedor.sort_values(by='Faturamento', ascending=False)

    # Formata as colunas de moeda
    for col in ['Receita', 'Devolução', 'Faturamento']:
        df_vendedor[col] = df_vendedor[col].apply(formatar_moeda)

    # Seleciona o nome do vendedor disponível
    if 'VENDEDOR' in df_vendedor.columns:
        tabela_vendedor = df_vendedor[['VENDEDOR', 'Receita', 'Devolução', 'Faturamento']].rename(
            columns={'VENDEDOR': 'Vendedor'}
        )
    elif 'NOME_VENDEDOR' in df_vendedor.columns:
        tabela_vendedor = df_vendedor[['NOME_VENDEDOR', 'Receita', 'Devolução', 'Faturamento']].rename(
            columns={'NOME_VENDEDOR': 'Vendedor'}
        )
    else:
        tabela_vendedor = df_vendedor[['Receita', 'Devolução', 'Faturamento']]

    # --- NOVO TRECHO DE CÓDIGO ---
    # Coloca tanto o subtítulo quanto a tabela dentro da coluna central
    col_vazia_esq, col_tabela, col_vazia_dir = st.columns([1, 2, 1])

    with col_tabela:
        st.subheader("Receita, Devolução e Faturamento por Vendedor")
        st.dataframe(
            tabela_vendedor.style.set_properties(**{'width': 'auto'}),
            use_container_width=True
        )
# --- Fim do novo trecho ---

if __name__ == "__main__":
    main()
