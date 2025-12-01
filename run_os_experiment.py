import pandas as pd
import csv
import os
import uuid
import time
import random
from datetime import datetime
from os_factory import setup_virtual_machine, execute_os_command
from os_agent import OSAgent

# ==========================================
# CONFIGURATION
# ==========================================
N_SESSIONS = 200 # Increased slightly since we have more models
MAX_STEPS = 24

# The "Quad-Core" Model Strategy
MODELS = [
    "gemini-2.5-flash-lite", # Google Efficient
    "gemini-2.5-flash",      # Google Smart
    "gpt-4o-mini",           # OpenAI Efficient
    "gpt-4o"                 # OpenAI Smart
]

VARIANTS = ["Control", "Treatment"]
PERSONAS = ["Junior", "Senior"]

# ==========================================
# LOGGING SETUP
# ==========================================
LOG_DIR = "os_logs"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs(LOG_DIR, exist_ok=True)

METRICS_FILE = os.path.join(LOG_DIR, f"os_metrics_{TIMESTAMP}.csv")
TRACE_FILE = os.path.join(LOG_DIR, f"os_trace_{TIMESTAMP}.csv")

def setup_logging():
    if not os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                "Session_UUID", "Variant", "Persona", "Model", 
                "Outcome", "Steps_Taken", "Is_Actually_Fixed", "Total_Latency_ms"
            ])
        
    if not os.path.exists(TRACE_FILE):
        with open(TRACE_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                "Session_UUID", "Step_Num", "Reasoning", "SQL_Command", 
                "Tool_Output", "Latency_ms"
            ])
    print(f"📂 Experiment Logs initialized in: {LOG_DIR}/")

def log_metric(row):
    with open(METRICS_FILE, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(row)

def log_trace_batch(session_id, trace_data):
    with open(TRACE_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for step in trace_data:
            output_val = step.get('tool_output', step.get('output', 'N/A'))
            lat_val = step.get('latency_ms', step.get('latency', 0))
            
            writer.writerow([
                session_id,
                step['step'],
                step['reasoning'].replace("\n", " "), 
                step['sql'],
                str(output_val).replace("\n", " | "), 
                lat_val
            ])

# ==========================================
# RUN LOGIC
# ==========================================
def run_experiment():
    setup_logging()
    print(f"--- 🔧 STARTING MULTI-PROVIDER EXPERIMENT (N={N_SESSIONS}) ---")
    
    for i in range(1, N_SESSIONS + 1):
        s_id = str(uuid.uuid4())[:8]
        variant = random.choice(VARIANTS)
        persona = random.choice(PERSONAS)
        model = random.choice(MODELS)
        
        print(f"[{i}/{N_SESSIONS}] {persona} ({model}) on {variant} System...", end="", flush=True)
        
        conn = setup_virtual_machine(variant)
        
        def vm_executor(sql):
            return execute_os_command(conn, sql, variant)
        
        if variant == "Treatment":
            hint = """
            Tables: 
            1. System_Services (service_name, status, port_required)
            2. Network_Ports (port, protocol, process_name, status)
            """
            goal = "Start the 'Apache_Web_Server'. It uses Port 80. If it fails, find what is blocking it."
        else:
            hint = """
            Tables: 
            1. sys_config (svc_name, state [0=STOP/1=RUN], port)
            2. net_active (local_port, pid, status)
            3. proc_list (pid, image)
            """
            goal = "Start service 'apache_svc'. It uses Port 80. Ensure state=1."

        # Agent handles the provider logic internally
        agent = OSAgent(model, persona)
        
        outcome, steps, latency, trace_log = agent.repair_system(
            goal, 
            hint, 
            vm_executor, 
            max_steps=MAX_STEPS
        )
        
        cursor = conn.cursor()
        try:
            if variant == "Treatment":
                cursor.execute("SELECT status FROM System_Services WHERE service_name='Apache_Web_Server'")
                row = cursor.fetchone()
                is_fixed = (row and row[0] == 'RUNNING')
            else:
                cursor.execute("SELECT state FROM sys_config WHERE svc_name='apache_svc'")
                row = cursor.fetchone()
                is_fixed = (row and row[0] == 1)
        except Exception as e:
            is_fixed = False
            print(f"Validation Error: {e}")
            
        conn.close() 
        
        print(f" -> {outcome} | Fixed? {is_fixed} | Steps: {steps}")
        
        log_metric([s_id, variant, persona, model, outcome, steps, is_fixed, latency])
        log_trace_batch(s_id, trace_log)
        
        # Slightly longer sleep to be kind to both APIs
        time.sleep(2) 

    print("\n✅ Experiment Complete.")

if __name__ == "__main__":
    run_experiment()