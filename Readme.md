# 🐦 Bird Detection API with MCP

## 📋 Description
API de reconnaissance d'oiseaux basée sur l'IA utilisant :

- **FastAPI** pour l'API REST  
- **Groq** (modèle Qwen3-32B) comme LLM avec *function calling*  
- **MCP (Model Context Protocol)** pour l'intégration du modèle de prédiction  
- **ResNet-50** entraîné sur le dataset CUB-200 (200 espèces d'oiseaux)

L'API permet d'identifier des oiseaux à partir d'images (upload ou chemin de fichier) via un chat conversationnel avec streaming en temps réel.

---

## 🚀 Installation

### 1. Prérequis

- Python 3.8+ jusqu'a Python 3.12 
- Un compte Groq avec API key (https://groq.com)  
- Le modèle **ResNet-50** entraîné (`resnet50_cub.pth`) et le fichier `classes.txt`

### 2. Cloner ou télécharger le projet
```bash
git clone https://github.com/amine-sabri/Bird-Detection.git
cd Bird-Detection
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt # METTEZ À JOUR PIP AVANT D'INSTALLER LES DÉPENDANCES
```

---
## 📦 Structure du projet
```
├── mcp_client.py                # API FastAPI principale avec Groq (orchestrateur + MCP client)
├── mcp_server.py                # Serveur MCP reliant le modèle spécialiste
├── requirements.txt              # Dépendances Python

├── ui/
│   └── chatbot-bird/    Interface utilisateur (web/mobile/chatbot)

├── model/
│   └── resnet50_cub.pth         # Modèle PyTorch ResNet50 (CUB-200)

└── classes.txt                   # Liste des 200 espèces d'oiseaux

```
---

## ⚙️ Configuration

### 1. Configurer l'API Groq
Ouvrez le fichier principal (mcp_client.py) et modifiez :
```python
GROQ_API_KEY = "VOTRE_CLE_API_GROQ_ICI"  # Decommentez et Remplacez par votre clé cette ligne de code
GROQ_MODEL = "qwen/qwen3-32b"  # Ou un autre modèle Groq compatible
```

Alternative : utiliser une variable d'environnement :
```bash
export GROQ_API_KEY="votre_cle_api"
```

### 2. Configurer le chemin du serveur MCP
Modifiez le chemin vers `mcp_server.py` :
```python
MCP_SERVER_SCRIPT = "/chemin/absolu/vers/mcp_server.py"  # Exemple: "/home/user/project/mcp_server.py"
```

---

## 🏃 Lancement

### Démarrer l'API
```bash
python mcp_client.py
```

Ou avec Uvicorn directement :
```bash
uvicorn mcp_client:app --host 0.0.0.0 --port 8000 --reload
```

### Vérifier que tout fonctionne
Ouvrez votre navigateur : [http://localhost:8000](http://localhost:8000)

Vous devriez voir :
```json
{
  "service": "Bird Detection API - Universal Chat (Groq)",
  "status": "running",
  "mcp_connected": true,
  "available_tools": 5
}
```

---

## 📡 Utilisation de l'API

### Documentation interactive
Swagger UI : [http://localhost:8000/docs](http://localhost:8000/docs)

### Endpoints principaux

#### 1. Chat simple (texte)
```bash
curl -X POST http://localhost:8000/chat   -F "message=Bonjour, peux-tu m'aider à identifier un oiseau ?"
```

#### 2. Upload d'image
```bash
curl -X POST http://localhost:8000/chat   -F "message=Quelle espèce d'oiseau est-ce ?"   -F "file=@/chemin/vers/image.jpg"
```

#### 3. Chemin d'image
```bash
curl -X POST http://localhost:8000/chat   -F "message=Identifie cet oiseau"   -F "image_path=/chemin/vers/image.jpg"
```

#### 4. Streaming avec événements d'outils
```bash
curl -X POST http://localhost:8000/chat/stream   -F "message=Analyse cette photo"   -F "file=@bird.jpg"
```

### Gestion des sessions
```bash
# Créer une session
curl -X POST http://localhost:8000/sessions/create   -H "Content-Type: application/json"   -d '{"session_name": "Ma session"}'

# Lister les sessions
curl http://localhost:8000/sessions

# Supprimer une session
curl -X DELETE http://localhost:8000/sessions/{session_id}
```

---

## 🛠️ Dépannage

### Erreur "MCP non disponible"
- Vérifiez que `MCP_SERVER_SCRIPT` pointe vers le bon fichier
- Vérifiez que `mcp_server.py` est accessible
- Consultez les logs au démarrage pour voir les erreurs MCP

### Erreur "Modèle non initialisé"
- Vérifiez que `model/resnet50_cub.pth` existe
- Vérifiez que `classes.txt` existe au même niveau que `mcp_server.py`

### Erreur d'API Groq
- Vérifiez votre clé API Groq
- Vérifiez votre quota/limite de requêtes
- Essayez un autre modèle compatible


---

## 💻 Interface Frontend (Next.js)

Une interface web simple est incluse dans le dossier `ui/chatbot-bird` pour interagir avec l’API via un chatbot.

### 🚀 Installation du frontend

1. Accédez au dossier frontend :
```bash
cd ui/chatbot-bird
```

2. Installez les dépendances :
```bash
npm install
```

3. Démarrez le serveur de développement :
```bash
npm run dev
```

4. Ouvrez votre navigateur à l’adresse :
👉 [http://localhost:3000](http://localhost:3000)

Le chatbot sera accessible et communiquera avec votre API (port 8000 par défaut).

### 🔧 Configuration optionnelle

Si votre API n’est pas sur le même domaine ou port, vous pouvez mettre à jour la variable d’URL de l’API dans votre code frontend (`.env.local` ou un fichier de configuration). Exemple :

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Cela permettra au frontend de communiquer correctement avec l’API FastAPI.

---

## 🤝 Support
Pour toute question ou problème :
- Consultez les logs de l'API
- Vérifiez la documentation Swagger à `/docs`
- Vérifiez que tous les chemins de fichiers sont corrects
