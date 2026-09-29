import streamlit as st
import pandas as pd
import openpyxl
import re
from PIL import Image
import pytesseract
import io

st.set_page_config(page_title="Leitor de Guias CEC - Amil, Bradesco & Medsul", page_icon="📋", layout="centered")

st.title("📋 Processador de Guias - Clínica CEC")
st.markdown("### Leitura Inteligente de Guias e Preenchimento de Planilha")

# Seleção de Convênio
convenio_selecionado = st.selectbox(
    "Selecione o Convênio da Guia:",
    ["Amil", "Bradesco", "Tempo Med (Medsul)", "SulAmérica", "Unimed", "Outros"]
)

# Modalidade e Especialidade (Pré-definidos com opção de seleção simples)
col_mod, col_esp = st.columns(2)
with col_mod:
    modalidade = st.selectbox("Modalidade:", ["Presencial", "Online"], index=0) # Padrão Presencial
with col_esp:
    especialidade = st.selectbox("Especialidade:", ["Psicoterapia", "Outra"], index=0) # Padrão Psicoterapia

# 1. Upload da Planilha Mensal
uploaded_excel = st.file_uploader("1. Selecione a sua planilha Excel mensal (.xlsx)", type=["xlsx"])

# 2. Upload da Guia (Foto ou Câmera)
camera_or_file = st.radio("Escolha como enviar a foto da guia:", ("Upload de Foto", "Tirar Foto com Câmera"))

image_file = None
if camera_or_file == "Upload de Foto":
    image_file = st.file_uploader("2. Envie a foto da guia do plano", type=["jpg", "jpeg", "png"])
else:
    image_file = st.camera_input("2. Tire a foto da guia do plano")

def extrair_dados_amil(text):
    """
    Regras de leitura Amil:
    - Campo 5: Senha (utilizado como Número da Guia)
    - Campo 10: Nome do Beneficiário
    - Sessões: Sempre 1 atendimento por guia para Amil
    """
    senha_match = re.search(r'(?:5\s*-\s*SENHA|SENHA|TOKEN|GUIA)[:\s]+([A-Z0-9\-\.]{4,15})', text, re.IGNORECASE)
    if not senha_match:
        senha_match = re.search(r'5\s*[\-\:]\s*([0-9A-Z]{4,12})', text)
    numero_guia = senha_match.group(1).strip() if senha_match else ""

    nome_match = re.search(r'(?:10\s*-\s*NOME DO BENEFICIÁRIO|BENEFICIÁRIO|NOME)[:\s]+([A-ZÁÀÂÃÉÈÍÓÔÕÚÇ\s]{5,40})', text, re.IGNORECASE)
    paciente = nome_match.group(1).strip() if nome_match else ""

    return {
        "paciente": paciente,
        "numero_guia": numero_guia, # Extraído do Campo 5 (Senha)
        "convenio": "AMIL",
        "qtd_atendimentos": 1,      # Regra Amil: Sempre 1 atendimento por guia
        "texto_bruto": text
    }

def extrair_dados_bradesco(text):
    """
    Regras de leitura Bradesco:
    - Campo 5: Senha (utilizado como Número da Guia)
    - Nome do Beneficiário
    - Sessões: Pergunta ao usuário quantas sessões constam na guia
    """
    senha_match = re.search(r'(?:5\s*-\s*SENHA|SENHA|TOKEN|GUIA|NUMERO)[:\s]+([A-Z0-9\-\.]{4,15})', text, re.IGNORECASE)
    if not senha_match:
        senha_match = re.search(r'5\s*[\-\:]\s*([0-9A-Z]{4,12})', text)
    numero_guia = senha_match.group(1).strip() if senha_match else ""

    nome_match = re.search(r'(?:NOME DO BENEFICIÁRIO|BENEFICIÁRIO|PACIENTE|NOME)[:\s]+([A-ZÁÀÂÃÉÈÍÓÔÕÚÇ\s]{5,40})', text, re.IGNORECASE)
    paciente = nome_match.group(1).strip() if nome_match else ""

    qtd_match = re.search(r'(?:SESSÕES|SESSAO|ATENDIMENTOS|QTD)[:\s]+(\d+)', text, re.IGNORECASE)
    qtd_atendimentos = int(qtd_match.group(1)) if qtd_match else 1

    return {
        "paciente": paciente,
        "numero_guia": numero_guia, # Extraído do Campo 5 (Senha)
        "convenio": "BRADESCO",
        "qtd_atendimentos": qtd_atendimentos,
        "texto_bruto": text
    }

