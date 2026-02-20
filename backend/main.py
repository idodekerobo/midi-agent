import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Any
from pydantic_ai import Agent, RunContext, ToolCallPart, AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent, PartStartEvent, PartEndEvent, PartDeltaEvent
from pydantic_ai.messages import ModelMessage, UserPromptPart, BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()

AGENT_WORKSPACE_DIR = Path(__file__).parent / "agent_workspace"
AGENT_WORKSPACE_DIR.mkdir(exist_ok=True)
SKILLS_DIR = Path(__file__).parent / "skills"

gemini_api_key = os.getenv("GOOGLE_API_KEY")
gemini_provider = GoogleProvider(api_key=gemini_api_key)
gemini_3_model = GoogleModel('gemini-3-pro-preview', provider=gemini_provider)
# anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
# sonnet_model = AnthropicModel('claude-sonnet-4-5', provider=AnthropicProvider(api_key=anthropic_api_key))

def get_skills_summary() -> str:
    summary = ["<available_skills>"]

    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir():
            skill_name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"
            summary.append(f"  <skill>")
            summary.append(f"    <name>{skill_name}</name>")
            summary.append(f"    <location>{skill_md.absolute()}</location>")
            summary.append(f"  </skill>")

    summary.append("</available_skills>")
    return "\n".join(summary)

system_prompt = "\n".join([
    "You are a helpful assistant that can analyze music files and create a MIDI file for the song transcribed to piano.",
    "You will receive a music file from a user.",
    "Your job is to create a 2 minute MIDI that represents the entire song in a MIDI file using Piano.",
    "You are able to write code to accomplish that and should use the file system and write code, using the given tools to do so.",
    "You will let the user know what you're doing at each step by telling them ahead of time.",
    f"Your working directory to create files, scripts, and other things to run is {AGENT_WORKSPACE_DIR}. You can only read/write files in that directory.",
    "You have the following tools: read_file, write_file, edit_file, execute_command. execute_command lets you execute a shell command and return the file output.",
    "",
    "Here is your process for creating MIDI (and notation) from a music file:",
    "1. The song will be uploaded automatically as uploaded_audio.mp3. Do not handle upload logic.",
    "2. Create analysis.json (measured features) using a Python script with librosa:",
    "   - Extract tempo (BPM), beat times, onset times, pitch contour (pyin -> MIDI float), and loudness (RMS).",
    "3. Create score.json (monophonic melody) based on analysis.json + the audio:",
    "   - Output must be valid JSON only (no prose/markdown).",
    "   - Melody must be monophonic (no overlapping notes).",
    "   - Use ticks_per_beat=480, time_signature=4/4 unless strong evidence otherwise, quantize to a 1/16 grid.",
    "4. Deterministically render score.musicxml from score.json using code (no LLM for rendering):",
    "   - Divisions must equal ticks_per_beat (480).",
    "   - Fill gaps with rests so each measure sums correctly.",
    "5. Deterministically render output.mid from score.json using mido (piano):",
    "   - Set tempo + time signature meta messages.",
    "   - Set instrument with program_change program=0 (Acoustic Grand Piano) on channel 0.",
    "6. Execute your scripts using execute_command and confirm that analysis.json, score.json, score.musicxml, and output.mid were created.",
    "7. Briefly summarize detected tempo and a short preview of the melody (first few notes) for the user.",
    "",
    "IMPORTANT:",
    "- Use librosa for numerical timing/pitch measurements; do not rely on pure audio guessing for tempo/onsets/pitch.",
    "- Do not install packages; librosa and mido are already installed.",
    "",
    "Here are the following skills you have. When you need to use that skill, use the 'read_file' tool on the location provided to get the full skill definition.",
    get_skills_summary(),
])

agent = Agent(gemini_3_model, system_prompt=system_prompt)
# agent = Agent(sonnet_model, system_prompt=system_prompt)

import subprocess

def validate_path(relative_path: str, allowed_dirs: List[Path]) -> Path:
    """
    Ensure the path is within one of the allowed directories.
    Prevents directory traversal attacks.
    """
    try:
        p = Path(relative_path)
        if p.is_absolute():
            resolved_path = p.resolve()
        else:
            resolved_path = None
            for base in allowed_dirs:
                potential_path = (base / relative_path).resolve()
                try:
                    potential_path.relative_to(base)
                    resolved_path = potential_path
                    break
                except ValueError:
                    continue
            
            if not resolved_path:
                resolved_path = (allowed_dirs[0] / relative_path).resolve()

        for base in allowed_dirs:
            try:
                resolved_path.relative_to(base)
                return resolved_path
            except ValueError:
                continue
        
        allowed_names = ", ".join([d.name for d in allowed_dirs])
        raise ValueError(f"Path '{relative_path}' is outside allowed directories: {allowed_names}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Invalid path: {relative_path}")

