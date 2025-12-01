import pandas as pd
import os

# CONFIGURATION
# Pointing directly to your specific trace file
TRACE_FILE_PATH = "os_logs/os_trace_20251201_012410.csv"
OUTPUT_HTML = "trace_viewer.html"

def generate_html():
    # 1. Load Data
    if not os.path.exists(TRACE_FILE_PATH):
        print(f"❌ Error: File not found at {TRACE_FILE_PATH}")
        return

    print(f"Reading log: {TRACE_FILE_PATH}")
    df = pd.read_csv(TRACE_FILE_PATH)

    # 2. Start HTML Construction
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agentic-ExP Trace Viewer</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #e5ddd5; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; background-color: #efe7dd; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); overflow: hidden; }
            .header { background-color: #075e54; color: white; padding: 15px; text-align: center; font-size: 1.2em; font-weight: bold; }
            
            .session-block { border-bottom: 4px solid #ccc; padding-bottom: 20px; margin-bottom: 20px; background-color: #fff; }
            .session-header { background-color: #128c7e; color: white; padding: 10px 15px; font-size: 0.95em; position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; }
            
            .chat-box { padding: 15px; display: flex; flex-direction: column; gap: 15px; }
            
            .message { max-width: 85%; padding: 12px; border-radius: 8px; position: relative; font-size: 0.95em; line-height: 1.5; box-shadow: 0 1px 2px rgba(0,0,0,0.15); }
            
            /* Reasoning (Internal Monologue) - White/Gray */
            .msg-reasoning { align-self: flex-start; background-color: #ffffff; border-top-left-radius: 0; border: 1px solid #ddd; }
            .msg-reasoning::before { content: "🧠 THOUGHT"; display: block; font-size: 0.75em; color: #666; margin-bottom: 6px; font-weight: bold; letter-spacing: 0.5px; }
            
            /* SQL Action - Light Green */
            .msg-action { align-self: flex-end; background-color: #dcf8c6; border-top-right-radius: 0; font-family: "Consolas", monospace; font-size: 0.9em; }
            .msg-action::before { content: "⚡ SQL COMMAND"; display: block; font-size: 0.75em; color: #075e54; margin-bottom: 6px; font-weight: bold; letter-spacing: 0.5px; }
            
            /* System Output - Dark Terminal Style */
            .msg-system { align-self: center; background-color: #2b2b2b; color: #efefef; font-family: "Consolas", monospace; font-size: 0.85em; width: 95%; border-radius: 6px; border-left: 5px solid #ff9800; }
            .msg-system::before { content: "> TERMINAL OUTPUT"; display: block; font-size: 0.75em; color: #888; margin-bottom: 6px; border-bottom: 1px solid #444; padding-bottom: 4px; }

            .latency-tag { position: absolute; bottom: -20px; right: 5px; font-size: 0.7em; color: #888; font-style: italic; }
            .step-num { font-weight: bold; background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">Experiment Trace Logs</div>
    """

    # 3. Group by Session for readable flows
    # We define a custom order if needed, or just iterate groups
    grouped = df.groupby('Session_UUID')
    
    for session_id, group in grouped:
        # Extract Session Metadata (Variant/Model) from the first row of trace if available, 
        # otherwise we just show UUID. (Trace file usually doesn't have Variant col, metrics file does).
        # We will just show UUID and Row Count.
        step_count = len(group)
        
        html_content += f"""
        <div class="session-block">
            <div class="session-header">
                <span>Session: {session_id}</span>
                <span class="step-num">{step_count} Steps</span>
            </div>
            <div class="chat-box">
        """
        
        for _, row in group.iterrows():
            # Clean up Tool Output which might have pipes | from CSV formatting
            tool_out = str(row['Tool_Output']).replace('|', '<br>')
            
            # Step 1: Reasoning Bubble
            html_content += f"""
            <div class="message msg-reasoning">
                {row['Reasoning']}
                <span class="latency-tag">{row['Latency_ms']}ms</span>
            </div>
            """
            
            # Step 2: Action Bubble
            html_content += f"""
            <div class="message msg-action">
                {row['SQL_Command']}
            </div>
            """
            
            # Step 3: System Output Bubble
            html_content += f"""
            <div class="message msg-system">
                {tool_out}
            </div>
            """
            
        html_content += "</div></div>"

    # 4. Close HTML
    html_content += """
        </div>
    </body>
    </html>
    """

    # 5. Write to file
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ Generated '{OUTPUT_HTML}'. Open it in your browser to view the chat replay!")

if __name__ == "__main__":
    generate_html()