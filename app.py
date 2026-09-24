import os
import json
import time
import random
import smtplib
import ssl
import re
import mimetypes
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
HISTORY_FILE = DATA_DIR / "history.json"
SAMPLE_CSV_FILE = DATA_DIR / "sample_companies.csv"

app = FastAPI(title="AutoReach - Resume & Cold Email Dispatcher")

# Global campaign state
campaign_state = {
    "is_running": False,
    "should_stop": False,
    "total": 0,
    "processed": 0,
    "sent": 0,
    "failed": 0,
    "current_recipient": "",
    "current_company": "",
    "logs": [],
    "results": [],
    "start_time": None,
    "end_time": None
}

campaign_lock = threading.Lock()

# Default email templates
DEFAULT_TEMPLATES = [
    {
        "id": "tech_general",
        "name": "Software Engineer / Tech Application",
        "subject": "Application for {Role} - {SenderName}",
        "body": """Hi {Name},

I hope this email finds you well.

I am writing to express my strong interest in the {Role} opportunity at {Company}. With a strong background in software engineering, problem solving, and building scalable systems, I am confident I can make an immediate positive impact on your engineering team.

I have attached my updated resume for your review. You can also review my work and recent projects directly.

I would welcome the opportunity to discuss how my skill set and experience align with {Company}'s vision and current roadmap. Would you be open to a brief 10-minute chat this week?

Thank you for your time and consideration.

Warm regards,
{SenderName}
{SenderEmail}"""
    },
    {
        "id": "direct_application",
        "name": "General Job Application (Warm & Professional)",
        "subject": "Inquiry: {Role} Opportunity at {Company} - {SenderName}",
        "body": """Dear {Name},

I hope you are having a productive week.

I am reaching out regarding potential {Role} openings at {Company}. I have been closely following {Company}'s progress and innovative work, and I admire what your team has been building.

Having accumulated hands-on experience and proven results in this domain, I believe my background would be a great fit for your team.

Please find my resume attached to this email. I would appreciate the opportunity to connect and see how I could add value to {Company}.

Looking forward to hearing from you.

Best regards,
{SenderName}
{SenderEmail}"""
    },
    {
        "id": "short_punchy",
        "name": "Short & Punchy (For Founders & Executives)",
        "subject": "{Role} at {Company} - {SenderName}",
        "body": """Hi {Name},

I noticed the impressive work {Company} is doing and wanted to reach out directly regarding {Role} roles.

Briefly about me:
• Strong track record in developing high-impact solutions and driving results
• Fast learner with a bias for action and attention to detail
• Ready to hit the ground running

My resume is attached with details on my experience and accomplishments.

Are you available for a quick 5-minute call sometime this week?

Best,
{SenderName}"""
    },
    {
        "id": "internship_graduate",
        "name": "Internship / Graduate Opportunity",
        "subject": "{Role} Application - {SenderName} - {Company}",
        "body": """Dear {Name},

I hope you are doing well.

I am writing to express my enthusiasm for starting my career with {Company} as a {Role}. I have developed strong foundational skills, completed multiple hands-on projects, and am eager to contribute to your team.

I have attached my resume highlighting my educational background, projects, and technical skills.

I would love to learn more about upcoming opportunities at {Company} and discuss how my energy and dedication can support your goals.

Thank you very much for your time and consideration.

Sincerely,
{SenderName}
{SenderEmail}"""
    }
]

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "sender_name": "",
        "sender_email": "",
        "smtp_provider": "gmail",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "smtp_security": "SSL",
        "smtp_password": "",
        "min_delay": 5,
        "max_delay": 10,
        "daily_limit": 100
    }

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    # keep last 50 campaigns
    history = history[:50]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def create_smtp_connection(host: str, port: int, security: str, user: str, password: str, timeout: int = 10):
    """Establish and authenticate an SMTP connection with intelligent port fallback."""
    clean_pwd = str(password).strip().replace(" ", "")
    clean_user = str(user).strip()
    
    ports_to_try = [(host, port, security)]
    if "gmail" in host.lower():
        if port == 465:
            ports_to_try.append((host, 587, "TLS"))
        elif port == 587:
            ports_to_try.append((host, 465, "SSL"))

    last_err = None
    for h, p, sec in ports_to_try:
        try:
            if sec.upper() == "SSL" or p == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(h, p, context=context, timeout=timeout)
            else:
                server = smtplib.SMTP(h, p, timeout=timeout)
                server.ehlo()
                if sec.upper() == "TLS" or server.has_extn('starttls'):
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
            server.login(clean_user, clean_pwd)
            return server
        except smtplib.SMTPAuthenticationError:
            # Re-raise auth errors immediately
            raise
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err

