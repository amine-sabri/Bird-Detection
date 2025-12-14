import os
import sys
import json
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager, AsyncExitStack
import base64
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from groq import AsyncGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")
MCP_SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT")


groq_client = AsyncGroq(api_key=GROQ_API_KEY)

sessions_store: Dict[str, Dict] = {}

mcp_session = None
mcp_exit_stack = None
mcp_tools = []

# ==================== MODELS ====================

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    image_path: Optional[str] = None

class SessionCreate(BaseModel):
    session_name: Optional[str] = "New Session"
    system_prompt: Optional[str] = None

# ==================== MCP CLIENT ====================

async def initialize_mcp():
    """Initialise la connexion MCP au démarrage"""
    global mcp_session, mcp_exit_stack, mcp_tools
    
    try:
        print("🔌 Initialisation de la connexion MCP...")
        print(f"📂 Script MCP: {MCP_SERVER_SCRIPT}")
        
        if not os.path.exists(MCP_SERVER_SCRIPT):
            print(f"❌ Script MCP introuvable: {MCP_SERVER_SCRIPT}")
            return False
        
        print("✅ Script MCP trouvé")
        
        mcp_exit_stack = AsyncExitStack()
        
        server_params = StdioServerParameters(
            command=sys.executable,       # Python de l'environnement actuel
            args=["-u", MCP_SERVER_SCRIPT],
            env=os.environ.copy()         # garde toutes les variables d'environnement du venv
        )
        
        print("🚀 Lancement du processus serveur MCP...")
        
        stdio_transport = await asyncio.wait_for(
            mcp_exit_stack.enter_async_context(stdio_client(server_params)),
            timeout=10.0
        )
        print("✅ Transport stdio créé")
        
        print("🔗 Création de la session MCP...")
        mcp_session = await asyncio.wait_for(
            mcp_exit_stack.enter_async_context(
                ClientSession(stdio_transport[0], stdio_transport[1])
            ),
            timeout=10.0
        )
        print("✅ Session MCP créée")
        
        print("⚡ Initialisation de la session...")
        await asyncio.wait_for(mcp_session.initialize(), timeout=60.0)
        print("✅ Session initialisée")
        
        print("📋 Récupération de la liste des outils...")
        tools_result = await asyncio.wait_for(mcp_session.list_tools(), timeout=10.0)
        mcp_tools = tools_result.tools
        
        print(f"✅ MCP connecté avec {len(mcp_tools)} outils:")
        for tool in mcp_tools:
            print(f"   - {tool.name}: {tool.description}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur MCP : {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def cleanup_mcp():
    """Nettoie les ressources MCP"""
    global mcp_exit_stack, mcp_session
    if mcp_exit_stack:
        print("🧹 Nettoyage des ressources MCP...")
        try:
            await mcp_exit_stack.aclose()
            print("✅ Ressources MCP libérées")
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage: {e}")
    mcp_session = None
    mcp_exit_stack = None

async def call_mcp_tool(tool_name: str, arguments: dict):
    """Appelle un outil MCP"""
    try:
        if not mcp_session:
            return {"status": "error", "message": "MCP non initialisé"}
        
        print(f"🔧 Appel de l'outil MCP: {tool_name} avec arguments: {arguments}")
        result = await mcp_session.call_tool(tool_name, arguments)
        
        if result.content:
            for content in result.content:
                if hasattr(content, 'text'):
                    return json.loads(content.text)
        
        return {"status": "error", "message": "Aucun résultat"}
        
    except Exception as e:
        print(f"❌ Erreur MCP tool : {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def convert_mcp_tools_to_groq_format():
    """Convertit les outils MCP au format Groq/OpenAI."""
    groq_tools = []
    
    for tool in mcp_tools:
        properties = {}
        required = []
        
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            schema = tool.inputSchema
            if 'properties' in schema:
                properties = schema['properties']
            if 'required' in schema:
                required = schema['required']
        
        groq_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        groq_tools.append(groq_tool)
    
    return groq_tools

# ==================== GROQ CLIENT AVEC STREAMING ====================

async def chat_with_groq_and_tools_streaming(prompt: str, memory: List[ChatMessage] = None, 
                                              system_prompt: str = None, max_iterations: int = 5):
    """Chat avec Groq en utilisant le function calling natif avec streaming d'événements"""
    try:
        groq_tools = convert_mcp_tools_to_groq_format()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if memory:
            for msg in memory:
                if msg.role == "assistant":
                    messages.append({"role": "assistant", "content": msg.content})
                elif msg.role == "user":
                    messages.append({"role": "user", "content": msg.content})
        
        messages.append({"role": "user", "content": prompt})

        print(f"💬 Envoi à Groq avec {len(groq_tools)} outils...")

        for iteration in range(max_iterations):
            response = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=groq_tools,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            if not assistant_message.tool_calls:
                print("✅ Réponse finale de Groq")
                yield {
                    "type": "final_response",
                    "content": assistant_message.content
                }
                return

            print(f"🛠️ Groq veut utiliser {len(assistant_message.tool_calls)} outil(s)...")
            
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}
                    
                tool_call_id = tool_call.id
                
                # Envoyer l'événement de début d'utilisation d'outil
                yield {
                    "type": "tool_start",
                    "tool_name": function_name,
                    "arguments": function_args
                }
                
                print(f"   📞 Appel: {function_name}({function_args})")
                tool_result = await call_mcp_tool(function_name, function_args)
                print(f"   ✅ Résultat: {tool_result}")

                # Envoyer l'événement de fin d'utilisation d'outil
                yield {
                    "type": "tool_end",
                    "tool_name": function_name,
                    "result": tool_result
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": function_name,
                    "content": json.dumps(tool_result)
                })
        
        yield {
            "type": "final_response",
            "content": "Maximum d'itérations atteint"
        }

    except Exception as e:
        print(f"❌ Erreur Groq : {e}")
        import traceback
        traceback.print_exc()
        yield {
            "type": "error",
            "message": str(e)
        }

# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    print("=" * 70)
    print("🚀 DÉMARRAGE DE L'API BIRD DETECTION (Groq)")
    print("=" * 70)
    
    try:
        print("\n📡 Tentative de connexion au serveur MCP...")
        success = await asyncio.wait_for(initialize_mcp(), timeout=60.0)
        
        if success:
            print("\n" + "=" * 70)
            print("✅ API PRÊTE AVEC MCP CONNECTÉ !")
            print("=" * 70 + "\n")
        else:
            print("\n" + "=" * 70)
            print("⚠️ API DÉMARRÉE SANS MCP")
            print("=" * 70 + "\n")
            
    except asyncio.TimeoutError:
        print("\n" + "=" * 70)
        print("⏱️ TIMEOUT GLOBAL (60s) - API DÉMARRÉE SANS MCP")
        print("=" * 70 + "\n")
    except Exception as e:
        print(f"\n⚠️ Erreur inattendue : {e}")
        print("⚠️ L'API démarre sans MCP\n")
    
    yield
    
    print("\n" + "=" * 70)
    print("👋 ARRÊT DE L'API")
    print("=" * 70)
    await cleanup_mcp()

app = FastAPI(
    title="Bird Detection API - Universal Chat (Groq)",
    description="API universelle avec Groq : une seule route /chat pour texte, images, et chemins",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "https://gckins.gaultcore.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== SESSION MANAGEMENT ====================

def create_session(session_name: str = "New Session", system_prompt: str = None) -> str:
    """Crée une nouvelle session"""
    session_id = str(uuid.uuid4())

    
    default_system_prompt = """Tu es un expert en identification d'oiseaux, extrêmement direct et concis.

Tu as accès aux outils suivants via MCP :
- predict_bird_species : Pour identifier un oiseau à partir d'une image.

INSTRUCTIONS IMPORTANTES :
1. Quand l'utilisateur fournit une image, utilise TOUJOURS l'outil predict_bird_species.
2. Une fois le résultat de 'predict_bird_species' obtenu, ta réponse doit être **extrêmement simple** et se conformer à un format strict :

    - **Si le pourcentage de confiance de la meilleure prédiction est supérieur ou égal à 85%** :
        - Réponds **UNIQUEMENT** la phrase : "C'est un oiseau,  l'espèce est : mention les deux point avant le nom ":" [Nom de l'espèce] sans donner le numero associer avec le nom oiseau ([Pourcentage]%)."
        - Par exemple : "C'est un oiseau, l'espèce est : Mésange bleue (92.5%)."

    - **Si la détection a échoué** (status: error), OU si aucune classe n'est trouvée, OU si le pourcentage de confiance est **inférieur à 85%** :
        - Réponds **UNIQUEMENT** la phrase suivante, en y insérant le pourcentage de confiance le plus élevé obtenu (même s'il est très bas) : 
          "Ce n'est pas un oiseau, ou je ne peux pas l'identifier. Le pourcentage le plus élevé est de [Pourcentage]%."
          Par exemple : "Ce n'est pas un oiseau, ou je ne peux pas l'identifier. Le pourcentage le plus élevé est de 12.5%."

3. Ne t'écarte JAMAIS de ces deux formats de réponse.
"""
    

    sessions_store[session_id] = {
        "id": session_id,
        "name": session_name,
        "created_at": datetime.now().isoformat(),
        "system_prompt": system_prompt or default_system_prompt,
        "memory": []
    }

    return session_id

def get_session(session_id: str) -> Dict:
    """Récupère une session"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return sessions_store[session_id]

def add_to_memory(session_id: str, role: str, content: str):
    """Ajoute un message à la mémoire"""
    if session_id in sessions_store:
        sessions_store[session_id]["memory"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Endpoint racine"""
    return {
        "service": "Bird Detection API - Universal Chat (Groq)",
        "version": "4.0.0",
        "status": "running",
        "ai_provider": "Groq",
        "model": GROQ_MODEL,
        "mcp_connected": mcp_session is not None,
        "available_tools": len(mcp_tools),
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST) - Route universelle pour tout (texte, image, chemin)",
            "chat_stream": "/chat/stream (POST) - Version streaming avec événements d'outils",
            "sessions": "/sessions",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Vérification de santé"""
    return {
        "status": "healthy",
        "ai_provider": "Groq",
        "model": GROQ_MODEL,
        "mcp_status": "connected" if mcp_session else "disconnected",
        "active_sessions": len(sessions_store),
        "available_tools": [tool.name for tool in mcp_tools] if mcp_tools else []
    }

@app.post("/sessions/create")
async def create_new_session(request: SessionCreate):
    """Crée une nouvelle session"""
    session_id = create_session(request.session_name, request.system_prompt)
    return {
        "status": "success",
        "session_id": session_id,
        "session": sessions_store[session_id]
    }

@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Récupère les infos d'une session"""
    session = get_session(session_id)
    return {
        "status": "success",
        "session": session
    }

@app.get("/sessions")
async def list_sessions():
    """Liste toutes les sessions"""
    return {
        "status": "success",
        "total_sessions": len(sessions_store),
        "sessions": list(sessions_store.values())
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Supprime une session"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions_store[session_id]
    return {
        "status": "success",
        "message": f"Session {session_id} deleted"
    }

@app.delete("/sessions/{session_id}/memory")
async def clear_session_memory(session_id: str):
    """Efface la mémoire d'une session"""
    session = get_session(session_id)
    session["memory"] = []
    
    return {
        "status": "success",
        "message": "Memory cleared"
    }

# ==================== ROUTE STREAMING /CHAT/STREAM ====================

@app.post("/chat/stream")
async def chat_stream(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    image_path: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    🌟 ROUTE STREAMING - Envoie les événements d'utilisation d'outils en temps réel
    """
    
    # CRITIQUE : Lire le fichier AVANT d'entrer dans le générateur async
    file_contents = None
    file_name = None
    if file:
        file_name = file.filename
        file_contents = await file.read()
        print(f"📤 Fichier lu en mémoire: {file_name} ({len(file_contents)} bytes)")
    
    async def event_generator():
        try:
            if not mcp_session:
                yield f"data: {json.dumps({'type': 'error', 'message': 'MCP non disponible'})}\n\n"
                return
            
            # Récupérer ou créer une session
            current_session_id = session_id
            if current_session_id:
                session = get_session(current_session_id)
                memory = [ChatMessage(**msg) for msg in session["memory"]]
                sys_prompt = system_prompt or session["system_prompt"]
            else:
                current_session_id = create_session()
                session = get_session(current_session_id)
                memory = []
                sys_prompt = system_prompt or session["system_prompt"]
                yield f"data: {json.dumps({'type': 'session_created', 'session_id': current_session_id})}\n\n"
            
            enriched_message = message
            user_message_for_memory = message
            tool_results_for_prompt = None
            
            # Gestion de l'upload d'image
            if file_contents:
                print(f"📤 Upload d'image détecté: {file_name}")
                user_message_for_memory = f"{message} [Image uploadée: {file_name}]"
                
                yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': 'predict_bird_species', 'arguments': {'source': 'uploaded_image'}})}\n\n"
                
                try:
                    base64_image_str = f"data:image/jpeg;base64,{base64.b64encode(file_contents).decode('utf-8')}"
                    tool_result = await call_mcp_tool(
                        "predict_bird_species", 
                        {"image_source": base64_image_str, "top_k": 5}
                    )
                    
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool_name': 'predict_bird_species', 'result': tool_result})}\n\n"
                    
                    tool_results_for_prompt = tool_result
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool_name': 'predict_bird_species', 'error': str(e)})}\n\n"
                    tool_results_for_prompt = {"status": "error", "message": str(e)}
            
            elif image_path:
                print(f"📂 Chemin d'image détecté: {image_path}")
                
                if os.path.exists(image_path):
                    enriched_message = f"""{message}

[CHEMIN D'IMAGE: {image_path}]
Pour identifier cet oiseau, utilise l'outil predict_bird_species avec ce paramètre :
- image_source: {image_path}

Analyse cette image et fournis des informations détaillées sur l'espèce identifiée."""
                else:
                    enriched_message = f"{message}\n\nATTENTION : Le chemin d'image '{image_path}' n'existe pas."
                
                user_message_for_memory = f"{message} [Chemin: {image_path}]"
            
            # Sauvegarder le message utilisateur
            add_to_memory(current_session_id, "user", user_message_for_memory)
            
            # Si on a pré-analysé l'image
            if tool_results_for_prompt:
                add_to_memory(current_session_id, "tool", json.dumps(tool_results_for_prompt))
                
                enriched_message = f"""
L'utilisateur a envoyé ce message : "{message}"
Et il a uploadé une image. J'ai déjà analysé cette image pour toi.
Voici les résultats de l'outil 'predict_bird_species':
{json.dumps(tool_results_for_prompt, indent=2)}

Ta tâche est de répondre à l'utilisateur en te basant sur ces résultats.
Si la prédiction a réussi (status: success), fournis une analyse détaillée de l'espèce.
Si c'était une erreur (status: error), explique l'erreur gentiment.
"""
                memory = [ChatMessage(**msg) for msg in session["memory"]]
            
            # Streaming des événements
            final_response = ""
            async for event in chat_with_groq_and_tools_streaming(
                prompt=enriched_message,
                memory=memory,
                system_prompt=sys_prompt,
                max_iterations=5
            ):
                if event["type"] == "final_response":
                    final_response = event["content"]
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"
            
            # Sauvegarder la réponse
            add_to_memory(current_session_id, "assistant", final_response)
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            print(f"❌ Erreur dans /chat/stream : {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# ==================== ROUTE /CHAT (VERSION NON-STREAMING) ====================

@app.post("/chat")
async def chat(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    image_path: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    🌟 ROUTE UNIVERSELLE - Version non-streaming (ancienne version)
    """
    try:
        if not mcp_session:
            raise HTTPException(
                status_code=503,
                detail="MCP non disponible. Les outils ne sont pas accessibles."
            )
        
        if session_id:
            session = get_session(session_id)
            memory = [ChatMessage(**msg) for msg in session["memory"]]
            sys_prompt = system_prompt or session["system_prompt"]
        else:
            session_id = create_session()
            session = get_session(session_id)
            memory = []
            sys_prompt = system_prompt or session["system_prompt"]
        
        enriched_message = message
        user_message_for_memory = message
        tool_results_for_prompt = None
        
        if file:
            print(f"📤 Upload d'image détecté: {file.filename}")
            user_message_for_memory = f"{message} [Image uploadée: {file.filename}]"
            
            contents = await file.read()
            
            print("🔧 Appel direct de MCP pour la prédiction...")
            try:
                base64_image_str = f"data:image/jpeg;base64,{base64.b64encode(contents).decode('utf-8')}"
                tool_result = await call_mcp_tool(
                    "predict_bird_species", 
                    {"image_source": base64_image_str, "top_k": 5}
                )
                print(f"✅ Résultat de la prédiction : {tool_result}")
                tool_results_for_prompt = tool_result
            except Exception as e:
                print(f"❌ Erreur lors de l'appel direct: {e}")
                tool_results_for_prompt = {"status": "error", "message": str(e)}
        
        elif image_path:
            print(f"📂 Chemin d'image détecté: {image_path}")
            
            if os.path.exists(image_path):
                enriched_message = f"""{message}

[CHEMIN D'IMAGE: {image_path}]
Pour identifier cet oiseau, utilise l'outil predict_bird_species avec ce paramètre :
- image_source: {image_path}

Analyse cette image et fournis des informations détaillées sur l'espèce identifiée."""
            else:
                enriched_message = f"{message}\n\nATTENTION : Le chemin d'image '{image_path}' n'existe pas."
            
            user_message_for_memory = f"{message} [Chemin: {image_path}]"
        
        else:
            print(f"💬 Chat texte simple")
        
        add_to_memory(session_id, "user", user_message_for_memory)
        
        if tool_results_for_prompt:
            add_to_memory(session_id, "tool", json.dumps(tool_results_for_prompt))
            
            enriched_message = f"""
L'utilisateur a envoyé ce message : "{message}"
Et il a uploadé une image. J'ai déjà analysé cette image pour toi.
Voici les résultats de l'outil 'predict_bird_species':
{json.dumps(tool_results_for_prompt, indent=2)}

Ta tâche est de répondre à l'utilisateur en te basant sur ces résultats.
Si la prédiction a réussi (status: success), fournis une analyse détaillée de l'espèce.
Si c'était une erreur (status: error), explique l'erreur gentiment.
"""
            memory = [ChatMessage(**msg) for msg in session["memory"]]
        
        print(f"\n💬 Envoi du prompt à Groq...")
        
        # Version non-streaming : collecter tous les événements
        final_response = ""
        async for event in chat_with_groq_and_tools_streaming(
            prompt=enriched_message,
            memory=memory,
            system_prompt=sys_prompt,
            max_iterations=5
        ):
            if event["type"] == "final_response":
                final_response = event["content"]
        
        add_to_memory(session_id, "assistant", final_response)
        
        return {
            "status": "success",
            "session_id": session_id,
            "response": final_response,
            "memory_size": len(session["memory"]),
            "input_type": "image_upload" if file else ("image_path" if image_path else "text"),
            "ai_provider": "Groq"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur dans /chat : {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/json")
async def chat_json(request: ChatRequest):
    """Version JSON pure de /chat (pour les cas sans upload d'image)"""
    return await chat(
        message=request.message,
        session_id=request.session_id,
        system_prompt=request.system_prompt,
        image_path=request.image_path,
        file=None
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Lancement de l'API Bird Detection - Universal Chat (Groq)...")
    print(f"📂 Serveur MCP: {MCP_SERVER_SCRIPT}")
    print(f"🤖 Modèle Groq: {GROQ_MODEL}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
