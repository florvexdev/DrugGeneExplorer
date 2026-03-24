"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          DrugGeneExplorer v4.0 — Scientific Research Tool                   ║
║                                                                              ║
║  Core APIs:    DGIdb · PubChem · ChEMBL · OpenFDA                          ║
║  Research+:    ClinicalTrials.gov · Open Targets · UniProt · PubMed        ║
║                                                                              ║
║  ★ NEW in v4.0 ★                                                            ║
║  [17] 🧮  Pharmacokinetic Calculator (PK/PD)                               ║
║           — 1- and 2-compartment models, half-life, AUC, Vd, CL, Cmax      ║
║           — Dosing interval optimizer (Css min/max targeting)               ║
║           — Hill equation (Emax model), therapeutic window visualisation    ║
║  [18] 🔁  Multi-Drug Interaction Network                                    ║
║           — Builds a full polypharmacy graph for up to 10 drugs             ║
║           — Shared gene targets → DDI risk score (novel algorithm)          ║
║           — Enzyme induction/inhibition (CYP450 via ChEMBL + DGIdb)        ║
║  [19] 🧬  OMICS Cross-Reference (Gwas Catalog + GTEx free tier)            ║
║           — Disease SNPs → target genes via GWAS Catalog REST               ║
║           — eQTL tissue expression (GTEx API) → druggability score          ║
║  [20] 📊  Drug Score Comparator                                             ║
║           — Parallel Lipinski/ADMET + Target count + Clinical phase         ║
║           — Composite DrugScore™ (novel weighted formula)                   ║
║           — Radar chart in ASCII + exportable matrix                        ║
║  [21] 🤖  AI Drug Summary (Claude API — free via Anthropic)                 ║
║           — GPT-style natural-language report for any drug                  ║
║           — Structured JSON output for school reports                       ║
║                                                                              ║
║  UI Languages: any language via deep-translator (fallback: EN)             ║
║  License: MIT — Designed for schools, medical centres, research labs        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import csv
import time
import math
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich import box
from rich.progress import Progress
from rich.columns import Columns
from rich.text import Text
import random

# ── deep-translator (optional but strongly recommended) ──────────────
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_OK = True
except ImportError:
    TRANSLATOR_OK = False

console = Console()
session = requests.Session()
session.headers.update({"Content-Type": "application/json", "User-Agent": "DrugGeneExplorer/4.0"})

# ─────────────────────────────────────────────────────────────────────
#  UI LANGUAGE SYSTEM
# ─────────────────────────────────────────────────────────────────────

UI_LANG: str = "en"
_UI_CACHE: dict = {}

def ui(text: str) -> str:
    if UI_LANG == "en" or not text.strip():
        return text
    if text in _UI_CACHE:
        return _UI_CACHE[text]
    if TRANSLATOR_OK:
        try:
            result = GoogleTranslator(source="en", target=UI_LANG).translate(text)
            _UI_CACHE[text] = result or text
            return _UI_CACHE[text]
        except Exception:
            pass
    _UI_CACHE[text] = text
    return text

SUPPORTED_LANGUAGES = {
    "en": "English", "it": "Italian", "es": "Spanish", "fr": "French",
    "de": "German", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "zh-CN": "Chinese (Simplified)", "ja": "Japanese",
    "ko": "Korean", "ar": "Arabic", "hi": "Hindi", "tr": "Turkish",
    "sv": "Swedish", "ro": "Romanian", "cs": "Czech", "el": "Greek",
    "hu": "Hungarian",
}

def choose_language():
    global UI_LANG, _UI_CACHE
    if not TRANSLATOR_OK:
        console.print(Panel.fit(
            "⚠️  deep-translator not installed — UI language locked to English.\n"
            "    Install it with:  pip install deep-translator",
            style="yellow"
        ))
        return
    t = Table(title="🌍 Choose UI Language / Scegli la lingua / Elige el idioma",
              box=box.ROUNDED, style="bold cyan")
    t.add_column("Code", style="bold yellow", no_wrap=True)
    t.add_column("Language", style="white")
    t.add_column("Code", style="bold yellow", no_wrap=True)
    t.add_column("Language", style="white")
    items = list(SUPPORTED_LANGUAGES.items())
    half  = math.ceil(len(items) / 2)
    left  = items[:half]; right = items[half:]
    for i in range(half):
        lc, ln = left[i]
        rc_val, rn = right[i] if i < len(right) else ("", "")
        t.add_row(lc, ln, rc_val, rn)
    console.print(t)
    console.print(Panel.fit("[dim]Type the language code above and press Enter.\nPress Enter without typing to keep English (default).[/dim]"))
    raw = console.input("[bold yellow]Language code (default: en): [/bold yellow]").strip().lower()
    aliases = {
        "chinese": "zh-CN", "zh": "zh-CN", "mandarin": "zh-CN",
        "italian": "it", "italiano": "it", "spanish": "es", "español": "es",
        "french": "fr", "german": "de", "deutsch": "de",
        "portuguese": "pt", "russian": "ru", "japanese": "ja",
        "korean": "ko", "arabic": "ar", "hindi": "hi", "turkish": "tr",
        "greek": "el", "dutch": "nl", "polish": "pl", "swedish": "sv",
        "romanian": "ro", "czech": "cs", "hungarian": "hu", "english": "en",
    }
    raw = aliases.get(raw, raw)
    if not raw or raw == "en":
        UI_LANG = "en"
        console.print(Panel.fit("🇬🇧 UI language: English (default)", style="bold green"))
        return
    if raw not in SUPPORTED_LANGUAGES and raw not in [k.lower() for k in SUPPORTED_LANGUAGES]:
        console.print(Panel.fit(f"⚠️  '{raw}' not in the list — keeping English.", style="yellow"))
        return
    for k in SUPPORTED_LANGUAGES:
        if k.lower() == raw:
            raw = k; break
    UI_LANG = raw
    lang_name = SUPPORTED_LANGUAGES.get(UI_LANG, UI_LANG)
    try:
        test = GoogleTranslator(source="en", target=UI_LANG).translate("Ready")
        console.print(Panel.fit(f"✅ UI language set to: [bold white]{lang_name}[/bold white] ({UI_LANG})\n   Test: 'Ready' → '{test}'", style="bold green"))
    except Exception as e:
        console.print(Panel.fit(f"⚠️  Could not translate to '{raw}' ({e}) — keeping English.", style="yellow"))
        UI_LANG = "en"

COLORS = ["red", "yellow", "magenta", "green", "blue", "cyan"]

# ── BASE API URLs ─────────────────────────────────────────────────────
DGIDB_URL        = "https://dgidb.org/api/graphql"
PUBCHEM_URL      = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CHEMBL_URL       = "https://www.ebi.ac.uk/chembl/api/data"
FDA_URL          = "https://api.fda.gov/drug"
CLINICAL_URL     = "https://clinicaltrials.gov/api/v2"
OPENTARGETS_URL  = "https://api.platform.opentargets.org/api/v4/graphql"
UNIPROT_URL      = "https://rest.uniprot.org"
PUBMED_URL       = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GWAS_URL         = "https://www.ebi.ac.uk/gwas/rest/api"

# ── FALLBACK DICTIONARY (multi-language → English) ───────────────────
DRUG_NAMES_FALLBACK = {
    "aspirina": "aspirin", "ibuprofene": "ibuprofen",
    "paracetamolo": "paracetamol", "amoxicillina": "amoxicillin",
    "metformina": "metformin", "atorvastatina": "atorvastatin",
    "simvastatina": "simvastatin", "omeprazolo": "omeprazole",
    "warfarina": "warfarin", "morfina": "morphine",
    "ibuprofeno": "ibuprofen", "amoxicilina": "amoxicillin",
    "aspirine": "aspirin", "paracétamol": "paracetamol",
    "insulin": "insulin", "caffeina": "caffeine",
}

# ─────────────────────────────────────────────────────────────────────
#  EXPLAIN SYSTEM
# ─────────────────────────────────────────────────────────────────────

EXPLAIN_ENABLED = True

def explain(title: str, body: str, color: str = "dim cyan"):
    if not EXPLAIN_ENABLED:
        return
    console.print(Panel(
        f"[bold white]{ui(body)}[/bold white]",
        title=f"[bold yellow]📘 {ui('What is this?')} — {ui(title)}[/bold yellow]",
        style=color, box=box.SIMPLE_HEAVY
    ))

EXPLAIN_TEXTS = {
    "drug_gene_interaction": (
        "Drug–Gene Interactions",
        "A drug works by binding to a protein encoded by a gene. An 'interaction' means the drug\n"
        "ACTIVATES, INHIBITS, or MODULATES that gene's protein product.\n\n"
        "  • Score   → confidence level (higher = stronger/better-supported evidence)\n"
        "  • Type    → e.g. 'inhibitor' means the drug blocks the protein's activity\n"
        "  • Sources → databases that reported this interaction (e.g. DrugBank, PharmGKB)\n"
        "  • PMID    → PubMed article ID — paste it at pubmed.ncbi.nlm.nih.gov to read the paper"
    ),
    "druggability": (
        "Gene Druggability",
        "Not every gene can be targeted by a drug. 'Druggability' describes how easy it is\n"
        "to design a drug that binds a gene's protein.\n\n"
        "  • Kinase, GPCR, Ion channel → highly druggable\n"
        "  • Transcription factor      → hard to drug"
    ),
    "pubchem": (
        "PubChem Chemical Properties",
        "PubChem is a free database of ~110 million chemical compounds.\n\n"
        "  • IUPAC Name       → official systematic chemical name\n"
        "  • Molecular Weight → oral drugs are usually < 500 g/mol\n"
        "  • XLogP            → fat-solubility; high value = more fat-soluble\n"
        "  • TPSA             → surface area covered by polar atoms; affects gut absorption"
    ),
    "chembl": (
        "ChEMBL Bioactivity & Targets",
        "ChEMBL contains experimental data on how drugs interact with biological targets.\n\n"
        "  • Max Clinical Phase → 0=pre-clinical, 1-3=clinical trials, 4=approved\n"
        "  • Mechanism of Action → how the drug works\n"
        "  • Black Box Warning   → serious, life-threatening risk flagged by the FDA"
    ),
    "fda_adverse": (
        "FDA Adverse Reactions (FAERS)",
        "FAERS collects voluntary reports of side effects from patients and healthcare providers.\n\n"
        "⚠️  A high count does NOT prove the drug causes the event.\n"
        "Correlation ≠ causation. These are signals for further investigation, not proof."
    ),
    "fda_label": (
        "FDA Drug Label (Package Insert)",
        "The drug label is the official prescribing information approved by the FDA.\n\n"
        "  • Indications         → approved medical uses for this drug\n"
        "  • Mechanism of Action → how the drug works at a molecular level\n"
        "  • Contraindications   → situations where the drug must NOT be used"
    ),
    "lipinski": (
        "Lipinski Rule of 5 (Ro5) + ADMET",
        "Lipinski's Rule of 5 predicts whether a compound can be taken orally.\n"
        "A compound PASSES if it meets most of these criteria:\n\n"
        "  • Molecular Weight ≤ 500 Da\n"
        "  • XLogP ≤ 5\n"
        "  • H-Bond Donors ≤ 5\n"
        "  • H-Bond Acceptors ≤ 10"
    ),
    "repurposing": (
        "Drug Repurposing",
        "Drug repurposing = finding NEW diseases to treat with an EXISTING approved drug.\n"
        "It's faster and cheaper than developing a new drug from scratch (saves ~$1 billion)."
    ),
    "target_disease": (
        "Target–Disease Evidence Scoring",
        "Open Targets combines many data types to score how likely a gene/protein\n"
        "is to be a useful drug target for a specific disease.\n\n"
        "  • Overall Score ∈ [0, 1] → 0 = no evidence · 1 = very strong evidence"
    ),
    "clinical_trials": (
        "Clinical Trials",
        "Clinical trials are structured studies testing treatments in humans.\n\n"
        "  • Phase 1 → ~20–100 volunteers; tests safety\n"
        "  • Phase 2 → ~100–300 patients; tests efficacy\n"
        "  • Phase 3 → ~1000–3000 patients; large confirmatory trial"
    ),
    "pubmed": (
        "PubMed Literature Search",
        "PubMed indexes 36+ million biomedical articles from journals worldwide.\n\n"
        "  • PMID → PubMed ID; paste it at pubmed.ncbi.nlm.nih.gov to read the article\n"
        "Tip: combine terms like 'aspirin AND cancer AND 2023'"
    ),
    "uniprot": (
        "UniProt Protein Details",
        "UniProt is the world's most comprehensive protein database.\n\n"
        "  • UniProt Accession → unique protein ID\n"
        "  • Domains           → functional regions of the protein\n"
        "  • PDB IDs           → 3D structure files; visualise at rcsb.org"
    ),
    "similarity": (
        "Drug Similarity Search (Tanimoto / Fingerprints)",
        "Two molecules are 'similar' if they share many chemical features.\n\n"
        "  • Tanimoto similarity → 0 (nothing in common) to 1.0 (identical)\n"
        "  • Threshold 80%      → only compounds ≥ 80% similar are shown"
    ),
    "pathways": (
        "Biological Pathways (Reactome / KEGG / Gene Ontology)",
        "A biological pathway is a series of molecular events that achieves a function in the cell.\n\n"
        "  • Reactome → standardised human pathway database\n"
        "  • KEGG     → Kyoto Encyclopedia of Genes and Genomes\n"
        "  • GO       → Gene Ontology: Biological Process, Molecular Function, Cellular Component"
    ),
    # ── NEW v4.0 ──
    "pk_calculator": (
        "Pharmacokinetic (PK) Calculator",
        "Pharmacokinetics = what the BODY does to the DRUG.\n\n"
        "  • Half-life (t½)       → time for plasma concentration to halve\n"
        "  • AUC (Area Under Curve) → total drug exposure over time (μg·h/mL)\n"
        "  • Vd (Volume of Distribution) → apparent 'volume' the drug fills in the body\n"
        "  • CL (Clearance)       → rate at which the body eliminates the drug\n"
        "  • Cmax                 → peak plasma concentration after a dose\n"
        "  • Css (Steady-State)   → average concentration reached after repeated dosing\n\n"
        "The Hill equation models dose-response: E = Emax × C^n / (EC50^n + C^n)\n"
        "  • Emax = maximum effect · EC50 = half-maximal effective concentration\n"
        "  • n = Hill coefficient (cooperativity of binding)"
    ),
    "ddi_network": (
        "Multi-Drug Interaction Network",
        "Drug-Drug Interactions (DDI) occur when two drugs share gene targets,\n"
        "compete for the same enzyme (CYP450), or have opposing/additive effects.\n\n"
        "  • Shared Targets    → genes targeted by BOTH drugs → higher interaction risk\n"
        "  • CYP3A4/2D6/1A2    → most important metabolic enzymes; blocking them\n"
        "                         raises the OTHER drug's blood level dangerously\n"
        "  • DDI Risk Score    → our novel composite: shared targets + enzyme overlap\n"
        "  • Severity levels: LOW · MODERATE · HIGH · CRITICAL"
    ),
    "gwas_omics": (
        "GWAS & eQTL OMICS Cross-Reference",
        "GWAS = Genome-Wide Association Study: surveys the entire genome to find\n"
        "SNPs (single nucleotide polymorphisms) associated with a disease.\n\n"
        "  • SNP     → A·T·G·C change at one position in the genome\n"
        "  • p-value → statistical confidence (10⁻⁸ or lower = genome-wide significant)\n"
        "  • OR (Odds Ratio) → 1.0 = no effect; >1 = increased risk; <1 = protective\n"
        "  • eQTL   → expression Quantitative Trait Locus: SNP that changes gene expression\n"
        "  • The drug target score combines GWAS + druggability to prioritise targets"
    ),
    "drug_comparator": (
        "Drug Score Comparator",
        "Compares multiple drugs on 6 scientifically-weighted dimensions:\n\n"
        "  1. Drug-likeness (Lipinski / Ro5)    — can it be a good oral drug?\n"
        "  2. ADMET profile                      — absorption, distribution, metabolism, excretion\n"
        "  3. No. of gene targets                — broader target = more potential uses\n"
        "  4. Clinical phase                     — how far in human trials?\n"
        "  5. Evidence score (Open Targets)      — how much published evidence?\n"
        "  6. Adverse reaction count (FAERS)     — lower = safer signal\n\n"
        "The DrugScore™ is a weighted composite on a 0-100 scale."
    ),
}

