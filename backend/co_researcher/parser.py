import os
import time
import requests

LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "llx-kxyquEwhrd9z5QeQWtrGeHh2dwbAzqDz34nP1dSh4qo6iAhL")
LLAMAPARSE_BASE_URL = "https://api.cloud.llamaindex.ai/api/v1/parsing"

def parse_pdf(file_bytes: bytes, filename: str) -> str:
    """
    Parse a PDF using LlamaParse API.
    Returns extracted text as markdown.
    """
    headers = {
        "Authorization": f"Bearer {LLAMAPARSE_API_KEY}",
    }

    # Step 1: Upload the file
    files = {
        "file": (filename, file_bytes, "application/pdf"),
    }
    data = {
        "result_type": "markdown",
        "language": "en",
    }

    upload_resp = requests.post(
        f"{LLAMAPARSE_BASE_URL}/upload",
        headers=headers,
        files=files,
        data=data,
        timeout=60
    )
    upload_resp.raise_for_status()
    job_id = upload_resp.json()["id"]

    # Step 2: Poll for completion (max 5 minutes)
    for _ in range(60):
        status_resp = requests.get(
            f"{LLAMAPARSE_BASE_URL}/job/{job_id}",
            headers=headers,
            timeout=30
        )
        status_resp.raise_for_status()
        status = status_resp.json()["status"]

        if status == "SUCCESS":
            break
        elif status == "ERROR":
            raise RuntimeError(f"LlamaParse failed for {filename}: {status_resp.json()}")

        time.sleep(5)
    else:
        raise TimeoutError(f"LlamaParse timed out for {filename}")

    # Step 3: Download result
    result_resp = requests.get(
        f"{LLAMAPARSE_BASE_URL}/job/{job_id}/result/markdown",
        headers=headers,
        timeout=30
    )
    result_resp.raise_for_status()
    return result_resp.json()["markdown"]