# TODO: why do i need the process tool? how does it make the agent better? 
# TODO: re-write these to only use the working directory and sub-paths under the cwd
@agent.tool
async def read_file(ctx: RunContext[None], path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        safe_path = validate_path(path, [AGENT_WORKSPACE_DIR, SKILLS_DIR])
        return safe_path.read_text()
    except FileNotFoundError:
        return f"Error: File '{path}' not found"
    except ValueError as e:
        return f"Error: {str(e)}"

@agent.tool
async def write_file(ctx: RunContext[None], path: str, content: str) -> str:
    """Create or overwrite a file with content."""
    try:
        safe_path = validate_path(path, [AGENT_WORKSPACE_DIR])
        # Create parent directories if they don't exist
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content)
        return f"Successfully wrote to '{safe_path}'"
    except ValueError as e:
        return f"Error: {str(e)}"

@agent.tool
async def edit_file(ctx: RunContext[None], path: str, old_str: str, new_str: str) -> str:
    """Replace text in a file."""
    try:
        safe_path = validate_path(path, [AGENT_WORKSPACE_DIR])
        content = safe_path.read_text()
        new_content = content.replace(old_str, new_str)
        safe_path.write_text(new_content)
        return f"Updated '{safe_path}'"
    except FileNotFoundError:
        return f"Error: File '{path}' not found"
    except ValueError as e:
        return f"Error: {str(e)}"

@agent.tool
async def execute_command(ctx: RunContext[None], command: str) -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(AGENT_WORKSPACE_DIR),  # Run commands FROM the workspace
            timeout=30
        )
        return f"Exit Code: {result.returncode}\nOutput: {result.stdout}\nError: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (exceeded 30 seconds)"
    except Exception as e:
        return f"Error executing command: {str(e)}"

class ChatRequest(BaseModel):
    message: str = ""
    history: List[Any] = []
    file_data: str | None = None
    media_type: str | None = "audio/mpeg"

@app.get("/")
async def root():
    return {"message": "hello from fast api"}

@app.post("/chat")
async def chat(
    message: str = Form(...),
    history_json: str = Form("[]"),
    file: UploadFile = File(None)
):
    history = json.loads(history_json)
    
    # Prepare multimodal parts
    parts = []
    
    if file:
        audio_bytes = await file.read()
        # Save to workspace for skills
        audio_filename = "uploaded_audio.mp3" # TODO: use original name or a uuid
        audio_path = AGENT_WORKSPACE_DIR / audio_filename
        audio_path.write_bytes(audio_bytes)
        
        # Add as a binary part for Gemini's multimodal understanding
        parts.append(BinaryContent(data=audio_bytes, media_type=file.content_type or "audio/mpeg"))

    async def event_generator():
        prompt = [message] + parts if parts else message
        async for event in agent.run_stream_events(prompt, message_history=history):
            print(f'\nagent event: {type(event).__name__}')
            print(f'{event}\n\n')

            event_type = type(event).__name__

            if isinstance(event, AgentRunResultEvent):
                yield f"data: {json.dumps({'type': 'final', 'content': event.result.output, 'new_history': []})}\n\n"
            
            elif event_type == "PartDeltaEvent":
                if hasattr(event, 'delta') and hasattr(event.delta, 'content'):
                    yield f"data: {json.dumps({'type': 'delta', 'content': event.delta.content})}\n\n"
            
            elif event_type == "FunctionToolCallEvent":
                yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': event.part.tool_name, 'args': event.part.args})}\n\n"

            elif event_type == "FunctionToolResultEvent":
                yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': event.result.tool_name, 'content': str(event.result.content)})}\n\n"

            elif event_type == "PartStartEvent":
                content = getattr(event.part, 'content', None)
                tool_name = getattr(event.part, 'tool_name', None)
                yield f"data: {json.dumps({'type': 'part_start', 'content': content, 'tool_name': tool_name})}\n\n"

            elif event_type == "PartEndEvent":
                content = getattr(event.part, 'content', None)
                tool_name = getattr(event.part, 'tool_name', None)
                yield f"data: {json.dumps({'type': 'part_end', 'content': content, 'tool_name': tool_name})}\n\n"

            else:
                yield f"data: {json.dumps({'type': 'event', 'event': str(event)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
