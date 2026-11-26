"""Render the synthesised source texts (synthesis/source) into the PDFs/CSV the factory reads.
Run: python synthesis/build_docs.py"""
import shutil
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "synthesis" / "source"
styles = getSampleStyleSheet()


def to_pdf(md: Path, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    story = []
    for line in md.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            story += [Paragraph(line[2:], styles["Title"]), Spacer(1, 6)]
        elif line[:2].strip().rstrip(".").isdigit() and len(line) < 70:
            story += [Spacer(1, 6), Paragraph(line, styles["Heading3"])]
        else:
            story.append(Paragraph(line.replace("&", "&amp;"), styles["BodyText"]))
    SimpleDocTemplate(str(out), pagesize=A4, title=md.stem).build(story)


PLAN = {
    "demos/hr_policy/docs": {"leave_policy.md": "Leave_Policy_Shore_Staff.pdf", "travel_policy.md": "Travel_and_Expense_Policy.pdf", "conduct_grievance.md": "Code_of_Conduct_and_Grievance.pdf"},
    "demos/hr_policy/docs_v2": {"leave_policy_2027.md": "Leave_Policy_Shore_Staff.pdf", "travel_policy.md": "Travel_and_Expense_Policy.pdf", "conduct_grievance.md": "Code_of_Conduct_and_Grievance.pdf"},
    "demos/ship_spares/docs": {"poseidon_terms.md": "Supplier_Terms_Poseidon_Marine.pdf", "harbourline_terms.md": "Supplier_Terms_Harbourline_Spares.pdf", "procurement_procedure.md": "Spares_Procurement_Procedure.pdf", "spares_catalogue.csv": "spares_catalogue.csv"},
}

if __name__ == "__main__":
    for folder, files in PLAN.items():
        for src, dst in files.items():
            out = ROOT / folder / dst
            if src.endswith(".csv"):
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(SRC / src, out)
            else:
                to_pdf(SRC / src, out)
            print("wrote", out.relative_to(ROOT))
