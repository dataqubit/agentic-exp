import os
import time
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load Env
load_dotenv()

# --- GOOGLE SETUP ---
from google import genai
from google.genai import types
gemini_key = os.getenv("GEMINI_API_KEY")
client_google = None
if gemini_key:
    client_google = genai.Client(api_key=gemini_key)

# --- OPENAI SETUP ---
from openai import OpenAI
openai_key = os.getenv("OPENAI_API_KEY")
client_openai = None
if openai_key:
    client_openai = OpenAI(api_key=openai_key)

# 1. Output Schema (Universal)
class OSAction(BaseModel):
    reasoning: str = Field(description="Internal thought process. Analyze the previous result. What is the next logical step?")
    sql_command: str = Field(description="The SQL command to run (SELECT/UPDATE/DELETE).")
    is_fixed: bool = Field(description="Set to True ONLY if you have verified the Service is RUNNING.")

class OSAgent:
    def __init__(self, model_name, persona):
        self.model_name = model_name
        self.provider = "openai" if "gpt" in model_name else "google"
        
        # Validation
        if self.provider == "google" and not client_google:
            raise ValueError("Model requires GEMINI_API_KEY.")
        if self.provider == "openai" and not client_openai:
            raise ValueError("Model requires OPENAI_API_KEY.")

        # Persona Configuration
        if persona == "Junior":
            self.sys_prompt = "You are a Junior SysAdmin. You are helpful but easily confused by error codes. You rely on checking the status of things frequently."
        else:
            self.sys_prompt = "You are a Senior Kernel Engineer. You understand service dependencies, deadlocks, and buffer overflows. You fix root causes."

        # Provider-Specific Fallbacks
        if self.provider == "google":
            self.fallback_model = "gemini-2.5-flash"
        else:
            self.fallback_model = "gpt-4o" 

    def _call_api_robust(self, history, retries=3):
        """
        Dispatches to the correct provider with retry logic.
        """
        delay = 2
        current_model = self.model_name
        
        for attempt in range(retries):
            try:
                # ==========================
                # PATH A: GOOGLE GEMINI
                # ==========================
                if "gemini" in current_model:
                    # Convert history to Gemini format (user/model)
                    gemini_hist = []
                    for h in history:
                        role = "model" if h["role"] == "assistant" else "user"
                        gemini_hist.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))

                    response = client_google.models.generate_content(
                        model=current_model,
                        contents=gemini_hist,
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            response_mime_type="application/json",
                            response_schema=OSAction
                        )
                    )
                    if response.parsed is None: raise ValueError("Gemini Parsing Error")
                    return response.parsed, current_model

                # ==========================
                # PATH B: OPENAI GPT
                # ==========================
                else:
                    # History is already in OpenAI format (system/user/assistant)
                    completion = client_openai.beta.chat.completions.parse(
                        model=current_model,
                        messages=history,
                        temperature=0.1,
                        response_format=OSAction
                    )
                    return completion.choices[0].message.parsed, current_model

            except Exception as e:
                error_msg = str(e)
                print(f"   ⚠️ [{current_model}] Error (Attempt {attempt+1}): {error_msg}")
                
                # Retry logic for network/rate limits
                if any(x in error_msg for x in ["503", "429", "timed out", "Rate limit"]):
                    time.sleep(delay)
                    delay *= 2
                    
                    # Switch to fallback if primary fails repeatedly
                    if attempt >= 1 and current_model != self.fallback_model:
                        # Ensure we switch to the correct provider's fallback
                        if "gemini" in current_model and "gemini" in self.fallback_model:
                            current_model = self.fallback_model
                        elif "gpt" in current_model and "gpt" in self.fallback_model:
                            current_model = self.fallback_model
                else:
                    time.sleep(1)
                    
        return None, current_model

    def repair_system(self, goal, schema_hint, execute_callback, max_steps=12):
        # Initialize History with System Prompt
        self.history = []
        
        # We define a "Universal Context" that works for both providers.
        # OpenAI prefers a dedicated "system" message.
        # Gemini usually takes it in config, but accepts it as first user message too.
        # To keep it unified, we will put instructions in the first USER message.
        
        context = f"""
        SYSTEM INSTRUCTIONS: {self.sys_prompt}
        
        GOAL: {goal}
        ENVIRONMENT: You are interacting with a Simulation OS via SQL.
        SCHEMA: {schema_hint}
        RULES:
        1. Investigate first (SELECT).
        2. Fix issues (UPDATE/DELETE).
        3. If you get an error, read it and fix the root cause (e.g., dependencies).
        """
        
        # Standardized History Format: list of dicts {'role': 'user'|'assistant', 'content': str}
        self.history.append({"role": "user", "content": context})
        
        trace_log = [] 
        steps = 0
        total_latency = 0
        
        print(f"   🤖 {self.provider.upper()} Agent starting repair loop (Max {max_steps})...")

        while steps < max_steps:
            steps += 1
            start = time.time()
            
            # 1. CALL API (Polymorphic)
            action_data, used_model = self._call_api_robust(self.history)
            
            latency = int((time.time() - start) * 1000)
            total_latency += latency

            # 2. HANDLE FAILURES
            if action_data is None:
                error_feedback = "SYSTEM ERROR: Invalid Output Format or API Failure. Please retry."
                self.history.append({"role": "user", "content": error_feedback})
                
                trace_log.append({
                    "step": steps,
                    "reasoning": "API_FAILURE",
                    "sql": "N/A",
                    "tool_output": "API Error",
                    "latency_ms": latency
                })
                continue 

            # 3. EXECUTE
            tool_output = "N/A"
            if not action_data.is_fixed:
                tool_output = execute_callback(action_data.sql_command)
            
            # 4. TRACE
            trace_entry = {
                "step": steps,
                "reasoning": action_data.reasoning,
                "sql": action_data.sql_command,
                "tool_output": tool_output,
                "is_fixed_claim": action_data.is_fixed,
                "latency_ms": latency
            }
            trace_log.append(trace_entry)

            if action_data.is_fixed:
                return "CLAIMED_FIX", steps, total_latency, trace_log

            # 5. UPDATE HISTORY (Standardized)
            # Store Model response
            # Note: For strict OpenAI history, we should theoretically store the tool call structure,
            # but storing it as a text response works fine for this simulation and keeps compatibility with Gemini.
            model_response_text = f"Reasoning: {action_data.reasoning}\nSQL: {action_data.sql_command}"
            self.history.append({"role": "assistant", "content": model_response_text})
            
            # Store Tool output
            user_feedback = f"TERMINAL OUTPUT:\n{tool_output}"
            self.history.append({"role": "user", "content": user_feedback})
            
        return "TIMEOUT", steps, total_latency, trace_log