from calendar import monthrange
from datetime import datetime
import io
import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
import streamlit as st
from supabase import Client, create_client

# Define o caminho do diretório do script atual
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# CONEXÃO BANCO DE DADOS
# ==========================================
SUPABASE_URL = st.secrets.get(
    "SUPABASE_URL", "https://rqzenyisowodympiheod.supabase.co"
)
SUPABASE_KEY = st.secrets.get(
    "SUPABASE_KEY", "sb_publishable_yKGWZScOzAmahuDH62c0aw_SjlyvXjj"
)


@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = init_supabase()

DIAS_SEMANA = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]


# ==========================================
# 1. FUNÇÕES REGRAS DE NEGÓCIO E CÁLCULO
# ==========================================
def formatar_horas(decimal):
    try:
        if decimal is None:
            return "00:00:00"
        horas = int(abs(decimal))
        minutos = int(round((abs(decimal) - horas) * 60))
        if minutos == 60:
            horas += 1
            minutos = 0
        sinal = "-" if decimal < 0 else ""
        return f"{sinal}{horas:02d}:{minutos:02d}:00"
    except Exception:
        return "00:00:00"


def converter_texto_para_decimal(texto_hora):
    try:
        if not texto_hora or ":" not in str(texto_hora):
            return float(str(texto_hora).replace(",", "."))
        partes = list(map(int, str(texto_hora).split(":")))
        h = partes[0]
        m = partes[1] if len(partes) > 1 else 0
        return round(h + (m / 60.0), 2)
    except Exception:
        return 8.0


def calcular_trabalhado_dia(e1, s1, e2, s2, obs, base_hora):
    try:
        fmt = "%H:%M:%S"
        total_segundos = 0

        e1 = (e1 or "").strip()
        s1 = (s1 or "").strip()
        e2 = (e2 or "").strip()
        s2 = (s2 or "").strip()

        e1 = e1 + ":00" if len(e1) == 5 else e1
        s1 = s1 + ":00" if len(s1) == 5 else s1
        e2 = e2 + ":00" if len(e2) == 5 else e2
        s2 = s2 + ":00" if len(s2) == 5 else s2

        if base_hora == 6.0:
            if all([e1, s1, e2, s2]):
                permanencia = (
                    datetime.strptime(s2, fmt) - datetime.strptime(e1, fmt)
                ).total_seconds()
                intervalo_real = (
                    datetime.strptime(e2, fmt) - datetime.strptime(s1, fmt)
                ).total_seconds()
                total_segundos = permanencia - intervalo_real + 900
            elif e1 and s2:
                total_segundos = (
                    datetime.strptime(s2, fmt) - datetime.strptime(e1, fmt)
                ).total_seconds()
        else:
            if all([e1, s1, e2, s2]):
                t1 = (
                    datetime.strptime(s1, fmt) - datetime.strptime(e1, fmt)
                ).total_seconds()
                t2 = (
                    datetime.strptime(s2, fmt) - datetime.strptime(e2, fmt)
                ).total_seconds()
                total_segundos = t1 + t2
            elif e1 and s2:
                total_segundos = (
                    datetime.strptime(s2, fmt) - datetime.strptime(e1, fmt)
                ).total_seconds()

        if "AH:" in str(obs).upper():
            try:
                h_txt = str(obs).upper().split("AH:")[1].strip()
                partes = list(map(int, h_txt.split(":")))
                total_segundos += (partes[0] * 3600) + (partes[1] * 60)
            except Exception:
                pass
        return round(total_segundos / 3600, 2)
    except Exception:
        return 0.0


def obter_dados_usuario(usuario):
    try:
        res = (
            supabase.table("usuarios")
            .select("cargo, jornada")
            .eq("usuario", usuario.lower())
            .execute()
        )
        if res.data:
            cargo = res.data[0].get("cargo") or "NÃO INFORMADO"
            base_hora = res.data[0].get("jornada") or 8.0
            return cargo, float(base_hora)
    except Exception:
        pass
    return "NÃO INFORMADO", 8.0


def obter_meta_mensal(usuario, mes, ano):
    try:
        res = (
            supabase.table("metas_mensais")
            .select("meta")
            .eq("usuario", usuario.lower())
            .eq("mes", str(mes))
            .eq("ano", str(ano))
            .execute()
        )
        if res.data:
            return float(res.data[0].get("meta", 0.0))
    except Exception:
        pass
    return 0.0


