import tempfile
import requests
import os
import sys
import re
import threading
import json
import webbrowser 
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import datetime
from PIL import Image

# --- TEMA RETRÔ (WINDOWS 95/NT) ---
COLOR_WIN_GREY = "#d4d0c8"
COLOR_WIN_BLUE = "#000080"
COLOR_WIN_BORDER = "#808080"

# --- CONFIGURAÇÃO DE AMBIENTE ---
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")

ARQUIVO_RECEPTORES = "banco_receptores.json"

def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r") as f: return json.load(f)
        except: return {}
    return {}

def salvar_json(caminho, dados):
    with open(caminho, "w") as f: json.dump(dados, f, indent=4)

banco_receptores = carregar_json(ARQUIVO_RECEPTORES)

def limpar_sequencia(texto):
    linhas = texto.splitlines()
    if not linhas: return ""
    corpo = "".join([l for l in linhas if not l.startswith(">")])
    return re.sub(r'[^A-Z]', '', corpo.upper())

class JanelaSelecaoMultipla(ctk.CTkToplevel):
    def __init__(self, parent, selecionados_atual, callback):
        super().__init__(parent)
        self.title("Selecionar Alvos")
        self.geometry("450x550")
        self.configure(fg_color=COLOR_WIN_GREY) # Fundo Cinza
        self.attributes("-topmost", True)
        self.after(200, lambda: self._carregar_icone(parent.caminho_ico))
        self.callback = callback
        self.vars = {}
        
        # Busca estilo Input clássico
        self.entry_busca = ctk.CTkEntry(self, placeholder_text="Buscar...", width=400, corner_radius=0, border_width=2)
        self.entry_busca.pack(pady=10, padx=10)
        self.entry_busca.bind("<KeyRelease>", lambda e: self.atualizar_lista())
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=0, border_width=1)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkButton(self, text="CONFIRMAR SELEÇÃO", fg_color=COLOR_WIN_GREY, text_color="black", 
                      border_width=2, border_color=COLOR_WIN_BORDER, corner_radius=0, 
                      font=("Arial", 12, "bold"), hover_color="#ffffff", command=self.confirmar).pack(pady=10)
        self.atualizar_lista(selecionados_atual)

    def _carregar_icone(self, caminho):
        try: self.iconbitmap(caminho)
        except: pass

    def atualizar_lista(self, selecionados=None):
        termo = self.entry_busca.get().lower()
        for w in self.scroll.winfo_children(): w.destroy()
        cores = {"Bacteriana": "#8e44ad", "Parasitária": "#27ae60", "Fúngica": "#d35400", "Humana": "#2980b9", "Animal": "#16a085", "Viral": "#c0392b", "Proteômica/Outros": "#7f8c8d"}
        for nome in sorted(banco_receptores.keys()):
            tipo = banco_receptores[nome].get("tipo", "Proteômica/Outros")
            if termo in nome.lower() or termo in tipo.lower():
                cor_item = cores.get(tipo, "#7f8c8d")
                ja_selecionado = (selecionados and nome in selecionados) or (nome in self.vars and self.vars[nome].get())
                var = ctk.BooleanVar(value=ja_selecionado)
                self.vars[nome] = var
                item_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
                item_frame.pack(fill="x", padx=10, pady=2)
                cb = ctk.CTkCheckBox(item_frame, text=f"{nome} | {tipo.upper()}", variable=var, 
                                     text_color=cor_item, font=("Arial", 11, "bold"), corner_radius=0)
                cb.pack(side="left")

    def confirmar(self):
        escolhidos = [nome for nome, v in self.vars.items() if v.get()]
        self.callback(escolhidos)
        self.destroy()

class NexusApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nexus - Interações Proteícas")
        self.geometry("800x500") 
        self.minsize(800, 500) 
        self.configure(fg_color=COLOR_WIN_GREY)
        ctk.set_appearance_mode("light") 
        self.receptores_selecionados = []
        self.resultados_armazenados = []

        if getattr(sys, 'frozen', False): caminho_base = os.path.dirname(sys.executable)
        else: caminho_base = os.path.dirname(os.path.abspath(__file__))

        self.caminho_ico = os.path.join(caminho_base, "NexusIco.ico")
        try: self.iconbitmap(self.caminho_ico)
        except: pass

        try:
            img_lixeira = Image.open(os.path.join(caminho_base, "lixeira.png"))
            self.icon_lixeira = ctk.CTkImage(light_image=img_lixeira, dark_image=img_lixeira, size=(20, 20))
        except: self.icon_lixeira = None

        # Splash Screen Clássica
        self.overlay = ctk.CTkFrame(self, fg_color=COLOR_WIN_GREY, corner_radius=0)
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay_content = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.overlay_content.place(relx=0.5, rely=0.5, anchor="center")

        try:
            img_logo = Image.open(os.path.join(caminho_base, "Nexus Logo.png"))
            foto_logo = ctk.CTkImage(light_image=img_logo, dark_image=img_logo, size=(247, 193))
            self.label_logo = ctk.CTkLabel(self.overlay_content, image=foto_logo, text="")
            self.label_logo.pack(pady=10)
        except: ctk.CTkLabel(self.overlay_content, text="🧬", font=("Arial", 60)).pack(pady=10)

        self.label_status = ctk.CTkLabel(self.overlay_content, text="Inicializando Programa...", font=("Arial", 14), text_color="black")
        self.label_status.pack(pady=5)
        self.progress = ctk.CTkProgressBar(self.overlay_content, width=400, mode="indeterminate", progress_color=COLOR_WIN_BLUE, corner_radius=0)
        self.progress.start()
        self.progress.pack(pady=20)
        threading.Thread(target=self.carregar_motores_ai, daemon=True).start()

    def carregar_motores_ai(self):
        global torch, AutoTokenizer, EsmModel, FPDF
        try:
            import torch
            from fpdf import FPDF
            from transformers import AutoTokenizer, EsmModel
            MODEL_NAME = "facebook/esm2_t6_8M_UR50D"
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            self.model = EsmModel.from_pretrained(MODEL_NAME)
            self.after(0, self.finalizar_carregamento)
        except Exception as e: self.after(0, lambda: messagebox.showerror("Erro Crítico", str(e)))

    def finalizar_carregamento(self):
        self.overlay.destroy()
        self.setup_ui()

    def setup_ui(self):
        # Barra de botões superior
        header_links = ctk.CTkFrame(self, fg_color="transparent", height=40)
        header_links.pack(fill="x", padx=10, pady=(10, 0))
        
        btn_style = {"text_color": "white", "corner_radius": 0, "font": ("Arial", 11, "bold"), "height": 30}
        ctk.CTkButton(header_links, text="UniProt", width=100, fg_color="#005a84", command=lambda: webbrowser.open("https://www.uniprot.org/"), **btn_style).pack(side="left", padx=5)
        ctk.CTkButton(header_links, text="NCBI Protein", width=100, fg_color="#2271b1", command=lambda: webbrowser.open("https://www.ncbi.nlm.nih.gov/protein/"), **btn_style).pack(side="left", padx=5)

        self.tabview = ctk.CTkTabview(self, corner_radius=0, segmented_button_selected_color=COLOR_WIN_BLUE)
        self.tabview.pack(pady=(5, 10), padx=10, fill="both", expand=True)
        self.tab_analise = self.tabview.add("Análise de Interação")
        self.tab_banco_rec = self.tabview.add("Gerenciar Banco de Proteínas")
        self.setup_aba_analise()
        self.setup_aba_banco()

    def setup_aba_analise(self):
        parent = self.tab_analise
        self.toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        self.toolbar.pack(pady=10, padx=20, fill="x")
        
        # Botões com bordas retas (corner_radius=0)
        btn_cfg = {"corner_radius": 0, "height": 35}
        ctk.CTkButton(self.toolbar, text="CARREGAR FASTA", command=lambda: self.abrir_arquivo(self.textbox, self.entry_nome_viral), fg_color="#34495e", width=120, **btn_cfg).grid(row=0, column=0, padx=3)
        self.btn_pdf = ctk.CTkButton(self.toolbar, text="SALVAR PDF", command=self.exportar_pdf, fg_color="#c0392b", state="disabled", width=120, font=("Arial", 11, "bold"), **btn_cfg)
        self.btn_pdf.grid(row=0, column=1, padx=3)
        self.btn_selecionar = ctk.CTkButton(self.toolbar, text="SELECIONAR ALVOS NO BANCO", command=self.abrir_menu_selecao, width=250, fg_color="#2980b9", **btn_cfg)
        self.btn_selecionar.grid(row=0, column=2, padx=10)
        ctk.CTkButton(self.toolbar, text="ANALISAR", command=self.processar, fg_color="#27ae60", width=120, font=("Arial", 12, "bold"), **btn_cfg).grid(row=0, column=3, padx=3)
        ctk.CTkButton(self.toolbar, text="NOVA ANÁLISE", command=self.resetar, fg_color="#7f8c8d", width=120, **btn_cfg).grid(row=0, column=4, padx=3)
        
        self.toolbar.grid_columnconfigure(2, weight=1)
        self.entry_nome_viral = ctk.CTkEntry(parent, placeholder_text="NOME DA PROTEÍNA EM ESTUDO", width=600, height=35, corner_radius=0)
        self.entry_nome_viral.pack(pady=(10, 5), padx=30)
        self.textbox = ctk.CTkTextbox(parent, height=120, border_width=2, corner_radius=0)
        self.textbox.insert("1.0", "INSIRA A SEQUÊNCIA DE AMINOÁCIDOS OU CARREGUE UM ARQUIVO FASTA...")
        self.textbox.pack(pady=5, padx=30, fill="x")
        
        self.txt_status_final = ctk.CTkLabel(parent, text="", font=("Arial", 12, "italic"))
        self.txt_status_final.pack()
        
        self.scroll_frame = ctk.CTkScrollableFrame(parent, fg_color="white", border_width=1, corner_radius=0)
        self.scroll_frame.pack(pady=10, padx=30, fill="both", expand=True)
        self.header_table = ctk.CTkFrame(self.scroll_frame, fg_color="#f2f4f7", corner_radius=0)
        self.header_table.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(self.header_table, text="PROTEÍNA ALVO / CATEGORIA", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=20)
        ctk.CTkLabel(self.header_table, text="AFINIDADE (%)", font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="e", padx=40)
        self.header_table.grid_columnconfigure(0, weight=1)

    def abrir_menu_selecao(self): JanelaSelecaoMultipla(self, self.receptores_selecionados, self.finalizar_selecao)
    def finalizar_selecao(self, lista):
        self.receptores_selecionados = lista
        qtd = len(lista)
        self.btn_selecionar.configure(text=f"{qtd} ALVOS SELECIONADOS" if qtd > 0 else "SELECIONAR ALVOS NO BANCO")

    def setup_aba_banco(self):
        parent = self.tab_banco_rec
        split = ctk.CTkFrame(parent, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=10, pady=10)
        left = ctk.CTkFrame(split, width=320, border_width=1, corner_radius=0)
        left.pack(side="left", fill="both", expand=False, padx=5)
        left.pack_propagate(False)
        
        ctk.CTkLabel(left, text="CADASTRAR NOVO ALVO", font=("Arial", 16, "bold")).pack(pady=15)
        self.entry_nome = ctk.CTkEntry(left, placeholder_text="Nome da Proteína", width=280, corner_radius=0); self.entry_nome.pack(pady=5)
        ctk.CTkLabel(left, text="Categoria Biológica:", font=("Arial", 12, "bold")).pack(pady=(5,0))
        self.tipo_receptor = ctk.CTkOptionMenu(left, values=["SELECIONAR", "Bacteriana", "Parasitária", "Fúngica", "Humana", "Animal", "Viral", "Proteômica/Outros"], width=280, fg_color="#34495e", corner_radius=0)
        self.tipo_receptor.pack(pady=5); self.tipo_receptor.set("SELECIONAR")
        ctk.CTkButton(left, text="CARREGAR FASTA", command=lambda: self.abrir_arquivo(self.entry_seq, self.entry_nome), fg_color="#34495e", width=280, corner_radius=0).pack(pady=5)
        self.entry_seq = ctk.CTkTextbox(left, width=280, height=100, corner_radius=0); self.entry_seq.pack(pady=5)
        ctk.CTkButton(left, text="SALVAR NO BANCO", command=self.adicionar_receptor, fg_color="#27ae60", width=250, height=45, corner_radius=0).pack(pady=15)
        
        right = ctk.CTkFrame(split, border_width=1, corner_radius=0)
        right.pack(side="right", fill="both", expand=True, padx=5)
        self.scroll_rec = ctk.CTkScrollableFrame(right, fg_color="white", corner_radius=0)
        self.scroll_rec.pack(pady=10, padx=10, fill="both", expand=True)
        self.atualizar_listas_rec()

    def atualizar_listas_rec(self):
        for w in self.scroll_rec.winfo_children(): w.destroy()
        for nome in sorted(banco_receptores.keys()):
            tipo = banco_receptores[nome].get("tipo", "N/I")
            f = ctk.CTkFrame(self.scroll_rec, fg_color="#f8f9fa", corner_radius=0)
            f.pack(fill="x", pady=2)
            ctk.CTkButton(f, text=f"{nome} | {tipo.upper()}", anchor="w", fg_color="transparent", text_color="black", command=lambda n=nome: self.carregar_para_edicao(n)).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(f, text="" if self.icon_lixeira else "🗑", image=self.icon_lixeira, width=35, fg_color="#95a5a6", hover_color="#7f8c8d", corner_radius=0, command=lambda n=nome: self.excluir_receptor(n)).pack(side="right", padx=2)

    def adicionar_receptor(self):
        n, s, t = self.entry_nome.get().strip(), limpar_sequencia(self.entry_seq.get("1.0", "end-1c")), self.tipo_receptor.get()
        if t == "SELECIONAR": messagebox.showwarning("Atenção", "POR FAVOR, SELECIONE A CATEGORIA!"); return
        if n and len(s) > 10:
            banco_receptores[n] = {"seq": s, "tipo": t}
            salvar_json(ARQUIVO_RECEPTORES, banco_receptores)
            self.atualizar_listas_rec()
            messagebox.showinfo("Sucesso", f"Proteína {n} salva!")
            self.entry_nome.delete(0, 'end'); self.entry_seq.delete("1.0", "end"); self.tipo_receptor.set("SELECIONAR")
        else: messagebox.showwarning("Erro", "PREENCHA NOME E SEQUÊNCIA.")

    def excluir_receptor(self, nome):
        if messagebox.askyesno("Confirmar", f"Remover '{nome}'?"):
            if nome in banco_receptores: del banco_receptores[nome]; salvar_json(ARQUIVO_RECEPTORES, banco_receptores); self.atualizar_listas_rec()

    def carregar_para_edicao(self, nome):
        d = banco_receptores.get(nome)
        if d: self.entry_nome.delete(0, 'end'); self.entry_nome.insert(0, nome); self.entry_seq.delete("1.0", "end"); self.entry_seq.insert("1.0", d.get("seq", "")); self.tipo_receptor.set(d.get("tipo", "SELECIONAR"))

    def abrir_arquivo(self, target, entry_nome=None):
        c = filedialog.askopenfilename(filetypes=[("FASTA", "*.fasta *.txt")])
        if c: 
            with open(c, 'r') as f:
                conteudo = f.read()
                match = re.search(r'^>(.*?)(?:\s|$)', conteudo)
                if match and entry_nome:
                    entry_nome.delete(0, 'end'); entry_nome.insert(0, match.group(1).strip())
                target.delete("1.0", "end"); target.insert("1.0", limpar_sequencia(conteudo))

    def resetar(self):
        self.textbox.delete("1.0", "end"); self.entry_nome_viral.delete(0, 'end'); self.receptores_selecionados = []
        self.btn_selecionar.configure(text="SELECIONAR ALVOS NO BANCO"); self.btn_pdf.configure(state="disabled"); self.txt_status_final.configure(text="")
        for w in self.scroll_frame.winfo_children(): 
            if w != self.header_table: w.destroy()

    def processar(self):
        if not self.receptores_selecionados: messagebox.showwarning("Atenção", "SELECIONE AO MENOS UM ALVO"); return
        seq = limpar_sequencia(self.textbox.get("1.0", "end-1c"))
        if len(seq) < 10: messagebox.showwarning("Atenção", "SEQUÊNCIA INVÁLIDA"); return
        nome_amostra = self.entry_nome_viral.get().strip()
        if not nome_amostra: messagebox.showwarning("Atenção", "INSIRA O NOME DA PROTEÍNA"); return
        self.txt_status_final.configure(text="Calculando...", text_color="#2980b9")
        threading.Thread(target=self.rodar_analise_ia, args=(seq, self.receptores_selecionados), daemon=True).start()

    def rodar_analise_ia(self, seq_estudo, escolhidos):
        try:
            import math; from sklearn.metrics.pairwise import cosine_similarity
            v_estudo = self.gerar_assinatura(seq_estudo)
            res = []
            for nome in escolhidos:
                v_rec = self.gerar_assinatura(banco_receptores[nome]["seq"])
                sim = float(cosine_similarity(v_estudo, v_rec)[0][0])
                score = (1 / (1 + math.exp(-28 * (sim - 0.85)))) * 100
                if sim < 0.83: score *= 0.1
                res.append((nome, score, banco_receptores[nome].get("tipo", "Desconhecido")))
            res.sort(key=lambda x: x[1], reverse=True)
            self.resultados_armazenados = res
            self.after(0, self.sucesso_analise)
        except Exception as e: self.after(0, lambda: messagebox.showerror("IA", str(e)))

    def gerar_assinatura(self, seq):
        inputs = self.tokenizer(seq, return_tensors="pt", truncation=True, max_length=1024)
        with torch.no_grad(): out = self.model(**inputs)
        return out.last_hidden_state.max(dim=1).values.numpy()

    def interpretar(self, af):
        if af >= 85: return "ALTO", "Interacao forte detectada.", "#27ae60"
        if af >= 60: return "MEDIO", "Possivel interacao moderada.", "#f39c12"
        if af >= 30: return "BAIXO", "Interacao improvavel ou fraca.", "#d35400"
        return "NULO", "Sem evidencia de interacao.", "#7f8c8d"

    def sucesso_analise(self):
        self.txt_status_final.configure(text="Análise Concluída!", text_color="#27ae60")
        self.btn_pdf.configure(state="normal")
        for w in self.scroll_frame.winfo_children(): 
            if w != self.header_table: w.destroy()
        for r in self.resultados_armazenados:
            label_formatado = f"{r[0]} | {r[2].upper()}"
            af = r[1]
            st, desc, cor = self.interpretar(af)
            row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=label_formatado, font=("Arial", 12, "bold")).pack(side="left", padx=20)
            ctk.CTkLabel(row, text=f"{af:.2f}% ({st})", font=("Courier", 14, "bold"), text_color=cor).pack(side="right", padx=40)

    def exportar_pdf(self):
        nome_amostra = self.entry_nome_viral.get().strip()
        nome_limpo = re.sub(r'[^\w\s-]', '', nome_amostra).strip()
        loc = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Nexus_{nome_limpo}")
        
        if loc:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 18)
                pdf.cell(190, 15, "Nexus - Relatorio", ln=True, align='C')
                
                pdf.set_font("Arial", "B", 10)
                pdf.cell(190, 8, f"AMOSTRA: {nome_amostra.upper()}", ln=True)
                pdf.cell(190, 8, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
                pdf.ln(5)

                pdf.set_font("Arial", "B", 10)
                pdf.set_fill_color(220, 220, 220)
                
                pdf.cell(50, 10, "Proteina Alvo", 1, 0, 'C', 1)
                pdf.cell(35, 10, "Categoria", 1, 0, 'C', 1)
                pdf.cell(35, 10, "Afinidade (%)", 1, 0, 'C', 1)
                pdf.cell(70, 10, "Interpretacao", 1, 1, 'C', 1)

                pdf.set_font("Arial", "", 9)
                for r in self.resultados_armazenados:
                    st, ds, _ = self.interpretar(r[1])
                    p_nome = str(r[0]).encode('latin-1', 'replace').decode('latin-1')[:25]
                    p_cat = str(r[2]).encode('latin-1', 'replace').decode('latin-1')
                    p_desc = ds.encode('latin-1', 'replace').decode('latin-1')

                    pdf.cell(50, 10, p_nome, 1)
                    pdf.cell(35, 10, p_cat, 1, 0, 'C')
                    pdf.cell(35, 10, f"{r[1]:.2f}% ({st})", 1, 0, 'C')
                    pdf.cell(70, 10, p_desc, 1, 1, 'L')
                
                pdf.ln(10)
                pdf.set_font("Arial", "I", 8)
                pdf.cell(0, 5, "Analise gerada via Nexus", ln=True, align='R')

                pdf.output(loc)
                messagebox.showinfo("Sucesso", "PDF gerado com sucesso!")
            except PermissionError:
                messagebox.showerror("Erro", "O arquivo PDF ja esta aberto em outro programa.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao gerar PDF: {str(e)}")

if __name__ == "__main__":
    app = NexusApp()

    app.mainloop()