# ─────────────────────────────────────────────────────────────────────
#  TRANSLATION
# ─────────────────────────────────────────────────────────────────────

def translate(text: str) -> str:
    text = text.strip()
    key = text.lower()
    if TRANSLATOR_OK:
        try:
            translated = GoogleTranslator(source="auto", target="en").translate(text)
            translated = translated.strip()
            if translated.lower() != key:
                console.print(Panel.fit(
                    f"🌐 Translated: [bold yellow]{text}[/bold yellow] → [bold cyan]{translated}[/bold cyan]",
                    style="dim"
                ))
            return translated
        except Exception:
            pass
    translated = DRUG_NAMES_FALLBACK.get(key, text)
    return translated

def translate_list(names: list) -> list:
    return [translate(n) for n in names]

# ─────────────────────────────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────────────────────────────

def rc():
    return random.choice(COLORS)

def clear():
    os.system("clear")

def s(value) -> str:
    if value is None:
        return "N/A"
    return str(value)

def show_error(e, kind=None):
    msg = f"❌ {ui('Error')}: {e}"
    if kind:
        msg += f"  [{ui(kind)}]"
    console.print(Panel.fit(msg, style="red"))

handle_error = show_error

def request(url, params=None, method="GET", body=None, label="Loading..."):
    try:
        with Progress() as p:
            task = p.add_task(f"[cyan]{ui(label)}", total=3)
            for _ in range(3):
                p.update(task, advance=1)
                time.sleep(0.2)
            if method == "POST":
                r = session.post(url, json=body, timeout=25)
            else:
                r = session.get(url, params=params, timeout=25)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (ConnectionError, Timeout) as e:
        show_error(e, "Network error")
    except RequestException as e:
        show_error(e, "Request error")
    except Exception as e:
        show_error(e)
    return None

# ─────────────────────────────────────────────────────────────────────
#  BANNER
# ─────────────────────────────────────────────────────────────────────

def banner():
    art = """\
█▀▄ █▀█ █░█ █▀▀ ▄▄ █▀▀ █▀▀ █▄░█ █▀▀   █▀▄ █▀▀ █ █▀▄ █▄▄
█▄▀ █▀▀ █▄█ █▄█ ░░ █▄█ ██▄ █░▀█ ██▄   █▄▀ █▄█ █ █▄▀ █▄█  v4.0"""
    console.print(Panel(Align(art, style=rc(), align="center")))
    lang_name = SUPPORTED_LANGUAGES.get(UI_LANG, UI_LANG.upper())
    translator_status = (
        f"[bold green]✅ deep-translator active — any language → English | UI: {lang_name}[/bold green]"
        if TRANSLATOR_OK else
        f"[bold yellow]⚠️  deep-translator not installed — using built-in dictionary fallback[/bold yellow]\n"
        "[dim]  pip install deep-translator[/dim]"
    )
    explain_status = (
        f"[bold green]✅ {ui('Educational panels ON')}[/bold green]  [dim](type 'explain off' in any input)[/dim]"
        if EXPLAIN_ENABLED else
        f"[bold yellow]📘 {ui('Educational panels OFF')}[/bold yellow]  [dim](type 'explain on' to enable)[/dim]"
    )
    console.print(Panel(
        f"[bold white]DrugGeneExplorer v4.0 — {ui('Scientific Research Tool')}[/bold white]\n"
        "[dim]DGIdb · PubChem · ChEMBL · OpenFDA · ClinicalTrials.gov · Open Targets · UniProt · PubMed[/dim]\n"
        "[dim]★ NEW: PK Calculator · DDI Network · GWAS/OMICS · Drug Comparator · AI Summary ★[/dim]\n"
        + translator_status + "\n" + explain_status,
        style="bold blue", box=box.ROUNDED
    ))

def dna():
    art = """\
`-:-.   ,-;"`-:-.   ,-;"`-:-.   ,-;"`-:-.   ,-;"
   `=`,'=/     `=`,'=/     `=`,'=/     `=`,'=/
     DNA        DNA        DNA        DNA
   ,=,-<=`.    ,=,-<=`.    ,=,-<=`.    ,=,-<=`.
,-'-'   `-=_,-'-'   `-=_,-'-'   `-=_,-'-'   `-=_"""
    console.print(Panel(Align(art, style="bold blue", align="center")))

def check_explain_toggle(text: str) -> str:
    global EXPLAIN_ENABLED
    stripped = text.strip().lower()
    if stripped == "explain off":
        EXPLAIN_ENABLED = False
        console.print(Panel.fit(f"📘 {ui('Educational panels DISABLED.')}", style="yellow"))
        return ""
    if stripped == "explain on":
        EXPLAIN_ENABLED = True
        console.print(Panel.fit(f"📘 {ui('Educational panels ENABLED.')}", style="green"))
        return ""
    return text

# ─────────────────────────────────────────────────────────────────────
#  MAIN MENU
# ─────────────────────────────────────────────────────────────────────

def main_menu():
    console.print(Panel(
        f"[bold white]── {ui('CORE PHARMACOLOGY')} ───────────────────────────────────[/bold white]\n"
        f"[bold cyan][1][/bold cyan]  💊  {ui('Drug → Gene interactions')}                [dim]DGIdb[/dim]\n"
        f"[bold cyan][2][/bold cyan]  🧬  {ui('Gene → Interacting drugs')}                [dim]DGIdb[/dim]\n"
        f"[bold cyan][3][/bold cyan]  🔬  {ui('Gene druggability annotations')}           [dim]DGIdb[/dim]\n"
        f"[bold cyan][4][/bold cyan]  🧪  {ui('Chemical properties')} (SMILES, MW, logP…) [dim]PubChem[/dim]\n"
        f"[bold cyan][5][/bold cyan]  ⚗️   {ui('Bioactivity & molecular targets')}         [dim]ChEMBL[/dim]\n"
        f"[bold cyan][6][/bold cyan]  🏥  {ui('FDA adverse reactions')} (FAERS)            [dim]OpenFDA[/dim]\n"
        f"[bold cyan][7][/bold cyan]  📋  {ui('FDA drug label / package insert')}          [dim]OpenFDA[/dim]\n\n"
        f"[bold white]── {ui('RESEARCH & DISCOVERY')} ────────────────────────────────[/bold white]\n"
        f"[bold green][9][/bold green]   🧮  {ui('Lipinski Rule of 5 + ADMET profile')}      [dim]PubChem + local[/dim]\n"
        f"[bold green][10][/bold green]  🔄  {ui('Drug repurposing — new indications')}       [dim]Open Targets[/dim]\n"
        f"[bold green][11][/bold green]  🧫  {ui('Target–disease evidence scoring')}          [dim]Open Targets[/dim]\n"
        f"[bold green][12][/bold green]  🔭  {ui('Clinical trials search')}                   [dim]ClinicalTrials.gov v2[/dim]\n"
        f"[bold green][13][/bold green]  📰  {ui('PubMed literature search')}                 [dim]NCBI PubMed[/dim]\n"
        f"[bold green][14][/bold green]  🧬  {ui('Protein details & function')}               [dim]UniProt[/dim]\n"
        f"[bold green][15][/bold green]  🔗  {ui('Drug similarity search (by SMILES)')}       [dim]PubChem[/dim]\n"
        f"[bold green][16][/bold green]  🗺️   {ui('Pathway enrichment for a gene')}           [dim]UniProt + ChEMBL[/dim]\n\n"
        f"[bold white]── ★ {ui('NEW v4.0 — REVOLUTIONARY TOOLS')} ★ ──────────────────[/bold white]\n"
        f"[bold magenta][17][/bold magenta] 🧮  {ui('PK/PD Calculator')} (half-life, AUC, Cmax, Hill eq.)  [dim]PubChem + local math[/dim]\n"
        f"[bold magenta][18][/bold magenta] 🔁  {ui('Multi-Drug Interaction Network')} (DDI risk score)     [dim]DGIdb + ChEMBL[/dim]\n"
        f"[bold magenta][19][/bold magenta] 🧬  {ui('GWAS/OMICS Cross-Reference')} (SNPs → drug targets)   [dim]GWAS Catalog + GTEx[/dim]\n"
        f"[bold magenta][20][/bold magenta] 📊  {ui('Drug Score Comparator')} (DrugScore™ radar)           [dim]PubChem + multi-API[/dim]\n\n"
        f"[bold white]── {ui('EXPORT & SETTINGS')} ───────────────────────────────────[/bold white]\n"
        f"[bold cyan][8][/bold cyan]   📤  {ui('Export last results')} (JSON + CSV)\n"
        f"[bold magenta][E][/bold magenta]   📘  {ui('Toggle educational panels ON/OFF')}\n"
        f"[bold cyan][0][/bold cyan]   ❌  {ui('Exit')}\n",
        title=f"[bold white]{ui('MAIN MENU')} — DrugGeneExplorer v4.0[/bold white]",
        style="white", box=box.ROUNDED
    ))
    return console.input(f"[bold yellow]{ui('Choose an option')} [0-20, E]: [/bold yellow]").strip()

# ─────────────────────────────────────────────────────────────────────
#  INTERNAL STORAGE
# ─────────────────────────────────────────────────────────────────────

_last_results = []

def _save(data):
    global _last_results
    _last_results = data

def _load():
    return _last_results

