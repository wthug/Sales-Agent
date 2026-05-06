import os
import csv
import docx
from celery_app import celery_app
from Agent.batch_agent import create_batch_agent

# Initialize the batch agent once per Celery worker
batch_agent = create_batch_agent()


# ---------------------------------------------------------------------------
# File Extraction Helper
# ---------------------------------------------------------------------------

def _extract_rows_from_file(file_path: str) -> list:
    """
    Reads a CSV or DOCX file and returns a list of dicts with
    'item' and 'specification' keys (case-insensitive header match).
    Falls back to positional columns: column 0 = item, column 1 = specification.
    """
    rows = []
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    def _parse_row(headers, cells):
        lower_headers = [str(h).strip().lower() for h in headers]
        cell_map = {
            lower_headers[i]: str(cells[i]).strip()
            for i in range(min(len(lower_headers), len(cells)))
        }
        item = cell_map.get('item', cells[0].strip() if cells else '')
        spec  = cell_map.get('specification', cells[1].strip() if len(cells) > 1 else '')
        return item, spec

    if ext == '.csv':
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = None
            for raw_row in reader:
                if not any(raw_row):        # skip blank lines
                    continue
                if headers is None:
                    headers = raw_row
                    continue
                item, spec = _parse_row(headers, raw_row)
                rows.append({'item': item, 'specification': spec})

    elif ext == '.docx':
        doc = docx.Document(file_path)
        for table in doc.tables:
            headers = None
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if not any(cells):
                    continue
                if headers is None:
                    headers = cells
                    continue
                item, spec = _parse_row(headers, cells)
                rows.append({'item': item, 'specification': spec})

    else:
        print(f"[WARN] Unsupported file type: {ext}")

    return rows


# ---------------------------------------------------------------------------
# Celery Task — Query Mode: Item + Specification → batch_agent → CSV
# ---------------------------------------------------------------------------

@celery_app.task(bind=True)
def process_query_batch_task(self, doc_name: str, user_id, folder_name: str = ""):
    """
    Background task that:
    1. Extracts rows from uploaded CSV / DOCX (Item + Specification columns).
    2. Invokes the batch_agent for each row.
    3. Writes all responses to an output CSV file for download.
    """
    file_path = os.path.join("downloaded_documents", doc_name)
    if not os.path.exists(file_path):
        return {"error": f"File not found: {doc_name}"}

    self.update_state(state='PROGRESS', meta={'message': 'Reading file...'})
    rows = _extract_rows_from_file(file_path)

    if not rows:
        return {
            "error": (
                "No data rows found in the file. "
                "Ensure the file has 'Item' and 'Specification' columns."
            )
        }

    total = len(rows)
    results = []
    fn = folder_name.strip() if folder_name else None

    for idx, row_data in enumerate(rows):
        item = row_data['item']
        spec  = row_data['specification']

        self.update_state(state='PROGRESS', meta={
            'message': f'Processing row {idx + 1}/{total}',
            'current': idx + 1,
            'total': total
        })

        # Build the question and invoke the batch agent
        question = f"Item: {item}\nSpecification: {spec}"
        print(f"\n[Row {idx + 1}/{total}] Question: {question[:80]}...")

        try:
            response = batch_agent.invoke({
                "messages": [{"role": "user", "content": question}],
                "folder_name": fn
            })
            ai_text = response["messages"][-1].content
            print(f"[Row {idx + 1}] ✓ Agent responded ({len(ai_text)} chars)")
        except Exception as e:
            print(f"[Row {idx + 1}] ✗ Agent error: {e}")
            ai_text = f"Error: {str(e)}"

        results.append({
            "Row":           idx + 1,
            "Item":          item,
            "Specification": spec,
            "AI Response":   ai_text
        })

    # Write output CSV (flush row by row to avoid data loss on large batches)
    self.update_state(state='PROGRESS', meta={'message': 'Writing output CSV...'})

    if not os.path.exists("processed_documents"):
        os.makedirs("processed_documents")

    output_filename = f"query_{doc_name.rsplit('.', 1)[0]}.csv"
    output_path = os.path.join("processed_documents", output_filename)

    with open(output_path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=["Row", "Item", "Specification", "AI Response"])
        writer.writeheader()
        for result in results:
            writer.writerow(result)
            f.flush()

    print(f"\n[DONE] Output saved to: {output_path}")

    return {
        "status":      "completed",
        "output_file": output_path,
        "filename":    output_filename
    }