def find_column(df_columns, candidates):
    cols_lower = {str(c).strip().lower(): c for c in df_columns}
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    # Check partial match
    for cand in candidates:
        for cl, orig in cols_lower.items():
            if cand in cl:
                return orig
    return None

class ConfigModel(BaseModel):
    sender_name: str
    sender_email: str
    smtp_provider: str = "gmail"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_security: str = "SSL"
    smtp_password: str
    min_delay: int = 5
    max_delay: int = 10
    daily_limit: int = 100

class TestConnModel(BaseModel):
    sender_email: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    smtp_password: str

class TestSendModel(BaseModel):
    test_recipient_email: str
    subject: str
    body: str
    resume_filename: Optional[str] = None
    company: str = "Demo Company"
    name: str = "Hiring Manager"
    role: str = "Software Engineer"

class StartCampaignModel(BaseModel):
    subject: str
    body: str
    resume_filename: Optional[str] = None
    recipients: List[Dict[str, Any]]
    min_delay: int = 5
    max_delay: int = 10

# Helper to render email content with placeholders
def render_template(text: str, variables: dict) -> str:
    rendered = text
    for key, value in variables.items():
        pattern = re.compile(r"\{" + re.escape(key) + r"\}", re.IGNORECASE)
        rendered = pattern.sub(str(value if value is not None else ""), rendered)
    return rendered

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Loading AutoReach Application...</h1>")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/config")
async def get_config():
    cfg = load_config()
    # Mask password for display safety
    cfg_copy = dict(cfg)
    if cfg_copy.get("smtp_password"):
        cfg_copy["has_password"] = True
        cfg_copy["smtp_password_masked"] = "••••••••••••••••"
    else:
        cfg_copy["has_password"] = False
        cfg_copy["smtp_password_masked"] = ""
    return cfg_copy

@app.post("/api/config")
async def update_config(data: ConfigModel):
    existing = load_config()
    new_cfg = data.model_dump()
    # If password is blank or mask, preserve existing password
    if not new_cfg.get("smtp_password") or "••••" in new_cfg.get("smtp_password"):
        new_cfg["smtp_password"] = existing.get("smtp_password", "")
    save_config(new_cfg)
    return {"status": "success", "message": "Settings saved successfully"}

@app.get("/api/templates")
async def get_templates():
    return DEFAULT_TEMPLATES

@app.post("/api/test-connection")
async def test_connection(data: TestConnModel):
    password = data.smtp_password
    if not password or "••••" in password:
        cfg = load_config()
        password = cfg.get("smtp_password", "")

    if not password:
        raise HTTPException(status_code=400, detail="Password or App Password is required.")

    try:
        server = create_smtp_connection(
            host=data.smtp_host,
            port=data.smtp_port,
            security=data.smtp_security,
            user=data.sender_email,
            password=password,
            timeout=10
        )
        server.quit()
        return {"status": "success", "message": f"Successfully connected and authenticated with {data.smtp_host}!"}
    except smtplib.SMTPAuthenticationError as e:
        err_msg = str(e)
        if "gmail" in data.smtp_host.lower():
            hint = " (Note for Gmail: You must generate a 16-character App Password at myaccount.google.com/apppasswords. Your regular password will not work)."
        else:
            hint = ""
        raise HTTPException(status_code=400, detail=f"Authentication failed: {err_msg}{hint}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection error: {str(e)}")

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    allowed_exts = {".pdf", ".docx", ".doc"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, or DOC resume files are allowed.")
    
    # Clean filename
    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", file.filename)
    target_path = UPLOADS_DIR / safe_name
    
    contents = await file.read()
    with open(target_path, "wb") as f:
        f.write(contents)
        
    size_kb = round(len(contents) / 1024, 1)
    size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 2)} MB"
    
    return {
        "status": "success",
        "filename": safe_name,
        "original_name": file.filename,
        "size": size_str,
        "path": str(target_path)
    }