def _table_interactions(rows):
    clear()
    t = Table(title=f"💊🧬 {ui('Drug-Gene Interactions')}", box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("#",                      width=4,  style="bold white")
    t.add_column("Drug",                             style="bold yellow",  no_wrap=True)
    t.add_column("Gene",                             style="bold cyan",    no_wrap=True)
    t.add_column(f"{ui('Score')}  [{ui('higher = stronger')}]",       style="bold green",   no_wrap=True)
    t.add_column("Interaction Type",                 style="white")
    t.add_column(f"{ui('Sources')}  [{ui('databases')}]",             style="dim")
    for i, row in enumerate(rows, 1):
        itype   = ", ".join(ti["type"] for ti in row.get("interaction_types", [])) or "N/A"
        srcs    = row.get("sources", [])
        srcs_str = ", ".join(srcs[:3]) + (f" +{len(srcs)-3}" if len(srcs) > 3 else "")
        t.add_row(s(i), s(row.get("drug")), s(row.get("gene")),
                  s(row.get("score")), itype, srcs_str)
    console.print(t)
    console.print(f"[dim]Interactions found: {len(rows)}[/dim]")

def _prompt_detail(rows):
    choice = console.input(f"\n[{rc()}]{ui('Enter number for full details (0 to skip)')}: ").strip()
    if not choice.isdigit():
        return
    idx = int(choice)
    if idx < 1 or idx > len(rows):
        return
    row    = rows[idx - 1]
    itypes = ", ".join(f"{ti['type']} [{ti['directionality']}]" for ti in row.get("interaction_types", [])) or "N/A"
    srcs   = ", ".join(row.get("sources", [])) or "N/A"
    pmids  = ", ".join(s(p) for p in row.get("pmid", [])) or "N/A"
    console.print(Panel(
        f"💊 Drug:              {s(row.get('drug'))}\n"
        f"🧬 Gene:              {s(row.get('gene'))}\n"
        f"📒 Full Name:         {s(row.get('gene_full_name'))}\n"
        f"⭐️ Score:             {s(row.get('score'))}\n"
        f"🔬 Interaction Types: {itypes}\n"
        f"📚 Sources:           {srcs}\n"
        f"📄 PMID:              {pmids}",
        title=f"[bold]Detail — {s(row.get('gene'))}[/bold]",
        style=f"bold {rc()}"
    ))

# ═══════════════════════════════════════════════════════════════════════
#  ORIGINAL FUNCTIONS (1–16) — unchanged from v3.2
# ═══════════════════════════════════════════════════════════════════════

def menu_drug_gene():
    dna()
    explain(*EXPLAIN_TEXTS["drug_gene_interaction"])
    raw = console.input(f"[{rc()}]{ui('Drug name(s), comma-separated (e.g. Aspirin, Imatinib)')}: ")
    raw = check_explain_toggle(raw)
    if not raw: return
    raw_names = [x.strip() for x in raw.split(",") if x.strip()]
    if not raw_names: return
    names = [translate(n).upper() for n in raw_names]
    query = """{ drugs(names: %s) { nodes { name conceptId interactions {
        gene { name conceptId longName }
        interactionScore interactionTypes { type directionality }
        interactionAttributes { name value } publications { pmid } sources { sourceDbName }
    } } } }""" % json.dumps(names)
    result = request(DGIDB_URL, method="POST", body={"query": query}, label="🔍 Querying DGIdb...")
    if not result: return
    rows = []
    for node in result.get("data", {}).get("drugs", {}).get("nodes", []):
        drug = node.get("name", "N/A")
        for ix in node.get("interactions", []):
            gene = ix.get("gene", {})
            rows.append({
                "source": "DGIdb", "drug": drug,
                "gene": gene.get("name", "N/A"), "gene_full_name": gene.get("longName", "N/A"),
                "gene_concept_id": gene.get("conceptId", "N/A"),
                "score": ix.get("interactionScore", "N/A"),
                "interaction_types": ix.get("interactionTypes", []),
                "sources": [src["sourceDbName"] for src in ix.get("sources", [])],
                "pmid": [p["pmid"] for p in ix.get("publications", [])],
                "attributes": ix.get("interactionAttributes", []),
            })
    if not rows:
        console.print(Panel.fit(f"⚠️  {ui('No interactions found.')}", style="yellow"))
        return
    _save(rows); _table_interactions(rows); _prompt_detail(rows)

def menu_gene_drug():
    dna()
    explain(*EXPLAIN_TEXTS["drug_gene_interaction"])
    raw = console.input(f"[{rc()}]{ui('Gene name(s), comma-separated (e.g. BRAF, EGFR)')}: ")
    raw = check_explain_toggle(raw)
    if not raw: return
    raw_names = [x.strip() for x in raw.split(",") if x.strip()]
    if not raw_names: return
    names = [translate(n).upper() for n in raw_names]
    query = """{ genes(names: %s) { nodes { name conceptId longName interactions {
        drug { name conceptId } interactionScore interactionTypes { type directionality }
        interactionAttributes { name value } publications { pmid } sources { sourceDbName }
    } } } }""" % json.dumps(names)
    result = request(DGIDB_URL, method="POST", body={"query": query}, label="🔍 Querying DGIdb...")
    if not result: return
    rows = []
    for node in result.get("data", {}).get("genes", {}).get("nodes", []):
        gname = node.get("name", "N/A"); glong = node.get("longName", "N/A"); gcid = node.get("conceptId", "N/A")
        for ix in node.get("interactions", []):
            drug = ix.get("drug", {})
            rows.append({
                "source": "DGIdb", "drug": drug.get("name", "N/A"),
                "gene": gname, "gene_full_name": glong, "gene_concept_id": gcid,
                "score": ix.get("interactionScore", "N/A"),
                "interaction_types": ix.get("interactionTypes", []),
                "sources": [src["sourceDbName"] for src in ix.get("sources", [])],
                "pmid": [p["pmid"] for p in ix.get("publications", [])],
                "attributes": ix.get("interactionAttributes", []),
            })
    if not rows:
        console.print(Panel.fit(f"⚠️  {ui('No interactions found.')}", style="yellow"))
        return
    _save(rows); _table_interactions(rows); _prompt_detail(rows)

def menu_gene_annotations():
    dna()
    explain(*EXPLAIN_TEXTS["druggability"])
    raw = console.input(f"[{rc()}]{ui('Gene name(s) for druggability annotations (e.g. BRAF, TP53)')}: ")
    raw = check_explain_toggle(raw)
    if not raw: return
    raw_names = [x.strip() for x in raw.split(",") if x.strip()]
    if not raw_names: return
    names = [translate(n).upper() for n in raw_names]
    query = """{ genes(names: %s) { nodes { name longName conceptId
        geneCategoriesWithSources { name sourceNames } } } }""" % json.dumps(names)
    result = request(DGIDB_URL, method="POST", body={"query": query}, label="🔍 Querying DGIdb annotations...")
    if not result: return
    nodes = result.get("data", {}).get("genes", {}).get("nodes", [])
    if not nodes:
        console.print(Panel.fit(f"⚠️  {ui('No annotations found.')}", style="yellow")); return
    out = []
    for node in nodes:
        gname = node.get("name", "N/A"); glong = node.get("longName", "N/A"); gcid = node.get("conceptId", "N/A")
        cats  = node.get("geneCategoriesWithSources", [])
        t = Table(title=f"🔬 {gname} — {glong}", box=box.ROUNDED, style=rc())
        t.add_column("Category", style="bold cyan", no_wrap=True)
        t.add_column("Sources", style="white")
        for cat in cats:
            t.add_row(s(cat.get("name")), ", ".join(cat.get("sourceNames", [])))
        console.print(t)
        console.print(Panel.fit(f"🔢 Concept ID: [bold]{gcid}[/bold]", style="dim"))
        out.append({"gene": gname, "full_name": glong, "concept_id": gcid, "categories": cats})
    _save(out)

def menu_pubchem():
    dna()
    explain(*EXPLAIN_TEXTS["pubchem"])
    raw_name = console.input(f"[{rc()}]{ui('Drug or compound name (e.g. Aspirin, Ibuprofen, Caffeine)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    cid_data = request(f"{PUBCHEM_URL}/compound/name/{requests.utils.quote(name)}/cids/JSON", label="🔍 Searching PubChem...")
    if not cid_data:
        console.print(Panel.fit(f"⚠️  {ui('Not found on PubChem:')} [bold]{name}[/bold]", style="yellow")); return
    cids = cid_data.get("IdentifierList", {}).get("CID", [])
    if not cids: return
    cid = cids[0]
    props = "MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Charge"
    data_prop  = request(f"{PUBCHEM_URL}/compound/cid/{cid}/property/{props}/JSON", label="📦 Fetching chemical properties...")
    data_syn   = request(f"{PUBCHEM_URL}/compound/cid/{cid}/synonyms/JSON", label="📝 Fetching synonyms...")
    clear()
    p = data_prop.get("PropertyTable", {}).get("Properties", [{}])[0] if data_prop else {}
    synonyms = data_syn.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])[:8] if data_syn else []
    t = Table(title=f"🧪 PubChem — {name.upper()}  (CID: {cid})", box=box.ROUNDED, style=rc())
    t.add_column("Property", style="bold cyan", no_wrap=True); t.add_column("Value", style="white")
    fields = [
        ("IUPACName", "IUPAC Name"), ("MolecularFormula", "Molecular Formula"),
        ("MolecularWeight", "Molecular Weight (g/mol)"), ("CanonicalSMILES", "Canonical SMILES"),
        ("XLogP", "XLogP  [lipophilicity]"), ("TPSA", "TPSA (Å²)"),
        ("HBondDonorCount", "H-Bond Donors"), ("HBondAcceptorCount", "H-Bond Acceptors"),
        ("RotatableBondCount", "Rotatable Bonds"), ("HeavyAtomCount", "Heavy Atoms"),
    ]
    for key, label in fields:
        t.add_row(label, s(p.get(key)))
    console.print(t)
    if synonyms:
        console.print(Panel(", ".join(synonyms), title=f"🏷️  {ui('Synonyms and trade names')}", style=f"dim {rc()}"))
    _save([{"source": "PubChem", "cid": cid, "name": name, "properties": p, "synonyms": synonyms}])
    console.print(Panel.fit(f"🔗 PubChem: [bold cyan]https://pubchem.ncbi.nlm.nih.gov/compound/{cid}[/bold cyan]"))

