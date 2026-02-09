import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Any
from pydantic_ai import Agent, RunContext, ToolCallPart, AgentRunResultEvent
from pydantic_ai.messages import ModelMessage, UserPromptPart, BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()

AGENT_WORKSPACE_DIR = Path(__file__).parent / "agent_workspace"
AGENT_WORKSPACE_DIR.mkdir(exist_ok=True)
SKILLS_DIR = Path(__file__).parent / "skills"

api_key = os.getenv("GOOGLE_API_KEY")
provider = GoogleProvider(api_key=api_key)
model = GoogleModel('gemini-3-pro-preview', provider=provider)

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
    "You are a helpful assistant that can listen to music files and create midi files.",
    "You are able to write code to accomplish that and should use the file system and write code, using the given tools to do so.",
    "You will let the user know what you're doing at each step by telling them ahead of time.",
    f"Your working directory to create files, scripts, and other things to run is {AGENT_WORKSPACE_DIR}. You can only read/write files in that directory.",
    "You have the following tools: read_file, write_file, edit_file, execute_command. execute_command lets you execute a shell command and return the file output.",
    "",
    "Here is your process for creating midi from a music file:",
    # TODO: finish this
    "1. The song will be uploaded to the agent automatically so you don't need to do anything. Listen to the song using audio understanding. You do not need to install any extra packages or dependencies. Just use your multimodal LLM audio understanding.",
    "2. Identify the main melodies/chords of the song and timestamps. Tell the user what the notes of main melodies and chords are and the timestamps they map too.",
    "3. Use the write_file tool to write a script that makes a midi (.mid) file. Use the execute_command tool to run the script. The midi you make will represent the song based on your understanding of the song. The mido package is already imported and you don't need to install anything else.",
    "Here are the following skills you have. When you need to use that skill, use the 'read_file' tool on the location provided to get the full skill definition.",
    get_skills_summary(),
])

agent = Agent(model, system_prompt=system_prompt)

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

            if isinstance(event, AgentRunResultEvent):
                yield f"data: {json.dumps({'type': 'final', 'content': event.result.output, 'new_history': []})}\n\n"
            elif type(event).__name__ == "PartDeltaEvent":
                if hasattr(event, 'delta') and hasattr(event.delta, 'content'):
                    yield f"data: {json.dumps({'type': 'delta', 'content': event.delta.content})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'event', 'event': str(event)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
