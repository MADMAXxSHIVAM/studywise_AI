"""StudyWise AI - a rule-based smart study planner.

Run:
    python3 StudyWise_AI_Project.py

Python is the core language for the application logic, interface and data handling.
The current desktop interface uses Tkinter, and study topics are saved locally
in studywise_data.json in the same folder as this script. The design can be
extended with a web interface using HTML/CSS/JavaScript if needed.
"""

import json
import sys
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "studywise_data.json"


# --------------------------- AI DECISION ENGINE ---------------------------
def analyse_topic(days_left, difficulty, confidence, importance):
    """Return a priority score, category, explanation and study advice.

    All input values are on a 1-5 scale, except days_left.
    The low-confidence score is higher when the student's confidence is lower.
    """
    if days_left < 0:
        raise ValueError("Days remaining cannot be negative.")
    for value, label in (
        (difficulty, "Difficulty"),
        (confidence, "Confidence"),
        (importance, "Exam importance"),
    ):
        if not 1 <= value <= 5:
            raise ValueError(f"{label} must be between 1 and 5.")

    # Rule 1: convert the time remaining into an urgency score.
    if days_left <= 1:
        urgency = 5
    elif days_left <= 3:
        urgency = 4
    elif days_left <= 7:
        urgency = 3
    elif days_left <= 14:
        urgency = 2
    else:
        urgency = 1

    # Rule 2: combine four factors using transparent weights.
    knowledge_gap = 6 - confidence
    score = round(
        0.30 * urgency
        + 0.25 * difficulty
        + 0.25 * knowledge_gap
        + 0.20 * importance,
        2,
    )

    # Rule 3: classify the topic using the final score.
    if score >= 4.0:
        priority = "HIGH"
        advice = "Revise today for 40 minutes, then solve 5 practice questions."
    elif score >= 3.0:
        priority = "MEDIUM"
        advice = "Schedule a 25-minute revision session within the next 2 days."
    else:
        priority = "LOW"
        advice = "Review this topic for 15 minutes during weekly revision."

    reasons = []
    if urgency >= 4:
        reasons.append("the exam is close")
    if difficulty >= 4:
        reasons.append("the topic is difficult")
    if confidence <= 2:
        reasons.append("confidence is low")
    if importance >= 4:
        reasons.append("exam importance is high")
    explanation = ", ".join(reasons) if reasons else "the topic has a manageable revision profile"

    return {
        "score": score,
        "priority": priority,
        "advice": advice,
        "explanation": explanation,
    }


