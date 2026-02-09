const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  isThought?: boolean;
}

export interface ChatResponse {
  response: string;
  new_history: unknown[];
}

export async function sendMessage(
  message: string,
  history: unknown[],
  onChunk: (data: any) => void,
  file?: File,
): Promise<void> {
  const formData = new FormData();
  formData.append("message", message);
  formData.append("history_json", JSON.stringify(history));
  
  if (file) {
    formData.append("file", file);
  }

  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok || !response.body) {
    throw new Error(`API error: ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n\n");
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.replace("data: ", "");
        try {
          const data = JSON.parse(jsonStr);
          onChunk(data);
        } catch (error) {
          console.error("Error parsing SSE chunk", error);
        }
      }
    }
  }
}
