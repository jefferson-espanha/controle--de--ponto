import os
import time
from supabase import Client, create_client
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS
# ==========================================
st.set_page_config(
    page_title="Login - Sistema de Ponto",
    page_icon="⏱️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Estilização CSS para reproduzir o visual do PyQt6
st.markdown(
    """
    <style>
    /* Fundo da tela principal */
    .stApp {
        background-color: #f4f6f8;
    }

    /* Esconde menu e rodapé padrão do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Card Central de Login */
    [data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 30px;
        box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.08);
        border: 1px solid #e2e8f0;
    }

    /* Rótulos dos campos */
    label {
        font-weight: bold !important;
        color: #2c3e50 !important;
        font-size: 14px !important;
    }

    /* Inputs de texto */
    div[data-baseweb="input"] {
        border-radius: 4px !important;
        background-color: white !important;
    }

    /* Botão Verde ENTRAR */
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #27ae60 !important;
        color: white !important;
        font-weight: bold !important;
        font-size: 14px !important;
        border-radius: 4px !important;
        padding: 10px !important;
        border: none !important;
        width: 100% !important;
        margin-top: 10px !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #219150 !important;
    }

    /* Botão Azul CADASTRAR */
    .btn-cadastrar > button {
        background-color: #2980b9 !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px !important;
    }
    .btn-cadastrar > button:hover {
        background-color: #1f6391 !important;
    }

    /* Botão Vermelho EXCLUIR */
    .btn-excluir > button {
        background-color: #c0392b !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px !important;
    }
    .btn-excluir > button:hover {
        background-color: #962d22 !important;
    }

    /* Estilização da Assinatura no Rodapé */
    .rodape-assinatura {
        text-align: center;
        color: #000000;
        font-size: 14px;
        font-weight: bold;
        letter-spacing: 0.5px;
        padding-top: 25px;
        padding-bottom: 10px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. CONEXÃO E CONFIGURAÇÃO BANCO SUPABASE
# ==========================================
SUPABASE_URL = "https://rqzenyisowodympiheod.supabase.co"
SUPABASE_KEY = "sb_publishable_yKGWZScOzAmahuDH62c0aw_SjlyvXjj"


@st.cache_resource
def init_supabase() -> Client:
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Erro ao inicializar o Supabase: {e}")
        st.stop()


supabase = init_supabase()

def configurar_banco_inicial():
    """Garante que o admin inicial exista no banco"""
    try:
        res = (
            supabase.table("usuarios")
            .select("*")
            .eq("usuario", "jefferson.espanha")
            .execute()
        )
        if not res.data:
            admin_inicial = {
                "usuario": "jefferson.espanha",
                "senha": "odio",
                "tipo": "admin",
                "cargo": "Diretor",
                "jornada": 8,
                "primeiro_acesso": 0,
            }
            supabase.table("usuarios").insert(admin_inicial).execute()
    except Exception:
        pass


configurar_banco_inicial()

# Gerenciamento de Sessão
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "primeiro_acesso" not in st.session_state:
    st.session_state.primeiro_acesso = False
if "modal_adm" not in st.session_state:
    st.session_state.modal_adm = None


# ==========================================
# 3. INTERFACE DE LOGIN
# ==========================================
def render_login():
    # Exibição do Logo
    col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
    with col_img2:
        if os.path.exists("ponto.png"):
            st.image("ponto.png", use_container_width=True)
        else:
            st.markdown(
                "<h2 style='text-align: center; color: #2c3e50;'>SISTEMA DE"
                " PONTO</h2>",
                unsafe_allow_html=True,
            )

    # Form do Login
    with st.form("form_login"):
        usuario = st.text_input("USUÁRIO:").strip().lower()
        senha = st.text_input("SENHA:", type="password").strip()
        btn_entrar = st.form_submit_button("ENTRAR")

    if btn_entrar:
        if not usuario or not senha:
            st.warning("Preencha todos os campos do login.")
        else:
            try:
                res = (
                    supabase.table("usuarios")
                    .select("*")
                    .eq("usuario", usuario)
                    .eq("senha", senha)
                    .execute()
                )
                if res.data:
                    dados = res.data[0]
                    usuario_logado = dados["usuario"]
                    tipo_logado = dados.get("tipo", "user")
                    is_primeiro = int(dados.get("primeiro_acesso", 0))

                    if is_primeiro == 1:
                        st.session_state.temp_usuario = usuario_logado
                        st.session_state.primeiro_acesso = True
                        st.rerun()
                    else:
                        st.session_state.usuario_logado = usuario_logado
                        st.session_state.tipo_logado = tipo_logado
                        st.rerun()
                else:
                    st.error("Login ou Senha Incorretos!")
            except Exception as e:
                st.error(f"Falha ao conectar com Supabase: {e}")

    # Modal "Esqueceu sua senha?"
    with st.expander("Esqueceu sua senha?"):
        with st.form("form_esqueci"):
            u_reset = st.text_input("Informe seu Usuário:").strip().lower()
            s_reset = st.text_input("Nova Senha:", type="password").strip()
            btn_reset = st.form_submit_button("REDEFINIR SENHA")

            if btn_reset:
                if not u_reset or not s_reset:
                    st.warning("Preencha o usuário e a nova senha.")
                else:
                    try:
                        res = (
                            supabase.table("usuarios")
                            .select("*")
                            .eq("usuario", u_reset)
                            .execute()
                        )
                        if not res.data:
                            st.error("Usuário não encontrado!")
                        else:
                            supabase.table("usuarios").update(
                                {"senha": s_reset}
                            ).eq("usuario", u_reset).execute()
                            st.success(
                                "Senha redefinida com sucesso! Faça login"
                                " novamente."
                            )
                    except Exception as e:
                        st.error(f"Erro ao redefinir senha: {e}")

    # Botões Administrativos
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="btn-cadastrar">', unsafe_allow_html=True)
        if st.button("CADASTRAR", use_container_width=True):
            st.session_state.modal_adm = (
                "cadastrar"
                if st.session_state.modal_adm != "cadastrar"
                else None
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="btn-excluir">', unsafe_allow_html=True)
        if st.button("EXCLUIR", use_container_width=True):
            st.session_state.modal_adm = (
                "excluir" if st.session_state.modal_adm != "excluir" else None
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # Painel Administrativo de Cadastro
    if st.session_state.modal_adm == "cadastrar":
        st.markdown("---")
        st.subheader("Novo Servidor")
        chave = st.text_input(
            "Chave Administrativa:", type="password", key="chave_cad"
        )
        if chave == "odio":
            with st.form("form_cad"):
                u_ent = (
                    st.text_input("Nome de Usuário (Login):").strip().lower()
                )
                s_ent = st.text_input("Senha Provisória:").strip()
                cargos = [
                    "Oficial Administrativo",
                    "Assessor I",
                    "Assessor II",
                    "Diretor",
                    "Diretora",
                    "Chefe de Divisão",
                    "Estagiário",
                    "Estagiária",
                    "Adjunto Procurador-Geral",
                    "Procurador-Geral",
                ]
                cargo = st.selectbox("Cargo:", cargos)
                tipo = st.selectbox("Nível de Acesso:", ["user", "admin"])
                btn_salvar = st.form_submit_button("CADASTRAR SERVIDOR")

                if btn_salvar:
                    if not u_ent or not s_ent:
                        st.error("Preencha usuário e senha!")
                    else:
                        jornada = 6 if "Estagiári" in cargo else 8
                        payload = {
                            "usuario": u_ent,
                            "senha": s_ent,
                            "tipo": tipo,
                            "cargo": cargo,
                            "jornada": jornada,
                            "primeiro_acesso": 1,
                        }
                        try:
                            supabase.table("usuarios").insert(payload).execute()
                            st.success(
                                f"Usuário '{u_ent}' cadastrado!\nSenha"
                                f" provisória: {s_ent}"
                            )
                            st.session_state.modal_adm = None
                        except Exception as e:
                            st.error(
                                f"Este usuário já existe ou ocorreu um erro: {e}"
                            )
        elif chave and chave != "odio":
            st.error("Chave Incorreta!")

    # Painel Administrativo de Exclusão
    elif st.session_state.modal_adm == "excluir":
        st.markdown("---")
        st.subheader("Excluir Usuário")
        chave = st.text_input(
            "Chave Administrativa:", type="password", key="chave_exc"
        )
        if chave == "odio":
            try:
                res = supabase.table("usuarios").select("usuario").execute()
                users = [
                    r["usuario"]
                    for r in res.data
                    if r["usuario"] != "jefferson.espanha"
                ]
                user_del = st.selectbox(
                    "Selecione o usuário para excluir:", users
                )
                if st.button("EXCLUIR AGORA"):
                    supabase.table("usuarios").delete().eq(
                        "usuario", user_del
                    ).execute()
                    st.success("Usuário removido com sucesso!")
                    st.session_state.modal_adm = None
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")
        elif chave and chave != "odio":
            st.error("Chave Incorreta!")


# ==========================================
# 4. TROCA DE SENHA NO PRIMEIRO ACESSO
# ==========================================
def render_troca_senha():
    st.subheader("Alterar Senha")
    st.info(
        f"Olá, {st.session_state.temp_usuario}!\nPrimeiro acesso"
        " detectado.\nCrie sua senha definitiva:"
    )

    with st.form("form_troca_senha"):
        nova_s = st.text_input("Nova Senha:", type="password").strip()
        btn_salvar = st.form_submit_button("SALVAR NOVA SENHA")

        if btn_salvar:
            if len(nova_s) < 3:
                st.warning("A senha deve ter pelo menos 3 caracteres.")
            else:
                try:
                    supabase.table("usuarios").update(
                        {"senha": nova_s, "primeiro_acesso": 0}
                    ).eq("usuario", st.session_state.temp_usuario).execute()
                    st.success(
                        "Senha atualizada com sucesso!\nFaça login novamente."
                    )
                    st.session_state.primeiro_acesso = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")


# ==========================================
# 5. TELA PRINCIPAL (PÓS-LOGIN)
# ==========================================
def render_main():
    st.sidebar.title(f"Usuário: {st.session_state.usuario_logado}")
    if st.sidebar.button("Sair"):
        st.session_state.usuario_logado = None
        st.rerun()

    st.title("Sistema de Ponto")
    st.write("Sua aplicação principal foi iniciada com sucesso.")


# ==========================================
# 6. FLUXO DE EXECUÇÃO E ASSINATURA
# ==========================================
if st.session_state.primeiro_acesso:
    render_troca_senha()
elif st.session_state.usuario_logado:
    render_main()
else:
    render_login()

# Rodapé de Assinatura Digital
st.markdown(
    """
    <div class="rodape-assinatura">
        Desenvolvido por <i>Jefferson Espanha</i> &copy; 2026 | Procuradoria do Município
    </div>
    """,
    unsafe_allow_html=True,
)