def extrair_dados_tempomed(text):
    """
    Regras de leitura Tempo Med / Medsul:
    - Grava na planilha como "MEDSUL"
    - Campo 5: Senha (utilizado como Número da Guia)
    - Nome do Beneficiário
    """
    senha_match = re.search(r'(?:5\s*-\s*SENHA|SENHA|TOKEN|GUIA|NUMERO)[:\s]+([A-Z0-9\-\.]{4,15})', text, re.IGNORECASE)
    if not senha_match:
        senha_match = re.search(r'5\s*[\-\:]\s*([0-9A-Z]{4,12})', text)
    numero_guia = senha_match.group(1).strip() if senha_match else ""

    nome_match = re.search(r'(?:NOME DO BENEFICIÁRIO|BENEFICIÁRIO|PACIENTE|NOME)[:\s]+([A-ZÁÀÂÃÉÈÍÓÔÕÚÇ\s]{5,40})', text, re.IGNORECASE)
    paciente = nome_match.group(1).strip() if nome_match else ""

    qtd_match = re.search(r'(?:SESSÕES|SESSAO|ATENDIMENTOS|QTD)[:\s]+(\d+)', text, re.IGNORECASE)
    qtd_atendimentos = int(qtd_match.group(1)) if qtd_match else 1

    return {
        "paciente": paciente,
        "numero_guia": numero_guia, # Extraído do Campo 5 (Senha)
        "convenio": "MEDSUL",        # Registra como MEDSUL na planilha
        "qtd_atendimentos": qtd_atendimentos,
        "texto_bruto": text
    }