def gerar_pdf_bytes(usuario, mes, ano, dados_memoria, totais, cargo):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    path_cabecalho = os.path.join(PASTA_ATUAL, "cabecalho.png")
    path_rodape = os.path.join(PASTA_ATUAL, "rodape.png")

    def desenhar_estrutura():
        if os.path.exists(path_cabecalho):
            c.drawImage(
                path_cabecalho,
                0,
                h - 3.5 * cm,
                width=w,
                height=3.5 * cm,
                mask="auto",
            )

        if os.path.exists(path_rodape):
            c.drawImage(
                path_rodape,
                0,
                0,
                width=w,
                height=2.5 * cm,
                mask="auto",
            )

        c.setFont("Helvetica-Bold", 10)
        c.drawString(1.5 * cm, h - 4.0 * cm, f"SERVIDOR: {str(usuario).upper()}")
        c.drawString(1.5 * cm, h - 4.5 * cm, f"CARGO: {str(cargo).upper()}")
        c.drawString(w - 6 * cm, h - 4.0 * cm, f"MÊS/ANO: {mes}/{ano}")

    desenhar_estrutura()
    data_pdf = [[
        "Data",
        "Dia",
        "Ent.",
        "Alm.",
        "Ret.",
        "Sai.",
        "Tot.",
        "Comp.",
        "Dev.",
        "Obs",
    ]]

    for v in dados_memoria:
        data_pdf.append([
            str(v["Data"]),
            str(v["Dia"])[:3],
            str(v["Entrada"]),
            str(v["Almoço"]),
            str(v["Retorno"]),
            str(v["Saída"]),
            str(v["Total"]),
            str(v["Comp."]),
            str(v["Dev."]),
            str(v["Obs"])[:25],
        ])

    table = Table(
        data_pdf,
        colWidths=[
            2.1 * cm,
            1.0 * cm,
            1.4 * cm,
            1.4 * cm,
            1.4 * cm,
            1.4 * cm,
            1.4 * cm,
            1.4 * cm,
            1.4 * cm,
            5.8 * cm,
        ],
    )
    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    )

    largura_t, altura_t = table.wrapOn(c, w, h)
    y_pos_tabela = (h - 5.0 * cm) - altura_t
    table.drawOn(c, 1 * cm, y_pos_tabela)

    y_resumo = y_pos_tabela - 1.2 * cm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(
        1.5 * cm,
        y_resumo,
        f"Trabalhado: {totais['total']} | Extras: {totais['comp']} | Devedoras:"
        f" {totais['dev']} | Cursos: {totais['cursos']}",
    )
    c.drawString(
        1.5 * cm,
        y_resumo - 0.4 * cm,
        f"Falta Ponto Facultativo: {totais['fac']}",
    )

    y_ass = y_resumo - 2.5 * cm
    if y_ass < 3.0 * cm:
        c.showPage()
        desenhar_estrutura()
        y_ass = h - 8 * cm

    c.setFont("Helvetica", 9)
    c.line(2 * cm, y_ass, 8 * cm, y_ass)
    c.drawCentredString(5 * cm, y_ass - 0.4 * cm, "Assinatura do Servidor")
    c.line(w - 8 * cm, y_ass, w - 2 * cm, y_ass)
    c.drawCentredString(w - 5 * cm, y_ass - 0.4 * cm, "Chefia Imediata")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# 2. INTERFACE STREAMLIT