@app.get("/api/resumes")
async def list_resumes():
    resumes = []
    if UPLOADS_DIR.exists():
        for p in UPLOADS_DIR.glob("*"):
            if p.is_file() and p.suffix.lower() in [".pdf", ".docx", ".doc"]:
                size_kb = round(p.stat().st_size / 1024, 1)
                size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 2)} MB"
                resumes.append({
                    "filename": p.name,
                    "size": size_str,
                    "modified": p.stat().st_mtime
                })
    resumes.sort(key=lambda x: x["modified"], reverse=True)
    return resumes

@app.post("/api/upload-recipients")
async def upload_recipients(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Only CSV or Excel (.xlsx, .xls) files are accepted.")
    
    temp_path = UPLOADS_DIR / f"temp_{file.filename}"
    contents = await file.read()
    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        if ext == ".csv":
            # Try utf-8, fallback to latin-1
            try:
                df = pd.read_csv(temp_path, encoding="utf-8")
            except Exception:
                df = pd.read_csv(temp_path, encoding="latin-1")
        else:
            df = pd.read_excel(temp_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    finally:
        if temp_path.exists():
            temp_path.unlink()

    # Normalize columns
    email_col = find_column(df.columns, ["email", "e-mail", "mail", "recipient_email", "hr_email", "contact_email"])
    company_col = find_column(df.columns, ["company", "company_name", "organization", "firm", "employer"])
    name_col = find_column(df.columns, ["name", "recruiter", "hr", "contact_name", "contact", "person", "first_name"])
    role_col = find_column(df.columns, ["role", "position", "job_title", "title", "job"])

    if not email_col:
        raise HTTPException(status_code=400, detail="Could not identify an 'Email' column in the file. Please ensure there is a column named 'Email'.")

    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    recipients = []
    seen_emails = set()

    for idx, row in df.iterrows():
        raw_email = str(row[email_col]).strip() if pd.notna(row[email_col]) else ""
        if not raw_email or raw_email.lower() == "nan":
            continue

        raw_company = str(row[company_col]).strip() if company_col and pd.notna(row[company_col]) else "Company"
        raw_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Hiring Team"
        raw_role = str(row[role_col]).strip() if role_col and pd.notna(row[role_col]) else "Software Engineer"

        is_valid = bool(email_regex.match(raw_email))
        is_dup = raw_email.lower() in seen_emails
        seen_emails.add(raw_email.lower())

        # Collect any extra columns as custom attributes
        extra_data = {}
        for col in df.columns:
            if col not in [email_col, company_col, name_col, role_col]:
                val = str(row[col]).strip() if pd.notna(row[col]) else ""
                extra_data[str(col)] = val

        recipients.append({
            "id": idx + 1,
            "email": raw_email,
            "company": raw_company,
            "name": raw_name,
            "role": raw_role,
            "valid": is_valid,
            "duplicate": is_dup,
            "selected": is_valid and not is_dup,
            "extra": extra_data
        })

    valid_count = sum(1 for r in recipients if r["valid"] and not r["duplicate"])
    return {
        "status": "success",
        "total_rows": len(recipients),
        "valid_count": valid_count,
        "filename": file.filename,
        "recipients": recipients
    }

@app.get("/api/download-sample-csv")
async def download_sample_csv():
    if not SAMPLE_CSV_FILE.exists():
        content = "Company,Name,Email,Role,Notes\nGoogle,Sundar Pichai,example-hr@company.com,Software Engineer,Silicon Valley\n"
        with open(SAMPLE_CSV_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    return FileResponse(
        SAMPLE_CSV_FILE,
        media_type="text/csv",
        filename="job_companies_template.csv"
    )

def build_email_message(sender_name: str, sender_email: str, recipient_email: str, subject: str, body_text: str, resume_path: Optional[Path] = None):
    msg = MIMEMultipart("mixed")
    msg["From"] = f'"{sender_name}" <{sender_email}>' if sender_name else sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    
    # Body (convert line breaks to HTML for better readability or include both plain and html)
    alt_part = MIMEMultipart("alternative")
    plain_part = MIMEText(body_text, "plain", "utf-8")
    
    # Simple HTML conversion preserving paragraphs and linebreaks
    html_content = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, sans-serif; font-size: 15px; line-height: 1.6; color: #222;">
{html_content}
</body>
</html>"""
    html_part = MIMEText(html_body, "html", "utf-8")
    alt_part.attach(plain_part)
    alt_part.attach(html_part)
    msg.attach(alt_part)

    # Attach resume if specified
    if resume_path and resume_path.exists():
        with open(resume_path, "rb") as f:
            data = f.read()
        part = MIMEApplication(data, Name=resume_path.name)
        part["Content-Disposition"] = f'attachment; filename="{resume_path.name}"'
        msg.attach(part)

    return msg

@app.post("/api/send-test")
async def send_test_email(data: TestSendModel):
    cfg = load_config()
    sender_name = cfg.get("sender_name", "")
    sender_email = cfg.get("sender_email", "")
    password = cfg.get("smtp_password", "")
    host = cfg.get("smtp_host", "smtp.gmail.com")
    port = int(cfg.get("smtp_port", 465))
    security = cfg.get("smtp_security", "SSL")

    if not sender_email or not password:
        raise HTTPException(status_code=400, detail="Sender email and App Password must be configured in Settings first.")

    resume_path = (UPLOADS_DIR / data.resume_filename) if data.resume_filename else None

    # Render placeholders
    vars_dict = {
        "Company": data.company,
        "Name": data.name,
        "Role": data.role,
        "SenderName": sender_name or "Applicant",
        "SenderEmail": sender_email
    }
    rendered_subject = render_template(data.subject, vars_dict)
    rendered_body = render_template(data.body, vars_dict)

    try:
        server = create_smtp_connection(host, port, security, sender_email, password, timeout=15)
        msg = build_email_message(sender_name, sender_email, data.test_recipient_email, rendered_subject, rendered_body, resume_path)
        server.send_message(msg)
        server.quit()
        return {
            "status": "success",
            "message": f"Test email sent successfully to {data.test_recipient_email}! Check your inbox (and spam/promotions folder)."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send test email: {str(e)}")

def campaign_worker(data: StartCampaignModel, cfg: dict):
    global campaign_state
    
    sender_name = cfg.get("sender_name", "")
    sender_email = cfg.get("sender_email", "")
    password = cfg.get("smtp_password", "")
    host = cfg.get("smtp_host", "smtp.gmail.com")
    port = int(cfg.get("smtp_port", 465))
    security = cfg.get("smtp_security", "SSL")

    resume_path = (UPLOADS_DIR / data.resume_filename) if data.resume_filename else None

    recipients = [r for r in data.recipients if r.get("selected", True)]
    
    with campaign_lock:
        campaign_state["is_running"] = True
        campaign_state["should_stop"] = False
        campaign_state["total"] = len(recipients)
        campaign_state["processed"] = 0
        campaign_state["sent"] = 0
        campaign_state["failed"] = 0
        campaign_state["logs"] = []
        campaign_state["results"] = []
        campaign_state["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        campaign_state["end_time"] = None

    server = None

    def get_server():
        nonlocal server
        if server is None:
            server = create_smtp_connection(host, port, security, sender_email, password, timeout=20)
        else:
            try:
                status = server.noop()[0]
                if status != 250:
                    server = create_smtp_connection(host, port, security, sender_email, password, timeout=20)
            except Exception:
                try:
                    server.quit()
                except Exception:
                    pass
                server = create_smtp_connection(host, port, security, sender_email, password, timeout=20)
        return server

    for idx, r in enumerate(recipients):
        with campaign_lock:
            if campaign_state["should_stop"]:
                campaign_state["logs"].append({
                    "time": time.strftime("%H:%M:%S"),
                    "type": "warning",
                    "text": "Campaign stopped by user."
                })
                break
            campaign_state["current_recipient"] = r["email"]
            campaign_state["current_company"] = r.get("company", "")

        target_email = r["email"].strip()
        comp = r.get("company", "Company")
        name = r.get("name", "Hiring Team")
        role = r.get("role", "Software Engineer")

        # Variables for substitution
        vars_dict = {
            "Company": comp,
            "Name": name,
            "Role": role,
            "SenderName": sender_name or "Applicant",
            "SenderEmail": sender_email
        }
        # Add any extra columns
        if "extra" in r and isinstance(r["extra"], dict):
            for k, v in r["extra"].items():
                vars_dict[k] = v

        sub = render_template(data.subject, vars_dict)
        body = render_template(data.body, vars_dict)

        result_entry = {
            "email": target_email,
            "company": comp,
            "name": name,
            "role": role,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "error": None
        }

        try:
            active_server = get_server()
            msg = build_email_message(sender_name, sender_email, target_email, sub, body, resume_path)
            active_server.send_message(msg)
            
            result_entry["status"] = "sent"
            with campaign_lock:
                campaign_state["sent"] += 1
                campaign_state["processed"] += 1
                campaign_state["logs"].append({
                    "time": time.strftime("%H:%M:%S"),
                    "type": "success",
                    "text": f"[{idx+1}/{len(recipients)}] Sent to {name} at {comp} ({target_email})"
                })
                campaign_state["results"].append(result_entry)

        except Exception as e:
            # If failed, attempt reconnect once
            try:
                server = None
                active_server = get_server()
                msg = build_email_message(sender_name, sender_email, target_email, sub, body, resume_path)
                active_server.send_message(msg)
                
                result_entry["status"] = "sent"
                with campaign_lock:
                    campaign_state["sent"] += 1
                    campaign_state["processed"] += 1
                    campaign_state["logs"].append({
                        "time": time.strftime("%H:%M:%S"),
                        "type": "success",
                        "text": f"[{idx+1}/{len(recipients)}] Sent to {name} at {comp} ({target_email}) [retried]"
                    })
                    campaign_state["results"].append(result_entry)
            except Exception as e2:
                err_str = str(e2)
                result_entry["status"] = "failed"
                result_entry["error"] = err_str
                with campaign_lock:
                    campaign_state["failed"] += 1
                    campaign_state["processed"] += 1
                    campaign_state["logs"].append({
                        "time": time.strftime("%H:%M:%S"),
                        "type": "error",
                        "text": f"[{idx+1}/{len(recipients)}] Failed to send to {comp} ({target_email}): {err_str}"
                    })
                    campaign_state["results"].append(result_entry)

        # Delay before next email to protect account reputation
        if idx < len(recipients) - 1:
            delay = random.randint(data.min_delay, max(data.min_delay, data.max_delay))
            with campaign_lock:
                if campaign_state["should_stop"]:
                    break
            time.sleep(delay)

    if server:
        try:
            server.quit()
        except Exception:
            pass

    with campaign_lock:
        campaign_state["is_running"] = False
        campaign_state["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        campaign_state["logs"].append({
            "time": time.strftime("%H:%M:%S"),
            "type": "info",
            "text": f"Campaign finished. Total: {campaign_state['processed']} | Sent: {campaign_state['sent']} | Failed: {campaign_state['failed']}"
        })
        
        # Save to history
        save_history({
            "start_time": campaign_state["start_time"],
            "end_time": campaign_state["end_time"],
            "subject": data.subject,
            "resume_filename": data.resume_filename,
            "total": campaign_state["total"],
            "sent": campaign_state["sent"],
            "failed": campaign_state["failed"],
            "results": campaign_state["results"]
        })

@app.post("/api/start-campaign")
async def start_campaign(data: StartCampaignModel, background_tasks: BackgroundTasks):
    global campaign_state
    
    with campaign_lock:
        if campaign_state["is_running"]:
            raise HTTPException(status_code=400, detail="A campaign is already running.")

    cfg = load_config()
    if not cfg.get("sender_email") or not cfg.get("smtp_password"):
        raise HTTPException(status_code=400, detail="Please configure and save your Sender Email & Password in Settings first.")

    recipients = [r for r in data.recipients if r.get("selected", True)]
    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipients selected.")

    # Start thread
    t = threading.Thread(target=campaign_worker, args=(data, cfg), daemon=True)
    t.start()

    return {"status": "success", "message": f"Campaign started for {len(recipients)} companies!"}

@app.post("/api/stop-campaign")
async def stop_campaign():
    global campaign_state
    with campaign_lock:
        if campaign_state["is_running"]:
            campaign_state["should_stop"] = True
            return {"status": "success", "message": "Stopping campaign after current email completes..."}
        else:
            return {"status": "info", "message": "No campaign currently running."}

@app.get("/api/campaign-status")
async def get_campaign_status():
    with campaign_lock:
        return dict(campaign_state)

@app.get("/api/history")
async def get_history():
    return load_history()

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    
    port = 8000
    print(f"==================================================")
    print(f" AutoReach Cold Email Dispatcher is starting...   ")
    print(f" URL: http://localhost:{port}                     ")
    print(f"==================================================")
    
    # Open browser automatically after half a second
    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")
        
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)