if uploaded_excel and image_file:
    image = Image.open(image_file)
    st.image(image, caption=f"Guia {convenio_selecionado} Enviada", use_column_width=True)
    
    with st.spinner("Lendo foto e analisando campos..."):
        text = pytesseract.image_to_string(image, lang="por") if "por" in pytesseract.get_languages() else pytesseract.image_to_string(image)
        
        if convenio_selecionado == "Amil":
            dados = extrair_dados_amil(text)
        elif convenio_selecionado == "Bradesco":
            dados = extrair_dados_bradesco(text)
        elif convenio_selecionado == "Tempo Med (Medsul)":
            dados = extrair_dados_tempomed(text)
        else:
            nome_match = re.search(r'(?:NOME|BENEFICIÁRIO)[:\s]+([A-Z\s]{5,40})', text, re.IGNORECASE)
            guia_match = re.search(r'(?:GUIA|SENHA|NUMERO)[:\s]+([0-9A-Z]{5,15})', text, re.IGNORECASE)
            dados = {
                "paciente": nome_match.group(1).strip() if nome_match else "",
                "numero_guia": guia_match.group(1).strip() if guia_match else "",
                "convenio": convenio_selecionado.upper(),
                "qtd_atendimentos": 1
            }

    st.subheader("🔍 Validação dos Dados Extraídos")
    
    # Incongruências & Avisos da Leitura
    if not dados["numero_guia"]:
        st.warning(f"⚠️ **Incongruência no Nº da Guia ({convenio_selecionado})**: Não foi possível identificar com clareza o **Campo 5 (Senha/Guia)** na imagem. Por favor, confira ou digite manualmente.")
    
    if not dados["paciente"]:
        st.warning("⚠️ **Incongruência no Nome**: O nome do paciente não foi capturado perfeitamente. Verifique o campo abaixo.")

    col1, col2 = st.columns(2)
    with col1:
        paciente = st.text_input("Nome Completo Paciente (Coluna E)", value=dados["paciente"])
        numero_guia = st.text_input("Número Guia / Campo 5 - Senha (Coluna F)", value=dados["numero_guia"])
    with col2:
        convenio = st.text_input("Convênio (Coluna G)", value=dados["convenio"])
        
        # Regra de Quantidade de Sessões
        if convenio_selecionado == "Amil":
            qtd_atendimentos = st.number_input("Nº de Atendimentos (Coluna H) [Regra Amil: 1 por guia]", value=1, disabled=True)
        else:
            qtd_atendimentos = st.number_input(
                f"Nº de Atendimentos (Quantas sessões constam nesta guia {convenio_selecionado}?)",
                value=dados.get("qtd_atendimentos", 1),
                min_value=1
            )

    # Leitura prévia da planilha para checar duplicidade e linhas existentes
    wb = openpyxl.load_workbook(uploaded_excel)
    ws = wb.active
    
    guias_existentes = {}
    pacientes_existentes = {}
    
    for row in range(5, 150):
        val_pac = ws.cell(row=row, column=5).value  # Coluna E
        val_guia = ws.cell(row=row, column=6).value # Coluna F
        
        if val_pac:
            pacientes_existentes[str(val_pac).strip().lower()] = row
        if val_guia:
            guias_existentes[str(val_guia).strip().lower()] = row

    # Alerta de Guia Repetida (Evitar Duplicidade)
    guia_duplicada = False
    if numero_guia and str(numero_guia).strip().lower() in guias_existentes:
        guia_duplicada = True
        linha_duplicada = guias_existentes[str(numero_guia).strip().lower()]
        st.error(f"🚫 **ATENÇÃO: GUIA REPETIDA!**\nA guia/senha número **{numero_guia}** já foi cadastrada anteriormente na **Linha {linha_duplicada}** da planilha.")

    permitir_salvar = True
    if guia_duplicada:
        permitir_salvar = st.checkbox("Deseja substituir/sobrescrever a guia existente?")

    if st.button("✅ Preencher Linha da Guia na Planilha", disabled=not permitir_salvar):
        linha_destino = None
        
        if guia_duplicada and str(numero_guia).strip().lower() in guias_existentes:
            linha_destino = guias_existentes[str(numero_guia).strip().lower()]
        else:
            # Busca paciente existente ou primeira linha vazia
            if paciente and paciente.strip().lower() in pacientes_existentes:
                linha_destino = pacientes_existentes[paciente.strip().lower()]
            else:
                for row in range(5, 200):
                    if ws.cell(row=row, column=5).value is None and ws.cell(row=row, column=4).value is None:
                        linha_destino = row
                        break
        
        # Atualiza as colunas na planilha Excel
        ws.cell(row=linha_destino, column=5, value=paciente)            # Coluna E: NOME COMPLETO
        ws.cell(row=linha_destino, column=6, value=numero_guia)          # Coluna F: NÚMERO GUIA / Campo 5 (Senha)
        ws.cell(row=linha_destino, column=7, value=convenio)             # Coluna G: CONVÊNIO (MEDSUL / BRADESCO / AMIL)
        ws.cell(row=linha_destino, column=8, value=qtd_atendimentos)     # Coluna H: ATENDIMENTOS
        
        output_buffer = io.BytesIO()
        wb.save(output_buffer)
        output_buffer.seek(0)
        
        st.success(f"🎉 Guia {convenio_selecionado} processada com sucesso na **Linha {linha_destino}**! [Preenchido como {convenio} | Modalidade: {modalidade} | Especialidade: {especialidade}]")
        st.download_button(
            label="📥 Baixar Planilha Atualizada (.xlsx)",
            data=output_buffer,
            file_name="Planilha_CEC_Atualizada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