# ==========================================
def main(usuario="ADMIN"):
    st.set_page_config(
        page_title=f"Sistema de Ponto - {usuario}",
        page_icon="⏱️",
        layout="wide",
    )

    # Estilização CSS Personalizada
    st.markdown(
        """
        <style>
        .stButton>button {
            border-radius: 5px;
            font-weight: bold;
        }
        .rodape-assinatura {
            text-align: center;
            color: #000000;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 0.5px;
            margin-top: 30px;
            margin-bottom: 10px;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title(f"⏱️ Sistema de Ponto - {usuario.upper()}")

    # ------------------------------------------
    # BOTÕES DE REGISTRO RÁPIDO DE PONTO
    # ------------------------------------------
    st.subheader("Batida Ponto Rápida")
    c1, c2, c3, c4 = st.columns(4)

    def registrar_ponto_rapido(tipo):
        hoje = datetime.now().strftime("%d/%m/%Y")
        hora = datetime.now().strftime("%H:%M:%S")
        mapa = {
            "ENTRADA": "entrada",
            "ALMOÇO": "almoco",
            "RETORNO": "retorno",
            "SAÍDA": "saida",
        }
        coluna = mapa.get(tipo)

        try:
            res = (
                supabase.table("ponto")
                .select("id")
                .eq("funcionario", usuario)
                .eq("data", hoje)
                .execute()
            )

            if res.data:
                id_reg = res.data[0]["id"]
                supabase.table("ponto").update({coluna: hora}).eq(
                    "id", id_reg
                ).execute()
            else:
                nova_linha = {
                    "funcionario": usuario,
                    "data": hoje,
                    "entrada": "",
                    "almoco": "",
                    "retorno": "",
                    "saida": "",
                    coluna: hora,
                }
                supabase.table("ponto").insert(nova_linha).execute()

            st.success(f"{tipo} registrada com sucesso às {hora}!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao registrar ponto: {e}")

    with c1:
        if st.button("🟢 ENTRADA", use_container_width=True):
            registrar_ponto_rapido("ENTRADA")
    with c2:
        if st.button("🟡 ALMOÇO", use_container_width=True):
            registrar_ponto_rapido("ALMOÇO")
    with c3:
        if st.button("🔵 RETORNO", use_container_width=True):
            registrar_ponto_rapido("RETORNO")
    with c4:
        if st.button("🔴 SAÍDA", use_container_width=True):
            registrar_ponto_rapido("SAÍDA")

    st.markdown("---")

    # ------------------------------------------
    # FILTROS DE MÊS E ANO
    # ------------------------------------------
    col_mes, col_ano, col_empty = st.columns([2, 2, 6])
    with col_mes:
        meses = [f"{i:02d}" for i in range(1, 13)]
        mes_sel = st.selectbox(
            "Mês",
            meses,
            index=int(datetime.now().strftime("%m")) - 1,
            key="filtro_mes",
        )
    with col_ano:
        anos = [str(a) for a in range(2024, 2031)]
        ano_sel = st.selectbox(
            "Ano",
            anos,
            index=anos.index(datetime.now().strftime("%Y")),
            key="filtro_ano",
        )

    mes_int = int(mes_sel)
    ano_int = int(ano_sel)
    _, ultimo_dia = monthrange(ano_int, mes_int)

    cargo_atual, base_hora_atual = obter_dados_usuario(usuario)
    meta_mes_atual = obter_meta_mensal(usuario, mes_sel, ano_sel)

    # ------------------------------------------
    # CARREGAMENTO DO BANCO DE DADOS
    # ------------------------------------------
    try:
        res = (
            supabase.table("ponto")
            .select("*")
            .eq("funcionario", usuario)
            .execute()
        )
        mapa_pontos = {r["data"]: r for r in res.data}
    except Exception:
        mapa_pontos = {}

    dados_memoria = []
    (
        total_comp_acumulado,
        total_dev_acumulado,
        total_trabalhado_bruto,
        total_cursos,
    ) = (0.0, 0.0, 0.0, 0.0)

    for dia in range(1, ultimo_dia + 1):
        data_str = f"{dia:02d}/{mes_int:02d}/{ano_int}"
        dt_obj = datetime.strptime(data_str, "%d/%m/%Y")
        e_fim_de_semana = dt_obj.weekday() >= 5
        r = mapa_pontos.get(data_str, {})

        id_reg = r.get("id")
        e1 = r.get("entrada", "") or ""
        a1 = r.get("almoco", "") or ""
        r1 = r.get("retorno", "") or ""
        s1 = r.get("saida", "") or ""
        obs = r.get("obs", "") or ""
        h_curso = float(r.get("cursos") or 0.0)

        h_d_final = calcular_trabalhado_dia(
            e1, a1, r1, s1, obs, float(base_hora_atual)
        )

        comp_dia, dev_dia = 0.0, 0.0
        tem_ponto = any(x and str(x).strip() != "" for x in [e1, a1, r1, s1])
        tem_ah = "AH:" in str(obs).upper()

        if tem_ponto or tem_ah:
            if any(
                x in str(obs).upper()
                for x in [
                    "FÉRIAS",
                    "ABONADA",
                    "ATESTADO",
                    "FERIADO",
                    "FACULTATIVO",
                ]
            ):
                h_d_exibir = base_hora_atual
            else:
                if not e_fim_de_semana:
                    comp_dia = max(0, h_d_final - base_hora_atual)
                    dev_dia = max(0, base_hora_atual - h_d_final)
                else:
                    comp_dia = h_d_final
                h_d_exibir = h_d_final
        else:
            h_d_exibir = 0.0

        total_comp_acumulado += comp_dia
        total_dev_acumulado += dev_dia
        total_trabalhado_bruto += h_d_exibir
        total_cursos += h_curso

        obs_exibir = (
            f"({formatar_horas(h_curso)}) " + obs if h_curso > 0 else obs
        )

        ent_disp = e1 if (e1 or not e_fim_de_semana) else "---------"
        alm_disp = a1 if (a1 or not e_fim_de_semana) else "---------"
        ret_disp = r1 if (r1 or not e_fim_de_semana) else "---------"
        sai_disp = s1 if (s1 or not e_fim_de_semana) else "---------"

        tot_disp = (
            formatar_horas(h_d_exibir)
            if (tem_ponto or tem_ah or not e_fim_de_semana)
            else "---------"
        )
        comp_disp = (
            formatar_horas(comp_dia)
            if (tem_ponto or tem_ah or not e_fim_de_semana)
            else "---------"
        )
        dev_disp = (
            formatar_horas(dev_dia)
            if (tem_ponto or tem_ah or not e_fim_de_semana)
            else "---------"
        )

        row_data = {
            "ID": id_reg,
            "Data": data_str,
            "Dia": DIAS_SEMANA[dt_obj.weekday()],
            "Entrada": ent_disp,
            "Almoço": alm_disp,
            "Retorno": ret_disp,
            "Saída": sai_disp,
            "Total": tot_disp,
            "Comp.": comp_disp,
            "Dev.": dev_disp,
            "Obs": obs_exibir,
            "Cursos": h_curso,
            "raw_e1": e1,
            "raw_a1": a1,
            "raw_r1": r1,
            "raw_s1": s1,
            "raw_obs": obs,
        }
        dados_memoria.append(row_data)

    # ------------------------------------------
    # TABELA PRINCIPAL DE EXIBIÇÃO
    # ------------------------------------------
    st.subheader(" Folha de Ponto Mensal")
    cols_header = st.columns([1.2, 1.2, 1, 1, 1, 1, 1, 1, 1, 2.5, 0.8])
    headers = [
        "Data",
        "Dia",
        "Ent.",
        "Alm.",
        "Ret.",
        "Sai.",
        "Total",
        "Comp.",
        "Dev.",
        "Obs",
        "Editar",
    ]
    for col, h in zip(cols_header, headers):
        col.markdown(f"**{h}**")

    for idx, row in enumerate(dados_memoria):
        c_data, c_dia, c_ent, c_alm, c_ret, c_sai, c_tot, c_comp, c_dev, c_obs, c_btn = (
            st.columns([1.2, 1.2, 1, 1, 1, 1, 1, 1, 1, 2.5, 0.8])
        )
        c_data.text(row["Data"])
        c_dia.text(row["Dia"][:3])
        c_ent.text(row["Entrada"])
        c_alm.text(row["Almoço"])
        c_ret.text(row["Retorno"])
        c_sai.text(row["Saída"])
        c_tot.text(row["Total"])
        c_comp.text(row["Comp."])
        c_dev.text(row["Dev."])
        c_obs.text(row["Obs"])

        if c_btn.button("✏️", key=f"btn_edit_{idx}"):
            st.session_state.edit_row = row
            st.rerun()

    # ------------------------------------------
    # MODAL DE EDIÇÃO DE REGISTRO
    # ------------------------------------------
    if "edit_row" in st.session_state and st.session_state.edit_row:
        row_edit = st.session_state.edit_row
        st.markdown("---")
        st.subheader(f"✏️ Editar Registro de Ponto - {row_edit['Data']}")

        with st.form("form_edicao_ponto"):
            e1_input = st.text_input(
                "Entrada:", value=row_edit["raw_e1"] or "00:00:00"
            )
            a1_input = st.text_input(
                "Almoço:", value=row_edit["raw_a1"] or "00:00:00"
            )
            r1_input = st.text_input(
                "Retorno:", value=row_edit["raw_r1"] or "00:00:00"
            )
            s1_input = st.text_input(
                "Saída:", value=row_edit["raw_s1"] or "00:00:00"
            )
            obs_input = st.text_input(
                "Observação:", value=row_edit["raw_obs"] or ""
            )

            cur_raw = row_edit.get("Cursos", 0.0)
            cur_val_str = (
                formatar_horas(cur_raw) if cur_raw > 0 else "00:00:00"
            )
            curso_input = st.text_input("Horas Curso:", value=cur_val_str)

            col_salvar, col_cancelar = st.columns(2)
            with col_salvar:
                btn_salvar = st.form_submit_button(
                    "💾 SALVAR REGISTRO", use_container_width=True
                )
            with col_cancelar:
                btn_cancelar = st.form_submit_button(
                    "❌ CANCELAR", use_container_width=True
                )

            if btn_salvar:
                h_curso_val = converter_texto_para_decimal(
                    curso_input.strip()
                )
                dados_update = {
                    "entrada": e1_input.strip(),
                    "almoco": a1_input.strip(),
                    "retorno": r1_input.strip(),
                    "saida": s1_input.strip(),
                    "obs": obs_input.strip().upper(),
                    "cursos": h_curso_val,
                }
                try:
                    if row_edit.get("ID"):
                        supabase.table("ponto").update(dados_update).eq(
                            "id", row_edit["ID"]
                        ).execute()
                    else:
                        dados_update["funcionario"] = usuario
                        dados_update["data"] = row_edit["Data"]
                        supabase.table("ponto").insert(dados_update).execute()

                    st.success("Registro atualizado com sucesso!")
                    st.session_state.edit_row = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            if btn_cancelar:
                st.session_state.edit_row = None
                st.rerun()

    st.markdown("---")

    # ------------------------------------------
    # CÁLCULOS TOTAIS E CONFIGURAÇÕES
    # ------------------------------------------
    saldo_mes = total_comp_acumulado - total_dev_acumulado
    exibir_extras = max(0, saldo_mes)
    exibir_dev = abs(min(0, saldo_mes))
    bonus_abatimento = exibir_extras + total_cursos
    falta_fac_final = max(0, meta_mes_atual - bonus_abatimento)

    txt_meta = (
        "META OK ✅"
        if (meta_mes_atual > 0 and falta_fac_final <= 0)
        else (
            f"Faltam {formatar_horas(falta_fac_final)}"
            if meta_mes_atual > 0
            else "00:00:00"
        )
    )

    totais_dict = {
        "total": formatar_horas(total_trabalhado_bruto),
        "comp": formatar_horas(exibir_extras),
        "dev": formatar_horas(exibir_dev),
        "cursos": formatar_horas(total_cursos),
        "fac": txt_meta,
    }

    # Painel de métricas
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Trabalhado", totais_dict["total"])
    m2.metric("Extras (Líquido)", totais_dict["comp"])
    m3.metric("Cursos", totais_dict["cursos"])
    m4.metric("Devedoras", totais_dict["dev"])
    m5.metric("Falta Facultativo", txt_meta)

    st.markdown("---")

    # Painel de Configurações do Servidor
    st.subheader("⚙️ Configurações do Servidor")
    with st.form("form_config_servidor"):
        col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
        with col_cfg1:
            cfg_base = st.text_input(
                "Hora base do servidor:",
                value=formatar_horas(base_hora_atual),
            )
        with col_cfg2:
            cfg_meta = st.text_input(
                "Meta de Hora de Ponto Facultativo do mês:",
                value=formatar_horas(meta_mes_atual),
            )
        with col_cfg3:
            cfg_cargo = st.text_input(
                "Cargo:", value=cargo_atual
            )

        btn_salvar_cfg = st.form_submit_button("💾 SALVAR CONFIGURAÇÕES")

        if btn_salvar_cfg:
            base_dec = converter_texto_para_decimal(cfg_base)
            meta_dec = converter_texto_para_decimal(cfg_meta)
            novo_cargo = cfg_cargo.strip().upper()
            jornada_int = int(round(base_dec))

            try:
                supabase.table("usuarios").update(
                    {"jornada": jornada_int, "cargo": novo_cargo}
                ).eq("usuario", usuario.lower()).execute()

                payload_meta = {
                    "usuario": usuario.lower(),
                    "mes": str(mes_sel),
                    "ano": str(ano_sel),
                    "meta": meta_dec,
                }

                supabase.table("metas_mensais").upsert(
                    payload_meta, on_conflict="usuario, mes, ano"
                ).execute()

                st.success("Configurações salvas no banco com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar configurações: {e}")

    # ------------------------------------------
    # GERADOR DE PDF DE EXPORTAÇÃO
    # ------------------------------------------
    st.markdown("---")
    pdf_bytes = gerar_pdf_bytes(
        usuario,
        mes_sel,
        ano_sel,
        dados_memoria,
        totais_dict,
        cfg_cargo if 'cfg_cargo' in locals() else cargo_atual,
    )

    st.download_button(
        label="📄 BAIXAR PDF DA FOLHA DE PONTO",
        data=pdf_bytes,
        file_name=f"Ponto_{usuario}_{mes_sel}_{ano_sel}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    # Assinatura digital do rodapé
    st.markdown(
        """
        <div class="rodape-assinatura">
            Desenvolvido por <i>Jefferson Espanha</i> &copy; 2026 | Procuradoria do Município
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
