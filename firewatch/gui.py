import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .evaluation import evaluate
from .models import Evidence, HumanReview, Incident, SharedState
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
        self.messages = queue.Queue()
        self.fields = {}
        root.title("FireWatch AI — V1 | Traceable Workflow")
        root.geometry("1120x760")
        root.minsize(760, 560)
        root.configure(bg="#101d30")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#edf1f5")
        style.configure("TLabel", background="#edf1f5", foreground="#182c43", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("TNotebook.Tab", padding=(9, 8), font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff", background="#101d30")
        style.configure("Hero.TLabel", foreground="#c3d1df", background="#101d30")
        style.configure("Card.TLabel", font=("Segoe UI", 11, "bold"), background="#ffffff")
        header = tk.Frame(root, bg="#101d30", padx=20, pady=14)
        header.pack(fill="x")
        ttk.Label(header, text="FIREWATCH AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="V1 • Specialized components • Shared state • Human review", style="Hero.TLabel").pack(anchor="w")
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
        for name in ("Multi-Agent Analysis", "Evidence", "Safety & Human Gate", "Explainable Report", "Agent Trace", "Shared State", "Evaluation"):
            tab = ttk.Frame(self.tabs)
            short_labels = {"Multi-Agent Analysis": "Agents", "Safety & Human Gate": "Safety / Review",
                            "Explainable Report": "Report", "Agent Trace": "Trace", "Shared State": "State"}
            self.tabs.add(tab, text=short_labels.get(name, name))
            if name == "Safety & Human Gate":
                self.build_review(tab)
            if name == "Explainable Report":
                bar = ttk.Frame(tab)
                bar.pack(fill="x", padx=10, pady=5)
                ttk.Button(bar, text="Export TXT report", command=self.export_report).pack(side="left")
                ttk.Button(bar, text="Export run JSON", command=self.export_run).pack(side="left", padx=8)
            if name == "Evaluation":
                bar = ttk.Frame(tab)
                bar.pack(fill="x", padx=10, pady=5)
                self.eval_button = ttk.Button(bar, text="Run 10 synthetic scenarios", command=self.run_evaluation)
                self.eval_button.pack(side="left")
                ttk.Button(bar, text="Export evaluation JSON", command=self.export_evaluation).pack(side="left", padx=8)
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
        root.after(100, self.poll)

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
        record = incident.evidence[0]
        for key, var in self.fields.items():
            value = getattr(incident, key, None) if hasattr(incident, key) else getattr(record, key)
            if key == "observed_at":
                value = record.observed_at.isoformat()
            var.set("" if value is None else str(value))
        self.conflict.set(record.conflicts)
        self.description.delete("1.0", "end")
        self.description.insert("1.0", incident.description)

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
        return Incident(**values, description=description, evidence=[record])

    def start_job(self, kind, fn):
        if self.busy:
            return
        self.busy = True
        self.run_button.configure(state="disabled")
        self.eval_button.configure(state="disabled")
        self.status.set("Working — interface remains available. Gemini may take up to several minutes with retries.")
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
        def job():
            result = Pipeline().run(incident, use_llm=use_llm)
            self.store.save(result)
            return result
        self.start_job("analysis", job)

    def run_evaluation(self):
        self.start_job("evaluation", lambda: evaluate(self.store))

    def poll(self):
        try:
            while True:
                kind, value, error = self.messages.get_nowait()
                self.busy = False
                self.run_button.configure(state="normal")
                self.eval_button.configure(state="normal")
                if error:
                    self.status.set(error)
                    messagebox.showerror("Operation failed", error)
                elif kind == "analysis":
                    self.display(value)
                    self.tabs.select(1)
                    self.status.set(f"Saved run {value.run_id} | {value.duration_ms:.1f} ms | {value.mode}")
                else:
                    self.evaluation = value
                    self.set_output("Evaluation", f"{value['passed']}/{value['total']} synthetic scenarios matched project labels.\n"
                                    + value["limitation"] + "\n\n" + json.dumps(value, indent=2))
                    self.status.set("Synthetic evaluation completed and runs saved.")
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
        self.card_vars["Assessment"].set(result.assessment.status)
        self.card_vars["Priority"].set(result.risk.level)
        self.card_vars["Human review"].set("REQUIRED" if result.safety.human_review_required else "OPTIONAL")
        self.card_vars["Mode"].set(result.mode.upper())
        self.set_output("Multi-Agent Analysis", agent_summary(result))
        evidence = {"records": [e.model_dump(mode="json") for e in result.incident.evidence],
                    "analysis": result.evidence_result.model_dump()}
        self.set_output("Evidence", json.dumps(evidence, indent=2, ensure_ascii=False))
        self.set_output("Explainable Report", result.report)
        self.set_output("Agent Trace", "\n".join(e.model_dump_json() for e in result.trace))
        self.update_review_output()

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
                Path(filename).write_text(content, encoding="utf-8")
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


def launch(data_dir="data"):
    root = tk.Tk()
    FireWatchApp(root, data_dir)
    root.mainloop()