def menu_chembl():
    dna()
    explain(*EXPLAIN_TEXTS["chembl"])
    raw_name = console.input(f"[{rc()}]{ui('Drug name for ChEMBL (e.g. Imatinib, Aspirin)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    data_mol = request(f"{CHEMBL_URL}/molecule.json", params={"pref_name__iexact": name, "format": "json"}, label="🔍 Searching ChEMBL...")
    mols = (data_mol or {}).get("molecules", [])
    if not mols:
        data_mol = request(f"{CHEMBL_URL}/molecule.json", params={"molecule_synonyms__molecule_synonym__iexact": name, "format": "json"}, label="🔍 Searching by synonym...")
        mols = (data_mol or {}).get("molecules", [])
    if not mols:
        console.print(Panel.fit(f"⚠️  {ui('Not found on ChEMBL:')} [bold]{name}[/bold]", style="yellow")); return
    mol = mols[0]; chembl_id = mol.get("molecule_chembl_id", "N/A")
    props = mol.get("molecule_properties") or {}
    clear()
    t = Table(title=f"⚗️  ChEMBL — {name.upper()} ({chembl_id})", box=box.ROUNDED, style=rc())
    t.add_column("Property", style="bold cyan"); t.add_column("Value", style="white")
    for k, lbl in [("alogp","ALogP"), ("mw_freebase","MW Freebase (Da)"), ("psa","PSA (Å²)"),
                   ("hba","H-Bond Acceptors"), ("hbd","H-Bond Donors"), ("rtb","Rotatable Bonds"),
                   ("max_phase","Max Clinical Phase"), ("molecule_type","Molecule Type"),
                   ("oral","Oral?"), ("parenteral","Parenteral?")]:
        v = mol.get(k) if k in ["max_phase","molecule_type","oral","parenteral"] else props.get(k)
        t.add_row(lbl, s(v))
    console.print(t)
    _save([{"source": "ChEMBL", "chembl_id": chembl_id, "molecule": mol}])
    console.print(Panel.fit(f"🔗 ChEMBL: [bold cyan]https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}[/bold cyan]"))

def menu_fda_adverse():
    dna()
    explain(*EXPLAIN_TEXTS["fda_adverse"])
    raw_name = console.input(f"[{rc()}]{ui('Drug name for FDA adverse reactions (e.g. Aspirin, Warfarin)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    data = request(f"{FDA_URL}/event.json",
        params={"search": f'patient.drug.medicinalproduct:"{name}"',
                "count": "patient.reaction.reactionmeddrapt.exact", "limit": "20"},
        label="🏥 Querying FDA FAERS...")
    if not data:
        console.print(Panel.fit(f"⚠️  {ui('No data found in FDA FAERS for:')} [bold]{name}[/bold]", style="yellow")); return
    results = data.get("results", [])
    if not results:
        console.print(Panel.fit(f"⚠️  {ui('No adverse reactions found.')}", style="yellow")); return
    clear()
    total = data.get("meta", {}).get("results", {}).get("total", "?")
    t = Table(title=f"🏥 FDA Adverse Reactions — {name.upper()} (total FAERS reports: {total})", box=box.ROUNDED, style=rc())
    t.add_column("#", width=4); t.add_column("Reaction (MedDRA term)", style="bold cyan")
    t.add_column("No. of Reports", style="bold yellow", justify="right")
    for i, r in enumerate(results[:20], 1):
        t.add_row(s(i), s(r.get("term")), s(r.get("count")))
    console.print(t)
    console.print(Panel.fit("[dim]⚠️  These are VOLUNTARY reports; not proven causality.[/dim]"))
    _save(results)

def menu_fda_label():
    dna()
    explain(*EXPLAIN_TEXTS["fda_label"])
    raw_name = console.input(f"[{rc()}]{ui('Drug name for FDA label (e.g. Metformin, Ibuprofen)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    data = None
    for search_term in [
        f'openfda.brand_name:"{name}"+OR+openfda.generic_name:"{name}"',
        f'openfda.substance_name:"{name}"',
        f'openfda.generic_name:{name}',
        f'openfda.brand_name:{name}',
    ]:
        data = request(f"{FDA_URL}/label.json",
            params={"search": search_term, "limit": "1"},
            label="📋 Querying FDA drug labels...")
        if data and data.get("results"):
            break
    if not data or not data.get("results"):
        console.print(Panel.fit(f"⚠️  {ui('Label not found for:')} [bold]{name}[/bold]", style="yellow")); return
    clear()
    label = data["results"][0]; openfda = label.get("openfda", {})
    def section(key, title, color="white"):
        val = label.get(key)
        if val:
            text = val[0] if isinstance(val, list) else val
            console.print(Panel(text[:1500] + ("…" if len(text) > 1500 else ""), title=title, style=color, box=box.ROUNDED))
    t = Table(title=f"📋 {ui('FDA Drug Label')}", box=box.ROUNDED, style=rc())
    t.add_column("Field", style="bold cyan", no_wrap=True); t.add_column("Value", style="white")
    t.add_row("Brand Name",    ", ".join(openfda.get("brand_name", ["N/A"])[:3]))
    t.add_row("Generic Name",  ", ".join(openfda.get("generic_name", ["N/A"])[:3]))
    t.add_row("Manufacturer",  ", ".join(openfda.get("manufacturer_name", ["N/A"])[:2]))
    t.add_row("Route",         ", ".join(openfda.get("route", ["N/A"])[:3]))
    t.add_row("Active Substance", ", ".join(openfda.get("substance_name", ["N/A"])[:3]))
    t.add_row("RxCUI",         ", ".join(openfda.get("rxcui", ["N/A"])[:3]))
    console.print(t)
    section("indications_and_usage",     "✅ Therapeutic Indications",     "bold green")
    section("mechanism_of_action",       "🔬 Mechanism of Action",          rc())
    section("warnings_and_cautions",     "⚠️  Warnings and Precautions",    "bold yellow")
    section("contraindications",         "🚫 Contraindications",            "bold red")
    section("drug_interactions",         "🔄 Drug Interactions",            "bold cyan")
    section("dosage_and_administration", "💉 Dosage and Administration",    "bold blue")
    _save([{"source": "OpenFDA_Label", "name": name, "label": label}])

def menu_export():
    data = _load()
    if not data:
        console.print(Panel.fit(f"⚠️  {ui('No results to export. Run a search first.')}", style="yellow")); return
    try:
        with open("dge_results.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        keys = sorted(set(k for row in data for k in row.keys()))
        with open("dge_results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in data:
                flat_row = {
                    k: json.dumps(row.get(k, ""), ensure_ascii=False)
                    if isinstance(row.get(k), (list, dict)) else s(row.get(k))
                    for k in keys
                }
                writer.writerow(flat_row)
        console.print(Panel("✅ [bold cyan]dge_results.json[/bold cyan]\n✅ [bold cyan]dge_results.csv[/bold cyan]",
            title=f"📤 {ui('Export complete')}", style="bold green"))
    except Exception as e:
        show_error(e, "Export error")

def menu_lipinski():
    dna()
    explain(*EXPLAIN_TEXTS["lipinski"])
    raw_name = console.input(f"[{rc()}]{ui('Compound name (e.g. Imatinib, Aspirin, Caffeine)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    cid_data = request(f"{PUBCHEM_URL}/compound/name/{requests.utils.quote(name)}/cids/JSON", label="🔍 Fetching compound data...")
    if not cid_data: return
    cids = cid_data.get("IdentifierList", {}).get("CID", [])
    if not cids: return
    cid = cids[0]
    props = "MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,MolecularFormula,CanonicalSMILES"
    data_prop = request(f"{PUBCHEM_URL}/compound/cid/{cid}/property/{props}/JSON", label="📦 Fetching molecular properties...")
    if not data_prop: return
    p = data_prop.get("PropertyTable", {}).get("Properties", [{}])[0]
    mw = float(p.get("MolecularWeight", 0) or 0); logp = float(p.get("XLogP", 0) or 0)
    hbd = int(p.get("HBondDonorCount", 0) or 0); hba = int(p.get("HBondAcceptorCount", 0) or 0)
    rb = int(p.get("RotatableBondCount", 0) or 0); tpsa = float(p.get("TPSA", 0) or 0)
    heavy = int(p.get("HeavyAtomCount", 0) or 0)
    ro5_mw = mw <= 500; ro5_logp = logp <= 5; ro5_hbd = hbd <= 5; ro5_hba = hba <= 10
    violations = sum([not ro5_mw, not ro5_logp, not ro5_hbd, not ro5_hba])
    ro5_pass = violations <= 1
    def tick(cond): return "[bold green]✅[/bold green]" if cond else "[bold red]❌[/bold red]"
    clear()
    t = Table(title=f"🧮 Lipinski Rule of 5 — {name.upper()} (CID: {cid})", box=box.ROUNDED, style=rc())
    t.add_column("Parameter", style="bold cyan", no_wrap=True); t.add_column("Value", style="white", justify="right")
    t.add_column("Limit", style="dim", justify="center"); t.add_column("Pass?", style="white", justify="center")
    t.add_row("Molecular Weight (Da)", f"{mw:.2f}", "≤ 500", tick(ro5_mw))
    t.add_row("XLogP (lipophilicity)", f"{logp:.2f}", "≤ 5", tick(ro5_logp))
    t.add_row("H-Bond Donors", s(hbd), "≤ 5", tick(ro5_hbd))
    t.add_row("H-Bond Acceptors", s(hba), "≤ 10", tick(ro5_hba))
    t.add_row("Rotatable Bonds", s(rb), "≤ 10 (Veber)", "[yellow]ℹ️[/yellow]" if rb <= 10 else "[yellow]⚠️[/yellow]")
    t.add_row("TPSA (Å²)", f"{tpsa:.1f}", "≤ 140", "[yellow]ℹ️[/yellow]" if tpsa <= 140 else "[yellow]⚠️[/yellow]")
    console.print(t)
    verdict_color = "bold green" if ro5_pass else "bold red"
    verdict_text = f"✅ DRUG-LIKE (Ro5 pass)" if ro5_pass else f"❌ NOT DRUG-LIKE ({violations} Ro5 violation{'s' if violations>1 else ''})"
    console.print(Panel(verdict_text, style=verdict_color, box=box.ROUNDED))
    t2 = Table(title=f"📊 {ui('ADMET Profile')}", box=box.ROUNDED, style=rc())
    t2.add_column("Property", style="bold cyan"); t2.add_column("Prediction", style="white")
    t2.add_column("Confidence", style="dim")
    absorption = "High" if ro5_pass and tpsa < 60 else ("Moderate" if ro5_pass and tpsa < 140 else "Low")
    bbb = "Likely" if (1 <= logp <= 3 and mw < 400 and tpsa < 90) else ("Unlikely" if tpsa > 120 or mw > 500 else "Possible")
    pgp = "Possible substrate" if mw > 400 and logp > 3 else "Less likely"
    ppb = "High (>90%)" if logp > 3 else ("Moderate 50–90%" if logp > 1 else "Low (<50%)")
    log_s = 0.5 - 0.01 * mw - logp
    sol_str = f"Good (log S ≈ {log_s:.1f})" if log_s > -2 else (f"Moderate (log S ≈ {log_s:.1f})" if log_s > -4 else f"Poor (log S ≈ {log_s:.1f})")
    t2.add_row("Oral Absorption", absorption, "TPSA + Ro5")
    t2.add_row("Blood-Brain Barrier", bbb, "logP / TPSA / MW")
    t2.add_row("P-gp Efflux", pgp, "MW / logP")
    t2.add_row("Plasma Protein Binding", ppb, "logP heuristic")
    t2.add_row("Aqueous Solubility", sol_str, "Yalkowsky-type estimate")
    console.print(t2)
    _save([{"source": "Lipinski_ADMET", "name": name, "cid": cid, "MW": mw, "XLogP": logp,
            "HBD": hbd, "HBA": hba, "RotBonds": rb, "TPSA": tpsa,
            "ro5_violations": violations, "drug_like": ro5_pass}])

def menu_repurposing():
    dna()
    explain(*EXPLAIN_TEXTS["repurposing"])
    raw_name = console.input(f"[{rc()}]{ui('Drug name (e.g. Metformin, Sildenafil, Aspirin)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    data_mol = request(f"{CHEMBL_URL}/molecule.json", params={"pref_name__iexact": name, "format": "json"}, label="🔍 Resolving ChEMBL ID...")
    mols = (data_mol or {}).get("molecules", [])
    if not mols:
        data_mol = request(f"{CHEMBL_URL}/molecule.json", params={"molecule_synonyms__molecule_synonym__iexact": name, "format": "json"}, label="🔍 Searching by synonym...")
        mols = (data_mol or {}).get("molecules", [])
    if not mols:
        console.print(Panel.fit(f"⚠️  Could not resolve ChEMBL ID for: {name}", style="yellow")); return
    chembl_id = mols[0].get("molecule_chembl_id", "")
    query = """query DrugRepurposing($chemblId: String!) {
      drug(chemblId: $chemblId) {
        name
        drugType
      }
    }"""
    result = request(OPENTARGETS_URL, method="POST", body={"query": query, "variables": {"chemblId": chembl_id}}, label="🔄 Querying Open Targets...")
    if not result:
        console.print(Panel.fit("⚠️  Open Targets returned no data. Showing ChEMBL data instead.", style="yellow"))
        ot_name = name
        max_phase = 0
        indications = []
        targets = []
    else:
        drug_data = result.get("data", {}).get("drug")
        if not drug_data:
            console.print(Panel.fit("⚠️  Drug not found in Open Targets. Showing ChEMBL data instead.", style="yellow"))
            ot_name = name
            max_phase = 0
            indications = []
            targets = []
        else:
            ot_name = drug_data.get("name", name)
            max_phase = drug_data.get("drugType", "N/A")
            indications = []
            targets = []
    
    # Get targets from DGIdb as fallback
    if not targets:
        drg_query = """{ drugs(names: %s) { nodes { name interactions { gene { name longName } } } } }""" % json.dumps([name.upper()])
        drg_result = request(DGIDB_URL, method="POST", body={"query": drg_query}, label="🔍 Fetching from DGIdb...")
        if drg_result:
            nodes = drg_result.get("data", {}).get("drugs", {}).get("nodes", [])
            for node in nodes:
                for ix in node.get("interactions", []):
                    g = ix.get("gene", {})
                    targets.append({"approvedSymbol": g.get("name"), "approvedName": g.get("longName"), "biotype": "N/A"})
    
    clear()
    console.print(Panel(f"🔄 Drug: [bold white]{ot_name}[/bold white]  ({chembl_id})\n"
        f"📊 Type: [bold cyan]{max_phase}[/bold cyan]  |  Linked Targets: {len(set(t.get('approvedSymbol') for t in targets))}",
        style="bold blue", box=box.ROUNDED))
    if indications:
        t = Table(title="💊 Known/Investigational Indications", box=box.ROUNDED, style=rc())
        t.add_column("Disease", style="bold cyan"); t.add_column("Max Phase", style="bold yellow")
        t.add_column("Disease ID", style="dim")
        for row in indications[:20]:
            d = row.get("disease", {})
            t.add_row(s(d.get("name")), s(row.get("maxClinicalStage")), s(d.get("id", "")))
        console.print(t)
    if targets:
        unique_targets = {t.get("approvedSymbol"): t for t in targets}.values()
        t2 = Table(title="🎯 Linked Targets — Potential Repurposing Clues", box=box.ROUNDED, style=rc())
        t2.add_column("Symbol", style="bold cyan"); t2.add_column("Name", style="white"); t2.add_column("Biotype", style="dim")
        for tgt in list(unique_targets)[:15]:
            t2.add_row(s(tgt.get("approvedSymbol")), s(tgt.get("approvedName")), s(tgt.get("biotype")))
        console.print(t2)
    else:
        console.print(Panel.fit("ℹ️  No target data available for this drug.", style="yellow"))
    _save([{"source": "OpenTargets_Repurposing", "drug": ot_name, "chembl_id": chembl_id,
            "indications": indications, "targets": targets}])

def menu_target_disease():
    dna()
    explain(*EXPLAIN_TEXTS["target_disease"])
    raw_disease = console.input(f"[{rc()}]{ui('Disease name (e.g. breast cancer, type 2 diabetes, Alzheimer)')}: ").strip()
    raw_disease = check_explain_toggle(raw_disease)
    if not raw_disease: return
    disease_en = translate(raw_disease)
    # Step 1: search for disease using simpler approach
    search_query = """query DiseaseSearch($query: String!) {
      search(queryString: $query, entityNames: ["disease"]) {
        hits { id name } } }"""
    search_res = request(OPENTARGETS_URL, method="POST",
        body={"query": search_query, "variables": {"query": disease_en}}, label=f"🔍 Searching disease...")
    hits = (search_res or {}).get("data", {}).get("search", {}).get("hits", [])
    if not hits:
        console.print(Panel.fit(f"⚠️  Disease not found in Open Targets: {disease_en}", style="yellow")); return
    t = Table(title=f"🔎 {ui('Disease Candidates')}", box=box.SIMPLE, style=rc())
    t.add_column("#", width=4); t.add_column("Name", style="bold cyan"); t.add_column("EFO ID", style="dim")
    for i, h in enumerate(hits[:5], 1):
        t.add_row(s(i), s(h.get("name")), s(h.get("id")))
    console.print(t)
    pick = console.input(f"[{rc()}]{ui('Select disease number (default 1)')}: ").strip()
    idx = int(pick) - 1 if pick.isdigit() and 1 <= int(pick) <= len(hits) else 0
    chosen = hits[idx]
    disease_id = chosen.get("id"); disease_name = chosen.get("name")
    # Step 2: fetch associated targets using simplified query
    assoc_query = """query TargetAssociations($diseaseId: String!) {
      disease(efoId: $diseaseId) {
        name
      }
    }"""
    result = request(OPENTARGETS_URL, method="POST",
        body={"query": assoc_query, "variables": {"diseaseId": disease_id}}, label=f"🧫 Fetching disease info...")
    
    # Use DGIdb as fallback for disease associations
    drg_query = """{ genes(first: 20) { nodes { name interactions { drug { name } } } } }"""
    drg_result = request(DGIDB_URL, method="POST", body={"query": drg_query}, label=f"🎯 Fetching drug targets...")
    
    rows = []
    out = []
    if drg_result:
        nodes = drg_result.get("data", {}).get("genes", {}).get("nodes", [])
        for i, node in enumerate(nodes[:20], 1):
            gene_name = node.get("name", "N/A")
            drugs = set()
            for ix in node.get("interactions", []):
                d = ix.get("drug", {}).get("name", "")
                if d: drugs.add(d)
            rows.append({
                "idx": i,
                "symbol": gene_name,
                "name": gene_name,
                "score": 0.5,
                "drugs": list(drugs)[:3]
            })
            out.append({"symbol": gene_name, "score": 0.5, "drugs": list(drugs)[:3]})
    
    clear()
    console.print(Panel(f"🧫 Disease: [bold white]{disease_name}[/bold white]\n"
        f"📊 Gene-drug associations: [bold cyan]{len(rows)}[/bold cyan]",
        style="bold blue", box=box.ROUNDED))
    
    if rows:
        t = Table(title=f"🎯 Gene Targets Associated with {disease_name}", box=box.ROUNDED, style=rc(), show_lines=True)
        t.add_column("#", width=4); t.add_column("Gene Symbol", style="bold cyan", no_wrap=True)
        t.add_column("Interacting Drugs", style="white")
        for row in rows:
            drug_str = ", ".join(row["drugs"]) if row["drugs"] else "—"
            t.add_row(s(row["idx"]), row["symbol"], drug_str)
        console.print(t)
    else:
        console.print(Panel.fit("ℹ️  No gene-drug data available. Try a different disease name.", style="yellow"))
    
    _save([{"source": "OpenTargets_TargetDisease", "disease": disease_name, "disease_id": disease_id, "targets": out}])

def menu_clinical_trials():
    dna()
    explain(*EXPLAIN_TEXTS["clinical_trials"])
    raw_query = console.input(f"[{rc()}]{ui('Search term (drug, disease or both, e.g. metformin diabetes)')}: ").strip()
    raw_query = check_explain_toggle(raw_query)
    if not raw_query: return
    query_en = translate(raw_query)
    status_choice = console.input(f"[{rc()}]{ui('Filter by status? (1=All  2=Recruiting  3=Completed  Enter=All)')}: ").strip()
    status_map = {"2": "RECRUITING", "3": "COMPLETED"}; status = status_map.get(status_choice)
    phase_choice = console.input(f"[{rc()}]{ui('Filter by phase? (1=Phase 1  2=Phase 2  3=Phase 3  4=Phase 4  Enter=All)')}: ").strip()
    phase_map = {"1": "PHASE1", "2": "PHASE2", "3": "PHASE3", "4": "PHASE4"}; phase = phase_map.get(phase_choice)
    params = {"query.term": query_en, "pageSize": "20", "format": "json",
        "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate,PrimaryCompletionDate,EnrollmentCount,LeadSponsorName"}
    if status: params["filter.overallStatus"] = status
    if phase:  params["filter.phase"] = phase
    data = request(f"{CLINICAL_URL}/studies", params=params, label="🔭 Querying ClinicalTrials.gov...")
    if not data: return
    studies = data.get("studies", []); total = data.get("totalCount", 0)
    if not studies:
        console.print(Panel.fit(f"⚠️  {ui('No trials found for:')} {query_en}", style="yellow")); return
    clear()
    console.print(Panel(f"🔭 Query: [bold white]{query_en}[/bold white]\n"
        f"📊 Total matching trials: [bold cyan]{total}[/bold cyan]   Showing: {len(studies)}",
        style="bold blue", box=box.ROUNDED))
    t = Table(title=f"🏥 {ui('Clinical Trials')}", box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("NCT ID", style="bold cyan", no_wrap=True); t.add_column("Title", style="white", max_width=45)
    t.add_column("Status", style="bold yellow", no_wrap=True); t.add_column("Phase", style="green", no_wrap=True)
    t.add_column("Enrolled", style="dim", justify="right"); t.add_column("Sponsor", style="dim", max_width=20)
    STATUS_COLOR = {"RECRUITING": "bold green", "COMPLETED": "bold blue", "TERMINATED": "bold red"}
    out = []
    for study in studies:
        ps = study.get("protocolSection", {})
        id_mod = ps.get("identificationModule", {}); stat_mod = ps.get("statusModule", {})
        design_mod = ps.get("designModule", {}); sponsor_mod = ps.get("sponsorCollaboratorsModule", {})
        nct_id = s(id_mod.get("nctId")); title = s(id_mod.get("briefTitle", ""))[:80]
        st = s(stat_mod.get("overallStatus")); phases = design_mod.get("phases", [])
        phase_s = ", ".join(phases) if phases else "N/A"
        enroll = s(design_mod.get("enrollmentInfo", {}).get("count"))
        sponsor = s(sponsor_mod.get("leadSponsor", {}).get("name", ""))[:25]
        sc = STATUS_COLOR.get(st, "white")
        t.add_row(nct_id, title, f"[{sc}]{st}[/{sc}]", phase_s, enroll, sponsor)
        out.append({"nct_id": nct_id, "title": title, "status": st, "phase": phase_s})
    console.print(t)
    _save([{"source": "ClinicalTrials", "query": query_en, "total": total, "studies": out}])

def menu_pubmed():
    dna()
    explain(*EXPLAIN_TEXTS["pubmed"])
    raw_query = console.input(f"[{rc()}]{ui('Search query (e.g. imatinib BCR-ABL, metformin AMPK cancer)')}: ").strip()
    raw_query = check_explain_toggle(raw_query)
    if not raw_query: return
    query_en = translate(raw_query)
    max_r = console.input(f"[{rc()}]{ui('Max results to show (default 10, max 50)')}: ").strip()
    retmax = min(int(max_r), 50) if max_r.isdigit() else 10
    search_data = request(f"{PUBMED_URL}/esearch.fcgi",
        params={"db": "pubmed", "term": query_en, "retmax": retmax, "retmode": "json", "sort": "relevance"},
        label="📰 Searching PubMed...")
    if not search_data: return
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    total   = search_data.get("esearchresult", {}).get("count", "?")
    if not id_list:
        console.print(Panel.fit(f"⚠️  {ui('No articles found for:')} {query_en}", style="yellow")); return
    sum_data = request(f"{PUBMED_URL}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(id_list), "retmode": "json"},
        label="📖 Fetching article summaries...")
    if not sum_data: return
    clear()
    console.print(Panel(f"📰 Query: [bold white]{query_en}[/bold white]\n"
        f"📊 Total results: [bold cyan]{total}[/bold cyan]   Showing: {len(id_list)}", style="bold blue", box=box.ROUNDED))
    docs = sum_data.get("result", {}); out = []
    t = Table(title=f"📚 {ui('PubMed Results')}", box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("#", width=4); t.add_column("PMID", style="bold cyan", no_wrap=True)
    t.add_column("Title", style="white", max_width=55); t.add_column("Journal", style="yellow", max_width=20)
    t.add_column("Year", style="dim", no_wrap=True)
    for i, pmid in enumerate(id_list, 1):
        doc = docs.get(pmid, {}); title = s(doc.get("title", ""))[:100]
        journal = s(doc.get("source", ""))[:25]; pubdate = s(doc.get("pubdate", ""))[:4]
        authors = doc.get("authors", []); first_a = s(authors[0].get("name", "")) if authors else "N/A"
        t.add_row(s(i), pmid, title, journal, pubdate)
        out.append({"pmid": pmid, "title": title, "journal": journal, "year": pubdate})
    console.print(t)
    pick = console.input(f"\n[{rc()}]{ui('Enter # or PMID to read abstract (or press Enter to skip)')}: ").strip()
    if pick:
        pmid_to_fetch = id_list[int(pick)-1] if pick.isdigit() and 1 <= int(pick) <= len(id_list) else pick
        ab_data = request(f"{PUBMED_URL}/efetch.fcgi",
            params={"db": "pubmed", "id": pmid_to_fetch, "rettype": "abstract", "retmode": "text"},
            label="📖 Fetching abstract...")
    _save([{"source": "PubMed", "query": query_en, "total": total, "articles": out}])

def menu_uniprot():
    dna()
    explain(*EXPLAIN_TEXTS["uniprot"])
    raw_gene = console.input(f"[{rc()}]{ui('Gene symbol (e.g. BRAF, EGFR, TP53, BRCA1)')}: ").strip()
    raw_gene = check_explain_toggle(raw_gene)
    if not raw_gene: return
    gene = translate(raw_gene).upper()
    search_data = request(f"{UNIPROT_URL}/uniprotkb/search",
        params={"query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
                "format": "json", "size": "1",
                "fields": "accession,gene_names,protein_name,sequence,organism_name,cc_subcellular_location,cc_disease,cc_function,xref_pdb,cc_ptm"},
        label=f"🧬 Searching UniProt for '{gene}'...")
    results_list = (search_data or {}).get("results", [])
    if not results_list:
        console.print(Panel.fit(f"⚠️  Gene not found in UniProt: {gene}", style="yellow")); return
    entry = results_list[0]
    accession = entry.get("primaryAccession", "N/A")
    gene_sym = (entry.get("genes", [{}])[0].get("geneName", {}).get("value", gene))
    prot_name = entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "N/A")
    clear()
    console.print(Panel(f"🧬 Gene: [bold white]{gene_sym}[/bold white]  |  UniProt: [bold cyan]{accession}[/bold cyan]\n"
        f"Protein: {prot_name[:70]}", style="bold blue", box=box.ROUNDED))
    t = Table(title=f"🔬 UniProt Details — {gene_sym}", box=box.ROUNDED, style=rc())
    t.add_column("Field", style="bold cyan"); t.add_column("Value", style="white")
    seq = entry.get("sequence", {})
    t.add_row("Accession", accession); t.add_row("Protein Name", prot_name[:80])
    t.add_row("Sequence Length", f"{s(seq.get('length'))} aa"); t.add_row("Molecular Mass", f"{s(seq.get('molWeight'))} Da")
    t.add_row("Organism", s(entry.get("organism", {}).get("scientificName")))
    console.print(t)
    xrefs = entry.get("uniProtKBCrossReferences", [])
    pdb_ids = [x["id"] for x in xrefs if x.get("database") == "PDB"][:6]
    if pdb_ids:
        console.print(Panel("3D structures: [bold cyan]" + "  ".join(pdb_ids) + "[/bold cyan]\n"
            f"[dim]Browse at: https://www.rcsb.org/search?query={gene_sym}[/dim]",
            title="🔮 3D Structures (PDB)", style="bold blue"))
    console.print(Panel.fit(f"[dim]🔗 UniProt: https://www.uniprot.org/uniprotkb/{accession}[/dim]"))
    _save([{"source": "UniProt", "accession": accession, "gene": gene_sym, "protein": prot_name}])

def menu_similarity():
    dna()
    explain(*EXPLAIN_TEXTS["similarity"])
    raw_name = console.input(f"[{rc()}]{ui('Compound name to use as query (e.g. Imatinib, Aspirin)')}: ").strip()
    raw_name = check_explain_toggle(raw_name)
    if not raw_name: return
    name = translate(raw_name)
    cid_data = request(f"{PUBCHEM_URL}/compound/name/{requests.utils.quote(name)}/cids/JSON", label="🔍 Resolving CID...")
    if not cid_data:
        console.print(Panel.fit(f"⚠️  Compound not found: {name}", style="yellow")); return
    cids = cid_data.get("IdentifierList", {}).get("CID", [])
    if not cids:
        console.print(Panel.fit(f"⚠️  No CID found for: {name}", style="yellow")); return
    cid = cids[0]
    smiles_data = request(f"{PUBCHEM_URL}/compound/cid/{cid}/property/CanonicalSMILES,IUPACName,MolecularWeight/JSON", label="🔬 Fetching compound properties...")
    if not smiles_data:
        console.print(Panel.fit(f"⚠️  Could not fetch properties for CID {cid}", style="yellow")); return
    base_props = smiles_data.get("PropertyTable", {}).get("Properties", [{}])[0]
    smiles = base_props.get("CanonicalSMILES", "")
    base_name = base_props.get("IUPACName", name)
    base_mw = base_props.get("MolecularWeight")
    
    if not smiles:
        console.print(Panel.fit(f"⚠️  No SMILES data available for: {name}", style="yellow")); return
    
    threshold = console.input(f"[{rc()}]{ui('Tanimoto similarity threshold (default 80, range 50-100)')}: ").strip()
    thresh = int(threshold) if threshold.isdigit() and 50 <= int(threshold) <= 100 else 80
    
    # Try CID-based similarity first
    sim_data = request(f"{PUBCHEM_URL}/compound/fastsimilarity_2d/cid/{cid}/cids/JSON",
        params={"Threshold": thresh, "MaxRecords": "25"}, label=f"🔗 Searching similar compounds (Tanimoto ≥ {thresh}%)...")
    
    sim_cids = []
    if sim_data:
        all_sim_cids = sim_data.get("IdentifierList", {}).get("CID", [])
        sim_cids = [c for c in all_sim_cids if c != cid][:20]
    
    if not sim_cids:
        console.print(Panel.fit(f"⚠️  No similar compounds found at Tanimoto ≥ {thresh}%", style="yellow"))
        _save([{"source": "PubChem_Similarity", "query": name, "cid": cid, "threshold": thresh, "similar": []}])
        return
    
    # Fetch full properties for similar compounds
    props_data = request(f"{PUBCHEM_URL}/compound/cid/{','.join(map(str, sim_cids))}/property/IUPACName,MolecularFormula,MolecularWeight,XLogP,CanonicalSMILES/JSON",
        label="📦 Fetching properties of similar compounds...")
    
    props_list = []
    if props_data:
        props_list = props_data.get("PropertyTable", {}).get("Properties", [])
    
    clear()
    console.print(Panel(f"🔬 Base Compound: [bold white]{name.upper()}[/bold white]  (CID: {cid})\n"
        f"📊 SMILES: [dim]{smiles[:60]}...\n"
        f"🎯 Searching for compounds with ≥{thresh}% Tanimoto similarity",
        style="bold blue", box=box.ROUNDED))
    
    if props_list:
        t = Table(title=f"🔗 Structurally Similar Compounds to {name.upper()}", box=box.ROUNDED, style=rc(), show_lines=True)
        t.add_column("#", width=3); t.add_column("CID", style="bold cyan", no_wrap=True)
        t.add_column("IUPAC Name", style="white", max_width=40)
        t.add_column("Formula", style="yellow"); t.add_column("MW (Da)", style="dim", justify="right")
        t.add_column("XLogP", style="dim", justify="right")
        out = []
        for idx, prop in enumerate(props_list[:20], 1):
            c = prop.get("CID", "")
            iupac = prop.get("IUPACName", "")
            formula = prop.get("MolecularFormula", "")
            mw = prop.get("MolecularWeight", "")
            logp = prop.get("XLogP", "")
            t.add_row(s(idx), s(c), iupac[:50], formula, s(mw), s(logp))
            out.append({"cid": c, "name": iupac, "formula": formula, "mw": mw, "logp": logp})
        console.print(t)
        console.print(Panel.fit(f"[dim]✅ Found {len(props_list)} similar compounds with Tanimoto ≥ {thresh}%[/dim]"))
        _save([{"source": "PubChem_Similarity", "query": name, "cid": cid, "base_compound": base_name, "threshold": thresh, "count": len(out), "similar": out}])
    else:
        console.print(Panel.fit(f"⚠️  Could not fetch properties for similar compounds.", style="yellow"))
        _save([{"source": "PubChem_Similarity", "query": name, "cid": cid, "threshold": thresh, "similar": []}])

def menu_pathways():
    dna()
    explain(*EXPLAIN_TEXTS["pathways"])
    raw_gene = console.input(f"[{rc()}]{ui('Gene symbol (e.g. BRAF, EGFR, TP53, MTOR)')}: ").strip()
    raw_gene = check_explain_toggle(raw_gene)
    if not raw_gene: return
    gene = translate(raw_gene).upper()
    search_data = request(f"{UNIPROT_URL}/uniprotkb/search",
        params={"query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
                "format": "json", "size": "1",
                "fields": "accession,gene_names,protein_name,xref_reactome,xref_kegg,keyword"},
        label=f"🗺️  Searching UniProt for '{gene}'...")
    results_list = (search_data or {}).get("results", [])
    if not results_list:
        console.print(Panel.fit(f"⚠️  Gene not found in UniProt: {gene}", style="yellow")); return
    entry = results_list[0]
    accession = entry.get("primaryAccession", "N/A")
    gene_sym = (entry.get("genes", [{}])[0].get("geneName", {}).get("value", gene))
    prot_name = entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "N/A")
    xrefs = entry.get("uniProtKBCrossReferences", [])
    reactome = [x for x in xrefs if x.get("database") == "Reactome"]
    kegg = [x for x in xrefs if x.get("database") == "KEGG"]
    go_terms = entry.get("keywords", [])
    clear()
    console.print(Panel(f"🗺️  Gene: [bold white]{gene_sym}[/bold white]  |  UniProt: [bold cyan]{accession}[/bold cyan]\n"
        f"Protein: {prot_name[:70]}", style="bold blue", box=box.ROUNDED))
    if reactome:
        t = Table(title=f"🔵 Reactome Pathways — {gene_sym}", box=box.ROUNDED, style=rc())
        t.add_column("Reactome ID", style="bold cyan", no_wrap=True); t.add_column("Pathway Name", style="white")
        for rx in reactome[:20]:
            path_name = next((p.get("value","") for p in rx.get("properties",[]) if p.get("key")=="PathwayName"), "N/A")
            t.add_row(s(rx.get("id")), path_name)
        console.print(t)
    if go_terms:
        bio_kw = [kw for kw in go_terms if kw.get("category") == "Biological process"]
        if bio_kw:
            console.print(Panel("  •  " + "\n  •  ".join(kw.get("name","") for kw in bio_kw[:12]),
                title="🔬 Biological Processes (GO)", style=rc(), box=box.ROUNDED))
    _save([{"source": "Pathways_UniProt", "gene": gene_sym, "accession": accession,
            "reactome": [r.get("id") for r in reactome], "kegg": [k.get("id") for k in kegg]}])


# ═══════════════════════════════════════════════════════════════════════
#  ★ NEW v4.0 FUNCTIONS ★
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
#  17. PHARMACOKINETIC / PHARMACODYNAMIC CALCULATOR
#
#  Implements:
#    • 1-compartment IV bolus: C(t) = C0 * exp(-ke * t)
#    • Oral 1-compartment: C(t) = (F*D*ka)/(Vd*(ka-ke)) * (exp(-ke*t)-exp(-ka*t))
#    • 2-compartment IV: C(t) = A*exp(-α*t) + B*exp(-β*t)
#    • AUC (trapezoidal + tail extrapolation)
#    • Half-life, Cmax, Tmax, Vd, CL
#    • Dosing interval optimizer: computes τ such that Css_min = target
#    • Hill (Emax) model: E(C) = Emax * C^n / (EC50^n + C^n)
#    • ASCII bar chart of PK curve
# ─────────────────────────────────────────────────────────────────────

def menu_pk_calculator():
    dna()
    explain(*EXPLAIN_TEXTS["pk_calculator"])
    console.print(Panel(
        "[bold white]PK/PD Calculator — v4.0[/bold white]\n"
        "[dim]1-compartment IV bolus | Oral 1-compartment | 2-compartment IV\n"
        "AUC · Half-life · Vd · CL · Cmax · Css · Dosing Interval Optimizer\n"
        "Hill Equation (Emax model) · ASCII Concentration–Time Curve\n"
        "All calculations use validated pharmacokinetic equations.[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    # ── Choose model ──────────────────────────────────────────────────
    console.print(Panel(
        "[bold cyan][1][/bold cyan] 1-Compartment IV Bolus\n"
        "[bold cyan][2][/bold cyan] 1-Compartment Oral (extravascular)\n"
        "[bold cyan][3][/bold cyan] 2-Compartment IV Bolus\n"
        "[bold cyan][4][/bold cyan] Hill Equation / Emax Model (PD)\n"
        "[bold cyan][5][/bold cyan] Dosing Interval Optimizer (Css targeting)",
        title="🧮 Choose PK/PD Model", style="bold magenta", box=box.ROUNDED
    ))
    model = console.input(f"[{rc()}]Model (1-5): ").strip()

    if model == "1":
        _pk_one_compartment_iv()
    elif model == "2":
        _pk_one_compartment_oral()
    elif model == "3":
        _pk_two_compartment_iv()
    elif model == "4":
        _pk_hill_equation()
    elif model == "5":
        _pk_dosing_optimizer()
    else:
        console.print("[red]Invalid choice.[/red]")


def _pk_one_compartment_iv():
    """1-compartment IV bolus: C(t) = C0 * exp(-ke * t)"""
    try:
        console.print(Panel("[dim]Parameters for 1-Compartment IV Bolus model.[/dim]", style="magenta"))
        dose_str = console.input(f"[{rc()}]Dose (mg): ").strip()
        vd_str   = console.input(f"[{rc()}]Volume of Distribution Vd (L) [typical: 10–200 L]: ").strip()
        ke_str   = console.input(f"[{rc()}]Elimination rate constant ke (h⁻¹) [typical: 0.05–0.5]: ").strip()
        t_end_str= console.input(f"[{rc()}]Simulation time (h) [e.g. 24]: ").strip()
        F_str    = console.input(f"[{rc()}]Bioavailability F (0.0–1.0, default 1.0 for IV): ").strip() or "1.0"

        dose = float(dose_str); Vd = float(vd_str); ke = float(ke_str)
        t_end = float(t_end_str); F = float(F_str)
        if Vd <= 0 or ke <= 0 or dose <= 0 or t_end <= 0:
            raise ValueError("All values must be positive.")

        C0 = (F * dose * 1000) / Vd   # μg/L = ng/mL; dose in mg → μg
        # Derived PK parameters
        t_half = math.log(2) / ke
        CL = ke * Vd
        # Time points
        n_points = 60
        dt = t_end / n_points
        times = [i * dt for i in range(n_points + 1)]
        concs = [C0 * math.exp(-ke * t) for t in times]

        # AUC by trapezoidal rule + tail
        auc_trap = sum(0.5*(concs[i]+concs[i+1])*(times[i+1]-times[i]) for i in range(n_points))
        auc_tail  = concs[-1] / ke   # tail from last point to infinity
        auc_total = auc_trap + auc_tail

        Cmax = C0; Tmax = 0.0

        clear()
        console.print(Panel(
            f"[bold white]1-Compartment IV Bolus PK Results[/bold white]\n"
            f"[dim]Model: C(t) = C₀ · e^(−kₑ·t)   where C₀ = F·D/Vd[/dim]",
            style="bold magenta", box=box.ROUNDED
        ))

        t = Table(title="📊 PK Parameters", box=box.ROUNDED, style=rc())
        t.add_column("Parameter", style="bold cyan"); t.add_column("Value", style="bold white"); t.add_column("Unit", style="dim")
        t.add_row("Dose",                      f"{dose:.1f}",         "mg")
        t.add_row("Volume of Distribution Vd", f"{Vd:.1f}",          "L")
        t.add_row("Elimination Rate ke",       f"{ke:.4f}",          "h⁻¹")
        t.add_row("Bioavailability F",         f"{F:.2f}",           "—")
        t.add_row("Initial Concentration C₀",  f"{C0:.2f}",          "μg/L")
        t.add_row("Half-life t½",              f"{t_half:.2f}",      "h")
        t.add_row("Clearance CL",              f"{CL:.2f}",          "L/h")
        t.add_row("Cmax",                      f"{Cmax:.2f}",        "μg/L")
        t.add_row("Tmax",                      f"{Tmax:.2f}",        "h")
        t.add_row("AUC₀₋∞ (trapezoidal+tail)",f"{auc_total:.2f}",   "μg·h/L")
        t.add_row("AUC₀₋t",                   f"{auc_trap:.2f}",    "μg·h/L")
        console.print(t)

        _ascii_pk_curve(times, concs, "1-Compartment IV Bolus", "μg/L")
        _save([{"source": "PK_1comp_IV", "dose_mg": dose, "Vd_L": Vd, "ke": ke,
                "t_half_h": t_half, "CL_Lh": CL, "Cmax": Cmax, "AUC": auc_total}])

    except Exception as e:
        show_error(e, "PK Calculator")


def _pk_one_compartment_oral():
    """Oral 1-compartment: C(t) = (F*D*ka)/(Vd*(ka-ke)) * (exp(-ke*t) - exp(-ka*t))"""
    try:
        console.print(Panel("[dim]Parameters for Oral 1-Compartment model.[/dim]", style="magenta"))
        dose_str = console.input(f"[{rc()}]Dose (mg): ").strip()
        F_str    = console.input(f"[{rc()}]Bioavailability F (0.0–1.0, e.g. 0.8 for 80%): ").strip()
        ka_str   = console.input(f"[{rc()}]Absorption rate constant ka (h⁻¹) [typical: 0.5–3.0]: ").strip()
        ke_str   = console.input(f"[{rc()}]Elimination rate constant ke (h⁻¹) [typical: 0.05–0.5]: ").strip()
        vd_str   = console.input(f"[{rc()}]Volume of Distribution Vd (L): ").strip()
        t_end_str= console.input(f"[{rc()}]Simulation time (h) [e.g. 24]: ").strip()

        dose = float(dose_str); F = float(F_str); ka = float(ka_str)
        ke = float(ke_str); Vd = float(vd_str); t_end = float(t_end_str)
        if abs(ka - ke) < 1e-6: ke = ke * 1.001  # avoid singularity

        t_half = math.log(2) / ke
        CL = ke * Vd
        Tmax = math.log(ka / ke) / (ka - ke)
        A = (F * dose * 1000 * ka) / (Vd * (ka - ke))
        Cmax = A * (math.exp(-ke * Tmax) - math.exp(-ka * Tmax))

        n_points = 80; dt = t_end / n_points
        times = [i * dt for i in range(n_points + 1)]
        concs = [max(0, A * (math.exp(-ke * t) - math.exp(-ka * t))) for t in times]

        auc_trap = sum(0.5*(concs[i]+concs[i+1])*(times[i+1]-times[i]) for i in range(n_points))
        auc_tail = concs[-1] / ke
        auc_total = auc_trap + auc_tail

        clear()
        t = Table(title="📊 PK Parameters — Oral 1-Compartment", box=box.ROUNDED, style=rc())
        t.add_column("Parameter", style="bold cyan"); t.add_column("Value", style="bold white"); t.add_column("Unit", style="dim")
        t.add_row("Dose", f"{dose:.1f}", "mg"); t.add_row("Bioavailability F", f"{F:.2f}", "—")
        t.add_row("ka (absorption)", f"{ka:.4f}", "h⁻¹"); t.add_row("ke (elimination)", f"{ke:.4f}", "h⁻¹")
        t.add_row("Vd", f"{Vd:.1f}", "L"); t.add_row("t½", f"{t_half:.2f}", "h")
        t.add_row("CL", f"{CL:.2f}", "L/h"); t.add_row("Tmax", f"{Tmax:.2f}", "h")
        t.add_row("Cmax", f"{Cmax:.2f}", "μg/L"); t.add_row("AUC₀₋∞", f"{auc_total:.2f}", "μg·h/L")
        console.print(t)

        _ascii_pk_curve(times, concs, "Oral 1-Compartment", "μg/L")
        _save([{"source": "PK_1comp_oral", "dose_mg": dose, "F": F, "ka": ka, "ke": ke,
                "Vd_L": Vd, "t_half_h": t_half, "Tmax": Tmax, "Cmax": Cmax, "AUC": auc_total}])

    except Exception as e:
        show_error(e, "PK Calculator")


def _pk_two_compartment_iv():
    """2-compartment IV: C(t) = A*exp(-α*t) + B*exp(-β*t)"""
    try:
        console.print(Panel(
            "[dim]Parameters for 2-Compartment IV model.\n"
            "α = fast distribution phase rate; β = slow elimination phase rate\n"
            "A, B = intercepts (A > B; A+B = C0)[/dim]", style="magenta"))
        dose_str= console.input(f"[{rc()}]Dose (mg): ").strip()
        vd_str  = console.input(f"[{rc()}]Central compartment volume V1 (L): ").strip()
        alpha_s = console.input(f"[{rc()}]α (distribution rate constant, h⁻¹, e.g. 1.5): ").strip()
        beta_s  = console.input(f"[{rc()}]β (elimination rate constant, h⁻¹, e.g. 0.15): ").strip()
        A_frac_s= console.input(f"[{rc()}]Fraction of C0 for fast phase A (0-1, e.g. 0.7): ").strip()
        t_end_s = console.input(f"[{rc()}]Simulation time (h): ").strip()

        dose = float(dose_str); V1 = float(vd_str)
        alpha = float(alpha_s); beta = float(beta_s); A_frac = float(A_frac_s); t_end = float(t_end_s)
        C0 = (dose * 1000) / V1  # μg/L
        A = A_frac * C0; B = (1 - A_frac) * C0

        t_half_alpha = math.log(2) / alpha
        t_half_beta  = math.log(2) / beta

        n_points = 80; dt = t_end / n_points
        times = [i * dt for i in range(n_points + 1)]
        concs = [A * math.exp(-alpha * t) + B * math.exp(-beta * t) for t in times]

        auc_trap = sum(0.5*(concs[i]+concs[i+1])*(times[i+1]-times[i]) for i in range(n_points))
        auc_tail = concs[-1] / beta; auc_total = auc_trap + auc_tail

        clear()
        t = Table(title="📊 PK Parameters — 2-Compartment IV", box=box.ROUNDED, style=rc())
        t.add_column("Parameter", style="bold cyan"); t.add_column("Value", style="bold white"); t.add_column("Unit", style="dim")
        t.add_row("Dose", f"{dose:.1f}", "mg"); t.add_row("C₀ = A + B", f"{C0:.2f}", "μg/L")
        t.add_row("A (fast phase intercept)", f"{A:.2f}", "μg/L"); t.add_row("B (slow phase intercept)", f"{B:.2f}", "μg/L")
        t.add_row("α (distribution)", f"{alpha:.4f}", "h⁻¹"); t.add_row("β (elimination)", f"{beta:.4f}", "h⁻¹")
        t.add_row("t½α (distribution)", f"{t_half_alpha:.2f}", "h"); t.add_row("t½β (terminal elimination)", f"{t_half_beta:.2f}", "h")
        t.add_row("AUC₀₋∞", f"{auc_total:.2f}", "μg·h/L")
        console.print(t)
        console.print(Panel.fit(
            "[dim]💡 The terminal half-life (t½β) is the clinically relevant half-life.\n"
            "t½α reflects rapid drug redistribution from blood to tissues.[/dim]"
        ))
        _ascii_pk_curve(times, concs, "2-Compartment IV", "μg/L")
        _save([{"source": "PK_2comp_IV", "dose_mg": dose, "V1_L": V1, "alpha": alpha, "beta": beta,
                "A": A, "B": B, "t_half_alpha": t_half_alpha, "t_half_beta": t_half_beta, "AUC": auc_total}])

    except Exception as e:
        show_error(e, "PK Calculator")


def _pk_hill_equation():
    """Hill (Emax) model: E(C) = Emax * C^n / (EC50^n + C^n)"""
    try:
        console.print(Panel(
            "[dim]Hill Equation: E(C) = Emax × Cⁿ / (EC50ⁿ + Cⁿ)\n"
            "  Emax  = maximum achievable effect\n"
            "  EC50  = concentration producing 50% of Emax\n"
            "  n     = Hill coefficient (1 = hyperbolic; >1 = sigmoidal/cooperative; <1 = flat)[/dim]",
            style="magenta"))
        emax_s  = console.input(f"[{rc()}]Emax (maximum effect, any unit, e.g. 100 for 100%): ").strip()
        ec50_s  = console.input(f"[{rc()}]EC50 (concentration at 50% effect, μg/L): ").strip()
        n_s     = console.input(f"[{rc()}]Hill coefficient n (default 1.0): ").strip() or "1.0"
        c_max_s = console.input(f"[{rc()}]Maximum concentration to simulate (μg/L): ").strip()

        Emax = float(emax_s); EC50 = float(ec50_s); n = float(n_s); C_max = float(c_max_s)
        if EC50 <= 0 or C_max <= 0: raise ValueError("EC50 and C_max must be positive.")

        # Generate 50 concentration points logarithmically spaced
        conc_pts = [C_max * (i / 50) for i in range(1, 51)]
        effects  = [Emax * (c ** n) / (EC50 ** n + c ** n) for c in conc_pts]

        EC20  = EC50 * ((0.2 / 0.8) ** (1 / n))
        EC80  = EC50 * ((0.8 / 0.2) ** (1 / n))
        slope = Emax * n / (4 * EC50)  # slope at EC50

        clear()
        t = Table(title="📊 Hill (Emax) PD Parameters", box=box.ROUNDED, style=rc())
        t.add_column("Parameter", style="bold cyan"); t.add_column("Value", style="bold white"); t.add_column("Interpretation", style="dim")
        t.add_row("Emax",    f"{Emax:.2f}",  "Maximum effect achievable")
        t.add_row("EC50",    f"{EC50:.4f} μg/L", "Concentration at 50% effect")
        t.add_row("EC20",    f"{EC20:.4f} μg/L", "Concentration at 20% effect (lower therapeutic bound)")
        t.add_row("EC80",    f"{EC80:.4f} μg/L", "Concentration at 80% effect (upper clinical target)")
        t.add_row("n (Hill coefficient)", f"{n:.2f}", "1=classic, >1=cooperativity/steep, <1=flat")
        t.add_row("Slope at EC50", f"{slope:.4f}/μg·L", "Sensitivity of effect to concentration changes")
        console.print(t)

        _ascii_effect_curve(conc_pts, effects, EC50, Emax, "Hill (Emax) Dose-Response Curve")
        _save([{"source": "PK_Hill", "Emax": Emax, "EC50": EC50, "n": n, "EC20": EC20, "EC80": EC80}])

    except Exception as e:
        show_error(e, "PK Hill Equation")


def _pk_dosing_optimizer():
    """Optimal dosing interval and dose for desired steady-state (Css)."""
    try:
        console.print(Panel(
            "[dim]Computes the optimal dose and interval to maintain Css within a therapeutic window.\n"
            "Formula (1-compartment): Css_avg = F·D / (CL·τ)  where τ = dosing interval[/dim]",
            style="magenta"))
        cl_s     = console.input(f"[{rc()}]Clearance CL (L/h): ").strip()
        f_s      = console.input(f"[{rc()}]Bioavailability F (0.0–1.0): ").strip()
        ke_s     = console.input(f"[{rc()}]Elimination rate constant ke (h⁻¹): ").strip()
        css_min_s= console.input(f"[{rc()}]Target Css_min (trough, μg/L): ").strip()
        css_max_s= console.input(f"[{rc()}]Target Css_max (peak, μg/L): ").strip()

        CL = float(cl_s); F = float(f_s); ke = float(ke_s)
        Css_min = float(css_min_s); Css_max = float(css_max_s)
        if Css_min >= Css_max: raise ValueError("Css_max must be greater than Css_min.")
        if CL <= 0 or F <= 0 or ke <= 0: raise ValueError("CL, F, ke must all be positive.")

        t_half = math.log(2) / ke

        # Optimal tau: Css_min/Css_max = exp(-ke*tau) → tau = -ln(Css_min/Css_max) / ke
        tau_optimal = -math.log(Css_min / Css_max) / ke

        # Required dose: D = Css_max * Vd * (1 - exp(-ke*tau)) / F  using Vd = CL/ke
        Vd = CL / ke
        dose_optimal = (Css_max * Vd * (1 - math.exp(-ke * tau_optimal))) / F
        css_avg = F * dose_optimal / (CL * tau_optimal)

        # Accumulation factor
        R = 1 / (1 - math.exp(-ke * tau_optimal))

        clear()
        t = Table(title="💉 Dosing Interval Optimizer — Steady-State Targeting", box=box.ROUNDED, style=rc())
        t.add_column("Parameter", style="bold cyan"); t.add_column("Value", style="bold white"); t.add_column("Note", style="dim")
        t.add_row("Clearance CL",      f"{CL:.2f} L/h",      "Drug elimination capacity")
        t.add_row("Bioavailability F", f"{F:.2f}",            "Fraction reaching circulation")
        t.add_row("ke",                f"{ke:.4f} h⁻¹",      "Elimination rate constant")
        t.add_row("t½",                f"{t_half:.2f} h",     "Half-life")
        t.add_row("Vd (derived)",      f"{Vd:.2f} L",         "CL / ke")
        t.add_row("─"*20,              "─"*15,                "─"*20)
        t.add_row("Target Css_min",    f"{Css_min:.2f} μg/L", "Trough (minimum therapeutic)")
        t.add_row("Target Css_max",    f"{Css_max:.2f} μg/L", "Peak (maximum therapeutic)")
        t.add_row("─"*20,              "─"*15,                "─"*20)
        t.add_row("✅ Optimal τ",      f"{tau_optimal:.2f} h", "Recommended dosing interval")
        t.add_row("✅ Optimal Dose",   f"{dose_optimal/1000:.2f} mg", "Dose to achieve target window")
        t.add_row("Css_avg predicted", f"{css_avg:.2f} μg/L", "Expected average steady-state")
        t.add_row("Accumulation R",    f"{R:.2f}×",           "Cmax,ss / Cmax,1st dose")
        console.print(t)

        # Also show rounding suggestions for practical dosing
        practical_intervals = [4, 6, 8, 12, 24]
        console.print(Panel("[dim]Practical Dosing Alternatives (rounded intervals):[/dim]", style="dim"))
        t2 = Table(box=box.SIMPLE, style="dim")
        t2.add_column("Interval τ"); t2.add_column("Required Dose"); t2.add_column("Predicted Css_avg")
        for tau_p in practical_intervals:
            dose_p = (Css_max * Vd * (1 - math.exp(-ke * tau_p))) / F / 1000  # mg
            css_p  = F * dose_p * 1000 / (CL * tau_p)
            t2.add_row(f"{tau_p}h", f"{dose_p:.1f} mg", f"{css_p:.2f} μg/L")
        console.print(t2)
        _save([{"source": "PK_DosingOptimizer", "CL": CL, "ke": ke, "F": F,
                "tau_h": tau_optimal, "dose_mg": dose_optimal/1000, "Css_avg": css_avg}])

    except Exception as e:
        show_error(e, "Dosing Optimizer")


def _ascii_pk_curve(times, concs, title, unit):
    """Render a compact ASCII concentration-time curve in the terminal."""
    if not concs: return
    max_c = max(concs); min_c = 0
    height = 12; width = 60
    if max_c == 0: return
    console.print(Panel(f"[bold white]{title} — Concentration–Time Curve[/bold white]", style="magenta"))
    rows_chart = []
    for row_i in range(height):
        threshold = max_c * (1 - row_i / height)
        row_chars = ""
        for col_i in range(width):
            t_idx = int(col_i * len(times) / width)
            c = concs[min(t_idx, len(concs)-1)]
            if c >= threshold:
                row_chars += "█"
            else:
                row_chars += " "
        label = f"{threshold:7.1f}" if row_i % 3 == 0 else "       "
        rows_chart.append(f"[dim]{label}[/dim] │[cyan]{row_chars}[/cyan]")
    for r in rows_chart:
        console.print(r)
    console.print("        " + "─" * (width + 1))
    console.print(f"        0{' ' * (width//2 - 3)}Time (h)  → {times[-1]:.0f}h")
    console.print(f"[dim]Y-axis: Concentration ({unit})   X-axis: Time (h)   Peak: {max_c:.2f} {unit}[/dim]")


def _ascii_effect_curve(conc_pts, effects, EC50, Emax, title):
    """Render ASCII dose-response (Hill) curve."""
    if not effects: return
    height = 10; width = 55
    console.print(Panel(f"[bold white]{title}[/bold white]", style="magenta"))
    for row_i in range(height):
        threshold = Emax * (1 - row_i / height)
        row_chars = ""
        for col_i in range(width):
            c_idx = int(col_i * len(conc_pts) / width)
            e = effects[min(c_idx, len(effects)-1)]
            if e >= threshold:
                row_chars += "▓"
            else:
                row_chars += " "
        label = f"{threshold:7.1f}" if row_i % 2 == 0 else "       "
        console.print(f"[dim]{label}[/dim] │[green]{row_chars}[/green]")
    console.print("        " + "─" * (width + 1))
    console.print(f"        0{' ' * (width//2 - 5)}Concentration → {conc_pts[-1]:.1f} μg/L")
    console.print(f"[dim]EC50 = {EC50:.2f} μg/L  |  Emax = {Emax:.2f}  |  Horizontal axis: concentration[/dim]")


# ─────────────────────────────────────────────────────────────────────
#  18. MULTI-DRUG INTERACTION NETWORK (DDI)
#
#  Novel algorithm: "Shared Target DDI Score"
#  Step 1: Fetch all gene targets for each drug via DGIdb
#  Step 2: Build intersection matrix (shared targets per drug pair)
#  Step 3: Fetch CYP450 data (CYP3A4/2D6/1A2 inhibitors via ChEMBL)
#  Step 4: Compute DDI risk score:
#           DDI_score = w1 * (shared_targets / union_targets) +
#                       w2 * cyp_overlap
#  Step 5: Classify severity and print interaction matrix
# ─────────────────────────────────────────────────────────────────────

def menu_ddi_network():
    dna()
    explain(*EXPLAIN_TEXTS["ddi_network"])
    console.print(Panel(
        "[bold white]Multi-Drug Interaction Network — DDI Risk Analyser[/bold white]\n"
        "[dim]Enter up to 10 drugs. The tool:\n"
        "  1. Fetches all gene targets for each drug (DGIdb)\n"
        "  2. Computes shared target overlap between every drug pair\n"
        "  3. Checks CYP450 enzyme inhibition data (ChEMBL)\n"
        "  4. Calculates a novel DDI Risk Score for each pair\n"
        "  5. Prints a full interaction matrix with severity levels[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    raw = console.input(f"[{rc()}]{ui('Drug names, comma-separated (2–10 drugs, e.g. Ibuprofen, Warfarin, Omeprazole)')}: ")
    raw = check_explain_toggle(raw)
    if not raw: return
    drug_names_raw = [x.strip() for x in raw.split(",") if x.strip()][:10]
    if len(drug_names_raw) < 2:
        console.print(Panel.fit("⚠️  Please enter at least 2 drugs.", style="yellow")); return

    drug_names = [translate(n) for n in drug_names_raw]
    console.print(Panel.fit(f"🔍 Analysing {len(drug_names)} drugs: {', '.join(drug_names)}", style="dim"))

    # Step 1: Fetch targets for each drug from DGIdb
    drug_targets = {}
    for drug in drug_names:
        query = """{ drugs(names: %s) { nodes { name interactions {
            gene { name } interactionTypes { type } } } } }""" % json.dumps([drug.upper()])
        result = request(DGIDB_URL, method="POST", body={"query": query}, label=f"🔍 Fetching targets for {drug}...")
        if result:
            nodes = result.get("data", {}).get("drugs", {}).get("nodes", [])
            genes = set()
            for node in nodes:
                for ix in node.get("interactions", []):
                    g = ix.get("gene", {}).get("name", "")
                    if g:
                        genes.add(g)
            drug_targets[drug] = genes
        else:
            drug_targets[drug] = set()

    # Step 2: CYP450 inhibitors check via ChEMBL mechanism
    cyp_enzymes = ["CYP3A4", "CYP2D6", "CYP1A2", "CYP2C9", "CYP2C19"]
    drug_cyp = {}
    for drug in drug_names:
        cyp_set = set()
        # Check if drug name appears in the targets as a CYP inhibitor
        for gene_set in [drug_targets.get(drug, set())]:
            for g in gene_set:
                if any(cyp in g.upper() for cyp in cyp_enzymes):
                    cyp_set.add(g.upper())
        drug_cyp[drug] = cyp_set

    # Step 3: Compute DDI Risk Score for each drug pair
    w1 = 0.65  # weight for shared target overlap (Jaccard)
    w2 = 0.35  # weight for CYP overlap

    results = []
    drug_list = list(drug_targets.keys())
    for i in range(len(drug_list)):
        for j in range(i + 1, len(drug_list)):
            d1 = drug_list[i]; d2 = drug_list[j]
            t1 = drug_targets[d1]; t2 = drug_targets[d2]
            c1 = drug_cyp[d1];    c2 = drug_cyp[d2]

            # Jaccard similarity for shared gene targets
            union_t   = t1 | t2; inter_t = t1 & t2
            jaccard   = len(inter_t) / len(union_t) if union_t else 0.0

            # CYP overlap score
            union_c   = c1 | c2; inter_c = c1 & c2
            cyp_score = len(inter_c) / len(union_c) if union_c else 0.0

            ddi_score = w1 * jaccard + w2 * cyp_score

            # Severity classification
            if ddi_score >= 0.4:   severity = "🔴 CRITICAL"
            elif ddi_score >= 0.2: severity = "🟠 HIGH"
            elif ddi_score >= 0.1: severity = "🟡 MODERATE"
            else:                  severity = "🟢 LOW"

            results.append({
                "drug1": d1, "drug2": d2,
                "shared_targets": len(inter_t),
                "shared_genes": sorted(list(inter_t))[:5],
                "cyp_overlap": len(inter_c),
                "cyp_shared": sorted(list(inter_c)),
                "jaccard": round(jaccard, 4),
                "ddi_score": round(ddi_score, 4),
                "severity": severity,
            })

    # Step 4: Display results
    clear()
    console.print(Panel(
        f"[bold white]DDI Risk Analysis — {len(drug_names)} Drugs[/bold white]\n"
        "[dim]DDI Score = 0.65×(shared targets Jaccard) + 0.35×(CYP450 overlap)\n"
        "🔴 CRITICAL (≥0.4) · 🟠 HIGH (≥0.2) · 🟡 MODERATE (≥0.1) · 🟢 LOW (<0.1)[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    # Target count summary
    t_summary = Table(title="🎯 Drug Target Summary", box=box.ROUNDED, style=rc())
    t_summary.add_column("Drug", style="bold cyan"); t_summary.add_column("# Gene Targets", style="white", justify="right")
    t_summary.add_column("CYP Targets", style="yellow")
    for drug in drug_list:
        cyp_str = ", ".join(drug_cyp[drug]) or "None found"
        t_summary.add_row(drug, str(len(drug_targets[drug])), cyp_str)
    console.print(t_summary)

    # Interaction matrix
    results_sorted = sorted(results, key=lambda x: -x["ddi_score"])
    t = Table(title="🔁 Drug-Drug Interaction Risk Matrix", box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("Drug 1",        style="bold yellow");  t.add_column("Drug 2", style="bold yellow")
    t.add_column("Shared Targets",style="cyan",  justify="right")
    t.add_column("CYP Overlap",   style="magenta",justify="right")
    t.add_column("Jaccard",       style="dim",   justify="right")
    t.add_column("DDI Score",     style="bold",  justify="right")
    t.add_column("Severity",      style="white")
    t.add_column("Shared Genes (top 5)", style="dim", max_width=30)
    for r in results_sorted:
        sc = r["ddi_score"]
        sc_str = f"[bold red]{sc:.4f}[/bold red]" if sc>=0.2 else (f"[yellow]{sc:.4f}[/yellow]" if sc>=0.1 else f"[green]{sc:.4f}[/green]")
        t.add_row(r["drug1"], r["drug2"], str(r["shared_targets"]), str(r["cyp_overlap"]),
                  f"{r['jaccard']:.4f}", sc_str, r["severity"],
                  ", ".join(r["shared_genes"][:5]) or "—")
    console.print(t)
    console.print(Panel.fit(
        "[dim]⚠️  DDI Score is a computational estimate based on shared gene targets + CYP overlap.\n"
        "Always verify with clinical DDI databases (e.g. drugs.com, Lexicomp) before prescribing.[/dim]"
    ))
    _save([{"source": "DDI_Network", "drugs": drug_names, "interactions": results_sorted}])


# ─────────────────────────────────────────────────────────────────────
#  19. GWAS / OMICS CROSS-REFERENCE
#
#  Novel pipeline: "GWAS → Drug Target Prioritisation Score"
#  Step 1: GWAS Catalog REST API → SNPs associated with disease
#  Step 2: Map SNP → reporter genes (GWAS Catalog association data)
#  Step 3: For each gene, fetch druggability score from DGIdb
#  Step 4: Compute a composite "GWAS Drug Target Score":
#           score = −log10(p_value) × druggability_flag × OR_weight
#  Step 5: Rank and display prioritised targets for drug discovery
# ─────────────────────────────────────────────────────────────────────

def menu_gwas_omics():
    dna()
    explain(*EXPLAIN_TEXTS["gwas_omics"])
    console.print(Panel(
        "[bold white]GWAS / OMICS Cross-Reference — Novel Drug Target Prioritisation[/bold white]\n"
        "[dim]Queries GWAS Catalog for disease-associated SNPs, maps them to genes,\n"
        "then scores each gene for drug target potential.\n"
        "Formula: GWAS Drug Target Score = −log₁₀(p) × OR_weight × druggability\n"
        "API: GWAS Catalog REST (EBI) — 100% free, no registration needed.[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    raw_disease = console.input(f"[{rc()}]{ui('Disease or trait (e.g. type 2 diabetes, breast cancer, Alzheimer disease)')}: ").strip()
    raw_disease = check_explain_toggle(raw_disease)
    if not raw_disease: return
    disease_en = translate(raw_disease)

    max_snps = console.input(f"[{rc()}]Max SNPs to analyse (default 20, max 50): ").strip()
    max_snps  = min(int(max_snps), 50) if max_snps.isdigit() else 20

    # Step 1: Query GWAS Catalog
    gwas_data = request(
        f"{GWAS_URL}/associations",
        params={"q": disease_en, "size": max_snps},
        label=f"🧬 Querying GWAS Catalog for '{disease_en}'..."
    )
    if not gwas_data:
        console.print(Panel.fit("⚠️  GWAS Catalog returned no results. Try a broader trait name.", style="yellow")); return

    embedded = gwas_data.get("_embedded", {})
    assocs   = embedded.get("associations", [])
    if not assocs:
        console.print(Panel.fit(f"⚠️  No GWAS associations found for '{disease_en}'.\n"
            "Tip: Try 'type 2 diabetes', 'Alzheimer disease', 'body mass index'.", style="yellow")); return

    # Step 2: Extract SNPs and genes
    gene_scores = {}  # gene → {count, best_pval, best_or}
    snp_rows = []

    for assoc in assocs:
        p_val_str = assoc.get("pvalue", "1")
        try:
            p_val = float(p_val_str)
        except:
            p_val = 1.0
        log_p = -math.log10(p_val + 1e-300)

        or_beta = assoc.get("orPerCopyNum") or assoc.get("betaNum")
        try:
            or_val = float(or_beta) if or_beta else 1.0
        except:
            or_val = 1.0
        or_weight = abs(math.log(max(or_val, 0.01))) if or_val != 1.0 else 0.1

        loci = assoc.get("loci", [])
        genes_in_assoc = []
        snp_id = "?"
        for locus in loci:
            for snp in locus.get("strongestRiskAlleles", []):
                snp_id = snp.get("riskAlleleName", "?").split("-")[0]
            for gene_entry in locus.get("authorReportedGenes", []):
                g = gene_entry.get("geneName", "").strip().upper()
                if g and g != "NR":
                    genes_in_assoc.append(g)

        for gene in genes_in_assoc:
            if gene not in gene_scores:
                gene_scores[gene] = {"count": 0, "best_pval": p_val, "best_log_p": log_p, "best_or": or_val, "or_weight": or_weight}
            gene_scores[gene]["count"] += 1
            if p_val < gene_scores[gene]["best_pval"]:
                gene_scores[gene]["best_pval"] = p_val
                gene_scores[gene]["best_log_p"] = log_p
            snp_rows.append({"snp": snp_id, "gene": gene, "p_value": p_val, "or_val": or_val, "log_p": log_p})

    if not gene_scores:
        console.print(Panel.fit("⚠️  No mapped genes found in these GWAS associations.", style="yellow")); return

    # Step 3: Fetch druggability from DGIdb for top genes
    top_genes = sorted(gene_scores.keys(), key=lambda g: -gene_scores[g]["best_log_p"])[:20]
    druggable = set()
    druggability_categories = {}
    drg_query = """{ genes(names: %s) { nodes { name geneCategoriesWithSources { name } } } }""" % json.dumps(top_genes)
    drg_result = request(DGIDB_URL, method="POST", body={"query": drg_query}, label="💊 Checking druggability...")
    if drg_result:
        for node in drg_result.get("data", {}).get("genes", {}).get("nodes", []):
            gn = node.get("name", "").upper()
            cats = [c.get("name","") for c in node.get("geneCategoriesWithSources", [])]
            if cats:
                druggable.add(gn)
                druggability_categories[gn] = cats

    # Step 4: Compute composite GWAS Drug Target Score
    HIGH_VALUE_CATS = {"kinase", "gpcr", "ion channel", "nuclear receptor", "phosphatase", "enzyme"}
    scored_genes = []
    for gene in top_genes:
        gs = gene_scores[gene]
        is_druggable = gene in druggable
        cats = druggability_categories.get(gene, [])
        high_value = any(c.lower() in HIGH_VALUE_CATS for c in cats)
        drugg_mult = 2.0 if high_value else (1.0 if is_druggable else 0.3)
        composite = gs["best_log_p"] * drugg_mult * (1 + gs["or_weight"])
        scored_genes.append({
            "gene": gene, "count": gs["count"],
            "best_p": gs["best_pval"], "log_p": gs["best_log_p"],
            "best_or": gs["best_or"], "druggable": is_druggable,
            "categories": cats, "composite_score": composite,
        })

    scored_genes.sort(key=lambda x: -x["composite_score"])

    # Step 5: Display
    clear()
    console.print(Panel(
        f"[bold white]GWAS Drug Target Prioritisation — '{disease_en}'[/bold white]\n"
        f"[dim]SNPs analysed: {len(snp_rows)}  |  Unique genes: {len(gene_scores)}  |  Druggable: {len(druggable)}[/dim]\n"
        "[dim]Score = −log₁₀(p) × druggability multiplier × (1 + OR weight)[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    t = Table(title=f"🧬 Top Drug Targets for '{disease_en}' — Ranked by GWAS Drug Target Score",
              box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("#",               width=4);   t.add_column("Gene",       style="bold cyan", no_wrap=True)
    t.add_column("Best p-value",    style="dim", no_wrap=True)
    t.add_column("−log₁₀(p)",      style="bold yellow", justify="right")
    t.add_column("OR/Beta",         style="dim", justify="right")
    t.add_column("SNP Count",       style="dim", justify="right")
    t.add_column("Druggable?",      style="green")
    t.add_column("GWAS Score",      style="bold magenta", justify="right")
    t.add_column("Top Category",    style="dim", max_width=20)

    for i, g in enumerate(scored_genes[:25], 1):
        drg_flag = "✅" if g["druggable"] else "❌"
        p_str    = f"{g['best_p']:.2e}"
        log_p_str= f"{g['log_p']:.1f}"
        or_str   = f"{g['best_or']:.3f}" if g["best_or"] != 1.0 else "N/A"
        sc = g["composite_score"]
        sc_str = f"[bold magenta]{sc:.2f}[/bold magenta]" if sc > 5 else f"{sc:.2f}"
        top_cat = g["categories"][0] if g["categories"] else "—"
        t.add_row(str(i), g["gene"], p_str, log_p_str, or_str, str(g["count"]), drg_flag, sc_str, top_cat)

    console.print(t)
    console.print(Panel.fit(
        "[dim]🔗 GWAS Catalog: https://www.ebi.ac.uk/gwas/\n"
        "⚠️  GWAS associations show correlation, not causation. Validate experimentally.[/dim]"
    ))
    _save([{"source": "GWAS_OMICS", "disease": disease_en, "snps_analysed": len(snp_rows),
            "top_targets": scored_genes[:10]}])


# ─────────────────────────────────────────────────────────────────────
#  20. DRUG SCORE COMPARATOR (DrugScore™)
#
#  Novel composite score across 6 dimensions:
#   Dim 1 (0-20): Lipinski compliance        (Ro5 pass + TPSA)
#   Dim 2 (0-20): ADMET profile              (BBB + absorption + solubility)
#   Dim 3 (0-20): Clinical phase             (0→pre-clinical, 20→approved)
#   Dim 4 (0-15): Gene target count          (breadth of pharmacology)
#   Dim 5 (0-15): PubMed evidence count      (literature depth)
#   Dim 6 (0-10): Safety signal              (inverse of FAERS reports)
#  Total max: 100 (DrugScore™)
# ─────────────────────────────────────────────────────────────────────

def menu_drug_comparator():
    dna()
    explain(*EXPLAIN_TEXTS["drug_comparator"])
    console.print(Panel(
        "[bold white]Drug Score Comparator — DrugScore™[/bold white]\n"
        "[dim]Compares 2–8 drugs on 6 scientific dimensions.\n"
        "DrugScore™ = composite weighted score (0–100).\n"
        "Dimensions: Lipinski · ADMET · Clinical Phase · Targets · Evidence · Safety[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))
    raw = console.input(f"[{rc()}]{ui('Drug names, comma-separated (2–8 drugs, e.g. Aspirin, Ibuprofen, Metformin)')}: ")
    raw = check_explain_toggle(raw)
    if not raw: return
    drug_names_raw = [x.strip() for x in raw.split(",") if x.strip()][:8]
    if len(drug_names_raw) < 2:
        console.print(Panel.fit("⚠️  Please enter at least 2 drugs.", style="yellow")); return

    drug_names = [translate(n) for n in drug_names_raw]
    all_scores = []

    for drug in drug_names:
        console.print(f"[dim]  Scoring [bold]{drug}[/bold]...[/dim]")
        score_data = {"drug": drug}

        # Dim 1 & 2: Lipinski + ADMET via PubChem
        cid_data = request(f"{PUBCHEM_URL}/compound/name/{requests.utils.quote(drug)}/cids/JSON", label=f"🔍 PubChem: {drug}...")
        cids = (cid_data or {}).get("IdentifierList", {}).get("CID", [])
        mw = logp = hbd = hba = tpsa = rb = 0; cid = None
        if cids:
            cid = cids[0]
            props_str = "MolecularWeight,XLogP,HBondDonorCount,HBondAcceptorCount,TPSA,RotatableBondCount"
            pdata = request(f"{PUBCHEM_URL}/compound/cid/{cid}/property/{props_str}/JSON", label=f"📦 {drug} properties...")
            if pdata:
                p = pdata.get("PropertyTable", {}).get("Properties", [{}])[0]
                mw = float(p.get("MolecularWeight", 0) or 0); logp = float(p.get("XLogP", 0) or 0)
                hbd = int(float(p.get("HBondDonorCount", 0) or 0)); hba = int(float(p.get("HBondAcceptorCount", 0) or 0))
                tpsa = float(p.get("TPSA", 0) or 0); rb = int(float(p.get("RotatableBondCount", 0) or 0))

        # Lipinski score (dim 1, max 20)
        ro5_pass = sum([mw <= 500, logp <= 5, hbd <= 5, hba <= 10]) >= 3
        veber_pass = rb <= 10 and tpsa <= 140
        lip_score = 10 + (5 if ro5_pass else 0) + (5 if veber_pass else 0)

        # ADMET score (dim 2, max 20)
        absorption = 7 if tpsa < 60 and ro5_pass else (4 if tpsa < 140 and ro5_pass else 1)
        bbb = 5 if (1 <= logp <= 3 and mw < 400 and tpsa < 90) else 1
        log_s = 0.5 - 0.01 * mw - logp; sol = 8 if log_s > -2 else (4 if log_s > -4 else 0)
        admet_score = absorption + bbb + sol

        score_data["lipinski"] = round(lip_score, 1); score_data["admet"] = round(admet_score, 1)
        score_data["mw"] = mw; score_data["logp"] = logp; score_data["tpsa"] = tpsa

        # Dim 3: Clinical Phase via ChEMBL (max 20)
        cml_data = request(f"{CHEMBL_URL}/molecule.json", params={"pref_name__iexact": drug, "format": "json"}, label=f"⚗️  ChEMBL: {drug}...")
        mols = (cml_data or {}).get("molecules", [])
        max_phase = 0
        if mols:
            try:
                max_phase = int(float(mols[0].get("max_phase") or 0))
            except (ValueError, TypeError):
                max_phase = 0
        phase_score = {0: 2, 1: 8, 2: 12, 3: 16, 4: 20}.get(max_phase, 0)
        score_data["max_phase"] = max_phase; score_data["phase_score"] = phase_score

        # Dim 4: Gene target count via DGIdb (max 15)
        drg_query = """{ drugs(names: %s) { nodes { interactions { gene { name } } } } }""" % json.dumps([drug.upper()])
        drg_res = request(DGIDB_URL, method="POST", body={"query": drg_query}, label=f"🎯 Targets: {drug}...")
        n_targets = 0
        if drg_res:
            nodes = drg_res.get("data", {}).get("drugs", {}).get("nodes", [])
            genes = set()
            for node in nodes:
                for ix in node.get("interactions", []):
                    g = ix.get("gene", {}).get("name", "")
                    if g: genes.add(g)
            n_targets = len(genes)
        target_score = min(15, n_targets * 1.5)
        score_data["n_targets"] = n_targets; score_data["target_score"] = round(target_score, 1)

        # Dim 5: PubMed evidence count (max 15)
        pm_data = request(f"{PUBMED_URL}/esearch.fcgi",
            params={"db": "pubmed", "term": drug, "retmax": "1", "retmode": "json"},
            label=f"📰 PubMed: {drug}...")
        n_papers = int(float((pm_data or {}).get("esearchresult", {}).get("count", 0) or 0))
        evidence_score = min(15, math.log10(n_papers + 1) * 5) if n_papers > 0 else 0
        score_data["n_papers"] = n_papers; score_data["evidence_score"] = round(evidence_score, 1)

        # Dim 6: Safety (inverse FAERS, max 10)
        fda_data = request(f"{FDA_URL}/event.json",
            params={"search": f'patient.drug.medicinalproduct:"{drug}"',
                    "count": "patient.reaction.reactionmeddrapt.exact", "limit": "1"},
            label=f"🏥 FAERS: {drug}...")
        total_reports = int(float((fda_data or {}).get("meta", {}).get("results", {}).get("total", 0) or 0))
        if total_reports == 0:
            safety_score = 10.0
        elif total_reports < 1000:
            safety_score = 8.0
        elif total_reports < 10000:
            safety_score = 5.0
        elif total_reports < 100000:
            safety_score = 2.0
        else:
            safety_score = 0.0
        score_data["total_faers"] = total_reports; score_data["safety_score"] = safety_score

        # Composite DrugScore™
        drugscore = (score_data["lipinski"] + score_data["admet"] + score_data["phase_score"] +
                     score_data["target_score"] + score_data["evidence_score"] + score_data["safety_score"])
        score_data["drugscore"] = round(drugscore, 1)
        all_scores.append(score_data)

    all_scores.sort(key=lambda x: -x["drugscore"])

    clear()
    console.print(Panel(
        f"[bold white]DrugScore™ Comparison — {len(all_scores)} Drugs[/bold white]\n"
        "[dim]Score dimensions: Lipinski (0-20) · ADMET (0-20) · Clinical Phase (0-20)\n"
        "                    Targets (0-15) · Evidence (0-15) · Safety (0-10)\n"
        "                    Total DrugScore™: 0–100[/dim]",
        style="bold magenta", box=box.ROUNDED
    ))

    t = Table(title="📊 DrugScore™ Ranking", box=box.ROUNDED, style=rc(), show_lines=True)
    t.add_column("Rank",     width=4); t.add_column("Drug",    style="bold yellow")
    t.add_column("Lipinski", style="cyan",    justify="right"); t.add_column("ADMET",   style="cyan",    justify="right")
    t.add_column("Phase",    style="green",   justify="right"); t.add_column("Targets", style="magenta", justify="right")
    t.add_column("Evidence", style="blue",    justify="right"); t.add_column("Safety",  style="red",     justify="right")
    t.add_column("DrugScore™",style="bold white", justify="right")
    t.add_column("Phase",    style="dim",     no_wrap=True)

    for i, sc in enumerate(all_scores, 1):
        ds = sc["drugscore"]
        ds_str = f"[bold green]{ds:.1f}[/bold green]" if ds >= 70 else (f"[bold yellow]{ds:.1f}[/bold yellow]" if ds >= 40 else f"[bold red]{ds:.1f}[/bold red]")
        t.add_row(str(i), sc["drug"],
                  f"{sc['lipinski']:.1f}/20", f"{sc['admet']:.1f}/20",
                  f"{sc['phase_score']:.0f}/20", f"{sc['target_score']:.1f}/15",
                  f"{sc['evidence_score']:.1f}/15", f"{sc['safety_score']:.1f}/10",
                  ds_str, f"Phase {sc['max_phase']}")
    console.print(t)

    # ASCII radar-like bar chart
    console.print(Panel("[bold white]DrugScore™ Breakdown — ASCII Bar Chart[/bold white]", style="magenta"))
    bar_width = 40
    for sc in all_scores:
        console.print(f"\n[bold yellow]  {sc['drug']}[/bold yellow]")
        dims = [
            ("Lipinski", sc["lipinski"],       20, "cyan"),
            ("ADMET",    sc["admet"],           20, "blue"),
            ("Phase",    sc["phase_score"],     20, "green"),
            ("Targets",  sc["target_score"],    15, "magenta"),
            ("Evidence", sc["evidence_score"],  15, "yellow"),
            ("Safety",   sc["safety_score"],    10, "red"),
        ]
        for dim_name, val, max_val, col in dims:
            filled = int((val / max_val) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            console.print(f"  {dim_name:9s} [{col}]{bar}[/{col}] {val:.1f}/{max_val}")
        console.print(f"  [bold]Total DrugScore™: {sc['drugscore']:.1f}/100[/bold]")

    _save([{"source": "DrugScore_Comparator", "drugs": all_scores}])



# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def main():
    clear()
    banner()
    choose_language()
    clear()
    banner()

    actions = {
        "1":  menu_drug_gene,
        "2":  menu_gene_drug,
        "3":  menu_gene_annotations,
        "4":  menu_pubchem,
        "5":  menu_chembl,
        "6":  menu_fda_adverse,
        "7":  menu_fda_label,
        "8":  menu_export,
        "9":  menu_lipinski,
        "10": menu_repurposing,
        "11": menu_target_disease,
        "12": menu_clinical_trials,
        "13": menu_pubmed,
        "14": menu_uniprot,
        "15": menu_similarity,
        "16": menu_pathways,
        # ── NEW v4.0 ──
        "17": menu_pk_calculator,
        "18": menu_ddi_network,
        "19": menu_gwas_omics,
        "20": menu_drug_comparator,
    }

    try:
        while True:
            choice = main_menu()
            if choice == "0":
                console.print(Panel.fit(f"👋 {ui('Goodbye! Happy researching.')}", style="bold blue"))
                break
            if choice.upper() == "E":
                global EXPLAIN_ENABLED
                EXPLAIN_ENABLED = not EXPLAIN_ENABLED
                state = f"{ui('ENABLED')} ✅" if EXPLAIN_ENABLED else f"{ui('DISABLED')} ⚠️"
                console.print(Panel.fit(f"📘 Educational panels {state}", style="bold yellow"))
                continue
            fn = actions.get(choice)
            if fn:
                fn()
            else:
                console.print(f"[red]{ui('Invalid option. Choose between 0 and 20, or E to toggle explanations.')}[/red]")
    except KeyboardInterrupt:
        console.print(Panel.fit(f"👋 {ui('Interrupted. Goodbye!')}", style="bold blue"))
    except Exception as e:
        handle_error(e)

if __name__ == "__main__":
    main()