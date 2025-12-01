import sqlite3
import random
from faker import Faker

fake = Faker()

def setup_virtual_machine(variant="Treatment"):
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    rogue_pid = random.randint(1000, 9999)
    rogue_name = random.choice(['skype.exe', 'game.exe', 'backup.exe'])
    
    # ----------------------------------------------------
    # SCENARIO B: TREATMENT (Friendly / Denormalized)
    # ----------------------------------------------------
    if variant == "Treatment":
        # Table 1: Services (The Goal)
        cursor.execute("CREATE TABLE System_Services (service_name TEXT, status TEXT, port_required INTEGER)")
        cursor.execute("INSERT INTO System_Services VALUES ('Apache_Web_Server', 'STOPPED', 80)")
        cursor.execute("INSERT INTO System_Services VALUES ('SQL_Database', 'RUNNING', 3306)")

        # Table 2: Network (The Telemetry) - HAS NAMES
        cursor.execute("CREATE TABLE Network_Ports (port INTEGER, protocol TEXT, process_name TEXT, status TEXT)")
        cursor.execute(f"INSERT INTO Network_Ports VALUES (80, 'TCP', '{rogue_name}', 'LISTENING')")
        cursor.execute("INSERT INTO Network_Ports VALUES (3306, 'TCP', 'mysqld.exe', 'LISTENING')")
        
    # ----------------------------------------------------
    # SCENARIO A: CONTROL (Technical / Normalized)
    # ----------------------------------------------------
    else:
        # Table 1: Services (The Goal)
        cursor.execute("CREATE TABLE sys_config (svc_name TEXT, state INT, port INT)")
        cursor.execute("INSERT INTO sys_config VALUES ('apache_svc', 0, 80)") # 0=Stop
        
        # Table 2: Netstat (The Conflict - PIDs only)
        cursor.execute("CREATE TABLE net_active (local_port INT, pid INT, status TEXT)")
        cursor.execute(f"INSERT INTO net_active VALUES (80, {rogue_pid}, 'LISTEN')")
        
        # Table 3: Process Table (The Name resolution)
        cursor.execute("CREATE TABLE proc_list (pid INT, image TEXT)")
        cursor.execute(f"INSERT INTO proc_list VALUES ({rogue_pid}, '{rogue_name}')")

    conn.commit()
    return conn

def execute_os_command(conn, query, variant):
    cursor = conn.cursor()
    
    # 1. READ OPERATIONS
    if query.strip().upper().startswith("SELECT") or "PRAGMA" in query.upper():
        try:
            cursor.execute(query)
            if cursor.description:
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
            return "Command executed."
        except Exception as e:
            return f"SQL Error: {e}"

    # 2. WRITE OPERATIONS
    try:
        # --- TREATMENT LOGIC ---
        if variant == "Treatment":
            # Attempt to Start Service
            if "UPDATE System_Services" in query and "RUNNING" in query and "Apache_Web_Server" in query:
                # Check if Port 80 is clear
                cursor.execute("SELECT count(*) FROM Network_Ports WHERE port=80")
                if cursor.fetchone()[0] > 0:
                    return "ERROR 0x800: Port 80 is already in use by another process. Bind failed."
            
            # Attempt to Kill Process
            if "DELETE FROM Network_Ports" in query:
                cursor.execute(query)
                conn.commit()
                return f"Process Terminated. Rows affected: {cursor.rowcount}"

        # --- CONTROL LOGIC ---
        else:
            # Attempt to Start Service
            if "UPDATE sys_config" in query and "state=1" in query.replace(" ", "") and "apache_svc" in query:
                # Check Port 80
                cursor.execute("SELECT count(*) FROM net_active WHERE local_port=80")
                if cursor.fetchone()[0] > 0:
                    return "ERR_SERVICE_START_FAIL: Port 80 is currently in use by another process." 
        
            # Attempt to Kill Process
            if "DELETE FROM" in query:
                cursor.execute(query)
                conn.commit()
                return f"Process Terminated. Rows affected: {cursor.rowcount}"

        # Execute if logic passed
        cursor.execute(query)
        conn.commit()
        return f"SUCCESS. Rows affected: {cursor.rowcount}"
        
    except Exception as e:
        return f"KERNEL ERROR: {e}"