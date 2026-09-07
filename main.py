from calendar import monthrange
from datetime import datetime
import io
import os
# Define o caminho do diretório do script atual
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
import sys
import subprocess
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from supabase import Client, create_client

# ==========================================
# CONEXÃO BANCO DE DADOS
# ==========================================
SUPABASE_URL = "https://rqzenyisowodympiheod.supabase.co"
SUPABASE_KEY = "sb_publishable_yKGWZScOzAmahuDH62c0aw_SjlyvXjj"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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


def abrir_arquivo_pdf(caminho):
    try:
        if sys.platform == "win32":
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.run(["open", caminho])
        else:
            subprocess.run(["xdg-open", caminho])
    except Exception as e:
        print(f"Não foi possível abrir o PDF automaticamente: {e}")


def gerar_pdf_arquivo(
    usuario, mes, ano, df_exibicao, totais, cargo, caminho_saida
):
    c = canvas.Canvas(caminho_saida, pagesize=A4)
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
        c.drawString(
            1.5 * cm, h - 4.0 * cm, f"SERVIDOR: {str(usuario).upper()}"
        )
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

    for _, v in df_exibicao.iterrows():
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
        1.5 * cm, y_resumo - 0.4 * cm, f"Falta Ponto Facultativo: {totais['fac']}"
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
    abrir_arquivo_pdf(caminho_saida)

