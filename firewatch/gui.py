import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .evaluation import evaluate, evaluation_csv
from .gateway import configured_model, configuration_status
from .integration import check_gemini
from .models import (Evidence, EvaluationDecision, FireContext, HumanAssessment,
                     HumanReview, Incident, SharedState, ShadowDataset)
from .research import human_comparison, human_comparison_csv, run_shadow
from .comparison import compare, comparison_csv, comparison_report
from .bundle import comparison_bundle
from .pipeline import Pipeline
from .presentation import agent_summary
from .scenarios import SCENARIOS, get_scenario
from .storage import Store


class FireWatchApp:
    def __init__(self, root, data_dir="data"):
        self.root = root
        self.store = Store(data_dir)
        self.current = None
        self.evaluation = None
        self.busy = False
        self.filling_form = False
        self.running_fingerprint = None
        self.live_steps = []
        self.messages = queue.Queue()
        self.fields = {}
        self.context_fields = {}
        self.shadow_dataset = None
        self.shadow_analysis = None
        self.comparison = None
        self.comparison_cancel = threading.Event()
        self.gemini_model = tk.StringVar(value=configured_model())
        root.title("FireWatch AI — V6 | Comparative Evaluation & Evidence Bundles")
        root.geometry("1120x760")
        root.minsize(760, 560)
        root.configure(bg="#101d30")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#edf1f5")
        style.configure("TLabel", background="#edf1f5", foreground="#182c43", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("TNotebook.Tab", padding=(6, 8), font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff", background="#101d30")
        style.configure("Hero.TLabel", foreground="#c3d1df", background="#101d30")
        style.configure("Card.TLabel", font=("Segoe UI", 11, "bold"), background="#ffffff")
        header = tk.Frame(root, bg="#101d30", padx=20, pady=14)
        header.pack(fill="x")
        ttk.Label(header, text="FIREWATCH AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="V6 • Paired evaluation • Audited execution modes • Exportable evidence bundles", style="Hero.TLabel").pack(anchor="w")
        tk.Label(header, text="EDUCATIONAL PROTOTYPE  |  Synthetic examples  |  No independent fire diagnosis",
                 bg="#101d30", fg="#ffcb77", font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        cards = tk.Frame(root, bg="#edf1f5", padx=15, pady=10)
        cards.pack(fill="x")
        self.card_vars = {}
        for key, initial in (("Assessment", "Not analyzed"), ("Priority", "Not analyzed"), ("Human review", "Pending analysis"), ("Mode", "Deterministic")):
            panel = tk.Frame(cards, bg="white", padx=12, pady=8)
            panel.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(panel, text=key.upper(), bg="white", fg="#64768a", font=("Segoe UI", 8)).pack(anchor="w")
            var = tk.StringVar(value=initial)
            self.card_vars[key] = var
            ttk.Label(panel, textvariable=var, style="Card.TLabel", wraplength=160).pack(anchor="w")
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.incident_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.incident_tab, text="Incident")
        self.build_form()
        self.outputs = {}
        for name in ("Multi-Agent Analysis", "Workflow", "Evidence", "Safety & Human Gate", "Explainable Report", "Agent Trace", "Shared State", "Evaluation", "LLM", "V5", "V6"):
            tab = ttk.Frame(self.tabs)
            short_labels = {"Multi-Agent Analysis": "Agents",
                            "Explainable Report": "Report", "Agent Trace": "Trace", "Shared State": "State",
                            "Evaluation": "Eval", "Safety & Human Gate": "Review"}
            self.tabs.add(tab, text=short_labels.get(name, name))
            if name == "V5":
                self.build_v5_panel(tab)
                continue
            if name == "V6":
                self.build_comparison_panel(tab)
                continue
            if name == "Workflow":
                self.build_workflow_canvas(tab)
            if name == "Safety & Human Gate":
                self.build_review(tab)
            if name == "Evidence":
                self.build_evidence_panel(tab)
            if name == "Explainable Report":
                bar = ttk.Frame(tab)
                bar.pack(fill="x", padx=10, pady=5)
                ttk.Button(bar, text="Export TXT report", command=self.export_report).pack(side="left")
                ttk.Button(bar, text="Export run JSON", command=self.export_run).pack(side="left", padx=8)
            if name == "Evaluation":
                self.build_evaluation_panel(tab)
            if name == "LLM":
                self.build_llm_panel(tab)
            output = ScrolledText(tab, wrap="word", bg="#ffffff", fg="#182c43",
                                  font=("Consolas", 10), padx=12, pady=10, relief="flat")
            output.pack(fill="both", expand=True, padx=10, pady=8)
            output.configure(state="disabled")
            self.outputs[name] = output
        footer = ttk.Frame(root)
        footer.pack(fill="x", padx=16, pady=(0, 8))
        self.status = tk.StringVar(value="Ready — choose a synthetic scenario or enter a manual observation.")
        ttk.Label(footer, textvariable=self.status, wraplength=1050).pack(anchor="w")
        self.load_scenario()
        self.refresh_history()
        self.show_llm_status()
        for var in self.fields.values():
            var.trace_add("write", lambda *_: self.input_changed())
        for var in self.context_fields.values():
            var.trace_add("write", lambda *_: self.input_changed())
        self.conflict.trace_add("write", lambda *_: self.input_changed())
        self.llm.trace_add("write", lambda *_: self.input_changed())
        self.gemini_model.trace_add("write", lambda *_: self.input_changed())
        self.description.bind("<<Modified>>", self.description_changed)
        self.description.edit_modified(False)
        root.after(100, self.poll)

    def build_comparison_panel(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=5)
        self.comparison_case = tk.StringVar(value=list(SCENARIOS)[2])
        ttk.Combobox(bar, textvariable=self.comparison_case, values=["All 10 synthetic cases", *SCENARIOS], state="readonly", width=34).pack(side="left", fill="x", expand=True)
        self.comparison_repetitions = tk.StringVar(value="2")
        ttk.Label(bar, text="Trials").pack(side="left", padx=4)
        ttk.Combobox(bar, textvariable=self.comparison_repetitions, values=["1", "2", "3"], state="readonly", width=3).pack(side="left")
        self.comparison_llm = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Candidate uses Gemini", variable=self.comparison_llm).pack(side="left", padx=4)
        controls = ttk.Frame(tab)
        controls.pack(fill="x", padx=8, pady=3)
        self.comparison_button = ttk.Button(controls, text="Run paired comparison", command=self.run_comparison)
        self.comparison_button.pack(side="left")
        self.cancel_comparison_button = ttk.Button(controls, text="Stop after current pair", command=self.comparison_cancel.set, state="disabled")
        self.cancel_comparison_button.pack(side="left", padx=4)
        self.comparison_note = tk.StringVar(value="Offline replay by default. Gemini sends synthetic observations using the selected model in LLM. Up to 5 agent calls / 10 HTTP attempts per pair; stop takes effect after the current pair.")
        ttk.Label(tab, textvariable=self.comparison_note, wraplength=950).pack(anchor="w", padx=10, pady=4)
        history = ttk.Frame(tab)
        history.pack(fill="x", padx=8, pady=3)
        self.comparison_history_var = tk.StringVar()
        self.comparison_history = ttk.Combobox(history, textvariable=self.comparison_history_var, state="readonly")
        self.comparison_history.pack(side="left", fill="x", expand=True)
        ttk.Button(history, text="Load comparison", command=self.load_comparison).pack(side="left", padx=4)
        exports = ttk.Frame(tab)
        exports.pack(fill="x", padx=8, pady=3)
        for label, extension in (("Export JSON", ".json"), ("CSV", ".csv"), ("TXT", ".txt"), ("Evidence ZIP", ".zip")):
            ttk.Button(exports, text=label, command=lambda ext=extension: self.export_comparison(ext)).pack(side="left", padx=2)
        ttk.Button(exports, text="Open candidate run", command=self.open_comparison_run).pack(side="left", padx=4)
        table = ttk.Frame(tab)
        table.pack(fill="x", padx=8, pady=3)
        columns = ("case", "trial", "mode", "agreement", "review", "critic")
        self.comparison_tree = ttk.Treeview(table, columns=columns, show="headings", height=4)
        for key, title, width in (("case", "Synthetic scenario", 260), ("trial", "Trial", 45), ("mode", "Actual mode", 95),
                                  ("agreement", "Final agreement", 105), ("review", "Candidate review", 130), ("critic", "Critic", 90)):
            self.comparison_tree.heading(key, text=title)
            self.comparison_tree.column(key, width=width, minwidth=40)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.comparison_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.comparison_tree.configure(yscrollcommand=scrollbar.set)
        self.comparison_tree.pack(fill="x")
        horizontal = ttk.Scrollbar(tab, orient="horizontal", command=self.comparison_tree.xview)
        horizontal.pack(fill="x", padx=8)
        self.comparison_tree.configure(xscrollcommand=horizontal.set)
        output = ScrolledText(tab, wrap="word", font=("Consolas", 10), height=7)
        output.pack(fill="both", expand=True, padx=8, pady=5)
        output.configure(state="disabled")
        self.outputs["Comparison"] = output

    def run_comparison(self):
        if self.busy:
            return
        use_llm = self.comparison_llm.get()
        if use_llm and not configuration_status()["key_configured"]:
            messagebox.showinfo("Gemini comparison", "Configure a key in the launching process, or uncheck Candidate uses Gemini for offline replay.")
            return
        try:
            selected = self.comparison_case.get()
            numbers = list(range(1, 11)) if selected == "All 10 synthetic cases" else [list(SCENARIOS).index(selected) + 1]
            repetitions = int(self.comparison_repetitions.get())
        except ValueError:
            messagebox.showerror("Comparison", "Select a catalogue case and a trial count.")
            return
        model = self.gemini_model.get().strip()
        self.comparison_cancel.clear()
        self.start_job("comparison", lambda: compare(self.store, use_llm=use_llm, scenario_numbers=numbers,
            repetitions=repetitions, model=model, cancel_event=self.comparison_cancel,
            on_progress=lambda data: self.messages.put(("comparison_progress", data, None))))

    def show_comparison(self, evaluation):
        from .evaluation import decision_fields
        self.comparison = evaluation
        m = evaluation.metrics
        self.comparison_note.set(f"{evaluation.status} | {evaluation.requested_candidate} | Final agreement {m.final_decision_agreement}/{m.pairs} | Validated provider pairs {m.fully_validated_provider_pairs}/{m.pairs} | Intact runs {m.intact_runs}/{m.runs_checked}. No fire-accuracy claim.")
        self.comparison_tree.delete(*self.comparison_tree.get_children())
        for index, row in enumerate(evaluation.rows):
            self.comparison_tree.insert("", "end", iid=str(index), values=(row.scenario, row.repetition, row.candidate.mode,
                "Match" if decision_fields(row.reference) == decision_fields(row.candidate) else "Different",
                "REQUIRED" if row.candidate.safety.human_review_required else "OPTIONAL", row.candidate.critic.verdict))
        self.set_output("Comparison", comparison_report(evaluation))

    def load_comparison(self):
        cid = self.comparison_history_map.get(self.comparison_history_var.get())
        if cid and not self.busy:
            self.show_comparison(self.store.load_comparison(cid))
            self.status.set("Saved comparative report restored with its original run links and actual modes.")

    def open_comparison_run(self):
        selected = self.comparison_tree.selection()
        if selected and self.comparison and not self.busy:
            result = self.store.load(self.comparison.rows[int(selected[0])].candidate.run_id)
            self.fill(result.incident)
            self.display(result)
            self.tabs.select(1)

    def export_comparison(self, extension):
        if not self.comparison or self.busy:
            return
        if extension == ".json":
            self.write_export(self.comparison.model_dump_json(indent=2), extension)
        elif extension == ".csv":
            self.write_export(comparison_csv(self.comparison), extension)
        elif extension == ".txt":
            self.write_export(comparison_report(self.comparison), extension)
        else:
            filename = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Evidence bundle ZIP", "*.zip")])
            if filename:
                try:
                    Path(filename).write_bytes(comparison_bundle(self.comparison, self.store))
                    self.status.set("Evidence ZIP saved with original runs, human records, traces and checksum manifest.")
                except (OSError, ValueError, KeyError) as exc:
                    messagebox.showerror("Bundle export failed", str(exc))

    def build_v5_panel(self, tab):
        book = ttk.Notebook(tab)
        book.pack(fill="both", expand=True, padx=6, pady=6)
        for name in ("Context", "Human comparison", "Shadow"):
            panel = ttk.Frame(book)
            book.add(panel, text=name)
            if name == "Human comparison":
                bar = ttk.Frame(panel)
                bar.pack(fill="x", padx=8, pady=5)
                self.human_fields = {}
                definitions = [("reviewer", None), ("assessment", ["NO_INDICATION", "POSSIBLE_FIRE", "STRONG_INDICATION", "INSUFFICIENT_EVIDENCE"]),
                               ("risk", ["LOW", "MEDIUM", "HIGH", "UNDETERMINED"]), ("human_review", ["REQUIRED", "OPTIONAL"])]
                for row, (key, choices) in enumerate(definitions):
                    ttk.Label(bar, text=key.replace("_", " ").title()).grid(row=row, column=0, sticky="w", padx=4, pady=2)
                    var = tk.StringVar(value="")
                    self.human_fields[key] = var
                    widget = ttk.Combobox(bar, textvariable=var, values=choices, state="readonly") if choices else ttk.Entry(bar, textvariable=var)
                    widget.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
                bar.columnconfigure(1, weight=1)
                self.human_rationale = tk.StringVar()
                ttk.Label(bar, text="Rationale").grid(row=4, column=0, padx=4)
                ttk.Entry(bar, textvariable=self.human_rationale).grid(row=4, column=1, sticky="ew", padx=4)
                ttk.Button(bar, text="Record human judgment", command=self.save_human_assessment).grid(row=5, column=1, sticky="w", pady=4)
                exports = ttk.Frame(panel)
                exports.pack(fill="x", padx=8)
                ttk.Button(exports, text="Export comparison JSON", command=self.export_human_comparison).pack(side="left")
                ttk.Button(exports, text="Export CSV", command=lambda: self.export_human_comparison(csv=True)).pack(side="left", padx=6)
                ttk.Label(panel, text="Enter your own judgment for the selected run. GUI entries are marked system_output_seen = true; this is not a blinded human baseline. Approval and synthetic labels remain separate.", wraplength=900).pack(anchor="w", padx=8, pady=5)
            elif name == "Shadow":
                bar = ttk.Frame(panel)
                bar.pack(fill="x", padx=8, pady=5)
                ttk.Button(bar, text="Load dataset JSON", command=self.load_shadow_dataset).pack(side="left")
                ttk.Button(bar, text="Load synthetic demo", command=self.load_shadow_demo).pack(side="left", padx=4)
                self.shadow_dataset_note = tk.StringVar(value="No dataset loaded.")
                ttk.Label(panel, textvariable=self.shadow_dataset_note, wraplength=900).pack(anchor="w", padx=8)
                cutoff_bar = ttk.Frame(panel)
                cutoff_bar.pack(fill="x", padx=8, pady=5)
                self.shadow_cutoff = tk.StringVar(value="2026-10-14T12:00:00Z")
                ttk.Label(cutoff_bar, text="Cutoff (ISO with timezone)").pack(side="left")
                ttk.Entry(cutoff_bar, textvariable=self.shadow_cutoff, width=30).pack(side="left", padx=4)
                self.shadow_button = ttk.Button(cutoff_bar, text="Run Shadow (offline)", command=self.analyze_shadow)
                self.shadow_button.pack(side="left")
                export_bar = ttk.Frame(panel)
                export_bar.pack(fill="x", padx=8)
                ttk.Button(export_bar, text="Export shadow JSON", command=self.export_shadow).pack(side="left")
                ttk.Button(export_bar, text="Export TXT", command=lambda: self.export_shadow(txt=True)).pack(side="left", padx=4)
                self.shadow_history_var = tk.StringVar()
                self.shadow_history = ttk.Combobox(panel, textvariable=self.shadow_history_var, state="readonly")
                self.shadow_history.pack(fill="x", padx=8, pady=5)
                ttk.Button(panel, text="Load saved shadow", command=self.load_saved_shadow).pack(anchor="w", padx=8)
                ttk.Label(panel, text="Only records observed AND available by the cutoff are analyzed. Unknown availability is excluded. No eligible records = no run. Saved results stay linked to their own cutoff even if the input changes.", wraplength=900).pack(anchor="w", padx=8, pady=4)
            else:
                ttk.Label(panel, text="Descriptive context linked to evidence. No spread forecast. Unlinked context, exposure inconsistencies and restricted access with indicators add human-review reasons.", wraplength=900).pack(anchor="w", padx=8, pady=6)
            output = ScrolledText(panel, wrap="word", font=("Consolas", 10), height=7)
            output.pack(fill="both", expand=True, padx=8, pady=6)
            output.configure(state="disabled")
            self.outputs[name] = output

    def show_human_comparison(self):
        if self.current:
            data = human_comparison(self.current, self.store.human_assessments(self.current.run_id))
            self.set_output("Human comparison", json.dumps(data, indent=2, ensure_ascii=False))

    def save_human_assessment(self):
        if not self.current or self.busy:
            messagebox.showinfo("Human comparison", "Analyze or load a saved run first.")
            return
        try:
            values = {key: var.get().strip() for key, var in self.human_fields.items()}
            if values["human_review"] not in ("REQUIRED", "OPTIONAL"):
                raise ValueError("Select the human-review judgment explicitly")
            assessment = HumanAssessment(run_id=self.current.run_id, reviewer=values["reviewer"],
                                         rationale=self.human_rationale.get(), system_output_seen=True,
                                         decision=EvaluationDecision(assessment=values["assessment"], risk=values["risk"],
                                                                     human_review=values["human_review"] == "REQUIRED"))
            self.store.save_human_assessment(assessment)
            self.show_human_comparison()
            self.status.set("Human judgment recorded separately; the original Safety Gate remains unchanged.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Human judgment not saved", str(exc))

    def export_human_comparison(self, csv=False):
        if self.current:
            data = human_comparison(self.current, self.store.human_assessments(self.current.run_id))
            self.write_export(human_comparison_csv(data) if csv else json.dumps(data, indent=2, ensure_ascii=False), ".csv" if csv else ".json")

    def load_shadow_dataset(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(filetypes=[("Shadow dataset JSON", "*.json")])
        if filename:
            try:
                dataset = ShadowDataset.model_validate_json(Path(filename).read_text(encoding="utf-8-sig"))
                self.shadow_dataset = dataset
                self.shadow_dataset_note.set(f"Loaded dataset {dataset.dataset_id}: {len(dataset.records)} records. Availability is declared, not verified.")
            except (ValueError, OSError) as exc:
                messagebox.showerror("Invalid shadow dataset", str(exc))

    def load_shadow_demo(self):
        if self.busy:
            return
        from .v5_demo import shadow_demo
        self.shadow_dataset = shadow_demo()
        self.shadow_cutoff.set("2026-10-14T12:00:00Z")
        self.shadow_dataset_note.set("Synthetic demo loaded: 4 records, two excluded at the default cutoff. No real incident.")

    def analyze_shadow(self):
        if self.busy:
            return
        try:
            if self.shadow_dataset is None:
                raise ValueError("Load a dataset or the synthetic demo first")
            cutoff = datetime.fromisoformat(self.shadow_cutoff.get().strip().replace("Z", "+00:00"))
            if cutoff.tzinfo is None or cutoff.utcoffset() is None:
                raise ValueError("Cutoff must include a timezone")
            dataset = self.shadow_dataset
        except ValueError as exc:
            messagebox.showerror("Shadow input", str(exc))
            return
        self.start_job("shadow", lambda: run_shadow(dataset, cutoff, store=self.store))

    def show_shadow(self, analysis):
        self.shadow_analysis = analysis
        self.set_output("Shadow", analysis.model_dump_json(indent=2))

    def load_saved_shadow(self):
        shadow_id = self.shadow_history_map.get(self.shadow_history_var.get())
        if shadow_id and not self.busy:
            self.show_shadow(self.store.load_shadow(shadow_id))
            self.status.set("Saved shadow restored; its audit shows the cutoff used for that result.")

    def export_shadow(self, txt=False):
        if self.shadow_analysis:
            self.write_export(self.shadow_analysis.result.report if txt else self.shadow_analysis.model_dump_json(indent=2), ".txt" if txt else ".json")

    def build_llm_panel(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=12, pady=8)
        ttk.Label(bar, text="Requested model").pack(side="left")
        ttk.Entry(bar, textvariable=self.gemini_model, width=30).pack(side="left", padx=8)
        self.provider_button = ttk.Button(bar, text="Test Gemini JSON", command=self.test_provider)
        self.provider_button.pack(side="left")
        ttk.Button(bar, text="Refresh status", command=self.show_llm_status).pack(side="left", padx=8)
        self.llm_status = tk.StringVar()
        ttk.Label(tab, textvariable=self.llm_status, wraplength=950).pack(anchor="w", padx=12, pady=4)
        ttk.Label(tab, text="Test Gemini JSON sends a configuration probe only. Enabling Gemini for Analyze Incident sends the supplied observations to the provider. The synthetic pilot remains deterministic.",
                  wraplength=950).pack(anchor="w", padx=12, pady=4)

    def show_llm_status(self):
        status = configuration_status()
        self.llm_status.set(f"Key configured in this process: {'YES' if status['key_configured'] else 'NO'}. "
                            "Keys are never displayed or exported. A successful probe verifies JSON access only.")
        data = {"configuration": status, "selected_model": self.gemini_model.get(),
                "latest_saved_probe": None, "current_run_calls": []}
        probe = self.store.latest_provider_check()
        if probe:
            data["latest_saved_probe"] = probe.model_dump(mode="json")
        if self.current:
            data["run_id"] = self.current.run_id
            data["current_run_calls"] = [call.model_dump(mode="json") for call in self.current.llm_calls]
            data["retained_review_requests"] = self.current.llm_review_requests
        self.set_output("LLM", json.dumps(data, indent=2, ensure_ascii=False))

    def test_provider(self):
        model = self.gemini_model.get().strip()
        self.start_job("provider_check", lambda: check_gemini(model=model, store=self.store))

    def build_evidence_panel(self, tab):
        self.evidence_note = tk.StringVar(value="No analysis selected. Completeness is not confidence or source verification.")
        ttk.Label(tab, textvariable=self.evidence_note, wraplength=950).pack(anchor="w", padx=12, pady=8)
        frame = ttk.Frame(tab)
        frame.pack(fill="x", padx=10)
        columns = ("source", "provenance", "method", "timestamp", "flags")
        self.evidence_tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)
        for key, title, width in (("source", "Declared source", 220), ("provenance", "Provenance", 95),
                                  ("method", "Method", 70), ("timestamp", "Observed at", 210), ("flags", "Checks", 170)):
            self.evidence_tree.heading(key, text=title)
            self.evidence_tree.column(key, width=width, minwidth=60)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.evidence_tree.yview)
        vertical.pack(side="right", fill="y")
        self.evidence_tree.configure(yscrollcommand=vertical.set)
        self.evidence_tree.pack(fill="x")
        horizontal = ttk.Scrollbar(tab, orient="horizontal", command=self.evidence_tree.xview)
        horizontal.pack(fill="x", padx=10)
        self.evidence_tree.configure(xscrollcommand=horizontal.set)

    def show_evidence(self, result):
        self.evidence_tree.delete(*self.evidence_tree.get_children())
        quality = result.evidence_quality
        label = (f"Indicator fields known: {quality.known_indicator_fields}/3 ({quality.completeness}). "
                 if quality else "No V2/V3 quality summary in this older run. ")
        self.evidence_note.set(label + "Provenance is declared; completeness does not verify source truth.")
        checked = result.evidence_result
        for record in result.incident.evidence:
            flags = []
            if record.id in checked.stale_ids: flags.append("old")
            if record.id in checked.future_ids: flags.append("future time")
            if record.id in checked.conflicts: flags.append("conflict flagged")
            self.evidence_tree.insert("", "end", iid=record.id,
                                      values=(record.source, record.provenance, record.method,
                                              record.observed_at.isoformat(), ", ".join(flags) or "No timestamp/conflict flag"))

    def build_evaluation_panel(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=5)
        self.eval_button = ttk.Button(bar, text="Run pilot (10 cases × 2 trials)", command=self.run_evaluation)
        self.eval_button.pack(side="left")
        ttk.Button(bar, text="Export JSON", command=self.export_evaluation).pack(side="left", padx=6)
        ttk.Button(bar, text="Export CSV", command=self.export_evaluation_csv).pack(side="left")
        cards = ttk.Frame(tab)
        cards.pack(fill="x", padx=10, pady=4)
        self.eval_metrics_vars = {}
        for key in ("System matches", "Checklist matches", "Missed / extra reviews", "Repeated decisions"):
            column = len(self.eval_metrics_vars)
            cards.columnconfigure(column, weight=1, uniform="evaluation")
            frame = ttk.Frame(cards)
            frame.grid(row=0, column=column, sticky="ew", padx=3)
            ttk.Label(frame, text=key, font=("Segoe UI", 9), wraplength=150).pack(anchor="w")
            var = tk.StringVar(value="—")
            self.eval_metrics_vars[key] = var
            ttk.Label(frame, textvariable=var, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        self.eval_note = tk.StringVar(value="Synthetic reference labels. Checklist is executable code, not measured human judgment.")
        ttk.Label(tab, textvariable=self.eval_note, wraplength=950).pack(anchor="w", padx=12, pady=4)
        history = ttk.Frame(tab)
        history.pack(fill="x", padx=10, pady=4)
        self.eval_history_var = tk.StringVar()
        self.eval_history = ttk.Combobox(history, textvariable=self.eval_history_var, state="readonly")
        self.eval_history.pack(side="left", fill="x", expand=True)
        ttk.Button(history, text="Load saved pilot", command=self.load_pilot).pack(side="left", padx=6)
        ttk.Button(history, text="Open selected analysis", command=self.open_evaluation_case).pack(side="left")
        table = ttk.Frame(tab)
        table.pack(fill="x", padx=10, pady=4)
        columns = ("scenario", "assessment", "risk", "review", "system", "baseline", "repeat")
        self.eval_tree = ttk.Treeview(table, columns=columns, show="headings", height=4)
        for key, title, width in (("scenario", "Synthetic case", 250), ("assessment", "Assessment", 150),
                                  ("risk", "Priority", 120), ("review", "Review", 75), ("system", "System", 65),
                                  ("baseline", "Checklist", 70), ("repeat", "Repeat", 65)):
            self.eval_tree.heading(key, text=title)
            self.eval_tree.column(key, width=width, minwidth=50)
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.eval_tree.yview)
        vertical.pack(side="right", fill="y")
        self.eval_tree.configure(yscrollcommand=vertical.set)
        self.eval_tree.pack(fill="x")
        horizontal = ttk.Scrollbar(tab, orient="horizontal", command=self.eval_tree.xview)
        horizontal.pack(fill="x", padx=10)
        self.eval_tree.configure(xscrollcommand=horizontal.set)
        self.eval_tree.tag_configure("pass", background="#e2f0e8")
        self.eval_tree.tag_configure("fail", background="#fff0d4")
        self.eval_tree.bind("<<TreeviewSelect>>", self.evaluation_case_selected)

    def show_evaluation(self, data):
        self.evaluation = data
        metrics, total = data["metrics"], data["total"]
        self.eval_metrics_vars["System matches"].set(f"{metrics['system_case_matches']}/{total}")
        self.eval_metrics_vars["Checklist matches"].set(f"{metrics['baseline_case_matches']}/{total}")
        self.eval_metrics_vars["Missed / extra reviews"].set(f"{metrics['system_missed_reviews']} / {metrics['system_extra_reviews']}")
        self.eval_metrics_vars["Repeated decisions"].set(f"{metrics['reproducible_cases']}/{total}")
        self.eval_note.set(f"Citation ID occurrences valid: {metrics['valid_citation_ids']}/{metrics['citation_ids_checked']} (truth not verified). "
                           f"Trace run IDs valid: {metrics['valid_trace_run_ids']}/{metrics['completed_runs']}. "
                           f"Expected reviews: {metrics['expected_reviews']}; system required: {metrics['system_required_reviews']}. "
                           f"Checklist missed/extra reviews: {metrics['baseline_missed_reviews']}/{metrics['baseline_extra_reviews']}. "
                           f"Mean pipeline time: {metrics['mean_duration_ms']:.2f} ms. Synthetic protocol only.")
        self.eval_tree.delete(*self.eval_tree.get_children())
        for index, row in enumerate(data["rows"]):
            actual = row["actual"]
            self.eval_tree.insert("", "end", iid=str(index), tags=("pass" if row["passed"] else "fail",),
                                  values=(row["scenario"], actual["assessment"], actual["risk"],
                                          "Required" if actual["human_review"] else "Optional",
                                          "Match" if row["passed"] else "Mismatch",
                                          "Match" if row["baseline_passed"] else "Mismatch",
                                          "Stable" if row["reproducible"] else "Changed"))
        self.set_output("Evaluation", data["baseline_description"] + "\n\n" + data["limitation"]
                        + "\n\nSelect a row to inspect expected/actual fields and trial IDs.")

    def evaluation_case_selected(self, _):
        selection = self.eval_tree.selection()
        if selection and self.evaluation:
            row = self.evaluation["rows"][int(selection[0])]
            self.set_output("Evaluation", json.dumps(row, indent=2, ensure_ascii=False))

    def open_evaluation_case(self):
        selection = self.eval_tree.selection()
        if not selection or not self.evaluation or self.busy:
            return
        row = self.evaluation["rows"][int(selection[0])]
        result = self.store.load(row["run_id"])
        self.fill(result.incident)
        self.display(result)
        self.tabs.select(1)
        self.status.set(f"Loaded pilot analysis for {row['scenario']}; editing requires a new analysis.")

    def load_pilot(self):
        evaluation_id = self.eval_history_map.get(self.eval_history_var.get())
        if evaluation_id and not self.busy:
            self.show_evaluation(self.store.load_evaluation(evaluation_id).model_dump(mode="json"))
            self.status.set("Saved pilot evaluation loaded.")

    def build_workflow_canvas(self, tab):
        panel = ttk.Frame(tab)
        panel.pack(fill="x", padx=10, pady=6)
        self.flow_canvas = tk.Canvas(panel, height=230, bg="#edf1f5", highlightthickness=0,
                                     scrollregion=(0, 0, 650, 560))
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.flow_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.flow_canvas.configure(yscrollcommand=scrollbar.set)
        self.flow_canvas.pack(fill="x", expand=True)
        self.flow_positions = {
            "evidence": (210, 35), "planner": (210, 95), "information_request": (500, 155),
            "fire_assessment": (210, 155), "risk_exposure": (210, 215), "decision": (210, 275),
            "critic": (210, 335), "revision": (500, 275), "safety_gate": (210, 395),
            "reporter": (210, 455), "human_gate": (210, 515),
        }
        connections = [("evidence", "planner"), ("planner", "fire_assessment"),
                       ("planner", "information_request"), ("information_request", "fire_assessment"),
                       ("fire_assessment", "risk_exposure"), ("risk_exposure", "decision"),
                       ("decision", "critic"), ("critic", "revision"), ("revision", "decision"),
                       ("critic", "safety_gate"), ("safety_gate", "reporter"), ("reporter", "human_gate")]
        for source, target in connections:
            x1, y1 = self.flow_positions[source]
            x2, y2 = self.flow_positions[target]
            if x1 == x2:
                points = (x1, y1+18, x2, y2-18)
            elif y1 == y2:
                points = (x1-90, y1, x2+90, y2)
            else:
                points = (x1+90, y1, x2, y1, x2, y2+(18 if y2 < y1 else -18))
            self.flow_canvas.create_line(*points, arrow="last", fill="#7b8999", width=2)
        self.flow_boxes = {}
        for name, (x, y) in self.flow_positions.items():
            box = self.flow_canvas.create_rectangle(x-90, y-18, x+90, y+18, fill="white", outline="#7b8999", width=2)
            self.flow_boxes[name] = box
            self.flow_canvas.create_text(x, y, text=name.replace("_", " ").title(), font=("Segoe UI", 9))

    def refresh_flow(self, steps):
        visited = {step.node for step in steps}
        current = steps[-1].node if steps else None
        for name, box in self.flow_boxes.items():
            self.flow_canvas.itemconfigure(box, fill="#ffcb77" if name == current else "#b8e4d6" if name in visited else "white")
        path = " → ".join(step.node.replace("_", " ") for step in steps)
        self.set_output("Workflow", "EXECUTED NODES — amber: last completed; green: previously visited\n\n"
                        + (path or "No nodes executed yet.")
                        + "\n\nPlanner selects the information-request branch or direct assessment."
                        " Critic can return to Decision once; remaining issues go to human review.")

    def form_fingerprint(self):
        return (tuple((key, var.get()) for key, var in self.fields.items()),
                tuple((key, var.get()) for key, var in self.context_fields.items()),
                self.conflict.get(), self.description.get("1.0", "end").strip(),
                self.llm.get(), self.gemini_model.get())

    def description_changed(self, _):
        if self.description.edit_modified():
            self.input_changed()
            self.description.edit_modified(False)

    def input_changed(self):
        if self.filling_form:
            return
        self.card_vars["Assessment"].set("NOT ANALYZED")
        self.card_vars["Priority"].set("NOT ANALYZED")
        self.card_vars["Human review"].set("ANALYSIS NEEDED")
        self.card_vars["Mode"].set("PENDING")
        self.current = None
        if not self.busy:
            self.status.set("Input changed — analyze again. Previous results remain saved in history.")
            for name in self.outputs:
                if name not in ("Evaluation", "LLM", "Shadow", "Comparison"):
                    self.set_output(name, "Input changed. Run Analyze Incident or load a saved run.")
            for box in self.flow_boxes.values():
                self.flow_canvas.itemconfigure(box, fill="white")
            if hasattr(self, "evidence_tree"):
                self.evidence_tree.delete(*self.evidence_tree.get_children())
                self.evidence_note.set("Input changed; analyze again to inspect evidence.")

    def build_form(self):
        bar = ttk.Frame(self.incident_tab)
        bar.pack(fill="x", padx=12, pady=10)
        self.scenario = tk.StringVar(value=next(iter(SCENARIOS)))
        choices = ttk.Frame(bar)
        choices.pack(fill="x")
        controls = ttk.Frame(bar)
        controls.pack(fill="x", pady=(8, 0))
        selector = ttk.Combobox(choices, textvariable=self.scenario, values=list(SCENARIOS), state="readonly", width=38)
        selector.pack(side="left", fill="x", expand=True)
        selector.bind("<<ComboboxSelected>>", lambda _: self.load_scenario())
        ttk.Button(choices, text="Custom observation", command=self.custom).pack(side="left", padx=8)
        self.llm = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Use Gemini (optional)", variable=self.llm).pack(side="left")
        self.run_button = ttk.Button(controls, text="Analyze Incident", command=self.analyze)
        self.run_button.pack(side="left", padx=8)
        # Form scrolling is independent of root size; no screen-height assumptions.
        canvas = tk.Canvas(self.incident_tab, bg="#edf1f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.incident_tab, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12)
        canvas.configure(yscrollcommand=scrollbar.set)
        form = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        form.columnconfigure(1, weight=1)
        field_defs = [
            ("location", "Location", None),
            ("environment", "Environment", ["vegetation", "urban_interface"]),
            ("smoke", "Smoke", ["yes", "no", "unknown"]),
            ("flames", "Flames", ["yes", "no", "unknown"]),
            ("exposure", "People / infrastructure exposed", ["yes", "no", "unknown"]),
            ("humidity_pct", "Humidity (%) — blank = unknown", None),
            ("wind_kmh", "Wind (km/h) — blank = unknown", None),
            ("temperature_c", "Temperature (°C) — blank = unknown", None),
            ("vegetation", "Vegetation", ["dry", "not_dry", "unknown"]),
            ("source", "Evidence source", None),
            ("method", "Evidence method", ["manual", "sensor", "document"]),
            ("provenance", "Evidence provenance", ["synthetic", "reported", "measured"]),
            ("observed_at", "Observed at (ISO 8601 with timezone)", None),
        ]
        for row, (key, label, choices) in enumerate(field_defs):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            var = tk.StringVar()
            self.fields[key] = var
            widget = (ttk.Combobox(form, textvariable=var, values=choices, state="readonly")
                      if choices else ttk.Entry(form, textvariable=var))
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
        self.conflict = tk.BooleanVar()
        ttk.Checkbutton(form, text="Record contains conflicting observations (manually flagged)", variable=self.conflict).grid(
            row=13, column=0, columnspan=2, sticky="w", padx=6, pady=6)
        ttk.Label(form, text="Description / evidence content (not automatically extracted)").grid(row=14, column=0, columnspan=2, sticky="w", padx=6)
        self.description = ScrolledText(form, height=4, wrap="word", font=("Segoe UI", 10))
        self.description.grid(row=15, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        ttk.Label(form, text="Normalized fields above drive the rules. Source and provenance are declarations, not verification.",
                  wraplength=700).grid(row=16, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        history_bar = ttk.Frame(form)
        history_bar.grid(row=17, column=0, columnspan=2, sticky="ew", padx=6, pady=12)
        self.history_var = tk.StringVar()
        self.history = ttk.Combobox(history_bar, textvariable=self.history_var, state="readonly", width=66)
        self.history.pack(side="left", fill="x", expand=True)
        ttk.Button(history_bar, text="Load saved run", command=self.load_history).pack(side="left", padx=8)
        context_box = ttk.LabelFrame(form, text="V5 — declared context (optional; linked to this evidence record)")
        context_box.grid(row=18, column=0, columnspan=2, sticky="ew", padx=6, pady=10)
        context_box.columnconfigure(1, weight=1)
        definitions = [
            ("fuel_type", "Fuel type", ["grass", "shrub", "forest", "mixed", "unknown"]),
            ("vegetation_density", "Vegetation density", ["sparse", "moderate", "dense", "unknown"]),
            ("slope_deg", "Slope (degrees; blank = unknown)", None),
            ("wind_direction", "Wind direction", ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "unknown"]),
            ("gust_kmh", "Wind gust (km/h; blank = unknown)", None),
            ("distance_to_people_m", "Distance to people (m; blank = unknown)", None),
            ("distance_to_infrastructure_m", "Distance to infrastructure (m; blank = unknown)", None),
            ("people_present", "People reported present", ["yes", "no", "unknown"]),
            ("critical_infrastructure", "Critical infrastructure reported present", ["yes", "no", "unknown"]),
            ("access_status", "Reported access", ["open", "limited", "blocked", "unknown"]),
        ]
        for row, (key, label, choices) in enumerate(definitions):
            ttk.Label(context_box, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar()
            self.context_fields[key] = var
            widget = ttk.Combobox(context_box, textvariable=var, values=choices, state="readonly") if choices else ttk.Entry(context_box, textvariable=var)
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=3)

    def build_review(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=8)
        self.reviewer = tk.StringVar()
        self.review_comment = tk.StringVar()
        ttk.Label(bar, text="Reviewer").grid(row=0, column=0, padx=4)
        ttk.Entry(bar, textvariable=self.reviewer, width=24).grid(row=0, column=1, padx=4)
        ttk.Label(bar, text="Comment").grid(row=0, column=2, padx=4)
        ttk.Entry(bar, textvariable=self.review_comment).grid(row=0, column=3, sticky="ew", padx=4)
        bar.columnconfigure(3, weight=1)
        ttk.Button(bar, text="Record approval", command=lambda: self.save_review("APPROVED")).grid(row=1, column=1, pady=6)
        ttk.Button(bar, text="Record rejection", command=lambda: self.save_review("REJECTED")).grid(row=1, column=3, pady=6, sticky="w")
        ttk.Label(tab, text="Approval records review only. It does not clear hazards or trigger external actions.",
                  wraplength=900).pack(anchor="w", padx=14)

    def fill(self, incident):
        self.filling_form = True
        record = incident.evidence[0]
        for key, var in self.fields.items():
            value = getattr(incident, key, None) if hasattr(incident, key) else getattr(record, key)
            if key == "observed_at":
                value = record.observed_at.isoformat()
            var.set("" if value is None else str(value))
        for key, var in self.context_fields.items():
            value = getattr(incident.context, key)
            var.set("" if value is None else str(value))
        self.conflict.set(record.conflicts)
        self.description.delete("1.0", "end")
        self.description.insert("1.0", incident.description)
        self.description.edit_modified(False)
        self.filling_form = False
        self.input_changed()

    def load_scenario(self):
        self.fill(get_scenario(self.scenario.get()))

    def custom(self):
        self.fill(Incident(location="Enter location", evidence=[Evidence(
            source="Manual observation", provenance="reported", content="Manual observation; unverified.")]))

    def collect(self):
        values = {key: var.get().strip() for key, var in self.fields.items()}
        for key in ("humidity_pct", "wind_kmh", "temperature_c"):
            values[key] = float(values[key]) if values[key] else None
        description = self.description.get("1.0", "end").strip()
        record = Evidence(source=values.pop("source"), method=values.pop("method"), provenance=values.pop("provenance"),
                          observed_at=datetime.fromisoformat(values.pop("observed_at")),
                          content=description or "Normalized observation fields entered manually.", conflicts=self.conflict.get())
        contextual = {key: var.get().strip() for key, var in self.context_fields.items()}
        for key in ("slope_deg", "gust_kmh", "distance_to_people_m", "distance_to_infrastructure_m"):
            contextual[key] = float(contextual[key]) if contextual[key] else None
        context = FireContext(**contextual)
        linked = [record.id] if any(v not in (None, "unknown") for v in context.model_dump().values()) else []
        return Incident(**values, description=description, evidence=[record], context=context, context_evidence_ids=linked)

    def start_job(self, kind, fn):
        if self.busy:
            return
        self.busy = True
        self.run_button.configure(state="disabled")
        self.eval_button.configure(state="disabled")
        self.provider_button.configure(state="disabled")
        self.shadow_button.configure(state="disabled")
        self.comparison_button.configure(state="disabled")
        self.cancel_comparison_button.configure(state="normal" if kind == "comparison" else "disabled")
        self.status.set("Running synthetic pilot — 10 cases, two deterministic trials each."
                        if kind == "evaluation" else "Running offline Shadow Mode at the selected cutoff."
                        if kind == "shadow" else "Running paired comparison; progress appears after each pair."
                        if kind == "comparison" else "Analyzing incident — interface remains available.")
        def work():
            try:
                self.messages.put((kind, fn(), None))
            except Exception as exc:
                self.messages.put((kind, None, f"{type(exc).__name__}: operation failed; check local input/data access."))
        threading.Thread(target=work, daemon=True).start()

    def analyze(self):
        if self.busy:
            return
        try:
            incident = self.collect()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid observation", str(exc))
            return
        use_llm = self.llm.get()
        model = self.gemini_model.get().strip()
        self.running_fingerprint = self.form_fingerprint()
        self.live_steps = []
        self.refresh_flow([])
        def job():
            result = Pipeline(model=model).run(incident, use_llm=use_llm,
                                    on_step=lambda step: self.messages.put(("progress", step, None)))
            self.store.save(result)
            return result
        self.start_job("analysis", job)

    def run_evaluation(self):
        self.start_job("evaluation", lambda: evaluate(self.store))

    def poll(self):
        try:
            while True:
                kind, value, error = self.messages.get_nowait()
                if kind == "comparison_progress":
                    self.status.set(f"Comparison: {value['completed_pairs']}/{value['requested_pairs']} pairs | {value['scenario']} | {value['candidate_mode']}")
                    continue
                if kind == "progress":
                    self.live_steps.append(value)
                    self.refresh_flow(self.live_steps)
                    self.set_output("Shared State", "INTERMEDIATE GRAPH STATE — analysis in progress\n\n"
                                    + json.dumps(value.state, indent=2, ensure_ascii=False))
                    self.status.set(f"Completed node {value.step}: {value.node}")
                    continue
                self.busy = False
                self.run_button.configure(state="normal")
                self.eval_button.configure(state="normal")
                self.provider_button.configure(state="normal")
                self.shadow_button.configure(state="normal")
                self.comparison_button.configure(state="normal")
                self.cancel_comparison_button.configure(state="disabled")
                if error:
                    self.status.set(error)
                    messagebox.showerror("Operation failed", error)
                elif kind == "analysis":
                    self.display(value)
                    self.tabs.select(1)
                    self.status.set(f"Saved run {value.run_id} | {value.duration_ms:.1f} ms | {value.mode}")
                    if self.form_fingerprint() != self.running_fingerprint:
                        self.input_changed()
                        self.status.set("Result saved for the earlier input. Current form changed; analyze again or load the saved run.")
                elif kind == "provider_check":
                    self.show_llm_status()
                    self.status.set("Gemini JSON probe succeeded; fire-analysis validation is separate."
                                    if value.succeeded else f"Gemini JSON probe failed: {value.error_code}.")
                elif kind == "shadow":
                    self.show_shadow(value)
                    self.status.set(f"Shadow analysis saved: {value.shadow_id}; cutoff {value.audit.cutoff.isoformat()}.")
                elif kind == "comparison":
                    self.show_comparison(value)
                    self.status.set(f"Comparison {value.status.lower()}: {value.metrics.pairs} saved pairs. Requested mode and actual audits are shown separately.")
                else:
                    self.show_evaluation(value)
                    self.status.set("Pilot complete: 10 synthetic cases, 20 saved runs and persisted comparison metrics.")
                self.refresh_history()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def set_output(self, name, content):
        output = self.outputs[name]
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("1.0", content)
        output.configure(state="disabled")

    def display(self, result):
        self.current = result
        # Do not carry a previous run's entered judgment into another run.
        for key in ("assessment", "risk", "human_review"):
            self.human_fields[key].set("")
        self.human_rationale.set("")
        self.card_vars["Assessment"].set(result.assessment.status)
        self.card_vars["Priority"].set(result.risk.level)
        self.card_vars["Human review"].set("REQUIRED" if result.safety.human_review_required else "OPTIONAL")
        self.card_vars["Mode"].set(result.mode.upper())
        self.set_output("Multi-Agent Analysis", agent_summary(result))
        evidence = {"records": [e.model_dump(mode="json") for e in result.incident.evidence],
                    "analysis": result.evidence_result.model_dump(),
                    "quality": result.evidence_quality.model_dump() if result.evidence_quality else "Not recorded by this older version"}
        self.set_output("Evidence", json.dumps(evidence, indent=2, ensure_ascii=False))
        self.show_evidence(result)
        self.set_output("Explainable Report", result.report)
        self.set_output("Agent Trace", "\n".join(e.model_dump_json() for e in result.trace))
        self.refresh_flow(result.graph_steps)
        self.update_review_output()
        self.show_llm_status()
        self.set_output("Context", result.context_result.model_dump_json(indent=2) if result.context_result else "Context was not recorded by this older version.")
        self.show_human_comparison()

    def update_review_output(self):
        if not self.current:
            return
        content = {"run_id": self.current.run_id, "safety": self.current.safety.model_dump(),
                   "human_reviews": [r.model_dump(mode="json") for r in self.store.reviews(self.current.run_id)]}
        self.set_output("Safety & Human Gate", json.dumps(content, indent=2, ensure_ascii=False))
        state = SharedState.from_run(self.current, self.store.reviews(self.current.run_id))
        self.set_output("Shared State", "COMPLETED RUN SNAPSHOT — not a live execution graph\n\n" + state.model_dump_json(indent=2))

    def save_review(self, decision):
        if not self.current:
            messagebox.showinfo("Review", "Analyze or load a saved run first.")
            return
        try:
            review = HumanReview(run_id=self.current.run_id, decision=decision,
                                reviewer=self.reviewer.get(), comment=self.review_comment.get())
            self.store.review(review)
            self.update_review_output()
            self.status.set(f"Review {decision.lower()} recorded for {review.run_id}.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Review not saved", str(exc))

    def refresh_history(self):
        self.history_map = {f"{at} | {run_id}": run_id for run_id, at in self.store.recent()}
        self.history.configure(values=list(self.history_map))
        if self.history_map:
            self.history_var.set(next(iter(self.history_map)))
        self.eval_history_map = {f"{at} | {evaluation_id}": evaluation_id for evaluation_id, at in self.store.evaluations()}
        self.eval_history.configure(values=list(self.eval_history_map))
        if self.eval_history_map:
            self.eval_history_var.set(next(iter(self.eval_history_map)))
        self.shadow_history_map = {f"{at} | {shadow_id}": shadow_id for shadow_id, at in self.store.shadows()}
        self.shadow_history.configure(values=list(self.shadow_history_map))
        if self.shadow_history_map:
            self.shadow_history_var.set(next(iter(self.shadow_history_map)))
        self.comparison_history_map = {f"{at} | {cid}": cid for cid, at in self.store.comparisons()}
        self.comparison_history.configure(values=list(self.comparison_history_map))
        if self.comparison_history_map:
            self.comparison_history_var.set(next(iter(self.comparison_history_map)))

    def load_history(self):
        run_id = self.history_map.get(self.history_var.get())
        if run_id and not self.busy:
            result = self.store.load(run_id)
            self.fill(result.incident)
            self.display(result)
            self.status.set(f"Loaded saved run {run_id}. Editing the form requires a new analysis.")

    def write_export(self, content, extension):
        filename = filedialog.asksaveasfilename(defaultextension=extension,
                                               filetypes=[(extension.upper(), "*" + extension)])
        if filename:
            try:
                Path(filename).write_text(content, encoding="utf-8", newline="")
                self.status.set("Export saved.")
            except OSError:
                messagebox.showerror("Export failed", "Cannot write to the selected location.")

    def export_report(self):
        if self.current:
            self.write_export(self.current.report, ".txt")

    def export_run(self):
        if self.current:
            data = self.current.model_dump(mode="json")
            data["human_reviews"] = [r.model_dump(mode="json") for r in self.store.reviews(self.current.run_id)]
            self.write_export(json.dumps(data, indent=2, ensure_ascii=False), ".json")

    def export_evaluation(self):
        if self.evaluation:
            self.write_export(json.dumps(self.evaluation, indent=2), ".json")

    def export_evaluation_csv(self):
        if self.evaluation:
            self.write_export(evaluation_csv(self.evaluation), ".csv")


def launch(data_dir="data"):
    root = tk.Tk()
    FireWatchApp(root, data_dir)
    root.mainloop()