# ------------------------------ MAIN APP ----------------------------------
class StudyWiseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("StudyWise AI | Smart Study Planner")
        # Keep the app usable on laptop displays. The page itself scrolls when
        # its content is taller than the available screen height.
        self.root.geometry("1180x760")
        self.root.minsize(900, 560)
        self.root.configure(bg="#0b1220")
        self.topics = self.load_topics()
        self.build_styles()
        self.build_interface()
        self.refresh_topics()

        if "--demo" in sys.argv:
            self.load_demo_data()
            self.refresh_topics()
            if self.topics:
                first = max(self.topics, key=lambda item: item["score"])
                self.tree.selection_set(str(first["id"]))
                self.show_recommendation(first)
        if "--demo-plan" in sys.argv:
            self.root.after(900, self.generate_plan)

    def build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#111c2f")
        style.configure("TLabel", background="#0b1220", foreground="#e5edf8", font=("Arial", 10))
        style.configure("Title.TLabel", background="#0b1220", foreground="#f8fafc", font=("Arial", 22, "bold"))
        style.configure("Muted.TLabel", background="#0b1220", foreground="#94a3b8", font=("Arial", 9))
        style.configure("PanelTitle.TLabel", background="#111c2f", foreground="#f8fafc", font=("Arial", 11, "bold"))
        style.configure("CardValue.TLabel", background="#111c2f", foreground="#f8fafc", font=("Arial", 20, "bold"))
        style.configure("CardCaption.TLabel", background="#111c2f", foreground="#94a3b8", font=("Arial", 9))
        style.configure("TEntry", fieldbackground="#1e293b", foreground="#f8fafc", insertcolor="#f8fafc", padding=7)
        style.configure("TCombobox", fieldbackground="#1e293b", background="#1e293b", foreground="#f8fafc", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#1e293b")], foreground=[("readonly", "#f8fafc")])
        style.configure("Accent.TButton", background="#38bdf8", foreground="#082f49", font=("Arial", 10, "bold"), padding=9)
        style.map("Accent.TButton", background=[("active", "#7dd3fc")])
        style.configure("Secondary.TButton", background="#26364d", foreground="#e2e8f0", padding=8)
        style.map("Secondary.TButton", background=[("active", "#334b68")])
        style.configure("Treeview", background="#142238", fieldbackground="#142238", foreground="#e2e8f0", rowheight=30, borderwidth=0, font=("Arial", 9))
        style.configure("Treeview.Heading", background="#1e293b", foreground="#cbd5e1", font=("Arial", 9, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#075985")], foreground=[("selected", "#ffffff")])

    def build_interface(self):
        # Scrollable main page: the add-topic form and lower dashboard panels
        # remain reachable on smaller laptop screens.
        page = ttk.Frame(self.root)
        page.pack(fill="both", expand=True)

        self.page_canvas = tk.Canvas(
            page, bg="#0b1220", highlightthickness=0, borderwidth=0
        )
        self.page_scrollbar = ttk.Scrollbar(
            page, orient="vertical", command=self.page_canvas.yview
        )
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_scrollbar.pack(side="right", fill="y")
        self.page_canvas.pack(side="left", fill="both", expand=True)

        outer = ttk.Frame(self.page_canvas, padding=(22, 18))
        self.page_window = self.page_canvas.create_window(
            (0, 0), window=outer, anchor="nw"
        )
        outer.bind(
            "<Configure>",
            lambda _event: self.page_canvas.configure(
                scrollregion=self.page_canvas.bbox("all")
            ),
        )
        self.page_canvas.bind(
            "<Configure>",
            lambda event: self.page_canvas.itemconfigure(
                self.page_window, width=event.width
            ),
        )

        # Mouse-wheel scrolling works on both Linux (Button-4/5) and
        # Windows/macOS (MouseWheel). The topic table handles its own wheel.
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="StudyWise AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="SMART STUDY PLANNER  |  Rule-based revision priority assistant",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(header, text=date.today().strftime("%d %B %Y"), style="Muted.TLabel").place(relx=1.0, rely=0.25, anchor="ne")

        stats = ttk.Frame(outer)
        stats.pack(fill="x", pady=(0, 16))
        self.stat_total = self.make_stat_card(stats, "TOTAL TOPICS", "0")
        self.stat_high = self.make_stat_card(stats, "HIGH PRIORITY", "0")
        self.stat_done = self.make_stat_card(stats, "COMPLETED", "0")
        self.stat_pending = self.make_stat_card(stats, "STILL TO REVISE", "0")

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0, minsize=300)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self.build_form(content)
        self.build_dashboard(content)

    def make_stat_card(self, parent, caption, value):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=(14, 11))
        card.pack(side="left", fill="x", expand=True, padx=(0, 9))
        value_label = ttk.Label(card, text=value, style="CardValue.TLabel")
        value_label.pack(anchor="w")
        ttk.Label(card, text=caption, style="CardCaption.TLabel").pack(anchor="w", pady=(2, 0))
        return value_label

    def build_form(self, parent):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ttk.Label(panel, text="ADD A STUDY TOPIC", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 12))

        self.subject_var = tk.StringVar()
        self.topic_var = tk.StringVar()
        self.days_var = tk.StringVar(value="7")
        self.difficulty_var = tk.StringVar(value="3")
        self.confidence_var = tk.StringVar(value="3")
        self.importance_var = tk.StringVar(value="3")
        self.minutes_var = tk.StringVar(value="90")

        self.add_field(panel, "Subject", self.subject_var, "e.g. Mathematics")
        self.add_field(panel, "Topic / Chapter", self.topic_var, "e.g. Quadratic Equations")
        self.add_field(panel, "Days left until exam", self.days_var, "Number of days")
        self.add_choice(panel, "Difficulty (1 = easy, 5 = hard)", self.difficulty_var)
        self.add_choice(panel, "Confidence (1 = low, 5 = high)", self.confidence_var)
        self.add_choice(panel, "Exam importance (1-5)", self.importance_var)
        self.add_field(panel, "Available study time per day (minutes)", self.minutes_var, "e.g. 90")

        ttk.Button(panel, text="+  ADD TOPIC & ANALYSE", style="Accent.TButton", command=self.add_topic).pack(fill="x", pady=(14, 8))
        ttk.Button(panel, text="LOAD SAMPLE TOPICS", style="Secondary.TButton", command=self.load_demo_action).pack(fill="x")
        ttk.Label(
            panel,
            text="Your entries are stored locally on this computer. No account or internet connection is needed.",
            style="Muted.TLabel",
            wraplength=255,
            justify="left",
        ).pack(anchor="w", pady=(18, 0))

    def add_field(self, parent, label, variable, hint):
        ttk.Label(parent, text=label, style="PanelTitle.TLabel").pack(anchor="w", pady=(7, 4))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.pack(fill="x")
        entry.insert(0, "") if False else None
        entry.configure(cursor="xterm")

    def add_choice(self, parent, label, variable):
        ttk.Label(parent, text=label, style="PanelTitle.TLabel").pack(anchor="w", pady=(7, 4))
        choice = ttk.Combobox(parent, textvariable=variable, values=["1", "2", "3", "4", "5"], state="readonly")
        choice.pack(fill="x")

    def build_dashboard(self, parent):
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)

        table_panel = ttk.Frame(right, style="Panel.TFrame", padding=14)
        table_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        ttk.Label(table_panel, text="YOUR REVISION TOPICS", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 10))

        # Independent scrollbars let students browse long subject/topic lists.
        tree_area = ttk.Frame(table_panel, style="Panel.TFrame")
        tree_area.pack(fill="both", expand=True)
        tree_area.rowconfigure(0, weight=1)
        tree_area.columnconfigure(0, weight=1)

        columns = ("subject", "topic", "days", "score", "priority", "status")
        self.tree = ttk.Treeview(tree_area, columns=columns, show="headings", selectmode="browse", height=6)
        headings = {"subject": "SUBJECT", "topic": "TOPIC", "days": "DAYS LEFT", "score": "SCORE", "priority": "PRIORITY", "status": "STATUS"}
        widths = {"subject": 105, "topic": 190, "days": 75, "score": 65, "priority": 85, "status": 90}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w" if col in ("subject", "topic") else "center")
        self.tree.tag_configure("HIGH", foreground="#fca5a5")
        self.tree.tag_configure("MEDIUM", foreground="#fcd34d")
        self.tree.tag_configure("LOW", foreground="#86efac")

        tree_ybar = ttk.Scrollbar(tree_area, orient="vertical", command=self.tree.yview)
        tree_xbar = ttk.Scrollbar(tree_area, orient="horizontal", command=self.tree.xview)
        self.tree.configure(
            yscrollcommand=tree_ybar.set,
            xscrollcommand=tree_xbar.set,
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_ybar.grid(row=0, column=1, sticky="ns")
        tree_xbar.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<MouseWheel>", self._on_tree_mousewheel)
        self.tree.bind("<Button-4>", self._on_tree_mousewheel)
        self.tree.bind("<Button-5>", self._on_tree_mousewheel)

        actions = ttk.Frame(table_panel, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="MARK COMPLETED", style="Secondary.TButton", command=self.mark_completed).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="REMOVE", style="Secondary.TButton", command=self.remove_topic).pack(side="left")
        ttk.Button(actions, text="GENERATE TODAY'S PLAN", style="Accent.TButton", command=self.generate_plan).pack(side="right")

        bottom = ttk.Frame(right)
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        recommendation = ttk.Frame(bottom, style="Panel.TFrame", padding=14)
        recommendation.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        ttk.Label(recommendation, text="AI RECOMMENDATION", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.recommendation_text = tk.Text(recommendation, height=7, wrap="word", bg="#111c2f", fg="#cbd5e1", insertbackground="#ffffff", relief="flat", font=("Arial", 9), padx=2, pady=2)
        self.recommendation_text.pack(fill="both", expand=True)
        self.recommendation_text.insert("1.0", "Select a topic to view its priority score, the reasons behind the result and a suggested next step.")
        self.recommendation_text.configure(state="disabled")

        plan = ttk.Frame(bottom, style="Panel.TFrame", padding=14)
        plan.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        ttk.Label(plan, text="TODAY'S STUDY PLAN", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.plan_text = tk.Text(plan, height=7, wrap="word", bg="#111c2f", fg="#cbd5e1", insertbackground="#ffffff", relief="flat", font=("Arial", 9), padx=2, pady=2)
        self.plan_text.pack(fill="both", expand=True)
        self.plan_text.insert("1.0", "Add or load topics, then choose Generate Today's Plan.")
        self.plan_text.configure(state="disabled")

    def _wheel_units(self, event):
        """Translate platform-specific mouse wheel events into scroll units."""
        number = getattr(event, "num", None)
        if number == 4:
            return -3
        if number == 5:
            return 3
        delta = getattr(event, "delta", 0)
        if delta:
            return -int(delta / 120) or (-1 if delta > 0 else 1)
        return 0

    def _on_mousewheel(self, event):
        """Scroll the main page when the pointer is outside the topic table."""
        if getattr(event, "widget", None) == self.tree:
            return self._on_tree_mousewheel(event)
        units = self._wheel_units(event)
        if units:
            self.page_canvas.yview_scroll(units, "units")
        return "break"

    def _on_tree_mousewheel(self, event):
        """Scroll the topic table without moving the whole page."""
        units = self._wheel_units(event)
        if units:
            self.tree.yview_scroll(units, "units")
        return "break"

    def load_topics(self):
        if not DATA_FILE.exists():
            return []
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("Data file", "The saved data file could not be read. A fresh list will be started.")
            return []

    def save_topics(self):
        try:
            DATA_FILE.write_text(json.dumps(self.topics, indent=2), encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Save error", f"Could not save your topics:\n{error}")

    def add_topic(self):
        subject = self.subject_var.get().strip()
        topic = self.topic_var.get().strip()
        if not subject or not topic:
            messagebox.showwarning("Missing information", "Please enter both a subject and a topic.")
            return
        try:
            days = int(self.days_var.get())
            difficulty = int(self.difficulty_var.get())
            confidence = int(self.confidence_var.get())
            importance = int(self.importance_var.get())
            if days < 0:
                raise ValueError("Days left must be zero or more.")
            result = analyse_topic(days, difficulty, confidence, importance)
        except ValueError as error:
            messagebox.showerror("Check your values", str(error))
            return

        new_id = max((int(item.get("id", 0)) for item in self.topics), default=0) + 1
        self.topics.append({
            "id": new_id,
            "subject": subject,
            "topic": topic,
            "days": days,
            "difficulty": difficulty,
            "confidence": confidence,
            "importance": importance,
            "score": result["score"],
            "priority": result["priority"],
            "advice": result["advice"],
            "explanation": result["explanation"],
            "completed": False,
        })
        self.save_topics()
        self.refresh_topics()
        self.subject_var.set("")
        self.topic_var.set("")
        self.show_recommendation(self.topics[-1])

    def refresh_topics(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        ordered = sorted(self.topics, key=lambda item: (item.get("completed", False), -item.get("score", 0)))
        for item in ordered:
            status = "COMPLETED" if item.get("completed") else "PENDING"
            self.tree.insert("", "end", iid=str(item["id"]), values=(
                item["subject"], item["topic"], item["days"], f"{item['score']:.2f}", item["priority"], status
            ), tags=(item["priority"],))
        total = len(self.topics)
        high = sum(1 for item in self.topics if item["priority"] == "HIGH" and not item.get("completed"))
        done = sum(1 for item in self.topics if item.get("completed"))
        self.stat_total.configure(text=str(total))
        self.stat_high.configure(text=str(high))
        self.stat_done.configure(text=str(done))
        self.stat_pending.configure(text=str(total - done))

    def get_selected_topic(self):
        selection = self.tree.selection()
        if not selection:
            return None
        selected_id = int(selection[0])
        return next((item for item in self.topics if int(item["id"]) == selected_id), None)

    def on_select(self, _event=None):
        item = self.get_selected_topic()
        if item:
            self.show_recommendation(item)

    def show_recommendation(self, item):
        text = (
            f"{item['priority']} PRIORITY  |  Score: {item['score']:.2f}/5\n"
            f"WHY: {item['explanation']}.\n"
            f"NEXT: {item['advice']}"
        )
        self.set_text(self.recommendation_text, text)

    def mark_completed(self):
        item = self.get_selected_topic()
        if not item:
            messagebox.showinfo("Select a topic", "Choose a topic from the table first.")
            return
        item["completed"] = not item.get("completed", False)
        self.save_topics()
        self.refresh_topics()
        self.show_recommendation(item)

    def remove_topic(self):
        item = self.get_selected_topic()
        if not item:
            messagebox.showinfo("Select a topic", "Choose a topic from the table first.")
            return
        self.topics = [entry for entry in self.topics if entry["id"] != item["id"]]
        self.save_topics()
        self.refresh_topics()
        self.set_text(self.recommendation_text, "Select a topic to view its recommendation.")

    def generate_plan(self):
        try:
            available = int(self.minutes_var.get())
            if not 15 <= available <= 600:
                raise ValueError
        except ValueError:
            messagebox.showerror("Study time", "Enter a daily study time between 15 and 600 minutes.")
            return
        pending = sorted(
            (item for item in self.topics if not item.get("completed")),
            key=lambda item: item["score"],
            reverse=True,
        )
        lines = [f"TIME: {available} minutes"]
        used = 0
        for item in pending:
            duration = {"HIGH": 40, "MEDIUM": 25, "LOW": 15}[item["priority"]]
            if used + duration > available:
                continue
            used += duration
            lines.append(f"{duration}m | {item['subject']}: {item['topic']} ({item['priority']})")
        if not pending:
            lines.append("All saved topics are marked completed.")
        elif used == 0:
            lines.append("No complete session fits. Increase the daily minutes.")
        else:
            lines.append(f"Planned: {used} / {available} minutes. Take short breaks between sessions.")
        self.set_text(self.plan_text, "\n".join(lines))

    def set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def load_demo_data(self):
        samples = [
            ("Mathematics", "Quadratic Equations", 3, 5, 2, 5),
            ("Science", "Electricity", 7, 3, 3, 4),
            ("Social Science", "Nationalism in India", 18, 2, 4, 3),
        ]
        self.topics = []
        for index, (subject, topic, days, difficulty, confidence, importance) in enumerate(samples, start=1):
            result = analyse_topic(days, difficulty, confidence, importance)
            self.topics.append({
                "id": index, "subject": subject, "topic": topic, "days": days,
                "difficulty": difficulty, "confidence": confidence,
                "importance": importance, "score": result["score"],
                "priority": result["priority"], "advice": result["advice"],
                "explanation": result["explanation"], "completed": False,
            })
        self.save_topics()

    def load_demo_action(self):
        self.load_demo_data()
        self.refresh_topics()
        if self.topics:
            first = max(self.topics, key=lambda item: item["score"])
            self.tree.selection_set(str(first["id"]))
            self.show_recommendation(first)


def main():
    root = tk.Tk()
    StudyWiseApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