# ==========================================
# 2. MODAL DE EDIÇÃO COMPLETO
# ==========================================
class DialogEdicaoPonto(QDialog):

    def __init__(self, data_row, usuario, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"✏️ Editar Registro de Ponto - {data_row['Data']}"
        )
        self.setMinimumWidth(400)
        self.data_row = data_row
        self.usuario = usuario

        layout = QVBoxLayout(self)
        form = QFormLayout()

        ent_val = data_row.get("Entrada", "") or "00:00:00"
        alm_val = data_row.get("Almoço", "") or "00:00:00"
        ret_val = data_row.get("Retorno", "") or "00:00:00"
        sai_val = data_row.get("Saída", "") or "00:00:00"
        
        cur_raw = data_row.get("Cursos", 0.0)
        if isinstance(cur_raw, (float, int)):
            cur_val = formatar_horas(cur_raw) if cur_raw > 0 else "00:00:00"
        else:
            cur_val = str(cur_raw) if cur_raw else "00:00:00"

        self.input_e1 = QLineEdit(ent_val)
        self.input_a1 = QLineEdit(alm_val)
        self.input_r1 = QLineEdit(ret_val)
        self.input_s1 = QLineEdit(sai_val)
        self.input_obs = QLineEdit(data_row.get("Obs", ""))
        self.input_cursos = QLineEdit(cur_val)

        form.addRow("Entrada:", self.input_e1)
        form.addRow("Almoço:", self.input_a1)
        form.addRow("Retorno:", self.input_r1)
        form.addRow("Saída:", self.input_s1)
        form.addRow("Observação:", self.input_obs)
        form.addRow("Horas Curso:", self.input_cursos)

        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Atalhos Rápidos:</b>"))
        btn_grid = QHBoxLayout()

        for txt in ["FÉRIAS", "ABONADA", "ATESTADO", "FERIADO", "FACULTATIVO"]:
            b = QPushButton(txt)
            b.clicked.connect(
                lambda ch, t=txt: self.input_obs.setText(t)
            )
            btn_grid.addWidget(b)
        layout.addLayout(btn_grid)

        btn_prova = QPushButton("SEMANA DE PROVA")
        btn_prova.clicked.connect(
            lambda: self.input_obs.setText("SEMANA DE PROVA AH:02:45")
        )
        layout.addWidget(btn_prova)

        btn_salvar = QPushButton("💾 SALVAR REGISTRO")
        btn_salvar.setStyleSheet(
            "background-color: #0078D7; color: white; font-weight: bold;"
            " padding: 8px;"
        )
        btn_salvar.clicked.connect(self.salvar)
        layout.addWidget(btn_salvar)

    def salvar(self):
        h_curso_val = converter_texto_para_decimal(self.input_cursos.text().strip())

        dados = {
            "entrada": self.input_e1.text().strip(),
            "almoco": self.input_a1.text().strip(),
            "retorno": self.input_r1.text().strip(),
            "saida": self.input_s1.text().strip(),
            "obs": self.input_obs.text().strip().upper(),
            "cursos": h_curso_val,
        }

        try:
            if self.data_row.get("ID"):
                supabase.table("ponto").update(dados).eq(
                    "id", self.data_row["ID"]
                ).execute()
            else:
                dados["funcionario"] = self.usuario
                dados["data"] = self.data_row["Data"]
                supabase.table("ponto").insert(dados).execute()

            QMessageBox.information(
                self, "Sucesso", "Registro atualizado com sucesso!"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")


# ==========================================
# 3. JANELA PRINCIPAL
# ==========================================
class JanelaPonto(QMainWindow):

    def __init__(self, usuario="ADMIN"):
        super().__init__()
        self.usuario_atual = usuario
        self.setWindowTitle(f"Sistema de Ponto - {self.usuario_atual}")
        self.setGeometry(100, 100, 1280, 720)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        self.criar_topo_botoes()
        self.criar_barra_filtros()
        self.criar_tabela()
        self.criar_rodape()

        self.carregar_dados()

    def criar_topo_botoes(self):
        top_layout = QHBoxLayout()

        botoes = [
            ("ENTRADA", "#27ae60", "ENTRADA"),
            ("ALMOÇO", "#f39c12", "ALMOÇO"),
            ("RETORNO", "#2980b9", "RETORNO"),
            ("SAÍDA", "#c0392b", "SAÍDA"),
        ]

        for texto, cor, tipo in botoes:
            btn = QPushButton(texto)
            btn.setStyleSheet(
                f"background-color: {cor}; color: white; font-weight: bold;"
                " padding: 6px 20px;"
            )
            btn.clicked.connect(
                lambda checked, t=tipo: self.registrar_ponto_rapido(t)
            )
            top_layout.addWidget(btn)

        top_layout.addStretch()
        self.main_layout.addLayout(top_layout)

    def registrar_ponto_rapido(self, tipo):
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
                .eq("funcionario", self.usuario_atual)
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
                    "funcionario": self.usuario_atual,
                    "data": hoje,
                    "entrada": "",
                    "almoco": "",
                    "retorno": "",
                    "saida": "",
                    coluna: hora,
                }
                supabase.table("ponto").insert(nova_linha).execute()

            QMessageBox.information(
                self, "Ponto Registrado", f"{tipo} registrada às {hora}!"
            )
            self.carregar_dados()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao registrar ponto: {e}")

    def criar_barra_filtros(self):
        filter_layout = QHBoxLayout()

        self.combo_mes = QComboBox()
        self.combo_mes.addItems([f"{i:02d}" for i in range(1, 13)])
        self.combo_mes.setCurrentText(datetime.now().strftime("%m"))
        self.combo_mes.currentIndexChanged.connect(self.carregar_dados)

        self.combo_ano = QComboBox()
        self.combo_ano.addItems([str(a) for a in range(2024, 2031)])
        self.combo_ano.setCurrentText(datetime.now().strftime("%Y"))
        self.combo_ano.currentIndexChanged.connect(self.carregar_dados)

        filter_layout.addWidget(self.combo_mes)
        filter_layout.addWidget(self.combo_ano)
        filter_layout.addStretch()

        btn_pdf = QPushButton("📄 PDF")
        btn_pdf.setStyleSheet(
            "background-color: #c0392b; color: white; font-weight: bold;"
            " padding: 4px 15px;"
        )
        btn_pdf.clicked.connect(self.gerar_pdf)
        filter_layout.addWidget(btn_pdf)

        self.main_layout.addLayout(filter_layout)

    def criar_tabela(self):
        self.tabela = QTableWidget()
        colunas = [
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
        ]
        self.tabela.setColumnCount(len(colunas))
        self.tabela.setHorizontalHeaderLabels(colunas)

        header = self.tabela.horizontalHeader()
        for i in range(len(colunas)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela.itemDoubleClicked.connect(self.abrir_modal_edicao)
        self.main_layout.addWidget(self.tabela)

    def criar_rodape(self):
        bot_layout = QHBoxLayout()

        bot_layout.addWidget(QLabel("Hora base do servidor:"))
        self.input_base = QLineEdit("08:00:00")
        self.input_base.setFixedWidth(65)
        bot_layout.addWidget(self.input_base)

        bot_layout.addWidget(QLabel("Meta de Hora de Ponto Facultativo do mês:"))
        self.input_meta = QLineEdit("00:00:00")
        self.input_meta.setFixedWidth(65)
        bot_layout.addWidget(self.input_meta)

        bot_layout.addWidget(QLabel("Cargo:"))
        self.input_cargo = QLineEdit("")
        self.input_cargo.setFixedWidth(120)
        bot_layout.addWidget(self.input_cargo)

        btn_salvar_cfg = QPushButton("💾 SALVAR")
        btn_salvar_cfg.setStyleSheet(
            "background-color: #34495e; color: white; font-weight: bold;"
        )
        btn_salvar_cfg.clicked.connect(self.salvar_configuracoes)
        bot_layout.addWidget(btn_salvar_cfg)

        bot_layout.addSpacing(15)

        self.lbl_trab = QLabel("Trabalhado: 00:00:00")
        self.lbl_trab.setStyleSheet("font-weight: bold;")
        self.lbl_ext = QLabel("Extras (Líquido): 00:00:00")
        self.lbl_ext.setStyleSheet("color: green; font-weight: bold;")
        self.lbl_cur = QLabel("Cursos: 00:00:00")
        self.lbl_cur.setStyleSheet("color: purple; font-weight: bold;")
        self.lbl_dev = QLabel("Devedoras: 00:00:00")
        self.lbl_dev.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_fac = QLabel("Falta Ponto Facultativo: 00:00:00")
        self.lbl_fac.setStyleSheet("color: blue; font-weight: bold;")

        bot_layout.addWidget(self.lbl_trab)
        bot_layout.addWidget(self.lbl_ext)
        bot_layout.addWidget(self.lbl_cur)
        bot_layout.addWidget(self.lbl_dev)
        bot_layout.addWidget(self.lbl_fac)

        bot_layout.addStretch()
        self.main_layout.addLayout(bot_layout)

    def carregar_dados(self):
        mes_str = self.combo_mes.currentText()
        ano_str = self.combo_ano.currentText()
        mes_int, ano_int = int(mes_str), int(ano_str)
        _, ultimo_dia = monthrange(ano_int, mes_int)

        cargo_atual, base_hora_atual = obter_dados_usuario(self.usuario_atual)
        meta_mes_atual = obter_meta_mensal(self.usuario_atual, mes_str, ano_str)

        self.input_cargo.setText(cargo_atual)
        self.input_base.setText(formatar_horas(base_hora_atual))
        self.input_meta.setText(formatar_horas(meta_mes_atual))

        try:
            res = (
                supabase.table("ponto")
                .select("*")
                .eq("funcionario", self.usuario_atual)
                .execute()
            )
            mapa_pontos = {r["data"]: r for r in res.data}
        except Exception:
            mapa_pontos = {}

        self.tabela.setRowCount(ultimo_dia)
        self.dados_memoria = []

        (
            total_comp_acumulado,
            total_dev_acumulado,
            total_trabalhado_bruto,
            total_cursos,
        ) = (0.0, 0.0, 0.0, 0.0)

        linhas_exportar = []

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
            tem_ponto = any(x and x.strip() != "" for x in [e1, a1, r1, s1])
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

            # Ajuste automático de trazercadas com --------- nos sábados e domingos
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
            }
            self.dados_memoria.append(row_data)
            linhas_exportar.append(row_data)

            valores = [
                row_data["Data"],
                row_data["Dia"],
                ent_disp,
                alm_disp,
                ret_disp,
                sai_disp,
                tot_disp,
                comp_disp,
                dev_disp,
                obs_exibir,
            ]
            for col_idx, val in enumerate(valores):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabela.setItem(dia - 1, col_idx, item)

        self.df_exibicao = pd.DataFrame(linhas_exportar)

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

        self.lbl_trab.setText(
            f"Trabalhado: {formatar_horas(total_trabalhado_bruto)}"
        )
        self.lbl_ext.setText(
            f"Extras (Líquido): {formatar_horas(exibir_extras)}"
        )
        self.lbl_cur.setText(f"Cursos: {formatar_horas(total_cursos)}")
        self.lbl_dev.setText(f"Devedoras: {formatar_horas(exibir_dev)}")
        self.lbl_fac.setText(f"Falta Ponto Facultativo: {txt_meta}")

        self.totais_dict = {
            "total": formatar_horas(total_trabalhado_bruto),
            "comp": formatar_horas(exibir_extras),
            "dev": formatar_horas(exibir_dev),
            "cursos": formatar_horas(total_cursos),
            "fac": txt_meta,
        }

    def salvar_configuracoes(self):
        base_dec = converter_texto_para_decimal(self.input_base.text())
        meta_dec = converter_texto_para_decimal(self.input_meta.text())
        novo_cargo = self.input_cargo.text().strip().upper()
        mes, ano = self.combo_mes.currentText(), self.combo_ano.currentText()

        # Converte o valor da jornada (ex: 6.0) para número inteiro (ex: 6) para o Supabase
        jornada_int = int(round(base_dec))

        try:
            supabase.table("usuarios").update(
                {"jornada": jornada_int, "cargo": novo_cargo}
            ).eq("usuario", self.usuario_atual.lower()).execute()

            payload_meta = {
                "usuario": self.usuario_atual.lower(),
                "mes": str(mes),
                "ano": str(ano),
                "meta": meta_dec,
            }

            supabase.table("metas_mensais").upsert(
                payload_meta, on_conflict="usuario, mes, ano"
            ).execute()
            QMessageBox.information(
                self, "Sucesso", "Configurações salvas no banco com sucesso!"
            )
            self.carregar_dados()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")

    def gerar_pdf(self):
        caminho = f"Ponto_{self.usuario_atual}_{self.combo_mes.currentText()}_{self.combo_ano.currentText()}.pdf"
        try:
            gerar_pdf_arquivo(
                self.usuario_atual,
                self.combo_mes.currentText(),
                self.combo_ano.currentText(),
                self.df_exibicao,
                self.totais_dict,
                self.input_cargo.text(),
                caminho,
            )
            QMessageBox.information(
                self, "PDF Gerado", f"PDF gerado com sucesso!\nAbrindo {caminho}..."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro PDF", f"Falha ao gerar PDF: {e}")

    def abrir_modal_edicao(self, item):
        data_row = self.dados_memoria[item.row()]
        dialog = DialogEdicaoPonto(data_row, self.usuario_atual, self)
        if dialog.exec():
            self.carregar_dados()


def main(usuario="ADMIN"):
    window = JanelaPonto(usuario=usuario)
    window.showMaximized()
    return window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = main()
    sys.exit(app.exec())
