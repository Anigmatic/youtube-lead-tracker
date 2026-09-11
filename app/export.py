import csv

import openpyxl

_COLUMNS = [
    ("date", "Date"),
    ("language", "Language"),
    ("name", "Name"),
    ("channel_url", "Channel URL"),
    ("subscriber_count_display", "Subscriber Count"),
    ("avg_views_display", "Avg Views/Video"),
    ("contact_info", "Contact Info"),
    ("fit_assessment", "Fit Assessment"),
    ("fit_reason", "Fit Reason"),
    ("status", "Status"),
    ("outreach_method", "Outreach Method"),
    ("notes", "Notes"),
]


def export_csv(leads: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([label for _, label in _COLUMNS])
        for lead in leads:
            writer.writerow([lead.get(key, "") for key, _ in _COLUMNS])


def export_xlsx(leads: list, path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append([label for _, label in _COLUMNS])
    for lead in leads:
        ws.append([lead.get(key, "") for key, _ in _COLUMNS])
    wb.save(path)
